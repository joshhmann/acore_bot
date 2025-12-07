"""Dependency Injection Container for managing service lifecycles."""

import logging
from typing import Dict, Any, Optional, Type, TypeVar, Callable
from config import Config

logger = logging.getLogger(__name__)

T = TypeVar('T')


class DIContainer:
    """Simple dependency injection container.

    Manages service instances, configuration, and lifecycle.
    Supports singleton and factory patterns.
    """

    def __init__(self):
        """Initialize the DI container."""
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, bool] = {}

    def register(
        self,
        name: str,
        factory: Callable,
        singleton: bool = True
    ):
        """Register a service factory.

        Args:
            name: Service name (e.g., "llm", "tts", "stt")
            factory: Factory function that creates the service
            singleton: If True, reuse same instance (default: True)

        Example:
            ```python
            container.register("llm", lambda: OllamaService(
                host=Config.OLLAMA_HOST,
                model=Config.OLLAMA_MODEL
            ))
            ```
        """
        self._factories[name] = factory
        self._singletons[name] = singleton
        logger.debug(f"Registered service '{name}' (singleton={singleton})")

    def register_instance(self, name: str, instance: Any):
        """Register an existing instance.

        Args:
            name: Service name
            instance: Service instance

        Example:
            ```python
            my_service = MyService()
            container.register_instance("my_service", my_service)
            ```
        """
        self._services[name] = instance
        self._singletons[name] = True
        logger.debug(f"Registered instance '{name}'")

    def get(self, name: str, default: Any = None) -> Any:
        """Get a service instance.

        Args:
            name: Service name
            default: Default value if service not found

        Returns:
            Service instance or default

        Example:
            ```python
            llm = container.get("llm")
            ```
        """
        # Return existing instance if singleton
        if name in self._services:
            return self._services[name]

        # Create new instance from factory
        if name in self._factories:
            try:
                instance = self._factories[name]()

                # Cache if singleton
                if self._singletons.get(name, True):
                    self._services[name] = instance

                logger.debug(f"Created service '{name}'")
                return instance
            except Exception as e:
                logger.error(f"Failed to create service '{name}': {e}")
                return default

        logger.warning(f"Service '{name}' not found")
        return default

    def get_required(self, name: str) -> Any:
        """Get a required service (raises if not found).

        Args:
            name: Service name

        Returns:
            Service instance

        Raises:
            KeyError: If service not found

        Example:
            ```python
            llm = container.get_required("llm")  # Raises if not registered
            ```
        """
        service = self.get(name)
        if service is None:
            raise KeyError(f"Required service '{name}' not found in container")
        return service

    def has(self, name: str) -> bool:
        """Check if service is registered.

        Args:
            name: Service name

        Returns:
            True if service exists

        Example:
            ```python
            if container.has("tts"):
                tts = container.get("tts")
            ```
        """
        return name in self._services or name in self._factories

    def clear(self, name: Optional[str] = None):
        """Clear service instances (forces recreation).

        Args:
            name: Service name to clear, or None to clear all

        Example:
            ```python
            container.clear("llm")  # Clear specific service
            container.clear()  # Clear all services
            ```
        """
        if name:
            if name in self._services:
                del self._services[name]
                logger.debug(f"Cleared service '{name}'")
        else:
            self._services.clear()
            logger.debug("Cleared all services")

    async def cleanup_all(self):
        """Call cleanup() on all services that support it.

        This should be called when shutting down the application.
        """
        for name, service in self._services.items():
            try:
                if hasattr(service, 'cleanup') and callable(service.cleanup):
                    logger.info(f"Cleaning up service '{name}'")
                    cleanup_method = service.cleanup
                    # Check if cleanup is async
                    if hasattr(cleanup_method, '__call__'):
                        import asyncio
                        import inspect
                        if inspect.iscoroutinefunction(cleanup_method):
                            await cleanup_method()
                        else:
                            cleanup_method()
            except Exception as e:
                logger.error(f"Failed to cleanup service '{name}': {e}")

    def list_services(self) -> Dict[str, Dict[str, Any]]:
        """List all registered services.

        Returns:
            Dictionary mapping service names to metadata

        Example:
            ```python
            services = container.list_services()
            for name, info in services.items():
                print(f"{name}: {info}")
            ```
        """
        result = {}
        for name in set(list(self._factories.keys()) + list(self._services.keys())):
            result[name] = {
                "registered": name in self._factories,
                "instantiated": name in self._services,
                "singleton": self._singletons.get(name, True),
            }
        return result


