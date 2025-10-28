"""RVC (Retrieval-based Voice Conversion) service.

Uses rvc-inferpy for voice conversion with RVC models.
Requires Python 3.11 and rvc-inferpy package.
"""
import logging
from pathlib import Path
from typing import Optional
import shutil

try:
    from rvc_inferpy import RVCConverter
    RVC_AVAILABLE = True
except ImportError:
    RVC_AVAILABLE = False

logger = logging.getLogger(__name__)


class RVCService:
    """Service for voice conversion using RVC.

    Uses rvc-inferpy to convert voices with trained RVC models.
    """

    def __init__(
        self,
        model_path: Path,
        default_model: str = "default",
        device: str = "cpu",
        is_half: bool = False
    ):
        """Initialize RVC service.

        Args:
            model_path: Path to directory containing RVC models
            default_model: Default model name to use
            device: Device to use ("cpu" or "cuda:0")
            is_half: Use half precision (faster on GPU)
        """
        self.model_path = Path(model_path)
        self.default_model = default_model
        self.device = device
        self.is_half = is_half
        self.converter: Optional[RVCConverter] = None

        # Create model directory if it doesn't exist
        self.model_path.mkdir(parents=True, exist_ok=True)

        # Initialize RVC converter if available
        if RVC_AVAILABLE:
            try:
                # RVC looks for models in specific paths, create a models directory
                models_dir = Path("models").absolute()
                models_dir.mkdir(exist_ok=True)

                # Copy/link model files to expected location if they exist
                import os
                rmvpe_source = Path("rmvpe.pt").absolute()
                hubert_source = Path("hubert_base.pt").absolute()

                if rmvpe_source.exists():
                    rmvpe_dest = models_dir / "rmvpe.pt"
                    if not rmvpe_dest.exists():
                        import shutil
                        shutil.copy(rmvpe_source, rmvpe_dest)
                    logger.info(f"Using rmvpe model: {rmvpe_dest}")

                if hubert_source.exists():
                    hubert_dest = models_dir / "hubert_base.pt"
                    if not hubert_dest.exists():
                        import shutil
                        shutil.copy(hubert_source, hubert_dest)
                    logger.info(f"Using hubert model: {hubert_dest}")

                self.converter = RVCConverter(device=device, is_half=is_half)
                logger.info(f"RVC converter initialized (device: {device})")
            except Exception as e:
                logger.error(f"Failed to initialize RVC converter: {e}")
                self.converter = None
        else:
            logger.warning("RVC not available. Install with: pip install rvc-inferpy")
            logger.warning("Voice conversion will pass through audio unchanged.")

    def load_model(self, model_name: str) -> bool:
        """Load an RVC voice model.

        Args:
            model_name: Name of the model to load

        Returns:
            True if successful, False otherwise
        """
        model_file = self.model_path / f"{model_name}.pth"

        if not model_file.exists():
            logger.warning(f"RVC model not found: {model_file}")
            return False

        # RVCConverter loads models on-demand during inference
        # Just verify the file exists
        logger.info(f"RVC model available: {model_name}")
        return True

    async def convert(
        self,
        input_audio: Path,
        output_audio: Path,
        model_name: Optional[str] = None,
        pitch_shift: int = 0,
        index_rate: float = 0.75,
        f0_method: str = "crepe",
        protect: float = 0.33,
    ) -> Path:
        """Convert voice using RVC model.

        Args:
            input_audio: Path to input audio file
            output_audio: Path to save converted audio
            model_name: Model to use (defaults to self.default_model)
            pitch_shift: Semitones to shift pitch (-12 to +12)
            index_rate: Feature retrieval ratio (0.0-1.0)
            f0_method: Pitch detection method ("rmvpe+", "rmvpe", "fcpe", etc.)
            protect: Protection for voiced consonants (0.0-0.5)

        Returns:
            Path to converted audio file

        Raises:
            Exception: If conversion fails
        """
        model = model_name or self.default_model

        # Check if RVC is available
        if not RVC_AVAILABLE or self.converter is None:
            logger.warning("RVC not available. Passing through audio unchanged.")
            shutil.copy(input_audio, output_audio)
            return output_audio

        # Find model file (check direct path and subfolders)
        model_file = self.model_path / f"{model}.pth"

        # If not found directly, check in subfolder with same name
        if not model_file.exists():
            subfolder_model = self.model_path / model
            if subfolder_model.is_dir():
                # Find .pth file in subfolder
                pth_files = list(subfolder_model.glob("*.pth"))
                if pth_files:
                    model_file = pth_files[0]  # Use first .pth file found

        # Final check if model exists
        if not model_file.exists():
            logger.warning(f"RVC model not found: {model}. Passing through audio unchanged.")
            shutil.copy(input_audio, output_audio)
            return output_audio

        try:
            logger.info(f"Converting voice with RVC: {model} (pitch: {pitch_shift}, method: {f0_method})")
            logger.info(f"Model file path: {model_file.absolute()}")

            # Perform voice conversion
            # RVC expects the model file path (directory containing the .pth)
            # If model is in subfolder, pass the subfolder path
            # If model is direct .pth file, pass the file path
            model_dir = model_file.parent if model_file.parent != self.model_path else model_file
            logger.info(f"Passing to RVC: {model_dir.absolute()}")

            # Add rmvpe model path to the inference call
            rmvpe_path = Path("models/rmvpe.pt").absolute()
            hubert_path = Path("models/hubert_base.pt").absolute()

            result = self.converter.infer_audio(
                voice_model=str(model_dir.absolute()),
                audio_path=str(input_audio),
                f0_change=pitch_shift,
                f0_method=f0_method,
                index_rate=index_rate,
                protect=protect,
                split_infer=False,
                filter_radius=3,
                resample_sr=0,  # Keep original sample rate
                rmvpe_model_path=str(rmvpe_path) if rmvpe_path.exists() else None,
                hubert_model_path=str(hubert_path) if hubert_path.exists() else None,
            )

            # Move result to output path
            if result and Path(result).exists():
                shutil.move(result, output_audio)
                logger.info(f"Voice conversion successful: {output_audio}")
                return output_audio
            else:
                logger.error("RVC conversion failed: no output generated")
                shutil.copy(input_audio, output_audio)
                return output_audio

        except Exception as e:
            logger.error(f"RVC conversion failed: {e}")
            # Fallback: copy input to output
            shutil.copy(input_audio, output_audio)
            return output_audio

    def list_models(self) -> list[str]:
        """List available RVC models.

        Returns:
            List of model names (subfolder name if in subfolder, filename otherwise)
        """
        if not self.model_path.exists():
            return []

        models = []

        # Check for .pth files directly in model_path
        for model_file in self.model_path.glob("*.pth"):
            models.append(model_file.stem)

        # Check for .pth files in subfolders (one level deep)
        for subfolder in self.model_path.iterdir():
            if subfolder.is_dir():
                pth_files = list(subfolder.glob("*.pth"))
                if pth_files:
                    # Use subfolder name as model name
                    models.append(subfolder.name)

        return models

    def is_enabled(self) -> bool:
        """Check if RVC is properly configured.

        Returns:
            True if RVC is available and models exist
        """
        return RVC_AVAILABLE and self.converter is not None and len(self.list_models()) > 0

    def is_available(self) -> bool:
        """Check if RVC library is available.

        Returns:
            True if rvc-inferpy is installed
        """
        return RVC_AVAILABLE and self.converter is not None
