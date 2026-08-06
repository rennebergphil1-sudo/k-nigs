import discord
from discord import app_commands
from discord.ext import commands
import tempfile
import os
from gtts import gTTS

from database.db import get_pool
from utils.embeds import base_embed, success_embed, error_embed
from cogs.extras import is_mod
import config


class VoiceGreet(commands.Cog):
    """Bot joint einen konfigurierten Voice-Channel und sagt automatisch Hallo, wenn jemand beitritt."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="voice-begrüßung-setup", description="Richtet die automatische Sprach-Begrüßung ein")
    @app_commands.describe(
        channel="Voice-Channel, in dem begrüßt werden soll",
        text="Was gesagt werden soll (Platzhalter: {user} = Name)",
    )
    @is_mod()
    async def setup_greet(self, interaction: discord.Interaction, channel: discord.VoiceChannel, text: str = "Hallo {user}, willkommen!"):
        pool = get_pool()
        await pool.execute(
            """
            INSERT INTO voice_greet_config (guild_id, channel_id, message)
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id) DO UPDATE SET channel_id=$2, message=$3
            """,
            interaction.guild_id, channel.id, text,
        )
        await interaction.response.send_message(
            embed=success_embed("Eingerichtet", f"Ich begrüße jetzt automatisch alle, die {channel.mention} joinen.")
        )

    @app_commands.command(name="voice-begrüßung-aus", description="Deaktiviert die automatische Sprach-Begrüßung")
    @is_mod()
    async def disable_greet(self, interaction: discord.Interaction):
        pool = get_pool()
        await pool.execute("DELETE FROM voice_greet_config WHERE guild_id=$1", interaction.guild_id)
        await interaction.response.send_message(embed=success_embed("Deaktiviert", "Sprach-Begrüßung ist aus."))

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return
        if not after.channel or (before.channel and before.channel.id == after.channel.id):
            return

        pool = get_pool()
        cfg = await pool.fetchrow("SELECT * FROM voice_greet_config WHERE guild_id=$1", member.guild.id)
        if not cfg or cfg["channel_id"] != after.channel.id:
            return

        # Bot ist evtl. schon woanders im selben Server verbunden (z.B. Warteraum-Musik) -> nicht stören
        existing_vc = member.guild.voice_client
        if existing_vc and existing_vc.channel.id != after.channel.id:
            return

        text = cfg["message"].replace("{user}", member.display_name)

        try:
            if existing_vc and existing_vc.is_connected():
                vc = existing_vc
            else:
                vc = await after.channel.connect()
        except discord.ClientException:
            return

        tmp_path = None
        try:
            tts = gTTS(text=text, lang="de")
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = tmp.name
            tts.save(tmp_path)

            if vc.is_playing():
                vc.stop()

            source = discord.FFmpegPCMAudio(tmp_path)

            def after_play(error):
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

            vc.play(discord.PCMVolumeTransformer(source, volume=0.8), after=after_play)
        except Exception as e:
            print(f"[VoiceGreet] TTS-Fehler: {e}")
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceGreet(bot))
