"""Ollama LLM client service."""
import aiohttp
import logging
import json
from typing import List, Dict, Optional, AsyncGenerator

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
        """
        self.host = host.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.min_p = min_p
        self.top_k = top_k
        self.repeat_penalty = repeat_penalty
        self.session: Optional[aiohttp.ClientSession] = None

    async def initialize(self):
        """Initialize the HTTP session."""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None

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
            },
        }

        try:
            url = f"{self.host}/api/chat"
            async with self.session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"Ollama API error ({resp.status}): {error_text}")

                data = await resp.json()
                return data["message"]["content"]

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
            },
        }

        try:
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
