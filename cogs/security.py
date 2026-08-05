import discord
from discord.ext import commands
from discord import app_commands
from collections import deque
from datetime import datetime, timezone, timedelta

from database.db import get_pool
from utils.embeds import security_embed, error_embed, success_embed
import config


class Security(commands.Cog):
    """Anti-Raid (Massen-Joins) & Anti-Nuke (Massen-Löschungen/Bans) System."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.join_times: deque[datetime] = deque()
        self.channel_deletes: dict[int, deque[datetime]] = {}
        self.role_deletes: dict[int, deque[datetime]] = {}
        self.bans: dict[int, deque[datetime]] = {}
        self.lockdown_active = False

    async def log_event(self, guild: discord.Guild, user: discord.abc.User | None, event_type: str, details: str):
        pool = get_pool()
        await pool.execute(
            "INSERT INTO security_events (guild_id, user_id, event_type, details) VALUES ($1, $2, $3, $4)",
            guild.id, user.id if user else None, event_type, details,
        )
        if config.LOG_CHANNEL_ID:
            channel = guild.get_channel(config.LOG_CHANNEL_ID)
            if channel:
                embed = security_embed(f"Security-Event: {event_type}", details)
                if user:
                    embed.add_field(name="Betroffen", value=f"{user} (`{user.id}`)")
                await channel.send(embed=embed)

    def _prune(self, dq: deque, window_seconds: int):
        now = datetime.now(timezone.utc)
        while dq and (now - dq[0]).total_seconds() > window_seconds:
            dq.popleft()

    # ---------- ANTI-RAID ----------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        now = datetime.now(timezone.utc)
        self.join_times.append(now)
        self._prune(self.join_times, config.ANTIRAID_JOIN_INTERVAL)

        account_age = now - member.created_at
        if account_age < timedelta(days=config.ANTIRAID_MIN_ACCOUNT_AGE_DAYS):
            await self.log_event(
                member.guild, member, "Verdächtiger Join",
                f"Account ist nur {account_age.days} Tage alt (Minimum: {config.ANTIRAID_MIN_ACCOUNT_AGE_DAYS}).",
            )

        if len(self.join_times) >= config.ANTIRAID_JOIN_LIMIT and not self.lockdown_active:
            await self._trigger_lockdown(member.guild)

    async def _trigger_lockdown(self, guild: discord.Guild):
        self.lockdown_active = True
        try:
            everyone = guild.default_role
            for channel in guild.text_channels:
                overwrite = channel.overwrites_for(everyone)
                overwrite.send_messages = False
                await channel.set_permissions(everyone, overwrite=overwrite, reason="Anti-Raid Lockdown")
        except discord.Forbidden:
            pass

        await self.log_event(
            guild, None, "🚨 RAID ERKANNT",
            f"Mehr als {config.ANTIRAID_JOIN_LIMIT} Joins in {config.ANTIRAID_JOIN_INTERVAL}s. Server wurde gesperrt. "
            f"Nutze `/security lockdown-aufheben` um den Server wieder zu öffnen.",
        )

    # ---------- ANTI-NUKE: Channel-Löschungen ----------
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        await self._track_and_punish(
            channel.guild, "channel_delete", self.channel_deletes,
            config.ANTINUKE_CHANNEL_DELETE_LIMIT, config.ANTINUKE_CHANNEL_DELETE_INTERVAL,
            f"Channel `{channel.name}` gelöscht",
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        await self._track_and_punish(
            role.guild, "role_delete", self.role_deletes,
            config.ANTINUKE_ROLE_DELETE_LIMIT, config.ANTINUKE_ROLE_DELETE_INTERVAL,
            f"Rolle `{role.name}` gelöscht",
        )

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        await self._track_and_punish(
            guild, "ban", self.bans,
            config.ANTINUKE_BAN_LIMIT, config.ANTINUKE_BAN_INTERVAL,
            f"{user} wurde gebannt",
        )

    async def _track_and_punish(self, guild: discord.Guild, key: str, store: dict, limit: int, interval: int, detail: str):
        actor = await self._find_actor(guild, key)
        actor_id = actor.id if actor else 0

        dq = store.setdefault(actor_id, deque())
        dq.append(datetime.now(timezone.utc))
        self._prune(dq, interval)

        await self.log_event(guild, actor, key, detail)

        if len(dq) >= limit and actor and actor.id != guild.owner_id:
            try:
                member = guild.get_member(actor.id)
                if member:
                    # Alle gefährlichen Rollen/Berechtigungen entziehen
                    dangerous_roles = [r for r in member.roles if r.permissions.administrator or r.permissions.manage_guild]
                    if dangerous_roles:
                        await member.remove_roles(*dangerous_roles, reason="Anti-Nuke: Massenaktionen erkannt")
                    await guild.ban(member, reason=f"Anti-Nuke: {limit}x {key} in {interval}s", delete_message_days=0)
                await self.log_event(
                    guild, actor, "🚨 ANTI-NUKE AUSGELÖST",
                    f"{actor} hat {limit}+ {key}-Aktionen in {interval}s ausgeführt und wurde gebannt/entwaffnet.",
                )
            except discord.Forbidden:
                await self.log_event(guild, actor, "Anti-Nuke Fehler", "Keine Berechtigung, um zu handeln.")

    async def _find_actor(self, guild: discord.Guild, action_key: str) -> discord.abc.User | None:
        action_map = {
            "channel_delete": discord.AuditLogAction.channel_delete,
            "role_delete": discord.AuditLogAction.role_delete,
            "ban": discord.AuditLogAction.ban,
        }
        try:
            async for entry in guild.audit_logs(limit=1, action=action_map[action_key]):
                return entry.user
        except discord.Forbidden:
            return None
        return None

    # ---------- Befehle ----------
    security_group = app_commands.Group(name="security", description="Sicherheitssystem verwalten")

    @security_group.command(name="lockdown-aufheben", description="Hebt den Anti-Raid-Lockdown auf")
    @app_commands.checks.has_permissions(administrator=True)
    async def lockdown_aufheben(self, interaction: discord.Interaction):
        guild = interaction.guild
        everyone = guild.default_role
        for channel in guild.text_channels:
            overwrite = channel.overwrites_for(everyone)
            overwrite.send_messages = None
            await channel.set_permissions(everyone, overwrite=overwrite, reason="Lockdown aufgehoben")
        self.lockdown_active = False
        await interaction.response.send_message(embed=success_embed("Lockdown aufgehoben", "Der Server ist wieder offen."))

    @security_group.command(name="status", description="Zeigt den aktuellen Sicherheitsstatus")
    @app_commands.checks.has_permissions(administrator=True)
    async def status(self, interaction: discord.Interaction):
        embed = security_embed(
            "Security-Status",
            f"**Lockdown aktiv:** {'Ja' if self.lockdown_active else 'Nein'}\n"
            f"**Anti-Raid:** {config.ANTIRAID_JOIN_LIMIT} Joins / {config.ANTIRAID_JOIN_INTERVAL}s\n"
            f"**Anti-Nuke Channels:** {config.ANTINUKE_CHANNEL_DELETE_LIMIT} / {config.ANTINUKE_CHANNEL_DELETE_INTERVAL}s\n"
            f"**Anti-Nuke Rollen:** {config.ANTINUKE_ROLE_DELETE_LIMIT} / {config.ANTINUKE_ROLE_DELETE_INTERVAL}s\n"
            f"**Anti-Nuke Bans:** {config.ANTINUKE_BAN_LIMIT} / {config.ANTINUKE_BAN_INTERVAL}s",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Security(bot))
