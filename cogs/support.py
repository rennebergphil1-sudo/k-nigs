import discord
from discord import app_commands
from discord.ext import commands
import os
import random
import asyncio

from database.db import get_pool
from utils.embeds import base_embed, success_embed, error_embed
import config


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Ticket öffnen", style=discord.ButtonStyle.primary, custom_id="open_ticket_button")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog: Support = interaction.client.get_cog("Support")
        await cog.create_ticket(interaction)


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Ticket schließen", style=discord.ButtonStyle.danger, custom_id="close_ticket_button")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog: Support = interaction.client.get_cog("Support")
        await cog.close_ticket(interaction)


class Support(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_clients: dict[int, discord.VoiceClient] = {}

    async def cog_load(self):
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(CloseTicketView())

    @app_commands.command(name="ticket-panel", description="Sendet das Support-Ticket-Panel in diesen Channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticket_panel(self, interaction: discord.Interaction):
        embed = base_embed(
            "📩 Support",
            "Klicke auf den Button unten, um ein privates Support-Ticket zu öffnen. "
            "Ein Team-Mitglied kümmert sich schnellstmöglich um dein Anliegen.",
        )
        await interaction.channel.send(embed=embed, view=TicketPanelView())
        await interaction.response.send_message(embed=success_embed("Panel gesendet", "Das Ticket-Panel wurde gepostet."), ephemeral=True)

    async def create_ticket(self, interaction: discord.Interaction):
        guild = interaction.guild
        pool = get_pool()

        existing = await pool.fetchrow(
            "SELECT channel_id FROM support_tickets WHERE guild_id=$1 AND opened_by=$2 AND status='open'",
            guild.id, interaction.user.id,
        )
        if existing:
            channel = guild.get_channel(existing["channel_id"])
            if channel:
                await interaction.response.send_message(
                    embed=error_embed("Bereits offen", f"Du hast bereits ein offenes Ticket: {channel.mention}"),
                    ephemeral=True,
                )
                return

        category = guild.get_channel(config.SUPPORT_CATEGORY_ID) if config.SUPPORT_CATEGORY_ID else None
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        if config.MOD_ROLE_ID:
            mod_role = guild.get_role(config.MOD_ROLE_ID)
            if mod_role:
                overwrites[mod_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}"[:90],
            category=category,
            overwrites=overwrites,
        )

        await pool.execute(
            "INSERT INTO support_tickets (guild_id, channel_id, opened_by) VALUES ($1, $2, $3)",
            guild.id, channel.id, interaction.user.id,
        )

        embed = base_embed(
            f"Ticket von {interaction.user.display_name}",
            "Beschreib dein Anliegen, ein Team-Mitglied meldet sich gleich. "
            "Solange du im Warteraum-Voice-Channel bist, läuft Musik für dich!",
        )
        await channel.send(content=interaction.user.mention, embed=embed, view=CloseTicketView())

        await interaction.response.send_message(
            embed=success_embed("Ticket erstellt", f"Dein Ticket wurde erstellt: {channel.mention}"),
            ephemeral=True,
        )

    async def close_ticket(self, interaction: discord.Interaction):
        pool = get_pool()
        row = await pool.fetchrow(
            "SELECT id FROM support_tickets WHERE channel_id=$1 AND status='open'",
            interaction.channel_id,
        )
        if not row:
            await interaction.response.send_message(
                embed=error_embed("Kein Ticket", "Dies ist kein aktives Ticket."), ephemeral=True
            )
            return

        await pool.execute(
            "UPDATE support_tickets SET status='closed', closed_at=now() WHERE id=$1", row["id"]
        )
        await interaction.response.send_message(embed=success_embed("Ticket wird geschlossen", "Channel wird in 5 Sekunden gelöscht."))
        await asyncio.sleep(5)
        await interaction.channel.delete(reason="Ticket geschlossen")

    # ---------- Warteraum-Musik ----------
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if not config.WAITING_VOICE_CHANNEL_ID:
            return
        waiting_channel_id = config.WAITING_VOICE_CHANNEL_ID

        # Jemand betritt den Warteraum
        if after.channel and after.channel.id == waiting_channel_id:
            await self._ensure_music_playing(after.channel)

        # Warteraum wurde verlassen -> prüfen ob leer
        if before.channel and before.channel.id == waiting_channel_id:
            if len(before.channel.members) == 0:
                await self._stop_music(before.channel.guild.id)

    async def _ensure_music_playing(self, channel: discord.VoiceChannel):
        guild_id = channel.guild.id
        vc = self.voice_clients.get(guild_id)

        if vc and vc.is_connected():
            if not vc.is_playing():
                self._play_next(vc, guild_id)
            return

        try:
            vc = await channel.connect()
            self.voice_clients[guild_id] = vc
            self._play_next(vc, guild_id)
        except discord.ClientException:
            pass

    def _play_next(self, vc: discord.VoiceClient, guild_id: int):
        track = self._pick_track()
        if not track:
            return

        def after_play(error):
            if error:
                print(f"Player-Fehler: {error}")
            if vc.is_connected():
                self._play_next(vc, guild_id)

        source = discord.FFmpegPCMAudio(track)
        vc.play(discord.PCMVolumeTransformer(source, volume=0.5), after=after_play)

    def _pick_track(self) -> str | None:
        folder = config.MUSIC_FOLDER
        if not os.path.isdir(folder):
            return None
        tracks = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith((".mp3", ".wav", ".ogg"))]
        if not tracks:
            return None
        return random.choice(tracks)

    async def _stop_music(self, guild_id: int):
        vc = self.voice_clients.pop(guild_id, None)
        if vc and vc.is_connected():
            await vc.disconnect()


async def setup(bot: commands.Bot):
    await bot.add_cog(Support(bot))
