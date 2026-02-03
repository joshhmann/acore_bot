"""LuxTTS API client for using LuxTTS OpenAI-compatible backend."""

import logging
from pathlib import Path
from typing import Optional
import aiohttp

logger = logging.getLogger(__name__)


class LuxTTSClient:
    """Client for LuxTTS OpenAI-compatible service."""

    def __init__(
        self,
        api_url: str = "http://localhost:9999",
        default_voice: str = "default",
        speed: float = 1.0,
    ):
        """Initialize LuxTTS API client.

        Args:
            api_url: Base URL of LuxTTS service
            default_voice: Default voice to use (must be uploaded first)
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
            self.session = None

    def is_available(self) -> bool:
        """Check if LuxTTS API is available.

        Returns:
            True if API is reachable
        """
        try:
            import asyncio

            async def check():
                session = await self._get_session()
                try:
                    async with session.get(
                        f"{self.api_url}/health", timeout=aiohttp.ClientTimeout(total=2)
                    ) as resp:
                        return resp.status == 200
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.debug(f"Health check failed: {e}")
                    return False
                except Exception as e:
                    logger.warning(f"Unexpected error during health check: {e}")
                    return False

            return asyncio.run(check())
        except Exception as e:
            logger.error(f"Failed to run health check: {e}")
            return False

    def get_voices(self) -> list[str]:
        """Get list of available voices.

        Returns:
            List of voice IDs
        """
        try:
            import asyncio

            async def fetch_voices():
                session = await self._get_session()
                try:
                    async with session.get(
                        f"{self.api_url}/v1/voices",
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            # Extract voice_ids from the response
                            return [v["voice_id"] for v in data.get("voices", [])]
                        else:
                            logger.warning(
                                f"Failed to fetch voices: HTTP {resp.status}"
                            )
                            return []
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.debug(f"Failed to fetch voices: {e}")
                    return []
                except Exception as e:
                    logger.warning(f"Unexpected error fetching voices: {e}")
                    return []

            return asyncio.run(fetch_voices())
        except Exception as e:
            logger.error(f"Failed to run get_voices: {e}")
            return []

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

        # Handle text truncation gracefully
        if len(text) > 4096:
            logger.warning(f"Text truncated from {len(text)} to 4096 characters")
            text = text[:4096]

        try:
            session = await self._get_session()

            # Call OpenAI-compatible /v1/audio/speech endpoint
            payload = {
                "model": "luxtts",
                "input": text,
                "voice": voice,
                "response_format": "wav",
                "speed": speed,
            }

            async with session.post(
                f"{self.api_url}/v1/audio/speech",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"API error {resp.status}: {error_text}")

                # Save audio to file
                audio_data = await resp.read()
                output_file.write_bytes(audio_data)

                logger.info(
                    f"Generated speech via LuxTTS API: {output_file} (voice: {voice})"
                )
                return output_file

        except Exception as e:
            logger.error(f"Failed to generate speech via LuxTTS API: {e}")
            raise RuntimeError(f"Speech generation failed: {e}")

    def voice_exists(self, voice: str) -> bool:
        """Check if a voice exists.

        Args:
            voice: Voice ID to check

        Returns:
            True if voice exists
        """
        return voice in self.get_voices()
