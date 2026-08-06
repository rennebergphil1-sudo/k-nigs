import discord
from discord.ext import commands
import asyncio
import logging

import config
from database.db import init_pool

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("rp-bot")

INTENTS = discord.Intents.default()
INTENTS.members = True
INTENTS.message_content = True
INTENTS.voice_states = True

COGS = [
    "cogs.characters",
    "cogs.rp_tools",
    "cogs.security",
    "cogs.support",
    "cogs.extras",
    "cogs.leveling",
    "cogs.roles",
    "cogs.moderation",
    "cogs.giveaways",
    "cogs.welcome",
    "cogs.tiktok",
    "cogs.voice_greet",
]


class RPBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=INTENTS)

    async def setup_hook(self):
        await init_pool()
        log.info("Datenbank-Pool initialisiert.")

        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info(f"Cog geladen: {cog}")
            except Exception as e:
                log.error(f"Fehler beim Laden von {cog}: {e}")

        if config.GUILD_ID:
            guild = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info(f"Slash-Commands für Guild {config.GUILD_ID} synchronisiert.")
        else:
            await self.tree.sync()
            log.info("Slash-Commands global synchronisiert (kann bis zu 1h dauern).")

    async def on_ready(self):
        log.info(f"Eingeloggt als {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="über das RP-Universum 🛡️")
        )


async def main():
    if not config.DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN fehlt in der .env Datei!")

    bot = RPBot()
    async with bot:
        await bot.start(config.DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
