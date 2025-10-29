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

    def __init__(
        self,
        bot: commands.Bot,
        tts: TTSService,
        rvc: Optional[UnifiedRVCService] = None,
        voice_activity_detector=None,
    ):
        """Initialize voice cog.

        Args:
            bot: Discord bot instance
            tts: TTS service instance
            rvc: Optional RVC service instance
            voice_activity_detector: Optional voice activity detector
        """
        self.bot = bot
        self.tts = tts
        self.rvc = rvc
        self.voice_activity_detector = voice_activity_detector
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

    @app_commands.command(name="list_kokoro_voices", description="List all available Kokoro TTS voices")
    async def list_kokoro_voices(self, interaction: discord.Interaction):
        """List all available Kokoro voices with descriptions.

        Args:
            interaction: Discord interaction
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Check if Kokoro is available
            if not hasattr(self.tts, 'kokoro') or not self.tts.kokoro:
                await interaction.followup.send(
                    "❌ Kokoro TTS is not available. The bot is configured to use Edge TTS.",
                    ephemeral=True,
                )
                return

            # Get available voices
            voices = self.tts.kokoro.get_voices()

            if not voices:
                await interaction.followup.send(
                    "❌ No Kokoro voices found.",
                    ephemeral=True,
                )
                return

            # Voice descriptions by type
            voice_descriptions = {
                "am_adam": "Adult Male - Clear, neutral",
                "am_michael": "Adult Male - Warm, professional",
                "am_onyx": "Adult Male - Deep, commanding",
                "af_bella": "Adult Female - Soft, friendly",
                "af_sarah": "Adult Female - Clear, professional",
                "af_nicole": "Adult Female - Warm, expressive",
                "af_sky": "Adult Female - Bright, energetic",
                "bm_george": "British Male - Distinguished, proper",
                "bm_lewis": "British Male - Casual, approachable",
                "bf_emma": "British Female - Elegant, refined",
                "bf_isabella": "British Female - Warm, charming",
            }

            # Group voices by gender/region
            male_voices = [v for v in voices if v.startswith(("am_", "bm_"))]
            female_voices = [v for v in voices if v.startswith(("af_", "bf_"))]

            # Create embed
            embed = discord.Embed(
                title="🎙️ Kokoro TTS Voices",
                description="Use `/set_voice <voice>` to change your default voice",
                color=discord.Color.purple(),
            )

            # Add male voices
            if male_voices:
                male_text = "\n".join([
                    f"**{v}**\n{voice_descriptions.get(v, 'No description')}"
                    for v in sorted(male_voices)[:8]
                ])
                embed.add_field(
                    name="🎤 Male Voices",
                    value=male_text,
                    inline=False,
                )

            # Add female voices
            if female_voices:
                female_text = "\n".join([
                    f"**{v}**\n{voice_descriptions.get(v, 'No description')}"
                    for v in sorted(female_voices)[:8]
                ])
                embed.add_field(
                    name="🎤 Female Voices",
                    value=female_text,
                    inline=False,
                )

            # Show current voice
            current_voice = getattr(self.tts, 'kokoro_voice', 'Unknown')
            embed.set_footer(text=f"Current voice: {current_voice} | Total voices: {len(voices)}")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"List_kokoro_voices command failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="listen", description="Start listening to voice channel (Whisper STT)")
    async def listen(self, interaction: discord.Interaction):
        """Start listening to voice channel and transcribe speech.

        Args:
            interaction: Discord interaction
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Check if Whisper is available
            if not self.voice_activity_detector:
                await interaction.followup.send(
                    "❌ Voice activity detection is not available.\n"
                    "Enable it with `WHISPER_ENABLED=true` in .env\n"
                    "Install with: `pip install openai-whisper`",
                    ephemeral=True,
                )
                return

            # Check if bot is in voice channel
            guild_id = interaction.guild.id
            if guild_id not in self.voice_clients:
                await interaction.followup.send(
                    "❌ Bot is not in a voice channel! Use `/join` first.",
                    ephemeral=True,
                )
                return

            # Check if already listening
            if self.voice_activity_detector.is_recording(guild_id):
                await interaction.followup.send(
                    "⚠️ Already listening in this server!",
                    ephemeral=True,
                )
                return

            voice_client = self.voice_clients[guild_id]

            # Start recording
            success = await self.voice_activity_detector.start_recording(
                guild_id=guild_id,
                user_id=interaction.user.id,
                voice_client=voice_client,
            )

            if success:
                await interaction.followup.send(
                    format_success(
                        f"🎤 Now listening to voice channel!\n"
                        f"Speak naturally - I'll transcribe after {Config.WHISPER_SILENCE_THRESHOLD}s of silence.\n"
                        f"Use `/stop_listening` to stop."
                    ),
                    ephemeral=True,
                )
                logger.info(f"Started listening in guild {guild_id}")
            else:
                await interaction.followup.send(
                    format_error("Failed to start voice activity detection"),
                    ephemeral=True,
                )

        except Exception as e:
            logger.error(f"Listen command failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="stop_listening", description="Stop listening to voice channel")
    async def stop_listening(self, interaction: discord.Interaction):
        """Stop listening and transcribe recorded audio.

        Args:
            interaction: Discord interaction
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            if not self.voice_activity_detector:
                await interaction.followup.send(
                    "❌ Voice activity detection is not available.",
                    ephemeral=True,
                )
                return

            guild_id = interaction.guild.id

            # Check if recording
            if not self.voice_activity_detector.is_recording(guild_id):
                await interaction.followup.send(
                    "❌ Not currently listening in this server!",
                    ephemeral=True,
                )
                return

            await interaction.followup.send(
                "🔄 Stopping and transcribing audio...",
                ephemeral=True,
            )

            # Stop recording and transcribe
            result = await self.voice_activity_detector.stop_recording(guild_id)

            if result and result.get("text"):
                transcription = result["text"]
                language = result.get("language", "unknown")

                # Send transcription result
                embed = discord.Embed(
                    title="🎤 Voice Transcription",
                    description=transcription,
                    color=discord.Color.blue(),
                )
                embed.add_field(name="Language", value=language, inline=True)
                embed.add_field(
                    name="Detected by",
                    value=f"{interaction.user.name}",
                    inline=True,
                )

                await interaction.channel.send(embed=embed)
                await interaction.followup.send(
                    format_success("✅ Transcription complete!"),
                    ephemeral=True,
                )

                logger.info(f"Transcribed: {transcription[:100]}...")
            else:
                await interaction.followup.send(
                    "⚠️ No audio was recorded or transcription failed.",
                    ephemeral=True,
                )

        except Exception as e:
            logger.error(f"Stop listening command failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="stt_status", description="Check speech-to-text status")
    async def stt_status(self, interaction: discord.Interaction):
        """Check Whisper STT service status.

        Args:
            interaction: Discord interaction
        """
        try:
            if not self.voice_activity_detector:
                await interaction.response.send_message(
                    "❌ **Whisper STT:** Not available\n\n"
                    "To enable:\n"
                    "1. Set `WHISPER_ENABLED=true` in .env\n"
                    "2. Install: `pip install openai-whisper`\n"
                    "3. Restart the bot",
                    ephemeral=True,
                )
                return

            whisper = self.voice_activity_detector.whisper

            embed = discord.Embed(
                title="🎤 Speech-to-Text Status",
                color=discord.Color.green(),
            )

            embed.add_field(
                name="Status",
                value="✅ Available" if whisper.is_available() else "❌ Not Available",
                inline=True,
            )
            embed.add_field(
                name="Model",
                value=whisper.model_size.capitalize(),
                inline=True,
            )
            embed.add_field(
                name="Device",
                value=whisper.device.upper(),
                inline=True,
            )
            embed.add_field(
                name="Language",
                value=whisper.language or "Auto-detect",
                inline=True,
            )

            # Check if currently recording
            guild_id = interaction.guild.id
            is_listening = self.voice_activity_detector.is_recording(guild_id)
            embed.add_field(
                name="Currently Listening",
                value="🎙️ Yes" if is_listening else "⏸️ No",
                inline=True,
            )

            # Memory estimate
            memory_info = whisper.estimate_model_memory()
            embed.add_field(
                name="Memory Usage",
                value=f"RAM: ~{memory_info['ram']} MB\nVRAM: ~{memory_info['vram']} MB",
                inline=True,
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"STT status command failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

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
