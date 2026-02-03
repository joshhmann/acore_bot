"""Image generation tools for the enhanced tool system."""

import asyncio
import base64
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import List, Optional

import aiohttp
from PIL import Image

from config import Config

logger = logging.getLogger(__name__)

IMAGE_CACHE_DIR = Config.DATA_DIR / "image_cache"
IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

RATE_LIMIT_LOCK = asyncio.Lock()
LAST_IMAGE_REQUEST = {}


@dataclass
class ImageResult:
    """Result from image generation."""

    success: bool
    image_url: Optional[str] = None
    image_path: Optional[Path] = None
    b64_image: Optional[str] = None
    revised_prompt: Optional[str] = None
    error: Optional[str] = None
    provider: Optional[str] = None
    generation_time: Optional[float] = None
    size: Optional[str] = None
    quality: Optional[str] = None
    style: Optional[str] = None


class ImageProvider:
    """Base class for image generation providers."""

    async def generate(
        self, prompt: str, size: str, quality: str, style: str
    ) -> ImageResult:
        raise NotImplementedError

    async def edit(
        self, image_path: str, mask_path: Optional[str], prompt: str
    ) -> ImageResult:
        raise NotImplementedError

    async def create_variation(self, image_path: str, n: int) -> List[ImageResult]:
        raise NotImplementedError


