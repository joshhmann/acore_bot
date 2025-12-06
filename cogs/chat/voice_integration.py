"""Voice integration for TTS and voice channel handling."""

import asyncio
import discord
import logging
import uuid
import json
import subprocess
import os
from pathlib import Path

from config import Config

logger = logging.getLogger(__name__)


class VoiceIntegration:
    """Handles TTS generation and voice channel integration."""

    def __init__(self, bot, sentiment_analyzer):
        """Initialize voice integration.

        Args:
            bot: Discord bot instance
            sentiment_analyzer: Function to analyze text sentiment
        """
        self.bot = bot
        self._analyze_sentiment = sentiment_analyzer

    async def speak_response_in_voice(self, guild: discord.Guild, text: str):
        """Speak the response in voice channel if bot is connected.

        Args:
            guild: Discord guild
            text: Text to speak
        """
        try:
            # Get voice cog to access TTS
            voice_cog = self.bot.get_cog("VoiceCog")
            if not voice_cog:
                return

            # Check if bot is in a voice channel in this guild
            voice_client = guild.voice_client
            if not voice_client or not voice_client.is_connected():
                return

            # Don't interrupt if already playing
            if voice_client.is_playing():
                logger.info("Voice client already playing, skipping TTS")
                return

            # Analyze sentiment for voice modulation
            sentiment = self._analyze_sentiment(text)
            kokoro_speed = 1.0
            edge_rate = "+0%"

            if sentiment == "positive":
                kokoro_speed = 1.1
                edge_rate = "+10%"
            elif sentiment == "negative":
                kokoro_speed = 0.9
                edge_rate = "-10%"

            # Generate TTS
            audio_file = Config.TEMP_DIR / f"tts_{uuid.uuid4()}.mp3"
            await voice_cog.tts.generate(
                text, audio_file, speed=kokoro_speed, rate=edge_rate
            )

            # Apply RVC if enabled
            if voice_cog.rvc and voice_cog.rvc.is_enabled() and Config.RVC_ENABLED:
                rvc_file = Config.TEMP_DIR / f"rvc_{uuid.uuid4()}.mp3"
                await voice_cog.rvc.convert(
                    audio_file,
                    rvc_file,
                    model_name=Config.DEFAULT_RVC_MODEL,
                    pitch_shift=Config.RVC_PITCH_SHIFT,
                    index_rate=Config.RVC_INDEX_RATE,
                    protect=Config.RVC_PROTECT,
                )
                audio_file = rvc_file

            # Play audio with explicit FFmpeg options for proper conversion
            # Log detailed audio file info
            file_size = os.path.getsize(audio_file) if os.path.exists(audio_file) else 0
            logger.info(f"=== AUDIO PLAYBACK DEBUG ===")
            logger.info(f"File path: {audio_file}")
            logger.info(f"File size: {file_size} bytes")
            logger.info(f"File extension: {audio_file.suffix}")
            logger.info(
                f"FFmpeg options: -vn -af aresample=48000,aformat=sample_fmts=s16:channel_layouts=stereo"
            )

            # Probe audio file properties
            try:
                probe_result = subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "quiet",
                        "-print_format",
                        "json",
                        "-show_format",
                        "-show_streams",
                        str(audio_file),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if probe_result.returncode == 0:
                    probe_data = json.loads(probe_result.stdout)
                    if "streams" in probe_data and len(probe_data["streams"]) > 0:
                        stream = probe_data["streams"][0]
                        logger.info(
                            f"Audio properties - Sample rate: {stream.get('sample_rate')}, Channels: {stream.get('channels')}, Format: {probe_data.get('format', {}).get('format_name')}"
                        )
            except Exception as probe_error:
                logger.warning(f"Could not probe audio file: {probe_error}")

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
            logger.info(
                f"Speaking AI response in voice channel: {voice_client.channel.name}"
            )

        except Exception as e:
            logger.error(f"Failed to speak response in voice: {e}")

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
                logger.debug(f"Cleaned up audio file: {audio_file}")
        except Exception as e:
            logger.error(f"Failed to cleanup audio file: {e}")
