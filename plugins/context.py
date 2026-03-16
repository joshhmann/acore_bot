from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from memory.manager import MemoryManager
from providers.router import ProviderRouter
from tools.policy import ToolPolicy
from tools.registry import ToolHandler, ToolRegistry


def _env_truthy(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class PluginConfig:
    def __getitem__(self, key: str) -> str:
        return os.environ[key]

    def get(self, key: str, default: Any = None) -> Any:
        return os.getenv(key, default)

    def env_bool(self, key: str, default: bool = False) -> bool:
        return _env_truthy(key, default)

    def env_int(self, key: str, default: int = 0) -> int:
        raw = os.getenv(key)
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError:
            return default


class ToolPluginRegistry:
    def __init__(
        self,
        registry: ToolRegistry,
        policy: ToolPolicy,
        allowlists_by_env: dict[str, set[str]],
    ) -> None:
        self._registry = registry
        self._policy = policy
        self._allowlists = allowlists_by_env
        self._sources: list[Any] = []

    def register_tool(
        self,
        name: str,
        schema: dict[str, Any],
        handler: ToolHandler,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._registry.register_tool(
            name=name, schema=schema, handler=handler, metadata=metadata
        )

    def set_risk_tier(self, tool_name: str, tier: str) -> None:
        self._policy.tool_risk_tiers[tool_name] = tier

    def allow_in_environment(self, environment: str, tool_name: str) -> None:
        self._allowlists.setdefault(environment, set()).add(tool_name)

    def register_tool_source(self, source: Any) -> None:
        self._sources.append(source)

    async def activate_tool_sources(self) -> list[str]:
        loaded: list[str] = []
        for source in self._sources:
            registered = await source.register(
                registry=self._registry,
                policy=self._policy,
                allowlists_by_env=self._allowlists,
            )
            if isinstance(registered, list):
                loaded.extend(str(item) for item in registered)
        return loaded


class ProviderPluginRegistry:
    def __init__(self, provider_router: ProviderRouter) -> None:
        self._router = provider_router

    def register_provider(
        self, name: str, provider: Any, default: bool = False
    ) -> None:
        self._router.providers[name] = provider
        if default:
            self._router.default_provider_name = name

    def map_persona_provider(self, persona_id: str, provider_name: str) -> None:
        self._router.persona_provider_map[persona_id] = provider_name


class MemoryPluginRegistry:
    def __init__(self, memory_manager: MemoryManager) -> None:
        self._memory_manager = memory_manager
        self._backends: dict[str, Any] = {}

    def register_backend(self, name: str, backend: Any) -> None:
        self._backends[name] = backend

    def get_backend(self, name: str) -> Any:
        return self._backends.get(name)


@dataclass(slots=True)
class PluginContext:
    tools: ToolPluginRegistry
    providers: ProviderPluginRegistry
    memory: MemoryPluginRegistry
    config: PluginConfig
    logger: Any