class OpenAIImageProvider(ImageProvider):
    """DALL-E image generation via OpenAI API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.openai.com/v1"
        self.model = "dall-e-3"

    def _parse_size(self, size: str) -> tuple[int, int]:
        """Parse size string to dimensions."""
        sizes = {
            "1024x1024": (1024, 1024),
            "1024x1792": (1024, 1792),
            "1792x1024": (1792, 1024),
            "512x512": (512, 512),
            "256x256": (256, 256),
        }
        return sizes.get(size, (1024, 1024))

    async def generate(
        self, prompt: str, size: str, quality: str, style: str
    ) -> ImageResult:
        start_time = datetime.now()
        width, height = self._parse_size(size)

        async with RATE_LIMIT_LOCK:
            try:
                async with aiohttp.ClientSession() as session:
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    }
                    payload = {
                        "model": self.model,
                        "prompt": prompt,
                        "n": 1,
                        "size": f"{width}x{height}",
                        "quality": quality
                        if quality in ["standard", "hd"]
                        else "standard",
                        "style": style if style in ["vivid", "natural"] else "vivid",
                    }

                    async with session.post(
                        f"{self.base_url}/images/generations",
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=120),
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"DALL-E API error: {error_text}")
                            return ImageResult(
                                success=False,
                                error=f"API error: {response.status}",
                                provider="openai",
                            )

                        data = await response.json()
                        generation_time = (datetime.now() - start_time).total_seconds()

                        image_url = data["data"][0]["url"]
                        revised_prompt = data["data"][0].get("revised_prompt", "")

                        return ImageResult(
                            success=True,
                            image_url=image_url,
                            revised_prompt=revised_prompt,
                            provider="openai",
                            generation_time=generation_time,
                            size=size,
                            quality=quality,
                            style=style,
                        )
            except asyncio.TimeoutError:
                return ImageResult(
                    success=False, error="Request timeout", provider="openai"
                )
            except Exception as e:
                logger.error(f"DALL-E generation error: {e}")
                return ImageResult(success=False, error=str(e), provider="openai")

    async def edit(
        self, image_path: str, mask_path: Optional[str], prompt: str
    ) -> ImageResult:
        start_time = datetime.now()

        try:
            if not os.path.exists(image_path):
                return ImageResult(
                    success=False,
                    error=f"Image not found: {image_path}",
                    provider="openai",
                )

            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                }

                form_data = aiohttp.FormData()
                form_data.add_field("prompt", prompt, content_type="text/plain")
                form_data.add_field("model", "dall-e-2", content_type="text/plain")
                form_data.add_field(
                    "image",
                    open(image_path, "rb").read(),
                    filename="image.png",
                    content_type="image/png",
                )

                if mask_path and os.path.exists(mask_path):
                    form_data.add_field(
                        "mask",
                        open(mask_path, "rb").read(),
                        filename="mask.png",
                        content_type="image/png",
                    )

                async with session.post(
                    f"{self.base_url}/images/edits",
                    headers=headers,
                    data=form_data,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return ImageResult(
                            success=False,
                            error=f"API error: {response.status}",
                            provider="openai",
                        )

                    data = await response.json()
                    generation_time = (datetime.now() - start_time).total_seconds()

                    return ImageResult(
                        success=True,
                        image_url=data["data"][0]["url"],
                        provider="openai",
                        generation_time=generation_time,
                    )
        except Exception as e:
            logger.error(f"DALL-E edit error: {e}")
            return ImageResult(success=False, error=str(e), provider="openai")

    async def create_variation(self, image_path: str, n: int) -> List[ImageResult]:
        start_time = datetime.now()
        results = []

        try:
            if not os.path.exists(image_path):
                return [
                    ImageResult(
                        success=False,
                        error=f"Image not found: {image_path}",
                        provider="openai",
                    )
                ]

            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                }

                form_data = aiohttp.FormData()
                form_data.add_field("n", str(n), content_type="text/plain")
                form_data.add_field("model", "dall-e-2", content_type="text/plain")
                form_data.add_field(
                    "image",
                    open(image_path, "rb").read(),
                    filename="image.png",
                    content_type="image/png",
                )

                async with session.post(
                    f"{self.base_url}/images/variations",
                    headers=headers,
                    data=form_data,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return [
                            ImageResult(
                                success=False,
                                error=f"API error: {response.status}",
                                provider="openai",
                            )
                        ]

                    data = await response.json()
                    generation_time = (datetime.now() - start_time).total_seconds()

                    for item in data["data"]:
                        results.append(
                            ImageResult(
                                success=True,
                                image_url=item["url"],
                                provider="openai",
                                generation_time=generation_time,
                            )
                        )
        except Exception as e:
            logger.error(f"DALL-E variation error: {e}")
            return [ImageResult(success=False, error=str(e), provider="openai")]

        return results


class ReplicateImageProvider(ImageProvider):
    """Stable Diffusion via Replicate API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.replicate.com/v1"
        self.model = "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b"

    async def generate(
        self, prompt: str, size: str, quality: str, style: str
    ) -> ImageResult:
        start_time = datetime.now()

        width, height = 1024, 1024
        if size == "1024x1792":
            height = 1792
        elif size == "1792x1024":
            width = 1792
        elif size == "512x512":
            width = height = 512
        elif size == "256x256":
            width = height = 256

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Token {self.api_key}",
                    "Content-Type": "application/json",
                    "Prefer": "wait",
                }
                payload = {
                    "version": self.model,
                    "input": {
                        "prompt": prompt,
                        "width": width,
                        "height": height,
                        "num_outputs": 1,
                    },
                }

                async with session.post(
                    f"{self.base_url}/predictions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as response:
                    if response.status not in [200, 201]:
                        error_text = await response.text()
                        return ImageResult(
                            success=False,
                            error=f"API error: {response.status}",
                            provider="replicate",
                        )

                    data = await response.json()
                    generation_time = (datetime.now() - start_time).total_seconds()

                    output = data.get("output", "")
                    if isinstance(output, list):
                        output = output[0] if output else ""

                    return ImageResult(
                        success=True,
                        image_url=output if output.startswith("http") else None,
                        b64_image=output if not output.startswith("http") else None,
                        provider="replicate",
                        generation_time=generation_time,
                        size=size,
                        quality=quality,
                        style=style,
                    )
        except Exception as e:
            logger.error(f"Replicate generation error: {e}")
            return ImageResult(success=False, error=str(e), provider="replicate")

    async def edit(
        self, image_path: str, mask_path: Optional[str], prompt: str
    ) -> ImageResult:
        return ImageResult(
            success=False,
            error="Image editing not supported with Replicate provider",
            provider="replicate",
        )

    async def create_variation(self, image_path: str, n: int) -> List[ImageResult]:
        return [
            ImageResult(
                success=False,
                error="Image variations not supported with Replicate provider",
                provider="replicate",
            )
        ]


class ComfyUIImageProvider(ImageProvider):
    """ComfyUI local/remote server for Stable Diffusion workflows."""

    def __init__(
        self,
        server_url: str = "http://127.0.0.1:8188",
        workflow_id: Optional[str] = None,
    ):
        self.server_url = server_url.rstrip("/")
        self.workflow_id = workflow_id  # Optional: use saved workflow ID
        self.client_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]

    async def _get_history(self, prompt_id: str) -> dict:
        """Get execution history for a prompt."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.server_url}/history/{prompt_id}",
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    return await response.json()
                return {}

    async def _get_image(
        self, filename: str, subfolder: str = "", folder_type: str = "output"
    ) -> bytes:
        """Download image from ComfyUI."""
        async with aiohttp.ClientSession() as session:
            params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
            async with session.get(
                f"{self.server_url}/view",
                params=params,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                if response.status == 200:
                    return await response.read()
                raise Exception(f"Failed to get image: {response.status}")

    async def _queue_prompt(self, prompt_data: dict) -> str:
        """Queue a prompt and return the prompt ID."""
        async with aiohttp.ClientSession() as session:
            payload = {"prompt": prompt_data, "client_id": self.client_id}
            async with session.post(
                f"{self.server_url}/prompt",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Failed to queue prompt: {error_text}")
                data = await response.json()
                return data["prompt_id"]

    async def _wait_for_completion(self, prompt_id: str, timeout: int = 300) -> bool:
        """Wait for prompt execution to complete."""
        start_time = datetime.now()
        while (datetime.now() - start_time).total_seconds() < timeout:
            history = await self._get_history(prompt_id)
            if prompt_id in history:
                status = history[prompt_id].get("status", {})
                if status.get("status") == "completed":
                    return True
                elif status.get("status") == "failed":
                    raise Exception(f"ComfyUI execution failed: {status.get('errors')}")
            await asyncio.sleep(1)
        raise Exception("ComfyUI execution timeout")

    def _build_sdxl_workflow(
        self, prompt: str, width: int, height: int, steps: int = 30
    ) -> dict:
        """Build a basic SDXL workflow for ComfyUI."""
        # This is a minimal SDXL workflow structure
        # You can customize this or load from a saved workflow
        return {
            "3": {
                "inputs": {
                    "seed": int(datetime.now().timestamp()),
                    "steps": steps,
                    "cfg": 8.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
                "class_type": "KSampler",
            },
            "4": {
                "inputs": {
                    "ckpt_name": "sdxl_base_1.0.safetensors",
                },
                "class_type": "CheckpointLoaderSimple",
            },
            "5": {
                "inputs": {
                    "width": width,
                    "height": height,
                    "batch_size": 1,
                },
                "class_type": "EmptyLatentImage",
            },
            "6": {
                "inputs": {
                    "text": prompt,
                    "clip": ["4", 1],
                },
                "class_type": "CLIPTextEncode",
            },
            "7": {
                "inputs": {
                    "text": "low quality, worst quality, blurry, deformed, bad anatomy",
                    "clip": ["4", 1],
                },
                "class_type": "CLIPTextEncode",
            },
            "8": {
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2],
                },
                "class_type": "VAEDecode",
            },
            "9": {
                "inputs": {
                    "filename_prefix": "acore_bot",
                    "images": ["8", 0],
                },
                "class_type": "SaveImage",
            },
        }

    async def generate(
        self, prompt: str, size: str, quality: str, style: str
    ) -> ImageResult:
        start_time = datetime.now()

        # Parse size
        size_map = {
            "1024x1024": (1024, 1024),
            "1024x1792": (1024, 1792),
            "1792x1024": (1792, 1024),
            "512x512": (512, 512),
            "256x256": (256, 256),
        }
        width, height = size_map.get(size, (1024, 1024))

        try:
            # Build workflow
            workflow = self._build_sdxl_workflow(prompt, width, height)

            # Queue prompt
            prompt_id = await self._queue_prompt(workflow)

            # Wait for completion
            await self._wait_for_completion(prompt_id, timeout=300)

            # Get history and extract image info
            history = await self._get_history(prompt_id)
            prompt_history = history.get(prompt_id, {})
            outputs = prompt_history.get("outputs", {})

            # Find the SaveImage node output
            images = []
            for node_id, output in outputs.items():
                if "images" in output:
                    for img in output["images"]:
                        images.append(img)

            if not images:
                return ImageResult(
                    success=False,
                    error="No images generated",
                    provider="comfyui",
                )

            # Download first image
            first_image = images[0]
            image_data = await self._get_image(
                first_image["filename"],
                first_image.get("subfolder", ""),
                first_image.get("type", "output"),
            )

            generation_time = (datetime.now() - start_time).total_seconds()

            # Save locally
            output_path = IMAGE_CACHE_DIR / f"comfyui_{first_image['filename']}"
            with open(output_path, "wb") as f:
                f.write(image_data)

            return ImageResult(
                success=True,
                image_path=output_path,
                b64_image=base64.b64encode(image_data).decode(),
                provider="comfyui",
                generation_time=generation_time,
                size=size,
                quality=quality,
                style=style,
            )

        except Exception as e:
            logger.error(f"ComfyUI generation error: {e}")
            return ImageResult(success=False, error=str(e), provider="comfyui")

    async def edit(
        self, image_path: str, mask_path: Optional[str], prompt: str
    ) -> ImageResult:
        # ComfyUI supports inpainting via different workflow
        # This is a placeholder - you can create a custom inpainting workflow
        return ImageResult(
            success=False,
            error="Image editing with ComfyUI requires custom workflow setup",
            provider="comfyui",
        )

    async def create_variation(self, image_path: str, n: int) -> List[ImageResult]:
        # ComfyUI can do variations via image-to-image workflow
        # This is a placeholder
        return [
            ImageResult(
                success=False,
                error="Image variations with ComfyUI require custom workflow setup",
                provider="comfyui",
            )
        ]


class LiteLLMImageProvider(ImageProvider):
    """Image generation via LiteLLM proxy (supports multiple backends)."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "dall-e-3",
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _parse_size(self, size: str) -> str:
        """Parse size string for LiteLLM."""
        size_map = {
            "1024x1024": "1024x1024",
            "1024x1792": "1024x1792",
            "1792x1024": "1792x1024",
            "512x512": "512x512",
            "256x256": "256x256",
        }
        return size_map.get(size, "1024x1024")

    async def generate(
        self, prompt: str, size: str, quality: str, style: str
    ) -> ImageResult:
        start_time = datetime.now()

        parsed_size = self._parse_size(size)

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "n": 1,
                    "size": parsed_size,
                }

                # Add provider-specific parameters
                if "dall-e" in self.model.lower():
                    payload["quality"] = (
                        quality if quality in ["standard", "hd"] else "standard"
                    )
                    payload["style"] = (
                        style if style in ["vivid", "natural"] else "vivid"
                    )

                async with session.post(
                    f"{self.base_url}/images/generations",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return ImageResult(
                            success=False,
                            error=f"API error: {response.status} - {error_text}",
                            provider="litellm",
                        )

                    data = await response.json()
                    generation_time = (datetime.now() - start_time).total_seconds()

                    image_url = data["data"][0]["url"]
                    revised_prompt = data["data"][0].get("revised_prompt", "")

                    return ImageResult(
                        success=True,
                        image_url=image_url,
                        revised_prompt=revised_prompt,
                        provider="litellm",
                        generation_time=generation_time,
                        size=size,
                        quality=quality,
                        style=style,
                    )
        except Exception as e:
            logger.error(f"LiteLLM generation error: {e}")
            return ImageResult(success=False, error=str(e), provider="litellm")

    async def edit(
        self, image_path: str, mask_path: Optional[str], prompt: str
    ) -> ImageResult:
        return ImageResult(
            success=False,
            error="Image editing not supported with this LiteLLM model",
            provider="litellm",
        )

    async def create_variation(self, image_path: str, n: int) -> List[ImageResult]:
        return [
            ImageResult(
                success=False,
                error="Image variations not supported with this LiteLLM model",
                provider="litellm",
            )
        ]


class KoboldCPPImageProvider(ImageProvider):
    """Image generation via KoboldCPP (local AI server)."""

    def __init__(self, base_url: str = "http://127.0.0.1:5001"):
        self.base_url = base_url.rstrip("/")
        self.sd_api = "/sdapi/v1"

    async def _wait_for_job(self, job_id: str, timeout: int = 120) -> dict:
        """Wait for image generation job to complete."""
        start_time = datetime.now()
        while (datetime.now() - start_time).total_seconds() < timeout:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}{self.sd_api}/jobs/{job_id}",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == "complete":
                            return data
                        elif data.get("status") == "failed":
                            raise Exception(f"Job failed: {data.get('error')}")
                    await asyncio.sleep(1)
        raise Exception("Job timeout")

    def _parse_size(self, size: str) -> tuple[int, int]:
        """Parse size string to dimensions."""
        size_map = {
            "1024x1024": (1024, 1024),
            "1024x1792": (1024, 1792),
            "1792x1024": (1792, 1024),
            "512x512": (512, 512),
            "256x256": (256, 256),
        }
        return size_map.get(size, (512, 512))

    async def generate(
        self, prompt: str, size: str, quality: str, style: str
    ) -> ImageResult:
        start_time = datetime.now()
        width, height = self._parse_size(size)

        try:
            async with aiohttp.ClientSession() as session:
                # txt2img endpoint
                payload = {
                    "prompt": prompt,
                    "negative_prompt": "low quality, worst quality, blurry, deformed, bad anatomy",
                    "width": width,
                    "height": height,
                    "steps": 30,
                    "cfg_scale": 7,
                    "sampler_name": "Euler a",
                    "batch_size": 1,
                    "n_iter": 1,
                }

                async with session.post(
                    f"{self.base_url}{self.sd_api}/txt2img",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return ImageResult(
                            success=False,
                            error=f"KoboldCPP API error: {response.status}",
                            provider="koboldcpp",
                        )

                    data = await response.json()
                    generation_time = (datetime.now() - start_time).total_seconds()

                    # KoboldCPP returns base64 images
                    images = data.get("images", [])
                    if not images:
                        return ImageResult(
                            success=False,
                            error="No images in response",
                            provider="koboldcpp",
                        )

                    b64_image = images[0]

                    # Save locally
                    output_path = (
                        IMAGE_CACHE_DIR
                        / f"koboldcpp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    )
                    with open(output_path, "wb") as f:
                        f.write(base64.b64decode(b64_image))

                    return ImageResult(
                        success=True,
                        image_path=output_path,
                        b64_image=b64_image,
                        provider="koboldcpp",
                        generation_time=generation_time,
                        size=size,
                        quality=quality,
                        style=style,
                    )

        except Exception as e:
            logger.error(f"KoboldCPP generation error: {e}")
            return ImageResult(success=False, error=str(e), provider="koboldcpp")

    async def edit(
        self, image_path: str, mask_path: Optional[str], prompt: str
    ) -> ImageResult:
        """Edit image using img2img with mask."""
        start_time = datetime.now()

        if not os.path.exists(image_path):
            return ImageResult(
                success=False,
                error=f"Image not found: {image_path}",
                provider="koboldcpp",
            )

        try:
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            async with aiohttp.ClientSession() as session:
                payload = {
                    "prompt": prompt,
                    "negative_prompt": "low quality, worst quality, blurry, deformed",
                    "init_images": [image_data],
                    "denoising_strength": 0.5,
                    "width": 512,
                    "height": 512,
                    "steps": 20,
                }

                if mask_path and os.path.exists(mask_path):
                    # KoboldCPP supports mask via img2img with mask
                    with open(mask_path, "rb") as f:
                        mask_data = base64.b64encode(f.read()).decode()
                    payload["mask"] = mask_data
                    endpoint = f"{self.base_url}{self.sd_api}/img2img"
                else:
                    endpoint = f"{self.base_url}{self.sd_api}/img2img"

                async with session.post(
                    endpoint,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return ImageResult(
                            success=False,
                            error=f"KoboldCPP API error: {response.status}",
                            provider="koboldcpp",
                        )

                    data = await response.json()
                    generation_time = (datetime.now() - start_time).total_seconds()

                    images = data.get("images", [])
                    if not images:
                        return ImageResult(
                            success=False,
                            error="No images in response",
                            provider="koboldcpp",
                        )

                    b64_image = images[0]
                    output_path = (
                        IMAGE_CACHE_DIR
                        / f"koboldcpp_edit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    )
                    with open(output_path, "wb") as f:
                        f.write(base64.b64decode(b64_image))

                    return ImageResult(
                        success=True,
                        image_path=output_path,
                        b64_image=b64_image,
                        provider="koboldcpp",
                        generation_time=generation_time,
                    )

        except Exception as e:
            logger.error(f"KoboldCPP edit error: {e}")
            return ImageResult(success=False, error=str(e), provider="koboldcpp")

    async def create_variation(self, image_path: str, n: int) -> List[ImageResult]:
        """Create variations using img2img."""
        if not os.path.exists(image_path):
            return [
                ImageResult(
                    success=False,
                    error=f"Image not found: {image_path}",
                    provider="koboldcpp",
                )
            ]

        results = []
        for _ in range(n):
            result = await self.edit(image_path, None, "Create a similar variation")
            results.append(result)

        return results


class ImageToolSystem:
    """Image generation tool wrapper for EnhancedToolSystem."""

    def __init__(self):
        self.provider: Optional[ImageProvider] = None
        self._initialize_provider()

    def _initialize_provider(self):
        if not Config.IMAGE_GENERATION_ENABLED:
            logger.info("Image generation is disabled")
            return

        provider = Config.IMAGE_PROVIDER.lower()

        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY", "")
            if api_key:
                self.provider = OpenAIImageProvider(api_key)
                logger.info("Initialized OpenAI image provider")
            else:
                logger.warning("OpenAI API key not configured")
        elif provider == "replicate":
            api_key = os.getenv("REPLICATE_API_KEY", "")
            if api_key:
                self.provider = ReplicateImageProvider(api_key)
                logger.info("Initialized Replicate image provider")
            else:
                logger.warning("Replicate API key not configured")
        elif provider == "comfyui":
            server_url = os.getenv("COMFYUI_SERVER_URL", "http://127.0.0.1:8188")
            self.provider = ComfyUIImageProvider(server_url=server_url)
            logger.info(f"Initialized ComfyUI image provider at {server_url}")
        elif provider == "litellm":
            api_key = os.getenv("LITELLM_API_KEY", "dummy")
            base_url = os.getenv("LITELLM_BASE_URL", "")
            model = os.getenv("LITELLM_IMAGE_MODEL", "dall-e-3")
            if base_url:
                self.provider = LiteLLMImageProvider(api_key, base_url, model)
                logger.info(f"LiteLLM image provider initialized: {base_url}")
            else:
                logger.warning("LiteLLM base URL not configured")
        elif provider == "koboldcpp":
            base_url = os.getenv("KOBOLDCPP_URL", "http://127.0.0.1:5001")
            self.provider = KoboldCPPImageProvider(base_url=base_url)
            logger.info(f"KoboldCPP image provider initialized at {base_url}")
        else:
            logger.warning(f"Unknown image provider: {provider}")

    def _get_cache_key(self, prompt: str, size: str, quality: str, style: str) -> str:
        key_string = f"{prompt}:{size}:{quality}:{style}"
        return hashlib.md5(key_string.encode()).hexdigest()

    def _get_cached_result(self, cache_key: str) -> Optional[ImageResult]:
        cache_file = IMAGE_CACHE_DIR / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    data = json.load(f)
                    result = ImageResult(**data)
                    if result.success:
                        logger.debug(f"Image cache hit: {cache_key}")
                        return result
            except Exception:
                pass
        return None

    def _cache_result(self, cache_key: str, result: ImageResult):
        if not result.success:
            return

        cache_file = IMAGE_CACHE_DIR / f"{cache_key}.json"
        try:
            with open(cache_file, "w") as f:
                json.dump(
                    {
                        "success": result.success,
                        "image_url": result.image_url,
                        "image_path": str(result.image_path)
                        if result.image_path
                        else None,
                        "revised_prompt": result.revised_prompt,
                        "provider": result.provider,
                        "generation_time": result.generation_time,
                        "size": result.size,
                        "quality": result.quality,
                        "style": result.style,
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            logger.error(f"Failed to cache image result: {e}")

    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
        style: str = "vivid",
    ) -> str:
        """Generate image using configured provider."""
        if not self.provider:
            return "Error: Image generation is not configured. Set IMAGE_GENERATION_ENABLED=true and configure API keys."

        cache_key = self._get_cache_key(prompt, size, quality, style)
        cached = self._get_cached_result(cache_key)
        if cached:
            if cached.image_url:
                return f"Image generated (cached): {cached.image_url}"
            elif cached.b64_image:
                return f"Image generated (cached, base64): [Image data available]"

        result = await self.provider.generate(prompt, size, quality, style)
        self._cache_result(cache_key, result)

        if result.success:
            if result.revised_prompt:
                response = f"Image generated successfully!\n"
                response += f"Prompt used: {result.revised_prompt}\n"
                if result.image_url:
                    response += f"URL: {result.image_url}"
                return response
            else:
                if result.image_url:
                    return f"Image generated: {result.image_url}"
                else:
                    return "Image generated successfully (base64 data available)"
        else:
            return f"Error generating image: {result.error}"

    async def edit_image(
        self, image_path: str, mask_path: Optional[str], prompt: str
    ) -> str:
        """Edit image with DALL-E edit endpoint."""
        if not self.provider:
            return "Error: Image generation is not configured."

        if not isinstance(self.provider, OpenAIImageProvider):
            return "Error: Image editing requires OpenAI provider."

        if not os.path.exists(image_path):
            return f"Error: Image file not found: {image_path}"

        result = await self.provider.edit(image_path, mask_path, prompt)

        if result.success:
            return f"Image edited successfully: {result.image_url}"
        else:
            return f"Error editing image: {result.error}"

    async def create_variation(self, image_path: str, n: int = 1) -> str:
        """Create variations of an image."""
        if not self.provider:
            return "Error: Image generation is not configured."

        if not isinstance(self.provider, OpenAIImageProvider):
            return "Error: Image variations require OpenAI provider."

        if not os.path.exists(image_path):
            return f"Error: Image file not found: {image_path}"

        results = await self.provider.create_variation(image_path, n)

        successful = [r for r in results if r.success]
        if successful:
            urls = "\n".join([f"- {r.image_url}" for r in successful])
            return f"Created {len(successful)} variation(s):\n{urls}"
        else:
            return f"Error creating variations: {results[0].error if results else 'Unknown error'}"


image_tool_system = ImageToolSystem()
