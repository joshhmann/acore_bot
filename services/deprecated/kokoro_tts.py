"""Kokoro TTS service for high-quality local text-to-speech."""
import logging
from pathlib import Path
from typing import Optional
import numpy as np
import wave
import urllib.request
import os
import asyncio
import concurrent.futures

try:
    from kokoro_onnx import Kokoro
    KOKORO_AVAILABLE = True
except ImportError:
    KOKORO_AVAILABLE = False

logger = logging.getLogger(__name__)

# Model download URLs
KOKORO_MODEL_URL = "https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/kokoro-v1.0.onnx"
VOICES_BIN_URL = "https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/voices-v1.0.bin"


class KokoroTTSService:
    """Service for text-to-speech using Kokoro (local, high-quality)."""

    def _download_models(self) -> bool:
        """Download Kokoro model files if missing.

        Returns:
            True if models exist or were downloaded successfully
        """
        try:
            # Create models directory
            self.model_path.parent.mkdir(parents=True, exist_ok=True)

            # Download model file if missing
            if not self.model_path.exists():
                logger.info(f"Downloading Kokoro model (~311MB) to {self.model_path}...")
                urllib.request.urlretrieve(KOKORO_MODEL_URL, self.model_path)
                logger.info("Model downloaded successfully")

            # Download voices file if missing
            if not self.voices_path.exists():
                logger.info(f"Downloading Kokoro voices (~25MB) to {self.voices_path}...")
                urllib.request.urlretrieve(VOICES_BIN_URL, self.voices_path)
                logger.info("Voices downloaded successfully")

            return True
        except Exception as e:
            logger.error(f"Failed to download Kokoro models: {e}")
            return False

    def __init__(
        self,
        model_path: str = "models/kokoro-v1.0.onnx",
        voices_path: str = "models/voices-v1.0.bin",
        default_voice: str = "am_adam",
        speed: float = 1.0,
    ):
        """Initialize Kokoro TTS service.

        Args:
            model_path: Path to Kokoro ONNX model file
            voices_path: Path to voices binary file
            default_voice: Default voice to use
            speed: Speech speed multiplier
        """
        self.model_path = Path(model_path)
        self.voices_path = Path(voices_path)
        self.default_voice = default_voice
        self.speed = speed
        self.kokoro: Optional[Kokoro] = None
        self._model_ready = asyncio.Event()
        self._loading_task: Optional[asyncio.Task] = None
        self._load_failed = False

        if not KOKORO_AVAILABLE:
            logger.warning("Kokoro TTS not available. Install with: pip install kokoro-onnx")
            self._load_failed = True
            return

        # Start lazy loading in background (don't block __init__)
        logger.info("Kokoro TTS service created. Models will be loaded on first use.")

    async def _lazy_load_model(self):
        """Download and load Kokoro models in background (non-blocking).

        This is called automatically on first use.
        """
        if self._model_ready.is_set() or self._load_failed:
            return

        # Prevent multiple simultaneous loading attempts
        if self._loading_task and not self._loading_task.done():
            await self._loading_task
            return

        async def _do_load():
            try:
                logger.info("Starting Kokoro model lazy load...")

                # Download models if needed (in executor to avoid blocking)
                if not self.model_path.exists() or not self.voices_path.exists():
                    logger.info("Kokoro model files not found, downloading in background...")
                    success = await asyncio.to_thread(self._download_models)
                    if not success:
                        logger.error("Failed to download Kokoro models")
                        self._load_failed = True
                        return

                # Initialize Kokoro (in executor to avoid blocking)
                logger.info("Loading Kokoro model...")
                self.kokoro = await asyncio.to_thread(
                    Kokoro, str(self.model_path), str(self.voices_path)
                )
                logger.info(f"Kokoro TTS loaded successfully with voice: {self.default_voice}")
                self._model_ready.set()

            except Exception as e:
                logger.error(f"Failed to lazy load Kokoro TTS: {e}", exc_info=True)
                self._load_failed = True
                self.kokoro = None

        self._loading_task = asyncio.create_task(_do_load())
        await self._loading_task

    def is_available(self) -> bool:
        """Check if Kokoro TTS is available and ready.

        Returns:
            True if Kokoro is available
        """
        return KOKORO_AVAILABLE and self.kokoro is not None

    async def get_voices(self) -> list[str]:
        """Get list of available voices.

        Returns:
            List of voice names
        """
        # Trigger lazy loading if needed
        if not self._load_failed:
            await self._lazy_load_model()

        if not self.is_available():
            return []

        try:
            return self.kokoro.get_voices()
        except Exception as e:
            logger.error(f"Failed to get voices: {e}")
            return []

    def _generate_blocking(
        self,
        text: str,
        output_file: Path,
        voice: str,
        speed: float
    ) -> Path:
        """Blocking generation method to run in executor."""
        try:
            # Generate audio
            samples, sample_rate = self.kokoro.create(text, voice=voice, speed=speed)

            # Convert float32 to int16
            # Kokoro returns samples in range [-1, 1], scale to int16 range
            audio_int16 = np.clip(samples * 32767, -32768, 32767).astype(np.int16)

            # Save as WAV
            with wave.open(str(output_file), 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_int16.tobytes())

            logger.info(f"Generated speech: {output_file} (voice: {voice}, {len(samples)} samples)")
            return output_file
        except Exception as e:
            logger.error(f"Blocking speech generation failed: {e}")
            raise

    async def generate(
        self,
        text: str,
        output_file: Path,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> Path:
        """Generate speech from text (non-blocking).

        Args:
            text: Text to convert to speech
            output_file: Path to save audio file
            voice: Voice to use (defaults to self.default_voice)
            speed: Speech speed multiplier (defaults to self.speed)

        Returns:
            Path to generated audio file

        Raises:
            RuntimeError: If Kokoro is not available or generation fails
        """
        # Trigger lazy loading and wait for model to be ready
        if not self._load_failed:
            await self._lazy_load_model()

        if not self.is_available():
            raise RuntimeError("Kokoro TTS is not available")

        voice = voice or self.default_voice
        speed = speed or self.speed

        try:
            loop = asyncio.get_running_loop()
            # Run blocking generation in executor
            return await loop.run_in_executor(
                None,
                self._generate_blocking,
                text,
                output_file,
                voice,
                speed
            )

        except Exception as e:
            logger.error(f"Failed to generate speech: {e}")
            raise RuntimeError(f"Speech generation failed: {e}")

    def voice_exists(self, voice: str) -> bool:
        """Check if a voice exists.

        Args:
            voice: Voice name to check

        Returns:
            True if voice exists
        """
        if not self.is_available():
            return False

        return voice in self.get_voices()
