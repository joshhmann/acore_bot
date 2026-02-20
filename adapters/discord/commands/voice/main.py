"""Voice cog for TTS and RVC features."""

import discord
from discord.ext import commands
import logging
from pathlib import Path
from typing import Optional
import asyncio
import uuid

from config import Config
from services.voice.tts import TTSService
from services.voice.rvc import UnifiedRVCService
from services.voice.listener import EnhancedVoiceListener
from services.voice.commands import VoiceCommandParser, CommandType
from utils.helpers import format_error, format_success
from .manager import VoiceManager
from .commands import VoiceCommands

logger = logging.getLogger(__name__)


# TODO: Implement sound effects service
async def get_sound_effects_service():
    """Placeholder function for sound effects service."""

    class MockSoundEffects:
        effects = []
        enabled = False
        global_volume = 0.5

    return MockSoundEffects()


class VoiceCog(commands.Cog):
    """Cog for voice commands (TTS and RVC)."""

    def __init__(
        self,
        bot: commands.Bot,
        tts: TTSService,
        rvc: Optional[UnifiedRVCService] = None,
        voice_activity_detector=None,
        enhanced_voice_listener: Optional[EnhancedVoiceListener] = None,
    ):
        """Initialize voice cog."""
        self.bot = bot
        self.tts = tts
        self.rvc = rvc
        self.voice_activity_detector = voice_activity_detector
        self.enhanced_listener = enhanced_voice_listener
        self.voice_manager = VoiceManager(bot)

    async def cog_load(self):
        """Load sub-cogs (commands)."""
        # Register command cog
        await self.bot.add_cog(VoiceCommands(self.bot, self))

    def play_audio(self, guild_id: int, audio_file: Path):
        """Helper to play audio in a guild."""
        voice_client = self.voice_manager.get_voice_client(guild_id)
        if not voice_client:
            return

        # Play audio with explicit FFmpeg options for proper conversion
        audio_source = discord.FFmpegPCMAudio(
            str(audio_file),
            options="-vn -af aresample=48000,aformat=sample_fmts=s16:channel_layouts=stereo",
        )
        voice_client.play(
            audio_source,
            after=lambda e: asyncio.run_coroutine_threadsafe(
                self._cleanup_audio(audio_file, e), self.bot.loop
            ),
        )

    # MOVED TO commands.py
    # @app_commands.command(
    #     name="voices", description="List available TTS and RVC voices"
    # )
    async def get_voices_info(self, interaction: discord.Interaction):
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

    # MOVED TO commands.py
    # @app_commands.command(name="set_voice", description="Change the default TTS voice")
    # @app_commands.describe(voice="Voice name (e.g., af_bella, am_adam, bf_emma)")
    async def change_voice(self, interaction: discord.Interaction, voice: str):
        """Change the default TTS voice.

        Args:
            interaction: Discord interaction
            voice: Voice name to use
        """
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

    # MOVED TO commands.py (deprecated - use list_kokoro_voices instead)
    # @app_commands.command(
    #     name="list_tts_voices", description="List all available TTS voices"
    # )
    # @app_commands.describe(language="Filter by language code (e.g., en, es, fr)")
    async def get_tts_voices_by_language(
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
                voice_text = "\n".join(
                    [f"• {v}" for v in voice_list[:10]]
                )  # Limit to 10 per lang
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

    # MOVED TO commands.py
    # @app_commands.command(
    #     name="list_kokoro_voices", description="List all available Kokoro TTS voices"
    # )
    async def get_kokoro_voices_info(self, interaction: discord.Interaction):
        """List all available Kokoro voices with descriptions.

        Args:
            interaction: Discord interaction
        """
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

    # MOVED TO commands.py - keeping here for reference during refactor
    # @app_commands.command(name="listen", description="Start smart listening with automatic speech detection")
    # @app_commands.checks.cooldown(1, 5.0)  # 1 use per 5 seconds per user (expensive operation)
    async def start_listening_session(self, interaction: discord.Interaction):
        """Start smart listening to voice channel with automatic transcription.

        Args:
            interaction: Discord interaction
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Check if enhanced listener is available
            if not self.enhanced_listener:
                await interaction.followup.send(
                    "❌ Voice activity detection is not available.\n"
                    "Enable it with `WHISPER_ENABLED=true` in .env\n"
                    "Install with: `pip install faster-whisper`",
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
            if self.enhanced_listener.is_listening(guild_id):
                await interaction.followup.send(
                    "⚠️ Already listening in this server!",
                    ephemeral=True,
                )
                return

            voice_client = self.voice_manager.get_voice_client(guild_id)
            channel = interaction.channel

            # Define callbacks
            async def on_transcription(text: str, language: str):
                """Called when transcription is complete."""
                try:
                    embed = discord.Embed(
                        title="🎤 Voice Transcription",
                        description=text,
                        color=discord.Color.blue(),
                    )
                    embed.add_field(name="Language", value=language, inline=True)
                    await channel.send(embed=embed)
                except Exception as e:
                    logger.error(f"Failed to send transcription: {e}")

            async def on_bot_response_needed(text: str):
                """Called when bot should respond to the transcription."""
                try:
                    # Update dashboard
                    if hasattr(self.bot, "web_dashboard"):
                        self.bot.web_dashboard.set_status(
                            "Thinking", f"Processing voice input: {text[:30]}..."
                        )

                    # Parse for voice commands
                    parser = VoiceCommandParser()
                    command = parser.parse(text)

                    # Handle music commands
                    if parser.is_music_command(command):
                        music_cog = self.bot.get_cog("MusicCog")
                        if not music_cog:
                            logger.warning("MusicCog not found")
                            await channel.send("❌ Music feature not available.")
                            return

                        vc = self.voice_manager.get_voice_client(guild_id)
                        if not vc:
                            await channel.send("❌ Not connected to voice channel.")
                            return

                        logger.info(
                            f"Voice command detected: {command.type.value} (arg: {command.argument})"
                        )

                        # Helper function to send both text and voice response
                        async def send_response(text: str, voice_text: str = None):
                            """Send text to channel and speak response."""
                            await channel.send(text)
                            if voice_text is None:
                                # Strip emoji and markdown for voice
                                voice_text = text.replace("**", "").replace("*", "")
                                for emoji in [
                                    "🎵",
                                    "✅",
                                    "❌",
                                    "⏭️",
                                    "⏹️",
                                    "⏸️",
                                    "▶️",
                                    "🔊",
                                    "📋",
                                    "🔀",
                                ]:
                                    voice_text = voice_text.replace(emoji, "")
                                voice_text = voice_text.strip()

                            # Speak the response
                            try:
                                await self.speak_in_voice(
                                    voice_text, guild_id, priority=True
                                )
                            except Exception as e:
                                logger.error(f"Failed to speak response: {e}")

                        # Route to appropriate music command
                        if command.type == CommandType.PLAY and command.argument:
                            await send_response(
                                f"🎵 Searching for: **{command.argument}**",
                                f"Searching for {command.argument}",
                            )
                            song = await music_cog.music_player.search_song(
                                command.argument, requester="Voice Command"
                            )
                            if song:
                                await music_cog.music_player.add_to_queue(
                                    guild_id, song
                                )
                                # Don't speak "Playing..." - just send text and let music play
                                await channel.send(
                                    f"✅ Added **{song.title}** to queue"
                                )

                                # Wait for TTS to finish before starting music
                                state = music_cog.music_player.get_state(guild_id)
                                if not state.is_playing:
                                    # Wait for voice client to finish speaking
                                    if vc.is_playing():
                                        logger.debug(
                                            "Waiting for TTS to finish before starting music..."
                                        )
                                        while vc.is_playing():
                                            await asyncio.sleep(0.1)
                                    await music_cog.music_player.play_next(guild_id, vc)
                            else:
                                await send_response(
                                    f"❌ Could not find: {command.argument}",
                                    f"Sorry, I couldn't find {command.argument}",
                                )

                        elif command.type == CommandType.SKIP:
                            current = music_cog.music_player.get_now_playing(guild_id)
                            if current:
                                await music_cog.music_player.skip(guild_id, vc)
                                await send_response(
                                    f"⏭️ Skipped **{current.title}**", "Skipping"
                                )
                            else:
                                await send_response(
                                    "❌ Nothing is playing", "Nothing is playing"
                                )

                        elif command.type == CommandType.STOP:
                            await music_cog.music_player.stop(guild_id, vc)
                            await send_response("⏹️ Stopped playback", "Music stopped")

                        elif command.type == CommandType.PAUSE:
                            if await music_cog.music_player.pause(guild_id, vc):
                                await send_response("⏸️ Paused", "Paused")
                            else:
                                await send_response(
                                    "❌ Nothing to pause", "Nothing to pause"
                                )

                        elif command.type == CommandType.RESUME:
                            if await music_cog.music_player.resume(guild_id, vc):
                                await send_response("▶️ Resumed", "Resuming")
                            else:
                                await send_response(
                                    "❌ Nothing to resume", "Nothing to resume"
                                )

                        elif command.type == CommandType.VOLUME:
                            if command.argument:
                                try:
                                    if command.argument.startswith("+"):
                                        state = music_cog.music_player.get_state(
                                            guild_id
                                        )
                                        new_vol = min(
                                            100,
                                            int(state.volume * 100)
                                            + int(command.argument[1:]),
                                        )
                                    elif command.argument.startswith("-"):
                                        state = music_cog.music_player.get_state(
                                            guild_id
                                        )
                                        new_vol = max(
                                            0,
                                            int(state.volume * 100)
                                            - int(command.argument[1:]),
                                        )
                                    else:
                                        new_vol = int(command.argument)
                                    music_cog.music_player.set_volume(
                                        guild_id, new_vol / 100, vc
                                    )
                                    await send_response(
                                        f"🔊 Volume: **{new_vol}%**",
                                        f"Volume set to {new_vol} percent",
                                    )
                                except ValueError:
                                    await send_response(
                                        "❌ Invalid volume", "Invalid volume"
                                    )

                        elif command.type == CommandType.NOWPLAYING:
                            current = music_cog.music_player.get_now_playing(guild_id)
                            if current:
                                await send_response(
                                    f"🎵 Now playing: **{current.title}** ({current.duration_str})",
                                    f"Now playing {current.title}",
                                )
                            else:
                                await send_response(
                                    "❌ Nothing is playing", "Nothing is playing"
                                )

                        elif command.type == CommandType.QUEUE:
                            queue = music_cog.music_player.get_queue(guild_id)
                            if queue:
                                queue_text = "\n".join(
                                    [
                                        f"{i + 1}. {s.title}"
                                        for i, s in enumerate(queue[:5])
                                    ]
                                )
                                await send_response(
                                    f"📋 Queue:\n{queue_text}",
                                    f"There are {len(queue)} songs in the queue",
                                )
                            else:
                                await send_response(
                                    "📋 Queue is empty", "Queue is empty"
                                )

                        elif command.type == CommandType.SHUFFLE:
                            count = music_cog.music_player.shuffle_queue(guild_id)
                            if count:
                                await send_response(
                                    f"🔀 Shuffled {count} songs",
                                    f"Shuffled {count} songs",
                                )
                            else:
                                await send_response(
                                    "❌ Not enough songs to shuffle",
                                    "Not enough songs to shuffle",
                                )

                        elif command.type == CommandType.DISCONNECT:
                            music_cog.music_player.cleanup(guild_id)
                            await vc.disconnect()
                            await send_response("👋 Disconnected", "Disconnecting")

                        return  # Don't continue to chat response

                    # Regular chat - get the chat cog to generate a response
                    chat_cog = self.bot.get_cog("ChatCog")
                    if not chat_cog:
                        logger.warning("ChatCog not found - cannot generate response")
                        return

                    logger.info(f"Generating response for voice input: {text}")

                    # Build simple history with the voice transcription
                    history = [{"role": "user", "content": text}]

                    # Generate response using Ollama
                    response = await chat_cog.ollama.chat(
                        history, system_prompt=chat_cog.system_prompt
                    )

                    if not response:
                        logger.warning("Empty response from Ollama")
                        return

                    # Send response as text
                    await channel.send(f"🤖 {response[:1900]}")
                    logger.info(f"Sent voice response: {response[:100]}...")

                    # Speak the response if connected to voice
                    if guild_id not in self.voice_clients:
                        return
                    vc = self.voice_manager.get_voice_client(guild_id)

                    if vc and not vc.is_playing():
                        try:
                            # Generate TTS
                            audio_file = (
                                Config.TEMP_DIR / f"voice_response_{uuid.uuid4()}.wav"
                            )
                            await self.tts.generate(response, audio_file)

                            # Apply RVC if enabled
                            if (
                                self.rvc
                                and self.rvc.is_enabled()
                                and Config.RVC_ENABLED
                            ):
                                rvc_file = (
                                    Config.TEMP_DIR / f"rvc_response_{uuid.uuid4()}.wav"
                                )
                                await self.rvc.convert(
                                    audio_file,
                                    rvc_file,
                                    model_name=Config.DEFAULT_RVC_MODEL,
                                    pitch_shift=Config.RVC_PITCH_SHIFT,
                                    index_rate=Config.RVC_INDEX_RATE,
                                    protect=Config.RVC_PROTECT,
                                )
                                audio_file = rvc_file

                            # Play audio with explicit FFmpeg options for proper conversion
                            audio_source = discord.FFmpegPCMAudio(
                                str(audio_file),
                                before_options="-f wav",
                                options="-vn -af aresample=48000,aformat=sample_fmts=s16:channel_layouts=stereo",
                            )
                            vc.play(
                                audio_source,
                                after=lambda e: asyncio.run_coroutine_threadsafe(
                                    self._cleanup_audio(audio_file, e), self.bot.loop
                                ),
                            )
                            logger.info("Playing voice response audio")
                        except Exception as tts_error:
                            logger.error(f"Failed to generate/play TTS: {tts_error}")

                except Exception as e:
                    logger.error(f"Failed to generate bot response: {e}")

            # Start smart listening
            success = await self.enhanced_listener.start_smart_listen(
                guild_id=guild_id,
                user_id=interaction.user.id,
                voice_client=voice_client,
                temp_dir=Config.TEMP_DIR,
                on_transcription=on_transcription,
                on_bot_response_needed=on_bot_response_needed,
            )

            if success:
                await interaction.followup.send(
                    format_success(
                        f"🎤 Now listening with smart detection!\n\n"
                        f"**Features:**\n"
                        f"• Auto-transcription after {Config.WHISPER_SILENCE_THRESHOLD}s silence\n"
                        f"• Smart response triggers (questions, bot mentions, commands)\n"
                        f"• Transcriptions shown in chat\n\n"
                        f"Use `/stop_listening` to stop."
                    ),
                    ephemeral=True,
                )
                logger.info(f"Started smart listening in guild {guild_id}")

                if hasattr(self.bot, "web_dashboard"):
                    self.bot.web_dashboard.set_status(
                        "Listening", "Smart voice detection active"
                    )
            else:
                await interaction.followup.send(
                    format_error("Failed to start smart voice detection"),
                    ephemeral=True,
                )

        except Exception as e:
            logger.error(f"Listen command failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    # MOVED TO commands.py - keeping here for reference during refactor
    # @app_commands.command(
    #     name="stop_listening", description="Stop listening to voice channel"
    # )
    async def stop_listening_session(self, interaction: discord.Interaction):
        """Stop listening and transcribe any remaining audio.

        Args:
            interaction: Discord interaction
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            if not self.enhanced_listener:
                await interaction.followup.send(
                    "❌ Voice activity detection is not available.",
                    ephemeral=True,
                )
                return

            guild_id = interaction.guild.id

            # Check if listening
            if not self.enhanced_listener.is_listening(guild_id):
                await interaction.followup.send(
                    "❌ Not currently listening in this server!",
                    ephemeral=True,
                )
                return

            # Get session duration
            duration = self.enhanced_listener.get_session_duration(guild_id)

            await interaction.followup.send(
                "🔄 Stopping smart listener...",
                ephemeral=True,
            )

            # Stop listening and transcribe any remaining audio
            result = await self.enhanced_listener.stop_listen(guild_id)

            if result and result.get("text"):
                transcription = result["text"]
                language = result.get("language", "unknown")

                # Send final transcription
                embed = discord.Embed(
                    title="🎤 Final Voice Transcription",
                    description=transcription,
                    color=discord.Color.green(),
                )
                embed.add_field(name="Language", value=language, inline=True)
                embed.add_field(
                    name="Session Duration",
                    value=f"{duration:.1f}s",
                    inline=True,
                )

                await interaction.channel.send(embed=embed)
                await interaction.followup.send(
                    format_success(f"✅ Stopped listening (session: {duration:.1f}s)"),
                    ephemeral=True,
                )

                logger.info(
                    f"Stopped listening - final transcription: {transcription[:100]}..."
                )
            else:
                await interaction.followup.send(
                    format_success(
                        f"✅ Stopped listening (session: {duration:.1f}s)\nNo final audio to transcribe."
                    ),
                    ephemeral=True,
                )

        except Exception as e:
            logger.error(f"Stop listening command failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    # MOVED TO commands.py
    # @app_commands.command(name="stt_status", description="Check speech-to-text status")
    async def get_stt_status_info(self, interaction: discord.Interaction):
        """Check Whisper STT service status.

        Args:
            interaction: Discord interaction
        """
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

    # Sound effects commands disabled - service was removed
    # @app_commands.command(name="reload_sounds", description="Reload sound effects configuration")
    # async def reload_sounds(self, interaction: discord.Interaction):
    #     """Reload sound effects from config file."""
    #     await interaction.response.send_message("❌ Sound effects feature is currently disabled", ephemeral=True)

    # @app_commands.command(name="list_sounds", description="Show all available sound effects")
    async def list_sounds_disabled(self, interaction: discord.Interaction):
        """List all available sound effects and their triggers.

        Args:
            interaction: Discord interaction
        """
        try:
            sound_effects = await get_sound_effects_service()

            if not sound_effects.effects:
                await interaction.response.send_message(
                    "❌ No sound effects configured. Add sounds to `sound_effects/` directory!",
                    ephemeral=True,
                )
                return

            # Create embed
            embed = discord.Embed(
                title="🔊 Sound Effects",
                description=f"Available reaction sounds ({len(sound_effects.effects)} loaded)",
                color=discord.Color.blue(),
            )

            # Add each effect as a field
            for effect in sound_effects.effects[:25]:  # Discord limit: 25 fields
                triggers_text = ", ".join([f"`{t}`" for t in effect.triggers[:5]])
                if len(effect.triggers) > 5:
                    triggers_text += f" +{len(effect.triggers) - 5} more"

                cooldown_status = "✅ Ready" if effect.can_play() else "⏳ On cooldown"

                embed.add_field(
                    name=f"**{effect.name}** ({cooldown_status})",
                    value=f"Triggers: {triggers_text}\nCooldown: {effect.cooldown}s",
                    inline=False,
                )

            # Add status info
            status = "🟢 Enabled" if sound_effects.enabled else "🔴 Disabled"
            embed.set_footer(
                text=f"Status: {status} | Volume: {int(sound_effects.global_volume * 100)}%"
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"List sounds command failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    # @app_commands.command(name="toggle_sounds", description="Enable or disable sound effects")
    async def toggle_sounds_disabled(self, interaction: discord.Interaction):
        """Toggle sound effects on/off.

        Args:
            interaction: Discord interaction
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            sound_effects = await get_sound_effects_service()
            sound_effects.enabled = not sound_effects.enabled

            status = "enabled" if sound_effects.enabled else "disabled"
            emoji = "🔊" if sound_effects.enabled else "🔇"

            await interaction.followup.send(
                format_success(f"{emoji} Sound effects {status}"),
                ephemeral=True,
            )
            logger.info(f"Sound effects {status} by {interaction.user}")

        except Exception as e:
            logger.error(f"Toggle sounds command failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    async def speak_in_voice(self, text: str, guild_id: int, priority: bool = False):
        """Speak text in voice channel without Discord interaction.

        Args:
            text: Text to speak
            guild_id: Guild ID
            priority: If True, interrupt current playback
        """
        try:
            # Check if connected to voice
            if guild_id not in self.voice_clients:
                logger.warning(
                    f"Cannot speak in voice - not connected to guild {guild_id}"
                )
                return
            voice_client = self.voice_manager.get_voice_client(guild_id)

            # Check if already playing
            if voice_client.is_playing() and not priority:
                logger.debug("Skipping voice response - already playing")
                return

            # Generate TTS
            audio_file = Config.TEMP_DIR / f"tts_{uuid.uuid4()}.mp3"
            await self.tts.generate(text, audio_file)

            # Apply RVC if enabled and available
            if self.rvc and self.rvc.is_enabled() and Config.RVC_ENABLED:
                rvc_file = Config.TEMP_DIR / f"rvc_{uuid.uuid4()}.mp3"
                await self.rvc.convert(
                    audio_file,
                    rvc_file,
                    model_name=Config.DEFAULT_RVC_MODEL,
                    pitch_shift=Config.RVC_PITCH_SHIFT,
                    index_rate=Config.RVC_INDEX_RATE,
                    protect=Config.RVC_PROTECT,
                )
                audio_file = rvc_file

            # Stop current playback if priority
            if priority and voice_client.is_playing():
                voice_client.stop()

            # Play audio with explicit FFmpeg options for proper conversion
            audio_source = discord.FFmpegPCMAudio(
                str(audio_file),
                options="-vn -af aresample=48000,aformat=sample_fmts=s16:channel_layouts=stereo",
            )
            # Mark as TTS for smart barge-in
            audio_source._is_tts = True

            voice_client.play(
                audio_source,
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self._cleanup_audio(audio_file, e), self.bot.loop
                ),
            )

            logger.info(f"Speaking in voice: {text[:50]}...")

        except Exception as e:
            logger.error(f"Speak in voice failed: {e}")

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

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        """Clean up voice client when bot is removed from a guild.

        This prevents memory leaks from orphaned voice client references.

        Args:
            guild: The guild the bot was removed from
        """
        await self.voice_manager.cleanup_guild(guild.id)


async def setup(bot: commands.Bot):
    """Setup function for the cog."""
    # This will be called from main.py with proper dependencies
    pass
