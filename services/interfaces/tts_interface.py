"""Abstract base class for Text-to-Speech services."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class TTSInterface(ABC):
    """Interface for Text-to-Speech services.

    All TTS implementations (Kokoro, Supertonic, Edge, etc.) should inherit from
    this class to ensure a consistent interface.
    """

    @abstractmethod
    async def generate(
        self,
        text: str,
        output_path: Path,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        **kwargs
    ) -> Path:
        """Generate speech from text and save to file.

        Args:
            text: Text to convert to speech
            output_path: Path to save audio file
            voice: Voice to use (implementation-specific)
            speed: Speech speed multiplier (1.0 = normal, >1.0 = faster, <1.0 = slower)
            **kwargs: Additional implementation-specific parameters
                - rate: For Edge TTS (+10%, -10%, etc.)
                - steps: For Supertonic TTS (denoising steps)
                - pitch: For pitch modulation

        Returns:
            Path to generated audio file

        Raises:
            Exception: If TTS generation fails
        """
        pass

    @abstractmethod
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
        pass

    async def is_available(self) -> bool:
        """Check if the TTS service is available and working.

        Returns:
            True if service is operational, False otherwise

        Note:
            Default implementation always returns True. Override to add
            health checks (e.g., API availability, model loading, etc.)
        """
        return True

    async def cleanup(self):
        """Clean up resources (close connections, unload models, etc.).

        Note:
            Default implementation does nothing. Override if service needs cleanup.
        """
        pass
