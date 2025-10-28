"""Voice cog for TTS and RVC features."""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from pathlib import Path
from typing import Optional
import asyncio
import uuid

from config import Config
from services.tts import TTSService
from services.rvc_unified import UnifiedRVCService
from utils.helpers import format_error, format_success, format_info

logger = logging.getLogger(__name__)


class VoiceCog(commands.Cog):
    """Cog for voice commands (TTS and RVC)."""

    def __init__(self, bot: commands.Bot, tts: TTSService, rvc: Optional[UnifiedRVCService] = None):
        """Initialize voice cog.

        Args:
            bot: Discord bot instance
            tts: TTS service instance
            rvc: Optional RVC service instance
        """
        self.bot = bot
        self.tts = tts
        self.rvc = rvc
        self.voice_clients = {}  # guild_id -> voice_client

    @app_commands.command(name="join", description="Join your voice channel")
    async def join(self, interaction: discord.Interaction):
        """Join the user's voice channel.

        Args:
            interaction: Discord interaction
        """
        if not interaction.user.voice:
            await interaction.response.send_message(
                "❌ You need to be in a voice channel!", ephemeral=True
            )
            return

        channel = interaction.user.voice.channel

        try:
            if interaction.guild.id in self.voice_clients:
                await interaction.response.send_message(
                    "✅ Already connected to a voice channel!", ephemeral=True
                )
                return

            voice_client = await channel.connect()
            self.voice_clients[interaction.guild.id] = voice_client

            await interaction.response.send_message(
                format_success(f"Joined **{channel.name}**!"), ephemeral=True
            )

        except Exception as e:
            logger.error(f"Failed to join voice channel: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="leave", description="Leave voice channel")
    async def leave(self, interaction: discord.Interaction):
        """Leave the current voice channel.

        Args:
            interaction: Discord interaction
        """
        guild_id = interaction.guild.id

        if guild_id not in self.voice_clients:
            await interaction.response.send_message(
                "❌ Not connected to any voice channel!", ephemeral=True
            )
            return

        try:
            voice_client = self.voice_clients[guild_id]
            await voice_client.disconnect()
            del self.voice_clients[guild_id]

            await interaction.response.send_message(
                format_success("Disconnected from voice channel!"), ephemeral=True
            )

        except Exception as e:
            logger.error(f"Failed to leave voice channel: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="speak", description="Generate speech and play in voice channel")
    @app_commands.describe(text="Text to speak")
    async def speak(self, interaction: discord.Interaction, text: str):
        """Generate TTS and play in voice channel.

        Args:
            interaction: Discord interaction
            text: Text to convert to speech
        """
        await interaction.response.defer(thinking=True)

        try:
            guild_id = interaction.guild.id

            # Check if connected to voice
            if guild_id not in self.voice_clients:
                await interaction.followup.send(
                    "❌ Not connected to a voice channel! Use `/join` first."
                )
                return

            voice_client = self.voice_clients[guild_id]

            # Check if already playing
            if voice_client.is_playing():
                await interaction.followup.send("⏸️ Already playing audio. Please wait...")
                return

            # Generate TTS
            audio_file = Config.TEMP_DIR / f"tts_{uuid.uuid4()}.mp3"
            await self.tts.generate(text, audio_file)

            # Apply RVC if enabled and available
            if self.rvc and self.rvc.is_enabled() and Config.RVC_ENABLED:
                rvc_file = Config.TEMP_DIR / f"rvc_{uuid.uuid4()}.mp3"
                await self.rvc.convert(audio_file, rvc_file, model_name=Config.DEFAULT_RVC_MODEL)
                audio_file = rvc_file

            # Play audio
            audio_source = discord.FFmpegPCMAudio(str(audio_file))
            voice_client.play(
                audio_source,
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self._cleanup_audio(audio_file, e), self.bot.loop
                ),
            )

            await interaction.followup.send(format_success("🔊 Playing audio..."))

        except Exception as e:
            logger.error(f"Speak command failed: {e}")
            await interaction.followup.send(format_error(e))

    @app_commands.command(name="speak_as", description="Speak with a specific RVC voice")
    @app_commands.describe(voice_model="Voice model to use", text="Text to speak")
    async def speak_as(self, interaction: discord.Interaction, voice_model: str, text: str):
        """Generate TTS with specific RVC voice.

        Args:
            interaction: Discord interaction
            voice_model: Name of RVC model to use
            text: Text to convert to speech
        """
        await interaction.response.defer(thinking=True)

        try:
            if not self.rvc or not self.rvc.is_enabled():
                await interaction.followup.send(
                    "❌ RVC is not available. Please configure RVC models first."
                )
                return

            guild_id = interaction.guild.id

            # Check if connected to voice
            if guild_id not in self.voice_clients:
                await interaction.followup.send(
                    "❌ Not connected to a voice channel! Use `/join` first."
                )
                return

            voice_client = self.voice_clients[guild_id]

            # Check if already playing
            if voice_client.is_playing():
                await interaction.followup.send("⏸️ Already playing audio. Please wait...")
                return

            # Generate TTS
            audio_file = Config.TEMP_DIR / f"tts_{uuid.uuid4()}.mp3"
            await self.tts.generate(text, audio_file)

            # Apply RVC
            rvc_file = Config.TEMP_DIR / f"rvc_{uuid.uuid4()}.mp3"
            await self.rvc.convert(audio_file, rvc_file, model_name=voice_model)

            # Play audio
            audio_source = discord.FFmpegPCMAudio(str(rvc_file))
            voice_client.play(
                audio_source,
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self._cleanup_audio(rvc_file, e), self.bot.loop
                ),
            )

            await interaction.followup.send(
                format_success(f"🔊 Playing audio with voice: **{voice_model}**")
            )

        except Exception as e:
            logger.error(f"Speak_as command failed: {e}")
            await interaction.followup.send(format_error(e))

    @app_commands.command(name="voices", description="List available TTS and RVC voices")
    async def voices(self, interaction: discord.Interaction):
        """List available voices.

        Args:
            interaction: Discord interaction
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            embed = discord.Embed(
                title="🎙️ Available Voices",
                color=discord.Color.blue(),
            )

            # Current TTS voice
            tts_info = self.tts.get_voice_info()

            # Build voice info string based on engine
            if tts_info.get('engine') == 'kokoro':
                voice_details = f"**{tts_info['voice']}**\nEngine: Kokoro\nSpeed: {tts_info.get('speed', 1.0)}x"
            else:
                voice_details = f"**{tts_info['voice']}**\nEngine: Edge TTS\nRate: {tts_info.get('rate', '+0%')}, Volume: {tts_info.get('volume', '+0%')}"

            embed.add_field(
                name="Current TTS Voice",
                value=voice_details,
                inline=False,
            )

            # RVC models
            if self.rvc and self.rvc.is_enabled():
                models = await self.rvc.list_models()
                if models:
                    model_list = "\n".join([f"• {m}" for m in models])
                    embed.add_field(
                        name="RVC Voice Models",
                        value=model_list,
                        inline=False,
                    )
                else:
                    embed.add_field(
                        name="RVC Voice Models",
                        value="No models found. Add .pth files to `data/voice_models/`",
                        inline=False,
                    )
            else:
                embed.add_field(
                    name="RVC Voice Models",
                    value="RVC not configured",
                    inline=False,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Voices command failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="set_voice", description="Change the default TTS voice")
    @app_commands.describe(voice="Voice name (e.g., am_adam for Kokoro, en-US-AriaNeural for Edge)")
    async def set_voice(self, interaction: discord.Interaction, voice: str):
        """Change the default TTS voice.

        Args:
            interaction: Discord interaction
            voice: Voice name to use
        """
        try:
            # Update the voice based on current TTS engine
            if Config.TTS_ENGINE == "kokoro":
                self.tts.kokoro_voice = voice
                engine_name = "Kokoro"
            else:
                self.tts.default_voice = voice
                engine_name = "Edge TTS"

            await interaction.response.send_message(
                format_success(f"Default {engine_name} voice changed to: **{voice}**"),
                ephemeral=True,
            )

        except Exception as e:
            logger.error(f"Set_voice command failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="list_tts_voices", description="List all available TTS voices")
    @app_commands.describe(language="Filter by language code (e.g., en, es, fr)")
    async def list_tts_voices(
        self, interaction: discord.Interaction, language: Optional[str] = None
    ):
        """List available TTS voices.

        Args:
            interaction: Discord interaction
            language: Optional language filter
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            if language:
                voices = await self.tts.get_voices_by_language(language)
            else:
                voices = await self.tts.list_voices()

            if not voices:
                await interaction.followup.send(
                    f"❌ No voices found{f' for language: {language}' if language else ''}",
                    ephemeral=True,
                )
                return

            # Group by language
            voice_dict = {}
            for voice in voices:
                lang = voice["Locale"]
                if lang not in voice_dict:
                    voice_dict[lang] = []
                voice_dict[lang].append(voice["ShortName"])

            # Create embed(s)
            embeds = []
            for lang, voice_list in sorted(voice_dict.items()):
                voice_text = "\n".join([f"• {v}" for v in voice_list[:10]])  # Limit to 10 per lang
                if len(voice_list) > 10:
                    voice_text += f"\n... and {len(voice_list) - 10} more"

                embed = discord.Embed(
                    title=f"🎙️ TTS Voices - {lang}",
                    description=voice_text,
                    color=discord.Color.blue(),
                )
                embeds.append(embed)

                # Discord limits to 10 embeds
                if len(embeds) >= 10:
                    break

            await interaction.followup.send(embeds=embeds[:10], ephemeral=True)

        except Exception as e:
            logger.error(f"List_tts_voices command failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    async def _cleanup_audio(self, audio_file: Path, error):
        """Clean up audio file after playback.

        Args:
            audio_file: Path to audio file
            error: Playback error if any
        """
        if error:
            logger.error(f"Audio playback error: {error}")

        try:
            if audio_file.exists():
                audio_file.unlink()
                logger.info(f"Cleaned up audio file: {audio_file}")
        except Exception as e:
            logger.error(f"Failed to cleanup audio file: {e}")


async def setup(bot: commands.Bot):
    """Setup function for the cog."""
    # This will be called from main.py with proper dependencies
    pass
