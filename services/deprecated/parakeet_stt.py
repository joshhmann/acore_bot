"""Parakeet speech-to-text service for fast, accurate transcription."""
import logging
import asyncio
from pathlib import Path
from typing import Optional
import wave

logger = logging.getLogger(__name__)

# Try importing NeMo
try:
    import nemo.collections.asr as nemo_asr
    import torch
    PARAKEET_AVAILABLE = True
except ImportError:
    PARAKEET_AVAILABLE = False
    logger.warning("Parakeet/NeMo not available. Install with: uv pip install nemo_toolkit['asr']")


class ParakeetSTTService:
    """Service for speech-to-text using NVIDIA Parakeet TDT."""

    def __init__(
        self,
        model_name: str = "nvidia/parakeet-tdt-0.6b-v3",
        device: Optional[str] = None,
        language: Optional[str] = None,
    ):
        """Initialize Parakeet STT service.

        Args:
            model_name: Parakeet model name from HuggingFace
            device: Device to run model on (cuda/cpu/auto)
            language: Default language (None for auto-detect, supports 25 European languages)
        """
        self.model_name = model_name
        self.language = language
        self.model = None

        if not PARAKEET_AVAILABLE:
            logger.error("Parakeet/NeMo not available")
            return

        # Determine device
        if device == "auto" or device is None:
            if torch.cuda.is_available():
                self.device = "cuda"
            else:
                self.device = "cpu"
        else:
            self.device = device

        logger.info(f"Initializing Parakeet STT with model: {model_name} on {self.device}")

        try:
            # Load ASR model from NeMo
            self.model = nemo_asr.models.ASRModel.from_pretrained(model_name)
            self.model = self.model.to(self.device)
            self.model.eval()
            logger.info(f"Parakeet model loaded successfully on {self.device}")
        except Exception as e:
            logger.error(f"Failed to load Parakeet model: {e}")
            self.model = None

    def is_available(self) -> bool:
        """Check if Parakeet is available and loaded.

        Returns:
            True if service is ready
        """
        return PARAKEET_AVAILABLE and self.model is not None

    async def transcribe_file(
        self,
        audio_path: Path,
        language: Optional[str] = None,
    ) -> dict:
        """Transcribe audio file to text.

        Args:
            audio_path: Path to audio file
            language: Language code (auto-detected if None)

        Returns:
            Dictionary with transcription results
        """
        if not self.is_available():
            raise RuntimeError("Parakeet STT is not available")

        try:
            # Run transcription in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._transcribe_sync,
                str(audio_path),
            )

            return result

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise RuntimeError(f"Failed to transcribe audio: {e}")

    def _transcribe_sync(self, audio_path: str) -> dict:
        """Synchronous transcription (run in thread pool).

        Args:
            audio_path: Path to audio file

        Returns:
            Transcription result dict
        """
        # NeMo transcribe returns list of transcriptions
        transcriptions = self.model.transcribe([audio_path])

        # Get the first transcription (we only sent one file)
        if transcriptions:
            # Check if result is a string or Hypothesis object
            result = transcriptions[0]
            if hasattr(result, 'text'):
                text = result.text
            else:
                text = str(result)
        else:
            text = ""

        # Parakeet includes punctuation and capitalization automatically
        return {
            "text": text.strip(),
            "language": self.language or "auto",  # Parakeet auto-detects among 25 languages
            "segments": [
                {
                    "text": text.strip(),
                    "start": 0.0,
                    "end": 0.0,  # NeMo doesn't provide timestamps by default
                }
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
            language: Language code (ignored, auto-detected)

        Returns:
            Transcription result dict
        """
        if not self.is_available():
            raise RuntimeError("Parakeet STT is not available")

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
            List of language codes (25 European languages)
        """
        if not PARAKEET_AVAILABLE:
            return []

        # Parakeet TDT 0.6B supports 25 European languages
        languages = [
            "en",  # English
            "de",  # German
            "es",  # Spanish
            "fr",  # French
            "it",  # Italian
            "pt",  # Portuguese
            "pl",  # Polish
            "nl",  # Dutch
            "ru",  # Russian
            "uk",  # Ukrainian
            "cs",  # Czech
            "ro",  # Romanian
            "hu",  # Hungarian
            "sk",  # Slovak
            "bg",  # Bulgarian
            "hr",  # Croatian
            "sl",  # Slovenian
            "lt",  # Lithuanian
            "lv",  # Latvian
            "et",  # Estonian
            "fi",  # Finnish
            "sv",  # Swedish
            "da",  # Danish
            "no",  # Norwegian
            "el",  # Greek
        ]

        return languages

    def estimate_model_memory(self) -> dict:
        """Estimate memory requirements for current model.

        Returns:
            Dictionary with memory estimates in MB
        """
        # Parakeet TDT 0.6B is ~600M parameters
        return {
            "ram": 2000,  # ~2GB RAM minimum
            "vram": 2500,  # ~2.5GB VRAM for GPU inference
            "note": "600M parameter model with automatic punctuation/capitalization",
        }
