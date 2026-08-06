import discord
from discord import app_commands
from discord.ext import commands
import random
from datetime import datetime, timezone, timedelta
import math

from database.db import get_pool
from utils.embeds import base_embed, success_embed, error_embed
import config

XP_COOLDOWN_SECONDS = 60
XP_MIN, XP_MAX = 15, 25


def xp_for_level(level: int) -> int:
    # Wächst quadratisch, damit hohe Level wirklich was bedeuten
    return 5 * (level ** 2) + 50 * level + 100


class Leveling(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._cooldowns: dict[tuple[int, int], datetime] = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        key = (message.guild.id, message.author.id)
        now = datetime.now(timezone.utc)
        last = self._cooldowns.get(key)
        if last and (now - last).total_seconds() < XP_COOLDOWN_SECONDS:
            return
        self._cooldowns[key] = now

        pool = get_pool()
        row = await pool.fetchrow(
            "SELECT xp, level FROM user_xp WHERE guild_id=$1 AND user_id=$2",
            message.guild.id, message.author.id,
        )
        gained = random.randint(XP_MIN, XP_MAX)

        if row:
            new_xp = row["xp"] + gained
            level = row["level"]
        else:
            new_xp = gained
            level = 0

        leveled_up = False
        while new_xp >= xp_for_level(level):
            new_xp -= xp_for_level(level)
            level += 1
            leveled_up = True

        await pool.execute(
            """
            INSERT INTO user_xp (guild_id, user_id, xp, level, last_message)
            VALUES ($1, $2, $3, $4, now())
            ON CONFLICT (guild_id, user_id)
            DO UPDATE SET xp=$3, level=$4, last_message=now()
            """,
            message.guild.id, message.author.id, new_xp, level,
        )

        if leveled_up:
            embed = success_embed(
                "🎉 Level Up!",
                f"{message.author.mention} ist jetzt **Level {level}**!",
            )
            try:
                await message.channel.send(embed=embed)
            except discord.Forbidden:
                pass

    @app_commands.command(name="level", description="Zeigt dein Level oder das eines anderen")
    @app_commands.describe(user="Optional: anderes Mitglied")
    async def level(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        pool = get_pool()
        row = await pool.fetchrow(
            "SELECT xp, level FROM user_xp WHERE guild_id=$1 AND user_id=$2",
            interaction.guild_id, target.id,
        )
        if not row:
            await interaction.response.send_message(
                embed=error_embed("Kein XP", f"{target.mention} hat noch keine XP gesammelt."),
                ephemeral=True,
            )
            return

        needed = xp_for_level(row["level"])
        progress_blocks = 10
        filled = math.floor((row["xp"] / needed) * progress_blocks)
        bar = "█" * filled + "░" * (progress_blocks - filled)

        embed = base_embed(f"📊 Level von {target.display_name}", "")
        embed.add_field(name="Level", value=str(row["level"]), inline=True)
        embed.add_field(name="XP", value=f"{row['xp']} / {needed}", inline=True)
        embed.add_field(name="Fortschritt", value=f"`{bar}`", inline=False)
        embed.set_thumbnail(url=target.display_avatar.url)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Zeigt die Top 10 nach XP")
    async def leaderboard(self, interaction: discord.Interaction):
        pool = get_pool()
        rows = await pool.fetch(
            "SELECT user_id, xp, level FROM user_xp WHERE guild_id=$1 ORDER BY level DESC, xp DESC LIMIT 10",
            interaction.guild_id,
        )
        if not rows:
            await interaction.response.send_message(
                embed=error_embed("Leer", "Noch keine XP-Daten vorhanden."), ephemeral=True
            )
            return

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, row in enumerate(rows):
            member = interaction.guild.get_member(row["user_id"])
            name = member.mention if member else f"<@{row['user_id']}>"
            prefix = medals[i] if i < 3 else f"`#{i + 1}`"
            lines.append(f"{prefix} {name} — Level {row['level']} ({row['xp']} XP)")

        embed = base_embed("🏆 XP-Leaderboard", "\n".join(lines))
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))
