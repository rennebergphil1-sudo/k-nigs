import discord
from discord import app_commands
from discord.ext import commands
import json

from database.db import get_pool
from utils.embeds import base_embed, success_embed, error_embed
import config


class Characters(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    char_group = app_commands.Group(name="charakter", description="Charakter-System für RP")

    @char_group.command(name="erstellen", description="Erstelle einen neuen RP-Charakter")
    @app_commands.describe(
        name="Name deines Charakters",
        fraktion="Fraktion/Gruppe (optional)",
        backstory="Kurze Hintergrundgeschichte (optional)",
        bild_url="Bild-URL für den Charakter (optional)",
    )
    async def erstellen(
        self,
        interaction: discord.Interaction,
        name: str,
        fraktion: str = None,
        backstory: str = None,
        bild_url: str = None,
    ):
        pool = get_pool()
        try:
            await pool.execute(
                """
                INSERT INTO characters (user_id, guild_id, name, faction, backstory, image_url)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                interaction.user.id, interaction.guild_id, name, fraktion, backstory, bild_url,
            )
        except Exception:
            await interaction.response.send_message(
                embed=error_embed("Fehler", f"Du hast bereits einen Charakter namens **{name}**."),
                ephemeral=True,
            )
            return

        embed = success_embed("Charakter erstellt", f"**{name}** wurde angelegt.")
        if fraktion:
            embed.add_field(name="Fraktion", value=fraktion, inline=True)
        if backstory:
            embed.add_field(name="Backstory", value=backstory[:1024], inline=False)
        if bild_url:
            embed.set_thumbnail(url=bild_url)

        await interaction.response.send_message(embed=embed)

    @char_group.command(name="zeigen", description="Zeige einen Charakter an")
    @app_commands.describe(name="Name des Charakters", user="Besitzer des Charakters (optional)")
    async def zeigen(self, interaction: discord.Interaction, name: str, user: discord.Member = None):
        pool = get_pool()
        target = user or interaction.user
        row = await pool.fetchrow(
            "SELECT * FROM characters WHERE user_id=$1 AND guild_id=$2 AND name=$3",
            target.id, interaction.guild_id, name,
        )
        if not row:
            await interaction.response.send_message(
                embed=error_embed("Nicht gefunden", f"Kein Charakter **{name}** für {target.mention} gefunden."),
                ephemeral=True,
            )
            return

        items = await pool.fetch("SELECT item_name, quantity FROM inventory_items WHERE character_id=$1", row["id"])
        embed = base_embed(row["name"], row["backstory"] or "")
        embed.add_field(name="Besitzer", value=target.mention, inline=True)
        if row["faction"]:
            embed.add_field(name="Fraktion", value=row["faction"], inline=True)

        stats = row["stats"] or {}
        if isinstance(stats, str):
            stats = json.loads(stats)
        if stats:
            stats_text = "\n".join(f"**{k}:** {v}" for k, v in stats.items())
            embed.add_field(name="Stats", value=stats_text, inline=False)

        if items:
            inv_text = "\n".join(f"• {i['item_name']} x{i['quantity']}" for i in items)
            embed.add_field(name="Inventar", value=inv_text, inline=False)

        if row["image_url"]:
            embed.set_thumbnail(url=row["image_url"])

        await interaction.response.send_message(embed=embed)

    @char_group.command(name="stat-setzen", description="Setze einen Stat-Wert für deinen Charakter")
    @app_commands.describe(name="Charaktername", stat="Name des Stats (z.B. Stärke)", wert="Wert des Stats")
    async def stat_setzen(self, interaction: discord.Interaction, name: str, stat: str, wert: str):
        pool = get_pool()
        row = await pool.fetchrow(
            "SELECT id, stats FROM characters WHERE user_id=$1 AND guild_id=$2 AND name=$3",
            interaction.user.id, interaction.guild_id, name,
        )
        if not row:
            await interaction.response.send_message(
                embed=error_embed("Nicht gefunden", f"Du hast keinen Charakter namens **{name}**."),
                ephemeral=True,
            )
            return

        stats = row["stats"] or {}
        if isinstance(stats, str):
            stats = json.loads(stats)
        stats[stat] = wert

        await pool.execute("UPDATE characters SET stats=$1 WHERE id=$2", json.dumps(stats), row["id"])
        await interaction.response.send_message(
            embed=success_embed("Stat aktualisiert", f"**{stat}** von **{name}** ist jetzt `{wert}`.")
        )

    @char_group.command(name="item-geben", description="Füge deinem Charakter ein Item hinzu")
    @app_commands.describe(name="Charaktername", item="Item-Name", menge="Anzahl (Standard 1)")
    async def item_geben(self, interaction: discord.Interaction, name: str, item: str, menge: int = 1):
        pool = get_pool()
        row = await pool.fetchrow(
            "SELECT id FROM characters WHERE user_id=$1 AND guild_id=$2 AND name=$3",
            interaction.user.id, interaction.guild_id, name,
        )
        if not row:
            await interaction.response.send_message(
                embed=error_embed("Nicht gefunden", f"Du hast keinen Charakter namens **{name}**."),
                ephemeral=True,
            )
            return

        existing = await pool.fetchrow(
            "SELECT id, quantity FROM inventory_items WHERE character_id=$1 AND item_name=$2",
            row["id"], item,
        )
        if existing:
            await pool.execute(
                "UPDATE inventory_items SET quantity=$1 WHERE id=$2",
                existing["quantity"] + menge, existing["id"],
            )
        else:
            await pool.execute(
                "INSERT INTO inventory_items (character_id, item_name, quantity) VALUES ($1, $2, $3)",
                row["id"], item, menge,
            )

        await interaction.response.send_message(
            embed=success_embed("Item hinzugefügt", f"**{item}** x{menge} wurde zu **{name}**s Inventar hinzugefügt.")
        )

    @char_group.command(name="liste", description="Zeige alle deine Charaktere auf diesem Server")
    async def liste(self, interaction: discord.Interaction):
        pool = get_pool()
        rows = await pool.fetch(
            "SELECT name, faction FROM characters WHERE user_id=$1 AND guild_id=$2",
            interaction.user.id, interaction.guild_id,
        )
        if not rows:
            await interaction.response.send_message(
                embed=error_embed("Keine Charaktere", "Du hast noch keinen Charakter erstellt."),
                ephemeral=True,
            )
            return

        text = "\n".join(f"• **{r['name']}**" + (f" ({r['faction']})" if r["faction"] else "") for r in rows)
        embed = base_embed("Deine Charaktere", text)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Characters(bot))