# ============================================================================
# Global Container Instance
# ============================================================================

# Global container instance (can be imported and used directly)
container = DIContainer()


# ============================================================================
# Helper Functions
# ============================================================================

def create_bot_services_container() -> DIContainer:
    """Create and configure a DI container with all bot services.

    Returns:
        Configured DIContainer instance

    Example:
        ```python
        from utils.di_container import create_bot_services_container

        container = create_bot_services_container()
        llm = container.get("llm")
        tts = container.get("tts")
        ```
    """
    c = DIContainer()

    # LLM Service (Ollama or OpenRouter)
    if Config.LLM_PROVIDER == "openrouter":
        from services.openrouter import OpenRouterService
        c.register("llm", lambda: OpenRouterService(
            api_key=Config.OPENROUTER_API_KEY,
            model=Config.OPENROUTER_MODEL,
            temperature=Config.LLM_TEMPERATURE,
            max_tokens=Config.LLM_MAX_TOKENS,
        ))
    else:  # ollama
        from services.ollama import OllamaService
        c.register("llm", lambda: OllamaService(
            host=Config.OLLAMA_HOST,
            model=Config.OLLAMA_MODEL,
            temperature=Config.LLM_TEMPERATURE,
            max_tokens=Config.LLM_MAX_TOKENS,
        ))

    # TTS Service
    from services.tts import TTSService
    c.register("tts", lambda: TTSService(
        engine=Config.TTS_ENGINE,
        kokoro_api_url=Config.KOKORO_API_URL,
        kokoro_voice=Config.KOKORO_VOICE,
    ))

    # STT Service (Whisper)
    if Config.STT_PROVIDER == "whisper":
        from services.whisper_stt import WhisperSTTService
        c.register("stt", lambda: WhisperSTTService(
            model_size=Config.WHISPER_MODEL_SIZE,
            language="en",
        ))

    # RVC Service (if enabled)
    if Config.RVC_ENABLED:
        from services.clients.rvc_client import RVCHTTPClient
        c.register("rvc", lambda: RVCHTTPClient(
            base_url=Config.RVC_WEBUI_URL,
            default_model=Config.DEFAULT_RVC_MODEL,
        ))

    # Chat History Manager
    from utils.helpers import ChatHistoryManager
    c.register("history", lambda: ChatHistoryManager(Config.DATA_DIR))

    # User Profiles (if enabled)
    if Config.USER_PROFILES_ENABLED:
        from services.user_profiles import UserProfileService
        c.register("user_profiles", lambda: UserProfileService(Config.DATA_DIR))

    # RAG Service (if enabled)
    if Config.RAG_ENABLED:
        from services.rag import RAGService
        c.register("rag", lambda: RAGService(
            knowledge_dir=Config.RAG_KNOWLEDGE_DIR,
            collection_name=Config.RAG_COLLECTION_NAME,
        ))

    # LLM Fallback Manager (if enabled)
    if Config.LLM_FALLBACK_ENABLED and Config.LLM_FALLBACK_MODELS:
        from services.llm_fallback import LLMFallbackManager, ModelConfig
        fallback_models = []
        for i, model_spec in enumerate(Config.LLM_FALLBACK_MODELS.split(',')):
            parts = model_spec.strip().split(':')
            model_name = parts[0].strip()
            cost_tier = parts[1].strip() if len(parts) > 1 else "free"
            max_temp = 1.0 if "amazon/nova" in model_name.lower() else None
            fallback_models.append(ModelConfig(
                name=model_name,
                provider=Config.LLM_PROVIDER,
                max_temp=max_temp,
                cost_tier=cost_tier,
                priority=i
            ))
        c.register("llm_fallback", lambda: LLMFallbackManager(fallback_models))

    logger.info(f"DI Container configured with {len(c.list_services())} services")
    return c
