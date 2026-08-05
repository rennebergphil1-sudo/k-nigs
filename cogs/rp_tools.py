import discord
from discord import app_commands
from discord.ext import commands
import random
import re
import io

from database.db import get_pool
from utils.embeds import base_embed, success_embed, error_embed
import config

DICE_PATTERN = re.compile(r"^(\d+)w(\d+)([+-]\d+)?$", re.IGNORECASE)


class RPTools(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="würfel", description="Würfle im Format XwY+Z, z.B. 1w20 oder 3w6+2")
    @app_commands.describe(wurf="z.B. 1w20, 2w6+3")
    async def wuerfel(self, interaction: discord.Interaction, wurf: str = "1w20"):
        match = DICE_PATTERN.match(wurf.strip())
        if not match:
            await interaction.response.send_message(
                embed=error_embed("Ungültiges Format", "Nutze z.B. `1w20` oder `3w6+2`."),
                ephemeral=True,
            )
            return

        count, sides, modifier = match.groups()
        count, sides = int(count), int(sides)
        modifier = int(modifier) if modifier else 0

        if count > 50 or sides > 1000:
            await interaction.response.send_message(
                embed=error_embed("Zu groß", "Maximal 50 Würfel mit je 1000 Seiten."),
                ephemeral=True,
            )
            return

        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls) + modifier

        embed = base_embed(f"🎲 {wurf}", f"**Ergebnis: {total}**")
        embed.add_field(name="Würfe", value=", ".join(str(r) for r in rolls), inline=False)
        if modifier:
            embed.add_field(name="Modifikator", value=f"{modifier:+d}", inline=True)

        await interaction.response.send_message(embed=embed)

    scene_group = app_commands.Group(name="szene", description="RP-Szenen-Channels verwalten")

    @scene_group.command(name="erstellen", description="Erstelle einen neuen RP-Szenen-Channel")
    @app_commands.describe(titel="Titel der Szene", kategorie="Kategorie, in der der Channel erstellt wird")
    async def erstellen(self, interaction: discord.Interaction, titel: str, kategorie: discord.CategoryChannel = None):
        guild = interaction.guild
        safe_name = re.sub(r"[^a-z0-9-]", "-", titel.lower().replace(" ", "-"))[:80]
        channel = await guild.create_text_channel(
            name=f"rp-{safe_name}",
            category=kategorie,
            topic=f"RP-Szene: {titel} | erstellt von {interaction.user}",
        )

        pool = get_pool()
        await pool.execute(
            "INSERT INTO rp_scenes (guild_id, channel_id, title, created_by) VALUES ($1, $2, $3, $4)",
            guild.id, channel.id, titel, interaction.user.id,
        )

        await channel.send(
            embed=success_embed(f"Szene gestartet: {titel}", f"Gestartet von {interaction.user.mention}. Viel Spaß beim Schreiben!")
        )
        await interaction.response.send_message(
            embed=success_embed("Szene erstellt", f"Channel {channel.mention} wurde erstellt.")
        )

    @scene_group.command(name="archivieren", description="Archiviert die aktuelle RP-Szene")
    async def archivieren(self, interaction: discord.Interaction):
        pool = get_pool()
        row = await pool.fetchrow(
            "SELECT id FROM rp_scenes WHERE channel_id=$1 AND archived=FALSE",
            interaction.channel_id,
        )
        if not row:
            await interaction.response.send_message(
                embed=error_embed("Keine Szene", "Dieser Channel ist keine aktive RP-Szene."),
                ephemeral=True,
            )
            return

        await pool.execute("UPDATE rp_scenes SET archived=TRUE WHERE id=$1", row["id"])
        await interaction.channel.edit(name=f"archiv-{interaction.channel.name}")
        await interaction.response.send_message(embed=success_embed("Szene archiviert", "Der Channel wurde als Archiv markiert."))

    @scene_group.command(name="log", description="Exportiere die letzten Nachrichten dieses Channels als Textdatei")
    @app_commands.describe(limit="Wie viele Nachrichten (Standard 200, max 1000)")
    async def log(self, interaction: discord.Interaction, limit: int = 200):
        limit = min(max(limit, 1), 1000)
        await interaction.response.defer(ephemeral=True)

        messages = [msg async for msg in interaction.channel.history(limit=limit, oldest_first=True)]
        lines = []
        for msg in messages:
            if msg.content:
                lines.append(f"[{msg.created_at:%Y-%m-%d %H:%M}] {msg.author.display_name}: {msg.content}")

        if not lines:
            await interaction.followup.send(
                embed=error_embed("Kein Inhalt", "Keine Textnachrichten gefunden."), ephemeral=True
            )
            return

        buffer = io.BytesIO("\n".join(lines).encode("utf-8"))
        file = discord.File(buffer, filename=f"rp-log-{interaction.channel.name}.txt")
        await interaction.followup.send(
            embed=success_embed("Log exportiert", f"{len(lines)} Nachrichten exportiert."),
            file=file,
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(RPTools(bot))
