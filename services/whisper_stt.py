"""Whisper speech-to-text service for voice activity detection."""
import logging
import asyncio
from pathlib import Path
from typing import Optional
import wave
import io

logger = logging.getLogger(__name__)

# Try importing faster-whisper
try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger.warning("Whisper not available. Install with: pip install faster-whisper")

# Try importing torch for model optimization
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class WhisperSTTService:
    """Service for speech-to-text using faster-whisper."""

    def __init__(
        self,
        model_size: str = "base",
        device: Optional[str] = None,
        language: Optional[str] = "en",
    ):
        """Initialize Whisper STT service.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
            device: Device to run model on (cuda/cpu/auto)
            language: Default language for transcription (None for auto-detect)
        """
        self.model_size = model_size
        self.language = language
        self.model = None

        if not WHISPER_AVAILABLE:
            logger.error("Whisper not available")
            return

        # Determine device
        if device == "auto" or device is None:
            if TORCH_AVAILABLE and torch.cuda.is_available():
                self.device = "cuda"
            else:
                self.device = "cpu"
        else:
            self.device = device

        # Determine compute type based on device
        if self.device == "cuda":
            compute_type = "float16"
        else:
            compute_type = "int8"

        logger.info(f"Initializing faster-whisper STT with model: {model_size} on {self.device} (compute_type: {compute_type})")

        try:
            # Load model with faster-whisper
            self.model = WhisperModel(
                model_size,
                device=self.device,
                compute_type=compute_type
            )
            logger.info(f"faster-whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load faster-whisper model: {e}")
            self.model = None

    def is_available(self) -> bool:
        """Check if Whisper is available and loaded.

        Returns:
            True if service is ready
        """
        return WHISPER_AVAILABLE and self.model is not None

    async def transcribe_file(
        self,
        audio_path: Path,
        language: Optional[str] = None,
        task: str = "transcribe",
    ) -> dict:
        """Transcribe audio file to text.

        Args:
            audio_path: Path to audio file
            language: Language code (None for auto-detect)
            task: "transcribe" or "translate" (translate to English)

        Returns:
            Dictionary with transcription results
        """
        if not self.is_available():
            raise RuntimeError("Whisper STT is not available")

        try:
            # Run transcription in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._transcribe_sync,
                str(audio_path),
                language or self.language,
                task,
            )

            return result

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise RuntimeError(f"Failed to transcribe audio: {e}")

    def _transcribe_sync(
        self, audio_path: str, language: Optional[str], task: str
    ) -> dict:
        """Synchronous transcription (run in thread pool).

        Args:
            audio_path: Path to audio file
            language: Language code
            task: transcribe or translate

        Returns:
            Transcription result dict
        """
        # faster-whisper returns segments generator and info tuple
        segments, info = self.model.transcribe(
            audio_path,
            language=language,
            task=task,
        )

        # Convert generator to list and build text
        segments_list = list(segments)
        text = " ".join([segment.text for segment in segments_list])

        return {
            "text": text.strip(),
            "language": info.language if hasattr(info, 'language') else "unknown",
            "segments": [
                {
                    "text": seg.text,
                    "start": seg.start,
                    "end": seg.end,
                }
                for seg in segments_list
            ],
        }

    async def transcribe_audio_data(
        self,
        audio_data: bytes,
        sample_rate: int = 48000,
        language: Optional[str] = None,
    ) -> dict:
        """Transcribe raw audio data.

        Args:
            audio_data: Raw audio bytes (PCM)
            sample_rate: Sample rate of audio
            language: Language code

        Returns:
            Transcription result dict
        """
        if not self.is_available():
            raise RuntimeError("Whisper STT is not available")

        try:
            # Create temporary WAV file
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = Path(temp_file.name)

                # Write WAV file
                with wave.open(str(temp_path), "wb") as wav_file:
                    wav_file.setnchannels(2)  # Stereo
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(audio_data)

                # Transcribe
                result = await self.transcribe_file(temp_path, language)

                # Clean up
                temp_path.unlink()

                return result

        except Exception as e:
            logger.error(f"Failed to transcribe audio data: {e}")
            raise RuntimeError(f"Audio transcription failed: {e}")

    def get_supported_languages(self) -> list:
        """Get list of supported languages.

        Returns:
            List of language codes
        """
        if not WHISPER_AVAILABLE:
            return []

        # Whisper supports these languages
        languages = [
            "en",  # English
            "es",  # Spanish
            "fr",  # French
            "de",  # German
            "it",  # Italian
            "pt",  # Portuguese
            "nl",  # Dutch
            "pl",  # Polish
            "ru",  # Russian
            "ja",  # Japanese
            "ko",  # Korean
            "zh",  # Chinese
            "ar",  # Arabic
            "tr",  # Turkish
            "hi",  # Hindi
            # ... and 90+ more
        ]

        return languages

    def estimate_model_memory(self) -> dict:
        """Estimate memory requirements for current model.

        Returns:
            Dictionary with memory estimates in MB
        """
        memory_estimates = {
            "tiny": {"ram": 400, "vram": 1000},
            "base": {"ram": 500, "vram": 1500},
            "small": {"ram": 1000, "vram": 2500},
            "medium": {"ram": 2500, "vram": 5000},
            "large": {"ram": 5000, "vram": 10000},
        }

        return memory_estimates.get(
            self.model_size, {"ram": 0, "vram": 0, "note": "Unknown model size"}
        )


