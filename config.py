import os
from dotenv import load_dotenv

load_dotenv()

# --- Discord ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0")) or None

# --- Datenbank ---
DATABASE_URL = os.getenv("DATABASE_URL")

# --- KI ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

# --- Channels / Rollen ---
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0")) or None
MOD_ROLE_ID = int(os.getenv("MOD_ROLE_ID", "0")) or None
SUPPORT_CATEGORY_ID = int(os.getenv("SUPPORT_CATEGORY_ID", "0")) or None
WAITING_VOICE_CHANNEL_ID = int(os.getenv("WAITING_VOICE_CHANNEL_ID", "0")) or None

# --- Branding: Phil7442 x Developer Studio Cyberpunk Look ---
COLOR_PRIMARY = 0x2DD4EE   # cyan
COLOR_ACCENT = 0x9B6BFF    # violet
COLOR_BG = 0x0A0E14        # dark background (embed footer/thumbnails)
COLOR_SUCCESS = 0x2DD4EE
COLOR_ERROR = 0xFF4B6E
COLOR_WARNING = 0xFFC542

BRAND_FOOTER = "Phil7442 × Developer Studio"
BRAND_ICON = None  # optional: URL zu deinem Logo

# --- Security-System Schwellenwerte ---
ANTIRAID_JOIN_LIMIT = 6          # max. Joins
ANTIRAID_JOIN_INTERVAL = 10      # ...innerhalb von X Sekunden -> Lockdown
ANTIRAID_MIN_ACCOUNT_AGE_DAYS = 3  # Accounts jünger werden markiert/gekickt

ANTINUKE_CHANNEL_DELETE_LIMIT = 3   # max. Channel-Löschungen
ANTINUKE_CHANNEL_DELETE_INTERVAL = 15
ANTINUKE_ROLE_DELETE_LIMIT = 3
ANTINUKE_ROLE_DELETE_INTERVAL = 15
ANTINUKE_BAN_LIMIT = 3
ANTINUKE_BAN_INTERVAL = 15

# --- Musik im Warteraum ---
# Lege deine Suno-Tracks (als .mp3) hier ab, der Bot spielt sie in Dauerschleife
MUSIC_FOLDER = "assets/waiting_music"
