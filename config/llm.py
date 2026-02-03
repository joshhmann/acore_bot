"""LLM (Large Language Model) configuration."""

from typing import Dict
from .base import BaseConfig


class LLMConfig(BaseConfig):
    """LLM provider and model configuration."""

    # Provider Selection
    PROVIDER: str = BaseConfig._get_env("LLM_PROVIDER", "ollama").lower()

    # Tool System
    USE_FUNCTION_CALLING: bool = BaseConfig._get_env_bool("USE_FUNCTION_CALLING", False)

    # Caching
    CACHE_ENABLED: bool = BaseConfig._get_env_bool("LLM_CACHE_ENABLED", True)
    CACHE_MAX_SIZE: int = BaseConfig._get_env_int("LLM_CACHE_MAX_SIZE", 1000)
    CACHE_TTL_SECONDS: int = BaseConfig._get_env_int("LLM_CACHE_TTL_SECONDS", 3600)

    # Fallback Models
    FALLBACK_ENABLED: bool = BaseConfig._get_env_bool("LLM_FALLBACK_ENABLED", False)
    FALLBACK_MODELS: list = BaseConfig._get_env_list("LLM_FALLBACK_MODELS")

    # Advanced Sampling
    FREQUENCY_PENALTY: float = BaseConfig._get_env_float("LLM_FREQUENCY_PENALTY", 0.0)
    PRESENCE_PENALTY: float = BaseConfig._get_env_float("LLM_PRESENCE_PENALTY", 0.0)
    TOP_P: float = BaseConfig._get_env_float("LLM_TOP_P", 1.0)


class OllamaConfig(BaseConfig):
    """Ollama-specific configuration."""

    HOST: str = BaseConfig._get_env("OLLAMA_HOST", "http://localhost:11434")
    MODEL: str = BaseConfig._get_env("OLLAMA_MODEL", "llama3.2")
    TEMPERATURE: float = BaseConfig._get_env_float("OLLAMA_TEMPERATURE", 1.17)
    MAX_TOKENS: int = BaseConfig._get_env_int("OLLAMA_MAX_TOKENS", 500)
    MIN_P: float = BaseConfig._get_env_float("OLLAMA_MIN_P", 0.075)
    TOP_K: int = BaseConfig._get_env_int("OLLAMA_TOP_K", 50)
    REPEAT_PENALTY: float = BaseConfig._get_env_float("OLLAMA_REPEAT_PENALTY", 1.1)


class OpenRouterConfig(BaseConfig):
    """OpenRouter-specific configuration."""

    API_KEY: str = BaseConfig._get_env("OPENROUTER_API_KEY", "")
    MODEL: str = BaseConfig._get_env(
        "OPENROUTER_MODEL", "nousresearch/hermes-3-llama-3.1-405b"
    )
    URL: str = BaseConfig._get_env("OPENROUTER_URL", "https://openrouter.ai/api/v1")
    TIMEOUT: int = BaseConfig._get_env_int("OPENROUTER_TIMEOUT", 180)
    STREAM_TIMEOUT: int = BaseConfig._get_env_int("OPENROUTER_STREAM_TIMEOUT", 180)


class ThinkingConfig(BaseConfig):
    """Thinking/Decision model configuration."""

    MODEL: str = BaseConfig._get_env("THINKING_MODEL", "")
    MODEL_PROVIDER: str = BaseConfig._get_env("THINKING_MODEL_PROVIDER", "")


class ChatConfig(BaseConfig):
    """Chat and context configuration."""

    CLEAN_THINKING_OUTPUT: bool = BaseConfig._get_env_bool(
        "CLEAN_THINKING_OUTPUT", True
    )
    HISTORY_ENABLED: bool = BaseConfig._get_env_bool("CHAT_HISTORY_ENABLED", True)
    HISTORY_MAX_MESSAGES: int = BaseConfig._get_env_int(
        "CHAT_HISTORY_MAX_MESSAGES", 100
    )
    CONTEXT_MESSAGE_LIMIT: int = BaseConfig._get_env_int("CONTEXT_MESSAGE_LIMIT", 20)
    MAX_CONTEXT_TOKENS: int = BaseConfig._get_env_int("MAX_CONTEXT_TOKENS", 8192)

    # Model-specific context limits
    MODEL_CONTEXT_LIMITS: Dict[str, int] = {
        "llama3.2": 128000,
        "mistral": 32000,
        "gpt-4": 8192,
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
        "claude-3-opus-20240229": 200000,
        "claude-3-sonnet-20240229": 200000,
        "claude-3-haiku-20240307": 200000,
        "nousresearch/hermes-3-llama-3.1-405b": 128000,
    }

    # Streaming
    STREAMING_ENABLED: bool = BaseConfig._get_env_bool(
        "RESPONSE_STREAMING_ENABLED", True
    )
    STREAM_UPDATE_INTERVAL: float = BaseConfig._get_env_float(
        "STREAM_UPDATE_INTERVAL", 1.0
    )

    # Token Limits by Context
    TOKENS_VERY_SHORT: int = BaseConfig._get_env_int("RESPONSE_TOKENS_VERY_SHORT", 50)
    TOKENS_SHORT: int = BaseConfig._get_env_int("RESPONSE_TOKENS_SHORT", 100)
    TOKENS_MEDIUM: int = BaseConfig._get_env_int("RESPONSE_TOKENS_MEDIUM", 200)
    TOKENS_LONG: int = BaseConfig._get_env_int("RESPONSE_TOKENS_LONG", 350)
    TOKENS_VERY_LONG: int = BaseConfig._get_env_int("RESPONSE_TOKENS_VERY_LONG", 500)
