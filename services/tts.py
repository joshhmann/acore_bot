"""Text-to-Speech service supporting Edge TTS and Kokoro TTS."""
import edge_tts
import logging
from pathlib import Path
from typing import Optional
from utils.helpers import clean_text_for_tts

try:
    from services.kokoro_tts import KokoroTTSService
    KOKORO_AVAILABLE = True
except ImportError:
    KOKORO_AVAILABLE = False

logger = logging.getLogger(__name__)


class TTSService:
    """Service for text-to-speech generation using Edge TTS or Kokoro TTS."""

    def __init__(
        self,
        engine: str = "edge",
        default_voice: str = "en-US-AriaNeural",
        rate: str = "+0%",
        volume: str = "+0%",
        kokoro_voice: str = "am_adam",
        kokoro_speed: float = 1.0
    ):
        """Initialize TTS service.

        Args:
            engine: TTS engine to use ("edge" or "kokoro")
            default_voice: Default Edge TTS voice to use
            rate: Speech rate adjustment for Edge TTS (e.g., "+50%", "-20%")
            volume: Volume adjustment for Edge TTS (e.g., "+50%", "-20%")
            kokoro_voice: Default Kokoro voice to use
            kokoro_speed: Kokoro speech speed multiplier
        """
        self.engine = engine.lower()
        self.default_voice = default_voice
        self.rate = rate
        self.volume = volume
        self.kokoro_voice = kokoro_voice
        self.kokoro_speed = kokoro_speed

        # Initialize Kokoro if requested
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
                    logger.warning("Kokoro TTS not available, falling back to Edge TTS")
                    self.engine = "edge"
            else:
                logger.warning("Kokoro TTS module not found, falling back to Edge TTS")
                self.engine = "edge"

    async def generate(
        self,
        text: str,
        output_path: Path,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        volume: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> Path:
        """Generate speech from text and save to file.

        Args:
            text: Text to convert to speech
            output_path: Path to save audio file
            voice: Voice to use (for Edge or Kokoro depending on engine)
            rate: Speech rate for Edge TTS (defaults to self.rate)
            volume: Volume level for Edge TTS (defaults to self.volume)
            speed: Speed multiplier for Kokoro TTS (defaults to self.kokoro_speed)

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
            # Use Kokoro TTS
            if self.engine == "kokoro" and self.kokoro:
                kokoro_voice = voice or self.kokoro_voice
                kokoro_speed = speed or self.kokoro_speed
                return await self.kokoro.generate(
                    text=cleaned_text,
                    output_file=output_path,
                    voice=kokoro_voice,
                    speed=kokoro_speed
                )

            # Use Edge TTS (default)
            else:
                communicate = edge_tts.Communicate(
                    cleaned_text,
                    voice=voice or self.default_voice,
                    rate=rate or self.rate,
                    volume=volume or self.volume,
                )

                await communicate.save(str(output_path))
                logger.info(f"Generated TTS audio: {output_path}")
                return output_path

        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            raise Exception(f"Failed to generate speech: {e}")

    async def list_voices(self) -> list:
        """List all available voices.

        Returns:
            List of voice info dicts
        """
        try:
            voices = await edge_tts.list_voices()
            return voices
        except Exception as e:
            logger.error(f"Failed to list voices: {e}")
            return []

    async def get_voices_by_language(self, language_code: str) -> list:
        """Get voices for a specific language.

        Args:
            language_code: Language code (e.g., "en", "es", "fr")

        Returns:
            List of matching voice info dicts
        """
        all_voices = await self.list_voices()
        return [v for v in all_voices if v["Locale"].startswith(language_code)]

    def get_voice_info(self) -> dict:
        """Get information about the current default voice.

        Returns:
            Dict with voice configuration
        """
        if self.engine == "kokoro":
            return {
                "engine": "kokoro",
                "voice": self.kokoro_voice,
                "speed": self.kokoro_speed,
            }
        else:
            return {
                "engine": "edge",
                "voice": self.default_voice,
                "rate": self.rate,
                "volume": self.volume,
            }
