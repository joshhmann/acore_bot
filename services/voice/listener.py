"""Enhanced voice listening with automatic speech detection and smart responses."""
import logging
import asyncio
from pathlib import Path
from typing import Optional, Callable
import wave
import time

from discord.ext import voice_recv
# Transcription fixer removed - Parakeet is accurate enough
# Sound effects service removed - was never fully integrated

logger = logging.getLogger(__name__)


class TranscriptionSink(voice_recv.AudioSink):
    """Audio sink that captures voice and feeds it to the transcription system."""

    def __init__(self, listener: 'EnhancedVoiceListener', guild_id: int):
        """Initialize the transcription sink.

        Args:
            listener: EnhancedVoiceListener instance
            guild_id: Discord guild ID for this session
        """
        super().__init__()
        self.listener = listener
        self.guild_id = guild_id
        self.user_buffers = {}  # user_id -> list of audio frames
        self.sample_rate = 48000  # Discord sends 48kHz audio
        self.channels = 2  # Stereo
        self.sample_width = 2  # 16-bit

    def wants_opus(self) -> bool:
        """We want decoded PCM audio, not opus."""
        return False

    def write(self, user, data):
        """Called when audio data is received from a user.

        Args:
            user: Discord user or member
            data: VoiceData containing the audio
        """
        if user is None:
            return

        try:
            user_id = user.id if hasattr(user, 'id') else user
            pcm_data = data.pcm

            if not pcm_data:
                return

            # Initialize buffer for new users
            if user_id not in self.user_buffers:
                self.user_buffers[user_id] = []

            # Add to user's buffer
            self.user_buffers[user_id].append(pcm_data)

            # Feed to enhanced listener for speech detection
            self.listener.add_audio_chunk(self.guild_id, pcm_data)

        except Exception as e:
            logger.error(f"Error in TranscriptionSink.write: {e}")

    def get_all_audio(self) -> bytes:
        """Get combined audio from all users.

        Returns:
            Combined PCM audio data
        """
        all_audio = []
        for user_id, chunks in self.user_buffers.items():
            all_audio.extend(chunks)
        return b''.join(all_audio)

    def get_user_audio(self, user_id: int) -> bytes:
        """Get audio from a specific user.

        Args:
            user_id: Discord user ID

        Returns:
            PCM audio data from that user
        """
        chunks = self.user_buffers.get(user_id, [])
        return b''.join(chunks)

    def clear_buffers(self):
        """Clear all audio buffers."""
        self.user_buffers.clear()

    def cleanup(self):
        """Cleanup resources."""
        self.clear_buffers()


