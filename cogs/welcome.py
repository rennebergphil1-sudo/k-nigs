import discord
from discord import app_commands
from discord.ext import commands

from database.db import get_pool
from utils.embeds import base_embed, success_embed
from cogs.extras import is_mod


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _get_settings(self, guild_id: int):
        pool = get_pool()
        return await pool.fetchrow("SELECT * FROM guild_settings WHERE guild_id=$1", guild_id)

    @app_commands.command(name="willkommen-setup", description="Richtet die Willkommensnachricht ein")
    @app_commands.describe(
        channel="Channel für die Willkommensnachricht",
        nachricht="Text (Platzhalter: {user} = Mention, {server} = Servername, {membercount} = Mitgliederzahl)",
    )
    @is_mod()
    async def willkommen_setup(self, interaction: discord.Interaction, channel: discord.TextChannel, nachricht: str):
        pool = get_pool()
        nachricht = nachricht.replace("\\n", "\n")
        await pool.execute(
            """
            INSERT INTO guild_settings (guild_id, welcome_channel_id, welcome_message)
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id) DO UPDATE SET welcome_channel_id=$2, welcome_message=$3
            """,
            interaction.guild_id, channel.id, nachricht,
        )
        await interaction.response.send_message(
            embed=success_embed("Eingerichtet", f"Willkommensnachrichten laufen jetzt über {channel.mention}.")
        )

    @app_commands.command(name="abschied-setup", description="Richtet die Abschiedsnachricht ein")
    @app_commands.describe(
        channel="Channel für die Abschiedsnachricht",
        nachricht="Text (Platzhalter: {user} = Name, {server} = Servername, {membercount} = Mitgliederzahl)",
    )
    @is_mod()
    async def abschied_setup(self, interaction: discord.Interaction, channel: discord.TextChannel, nachricht: str):
        pool = get_pool()
        nachricht = nachricht.replace("\\n", "\n")
        await pool.execute(
            """
            INSERT INTO guild_settings (guild_id, leave_channel_id, leave_message)
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id) DO UPDATE SET leave_channel_id=$2, leave_message=$3
            """,
            interaction.guild_id, channel.id, nachricht,
        )
        await interaction.response.send_message(
            embed=success_embed("Eingerichtet", f"Abschiedsnachrichten laufen jetzt über {channel.mention}.")
        )

    def _format(self, text: str, member: discord.Member) -> str:
        return (
            text.replace("{user}", member.mention)
            .replace("{server}", member.guild.name)
            .replace("{membercount}", str(member.guild.member_count))
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        settings = await self._get_settings(member.guild.id)
        if not settings or not settings["welcome_channel_id"] or not settings["welcome_message"]:
            return
        channel = member.guild.get_channel(settings["welcome_channel_id"])
        if not channel:
            return

        embed = base_embed("👋 Willkommen!", self._format(settings["welcome_message"], member))
        embed.set_thumbnail(url=member.display_avatar.url)
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        settings = await self._get_settings(member.guild.id)
        if not settings or not settings["leave_channel_id"] or not settings["leave_message"]:
            return
        channel = member.guild.get_channel(settings["leave_channel_id"])
        if not channel:
            return

        embed = base_embed("👋 Tschüss!", self._format(settings["leave_message"], member))
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
