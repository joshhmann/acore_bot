"""Kokoro API client for using Kokoro-FastAPI backend."""
import logging
import asyncio
from pathlib import Path
from typing import Optional
import aiohttp

logger = logging.getLogger(__name__)


class KokoroAPIClient:
    """Client for Kokoro-FastAPI service."""

    def __init__(
        self,
        api_url: str = "http://localhost:8880",
        default_voice: str = "am_adam",
        speed: float = 1.0,
    ):
        """Initialize Kokoro API client.

        Args:
            api_url: Base URL of Kokoro-FastAPI service
            default_voice: Default voice to use
            speed: Speech speed multiplier
        """
        self.api_url = api_url.rstrip("/")
        self.default_voice = default_voice
        self.speed = speed
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()

    def is_available(self) -> bool:
        """Check if Kokoro API is available.

        Returns:
            True if API is reachable
        """
        try:
            import asyncio
            import aiohttp

            async def check():
                session = await self._get_session()
                try:
                    async with session.get(f"{self.api_url}/health", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                        return resp.status == 200
                except:
                    return False

            return asyncio.run(check())
        except:
            return False

    def get_voices(self) -> list[str]:
        """Get list of available voices.

        Returns:
            List of voice names
        """
        # Return known Kokoro voices
        return [
            "af_bella", "af_sarah", "af_nicole", "af_sky",
            "am_adam", "am_michael", "bm_george", "bm_lewis",
            "bf_emma", "bf_isabella", "am_onyx",
        ]

    async def generate(
        self,
        text: str,
        output_file: Path,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> Path:
        """Generate speech from text using API.

        Args:
            text: Text to convert to speech
            output_file: Path to save audio file
            voice: Voice to use (defaults to self.default_voice)
            speed: Speech speed multiplier (defaults to self.speed)

        Returns:
            Path to generated audio file

        Raises:
            RuntimeError: If API is not available or generation fails
        """
        voice = voice or self.default_voice
        speed = speed or self.speed

        try:
            session = await self._get_session()

            # Call OpenAI-compatible /v1/audio/speech endpoint
            payload = {
                "model": "kokoro",
                "input": text,
                "voice": voice,
                "speed": speed,
                "response_format": "wav",
            }

            async with session.post(
                f"{self.api_url}/v1/audio/speech",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"API error {resp.status}: {error_text}")

                # Save audio to file
                audio_data = await resp.read()
                output_file.write_bytes(audio_data)

                logger.info(f"Generated speech via API: {output_file} (voice: {voice})")
                return output_file

        except Exception as e:
            logger.error(f"Failed to generate speech via API: {e}")
            raise RuntimeError(f"Speech generation failed: {e}")

    def voice_exists(self, voice: str) -> bool:
        """Check if a voice exists.

        Args:
            voice: Voice name to check

        Returns:
            True if voice exists
        """
        return voice in self.get_voices()
