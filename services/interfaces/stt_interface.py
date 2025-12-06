"""Abstract base class for Speech-to-Text services."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, TypedDict


class TranscriptionResult(TypedDict):
    """Standard format for transcription results."""
    text: str  # Full transcribed text
    language: str  # Detected or specified language code
    segments: list  # List of timed segments (optional, implementation-specific)


class STTInterface(ABC):
    """Interface for Speech-to-Text services.

    All STT implementations (Whisper, Parakeet, Google, etc.) should inherit
    from this class to ensure a consistent interface.
    """

    @abstractmethod
    async def transcribe_file(
        self,
        audio_path: Path,
        language: Optional[str] = None,
        task: str = "transcribe",
        **kwargs
    ) -> TranscriptionResult:
        """Transcribe audio file to text.

        Args:
            audio_path: Path to audio file
            language: Language code (e.g., "en", "es", None for auto-detect)
            task: Task type - "transcribe" (original language) or
                  "translate" (translate to English)
            **kwargs: Additional implementation-specific parameters
                - prompt: Hint text to guide transcription
                - temperature: Sampling temperature
                - beam_size: Beam search size

        Returns:
            TranscriptionResult dict with keys:
                - text: Full transcribed text
                - language: Detected or specified language
                - segments: List of timed segments (optional)

        Raises:
            RuntimeError: If transcription fails or service unavailable
        """
        pass

    @abstractmethod
    async def transcribe_audio_data(
        self,
        audio_data: bytes,
        sample_rate: int = 48000,
        language: Optional[str] = None,
        **kwargs
    ) -> TranscriptionResult:
        """Transcribe raw audio data to text.

        Args:
            audio_data: Raw audio bytes (PCM format)
            sample_rate: Sample rate of audio (Hz)
            language: Language code (None for auto-detect)
            **kwargs: Additional implementation-specific parameters

        Returns:
            TranscriptionResult dict (same format as transcribe_file)

        Raises:
            RuntimeError: If transcription fails or service unavailable
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the STT service is available and working.

        Returns:
            True if service is operational (model loaded, API accessible),
            False otherwise
        """
        pass

    async def cleanup(self):
        """Clean up resources (unload models, close connections, etc.).

        Note:
            Default implementation does nothing. Override if service needs cleanup.
        """
        pass

    def get_supported_languages(self) -> list[str]:
        """Get list of supported language codes.

        Returns:
            List of ISO 639-1 language codes (e.g., ["en", "es", "fr"])

        Note:
            Default returns empty list. Override to provide language support info.
        """
        return []