class EnhancedVoiceListener:
    """Enhanced voice listener with VAD and smart response triggers."""

    def __init__(
        self,
        stt_service,
        silence_threshold: float = 2.0,  # Seconds of silence before transcribing
        energy_threshold: int = 500,      # Audio energy threshold for speech detection
        bot_trigger_words: list = None,   # Words that trigger bot response
    ):
        """Initialize enhanced voice listener.

        Args:
            stt_service: STT service instance (WhisperSTTService or ParakeetSTTService)
            silence_threshold: Seconds of silence before auto-transcribing
            energy_threshold: Energy level to detect speech vs silence
            bot_trigger_words: Keywords that trigger bot response
        """
        self.stt = stt_service
        self.whisper = stt_service  # Backwards compatibility
        self.silence_threshold = silence_threshold
        self.energy_threshold = energy_threshold

        # Default trigger words (bot, assistant, hey, question)
        self.bot_trigger_words = bot_trigger_words or [
            "bot", "assistant", "arby", "hey", "help", "question", "tell me", "what",
            "can you", "could you", "would you", "will you", "how", "why", "when", "where", "who",
            "dagoth", "ur", "lord", "god", "sharmat", "dreamer"
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

            # Create the transcription sink
            sink = TranscriptionSink(self, guild_id)

            session = {
                "session_id": session_id,
                "user_id": user_id,
                "audio_file": audio_file,
                "start_time": time.time(),
                "voice_client": voice_client,
                "sink": sink,
                "audio_chunks": [],
                "last_speech_time": None,
                "is_recording_speech": False,
                "on_transcription": on_transcription,
                "on_bot_response_needed": on_bot_response_needed,
                "first_speech_time": None,
            }

            self.active_sessions[guild_id] = session

            # Start listening with the sink
            voice_client.listen(sink)
            logger.info(f"Voice receive sink attached for guild {guild_id}")

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
                        session["first_speech_time"] = None

                # Check max speech duration (force transcribe if talking too long or constant noise)
                if session.get("is_recording_speech") and session.get("first_speech_time"):
                    MAX_SPEECH_DURATION = 8.0  # Force transcribe after 8 seconds of continuous 'speech'
                    if current_time - session["first_speech_time"] > MAX_SPEECH_DURATION:
                        logger.info(f"Max speech duration ({MAX_SPEECH_DURATION}s) reached, forcing transcription...")
                        await self._auto_transcribe(guild_id)
                        
                        # Reset for next segment
                        session["last_speech_time"] = None
                        session["is_recording_speech"] = False
                        session["first_speech_time"] = None

                await asyncio.sleep(0.1)  # Check every 100ms for snappier response

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

    def _convert_audio_for_whisper(self, pcm_data: bytes) -> bytes:
        """Convert 48kHz stereo PCM to 16kHz mono for Whisper.

        Args:
            pcm_data: Raw PCM audio (48kHz, stereo, 16-bit)

        Returns:
            Converted PCM audio (16kHz, mono, 16-bit)
        """
        import numpy as np

        # Convert bytes to numpy array (16-bit signed integers)
        audio = np.frombuffer(pcm_data, dtype=np.int16)

        # Convert stereo to mono (average left and right channels)
        if len(audio) % 2 == 0:
            audio = audio.reshape(-1, 2)
            audio = audio.mean(axis=1).astype(np.int16)

        # Resample from 48kHz to 16kHz (divide by 3)
        # Simple decimation - take every 3rd sample
        audio = audio[::3]

        return audio.tobytes()

    def _write_wav_file(self, audio_file: Path, pcm_data: bytes):
        """Write PCM data to a WAV file.

        Args:
            audio_file: Output file path
            pcm_data: PCM audio data (16kHz, mono, 16-bit)
        """
        with wave.open(str(audio_file), 'wb') as wav:
            wav.setnchannels(1)  # Mono
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(16000)  # 16kHz for Whisper
            wav.writeframes(pcm_data)

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
            sink = session.get("sink")

            # Get audio from sink
            if sink:
                raw_audio = sink.get_all_audio()
                # Minimum audio threshold: ~0.5s of audio (48kHz * 2ch * 2bytes * 0.5s = 96000 bytes)
                if not raw_audio or len(raw_audio) < 96000:
                    logger.debug("Audio too short to transcribe (< 0.5s)")
                    logger.warning("No audio recorded to transcribe")
                    sink.clear_buffers()
                    return

                # Convert and write to WAV file (offload to thread)
                loop = asyncio.get_running_loop()
                bytes_written = await loop.run_in_executor(
                    None, 
                    self._process_audio_sync, 
                    raw_audio, 
                    audio_file
                )

                # Clear buffers for next segment
                sink.clear_buffers()

                logger.info(f"Wrote {bytes_written} bytes to {audio_file}")
            else:
                # Fallback: check if file exists (legacy path)
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

            # Check for interrupt command (stop talking)
            voice_client = session.get("voice_client")
            if voice_client and voice_client.is_playing():
                # Check if it's TTS that's playing
                source = voice_client.source if hasattr(voice_client, 'source') else None
                is_tts = getattr(source, '_is_tts', False) if source else False

                # If user says "stop" while bot is talking, interrupt it
                if is_tts and transcription.lower().strip() in ['stop', 'stop.', 'stop talking', 'stop talking.', 'quiet', 'quiet.', 'shut up', 'shut up.']:
                    logger.info(f"Interrupt detected - stopping bot TTS: '{transcription}'")
                    voice_client.stop()
                    # Don't process this as a command - just interrupt
                    return

            # Sound effects feature removed (service was never fully integrated)
            # Future: Could re-implement sound effects if needed

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

    def _process_audio_sync(self, raw_audio: bytes, audio_file: Path) -> int:
        """Process audio and write to file synchronously (run in executor).
        
        Args:
            raw_audio: Raw PCM audio
            audio_file: Output file path
            
        Returns:
            Number of bytes written
        """
        converted_audio = self._convert_audio_for_whisper(raw_audio)
        self._write_wav_file(audio_file, converted_audio)
        return len(converted_audio)

    def should_bot_respond(self, transcription: str) -> bool:
        """Determine if bot should respond based on transcription.

        Logic:
        1. Check for bot trigger words (bot, assistant, hey, etc.)
        2. Check for @mentions (at Arby, add Arby, etc.)
        3. Check if it's a question (ends with ?)
        4. Check for command-like phrases (tell me, show me, etc.)
        5. Check for conversational statements (I'm, We're, etc.)
        6. Check for substantial sentences (> 4 words)

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

        # 2. Check for @mention variations (Whisper transcribes @ as "at", "add", etc.)
        mention_patterns = [
            r'\b@\s*arby\b',      # "@Arby"
            r'\bat\s+arby\b',     # "at Arby"
            r'\badd\s+arby\b',    # "add Arby" (common mishear)
            r'\bat\s+r\.?b\.?\b', # "at R.B."
            r'\bdagoth\b',        # "Dagoth"
            r'\bdaddy\b',         # "Daddy" (common nickname for Dagoth Ur)
        ]
        import re
        for pattern in mention_patterns:
            if re.search(pattern, text_lower):
                logger.info(f"@mention detected in: {transcription}")
                return True

        # 3. Check if it's a question
        if transcription.strip().endswith("?"):
            logger.info(f"Question detected: {transcription}")
            return True

        # 4. Check for imperative phrases
        imperative_phrases = [
            "tell me", "show me", "give me", "help me",
            "explain", "describe", "what is", "how do",
            "can you", "could you", "would you", "will you"
        ]

        if any(phrase in text_lower for phrase in imperative_phrases):
            logger.info(f"Imperative phrase detected: {transcription}")
            return True

        # 5. Check for conversational statements (I'm, We're, etc.)
        conversational_starts = [
            "i am", "i'm", "i think", "i feel", "i want",
            "we are", "we're", "my", "this is", "that is", "it is", "it's"
        ]
        
        word_count = len(transcription.split())
        
        if word_count >= 3 and any(text_lower.startswith(start) for start in conversational_starts):
            logger.info(f"Conversational statement detected: {transcription}")
            return True

        # 6. Check for substantial sentences (general conversation)
        # If it's a decent length sentence, assume it's part of conversation
        if word_count >= 5:
            logger.info(f"Substantial sentence detected ({word_count} words): {transcription}")
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
            # Stop voice client listening
            voice_client = session.get("voice_client")
            if voice_client:
                try:
                    voice_client.stop_listening()
                    logger.info(f"Stopped voice client listening for guild {guild_id}")
                except Exception as e:
                    logger.warning(f"Error stopping voice client listening: {e}")

            # Get any remaining audio from sink
            sink = session.get("sink")
            audio_file = session["audio_file"]
            result = None

            if sink:
                raw_audio = sink.get_all_audio()
                if raw_audio and len(raw_audio) >= 1000:
                    # Convert and write final audio
                    converted_audio = self._convert_audio_for_whisper(raw_audio)
                    self._write_wav_file(audio_file, converted_audio)

                    # Transcribe
                    result = await self.whisper.transcribe_file(audio_file)

                # Cleanup sink
                sink.cleanup()

            # Fallback: check if file already exists
            elif audio_file.exists() and audio_file.stat().st_size > 0:
                result = await self.whisper.transcribe_file(audio_file)

            # Remove from active sessions
            del self.active_sessions[guild_id]

            # Cleanup audio file
            try:
                if audio_file.exists():
                    audio_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete audio file: {e}")

            return result

        except Exception as e:
            logger.error(f"Error stopping listen: {e}")
            # Ensure session is removed even on error
            if guild_id in self.active_sessions:
                del self.active_sessions[guild_id]
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
            if not session.get("is_recording_speech"):
                session["first_speech_time"] = time.time()
            session["last_speech_time"] = time.time()
            session["is_recording_speech"] = True

            # Smart Barge-in: Only stop BOT TTS, not music
            # Music continues playing while listening - we'll only stop it for actual commands
            voice_client = session.get("voice_client")
            if voice_client and voice_client.is_playing():
                # Check if this is bot TTS vs music by checking the source type
                # TTS sources have '_is_tts' attribute, music doesn't
                source = voice_client.source if hasattr(voice_client, 'source') else None
                is_tts = getattr(source, '_is_tts', False) if source else False

                if is_tts:
                    logger.info("Barge-in detected: User speaking, stopping bot TTS")
                    voice_client.stop()
                else:
                    # Music is playing - let it continue, we'll only stop for actual commands
                    logger.debug("User speaking but music continues (waiting for command)")

    def add_audio_chunk(self, guild_id: int, audio_chunk: bytes):
        """Add audio chunk to recording buffer.

        Args:
            guild_id: Discord guild ID
            audio_chunk: Audio data
        """
        session = self.active_sessions.get(guild_id)
        if not session:
            return

        # Check if music is playing - if so, keep buffers lean
        voice_client = session.get("voice_client")
        if voice_client and voice_client.is_playing():
            # Check if it's music (not TTS)
            source = voice_client.source if hasattr(voice_client, 'source') else None
            is_tts = getattr(source, '_is_tts', False) if source else False
            is_sound_effect = getattr(source, '_is_sound_effect', False) if source else False

            # If music is playing (not TTS/sound effects), keep only recent chunks
            if not is_tts and not is_sound_effect:
                # Keep buffer small during music (only last 5 seconds for commands)
                # This prevents backlog but still allows "Arby, stop" commands
                max_music_chunks = 250  # ~5 seconds at 20ms chunks
                if len(session["audio_chunks"]) > max_music_chunks:
                    logger.debug("Music playing - trimming audio buffer to recent audio only")
                    session["audio_chunks"] = session["audio_chunks"][-max_music_chunks:]
                # Continue processing - don't return! We need to hear "stop" commands

        # Limit buffer size to prevent memory issues (max ~30 seconds of audio)
        # 48kHz * 2 channels * 2 bytes * 30 seconds = ~5.7MB
        max_chunks = 1500  # ~30 seconds at 20ms chunks
        if len(session["audio_chunks"]) > max_chunks:
            # Buffer too large - drop old chunks
            logger.warning(f"Audio buffer overflow ({len(session['audio_chunks'])} chunks) - clearing old data")
            session["audio_chunks"] = session["audio_chunks"][-max_chunks:]

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
