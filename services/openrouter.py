"""OpenRouter LLM client service."""
import aiohttp
import logging
import json
from typing import List, Dict, Optional, AsyncGenerator

from config import Config

logger = logging.getLogger(__name__)


class OpenRouterService:
    """Service for interacting with OpenRouter API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        temperature: float = 0.7,
        max_tokens: int = 500,
        min_p: float = 0.075,
        top_k: int = 50,
        repeat_penalty: float = 1.1,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        top_p: float = 1.0,
    ):
        """Initialize OpenRouter service.

        Args:
            api_key: OpenRouter API Key
            model: Model name
            base_url: API Base URL
            temperature: Temperature
            max_tokens: Max tokens
            min_p: Min-P (mapped to top_p or passed if supported)
            top_k: Top-K
            repeat_penalty: Repetition penalty
            frequency_penalty: Frequency penalty
            presence_penalty: Presence penalty
            top_p: Top-P sampling
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.min_p = min_p
        self.top_k = top_k
        self.repeat_penalty = repeat_penalty
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty
        self.top_p = top_p
        self.session: Optional[aiohttp.ClientSession] = None

    async def initialize(self):
        """Initialize the HTTP session."""
        if not self.session:
            self.session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://github.com/joshhmann/acore_bot",
                    "X-Title": "Acore Bot",
                    "Content-Type": "application/json",
                }
            )

    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None

    def _clean_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Clean messages to only include 'role' and 'content' fields."""
        cleaned = []
        for msg in messages:
            cleaned.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })
        return cleaned

    async def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Send a chat request to OpenRouter."""
        if not self.session:
            await self.initialize()

        # Clean messages
        messages = self._clean_messages(messages)

        # Prepend system message if provided
        if system_prompt:
            # Check if there is already a system message at the start
            if messages and messages[0]["role"] == "system":
                messages[0]["content"] = f"{system_prompt}\n\n{messages[0]['content']}"
            else:
                messages = [{"role": "system", "content": system_prompt}] + messages

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": temperature or self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "repetition_penalty": self.repeat_penalty,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            # Pass extra parameters that might be supported by specific models
            "top_k": self.top_k,
            "min_p": self.min_p,
        }

        try:
            url = f"{self.base_url}/chat/completions"
            async with self.session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"OpenRouter API error ({resp.status}): {error_text}")

                data = await resp.json()
                return data["choices"][0]["message"]["content"]

        except aiohttp.ClientError as e:
            logger.error(f"OpenRouter request failed: {e}")
            raise Exception(f"Failed to connect to OpenRouter: {e}")
        except (KeyError, IndexError) as e:
            logger.error(f"Unexpected OpenRouter response format: {e}")
            raise Exception("Invalid response from OpenRouter")

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat responses from OpenRouter."""
        if not self.session:
            await self.initialize()

        messages = self._clean_messages(messages)

        if system_prompt:
            if messages and messages[0]["role"] == "system":
                messages[0]["content"] = f"{system_prompt}\n\n{messages[0]['content']}"
            else:
                messages = [{"role": "system", "content": system_prompt}] + messages

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": temperature or self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "repetition_penalty": self.repeat_penalty,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "top_k": self.top_k,
            "min_p": self.min_p,
        }

        try:
            url = f"{self.base_url}/chat/completions"
            async with self.session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"OpenRouter API error ({resp.status}): {error_text}")

                async for line in resp.content:
                    line = line.strip()
                    if not line or line == b"data: [DONE]":
                        continue
                    
                    if line.startswith(b"data: "):
                        try:
                            json_str = line[6:].decode("utf-8")
                            chunk = json.loads(json_str)
                            if "choices" in chunk and len(chunk["choices"]) > 0:
                                delta = chunk["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue

        except aiohttp.ClientError as e:
            logger.error(f"OpenRouter streaming request failed: {e}")
            raise Exception(f"Failed to connect to OpenRouter: {e}")

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate a response from a single prompt."""
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, system_prompt=system_prompt)

    async def chat_with_vision(
        self,
        prompt: str,
        images: List[str],
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Send a chat request with images to OpenRouter."""
        if not self.session:
            await self.initialize()

        # Format content for vision
        content = [{"type": "text", "text": prompt}]
        
        for img_b64 in images:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{img_b64}"
                }
            })

        messages = [{"role": "user", "content": content}]

        if system_prompt:
            messages.insert(0, {"role": "system", "content": system_prompt})

        vision_model = model or self.model

        payload = {
            "model": vision_model,
            "messages": messages,
            "stream": False,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "repetition_penalty": self.repeat_penalty,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "top_k": self.top_k,
            "min_p": self.min_p,
        }

        try:
            url = f"{self.base_url}/chat/completions"
            async with self.session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"OpenRouter Vision API error ({resp.status}): {error_text}")

                data = await resp.json()
                return data["choices"][0]["message"]["content"]

        except aiohttp.ClientError as e:
            logger.error(f"OpenRouter vision request failed: {e}")
            raise Exception(f"Failed to connect to OpenRouter: {e}")

    async def check_health(self) -> bool:
        """Check if OpenRouter is reachable (by listing models)."""
        if not self.session:
            await self.initialize()

        try:
            # OpenRouter has a models endpoint
            url = "https://openrouter.ai/api/v1/models"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"OpenRouter health check failed: {e}")
            return False

    async def list_models(self) -> List[str]:
        """List available models on OpenRouter."""
        if not self.session:
            await self.initialize()

        try:
            url = "https://openrouter.ai/api/v1/models"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return [model["id"] for model in data.get("data", [])]
                return []
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []
