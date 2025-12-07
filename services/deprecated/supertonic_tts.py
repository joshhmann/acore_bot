"""Supertonic TTS service - lightning-fast on-device TTS."""
import logging
import os
import sys
from pathlib import Path
from typing import Optional, Tuple
import tempfile

# Add supertonic to path
SUPERTONIC_PATH = Path("/root/supertonic/py")
sys.path.insert(0, str(SUPERTONIC_PATH))

try:
    from helper import load_text_to_speech, load_voice_style
    SUPERTONIC_AVAILABLE = True
except ImportError:
    SUPERTONIC_AVAILABLE = False

logger = logging.getLogger(__name__)


class SupertonicTTSService:
    """Supertonic TTS service for ultra-fast speech synthesis."""

    # Voice style mappings
    VOICE_STYLES = {
        'M1': '/root/supertonic/assets/voice_styles/M1.json',  # Male 1
        'M2': '/root/supertonic/assets/voice_styles/M2.json',  # Male 2
        'F1': '/root/supertonic/assets/voice_styles/F1.json',  # Female 1
        'F2': '/root/supertonic/assets/voice_styles/F2.json',  # Female 2
    }

    # Alias mappings for easier use
    VOICE_ALIASES = {
        'male': 'M1',
        'male1': 'M1',
        'male2': 'M2',
        'female': 'F1',
        'female1': 'F1',
        'female2': 'F2',
        'man': 'M1',
        'woman': 'F1',
        'default': 'M1',
    }

    def __init__(
        self,
        onnx_dir: str = "/root/supertonic/assets/onnx",
        use_gpu: bool = False,
        default_voice: str = "M1",
        default_steps: int = 5,
        default_speed: float = 1.05
    ):
        """Initialize Supertonic TTS service.

        Args:
            onnx_dir: Path to ONNX models
            use_gpu: Use GPU for inference
            default_voice: Default voice style
            default_steps: Default denoising steps (higher = better quality)
            default_speed: Default speech speed
        """
        if not SUPERTONIC_AVAILABLE:
            raise ImportError(
                "Supertonic TTS not available. "
                "Ensure /root/supertonic is properly set up."
            )

        self.onnx_dir = onnx_dir
        self.use_gpu = use_gpu
        self.default_voice = default_voice
        self.default_steps = default_steps
        self.default_speed = default_speed

        # Model will be loaded on first use
        self.tts_model = None
        self.loaded_voice_style = None
        self.loaded_voice_name = None

        logger.info(f"Supertonic TTS service initialized (GPU: {use_gpu})")

    def _ensure_model_loaded(self):
        """Lazy-load the TTS model on first use."""
        if self.tts_model is None:
            logger.info("Loading Supertonic TTS model...")
            self.tts_model = load_text_to_speech(self.onnx_dir, self.use_gpu)
            logger.info("Supertonic TTS model loaded successfully")

    def _load_voice_style(self, voice: str) -> Tuple:
        """Load a voice style.

        Args:
            voice: Voice name or path

        Returns:
            Voice style object
        """
        # Resolve aliases
        voice = self.VOICE_ALIASES.get(voice.lower(), voice)

        # Check if we already loaded this voice
        if self.loaded_voice_style and self.loaded_voice_name == voice:
            return self.loaded_voice_style

        # Get voice path
        if voice in self.VOICE_STYLES:
            voice_path = self.VOICE_STYLES[voice]
        elif os.path.exists(voice):
            voice_path = voice
        else:
            logger.warning(f"Voice {voice} not found, using default {self.default_voice}")
            voice_path = self.VOICE_STYLES[self.default_voice]

        # Load voice style
        logger.debug(f"Loading voice style: {voice_path}")
        style = load_voice_style([voice_path], verbose=False)

        # Cache it
        self.loaded_voice_style = style
        self.loaded_voice_name = voice

        return style

    def generate(
        self,
        text: str,
        voice: Optional[str] = None,
        steps: Optional[int] = None,
        speed: Optional[float] = None,
        output_path: Optional[str] = None
    ) -> str:
        """Generate speech from text.

        Args:
            text: Text to synthesize
            voice: Voice style name (M1, M2, F1, F2, or aliases like 'male', 'female')
            steps: Number of denoising steps (higher = better quality, 1-20)
            speed: Speech speed multiplier (0.5-2.0, 1.0 = normal)
            output_path: Optional output file path

        Returns:
            Path to generated audio file
        """
        # Ensure model is loaded
        self._ensure_model_loaded()

        # Use defaults if not specified
        voice = voice or self.default_voice
        steps = steps or self.default_steps
        speed = speed or self.default_speed

        # Load voice style
        style = self._load_voice_style(voice)

        # Generate speech
        logger.info(f"Generating speech (voice={voice}, steps={steps}, speed={speed})")
        wav, duration = self.tts_model(text, style, steps, speed)

        # Create output file
        if output_path is None:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            output_path = temp_file.name
            temp_file.close()

        # Trim audio to actual duration (handle batch dimension)
        import soundfile as sf
        sample_rate = self.tts_model.sample_rate
        if wav.ndim == 2:  # Batch format [batch, samples]
            # Take first item from batch and trim to duration
            trimmed_wav = wav[0, : int(sample_rate * duration[0].item())]
        else:  # Single sample [samples]
            trimmed_wav = wav[: int(sample_rate * duration.item())]

        # Save audio
        sf.write(output_path, trimmed_wav, sample_rate)

        logger.info(f"Generated speech in {duration[0] if wav.ndim == 2 else duration:.2f}s, saved to {output_path}")
        return output_path

    def is_available(self) -> bool:
        """Check if Supertonic TTS is available.

        Returns:
            True if available
        """
        return SUPERTONIC_AVAILABLE

    def get_available_voices(self) -> dict:
        """Get available voice styles.

        Returns:
            Dict of voice names and their descriptions
        """
        return {
            'M1': 'Male voice 1 (default male)',
            'M2': 'Male voice 2',
            'F1': 'Female voice 1 (default female)',
            'F2': 'Female voice 2',
        }

    def get_voice_aliases(self) -> dict:
        """Get voice name aliases.

        Returns:
            Dict of aliases to voice names
        """
        return self.VOICE_ALIASES.copy()


# Module-level convenience function
def create_supertonic_service(**kwargs) -> Optional[SupertonicTTSService]:
    """Create Supertonic TTS service if available.

    Args:
        **kwargs: Arguments to pass to SupertonicTTSService

    Returns:
        SupertonicTTSService or None if not available
    """
    if not SUPERTONIC_AVAILABLE:
        logger.warning("Supertonic TTS not available")
        return None

    try:
        return SupertonicTTSService(**kwargs)
    except Exception as e:
        logger.error(f"Failed to create Supertonic TTS service: {e}")
        return None
