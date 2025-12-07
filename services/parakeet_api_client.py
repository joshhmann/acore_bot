"""Parakeet STT API Client - connects to external Parakeet FastAPI service."""
import aiohttp
import logging
from pathlib import Path
from typing import Optional
import asyncio
import wave
import tempfile

logger = logging.getLogger(__name__)


class ParakeetAPIClient:
    """Low-level client for the Parakeet STT FastAPI service."""

    def __init__(self, base_url: str = "http://localhost:8890", timeout: float = 60.0):
        """Initialize the Parakeet API client.

        Args:
            base_url: Base URL of the Parakeet API service
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None
        logger.info(f"Parakeet API client initialized (URL: {self.base_url})")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self):
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def health_check(self) -> bool:
        """Check if the Parakeet service is healthy."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/healthz") as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("status") == "ok"
                return False
        except Exception as e:
            logger.error(f"Parakeet health check failed: {e}")
            return False

    async def transcribe(
        self,
        audio_path: Path,
        include_timestamps: bool = False,
    ) -> Optional[str]:
        """Transcribe audio file."""
        try:
            session = await self._get_session()
            data = aiohttp.FormData()
            data.add_field(
                "file",
                open(audio_path, "rb"),
                filename=audio_path.name,
                content_type="audio/wav",
            )
            data.add_field("include_timestamps", str(include_timestamps).lower())

            async with session.post(f"{self.base_url}/transcribe", data=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("text", "").strip()
                else:
                    error_text = await response.text()
                    logger.error(f"Parakeet transcription failed ({response.status}): {error_text}")
                    return None
        except asyncio.TimeoutError:
            logger.error("Parakeet transcription timed out")
            return None
        except Exception as e:
            logger.error(f"Parakeet transcription error: {e}")
            return None


class ParakeetAPIService:
    """High-level STT service that uses the Parakeet API.
    
    This provides the same interface as ParakeetSTTService but uses
    an external API instead of loading the model in-process.
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8890",
        language: Optional[str] = None,
    ):
        """Initialize Parakeet API Service.

        Args:
            api_url: URL of the Parakeet FastAPI service
            language: Default language (informational only, API auto-detects)
        """
        self.api_url = api_url
        self.language = language or "auto"
        self._client = ParakeetAPIClient(base_url=api_url)
        self._available = None  # Cached availability status
        logger.info(f"Parakeet API Service initialized (URL: {api_url})")

    def is_available(self) -> bool:
        """Check if Parakeet API is available.
        
        Note: This does a synchronous check by running async in a new loop.
        For async code, use is_available_async() instead.
        """
        if self._available is not None:
            return self._available
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Can't run sync in running loop, assume available
                return True
            self._available = loop.run_until_complete(self._client.health_check())
        except Exception:
            try:
                self._available = asyncio.run(self._client.health_check())
            except Exception:
                self._available = False
        
        return self._available

    async def is_available_async(self) -> bool:
        """Async check if Parakeet API is available."""
        self._available = await self._client.health_check()
        return self._available

    async def transcribe_file(
        self,
        audio_path: Path,
        language: Optional[str] = None,
    ) -> dict:
        """Transcribe audio file to text.

        Args:
            audio_path: Path to audio file
            language: Language code (ignored, API auto-detects)

        Returns:
            Dictionary with transcription results
        """
        text = await self._client.transcribe(audio_path)
        
        if text is None:
            raise RuntimeError("Parakeet API transcription failed")
        
        return {
            "text": text.strip(),
            "language": self.language,
            "segments": [
                {
                    "text": text.strip(),
                    "start": 0.0,
                    "end": 0.0,
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
        # Create temporary WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

            # Write WAV file
            with wave.open(str(temp_path), "wb") as wav_file:
                wav_file.setnchannels(2)  # Stereo
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_data)

            try:
                result = await self.transcribe_file(temp_path, language)
                return result
            finally:
                temp_path.unlink()

    def get_supported_languages(self) -> list:
        """Get list of supported languages."""
        return ["en", "de", "es", "fr", "it", "pt", "pl", "nl", "ru", "uk",
                "cs", "ro", "hu", "sk", "bg", "hr", "sl", "lt", "lv", "et",
                "fi", "sv", "da", "no", "el"]

    def estimate_model_memory(self) -> dict:
        """Estimate memory requirements."""
        return {
            "ram": 0,  # Model runs in separate process
            "vram": 0,  # Model runs in separate process
            "note": "Model runs in external Parakeet API service",
        }

    async def close(self):
        """Close the API client."""
        await self._client.close()


# Convenience function
async def transcribe_audio(audio_path: Path, api_url: str = "http://localhost:8890") -> Optional[str]:
    """Transcribe audio using Parakeet API."""
    client = ParakeetAPIClient(base_url=api_url)
    try:
        return await client.transcribe(audio_path)
    finally:
        await client.close()
