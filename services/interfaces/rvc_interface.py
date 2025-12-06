"""Abstract base class for Real-time Voice Conversion services."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class RVCInterface(ABC):
    """Interface for Real-time Voice Conversion (RVC) services.

    All RVC implementations (RVC-WebUI, local models, cloud APIs) should
    inherit from this class to ensure a consistent interface.
    """

    @abstractmethod
    async def convert(
        self,
        input_audio: Path,
        output_audio: Path,
        model_name: Optional[str] = None,
        pitch_shift: int = 0,
        index_rate: float = 0.75,
        **kwargs
    ) -> Path:
        """Convert voice in audio file using specified model.

        Args:
            input_audio: Path to input audio file
            output_audio: Path to save converted audio
            model_name: Model/voice to use (None = use default)
            pitch_shift: Pitch shift in semitones (-12 to +12)
            index_rate: Feature retrieval ratio (0.0-1.0, higher = more like target voice)
            **kwargs: Additional implementation-specific parameters
                - f0_method: Pitch detection method ("rmvpe", "crepe", "harvest")
                - protect: Consonant protection (0.0-0.5, prevents over-processing)
                - filter_radius: Median filtering radius for smoothing
                - resample_sr: Resample output to this sample rate

        Returns:
            Path to output audio file

        Raises:
            FileNotFoundError: If input file doesn't exist
            RuntimeError: If conversion fails or service unavailable
        """
        pass

    @abstractmethod
    async def list_models(self) -> list[str]:
        """List available voice conversion models.

        Returns:
            List of model names/identifiers

        Raises:
            RuntimeError: If unable to fetch model list
        """
        pass

    @abstractmethod
    async def is_enabled(self) -> bool:
        """Check if RVC service is enabled and available.

        Returns:
            True if service is operational, False otherwise
        """
        pass

    async def health_check(self) -> bool:
        """Check if the RVC service is healthy and responding.

        Returns:
            True if service is healthy, False otherwise

        Note:
            Default implementation calls is_enabled(). Override for
            more comprehensive health checks (API connectivity, model loading, etc.)
        """
        return await self.is_enabled()

    async def load_model(self, model_name: str):
        """Pre-load a model for faster conversion.

        Args:
            model_name: Model to pre-load

        Note:
            Default implementation does nothing. Override if service
            supports model preloading.
        """
        pass

    async def initialize(self):
        """Initialize the service (load default models, setup connections, etc.).

        Note:
            Default implementation does nothing. Override if needed.
        """
        pass

    async def cleanup(self):
        """Clean up resources (unload models, close connections, etc.).

        Note:
            Default implementation does nothing. Override if needed.
        """
        pass

    def get_default_model(self) -> Optional[str]:
        """Get the default model name.

        Returns:
            Default model name or None

        Note:
            Default returns None. Override to provide default model info.
        """
        return None
