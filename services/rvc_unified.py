"""RVC service using RVC-WebUI."""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class UnifiedRVCService:
    """RVC service using RVC-WebUI HTTP API."""

    def __init__(
        self,
        mode: str = "webui",
        model_path: Optional[Path] = None,  # Unused, kept for compatibility
        default_model: str = "default",
        device: str = "cpu",  # Unused, kept for compatibility
        webui_url: str = "http://localhost:7865",
    ):
        """Initialize RVC service.

        Args:
            mode: Must be "webui" (other modes deprecated)
            model_path: Deprecated - kept for backward compatibility
            default_model: Default model name
            device: Deprecated - kept for backward compatibility
            webui_url: RVC-WebUI API URL
        """
        self.mode = mode.lower()
        self.default_model = default_model
        self.backend = None

        if self.mode == "webui":
            try:
                from services.rvc_http import RVCHTTPClient
                self.backend = RVCHTTPClient(base_url=webui_url, default_model=default_model)
                logger.info(f"RVC initialized in WebUI mode: {webui_url}")
            except Exception as e:
                logger.error(f"Failed to initialize RVC WebUI client: {e}")
        else:
            logger.error(f"RVC mode '{mode}' is not supported. Only 'webui' mode is available.")

    async def convert(
        self,
        input_audio: Path,
        output_audio: Path,
        model_name: Optional[str] = None,
        pitch_shift: int = 0,
        index_rate: float = 0.75,
        f0_method: str = "rmvpe",  # Use RMVPE instead of CREPE to save VRAM
        protect: float = 0.33,
    ) -> Path:
        """Convert voice using configured backend.

        Args:
            input_audio: Path to input audio
            output_audio: Path to save converted audio
            model_name: Model to use
            pitch_shift: Pitch adjustment in semitones
            index_rate: Feature retrieval ratio
            f0_method: Pitch detection method
            protect: Protection for voiced consonants

        Returns:
            Path to converted audio

        Raises:
            Exception: If conversion fails
        """
        if not self.backend:
            logger.warning("No RVC backend available. Passing through audio unchanged.")
            import shutil
            shutil.copy(input_audio, output_audio)
            return output_audio

        return await self.backend.convert(
            input_audio=input_audio,
            output_audio=output_audio,
            model_name=model_name,
            pitch_shift=pitch_shift,
            index_rate=index_rate,
            f0_method=f0_method,
            protect=protect,
        )

    async def list_models(self) -> list[str]:
        """List available models.

        Returns:
            List of model names
        """
        if not self.backend:
            return []

        if hasattr(self.backend, "list_models"):
            return await self.backend.list_models()

        return []

    async def health_check(self) -> bool:
        """Check if RVC backend is available.

        Returns:
            True if backend is healthy
        """
        if not self.backend:
            return False

        if hasattr(self.backend, "health_check"):
            return await self.backend.health_check()

        return True  # inferpy mode doesn't have health check

    def is_enabled(self) -> bool:
        """Check if RVC is enabled and backend is available.

        Returns:
            True if RVC backend is initialized
        """
        return self.backend is not None

    def is_available(self) -> bool:
        """Check if RVC backend is initialized.

        Returns:
            True if backend exists
        """
        return self.backend is not None

    async def close(self):
        """Close RVC backend connections."""
        if self.backend and hasattr(self.backend, "close"):
            await self.backend.close()
