import discord
from discord import app_commands
from discord.ext import commands

from database.db import get_pool
from utils.embeds import base_embed, success_embed, error_embed
import config


def is_mod():
    """Check: Administrator ODER die konfigurierte Mod-Rolle."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        if config.MOD_ROLE_ID:
            role = interaction.guild.get_role(config.MOD_ROLE_ID)
            if role and role in interaction.user.roles:
                return True
        return False
    return app_commands.check(predicate)


class Extras(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            if interaction.response.is_done():
                await interaction.followup.send(
                    embed=error_embed("Keine Berechtigung", "Dafür brauchst du eine Team-Rolle oder Admin-Rechte."),
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    embed=error_embed("Keine Berechtigung", "Dafür brauchst du eine Team-Rolle oder Admin-Rechte."),
                    ephemeral=True,
                )

    # ---------- /say ----------
    @app_commands.command(name="say", description="Lass den Bot eine Nachricht schreiben")
    @app_commands.describe(
        nachricht="Was der Bot sagen soll",
        channel="Ziel-Channel (Standard: aktueller Channel)",
        als_embed="Als gestyltes Embed statt normaler Nachricht senden",
    )
    @is_mod()
    async def say(
        self,
        interaction: discord.Interaction,
        nachricht: str,
        channel: discord.TextChannel = None,
        als_embed: bool = False,
    ):
        target = channel or interaction.channel

        # \n in echten Zeilenumbruch umwandeln, falls jemand \n eintippt
        nachricht = nachricht.replace("\\n", "\n")

        try:
            if als_embed:
                embed = base_embed("", nachricht)
                await target.send(embed=embed)
            else:
                await target.send(nachricht)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Keine Berechtigung", f"Ich darf in {target.mention} nicht schreiben."),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=success_embed("Gesendet", f"Nachricht wurde in {target.mention} gepostet."),
            ephemeral=True,
        )

    @say.error
    async def say_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                embed=error_embed("Keine Berechtigung", "Nur Team-Mitglieder dürfen `/say` benutzen."),
                ephemeral=True,
            )

    # ---------- /announce ----------
    @app_commands.command(name="announce", description="Postet eine gestylte Ankündigung")
    @app_commands.describe(
        titel="Titel der Ankündigung",
        text="Inhalt der Ankündigung",
        channel="Ziel-Channel (Standard: aktueller Channel)",
        ping="Rolle, die gepingt werden soll (optional)",
    )
    @is_mod()
    async def announce(
        self,
        interaction: discord.Interaction,
        titel: str,
        text: str,
        channel: discord.TextChannel = None,
        ping: discord.Role = None,
    ):
        target = channel or interaction.channel
        text = text.replace("\\n", "\n")

        embed = base_embed(f"📢 {titel}", text)
        embed.set_author(name=f"Ankündigung von {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

        content = ping.mention if ping else None
        allowed = discord.AllowedMentions(roles=True) if ping else discord.AllowedMentions.none()

        try:
            await target.send(content=content, embed=embed, allowed_mentions=allowed)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Keine Berechtigung", f"Ich darf in {target.mention} nicht schreiben."),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=success_embed("Angekündigt", f"Ankündigung wurde in {target.mention} gepostet."),
            ephemeral=True,
        )

    @announce.error
    async def announce_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                embed=error_embed("Keine Berechtigung", "Nur Team-Mitglieder dürfen `/announce` benutzen."),
                ephemeral=True,
            )

    # ---------- Team-Liste ----------
    team_group = app_commands.Group(name="team", description="Team-Liste des Servers verwalten")

    @team_group.command(name="hierarchie-hinzufügen", description="Definiert eine Rang-Stufe für Uprank/Downrank")
    @app_commands.describe(
        rolle="Die Rolle für diese Stufe",
        stufe="Rangnummer (1 = niedrigste Stufe, höhere Zahl = höherer Rang)",
    )
    @is_mod()
    async def hierarchie_hinzufuegen(self, interaction: discord.Interaction, rolle: discord.Role, stufe: int):
        pool = get_pool()
        try:
            await pool.execute(
                "INSERT INTO team_hierarchy (guild_id, role_id, step) VALUES ($1, $2, $3)",
                interaction.guild_id, rolle.id, stufe,
            )
        except Exception:
            await interaction.response.send_message(
                embed=error_embed("Fehler", f"Stufe {stufe} oder die Rolle {rolle.mention} ist bereits vergeben."),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=success_embed("Hierarchie aktualisiert", f"**{rolle.name}** ist jetzt Stufe **{stufe}**.")
        )

    @team_group.command(name="hierarchie-liste", description="Zeigt die konfigurierte Rang-Hierarchie")
    async def hierarchie_liste(self, interaction: discord.Interaction):
        pool = get_pool()
        rows = await pool.fetch(
            "SELECT role_id, step FROM team_hierarchy WHERE guild_id=$1 ORDER BY step DESC",
            interaction.guild_id,
        )
        if not rows:
            await interaction.response.send_message(
                embed=error_embed("Leer", "Noch keine Hierarchie definiert. Mit `/team hierarchie-hinzufügen` anlegen."),
                ephemeral=True,
            )
            return
        lines = []
        for row in rows:
            role = interaction.guild.get_role(row["role_id"])
            lines.append(f"**Stufe {row['step']}** — {role.mention if role else '(gelöschte Rolle)'}")
        await interaction.response.send_message(embed=base_embed("📶 Rang-Hierarchie", "\n".join(lines)))

    async def _get_member_step(self, pool, guild_id: int, member: discord.Member):
        hierarchy = await pool.fetch(
            "SELECT role_id, step FROM team_hierarchy WHERE guild_id=$1 ORDER BY step ASC", guild_id
        )
        member_role_ids = {r.id for r in member.roles}
        current = None
        for row in hierarchy:
            if row["role_id"] in member_role_ids:
                if current is None or row["step"] > current["step"]:
                    current = row
        return current, hierarchy

    @team_group.command(name="uprank", description="Befördert jemanden zur nächsthöheren Rang-Stufe")
    @app_commands.describe(user="Das Mitglied")
    @is_mod()
    async def uprank(self, interaction: discord.Interaction, user: discord.Member):
        pool = get_pool()
        current, hierarchy = await self._get_member_step(pool, interaction.guild_id, user)
        if not hierarchy:
            await interaction.response.send_message(
                embed=error_embed("Keine Hierarchie", "Noch keine Rang-Hierarchie definiert."), ephemeral=True
            )
            return

        if current is None:
            target_step_row = hierarchy[0]
        else:
            higher = [r for r in hierarchy if r["step"] > current["step"]]
            if not higher:
                await interaction.response.send_message(
                    embed=error_embed("Höchster Rang", f"{user.mention} ist bereits auf der höchsten Stufe."),
                    ephemeral=True,
                )
                return
            target_step_row = min(higher, key=lambda r: r["step"])

        new_role = interaction.guild.get_role(target_step_row["role_id"])
        if not new_role:
            await interaction.response.send_message(embed=error_embed("Fehler", "Zielrolle existiert nicht mehr."), ephemeral=True)
            return

        try:
            if current:
                old_role = interaction.guild.get_role(current["role_id"])
                if old_role:
                    await user.remove_roles(old_role, reason="Uprank")
            await user.add_roles(new_role, reason=f"Uprank durch {interaction.user}")
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Keine Berechtigung", "Meine Rolle muss über den Team-Rollen stehen."), ephemeral=True
            )
            return

        await pool.execute(
            """
            INSERT INTO team_members (guild_id, user_id, position, rank_order)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET position=$3, rank_order=$4
            """,
            interaction.guild_id, user.id, new_role.name, -target_step_row["step"],
        )

        await interaction.response.send_message(
            embed=success_embed("⬆️ Upgerankt", f"{user.mention} ist jetzt **{new_role.name}**!")
        )

    @team_group.command(name="downrank", description="Degradiert jemanden zur nächstniedrigeren Rang-Stufe")
    @app_commands.describe(user="Das Mitglied")
    @is_mod()
    async def downrank(self, interaction: discord.Interaction, user: discord.Member):
        pool = get_pool()
        current, hierarchy = await self._get_member_step(pool, interaction.guild_id, user)
        if not hierarchy:
            await interaction.response.send_message(
                embed=error_embed("Keine Hierarchie", "Noch keine Rang-Hierarchie definiert."), ephemeral=True
            )
            return
        if current is None:
            await interaction.response.send_message(
                embed=error_embed("Kein Rang", f"{user.mention} hat aktuell keine Team-Rang-Rolle."), ephemeral=True
            )
            return

        lower = [r for r in hierarchy if r["step"] < current["step"]]
        old_role = interaction.guild.get_role(current["role_id"])

        try:
            if old_role:
                await user.remove_roles(old_role, reason=f"Downrank durch {interaction.user}")

            if not lower:
                # Komplett aus dem Team entfernen
                await pool.execute(
                    "DELETE FROM team_members WHERE guild_id=$1 AND user_id=$2", interaction.guild_id, user.id
                )
                await interaction.response.send_message(
                    embed=success_embed("⬇️ Aus dem Team entfernt", f"{user.mention} wurde auf die niedrigste Stufe entfernt.")
                )
                return

            target_step_row = max(lower, key=lambda r: r["step"])
            new_role = interaction.guild.get_role(target_step_row["role_id"])
            await user.add_roles(new_role, reason=f"Downrank durch {interaction.user}")
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Keine Berechtigung", "Meine Rolle muss über den Team-Rollen stehen."), ephemeral=True
            )
            return

        await pool.execute(
            """
            INSERT INTO team_members (guild_id, user_id, position, rank_order)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET position=$3, rank_order=$4
            """,
            interaction.guild_id, user.id, new_role.name, -target_step_row["step"],
        )

        await interaction.response.send_message(
            embed=success_embed("⬇️ Downgerankt", f"{user.mention} ist jetzt **{new_role.name}**.")
        )


    @team_group.command(name="hinzufügen", description="Fügt jemanden zur Team-Liste hinzu")
    @app_commands.describe(
        user="Das Team-Mitglied",
        position="Position/Titel, z.B. 'Owner', 'Admin', 'Moderator'",
        rang="Reihenfolge in der Liste (kleinere Zahl = weiter oben, Standard 100)",
        notiz="Optionale Notiz",
    )
    @is_mod()
    async def hinzufuegen(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        position: str,
        rang: int = 100,
        notiz: str = None,
    ):
        pool = get_pool()
        await pool.execute(
            """
            INSERT INTO team_members (guild_id, user_id, position, rank_order, note)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (guild_id, user_id)
            DO UPDATE SET position=$3, rank_order=$4, note=$5
            """,
            interaction.guild_id, user.id, position, rang, notiz,
        )
        await interaction.response.send_message(
            embed=success_embed("Team aktualisiert", f"{user.mention} ist jetzt **{position}**.")
        )

    @team_group.command(name="entfernen", description="Entfernt jemanden aus der Team-Liste")
    @app_commands.describe(user="Das Team-Mitglied")
    @is_mod()
    async def entfernen(self, interaction: discord.Interaction, user: discord.Member):
        pool = get_pool()
        result = await pool.execute(
            "DELETE FROM team_members WHERE guild_id=$1 AND user_id=$2",
            interaction.guild_id, user.id,
        )
        if result.endswith("0"):
            await interaction.response.send_message(
                embed=error_embed("Nicht gefunden", f"{user.mention} steht nicht auf der Team-Liste."),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=success_embed("Entfernt", f"{user.mention} wurde von der Team-Liste entfernt.")
        )

    @team_group.command(name="liste", description="Zeigt die komplette Team-Liste des Servers")
    async def liste(self, interaction: discord.Interaction):
        pool = get_pool()
        rows = await pool.fetch(
            "SELECT user_id, position, rank_order, note FROM team_members WHERE guild_id=$1 ORDER BY rank_order ASC",
            interaction.guild_id,
        )
        if not rows:
            await interaction.response.send_message(
                embed=error_embed("Leer", "Die Team-Liste ist noch leer. Mit `/team hinzufügen` befüllen."),
                ephemeral=True,
            )
            return

        embed = base_embed("👥 Team-Liste", "")
        for row in rows:
            member = interaction.guild.get_member(row["user_id"])
            name = member.mention if member else f"<@{row['user_id']}> (nicht mehr auf dem Server)"
            value = name
            if row["note"]:
                value += f"\n_{row['note']}_"
            embed.add_field(name=f"🔹 {row['position']}", value=value, inline=False)

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Extras(bot))
