import discord
from discord import app_commands
from discord.ext import commands

from database.db import get_pool
from utils.embeds import base_embed, success_embed, error_embed
import config
from cogs.extras import is_mod


class RoleButton(discord.ui.Button):
    def __init__(self, role_id: int, label: str, emoji: str = None):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=label,
            emoji=emoji,
            custom_id=f"rr:{role_id}",
        )

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(int(self.custom_id.split(":")[1]))
        if not role:
            await interaction.response.send_message(
                embed=error_embed("Rolle nicht gefunden", "Diese Rolle existiert nicht mehr."), ephemeral=True
            )
            return

        member = interaction.user
        try:
            if role in member.roles:
                await member.remove_roles(role, reason="Reaction-Role Toggle")
                await interaction.response.send_message(
                    embed=success_embed("Rolle entfernt", f"**{role.name}** wurde entfernt."), ephemeral=True
                )
            else:
                await member.add_roles(role, reason="Reaction-Role Toggle")
                await interaction.response.send_message(
                    embed=success_embed("Rolle vergeben", f"Du hast jetzt **{role.name}**!"), ephemeral=True
                )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Keine Berechtigung", "Meine Rolle muss über der Ziel-Rolle stehen."),
                ephemeral=True,
            )


class ReactionRoleView(discord.ui.View):
    def __init__(self, roles: list[tuple[int, str, str]]):
        super().__init__(timeout=None)
        for role_id, label, emoji in roles:
            self.add_item(RoleButton(role_id, label, emoji or None))


class Roles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # Bestehende Panels nach Neustart reaktivieren
        pool = get_pool()
        rows = await pool.fetch("SELECT DISTINCT message_id FROM reaction_roles")
        for row in rows:
            role_rows = await pool.fetch(
                "SELECT role_id, label, emoji FROM reaction_roles WHERE message_id=$1", row["message_id"]
            )
            roles = [(r["role_id"], r["label"], r["emoji"]) for r in role_rows]
            self.bot.add_view(ReactionRoleView(roles))

    rr_group = app_commands.Group(name="rollen-panel", description="Reaction-Role-Panel verwalten")

    @rr_group.command(name="erstellen", description="Erstellt ein Panel mit bis zu 5 Rollen-Buttons")
    @app_commands.describe(
        titel="Titel des Panels",
        beschreibung="Beschreibungstext",
        rolle1="1. Rolle", label1="Button-Text für Rolle 1", emoji1="Emoji für Rolle 1 (optional)",
        rolle2="2. Rolle", label2="Button-Text für Rolle 2", emoji2="Emoji für Rolle 2 (optional)",
        rolle3="3. Rolle", label3="Button-Text für Rolle 3", emoji3="Emoji für Rolle 3 (optional)",
        rolle4="4. Rolle", label4="Button-Text für Rolle 4", emoji4="Emoji für Rolle 4 (optional)",
        rolle5="5. Rolle", label5="Button-Text für Rolle 5", emoji5="Emoji für Rolle 5 (optional)",
    )
    @is_mod()
    async def erstellen(
        self,
        interaction: discord.Interaction,
        titel: str,
        beschreibung: str,
        rolle1: discord.Role, label1: str, emoji1: str = None,
        rolle2: discord.Role = None, label2: str = None, emoji2: str = None,
        rolle3: discord.Role = None, label3: str = None, emoji3: str = None,
        rolle4: discord.Role = None, label4: str = None, emoji4: str = None,
        rolle5: discord.Role = None, label5: str = None, emoji5: str = None,
    ):
        pairs = [
            (rolle1, label1, emoji1),
            (rolle2, label2, emoji2),
            (rolle3, label3, emoji3),
            (rolle4, label4, emoji4),
            (rolle5, label5, emoji5),
        ]
        roles_data = [(r.id, lbl or r.name, emoji) for r, lbl, emoji in pairs if r is not None]

        embed = base_embed(titel, beschreibung)
        view = ReactionRoleView([(r_id, lbl, emoji) for r_id, lbl, emoji in roles_data])

        await interaction.response.send_message(embed=embed, view=view)
        sent = await interaction.original_response()

        pool = get_pool()
        for role_id, label, emoji in roles_data:
            await pool.execute(
                "INSERT INTO reaction_roles (guild_id, message_id, role_id, emoji, label) VALUES ($1, $2, $3, $4, $5)",
                interaction.guild_id, sent.id, role_id, emoji, label,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Roles(bot))
