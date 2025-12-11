"""Abstract base class for Large Language Model services."""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, AsyncGenerator


class LLMInterface(ABC):
    """Interface for Large Language Model services.

    All LLM implementations (Ollama, OpenRouter, Claude, GPT, etc.) should
    inherit from this class to ensure a consistent interface.
    """

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Send a chat request to the LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'.
                      Format: [{"role": "user", "content": "Hello"},
                               {"role": "assistant", "content": "Hi!"}]
            system_prompt: Optional system prompt to prepend/inject
            temperature: Sampling temperature (0.0-2.0, where lower = more deterministic)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional implementation-specific parameters
                - top_p: Nucleus sampling parameter
                - top_k: Top-k sampling parameter
                - frequency_penalty: Penalize frequent tokens
                - presence_penalty: Penalize repeated tokens
                - stop: Stop sequences

        Returns:
            Assistant's response text

        Raises:
            Exception: If request fails or service unavailable
        """
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Stream chat responses token by token.

        Args:
            messages: List of message dicts (same format as chat())
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Yields:
            Response text chunks as they're generated

        Raises:
            Exception: If streaming fails or service unavailable
        """
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Generate a response from a single prompt (simpler interface).

        Args:
            prompt: User prompt/question
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            Generated response text

        Raises:
            Exception: If generation fails
        """
        pass

    async def chat_with_vision(
        self,
        prompt: str,
        images: List[str],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Generate response from prompt + images (for vision models).

        Args:
            prompt: User prompt/question about the images
            images: List of image data (base64 strings or URLs)
            system_prompt: Optional system prompt
            **kwargs: Additional parameters

        Returns:
            Generated response text

        Raises:
            NotImplementedError: If vision is not supported
            Exception: If generation fails

        Note:
            Default implementation raises NotImplementedError. Override
            only if the LLM supports vision/multimodal inputs.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support vision/multimodal inputs"
        )

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the LLM service is available and working.

        Returns:
            True if service is operational (API accessible, models loaded),
            False otherwise
        """
        pass

    async def initialize(self):
        """Initialize the service (load models, setup connections, etc.).

        Note:
            Default implementation does nothing. Override if needed.
        """
        pass

    async def cleanup(self):
        """Clean up resources (close connections, unload models, etc.).

        Note:
            Default implementation does nothing. Override if needed.
        """
        pass

    async def check_health(self) -> bool:
        """Check if the LLM service is healthy and accessible.

        Returns:
            True if service is operational, False otherwise
        """
        return True

    def get_model_name(self) -> str:
        """Get the current model name/identifier.

        Returns:
            Model name (e.g., "gpt-4", "llama3", "claude-3-opus")

        Note:
            Default returns class name. Override for proper model identification.
        """
        return self.__class__.__name__
