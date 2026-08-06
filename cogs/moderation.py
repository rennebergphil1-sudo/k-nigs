import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta

from database.db import get_pool
from utils.embeds import base_embed, success_embed, error_embed
from cogs.extras import is_mod


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            msg = error_embed("Keine Berechtigung", "Dafür brauchst du eine Team-Rolle oder Admin-Rechte.")
            if interaction.response.is_done():
                await interaction.followup.send(embed=msg, ephemeral=True)
            else:
                await interaction.response.send_message(embed=msg, ephemeral=True)

    @app_commands.command(name="warn", description="Verwarnt ein Mitglied")
    @app_commands.describe(user="Wer verwarnt wird", grund="Grund für die Verwarnung")
    @is_mod()
    async def warn(self, interaction: discord.Interaction, user: discord.Member, grund: str):
        pool = get_pool()
        await pool.execute(
            "INSERT INTO warnings (guild_id, user_id, moderator_id, reason) VALUES ($1, $2, $3, $4)",
            interaction.guild_id, user.id, interaction.user.id, grund,
        )
        count = await pool.fetchval(
            "SELECT COUNT(*) FROM warnings WHERE guild_id=$1 AND user_id=$2", interaction.guild_id, user.id
        )

        try:
            await user.send(embed=error_embed(f"Verwarnung auf {interaction.guild.name}", grund))
        except discord.Forbidden:
            pass

        await interaction.response.send_message(
            embed=success_embed("Verwarnt", f"{user.mention} wurde verwarnt (**{count}.** Verwarnung).\nGrund: {grund}")
        )

    @app_commands.command(name="warnungen", description="Zeigt die Verwarnungen eines Mitglieds")
    @app_commands.describe(user="Das Mitglied")
    @is_mod()
    async def warnungen(self, interaction: discord.Interaction, user: discord.Member):
        pool = get_pool()
        rows = await pool.fetch(
            "SELECT reason, moderator_id, created_at FROM warnings WHERE guild_id=$1 AND user_id=$2 ORDER BY created_at DESC",
            interaction.guild_id, user.id,
        )
        if not rows:
            await interaction.response.send_message(
                embed=success_embed("Sauberes Register", f"{user.mention} hat keine Verwarnungen."), ephemeral=True
            )
            return

        lines = []
        for i, row in enumerate(rows[:10], 1):
            mod = interaction.guild.get_member(row["moderator_id"])
            mod_name = mod.display_name if mod else "Unbekannt"
            lines.append(f"**{i}.** {row['reason']} — _von {mod_name}, {row['created_at']:%d.%m.%Y}_")

        embed = base_embed(f"⚠️ Verwarnungen von {user.display_name}", "\n".join(lines))
        embed.set_footer(text=f"Insgesamt {len(rows)} Verwarnung(en)")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="timeout", description="Timeoutet ein Mitglied für X Minuten")
    @app_commands.describe(user="Wer getimeoutet wird", minuten="Dauer in Minuten", grund="Grund")
    @is_mod()
    async def timeout(self, interaction: discord.Interaction, user: discord.Member, minuten: int, grund: str = None):
        try:
            await user.timeout(timedelta(minutes=minuten), reason=grund)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Keine Berechtigung", "Meine Rolle muss über der Zielperson stehen."), ephemeral=True
            )
            return

        await interaction.response.send_message(
            embed=success_embed("Timeout gesetzt", f"{user.mention} ist für **{minuten} Minuten** stummgeschaltet." + (f"\nGrund: {grund}" if grund else ""))
        )

    @app_commands.command(name="kick", description="Kickt ein Mitglied vom Server")
    @app_commands.describe(user="Wer gekickt wird", grund="Grund")
    @is_mod()
    async def kick(self, interaction: discord.Interaction, user: discord.Member, grund: str = None):
        try:
            await user.kick(reason=grund)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Keine Berechtigung", "Meine Rolle muss über der Zielperson stehen."), ephemeral=True
            )
            return
        await interaction.response.send_message(
            embed=success_embed("Gekickt", f"{user} wurde vom Server gekickt." + (f"\nGrund: {grund}" if grund else ""))
        )

    @app_commands.command(name="ban", description="Bannt ein Mitglied vom Server")
    @app_commands.describe(user="Wer gebannt wird", grund="Grund")
    @is_mod()
    async def ban(self, interaction: discord.Interaction, user: discord.Member, grund: str = None):
        try:
            await user.ban(reason=grund, delete_message_days=0)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Keine Berechtigung", "Meine Rolle muss über der Zielperson stehen."), ephemeral=True
            )
            return
        await interaction.response.send_message(
            embed=success_embed("Gebannt", f"{user} wurde vom Server gebannt." + (f"\nGrund: {grund}" if grund else ""))
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
