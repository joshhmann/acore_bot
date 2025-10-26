"""Text-to-Speech service using Edge TTS."""
import edge_tts
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class TTSService:
    """Service for text-to-speech generation using Edge TTS."""

    def __init__(self, default_voice: str = "en-US-AriaNeural", rate: str = "+0%", volume: str = "+0%"):
        """Initialize TTS service.

        Args:
            default_voice: Default voice to use
            rate: Speech rate adjustment (e.g., "+50%", "-20%")
            volume: Volume adjustment (e.g., "+50%", "-20%")
        """
        self.default_voice = default_voice
        self.rate = rate
        self.volume = volume

    async def generate(
        self,
        text: str,
        output_path: Path,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        volume: Optional[str] = None,
    ) -> Path:
        """Generate speech from text and save to file.

        Args:
            text: Text to convert to speech
            output_path: Path to save audio file
            voice: Voice to use (defaults to self.default_voice)
            rate: Speech rate (defaults to self.rate)
            volume: Volume level (defaults to self.volume)

        Returns:
            Path to generated audio file

        Raises:
            Exception: If TTS generation fails
        """
        try:
            communicate = edge_tts.Communicate(
                text,
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
        return {
            "voice": self.default_voice,
            "rate": self.rate,
            "volume": self.volume,
        }
