# RP Community Bot — Phil7442 × Developer Studio

Ein RP-Community-Bot mit Charakter-System, Schreib-/Szenen-Tools, Support-Ticket-System mit Musik-Warteraum und einem Anti-Raid/Anti-Nuke Security-System.

## Features

### 🎭 Charakter-System (`/charakter ...`)
- `erstellen` – neuen Charakter anlegen (Name, Fraktion, Backstory, Bild)
- `zeigen` – Charakter-Profil ansehen (inkl. Stats & Inventar)
- `stat-setzen` – Stats frei definieren (Stärke, Magie, Reputation, ...)
- `item-geben` – Items zum Inventar hinzufügen
- `liste` – eigene Charaktere auflisten

### ✍️ RP-Tools
- `/würfel` – Würfeln im Format `1w20`, `3w6+2`, etc.
- `/szene erstellen` – legt automatisch einen RP-Channel an
- `/szene archivieren` – markiert eine Szene als abgeschlossen
- `/szene log` – exportiert den Chatverlauf als `.txt`

### 🛡️ Security-System (Anti-Raid & Anti-Nuke)
- Erkennt Massen-Joins (Raid) → automatischer Server-Lockdown
- Erkennt Massen-Löschungen von Channels/Rollen & Massen-Bans → Täter wird entwaffnet + gebannt
- Alle Events landen im Log-Channel + werden in der DB gespeichert
- `/security status` – aktuellen Zustand ansehen
- `/security lockdown-aufheben` – Server manuell wieder öffnen

### 📩 Support-Tickets + Musik-Warteraum
- `/ticket-panel` – postet ein Button-Panel, User können Tickets öffnen
- Private Ticket-Channels mit Team-Rolle
- Sobald jemand den Warteraum-Voice-Channel betritt, joint der Bot automatisch und spielt
  Musik aus `assets/waiting_music/` in Dauerschleife (lege dort deine Suno-Tracks als `.mp3` ab)

## Setup

1. `.env.example` zu `.env` kopieren und ausfüllen (Token, DB-URL, Channel-IDs, etc.)
2. `pip install -r requirements.txt`
3. Bot Intents im Discord Developer Portal aktivieren: `Server Members`, `Message Content`, `Voice States`
4. Für Musik: `ffmpeg` muss installiert sein (lokal: `apt install ffmpeg`, auf Railway automatisch über Nixpacks/Railpack)
5. Deine Suno-generierten Songs als `.mp3` in `assets/waiting_music/` ablegen
6. Start: `python bot.py`

## Deploy auf Railway

- Neues Projekt aus diesem Repo erstellen
- Environment-Variablen aus `.env.example` in Railway eintragen
- PostgreSQL-Plugin hinzufügen → `DATABASE_URL` wird automatisch gesetzt
- Falls Musik nicht abspielt: Environment-Variable `RAILPACK_PACKAGES=ffmpeg` setzen

## Struktur

```
rp-community-bot/
├── bot.py                  # Einstiegspunkt
├── config.py                # Branding, Farben, Schwellenwerte
├── database/db.py           # asyncpg Pool + Schema
├── cogs/
│   ├── characters.py         # Charakter-System
│   ├── rp_tools.py           # Würfel, Szenen, Logs
│   ├── security.py           # Anti-Raid / Anti-Nuke
│   └── support.py            # Tickets + Musik-Warteraum
├── utils/embeds.py           # Cyberpunk-Embed-Helper
└── assets/waiting_music/     # Hier deine Suno-Tracks reinlegen
```

## Nächste Ausbaustufen (optional)

- KI-Schreibhilfe über Groq (Story-Vorschläge bei `/szene`)
- Charakter-Bewertung/Genehmigung durch Team (wie dein Bewerbungs-Bot)
- Level-/XP-System fürs Schreiben (wie im Community-Bot)
- Web-Dashboard (Netlify) zur Charakterverwaltung
