import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
from datetime import datetime, timezone, timedelta
import re

from database.db import get_pool
from utils.embeds import base_embed, success_embed, error_embed
from cogs.extras import is_mod

DURATION_PATTERN = re.compile(r"^(\d+)([mhdMHD])$")


def parse_duration(text: str):
    match = DURATION_PATTERN.match(text.strip())
    if not match:
        return None
    amount, unit = int(match.group(1)), match.group(2).lower()
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    return None


class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_id: int):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.children[0].custom_id = f"giveaway:{giveaway_id}"

    @discord.ui.button(label="🎉 Teilnehmen", style=discord.ButtonStyle.success, custom_id="giveaway:placeholder")
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        gw_id = int(button.custom_id.split(":")[1])
        pool = get_pool()

        row = await pool.fetchrow("SELECT ended FROM giveaways WHERE id=$1", gw_id)
        if not row or row["ended"]:
            await interaction.response.send_message(
                embed=error_embed("Vorbei", "Dieses Giveaway ist bereits beendet."), ephemeral=True
            )
            return

        existing = await pool.fetchrow(
            "SELECT 1 FROM giveaway_entries WHERE giveaway_id=$1 AND user_id=$2", gw_id, interaction.user.id
        )
        if existing:
            await pool.execute(
                "DELETE FROM giveaway_entries WHERE giveaway_id=$1 AND user_id=$2", gw_id, interaction.user.id
            )
            await interaction.response.send_message(
                embed=error_embed("Ausgetragen", "Du nimmst nicht mehr teil."), ephemeral=True
            )
        else:
            await pool.execute(
                "INSERT INTO giveaway_entries (giveaway_id, user_id) VALUES ($1, $2)", gw_id, interaction.user.id
            )
            await interaction.response.send_message(
                embed=success_embed("Teilnahme registriert", "Viel Glück! 🍀"), ephemeral=True
            )


class Giveaways(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        pool = get_pool()
        rows = await pool.fetch("SELECT id FROM giveaways WHERE ended=FALSE")
        for row in rows:
            self.bot.add_view(GiveawayView(row["id"]))
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    @app_commands.command(name="giveaway", description="Startet ein Giveaway")
    @app_commands.describe(
        preis="Was verlost wird",
        dauer="Dauer, z.B. 30m, 2h, 1d",
        gewinner="Anzahl der Gewinner (Standard 1)",
    )
    @is_mod()
    async def giveaway(self, interaction: discord.Interaction, preis: str, dauer: str, gewinner: int = 1):
        delta = parse_duration(dauer)
        if not delta:
            await interaction.response.send_message(
                embed=error_embed("Ungültige Dauer", "Nutze z.B. `30m`, `2h` oder `1d`."), ephemeral=True
            )
            return

        ends_at = datetime.now(timezone.utc) + delta
        embed = base_embed(
            f"🎉 Giveaway: {preis}",
            f"Klicke auf **Teilnehmen**, um mitzumachen!\n\n"
            f"**Gewinner:** {gewinner}\n"
            f"**Endet:** <t:{int(ends_at.timestamp())}:R>\n"
            f"**Gehostet von:** {interaction.user.mention}",
        )

        await interaction.response.send_message(embed=embed)
        sent = await interaction.original_response()

        pool = get_pool()
        gw_id = await pool.fetchval(
            """
            INSERT INTO giveaways (guild_id, channel_id, message_id, prize, winners_count, hosted_by, ends_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id
            """,
            interaction.guild_id, interaction.channel_id, sent.id, preis, gewinner, interaction.user.id, ends_at,
        )

        view = GiveawayView(gw_id)
        await sent.edit(view=view)

    @app_commands.command(name="giveaway-beenden", description="Beendet ein Giveaway sofort und zieht Gewinner")
    @app_commands.describe(message_id="Die Nachrichten-ID des Giveaways")
    @is_mod()
    async def giveaway_beenden(self, interaction: discord.Interaction, message_id: str):
        pool = get_pool()
        row = await pool.fetchrow(
            "SELECT id FROM giveaways WHERE message_id=$1 AND ended=FALSE", int(message_id)
        )
        if not row:
            await interaction.response.send_message(
                embed=error_embed("Nicht gefunden", "Kein aktives Giveaway mit dieser Nachrichten-ID."), ephemeral=True
            )
            return
        await interaction.response.send_message(embed=success_embed("Wird beendet", "Giveaway wird ausgewertet..."), ephemeral=True)
        await self._end_giveaway(row["id"])

    @tasks.loop(seconds=30)
    async def check_giveaways(self):
        pool = get_pool()
        rows = await pool.fetch("SELECT id FROM giveaways WHERE ended=FALSE AND ends_at <= now()")
        for row in rows:
            await self._end_giveaway(row["id"])

    @check_giveaways.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    async def _end_giveaway(self, giveaway_id: int):
        pool = get_pool()
        gw = await pool.fetchrow("SELECT * FROM giveaways WHERE id=$1", giveaway_id)
        if not gw or gw["ended"]:
            return

        await pool.execute("UPDATE giveaways SET ended=TRUE WHERE id=$1", giveaway_id)

        entries = await pool.fetch("SELECT user_id FROM giveaway_entries WHERE giveaway_id=$1", giveaway_id)
        guild = self.bot.get_guild(gw["guild_id"])
        channel = guild.get_channel(gw["channel_id"]) if guild else None
        if not channel:
            return

        try:
            message = await channel.fetch_message(gw["message_id"])
        except discord.NotFound:
            message = None

        if not entries:
            result_text = "Niemand hat teilgenommen. 😢"
            winners_mentions = []
        else:
            user_ids = [e["user_id"] for e in entries]
            winners = random.sample(user_ids, min(gw["winners_count"], len(user_ids)))
            winners_mentions = [f"<@{uid}>" for uid in winners]
            result_text = f"Gewinner: {', '.join(winners_mentions)} 🎉"

        embed = success_embed(f"🎉 Giveaway beendet: {gw['prize']}", result_text)
        if message:
            try:
                await message.edit(embed=embed, view=None)
            except discord.Forbidden:
                pass

        await channel.send(
            content=" ".join(winners_mentions) if winners_mentions else None,
            embed=base_embed("Herzlichen Glückwunsch!", f"Ihr habt **{gw['prize']}** gewonnen!") if winners_mentions else None,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaways(bot))
