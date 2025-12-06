"""Direct HTTP client for RVC-WebUI (bypassing Gradio Client issues)."""
import asyncio
import logging
import aiohttp
import shutil
from pathlib import Path
from typing import Optional
import json
import time
from config import Config
from services.interfaces import RVCInterface

logger = logging.getLogger(__name__)


class RVCHTTPClient(RVCInterface):
    """Simple HTTP client for RVC-WebUI API."""

    def __init__(self, base_url: str = "http://localhost:7865", default_model: str = "default"):
        """Initialize RVC HTTP client.

        Args:
            base_url: Base URL for RVC-WebUI
            default_model: Default model name
        """
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        """Ensure HTTP session is initialized."""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None

    async def health_check(self) -> bool:
        """Check if RVC-WebUI is running.

        Returns:
            True if healthy, False otherwise
        """
        await self._ensure_session()
        try:
            async with self.session.get(
                f"{self.base_url}/config",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                return response.status == 200
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

            await self._ensure_session()
            async with self.session.post(
                f"{self.base_url}/api/infer_change_voice",
                json=load_payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as load_response:
                if load_response.status != 200:
                    response_text = await load_response.text()
                    logger.error(f"Failed to load model: HTTP {load_response.status}")
                    logger.error(f"Response: {response_text[:500]}")
                else:
                    logger.info(f"Model loaded successfully: {model}")

            # Step 2: Copy input file to temp folder for RVC processing
            rvc_temp = Config.TEMP_DIR / "rvc"
            rvc_temp.mkdir(exist_ok=True)

            temp_input = rvc_temp / input_audio.name
            import shutil
            # Run blocking file copy in executor to avoid blocking event loop
            await asyncio.to_thread(shutil.copy, input_audio, temp_input)

            input_path = str(temp_input.absolute())
            index_path = f"logs/{model}/added_{model}_v2.index"


            # Check audio duration and chunk if necessary
            import librosa
            import soundfile as sf
            import numpy as np
            
            # Load audio to check duration (run in executor to avoid blocking)
            y, sr = await asyncio.to_thread(librosa.load, input_audio, sr=None)
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
                    
                    # Save chunk to temp file (run in executor to avoid blocking)
                    chunk_path = rvc_temp / f"{input_audio.stem}_chunk_{chunk_idx}.wav"
                    await asyncio.to_thread(sf.write, chunk_path, chunk_y, sr)
                    
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
                    # Use RVC output sample rate (48000 Hz), not original input rate

                    # Write to temp WAV first (sf.write only supports WAV)
                    temp_wav = output_audio.with_suffix('.wav')
                    sf.write(temp_wav, final_y, 48000)

                    # Convert to MP3 if output is MP3
                    if output_audio.suffix.lower() == '.mp3':
                        try:
                            import subprocess
                            subprocess.run([
                                'ffmpeg', '-i', str(temp_wav),
                                '-codec:a', 'libmp3lame',
                                '-b:a', '192k',
                                '-y',  # Overwrite output
                                str(output_audio)
                            ], check=True, capture_output=True)
                            temp_wav.unlink()  # Clean up temp WAV
                            logger.info(f"Merged {len(converted_chunks)} chunks into {output_audio}")
                        except Exception as e:
                            logger.error(f"Failed to convert merged WAV to MP3: {e}")
                            # Fall back to WAV
                            shutil.move(str(temp_wav), str(output_audio.with_suffix('.wav')))
                            return output_audio.with_suffix('.wav')
                    else:
                        # Output is already WAV
                        logger.info(f"Merged {len(converted_chunks)} chunks into {temp_wav}")

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
                48000,  # Resample sr (Discord expects 48kHz)
                0.25,  # RMS mix rate
                protect,  # Protect
            ],
            "fn_index": None,  # Will be determined by endpoint
            "session_hash": f"rvc_{int(time.time())}"
        }

        # Try the /api/infer_convert endpoint
        await self._ensure_session()
        try:
            async with self.session.post(
                f"{self.base_url}/api/infer_convert",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                response_status = response.status
                response_text = await response.text()

            if response_status != 200:
                logger.warning(f"RVC conversion with index failed: HTTP {response_status}")
                # Fallback: try without index
                logger.info("Retrying without index file...")
                payload["data"][5] = ""  # Clear index path

                async with self.session.post(
                    f"{self.base_url}/api/infer_convert",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as retry_response:
                    response_status = retry_response.status
                    response_text = await retry_response.text()

            logger.info(f"Response status: {response_status}")
            logger.info(f"Response text: {response_text[:500]}")

            if response_status == 200:
                result = json.loads(response_text)
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
                        try:
                            # Fix: Ensure output_file_path is string before creating Path
                            source_path = Path(str(output_file_path))

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
                                        # If output is MP3 but source is WAV (likely), convert it
                                        if output_path.suffix.lower() == '.mp3' and source_path.suffix.lower() != '.mp3':
                                            import subprocess
                                            logger.info(f"Converting RVC output to MP3: {output_path}")
                                            await asyncio.to_thread(subprocess.run, [
                                                'ffmpeg', '-i', str(source_path),
                                                '-codec:a', 'libmp3lame',
                                                '-b:a', '192k',
                                                '-y',
                                                str(output_path)
                                            ], check=True, capture_output=True)
                                        else:
                                            # Just copy/move
                                            await asyncio.to_thread(
                                                shutil.copy2,
                                                str(source_path),
                                                str(output_path)
                                            )
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

        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise

        raise Exception(f"RVC conversion failed - HTTP {response_status}")

    async def is_enabled(self) -> bool:
        """Check if RVC service is enabled and available.

        Returns:
            True if available
        """
        return bool(self.base_url)

    def get_default_model(self) -> Optional[str]:
        """Get the default model name.

        Returns:
            Default model name
        """
        return self.default_model

    async def initialize(self):
        """Initialize the service (ensure session is ready).

        Note:
            Session is created lazily by _ensure_session().
        """
        await self._ensure_session()

    async def cleanup(self):
        """Clean up resources.

        Alias for close() to match interface.
        """
        await self.close()