class VoiceActivityDetector:
    """Manages voice activity detection and recording in Discord voice channels."""

    def __init__(
        self,
        whisper_stt: WhisperSTTService,
        temp_dir: Path,
        silence_threshold: float = 2.0,
        max_recording_duration: int = 30,
    ):
        """Initialize voice activity detector.

        Args:
            whisper_stt: Whisper STT service instance
            temp_dir: Directory for temporary audio files
            silence_threshold: Seconds of silence before stopping recording
            max_recording_duration: Maximum recording length in seconds
        """
        self.whisper = whisper_stt
        self.temp_dir = Path(temp_dir)
        self.silence_threshold = silence_threshold
        self.max_recording_duration = max_recording_duration

        # Recording state per guild
        self.active_recordings = {}  # guild_id -> recording_data

        self.temp_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Voice activity detector initialized")

    def is_recording(self, guild_id: int) -> bool:
        """Check if currently recording in a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            True if recording is active
        """
        return guild_id in self.active_recordings

    async def start_recording(
        self, guild_id: int, user_id: int, voice_client
    ) -> bool:
        """Start recording audio from voice channel.

        Args:
            guild_id: Discord guild ID
            user_id: User who initiated recording
            voice_client: Discord voice client

        Returns:
            True if recording started
        """
        if self.is_recording(guild_id):
            logger.warning(f"Already recording in guild {guild_id}")
            return False

        try:
            import uuid

            recording_id = str(uuid.uuid4())
            audio_file = self.temp_dir / f"recording_{recording_id}.wav"

            self.active_recordings[guild_id] = {
                "recording_id": recording_id,
                "user_id": user_id,
                "audio_file": audio_file,
                "start_time": asyncio.get_event_loop().time(),
                "voice_client": voice_client,
                "audio_chunks": [],
            }

            logger.info(f"Started recording in guild {guild_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            return False

    async def stop_recording(self, guild_id: int) -> Optional[dict]:
        """Stop recording and transcribe audio.

        Args:
            guild_id: Discord guild ID

        Returns:
            Transcription result or None
        """
        if not self.is_recording(guild_id):
            return None

        try:
            recording_data = self.active_recordings.pop(guild_id)
            audio_file = recording_data["audio_file"]

            # Save audio chunks to file (simplified - in production use proper audio handling)
            logger.info(f"Stopped recording in guild {guild_id}, transcribing...")

            # Transcribe if file exists and has content
            if audio_file.exists() and audio_file.stat().st_size > 0:
                result = await self.whisper.transcribe_file(audio_file)

                # Clean up
                audio_file.unlink()

                logger.info(
                    f"Transcription complete: {result['text'][:100]}..."
                )
                return result
            else:
                logger.warning("No audio data recorded")
                return None

        except Exception as e:
            logger.error(f"Failed to stop recording and transcribe: {e}")
            return None

    def cleanup_recording(self, guild_id: int):
        """Clean up recording state without transcribing.

        Args:
            guild_id: Discord guild ID
        """
        if guild_id in self.active_recordings:
            recording_data = self.active_recordings.pop(guild_id)
            audio_file = recording_data.get("audio_file")

            if audio_file and audio_file.exists():
                audio_file.unlink()

            logger.info(f"Cleaned up recording for guild {guild_id}")
