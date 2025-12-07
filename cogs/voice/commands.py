"""Voice commands for the bot."""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional
import uuid
import asyncio

from config import Config
from services.voice_commands import VoiceCommandParser, CommandType
from utils.helpers import format_error, format_success, format_info

logger = logging.getLogger(__name__)


class VoiceCommands(commands.Cog):
    """Cog for voice commands."""

    def __init__(self, bot, voice_cog):
        self.bot = bot
        self.voice_cog = voice_cog
        # Shortcuts for cleaner code
        self.manager = voice_cog.voice_manager
        self.tts = voice_cog.tts
        self.rvc = voice_cog.rvc
        self.enhanced_listener = voice_cog.enhanced_listener

    @app_commands.command(name="join", description="Join your voice channel")
    async def join(self, interaction: discord.Interaction):
        """Join the user's voice channel."""
        if not interaction.user.voice:
            await interaction.response.send_message(
                "❌ You need to be in a voice channel!", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        channel = interaction.user.voice.channel

        try:
            if self.manager.is_connected(interaction.guild.id):
                await interaction.followup.send(
                    "✅ Already connected to a voice channel!"
                )
                return

            voice_client = await self.manager.join_channel(
                channel, interaction.guild.id
            )
            if voice_client:
                await interaction.followup.send(
                    format_success(f"Joined **{channel.name}**!")
                )
            else:
                await interaction.followup.send(
                    format_error("Failed to join voice channel")
                )

        except Exception as e:
            logger.error(f"Failed to join voice channel: {e}")
            await interaction.followup.send(format_error(e))

    @app_commands.command(name="leave", description="Leave voice channel")
    async def leave(self, interaction: discord.Interaction):
        """Leave the current voice channel."""
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id

        if not self.manager.is_connected(guild_id):
            await interaction.followup.send("❌ Not connected to any voice channel!")
            return

        if await self.manager.leave_channel(guild_id):
            await interaction.followup.send(
                format_success("Disconnected from voice channel!")
            )
        else:
            await interaction.followup.send(
                format_error("Failed to leave voice channel")
            )

    @app_commands.command(
        name="speak", description="Generate speech and play in voice channel"
    )
    @app_commands.describe(text="Text to speak")
    @app_commands.checks.cooldown(1, 3.0)
    async def speak(self, interaction: discord.Interaction, text: str):
        """Generate TTS and play in voice channel."""
        if len(text) > 1000:
            await interaction.response.send_message(
                "❌ Text too long! Please keep speech under 1000 characters.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            guild_id = interaction.guild.id
            if not self.manager.is_connected(guild_id):
                await interaction.followup.send(
                    "❌ Not connected to a voice channel! Use `/join` first."
                )
                return

            voice_client = self.manager.get_voice_client(guild_id)
            if voice_client.is_playing():
                await interaction.followup.send(
                    "⏸️ Already playing audio. Please wait..."
                )
                return

            audio_file = Config.TEMP_DIR / f"tts_{uuid.uuid4()}.wav"
            await self.tts.generate(text, audio_file)

            if self.rvc and self.rvc.is_enabled() and Config.RVC_ENABLED:
                rvc_file = Config.TEMP_DIR / f"rvc_{uuid.uuid4()}.wav"
                await self.rvc.convert(
                    audio_file,
                    rvc_file,
                    model_name=Config.DEFAULT_RVC_MODEL,
                    pitch_shift=Config.RVC_PITCH_SHIFT,
                    index_rate=Config.RVC_INDEX_RATE,
                    protect=Config.RVC_PROTECT,
                )
                audio_file = rvc_file

            self.voice_cog.play_audio(guild_id, audio_file)
            await interaction.followup.send(format_success("🔊 Playing audio..."))

        except Exception as e:
            logger.error(f"Speak command failed: {e}")
            await interaction.followup.send(format_error(e))

    @app_commands.command(name="listen", description="Start smart listening")
    async def listen(self, interaction: discord.Interaction):
        """Start smart listening."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            if not self.enhanced_listener:
                await interaction.followup.send("❌ STT not available.", ephemeral=True)
                return

            guild_id = interaction.guild.id
            if not self.manager.is_connected(guild_id):
                await interaction.followup.send(
                    "❌ Bot must join voice first.", ephemeral=True
                )
                return

            if self.enhanced_listener.is_listening(guild_id):
                await interaction.followup.send("⚠️ Already listening.", ephemeral=True)
                return

            voice_client = self.manager.get_voice_client(guild_id)

            # Start listening (callbacks are handled in VoiceCog for simplicity or can be passed)
            # For this refactor, we'll let VoiceCog handle the callbacks logic
            # This is a bit circular, but we want to move commands out of VoiceCog

            # Delegate to VoiceCog's start_listening logic or move it here?
            # It's better to keep complex logic in VoiceCog and call it
            success = await self.voice_cog.start_listening_session(interaction)

            if (
                not success
            ):  # if start_listening_session returns False or None (handled inside)
                pass

        except Exception as e:
            logger.error(f"Listen command failed: {e}")
            await interaction.followup.send(format_error(e))

    @app_commands.command(name="stop_listening", description="Stop listening")
    async def stop_listening(self, interaction: discord.Interaction):
        """Stop listening."""
        await interaction.response.defer(ephemeral=True)
        await self.voice_cog.stop_listening_session(interaction)

    @app_commands.command(
        name="voices", description="List available TTS and RVC voices"
    )
    async def voices(self, interaction: discord.Interaction):
        """List available voices."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            embed = discord.Embed(
                title="🎙️ Available Voices",
                color=discord.Color.blue(),
            )

            # Current TTS voice
            tts_info = self.tts.get_voice_info()

            # Build voice info string based on engine
            if tts_info.get("engine") == "kokoro":
                voice_details = f"**{tts_info['voice']}**\nEngine: Kokoro\nSpeed: {tts_info.get('speed', 1.0)}x"
            elif tts_info.get("engine") == "kokoro_api":
                voice_details = f"**{tts_info['voice']}**\nEngine: Kokoro API\nSpeed: {tts_info.get('speed', 1.0)}x"
            elif tts_info.get("engine") == "supertonic":
                voice_details = f"**{tts_info['voice']}**\nEngine: Supertonic\nSpeed: {tts_info.get('speed', 1.05)}x\nSteps: {tts_info.get('steps', 5)}"
            else:
                voice_details = (
                    f"**{tts_info.get('engine', 'Unknown')}**\nEngine: Unknown"
                )

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

            embed.set_footer(
                text="Use /list_kokoro_voices to see all available TTS voices."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Voices command failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="set_voice", description="Change the default TTS voice")
    @app_commands.describe(voice="Voice name (e.g., af_bella, am_adam, bf_emma)")
    async def set_voice(self, interaction: discord.Interaction, voice: str):
        """Change the default TTS voice."""
        try:
            # Update the voice based on current TTS engine
            if Config.TTS_ENGINE == "kokoro":
                # Validate voice exists
                if hasattr(self.tts, "kokoro") and self.tts.kokoro:
                    if voice not in self.tts.kokoro.get_voices():
                        await interaction.response.send_message(
                            f"❌ Invalid voice: **{voice}**. Use `/list_kokoro_voices` to see available options.",
                            ephemeral=True,
                        )
                        return

                self.tts.kokoro_voice = voice
                engine_name = "Kokoro"
            elif Config.TTS_ENGINE == "kokoro_api":
                self.tts.kokoro_voice = voice
                engine_name = "Kokoro API"
            elif Config.TTS_ENGINE == "supertonic":
                self.tts.supertonic_voice = voice
                engine_name = "Supertonic"
            else:
                await interaction.response.send_message(
                    f"❌ Unknown TTS engine: **{Config.TTS_ENGINE}**", ephemeral=True
                )
                return

            await interaction.response.send_message(
                format_success(f"Default {engine_name} voice changed to: **{voice}**"),
                ephemeral=True,
            )

        except Exception as e:
            logger.error(f"Set_voice command failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(
        name="list_kokoro_voices", description="List all available Kokoro TTS voices"
    )
    async def list_kokoro_voices(self, interaction: discord.Interaction):
        """List all available Kokoro voices with descriptions."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Check if Kokoro is available
            if not hasattr(self.tts, "kokoro") or not self.tts.kokoro:
                await interaction.followup.send(
                    f"❌ Kokoro TTS (local) is not available. The bot is configured to use: {Config.TTS_ENGINE}",
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
                male_text = "\n".join(
                    [
                        f"**{v}**\n{voice_descriptions.get(v, 'No description')}"
                        for v in sorted(male_voices)[:8]
                    ]
                )
                embed.add_field(
                    name="🎤 Male Voices",
                    value=male_text,
                    inline=False,
                )

            # Add female voices
            if female_voices:
                female_text = "\n".join(
                    [
                        f"**{v}**\n{voice_descriptions.get(v, 'No description')}"
                        for v in sorted(female_voices)[:8]
                    ]
                )
                embed.add_field(
                    name="🎤 Female Voices",
                    value=female_text,
                    inline=False,
                )

            # Show current voice
            current_voice = getattr(self.tts, "kokoro_voice", "Unknown")
            embed.set_footer(
                text=f"Current voice: {current_voice} | Total voices: {len(voices)}"
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"List_kokoro_voices command failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="stt_status", description="Check speech-to-text status")
    async def stt_status(self, interaction: discord.Interaction):
        """Check Whisper STT service status."""
        try:
            if not self.enhanced_listener:
                await interaction.response.send_message(
                    "❌ **Whisper STT:** Not available\n\n"
                    "To enable:\n"
                    "1. Set `WHISPER_ENABLED=true` in .env\n"
                    "2. Install: `pip install faster-whisper`\n"
                    "3. Restart the bot",
                    ephemeral=True,
                )
                return

            whisper = self.enhanced_listener.whisper

            embed = discord.Embed(
                title="🎤 Smart Speech-to-Text Status",
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

            # Check if currently listening
            guild_id = interaction.guild.id
            is_listening = self.enhanced_listener.is_listening(guild_id)
            embed.add_field(
                name="Currently Listening",
                value="🎙️ Yes" if is_listening else "⏸️ No",
                inline=True,
            )

            # Silence threshold
            embed.add_field(
                name="Silence Threshold",
                value=f"{self.enhanced_listener.silence_threshold}s",
                inline=True,
            )

            # Memory estimate
            memory_info = whisper.estimate_model_memory()
            embed.add_field(
                name="Memory Usage",
                value=f"RAM: ~{memory_info['ram']} MB\nVRAM: ~{memory_info['vram']} MB",
                inline=False,
            )

            # Smart detection features
            embed.add_field(
                name="Smart Features",
                value="• Auto-silence detection\n"
                "• Smart response triggers\n"
                "• Question detection\n"
                "• Bot mention detection",
                inline=False,
            )

            # Session info if listening
            if is_listening:
                duration = self.enhanced_listener.get_session_duration(guild_id)
                embed.set_footer(text=f"Current session duration: {duration:.1f}s")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"STT status command failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)


async def setup(bot: commands.Bot):
    # This cog is loaded manually by VoiceCog, so this setup might not be used directly
    # if we want to nest it. But usually we add cogs to bot.
    pass
