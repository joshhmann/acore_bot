"""Direct HTTP client for RVC-WebUI (bypassing Gradio Client issues)."""
import logging
import requests
from pathlib import Path
from typing import Optional
import json
import time
from config import Config

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
            # Step 1: Load the model first by calling infer_change_voice
            logger.info(f"Loading model: {model}")
            load_payload = {
                "data": [model, protect, protect],  # sid0, protect0, protect1
                "fn_index": None,
                "session_hash": f"rvc_{int(time.time())}"
            }

            load_response = self.session.post(
                f"{self.base_url}/api/infer_change_voice",
                json=load_payload,
                timeout=30
            )

            if load_response.status_code != 200:
                logger.error(f"Failed to load model: HTTP {load_response.status_code}")
                logger.error(f"Response: {load_response.text[:500]}")
            else:
                logger.info(f"Model loaded successfully: {model}")

            # Step 2: Copy input file to temp folder for RVC processing
            rvc_temp = Config.TEMP_DIR / "rvc"
            rvc_temp.mkdir(exist_ok=True)

            temp_input = rvc_temp / input_audio.name
            import shutil
            shutil.copy(input_audio, temp_input)

            input_path = str(temp_input.absolute())
            index_path = f"logs/{model}/added_{model}_v2.index"


            # Check audio duration and chunk if necessary
            import librosa
            import soundfile as sf
            import numpy as np
            
            # Load audio to check duration
            y, sr = librosa.load(input_audio, sr=None)
            duration = librosa.get_duration(y=y, sr=sr)
            
            MAX_CHUNK_DURATION = 20.0  # seconds
            
            if duration > MAX_CHUNK_DURATION:
                logger.info(f"Audio duration {duration:.2f}s exceeds limit {MAX_CHUNK_DURATION}s. Chunking...")
                
                # Split into chunks
                # We'll use a simple splitting strategy for now, but ideally we should split on silence
                # For now, just split by time with some overlap to avoid clicks (though simple concat might be fine for speech)
                
                chunk_samples = int(MAX_CHUNK_DURATION * sr)
                total_samples = len(y)
                
                converted_chunks = []
                
                for i in range(0, total_samples, chunk_samples):
                    chunk_idx = i // chunk_samples
                    chunk_y = y[i:min(i + chunk_samples, total_samples)]
                    
                    # Save chunk to temp file
                    chunk_path = rvc_temp / f"{input_audio.stem}_chunk_{chunk_idx}.wav"
                    sf.write(chunk_path, chunk_y, sr)
                    
                    logger.info(f"Processing chunk {chunk_idx + 1} ({len(chunk_y)/sr:.2f}s)...")
                    
                    # Process chunk recursively (but bypass duration check to avoid infinite recursion if logic is wrong)
                    # Actually, we can just call the API part directly or refactor. 
                    # To keep it simple, let's just do the API call logic here for each chunk.
                    # But that duplicates code.
                    # Let's refactor the API call into a private method `_convert_file`
                    
                    try:
                        chunk_output = rvc_temp / f"{input_audio.stem}_chunk_{chunk_idx}_out.wav"
                        await self._convert_file(
                            chunk_path, 
                            chunk_output, 
                            model, 
                            pitch_shift, 
                            index_rate, 
                            f0_method, 
                            protect, 
                            filter_radius,
                            index_path
                        )
                        
                        # Load converted chunk
                        chunk_out_y, chunk_out_sr = librosa.load(chunk_output, sr=None)
                        converted_chunks.append(chunk_out_y)
                        
                    except Exception as e:
                        logger.error(f"Failed to convert chunk {chunk_idx}: {e}")
                        # Fallback: use original chunk audio
                        converted_chunks.append(chunk_y)
                
                # Concatenate all chunks
                if converted_chunks:
                    final_y = np.concatenate(converted_chunks)
                    sf.write(output_audio, final_y, sr)
                    logger.info(f"Merged {len(converted_chunks)} chunks into {output_audio}")
                    return output_audio
            
            # If short enough, proceed with normal conversion
            input_path = str(temp_input.absolute())
            # index_path is already defined above
            

            await self._convert_file(
                temp_input,
                output_audio,
                model,
                pitch_shift,
                index_rate,
                f0_method,
                protect,
                filter_radius,
                index_path
            )
            
            return output_audio
        finally:
            # Clean up temp file
            try:
                if 'temp_input' in locals() and temp_input.exists():
                    temp_input.unlink()
            except Exception:
                pass



    async def _convert_file(
        self,
        input_path: Path,
        output_path: Path,
        model: str,
        pitch_shift: int,
        index_rate: float,
        f0_method: str,
        protect: float,
        filter_radius: int,
        index_path: str
    ):
        """Internal method to convert a single file."""
        input_str = str(input_path.absolute())
        
        logger.info(f"Converting audio: {input_str}")
        logger.info(f"Model: {model}, Index: {index_path}, F0 method: {f0_method}")

        # Step 3: Call the conversion API endpoint
        # Based on Gradio's internal API format
        # Try passing index path to the textbox (Input 5) instead of dropdown (Input 6)
        payload = {
            "data": [
                0,  # Speaker ID
                input_str,  # Input audio path
                pitch_shift,  # Transpose
                None,  # F0 curve file
                f0_method,  # F0 method
                index_path,  # Feature index path (Textbox)
                "",  # Index path from dropdown (Dropdown)
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
        try:
            response = self.session.post(
                f"{self.base_url}/api/infer_convert",
                json=payload,
                timeout=120
            )
            
            if response.status_code != 200:
                logger.warning(f"RVC conversion with index failed: HTTP {response.status_code}")
                # Fallback: try without index
                logger.info("Retrying without index file...")
                payload["data"][5] = ""  # Clear index path
                
                response = self.session.post(
                    f"{self.base_url}/api/infer_convert",
                    json=payload,
                    timeout=120
                )
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise

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

                if output_file_path:
                    # Copy directly from filesystem with proper delay for file writing
                    import asyncio
                    import os
                    from pathlib import Path as PathLib

                    try:
                        source_path = PathLib(output_file_path)

                        # Wait for file to be fully written (Gradio may still be writing)
                        logger.info(f"Waiting for RVC output file: {output_file_path}")
                        await asyncio.sleep(0.5)

                        # Try multiple times with increasing delays
                        max_attempts = 5
                        for attempt in range(max_attempts):
                            if source_path.exists():
                                # Check if file has content
                                file_size = source_path.stat().st_size
                                if file_size > 0:
                                    # Copy the file
                                    import shutil
                                    shutil.copy2(source_path, output_path)
                                    logger.info(f"RVC conversion successful: {output_path} ({file_size} bytes)")
                                    return output_path
                                else:
                                    logger.warning(f"RVC output file is empty, attempt {attempt + 1}/{max_attempts}")
                            else:
                                logger.warning(f"RVC output file not found, attempt {attempt + 1}/{max_attempts}")

                            # Wait before retry
                            if attempt < max_attempts - 1:
                                await asyncio.sleep(0.3)

                        logger.error(f"RVC output file not ready after {max_attempts} attempts")
                    except Exception as e:
                        logger.error(f"Failed to copy RVC output: {e}")
                        import traceback
                        logger.error(f"Traceback: {traceback.format_exc()}")
                else:
                    logger.error(f"No output file path in response")
            else:
                logger.error(f"Unexpected result format: {result}")

        raise Exception(f"RVC conversion failed - HTTP {response.status_code}")

    def is_available(self) -> bool:
        """Check if client is configured.

        Returns:
            True if available
        """
        return bool(self.base_url)
