"""Text-to-Speech service supporting Kokoro TTS and Supertonic TTS."""
import logging
from pathlib import Path
from typing import Optional
from utils.helpers import clean_text_for_tts
from services.interfaces import TTSInterface

try:
    from services.kokoro_tts import KokoroTTSService
    KOKORO_AVAILABLE = True
except ImportError:
    KOKORO_AVAILABLE = False

try:
    from services.clients.tts_client import KokoroAPIClient
    KOKORO_API_AVAILABLE = True
except ImportError:
    KOKORO_API_AVAILABLE = False

try:
    from services.supertonic_tts import SupertonicTTSService
    SUPERTONIC_AVAILABLE = True
except ImportError:
    SUPERTONIC_AVAILABLE = False

logger = logging.getLogger(__name__)


class TTSService(TTSInterface):
    """Service for text-to-speech generation using Kokoro TTS or Supertonic TTS."""

    def __init__(
        self,
        engine: str = "kokoro_api",
        kokoro_voice: str = "am_adam",
        kokoro_speed: float = 1.0,
        kokoro_api_url: Optional[str] = None,
        supertonic_voice: str = "M1",
        supertonic_steps: int = 5,
        supertonic_speed: float = 1.05
    ):
        """Initialize TTS service.

        Args:
            engine: TTS engine to use ("kokoro", "kokoro_api", or "supertonic")
            kokoro_voice: Default Kokoro voice to use
            kokoro_speed: Kokoro speech speed multiplier
            kokoro_api_url: Kokoro-FastAPI URL (e.g., "http://localhost:8880")
            supertonic_voice: Default Supertonic voice (M1, M2, F1, F2)
            supertonic_steps: Supertonic denoising steps (higher = better quality)
            supertonic_speed: Supertonic speech speed multiplier
        """
        self.engine = engine.lower()
        self.kokoro_voice = kokoro_voice
        self.kokoro_speed = kokoro_speed
        self.kokoro_api_url = kokoro_api_url
        self.supertonic_voice = supertonic_voice
        self.supertonic_steps = supertonic_steps
        self.supertonic_speed = supertonic_speed

        # Initialize Kokoro API client if requested
        self.kokoro_api: Optional[KokoroAPIClient] = None
        if self.engine == "kokoro_api":
            if KOKORO_API_AVAILABLE and kokoro_api_url:
                self.kokoro_api = KokoroAPIClient(
                    api_url=kokoro_api_url,
                    default_voice=kokoro_voice,
                    speed=kokoro_speed
                )
                logger.info(f"Kokoro API client initialized (URL: {kokoro_api_url}, voice: {kokoro_voice})")
            else:
                raise RuntimeError("Kokoro API client not available or URL not provided. Set KOKORO_API_URL in config.")

        # Initialize Kokoro (in-process) if requested
        self.kokoro: Optional[KokoroTTSService] = None
        if self.engine == "kokoro":
            if KOKORO_AVAILABLE:
                self.kokoro = KokoroTTSService(
                    default_voice=kokoro_voice,
                    speed=kokoro_speed
                )
                if self.kokoro.is_available():
                    logger.info(f"Kokoro TTS initialized (voice: {kokoro_voice})")
                else:
                    raise RuntimeError("Kokoro TTS models not available. Check installation.")
            else:
                raise RuntimeError("Kokoro TTS module not found. Install with: pip install kokoro-onnx")

        # Initialize Supertonic if requested
        self.supertonic: Optional[SupertonicTTSService] = None
        if self.engine == "supertonic":
            if SUPERTONIC_AVAILABLE:
                try:
                    self.supertonic = SupertonicTTSService(
                        default_voice=supertonic_voice,
                        default_steps=supertonic_steps,
                        default_speed=supertonic_speed
                    )
                    if self.supertonic.is_available():
                        logger.info(f"Supertonic TTS initialized (voice: {supertonic_voice}, steps: {supertonic_steps}, speed: {supertonic_speed})")
                    else:
                        raise RuntimeError("Supertonic TTS not available. Check installation.")
                except Exception as e:
                    logger.error(f"Failed to initialize Supertonic TTS: {e}")
                    raise RuntimeError(f"Supertonic TTS initialization failed: {e}")
            else:
                raise RuntimeError("Supertonic TTS module not found. Check installation.")

    async def generate(
        self,
        text: str,
        output_path: Path,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        steps: Optional[int] = None,
    ) -> Path:
        """Generate speech from text and save to file.

        Args:
            text: Text to convert to speech
            output_path: Path to save audio file
            voice: Voice to use (depends on engine)
            speed: Speed multiplier for Kokoro/Supertonic TTS
            steps: Denoising steps for Supertonic TTS (higher = better quality)

        Returns:
            Path to generated audio file

        Raises:
            Exception: If TTS generation fails
        """
        # Clean text before TTS - remove emojis, asterisks, markdown, etc.
        cleaned_text = clean_text_for_tts(text)

        if not cleaned_text:
            logger.warning("Text was empty after cleaning, using original")
            cleaned_text = text

        logger.info(f"TTS input (cleaned): {cleaned_text[:100]}...")

        try:
            # Use Supertonic TTS
            if self.engine == "supertonic" and self.supertonic:
                supertonic_voice = voice or self.supertonic_voice
                supertonic_speed = speed or self.supertonic_speed
                supertonic_steps = steps or self.supertonic_steps

                # Supertonic's generate is sync, so we need to run it in an executor
                import asyncio
                loop = asyncio.get_event_loop()
                audio_path = await loop.run_in_executor(
                    None,
                    lambda: self.supertonic.generate(
                        text=cleaned_text,
                        voice=supertonic_voice,
                        speed=supertonic_speed,
                        steps=supertonic_steps,
                        output_path=str(output_path)
                    )
                )
                return Path(audio_path)

            # Use Kokoro API
            elif self.engine == "kokoro_api" and self.kokoro_api:
                kokoro_voice = voice or self.kokoro_voice
                kokoro_speed = speed or self.kokoro_speed
                return await self.kokoro_api.generate(
                    text=cleaned_text,
                    output_file=output_path,
                    voice=kokoro_voice,
                    speed=kokoro_speed
                )

            # Use Kokoro TTS (in-process)
            elif self.engine == "kokoro" and self.kokoro:
                kokoro_voice = voice or self.kokoro_voice
                kokoro_speed = speed or self.kokoro_speed
                return await self.kokoro.generate(
                    text=cleaned_text,
                    output_file=output_path,
                    voice=kokoro_voice,
                    speed=kokoro_speed
                )

            # No valid TTS engine configured
            else:
                raise RuntimeError(f"No valid TTS engine configured. Current engine: {self.engine}")

        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            raise Exception(f"Failed to generate speech: {e}")

    async def list_voices(self) -> list:
        """List all available voices for the current TTS engine.

        Returns:
            List of voice info dicts (engine-specific format)
        """
        if self.engine == "kokoro_api" and self.kokoro_api:
            # Kokoro API doesn't have a list_voices endpoint
            # Return static list of known voices
            return [
                {"name": "af_adam", "description": "American Male (Adam)"},
                {"name": "af_bella", "description": "American Female (Bella)"},
                {"name": "af_nicole", "description": "American Female (Nicole)"},
                {"name": "af_sarah", "description": "American Female (Sarah)"},
                {"name": "am_adam", "description": "American Male (Adam - Alt)"},
                {"name": "am_michael", "description": "American Male (Michael)"},
                {"name": "bf_emma", "description": "British Female (Emma)"},
                {"name": "bf_isabella", "description": "British Female (Isabella)"},
                {"name": "bm_george", "description": "British Male (George)"},
                {"name": "bm_lewis", "description": "British Male (Lewis)"},
            ]
        elif self.engine == "supertonic":
            # Supertonic voices
            return [
                {"name": "M1", "description": "Male Voice 1"},
                {"name": "M2", "description": "Male Voice 2"},
                {"name": "F1", "description": "Female Voice 1"},
                {"name": "F2", "description": "Female Voice 2"},
            ]
        else:
            logger.warning(f"list_voices() not implemented for engine: {self.engine}")
            return []

    async def get_voices_by_language(self, language_code: str) -> list:
        """Get voices for a specific language.

        Args:
            language_code: Language code (e.g., "en", "es", "fr")

        Returns:
            List of matching voice info dicts
        """
        # Current engines (Kokoro, Supertonic) only support English
        if language_code.startswith("en"):
            return await self.list_voices()
        else:
            logger.warning(f"Language '{language_code}' not supported by {self.engine}")
            return []

    def get_voice_info(self) -> dict:
        """Get information about the current default voice.

        Returns:
            Dict with voice configuration
        """
        if self.engine == "supertonic":
            return {
                "engine": "supertonic",
                "voice": self.supertonic_voice,
                "speed": self.supertonic_speed,
                "steps": self.supertonic_steps,
            }
        elif self.engine == "kokoro":
            return {
                "engine": "kokoro",
                "voice": self.kokoro_voice,
                "speed": self.kokoro_speed,
            }
        elif self.engine == "kokoro_api":
            return {
                "engine": "kokoro_api",
                "voice": self.kokoro_voice,
                "speed": self.kokoro_speed,
            }
        else:
            return {
                "engine": self.engine,
                "error": "Unknown TTS engine",
            }

    async def is_available(self) -> bool:
        """Check if TTS service is available.

        Returns:
            True if at least one TTS engine is configured
        """
        if self.engine == "kokoro_api":
            return KOKORO_API_AVAILABLE and self.kokoro_api is not None
        elif self.engine == "kokoro":
            return KOKORO_AVAILABLE and self.kokoro is not None
        elif self.engine == "supertonic":
            return SUPERTONIC_AVAILABLE and self.supertonic is not None
        return False

    async def cleanup(self):
        """Clean up resources.

        Note:
            Current TTS engines don't require explicit cleanup.
        """
        pass
