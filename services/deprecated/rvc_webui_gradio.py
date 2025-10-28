"""RVC WebUI client using Gradio Client library."""
import logging
import sys
import os
from pathlib import Path
from typing import Optional
from gradio_client import Client

logger = logging.getLogger(__name__)

# Suppress Gradio Client emoji output on Windows
if sys.platform == "win32":
    os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"


class RVCWebUIGradioClient:
    """Client for RVC-WebUI using Gradio Client library."""

    def __init__(self, base_url: str = "http://localhost:7865", default_model: str = "default"):
        """Initialize RVC WebUI client.

        Args:
            base_url: Base URL of RVC-WebUI
            default_model: Default model name to use
        """
        self.base_url = base_url
        self.default_model = default_model
        self.client = None

    def _get_client(self) -> Client:
        """Get or create Gradio client.

        Returns:
            Active Gradio client
        """
        if self.client is None:
            # Redirect stdout temporarily to suppress emoji output on Windows
            import io
            old_stdout = sys.stdout
            try:
                if sys.platform == "win32":
                    sys.stdout = io.StringIO()
                self.client = Client(self.base_url)
            finally:
                sys.stdout = old_stdout
        return self.client

    async def health_check(self) -> bool:
        """Check if RVC-WebUI is running.

        Returns:
            True if accessible
        """
        try:
            client = self._get_client()
            return client is not None
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def list_models(self) -> list[str]:
        """List available models.

        Returns:
            List of model names
        """
        if self.default_model:
            return [self.default_model]
        return []

    async def convert(
        self,
        input_audio: Path,
        output_audio: Path,
        model_name: Optional[str] = None,
        pitch_shift: int = 0,
        index_rate: float = 0.75,
        f0_method: str = "rmvpe",
        protect: float = 0.33,
        filter_radius: int = 3,
    ) -> Path:
        """Convert voice using RVC-WebUI.

        Args:
            input_audio: Path to input audio
            output_audio: Path to save output
            model_name: Model to use
            pitch_shift: Pitch shift in semitones
            index_rate: Feature retrieval ratio
            f0_method: Pitch detection method
            protect: Protection for consonants
            filter_radius: Smoothing radius

        Returns:
            Path to output audio
        """
        model = model_name or self.default_model

        try:
            client = self._get_client()

            # First, try to select/load the model using infer_change_voice
            # This might be needed to activate the model before conversion
            try:
                logger.info(f"Attempting to select model: {model}")
                # Redirect stdout to suppress emoji output
                import io
                old_stdout = sys.stdout
                if sys.platform == "win32":
                    sys.stdout = io.StringIO()

                # Call infer_change_voice to select the model
                # Parameters: voice_name, protect1, protect2
                change_result = client.predict(
                    model,  # Voice name
                    protect,  # Protect value 1
                    protect,  # Protect value 2
                    api_name="/infer_change_voice"
                )

                sys.stdout = old_stdout
                logger.info(f"Model selection result: {change_result}")
            except Exception as select_error:
                logger.warning(f"Could not select model (this may be normal): {select_error}")
                # Continue anyway - model might already be selected

            # Call the infer_convert endpoint
            # RVC-WebUI expects a LOCAL file path, not an uploaded file
            # We need to copy the file to a location RVC-WebUI can access

            # Use RVC-WebUI's TEMP folder
            rvc_temp = Path("C:/Users/CRIMS/Documents/Github/Retrieval-based-Voice-Conversion-WebUI/TEMP")
            rvc_temp.mkdir(exist_ok=True)

            # Copy input file to RVC temp location
            temp_input = rvc_temp / input_audio.name
            import shutil
            shutil.copy(input_audio, temp_input)

            input_path = str(temp_input.absolute()).replace("\\", "/")
            index_path = f"logs/{model}/added_{model}_v2.index"

            logger.info(f"Converting audio: {input_path}")
            logger.info(f"Model: {model}, Index: {index_path}, F0 method: {f0_method}")

            # Redirect stdout to suppress emoji output on Windows
            import io
            old_stdout = sys.stdout
            result = None
            try:
                if sys.platform == "win32":
                    sys.stdout = io.StringIO()

                # Pass the path as a string (not handle_file) since RVC expects local paths
                result = client.predict(
                    0,  # Speaker ID
                    input_path,  # Input audio path (local file)
                    pitch_shift,  # Transpose
                    None,  # F0 curve file (optional, None is valid)
                    f0_method,  # F0 method
                    "",  # Feature index path (empty to use dropdown)
                    index_path,  # Index path from dropdown
                    index_rate,  # Index rate
                    filter_radius,  # Filter radius
                    0,  # Resample sr
                    0.25,  # RMS mix rate
                    protect,  # Protect
                    api_name="/infer_convert"
                )
            except Exception as predict_error:
                import traceback
                logger.error(f"Predict call failed: {predict_error}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise
            finally:
                sys.stdout = old_stdout

            # Log the result for debugging
            if result is None:
                raise Exception("RVC API returned None - check RVC-WebUI is running and model exists")

            logger.info(f"RVC API result type: {type(result)}, len: {len(result) if hasattr(result, '__len__') else 'N/A'}")
            logger.info(f"RVC API result value: {result}")

            # Result should be a tuple: (info_message, output_audio_file)
            if isinstance(result, tuple) and len(result) >= 2:
                output_file = result[1]

                logger.info(f"Output file type: {type(output_file)}")
                logger.info(f"Output file value: {output_file}")
                logger.info(f"Output file repr: {repr(output_file)}")

                # Copy the output file to our desired location
                import shutil
                if output_file is None:
                    # Log the full result for debugging
                    logger.error(f"Full result tuple: {result}")
                    logger.error(f"Result[0] (info): {result[0]}")
                    raise Exception("RVC conversion returned None for output file - check RVC-WebUI logs and web UI console for errors")
                elif isinstance(output_file, str) and Path(output_file).exists():
                    shutil.copy(output_file, output_audio)
                    logger.info(f"RVC conversion successful: {output_audio}")
                    return output_audio
                elif hasattr(output_file, 'name') and output_file.name:
                    # It's a file object with a path
                    shutil.copy(output_file.name, output_audio)
                    logger.info(f"RVC conversion successful: {output_audio}")
                    return output_audio
                elif isinstance(output_file, dict) and 'name' in output_file:
                    # It's a dict with file info
                    shutil.copy(output_file['name'], output_audio)
                    logger.info(f"RVC conversion successful: {output_audio}")
                    return output_audio
                else:
                    raise Exception(f"Output file in unexpected format: {type(output_file)}")

            raise Exception(f"Unexpected result format - type: {type(result)}, len: {len(result) if hasattr(result, '__len__') else 'N/A'}, value: {result}")

        except Exception as e:
            logger.error(f"RVC conversion failed: {e}")
            # Fallback: copy input to output
            import shutil
            shutil.copy(input_audio, output_audio)
            return output_audio
        finally:
            # Clean up temp file
            try:
                if 'temp_input' in locals() and temp_input.exists():
                    temp_input.unlink()
            except Exception:
                pass

    def is_available(self) -> bool:
        """Check if client is configured.

        Returns:
            True if configured
        """
        return bool(self.base_url)
