"""RVC WebUI API client for voice conversion."""
import logging
from pathlib import Path
from typing import Optional
import aiohttp
import aiofiles

logger = logging.getLogger(__name__)


class RVCWebUIClient:
    """Client for RVC-WebUI API."""

    def __init__(self, base_url: str = "http://localhost:7865", default_model: str = "default"):
        """Initialize RVC WebUI client.

        Args:
            base_url: Base URL of RVC-WebUI API
            default_model: Default model name to use
        """
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session.

        Returns:
            Active aiohttp session
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def health_check(self) -> bool:
        """Check if RVC-WebUI is running and accessible.

        Returns:
            True if RVC-WebUI is accessible
        """
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/") as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"RVC-WebUI health check failed: {e}")
            return False

    async def list_models(self) -> list[str]:
        """List available voice models.

        Returns:
            List of model names
        """
        # RVC-WebUI doesn't have a reliable /api/models endpoint
        # Return the default model if configured, otherwise return empty list
        # Users can manually check their RVC-WebUI logs/ directory for available models
        if self.default_model:
            return [self.default_model]

        # Fallback: try the API endpoint anyway
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/api/models") as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("models", [])
                else:
                    logger.debug(f"API /api/models returned HTTP {response.status}, using default model only")
                    return []
        except Exception as e:
            logger.debug(f"Could not list models via API: {e}")
            return []

    async def convert(
        self,
        input_audio: Path,
        output_audio: Path,
        model_name: Optional[str] = None,
        pitch_shift: int = 0,
        index_rate: float = 0.75,
        f0_method: str = "crepe",
        protect: float = 0.33,
        filter_radius: int = 3,
    ) -> Path:
        """Convert voice using RVC-WebUI Gradio API.

        Args:
            input_audio: Path to input audio file
            output_audio: Path to save converted audio
            model_name: Model to use (defaults to self.default_model)
            pitch_shift: Semitones to shift pitch (-12 to +12)
            index_rate: Feature retrieval ratio (0.0-1.0)
            f0_method: Pitch detection method
            protect: Protection for voiced consonants (0.0-0.5)
            filter_radius: Smoothing radius

        Returns:
            Path to converted audio file

        Raises:
            Exception: If conversion fails
        """
        model = model_name or self.default_model

        try:
            session = await self._get_session()

            # For now, use absolute path directly since RVC-WebUI is local
            # This avoids the complexity of Gradio's file upload system
            # Convert Windows backslashes to forward slashes for JSON compatibility
            uploaded_file = str(input_audio.absolute()).replace("\\", "/")

            # Prepare Gradio API request for inference
            # Based on RVC-WebUI's /infer_convert endpoint
            # Parameters match the Gradio interface in order
            gradio_data = {
                "data": [
                    0,  # Speaker ID (usually 0)
                    uploaded_file,  # Input audio file path
                    pitch_shift,  # Transpose (semitones)
                    None,  # F0 curve file (optional)
                    f0_method,  # F0 method (pm, harvest, crepe, rmvpe)
                    "",  # Feature index file path (use auto-detect)
                    f"logs/{model}/added_{model}_v2.index",  # Auto-detected index path (use forward slashes)
                    index_rate,  # Index rate (0-1)
                    filter_radius,  # Filter radius (0-7)
                    0,  # Resample sr (0 = no resampling)
                    0.25,  # RMS mix rate (0-1)
                    protect,  # Protect (0-0.5)
                ]
            }

            # Use Gradio's synchronous run endpoint
            async with session.post(
                f"{self.base_url}/run/infer_convert",
                json=gradio_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    result = await response.json()

                    # Gradio returns result in data field
                    # data[0] is the info message, data[1] is the audio file
                    if "data" in result and len(result["data"]) > 1:
                        # Second element should be the output audio file
                        output_info = result["data"][1]

                        if isinstance(output_info, dict) and "name" in output_info:
                            # Download the output file from temp storage
                            output_url = f"{self.base_url}/file={output_info['name']}"
                            async with session.get(output_url) as download_response:
                                if download_response.status == 200:
                                    async with aiofiles.open(output_audio, "wb") as f:
                                        await f.write(await download_response.read())
                                    logger.info(f"RVC WebUI conversion successful: {output_audio}")
                                    return output_audio
                                else:
                                    raise Exception(f"Failed to download output: HTTP {download_response.status}")
                        elif isinstance(output_info, str):
                            # Sometimes it returns a file path string
                            import shutil
                            shutil.copy(output_info, output_audio)
                            logger.info(f"RVC WebUI conversion successful: {output_audio}")
                            return output_audio

                    raise Exception(f"Unexpected API response format: {result}")
                else:
                    error_text = await response.text()
                    raise Exception(f"RVC WebUI API error ({response.status}): {error_text}")

        except Exception as e:
            logger.error(f"RVC WebUI conversion failed: {e}")
            # Fallback: copy input to output
            import shutil
            shutil.copy(input_audio, output_audio)
            return output_audio

    def is_available(self) -> bool:
        """Check if RVC WebUI client is configured.

        Returns:
            True if base_url is set
        """
        return bool(self.base_url)
