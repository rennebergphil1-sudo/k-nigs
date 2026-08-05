import discord
from datetime import datetime, timezone
import config


def base_embed(title: str, description: str = "", color: int = config.COLOR_PRIMARY) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text=config.BRAND_FOOTER, icon_url=config.BRAND_ICON)
    return embed


def success_embed(title: str, description: str = "") -> discord.Embed:
    return base_embed(f"✅ {title}", description, config.COLOR_SUCCESS)


def error_embed(title: str, description: str = "") -> discord.Embed:
    return base_embed(f"⛔ {title}", description, config.COLOR_ERROR)


def warning_embed(title: str, description: str = "") -> discord.Embed:
    return base_embed(f"⚠️ {title}", description, config.COLOR_WARNING)


def security_embed(title: str, description: str = "") -> discord.Embed:
    return base_embed(f"🛡️ {title}", description, config.COLOR_ACCENT)
