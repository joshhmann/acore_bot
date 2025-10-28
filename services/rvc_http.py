"""Direct HTTP client for RVC-WebUI (bypassing Gradio Client issues)."""
import logging
import requests
from pathlib import Path
from typing import Optional
import json
import time

logger = logging.getLogger(__name__)


class RVCHTTPClient:
    """Simple HTTP client for RVC-WebUI API."""

    def __init__(self, base_url: str = "http://localhost:7865", default_model: str = "default"):
        """Initialize RVC HTTP client.

        Args:
            base_url: Base URL for RVC-WebUI
            default_model: Default model name
        """
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.session = requests.Session()

    async def health_check(self) -> bool:
        """Check if RVC-WebUI is running.

        Returns:
            True if healthy, False otherwise
        """
        try:
            response = self.session.get(f"{self.base_url}/config", timeout=5)
            return response.status_code == 200
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
        """Convert voice using RVC-WebUI via direct API calls.

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
            # Copy input file to RVC-WebUI's TEMP folder
            rvc_temp = Path("C:/Users/CRIMS/Documents/Github/Retrieval-based-Voice-Conversion-WebUI/TEMP")
            rvc_temp.mkdir(exist_ok=True)

            temp_input = rvc_temp / input_audio.name
            import shutil
            shutil.copy(input_audio, temp_input)

            input_path = str(temp_input.absolute()).replace("\\", "/")
            index_path = f"logs/{model}/added_{model}_v2.index"

            logger.info(f"Converting audio: {input_path}")
            logger.info(f"Model: {model}, Index: {index_path}, F0 method: {f0_method}")

            # Call the API endpoint using plain HTTP POST
            # Based on Gradio's internal API format
            payload = {
                "data": [
                    0,  # Speaker ID
                    input_path,  # Input audio path
                    pitch_shift,  # Transpose
                    None,  # F0 curve file
                    f0_method,  # F0 method
                    "",  # Feature index path (empty to use dropdown)
                    index_path,  # Index path from dropdown
                    index_rate,  # Index rate
                    filter_radius,  # Filter radius
                    0,  # Resample sr
                    0.25,  # RMS mix rate
                    protect,  # Protect
                ],
                "fn_index": None,  # Will be determined by endpoint
                "session_hash": f"rvc_{int(time.time())}"
            }

            # Try the /api/infer_convert endpoint
            response = self.session.post(
                f"{self.base_url}/api/infer_convert",
                json=payload,
                timeout=120
            )

            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response text: {response.text[:500]}")

            if response.status_code == 200:
                result = response.json()
                logger.info(f"Result: {result}")

                # Extract output file path from result
                if "data" in result and len(result["data"]) >= 2:
                    output_info = result["data"][1]
                    logger.info(f"Output info: {output_info}")

                    # The output might be a dict with 'name' key or a direct path
                    output_file_path = None
                    if isinstance(output_info, dict) and "name" in output_info:
                        output_file_path = output_info["name"]
                    elif isinstance(output_info, str):
                        output_file_path = output_info

                    if output_file_path and Path(output_file_path).exists():
                        shutil.copy(output_file_path, output_audio)
                        logger.info(f"RVC conversion successful: {output_audio}")
                        return output_audio
                    else:
                        logger.error(f"Output file not found or invalid: {output_file_path}")
                else:
                    logger.error(f"Unexpected result format: {result}")

            raise Exception(f"RVC conversion failed - HTTP {response.status_code}")

        except Exception as e:
            logger.error(f"RVC conversion failed: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
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
            True if available
        """
        return bool(self.base_url)
