"""Streaming TTS service for sentence-by-sentence audio generation and playback."""
import asyncio
import logging
import re
import uuid
from pathlib import Path
from typing import Optional, Callable, AsyncGenerator
from collections import deque
import discord

from config import Config

logger = logging.getLogger(__name__)


class StreamMultiplexer:
    """Multiplexes a single async generator to multiple consumers."""

    def __init__(self, source_stream):
        """Initialize multiplexer.

        Args:
            source_stream: Source async generator
        """
        self.source_stream = source_stream
        self.consumers = []
        self.buffer = []
        self.done = False
        self.task = None

    async def _consume_source(self):
        """Consume source stream and broadcast to all consumers."""
        try:
            async for chunk in self.source_stream:
                self.buffer.append(chunk)
                # Wake up all consumers
                for queue in self.consumers:
                    await queue.put(chunk)
        finally:
            self.done = True
            # Signal completion to all consumers
            for queue in self.consumers:
                await queue.put(None)

    async def create_consumer(self) -> AsyncGenerator[str, None]:
        """Create a new consumer of the stream.

        Returns:
            Async generator yielding chunks
        """
        queue = asyncio.Queue()
        self.consumers.append(queue)

        # Start consuming source if not already started
        if not self.task:
            self.task = asyncio.create_task(self._consume_source())

        # Yield chunks from queue
        while True:
            chunk = await queue.get()
            if chunk is None:  # End signal
                break
            yield chunk


class StreamingTTSProcessor:
    """Processes TTS in real-time as sentences are generated from LLM streaming."""

    def __init__(self, tts_service, rvc_service=None):
        """Initialize streaming TTS processor.

        Args:
            tts_service: TTS service instance
            rvc_service: Optional RVC service for voice conversion
        """
        self.tts = tts_service
        self.rvc = rvc_service
        self.is_processing = False
        self.sentence_queue = deque()
        self.audio_queue = deque()
        self.current_task = None

    def extract_sentences(self, text: str) -> list[str]:
        """Extract complete sentences from text.

        Args:
            text: Text to extract sentences from

        Returns:
            List of complete sentences
        """
        # Split on sentence boundaries (., !, ?)
        # Keep the punctuation with the sentence
        sentences = re.split(r'([.!?]+)', text)

        # Recombine sentences with their punctuation
        combined = []
        for i in range(0, len(sentences) - 1, 2):
            sentence = sentences[i].strip()
            punct = sentences[i + 1] if i + 1 < len(sentences) else ''
            if sentence:
                combined.append(sentence + punct)

        # Handle any remaining text without punctuation
        if len(sentences) % 2 == 1 and sentences[-1].strip():
            combined.append(sentences[-1].strip())

        return [s for s in combined if s.strip()]

    async def generate_audio_for_sentence(
        self,
        sentence: str,
        speed: float = 1.0,
        rate: str = "+0%"
    ) -> Optional[Path]:
        """Generate audio file for a single sentence.

        Args:
            sentence: Sentence to convert to audio
            speed: Speed multiplier for Kokoro/Supertonic
            rate: Rate adjustment for Edge TTS

        Returns:
            Path to generated audio file or None if failed
        """
        try:
            # Generate unique filename
            audio_file = Config.TEMP_DIR / f"stream_tts_{uuid.uuid4()}.mp3"

            # Generate TTS
            await self.tts.generate(
                sentence,
                audio_file,
                speed=speed,
                rate=rate
            )

            # Apply RVC if enabled
            if self.rvc and self.rvc.is_enabled() and Config.RVC_ENABLED:
                rvc_file = Config.TEMP_DIR / f"stream_rvc_{uuid.uuid4()}.mp3"
                await self.rvc.convert(
                    audio_file,
                    rvc_file,
                    model_name=Config.DEFAULT_RVC_MODEL,
                    pitch_shift=Config.RVC_PITCH_SHIFT,
                    index_rate=Config.RVC_INDEX_RATE,
                    protect=Config.RVC_PROTECT
                )
                # Delete original TTS file
                try:
                    audio_file.unlink()
                except Exception:
                    pass
                audio_file = rvc_file

            logger.debug(f"Generated audio for sentence: {sentence[:50]}...")
            return audio_file

        except Exception as e:
            logger.error(f"Failed to generate audio for sentence: {e}")
            return None

    async def process_stream(
        self,
        llm_stream,
        voice_client: discord.VoiceClient,
        speed: float = 1.0,
        rate: str = "+0%",
        on_sentence_complete: Optional[Callable[[str], None]] = None
    ):
        """Process LLM stream and generate TTS in real-time.

        This method runs in parallel with LLM generation, processing
        complete sentences as they arrive.

        Args:
            llm_stream: Async generator yielding text chunks from LLM
            voice_client: Discord voice client to play audio
            speed: Speed multiplier for Kokoro/Supertonic
            rate: Rate adjustment for Edge TTS
            on_sentence_complete: Optional callback when sentence is complete
        """
        import time
        stream_start = time.time()
        first_audio_time = None
        sentence_count = 0

        self.is_processing = True
        buffer = ""
        audio_files = []
        playback_task = None

        try:
            # Process LLM stream
            async for chunk in llm_stream:
                buffer += chunk

                # Extract complete sentences
                sentences = self.extract_sentences(buffer)

                # If we have at least one complete sentence
                if len(sentences) > 0:
                    # Keep last "sentence" in buffer (might be incomplete)
                    last_part = sentences[-1]

                    # Check if last part ends with sentence terminator
                    if last_part and last_part[-1] in '.!?':
                        # All sentences are complete
                        complete_sentences = sentences
                        buffer = ""
                    else:
                        # Last part is incomplete, keep in buffer
                        complete_sentences = sentences[:-1]
                        buffer = last_part

                    # Process each complete sentence
                    for sentence in complete_sentences:
                        if sentence.strip():
                            # Generate audio for this sentence
                            audio_file = await self.generate_audio_for_sentence(
                                sentence,
                                speed=speed,
                                rate=rate
                            )

                            if audio_file:
                                sentence_count += 1
                                audio_files.append(audio_file)

                                # Track time to first audio
                                if first_audio_time is None:
                                    first_audio_time = time.time()
                                    ttfa = first_audio_time - stream_start
                                    logger.info(f"⚡ Streaming TTS: Time to first audio (TTFA): {ttfa:.2f}s")

                                # Start playback if not already playing
                                if not playback_task or playback_task.done():
                                    playback_task = asyncio.create_task(
                                        self._play_audio_queue(voice_client, audio_files)
                                    )

                                # Callback notification
                                if on_sentence_complete:
                                    try:
                                        on_sentence_complete(sentence)
                                    except Exception as e:
                                        logger.error(f"Sentence callback error: {e}")

            # Process any remaining text in buffer
            if buffer.strip():
                audio_file = await self.generate_audio_for_sentence(
                    buffer,
                    speed=speed,
                    rate=rate
                )
                if audio_file:
                    audio_files.append(audio_file)

            # Wait for all audio to finish playing
            if playback_task and not playback_task.done():
                await playback_task

            # Performance summary
            total_time = time.time() - stream_start
            logger.info(
                f"✅ Streaming TTS completed: "
                f"{sentence_count} sentences | "
                f"TTFA: {(first_audio_time - stream_start):.2f}s | "
                f"Total: {total_time:.2f}s | "
                f"Avg per sentence: {(total_time / sentence_count):.2f}s" if sentence_count > 0 else ""
            )

        except Exception as e:
            logger.error(f"Error in streaming TTS: {e}")

        finally:
            self.is_processing = False

    async def _play_audio_queue(
        self,
        voice_client: discord.VoiceClient,
        audio_files: list[Path]
    ):
        """Play audio files sequentially.

        Args:
            voice_client: Discord voice client
            audio_files: List of audio file paths
        """
        played_count = 0

        while played_count < len(audio_files):
            # Wait if currently playing
            while voice_client.is_playing():
                await asyncio.sleep(0.1)

            # Play next audio file
            audio_file = audio_files[played_count]

            try:
                audio_source = discord.FFmpegPCMAudio(
                    str(audio_file),
                    options='-vn -af aresample=48000,aformat=sample_fmts=s16:channel_layouts=stereo'
                )

                # Create future to wait for playback completion
                playback_done = asyncio.Future()

                def after_playback(error):
                    if error:
                        logger.error(f"Playback error: {error}")

                    # Clean up audio file
                    try:
                        audio_file.unlink()
                    except Exception as e:
                        logger.warning(f"Failed to delete temp audio: {e}")

                    # Signal completion
                    asyncio.run_coroutine_threadsafe(
                        self._set_future(playback_done),
                        voice_client.loop
                    )

                voice_client.play(audio_source, after=after_playback)
                logger.debug(f"Playing audio chunk {played_count + 1}/{len(audio_files)}")

                # Wait for playback to complete
                await playback_done
                played_count += 1

            except Exception as e:
                logger.error(f"Failed to play audio chunk: {e}")
                # Try to clean up file
                try:
                    audio_file.unlink()
                except Exception:
                    pass
                played_count += 1

    async def _set_future(self, future: asyncio.Future):
        """Set future result in async context."""
        if not future.done():
            future.set_result(None)

    async def speak_text_streaming(
        self,
        text: str,
        voice_client: discord.VoiceClient,
        speed: float = 1.0,
        rate: str = "+0%"
    ):
        """Speak text using sentence-by-sentence processing.

        This is a convenience method for non-streaming use cases.

        Args:
            text: Text to speak
            voice_client: Discord voice client
            speed: Speed multiplier
            rate: Rate adjustment
        """
        # Create fake stream from text
        async def text_stream():
            yield text

        await self.process_stream(
            text_stream(),
            voice_client,
            speed=speed,
            rate=rate
        )
