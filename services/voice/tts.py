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
        supertonic_speed: float = 1.05,
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
                    speed=kokoro_speed,
                )
                logger.info(
                    f"Kokoro API client initialized (URL: {kokoro_api_url}, voice: {kokoro_voice})"
                )
            else:
                raise RuntimeError(
                    "Kokoro API client not available or URL not provided. Set KOKORO_API_URL in config."
                )

        # Initialize Kokoro (in-process) if requested
        self.kokoro: Optional[KokoroTTSService] = None
        if self.engine == "kokoro":
            if KOKORO_AVAILABLE:
                self.kokoro = KokoroTTSService(
                    default_voice=kokoro_voice, speed=kokoro_speed
                )
                if self.kokoro.is_available():
                    logger.info(f"Kokoro TTS initialized (voice: {kokoro_voice})")
                else:
                    raise RuntimeError(
                        "Kokoro TTS models not available. Check installation."
                    )
            else:
                raise RuntimeError(
                    "Kokoro TTS module not found. Install with: pip install kokoro-onnx"
                )

        # Initialize Supertonic if requested
        self.supertonic: Optional[SupertonicTTSService] = None
        if self.engine == "supertonic":
            if SUPERTONIC_AVAILABLE:
                try:
                    self.supertonic = SupertonicTTSService(
                        default_voice=supertonic_voice,
                        default_steps=supertonic_steps,
                        default_speed=supertonic_speed,
                    )
                    if self.supertonic.is_available():
                        logger.info(
                            f"Supertonic TTS initialized (voice: {supertonic_voice}, steps: {supertonic_steps}, speed: {supertonic_speed})"
                        )
                    else:
                        raise RuntimeError(
                            "Supertonic TTS not available. Check GPU and installation."
                        )
                except Exception as e:
                    logger.error(f"Failed to initialize Supertonic TTS: {e}")
                    raise RuntimeError(f"Supertonic TTS initialization failed: {e}")
            else:
                raise RuntimeError(
                    "Supertonic TTS module not found. Install with: pip install supertonic"
                )

    def is_available(self) -> bool:
        """Check if TTS service is available.

        Returns:
            True if any TTS engine is available
        """
        if self.engine == "kokoro_api":
            return self.kokoro_api is not None and self.kokoro_api.is_available()
        elif self.engine == "kokoro":
            return self.kokoro is not None and self.kokoro.is_available()
        elif self.engine == "supertonic":
            return self.supertonic is not None and self.supertonic.is_available()
        return False

    async def list_voices(self) -> list:
        """List all available voices for this TTS engine.

        Returns:
            List of voice info dicts. Format may vary by implementation,
            but should include at minimum:
            [
                {"name": "voice_id", "description": "Voice description"},
                ...
            ]
        """
        voices = []
        if self.engine == "kokoro_api" and self.kokoro_api:
            voice_names = self.kokoro_api.get_voices()
            voices = [{"name": voice, "description": f"Kokoro API voice: {voice}"} for voice in voice_names]
        elif self.engine == "kokoro" and self.kokoro:
            voice_names = self.kokoro.get_voices()
            voices = [{"name": voice, "description": f"Kokoro voice: {voice}"} for voice in voice_names]
        elif self.engine == "supertonic" and self.supertonic:
            voice_names = self.supertonic.get_voices()
            voices = [{"name": voice, "description": f"Supertonic voice: {voice}"} for voice in voice_names]
        return voices

    async def list_voices(self) -> list:
        """List all available voices for this TTS engine.

        Returns:
            List of voice info dicts. Format may vary by implementation,
            but should include at minimum:
            [
                {"name": "voice_id", "description": "Voice description"},
                ...
            ]
        """
        voices = []
        if self.engine == "kokoro_api" and self.kokoro_api:
            voice_names = self.kokoro_api.get_voices()
            voices = [
                {"name": voice, "description": f"Kokoro API voice: {voice}"}
                for voice in voice_names
            ]
        elif self.engine == "kokoro" and self.kokoro:
            voice_names = self.kokoro.get_voices()
            voices = [
                {"name": voice, "description": f"Kokoro voice: {voice}"}
                for voice in voice_names
            ]
        elif self.engine == "supertonic" and self.supertonic:
            voice_names = self.supertonic.get_voices()
            voices = [
                {"name": voice, "description": f"Supertonic voice: {voice}"}
                for voice in voice_names
            ]
        return voices

    def get_voices(self) -> list[str]:
        """Get list of available voices.

        Returns:
            List of voice names
        """
        if self.engine == "kokoro_api" and self.kokoro_api:
            return self.kokoro_api.get_voices()
        elif self.engine == "kokoro" and self.kokoro:
            return self.kokoro.get_voices()
        elif self.engine == "supertonic" and self.supertonic:
            return self.supertonic.get_voices()
        return []

    def voice_exists(self, voice: str) -> bool:
        """Check if a voice exists.

        Args:
            voice: Voice name to check

        Returns:
            True if voice exists
        """
        return voice in self.get_voices()

    async def generate(
        self,
        text: str,
        output_file: Path,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        **kwargs,
    ) -> Path:
        """Generate speech from text.

        Args:
            text: Text to convert to speech
            output_file: Path to save audio file
            voice: Optional voice override
            speed: Optional speed override
            **kwargs: Additional engine-specific parameters

        Returns:
            Path to generated audio file

        Raises:
            RuntimeError: If TTS engine is not available or generation fails
        """
        # Clean text for TTS
        cleaned_text = clean_text_for_tts(text)

        if self.engine == "kokoro_api" and self.kokoro_api:
            return await self.kokoro_api.generate(
                text=cleaned_text,
                output_file=output_file,
                voice=voice or self.kokoro_voice,
                speed=speed or self.kokoro_speed,
            )
        elif self.engine == "kokoro" and self.kokoro:
            return await self.kokoro.generate(
                text=cleaned_text,
                output_file=output_file,
                voice=voice or self.kokoro_voice,
                speed=speed or self.kokoro_speed,
            )
        elif self.engine == "supertonic" and self.supertonic:
            # Supertonic uses different parameters
            steps = kwargs.get("steps", self.supertonic_steps)
            return await self.supertonic.generate(
                text=cleaned_text,
                output_file=output_file,
                voice=voice or self.supertonic_voice,
                speed=speed or self.supertonic_speed,
                steps=steps,
            )
        else:
            raise RuntimeError(f"TTS engine '{self.engine}' is not available")

    async def generate_stream(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        **kwargs,
    ):
        """Generate speech as a stream (if supported by engine).

        Args:
            text: Text to convert to speech
            voice: Optional voice override
            speed: Optional speed override
            **kwargs: Additional engine-specific parameters

        Yields:
            Audio chunks as bytes

        Raises:
            RuntimeError: If streaming is not supported by current engine
        """
        # Clean text for TTS
        cleaned_text = clean_text_for_tts(text)

        if (
            self.engine == "kokoro_api"
            and self.kokoro_api
            and hasattr(self.kokoro_api, "generate_stream")
        ):
            async for chunk in self.kokoro_api.generate_stream(
                text=cleaned_text,
                voice=voice or self.kokoro_voice,
                speed=speed or self.kokoro_speed,
            ):
                yield chunk
        elif (
            self.engine == "kokoro"
            and self.kokoro
            and hasattr(self.kokoro, "generate_stream")
        ):
            async for chunk in self.kokoro.generate_stream(
                text=cleaned_text,
                voice=voice or self.kokoro_voice,
                speed=speed or self.kokoro_speed,
            ):
                yield chunk
        elif (
            self.engine == "supertonic"
            and self.supertonic
            and hasattr(self.supertonic, "generate_stream")
        ):
            steps = kwargs.get("steps", self.supertonic_steps)
            async for chunk in self.supertonic.generate_stream(
                text=cleaned_text,
                voice=voice or self.supertonic_voice,
                speed=speed or self.supertonic_speed,
                steps=steps,
            ):
                yield chunk
        else:
            # Fallback to regular generation and yield entire file
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = Path(temp_file.name)
                await self.generate(text, temp_path, voice, speed, **kwargs)
                # Read and yield entire file as one chunk
                with open(temp_path, "rb") as f:
                    yield f.read()
                # Clean up temp file
                temp_path.unlink()

    def estimate_duration(self, text: str, speed: Optional[float] = None) -> float:
        """Estimate speech duration in seconds.

        Args:
            text: Text to estimate
            speed: Optional speed multiplier

        Returns:
            Estimated duration in seconds
        """
        # Clean text
        cleaned_text = clean_text_for_tts(text)

        # Use engine-specific estimation if available
        if self.engine == "kokoro_api" and self.kokoro_api:
            speed = speed or self.kokoro_speed
        elif self.engine == "kokoro" and self.kokoro:
            speed = speed or self.kokoro_speed
        elif self.engine == "supertonic" and self.supertonic:
            speed = speed or self.supertonic_speed
        else:
            speed = speed or 1.0

        # Rough estimation: ~150 words per minute at speed=1.0
        word_count = len(cleaned_text.split())
        base_duration = (word_count / 150) * 60  # seconds
        adjusted_duration = base_duration / speed

        return adjusted_duration

    async def cleanup(self):
        """Clean up resources and close HTTP sessions.

        Closes aiohttp sessions in:
        - Kokoro API client (if using kokoro_api engine)
        """
        if self.kokoro_api and hasattr(self.kokoro_api, "close"):
            try:
                await self.kokoro_api.close()
                logger.debug("Kokoro API client session closed")
            except Exception as e:
                logger.error(f"Error closing Kokoro API session: {e}")
