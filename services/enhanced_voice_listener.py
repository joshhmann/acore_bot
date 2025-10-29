"""Enhanced voice listening with automatic speech detection and smart responses."""
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable
import wave
import io
import time

logger = logging.getLogger(__name__)


class EnhancedVoiceListener:
    """Enhanced voice listener with VAD and smart response triggers."""

    def __init__(
        self,
        whisper_stt,
        silence_threshold: float = 2.0,  # Seconds of silence before transcribing
        energy_threshold: int = 500,      # Audio energy threshold for speech detection
        bot_trigger_words: list = None,   # Words that trigger bot response
    ):
        """Initialize enhanced voice listener.

        Args:
            whisper_stt: WhisperSTTService instance
            silence_threshold: Seconds of silence before auto-transcribing
            energy_threshold: Energy level to detect speech vs silence
            bot_trigger_words: Keywords that trigger bot response
        """
        self.whisper = whisper_stt
        self.silence_threshold = silence_threshold
        self.energy_threshold = energy_threshold

        # Default trigger words (bot, assistant, hey, question)
        self.bot_trigger_words = bot_trigger_words or [
            "bot", "assistant", "hey", "help", "question", "tell me", "what"
        ]

        # Active listening sessions per guild
        # Format: {guild_id: session_data}
        self.active_sessions = {}

        logger.info("Enhanced voice listener initialized")

    async def start_smart_listen(
        self,
        guild_id: int,
        user_id: int,
        voice_client,
        temp_dir: Path,
        on_transcription: Callable = None,
        on_bot_response_needed: Callable = None,
    ) -> bool:
        """Start smart listening with automatic speech detection.

        Args:
            guild_id: Discord guild ID
            user_id: User who initiated listening
            voice_client: Discord voice client
            temp_dir: Temporary directory for audio files
            on_transcription: Callback when transcription completes
            on_bot_response_needed: Callback when bot should respond

        Returns:
            True if started successfully
        """
        if guild_id in self.active_sessions:
            logger.warning(f"Already listening in guild {guild_id}")
            return False

        try:
            import uuid
            session_id = str(uuid.uuid4())
            audio_file = temp_dir / f"smart_listen_{session_id}.wav"

            session = {
                "session_id": session_id,
                "user_id": user_id,
                "audio_file": audio_file,
                "start_time": time.time(),
                "voice_client": voice_client,
                "audio_chunks": [],
                "last_speech_time": None,
                "is_recording_speech": False,
                "on_transcription": on_transcription,
                "on_bot_response_needed": on_bot_response_needed,
            }

            self.active_sessions[guild_id] = session

            # Start monitoring loop
            asyncio.create_task(self._monitor_audio(guild_id))

            logger.info(f"Started smart listening in guild {guild_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to start smart listening: {e}")
            return False

    async def _monitor_audio(self, guild_id: int):
        """Monitor audio stream and auto-detect speech segments.

        Args:
            guild_id: Discord guild ID
        """
        session = self.active_sessions.get(guild_id)
        if not session:
            return

        logger.info(f"Monitoring audio for guild {guild_id}")

        try:
            # In a real implementation, we'd capture audio from Discord
            # For now, we'll simulate with a timer-based approach

            # This is a simplified version - in production you'd:
            # 1. Use discord-ext-voice-recv or similar
            # 2. Process audio chunks in real-time
            # 3. Use actual VAD (like silero-vad or webrtcvad)

            # For this quick implementation:
            # - User speaks, we record
            # - After silence_threshold seconds, we auto-transcribe

            while guild_id in self.active_sessions:
                current_time = time.time()

                # Check if we should auto-stop (silence detected)
                if session["last_speech_time"]:
                    silence_duration = current_time - session["last_speech_time"]

                    if silence_duration >= self.silence_threshold:
                        # Silence threshold reached - transcribe!
                        logger.info(f"Silence detected ({silence_duration:.1f}s), auto-transcribing...")
                        await self._auto_transcribe(guild_id)

                        # Reset for next segment
                        session["last_speech_time"] = None
                        session["is_recording_speech"] = False

                await asyncio.sleep(0.5)  # Check every 500ms

        except Exception as e:
            logger.error(f"Error monitoring audio: {e}")
        finally:
            logger.info(f"Stopped monitoring audio for guild {guild_id}")

    def detect_speech_in_audio(self, audio_data: bytes) -> bool:
        """Simple energy-based speech detection.

        Args:
            audio_data: Raw audio bytes

        Returns:
            True if speech detected
        """
        try:
            import numpy as np

            # Convert to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16)

            # Calculate energy (RMS - Root Mean Square)
            energy = np.sqrt(np.mean(audio_array.astype(float) ** 2))

            # Check if energy exceeds threshold
            return energy > self.energy_threshold

        except Exception as e:
            logger.error(f"Error detecting speech: {e}")
            return False

    async def _auto_transcribe(self, guild_id: int):
        """Auto-transcribe recorded audio and process response.

        Args:
            guild_id: Discord guild ID
        """
        session = self.active_sessions.get(guild_id)
        if not session:
            return

        try:
            audio_file = session["audio_file"]

            # Check if audio file exists and has content
            if not audio_file.exists() or audio_file.stat().st_size == 0:
                logger.warning("No audio recorded to transcribe")
                return

            # Transcribe
            result = await self.whisper.transcribe_file(audio_file)

            if not result or not result.get("text"):
                logger.warning("Transcription returned empty")
                return

            transcription = result["text"].strip()
            language = result.get("language", "unknown")

            logger.info(f"Auto-transcribed: {transcription}")

            # Callback for transcription
            if session["on_transcription"]:
                await session["on_transcription"](transcription, language)

            # Check if bot should respond
            should_respond = self.should_bot_respond(transcription)

            if should_respond and session["on_bot_response_needed"]:
                logger.info("Bot response triggered")
                await session["on_bot_response_needed"](transcription)

        except Exception as e:
            logger.error(f"Error in auto-transcribe: {e}")

    def should_bot_respond(self, transcription: str) -> bool:
        """Determine if bot should respond based on transcription.

        Logic:
        1. Check for bot trigger words (bot, assistant, hey, etc.)
        2. Check if it's a question (ends with ?)
        3. Check for command-like phrases (tell me, show me, etc.)

        Args:
            transcription: Transcribed text

        Returns:
            True if bot should respond
        """
        text_lower = transcription.lower()

        # 1. Check for trigger words
        if any(trigger in text_lower for trigger in self.bot_trigger_words):
            logger.info(f"Trigger word found in: {transcription}")
            return True

        # 2. Check if it's a question
        if transcription.strip().endswith("?"):
            logger.info(f"Question detected: {transcription}")
            return True

        # 3. Check for imperative phrases
        imperative_phrases = [
            "tell me", "show me", "give me", "help me",
            "explain", "describe", "what is", "how do",
            "can you", "could you", "would you", "will you"
        ]

        if any(phrase in text_lower for phrase in imperative_phrases):
            logger.info(f"Imperative phrase detected: {transcription}")
            return True

        # Otherwise, stay quiet
        logger.info(f"No response trigger in: {transcription}")
        return False

    async def stop_listen(self, guild_id: int) -> Optional[dict]:
        """Stop listening and return final transcription if any.

        Args:
            guild_id: Discord guild ID

        Returns:
            Transcription result or None
        """
        session = self.active_sessions.get(guild_id)
        if not session:
            return None

        try:
            # Remove from active sessions
            del self.active_sessions[guild_id]

            # Transcribe any remaining audio
            audio_file = session["audio_file"]

            if audio_file.exists() and audio_file.stat().st_size > 0:
                result = await self.whisper.transcribe_file(audio_file)

                # Cleanup
                try:
                    audio_file.unlink()
                except:
                    pass

                return result

            return None

        except Exception as e:
            logger.error(f"Error stopping listen: {e}")
            return None

    def is_listening(self, guild_id: int) -> bool:
        """Check if currently listening in a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            True if listening
        """
        return guild_id in self.active_sessions

    def update_speech_detected(self, guild_id: int):
        """Update that speech was detected (resets silence timer).

        Args:
            guild_id: Discord guild ID
        """
        session = self.active_sessions.get(guild_id)
        if session:
            session["last_speech_time"] = time.time()
            session["is_recording_speech"] = True

    def add_audio_chunk(self, guild_id: int, audio_chunk: bytes):
        """Add audio chunk to recording buffer.

        Args:
            guild_id: Discord guild ID
            audio_chunk: Audio data
        """
        session = self.active_sessions.get(guild_id)
        if session:
            session["audio_chunks"].append(audio_chunk)

            # Detect if this chunk contains speech
            if self.detect_speech_in_audio(audio_chunk):
                self.update_speech_detected(guild_id)

    def get_session_duration(self, guild_id: int) -> float:
        """Get how long the current session has been active.

        Args:
            guild_id: Discord guild ID

        Returns:
            Duration in seconds
        """
        session = self.active_sessions.get(guild_id)
        if session:
            return time.time() - session["start_time"]
        return 0.0
