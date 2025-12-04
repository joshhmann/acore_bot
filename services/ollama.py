"""Ollama LLM client service."""
import aiohttp
import logging
import json
from typing import List, Dict, Optional, AsyncGenerator

from config import Config
from services.llm_cache import LLMCache
from services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class OllamaService:
    """Service for interacting with Ollama LLM."""

    def __init__(
        self,
        host: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 500,
        min_p: float = 0.075,
        top_k: int = 50,
        repeat_penalty: float = 1.1,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        top_p: float = 1.0,
    ):
        """Initialize Ollama service.

        Args:
            host: Ollama server URL (e.g., http://localhost:11434)
            model: Model name (e.g., llama3.2, mistral, etc.)
            temperature: Temperature for response generation (0.0-2.0, recommended 1.12-1.22 for roleplay)
            max_tokens: Maximum tokens in response
            min_p: Min-P sampling (0.0-1.0, recommended 0.075 for roleplay)
            top_k: Top-K sampling (recommended 50 for roleplay)
            repeat_penalty: Repetition penalty (recommended 1.1 for roleplay)
            frequency_penalty: Frequency penalty
            presence_penalty: Presence penalty
            top_p: Top-P sampling
        """
        self.host = host.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.min_p = min_p
        self.top_k = top_k
        self.repeat_penalty = repeat_penalty
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty
        self.top_p = top_p
        self.session: Optional[aiohttp.ClientSession] = None

        # Initialize Rate Limiter
        # Limits concurrent requests to avoid OOM and rate limits API calls
        self.rate_limiter = RateLimiter(
            max_concurrent=5,  # Max 5 parallel generations
            requests_per_minute=60  # Max 60 requests per minute
        )

        # Initialize LLM response cache
        self.cache = LLMCache(
            max_size=Config.LLM_CACHE_MAX_SIZE,
            ttl_seconds=Config.LLM_CACHE_TTL_SECONDS,
            enabled=Config.LLM_CACHE_ENABLED
        )

    async def initialize(self):
        """Initialize the HTTP session."""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None

    def _clean_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Clean messages to only include 'role' and 'content' fields.

        Ollama API only expects 'role' and 'content'. Extra fields like 'username' or 'user_id'
        can cause issues or be included in model responses.

        Args:
            messages: List of message dicts (may have extra metadata fields)

        Returns:
            Cleaned messages with only role and content
        """
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
        """Send a chat request to Ollama.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: Optional system prompt to prepend
            temperature: Override default temperature

        Returns:
            Assistant's response text

        Raises:
            Exception: If request fails
        """
        if not self.session:
            await self.initialize()

        # Clean messages to remove extra metadata fields
        messages = self._clean_messages(messages)

        # Check cache first
        temp = temperature or self.temperature
        cached_response = self.cache.get(
            messages=messages,
            model=self.model,
            temperature=temp,
            system_prompt=system_prompt
        )
        if cached_response:
            logger.debug(f"Returning cached response for Ollama chat (model: {self.model})")
            return cached_response

        # Prepend system message if provided
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature or self.temperature,
                "num_predict": self.max_tokens,
                "min_p": self.min_p,
                "top_k": self.top_k,
                "repeat_penalty": self.repeat_penalty,
                "frequency_penalty": self.frequency_penalty,
                "presence_penalty": self.presence_penalty,
                "top_p": self.top_p,
                "num_ctx": 4096,  # Ensure full context window
            },
        }

        try:
            async with self.rate_limiter.acquire():
                url = f"{self.host}/api/chat"
                async with self.session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"Ollama API error ({resp.status}): {error_text}")

                    data = await resp.json()
                    response = data["message"]["content"]

                    # Cache the response
                    self.cache.set(
                        messages=messages,
                        model=self.model,
                        temperature=temp,
                        response=response,
                        system_prompt=system_prompt
                    )

                    return response

        except aiohttp.ClientError as e:
            logger.error(f"Ollama request failed: {e}")
            raise Exception(f"Failed to connect to Ollama: {e}")
        except KeyError as e:
            logger.error(f"Unexpected Ollama response format: {e}")
            raise Exception("Invalid response from Ollama")

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat responses from Ollama token by token.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: Optional system prompt to prepend
            temperature: Override default temperature

        Yields:
            Chunks of response text as they arrive

        Raises:
            Exception: If request fails
        """
        if not self.session:
            await self.initialize()

        # Clean messages to remove extra metadata fields
        messages = self._clean_messages(messages)

        # Prepend system message if provided
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,  # Enable streaming
            "options": {
                "temperature": temperature or self.temperature,
                "num_predict": self.max_tokens,
                "min_p": self.min_p,
                "top_k": self.top_k,
                "repeat_penalty": self.repeat_penalty,
                "frequency_penalty": self.frequency_penalty,
                "presence_penalty": self.presence_penalty,
                "top_p": self.top_p,
                "num_ctx": 4096,  # Ensure full context window
            },
        }

        try:
            async with self.rate_limiter.acquire():
                url = f"{self.host}/api/chat"
                async with self.session.post(
                    url, json=payload, timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"Ollama API error ({resp.status}): {error_text}")

                    # Stream response chunks
                    async for line in resp.content:
                        if line:
                            try:
                                chunk = json.loads(line)
                                if "message" in chunk and "content" in chunk["message"]:
                                    content = chunk["message"]["content"]
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                # Skip invalid JSON lines
                                continue

        except aiohttp.ClientError as e:
            logger.error(f"Ollama streaming request failed: {e}")
            raise Exception(f"Failed to connect to Ollama: {e}")

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate a response from a single prompt.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt

        Returns:
            Generated text
        """
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, system_prompt=system_prompt)

    async def chat_with_vision(
        self,
        prompt: str,
        images: List[str],
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Send a chat request with images to a vision model.

        Args:
            prompt: User prompt/question about the image
            images: List of base64-encoded image strings
            model: Vision model to use (defaults to config VISION_MODEL)
            system_prompt: Optional system prompt

        Returns:
            Assistant's response describing/analyzing the image

        Raises:
            Exception: If request fails
        """
        if not self.session:
            await self.initialize()

        # Build message with images
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({
            "role": "user",
            "content": prompt,
            "images": images
        })

        # Use vision model
        vision_model = model or Config.VISION_MODEL

        payload = {
            "model": vision_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
                "min_p": self.min_p,
                "top_k": self.top_k,
                "repeat_penalty": self.repeat_penalty,
                "frequency_penalty": self.frequency_penalty,
                "presence_penalty": self.presence_penalty,
                "top_p": self.top_p,
            },
        }

        try:
            async with self.rate_limiter.acquire():
                url = f"{self.host}/api/chat"
                async with self.session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"Ollama Vision API error ({resp.status}): {error_text}")

                    data = await resp.json()
                    return data["message"]["content"]

        except aiohttp.ClientError as e:
            logger.error(f"Ollama vision request failed: {e}")
            raise Exception(f"Failed to connect to Ollama: {e}")
        except KeyError as e:
            logger.error(f"Unexpected Ollama response format: {e}")
            raise Exception("Invalid response from Ollama")

    async def check_health(self) -> bool:
        """Check if Ollama server is reachable.

        Returns:
            True if healthy, False otherwise
        """
        if not self.session:
            await self.initialize()

        try:
            url = f"{self.host}/api/tags"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

    async def list_models(self) -> List[str]:
        """List available models on the Ollama server.

        Returns:
            List of model names
        """
        if not self.session:
            await self.initialize()

        try:
            url = f"{self.host}/api/tags"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return [model["name"] for model in data.get("models", [])]
                return []
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    def get_cache_stats(self) -> Dict:
        """Get LLM cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return self.cache.get_stats()

    def clear_cache(self):
        """Clear the LLM response cache."""
        self.cache.clear()
        logger.info("Ollama LLM cache cleared")
