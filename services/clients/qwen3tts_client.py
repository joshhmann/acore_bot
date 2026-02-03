"""Qwen3-TTS OpenAI-compatible API client."""

import logging
from pathlib import Path
from typing import AsyncGenerator, Optional
import aiohttp

logger = logging.getLogger(__name__)


class Qwen3TTSClient:
    """Client for Qwen3-TTS OpenAI-compatible service."""

    def __init__(
        self,
        api_url: str = "http://localhost:8880",
        default_voice: str = "Vivian",
        speed: float = 1.0,
        language: str = "Auto",
    ):
        """Initialize Qwen3-TTS client.

        Args:
            api_url: Base URL of Qwen3-TTS service
            default_voice: Default voice to use (built-in Qwen3 voices)
            speed: Speech speed multiplier
            language: Default language code
        """
        self.api_url = api_url.rstrip("/")
        self.default_voice = default_voice
        self.speed = speed
        self.language = language
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
        """Check if Qwen3-TTS API is available.

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
            List of voice names (built-in Qwen3 voices)
        """
        # Built-in Qwen3-TTS voices
        return [
            "Vivian",
            "Ryan",
            "Serena",
            "Dylan",
            "Eric",
            "Aiden",
            "Uncle_Fu",
            "Ono_Anna",
            "Sohee",
        ]

    async def generate(
        self,
        text: str,
        output_file: Path,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        language: Optional[str] = None,
    ) -> Path:
        """Generate speech from text using API (non-streaming).

        Args:
            text: Text to convert to speech
            output_file: Path to save audio file
            voice: Voice to use (defaults to self.default_voice)
            speed: Speech speed multiplier (defaults to self.speed)
            language: Language code (defaults to self.language)

        Returns:
            Path to generated audio file

        Raises:
            RuntimeError: If API is not available or generation fails
        """
        voice = voice or self.default_voice
        speed = speed or self.speed
        language = language or self.language

        try:
            session = await self._get_session()

            # Call OpenAI-compatible /v1/audio/speech endpoint
            payload = {
                "model": "qwen3-tts",
                "input": text,
                "voice": voice,
                "response_format": "wav",
                "speed": speed,
                "language": language,
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

                logger.info(f"Generated speech via API: {output_file} (voice: {voice})")
                return output_file

        except Exception as e:
            logger.error(f"Failed to generate speech via API: {e}")
            raise RuntimeError(f"Speech generation failed: {e}")

    async def generate_stream(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        language: Optional[str] = None,
    ) -> AsyncGenerator[bytes, None]:
        """Generate streaming speech from text using API.

        Yields audio chunks as they are generated for real-time playback.

        Args:
            text: Text to convert to speech
            voice: Voice to use (defaults to self.default_voice)
            speed: Speech speed multiplier (defaults to self.speed)
            language: Language code (defaults to self.language)

        Yields:
            Audio chunks as bytes

        Raises:
            RuntimeError: If API is not available or generation fails
        """
        voice = voice or self.default_voice
        speed = speed or self.speed
        language = language or self.language

        try:
            session = await self._get_session()

            # Call OpenAI-compatible /v1/audio/speech endpoint with streaming
            payload = {
                "model": "qwen3-tts",
                "input": text,
                "voice": voice,
                "response_format": "wav",
                "speed": speed,
                "language": language,
                "stream": True,
            }

            async with session.post(
                f"{self.api_url}/v1/audio/speech",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"API error {resp.status}: {error_text}")

                # Yield audio chunks as they arrive
                async for chunk in resp.content.iter_chunked(8192):
                    if chunk:
                        yield chunk

                logger.debug(f"Completed streaming speech (voice: {voice})")

        except Exception as e:
            logger.error(f"Failed to generate streaming speech via API: {e}")
            raise RuntimeError(f"Streaming speech generation failed: {e}")

    def voice_exists(self, voice: str) -> bool:
        """Check if a voice exists.

        Args:
            voice: Voice name to check

        Returns:
            True if voice exists
        """
        return voice in self.get_voices()
