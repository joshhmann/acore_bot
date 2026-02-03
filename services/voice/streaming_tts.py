"""Streaming TTS Processor - Processes LLM streams and converts to audio in real-time.

This service allows the bot to speak LLM responses as they're being generated,
reducing perceived latency for voice responses.
"""

import asyncio
import logging
from typing import AsyncIterator, Optional
from pathlib import Path
import uuid
import io

logger = logging.getLogger(__name__)


class BytesAudioSource:
    """Custom audio source that reads from bytes buffer.

    Provides audio data to Discord voice client from in-memory bytes
    instead of a file, enabling real-time streaming playback.
    """

    def __init__(self, audio_data: bytes):
        """Initialize audio source from bytes.

        Args:
            audio_data: Raw audio bytes (WAV format)
        """
        self.audio_data = audio_data
        self.position = 0

        # Parse WAV header to get audio info
        self._parse_wav_header()

    def _parse_wav_header(self):
        """Parse WAV header to extract audio format info."""
        if len(self.audio_data) < 44:
            raise ValueError("Invalid WAV file: header too short")

        # WAV header structure
        # 0-3: "RIFF"
        # 4-7: file size
        # 8-11: "WAVE"
        # 12-15: "fmt "
        # 16-19: fmt chunk size
        # 20-21: audio format (1 = PCM)
        # 22-23: number of channels
        # 24-27: sample rate
        # 28-31: byte rate
        # 32-33: block align
        # 34-35: bits per sample
        # 36-39: "data"
        # 40-43: data chunk size

        self.sample_rate = int.from_bytes(self.audio_data[24:28], byteorder="little")
        self.channels = int.from_bytes(self.audio_data[22:24], byteorder="little")
        self.bits_per_sample = int.from_bytes(
            self.audio_data[34:36], byteorder="little"
        )
        self.bytes_per_sample = self.bits_per_sample // 8
        self.frame_size = self.channels * self.bytes_per_sample

        # Find data chunk start (skip header)
        self.data_start = 44
        self.data_size = len(self.audio_data) - self.data_start

    def read(self) -> bytes:
        """Read next audio frame.

        Returns:
            Audio frame bytes or empty bytes if done
        """
        if self.position >= self.data_size:
            return b""

        # Read one frame (20ms at 48kHz = 960 frames per frame)
        frame_count = 960  # 20ms at 48kHz
        frame_size_bytes = frame_count * self.frame_size

        end_pos = min(self.position + frame_size_bytes, self.data_size)
        data = self.audio_data[
            self.data_start + self.position : self.data_start + end_pos
        ]

        # Pad with zeros if not enough data
        if len(data) < frame_size_bytes:
            data = data + b"\x00" * (frame_size_bytes - len(data))

        self.position += frame_size_bytes
        return data

    def is_opus(self) -> bool:
        """Check if this is Opus-encoded audio.

        Returns:
            False (always PCM for WAV)
        """
        return False


