"""OpenRouter LLM client service."""
import aiohttp
import asyncio
import logging
import json
import time
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
        timeout: int = 180,
        stream_timeout: int = 180,
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
            timeout: Request timeout in seconds
            stream_timeout: Streaming request timeout in seconds
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
        self.timeout = timeout
        self.stream_timeout = stream_timeout
        self.session: Optional[aiohttp.ClientSession] = None

        # Performance metrics tracking
        self.last_response_time = 0.0  # seconds
        self.last_tps = 0.0  # tokens per second
        self.total_requests = 0
        self.total_tokens_generated = 0
        self.average_response_time = 0.0

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
        max_tokens: Optional[int] = None,
    ) -> str:
        """Send a chat request to OpenRouter.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: Optional system prompt
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
        """
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
            "max_tokens": max_tokens or self.max_tokens,
            "top_p": self.top_p,
            "repetition_penalty": self.repeat_penalty,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            # Pass extra parameters that might be supported by specific models
            "top_k": self.top_k,
            "min_p": self.min_p,
        }

        # Start timing
        start_time = time.time()

        try:
            url = f"{self.base_url}/chat/completions"
            async with self.session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=self.timeout)) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"OpenRouter API error ({resp.status}): {error_text}")

                data = await resp.json()

                # Calculate metrics
                end_time = time.time()
                response_time = end_time - start_time
                self.last_response_time = response_time
                self.total_requests += 1

                # Get token usage from response
                usage = data.get("usage", {})
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", 0)
                self.total_tokens_generated += completion_tokens

                # Calculate TPS (tokens per second)
                if response_time > 0 and completion_tokens > 0:
                    self.last_tps = completion_tokens / response_time
                else:
                    self.last_tps = 0.0

                # Update average response time
                if self.total_requests > 0:
                    old_avg = self.average_response_time
                    self.average_response_time = (old_avg * (self.total_requests - 1) + response_time) / self.total_requests

                # Log metrics
                logger.info(
                    f"OpenRouter response: {response_time:.2f}s | "
                    f"Tokens: {completion_tokens} | "
                    f"TPS: {self.last_tps:.1f} | "
                    f"Total: {total_tokens}"
                )

                return data["choices"][0]["message"]["content"]

        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            logger.error(f"OpenRouter request timed out after {elapsed:.1f}s")
            raise Exception("OpenRouter request timed out - the API took too long to respond. Try again or use a faster model.")
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
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat responses from OpenRouter.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: Optional system prompt
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
        """
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
            "max_tokens": max_tokens or self.max_tokens,
            "top_p": self.top_p,
            "repetition_penalty": self.repeat_penalty,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "top_k": self.top_k,
            "min_p": self.min_p,
        }

        # Streaming metrics
        start_time = time.time()
        first_token_time = None
        token_count = 0

        try:
            url = f"{self.base_url}/chat/completions"
            # Use sock_read timeout for streaming to allow long responses
            # total=None prevents timeout of the entire stream duration
            timeout = aiohttp.ClientTimeout(
                total=None, 
                sock_read=self.stream_timeout, 
                connect=self.timeout
            )
            async with self.session.post(
                url, json=payload, timeout=timeout
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
                                    # Track first token time (TTFT - Time To First Token)
                                    if first_token_time is None:
                                        first_token_time = time.time()
                                        ttft = first_token_time - start_time
                                        logger.debug(f"OpenRouter TTFT: {ttft:.2f}s")

                                    # Estimate token count (rough approximation)
                                    token_count += len(content.split())

                                    yield content
                        except json.JSONDecodeError:
                            continue

                # Calculate final metrics
                end_time = time.time()
                total_time = end_time - start_time
                self.last_response_time = total_time
                self.total_requests += 1
                self.total_tokens_generated += token_count

                # Calculate TPS
                if total_time > 0 and token_count > 0:
                    self.last_tps = token_count / total_time
                else:
                    self.last_tps = 0.0

                # Update average
                if self.total_requests > 0:
                    old_avg = self.average_response_time
                    self.average_response_time = (old_avg * (self.total_requests - 1) + total_time) / self.total_requests

                # Log metrics
                logger.info(
                    f"OpenRouter stream: {total_time:.2f}s | "
                    f"~{token_count} tokens | "
                    f"TPS: {self.last_tps:.1f} | "
                    f"TTFT: {(first_token_time - start_time) if first_token_time else 0:.2f}s"
                )

        except asyncio.TimeoutError:
            logger.error(f"OpenRouter streaming timeout after {time.time() - start_time:.1f}s")
            raise Exception("OpenRouter request timed out - try reducing message length or switching models")
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
            async with self.session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=self.timeout)) as resp:
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

    def get_performance_stats(self) -> Dict:
        """Get performance statistics for OpenRouter requests.

        Returns:
            Dictionary with performance metrics including:
            - last_response_time: Last request response time in seconds
            - last_tps: Last request tokens per second
            - average_response_time: Average response time across all requests
            - total_requests: Total number of requests made
            - total_tokens_generated: Total tokens generated
        """
        return {
            "last_response_time_seconds": round(self.last_response_time, 2),
            "last_response_time_ms": round(self.last_response_time * 1000, 1),
            "last_tps": round(self.last_tps, 1),
            "average_response_time_seconds": round(self.average_response_time, 2),
            "average_response_time_ms": round(self.average_response_time * 1000, 1),
            "total_requests": self.total_requests,
            "total_tokens_generated": self.total_tokens_generated,
            "model": self.model,
        }