class StreamingTTSProcessor:
    """Processes streaming text and converts to TTS audio in real-time.

    This class handles:
    - Buffering text chunks into complete sentences
    - Generating TTS audio for each sentence
    - Playing audio through Discord voice client
    - Applying RVC voice conversion if enabled
    """

    def __init__(self, tts_service, rvc_service=None):
        """Initialize streaming TTS processor.

        Args:
            tts_service: TTSService instance for audio generation
            rvc_service: Optional RVCService for voice conversion
        """
        self.tts = tts_service
        self.rvc = rvc_service
        self.sentence_endings = {".", "!", "?", "\n"}

    async def process_stream(
        self,
        text_stream: AsyncIterator[str],
        voice_client,
        speed: float = 1.0,
        rate: str = "+0%",
    ):
        """Process text stream and play as TTS audio.

        Args:
            text_stream: Async iterator yielding text chunks
            voice_client: Discord voice client to play audio through
            speed: Kokoro TTS speed modifier
            rate: Edge TTS rate modifier

        Returns:
            Full text that was spoken
        """
        buffer = ""
        full_text = ""

        try:
            async for chunk in text_stream:
                if not voice_client.is_connected():
                    logger.debug("Voice client disconnected during text streaming")
                    break

                buffer += chunk
                full_text += chunk

                if any(ending in buffer for ending in self.sentence_endings):
                    sentences = self._split_into_sentences(buffer)

                    for sentence in sentences[:-1]:
                        if sentence.strip():
                            if not voice_client.is_connected():
                                logger.debug("Voice client disconnected, stopping")
                                return full_text
                            await self._speak_sentence(
                                sentence, voice_client, speed, rate
                            )

                    buffer = sentences[-1] if sentences else ""

            if buffer.strip() and voice_client.is_connected():
                await self._speak_sentence(buffer, voice_client, speed, rate)

        except Exception as e:
            logger.error(f"Streaming TTS error: {e}")

        return full_text

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences.

        Args:
            text: Text to split

        Returns:
            List of sentences (last may be incomplete)
        """
        sentences = []
        current = ""

        for char in text:
            current += char
            if char in self.sentence_endings:
                sentences.append(current)
                current = ""

        # Add any remaining text
        if current:
            sentences.append(current)

        return sentences if sentences else [""]

    async def _speak_sentence(
        self, sentence: str, voice_client, speed: float, rate: str
    ):
        """Generate and play TTS for a single sentence.

        Args:
            sentence: Text to speak
            voice_client: Discord voice client
            speed: TTS speed
            rate: TTS rate
        """
        # Check if voice client is still connected before proceeding
        if not voice_client.is_connected():
            logger.debug("Voice client disconnected, skipping sentence")
            return

        if voice_client.is_playing():
            while voice_client.is_playing() and voice_client.is_connected():
                await asyncio.sleep(0.1)
            # Re-check connection after waiting
            if not voice_client.is_connected():
                logger.debug("Voice client disconnected while waiting for playback")
                return

        try:
            from config import Config

            use_streaming = self.tts.engine == "qwen3tts"

            if use_streaming:
                await self._speak_with_streaming(
                    sentence, voice_client, speed, rate, Config
                )
            else:
                await self._speak_with_file(sentence, voice_client, speed, rate, Config)

        except Exception as e:
            logger.error(f"Failed to speak sentence: {e}")

    async def _speak_with_streaming(
        self, sentence: str, voice_client, speed: float, rate: str, Config
    ):
        """Generate and play TTS using streaming for qwen3tts.

        Args:
            sentence: Text to speak
            voice_client: Discord voice client
            speed: TTS speed
            rate: TTS rate
            Config: Config module
        """
        import discord

        temp_file = None
        rvc_file = None

        try:
            if not voice_client.is_connected():
                logger.debug("Voice client not connected, skipping streaming TTS")
                return

            audio_chunks = []
            language = getattr(self.tts, "qwen3tts_language", "Auto")

            logger.debug(f"Starting streaming TTS for: {sentence[:50]}...")
            async for chunk in self.tts.generate_stream(
                sentence, speed=speed, language=language
            ):
                if not voice_client.is_connected():
                    logger.debug("Voice client disconnected during streaming, aborting")
                    return
                audio_chunks.append(chunk)

            full_audio = b"".join(audio_chunks)

            if not full_audio:
                logger.warning("No audio data received from streaming TTS")
                return

            if not voice_client.is_connected():
                logger.debug(
                    "Voice client disconnected after streaming, skipping playback"
                )
                return

            if self.rvc and Config.RVC_ENABLED:
                temp_file = Path(Config.TEMP_DIR) / f"stream_tts_{uuid.uuid4()}.wav"
                temp_file.write_bytes(full_audio)

                rvc_file = Path(Config.TEMP_DIR) / f"stream_rvc_{uuid.uuid4()}.wav"
                await self.rvc.convert(temp_file, rvc_file)

                full_audio = rvc_file.read_bytes()

            if not voice_client.is_connected():
                logger.debug("Voice client disconnected after RVC, skipping playback")
                return

            audio_source = BytesAudioSource(full_audio)
            voice_client.play(audio_source)

            while voice_client.is_playing() and voice_client.is_connected():
                await asyncio.sleep(0.1)

            if not voice_client.is_connected():
                logger.debug("Voice client disconnected during playback")

        except Exception as e:
            logger.error(f"Streaming TTS failed, falling back to file-based: {e}")
            if voice_client.is_connected():
                await self._speak_with_file(sentence, voice_client, speed, rate, Config)
        finally:
            if temp_file:
                temp_file.unlink(missing_ok=True)
            if rvc_file:
                rvc_file.unlink(missing_ok=True)

    async def _speak_with_file(
        self, sentence: str, voice_client, speed: float, rate: str, Config
    ):
        """Generate and play TTS using file-based approach.

        Args:
            sentence: Text to speak
            voice_client: Discord voice client
            speed: TTS speed
            rate: TTS rate
            Config: Config module
        """
        import discord

        if not voice_client.is_connected():
            logger.debug("Voice client not connected, skipping file-based TTS")
            return

        audio_file = Path(Config.TEMP_DIR) / f"stream_tts_{uuid.uuid4()}.wav"

        try:
            await self.tts.generate(sentence, str(audio_file), speed=speed, rate=rate)

            if not voice_client.is_connected():
                logger.debug("Voice client disconnected after TTS generation")
                audio_file.unlink(missing_ok=True)
                return

            if self.rvc and Config.RVC_ENABLED:
                rvc_file = Path(Config.TEMP_DIR) / f"stream_rvc_{uuid.uuid4()}.wav"
                await self.rvc.convert(audio_file, rvc_file)
                audio_file.unlink(missing_ok=True)
                audio_file = rvc_file

                if not voice_client.is_connected():
                    logger.debug("Voice client disconnected after RVC conversion")
                    audio_file.unlink(missing_ok=True)
                    return

            audio_source = discord.FFmpegPCMAudio(
                str(audio_file),
                options="-vn -af aresample=48000,aformat=sample_fmts=s16:channel_layouts=stereo",
            )

            def after_playing(error):
                if error:
                    logger.error(f"Audio playback error: {error}")
                try:
                    audio_file.unlink(missing_ok=True)
                except Exception as e:
                    logger.debug(f"Failed to delete temp audio: {e}")

            voice_client.play(audio_source, after=after_playing)

            while voice_client.is_playing() and voice_client.is_connected():
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"File-based TTS failed: {e}")
            audio_file.unlink(missing_ok=True)
