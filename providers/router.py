from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any

from services.interfaces.llm_interface import LLMInterface

from .base import (
    LLMProvider,
    LLMResponse,
    LLMStreamChunk,
    ProviderMessage,
    ProviderRequestHints,
)
from .registry import ProviderSpec, canonical_provider_name


@dataclass(slots=True)
class ModeProviderConfig:
    """Configuration for a mode-specific provider."""

    provider: str
    model: str | None = None
    privacy_safe: bool = False
    cost_tier: str = "standard"


@dataclass(slots=True)
class ModeRoutingConfig:
    """Configuration for mode-aware provider routing."""

    providers: dict[str, ModeProviderConfig] = field(default_factory=dict)
    fallbacks: dict[str, list[str]] = field(default_factory=dict)
    privacy_modes: set[str] = field(default_factory=set)

    def get_fallback_chain(self, mode: str) -> list[str]:
        """Get fallback provider chain for a mode."""
        return self.fallbacks.get(mode, [])


@dataclass(slots=True)
class ProviderCostEntry:
    """Cost tracking entry for a mode/provider/model combination."""

    mode: str
    provider: str
    model: str
    tokens_prompt: int = 0
    tokens_completion: int = 0
    request_count: int = 0


@dataclass(slots=True)
class ProviderRouter:
    """Routes provider selection based on persona, mode, and availability."""

    default_provider_name: str
    providers: dict[str, LLMProvider]
    persona_provider_map: dict[str, str]
    provider_specs: dict[str, ProviderSpec] | None = None
    mode_config: ModeRoutingConfig = field(default_factory=ModeRoutingConfig)
    cost_tracking: dict[str, ProviderCostEntry] = field(default_factory=dict)

    def resolve_provider_name(
        self, persona_id: str | None = None, mode: str | None = None
    ) -> str:
        """
        Resolve provider name with priority:
        1. Persona override (highest priority)
        2. Mode-aware selection with fallback
        3. Default provider (lowest priority)
        """
        # 1. Persona override takes highest priority
        if persona_id:
            mapped = self.persona_provider_map.get(persona_id)
            canonical = canonical_provider_name(mapped or "")
            if canonical and canonical in self.providers:
                return canonical

        # 2. Mode-aware selection
        if mode and mode in self.mode_config.providers:
            mode_cfg = self.mode_config.providers[mode]
            canonical = canonical_provider_name(mode_cfg.provider)
            if canonical and canonical in self.providers:
                return canonical
            # Try fallbacks for this mode
            for fallback in self.mode_config.get_fallback_chain(mode):
                canonical = canonical_provider_name(fallback)
                if canonical and canonical in self.providers:
                    return canonical

        # 3. Default fallback
        return self.default_provider_name

    def select_provider(
        self, persona_id: str | None = None, mode: str | None = None
    ) -> LLMProvider:
        """Select provider instance based on persona and mode."""
        return self.providers[self.resolve_provider_name(persona_id, mode)]

    def provider_names(self) -> list[str]:
        """List available provider names."""
        return sorted(self.providers.keys())

    def provider_spec(self, provider_name: str) -> ProviderSpec | None:
        """Get provider specification."""
        if self.provider_specs is None:
            return None
        canonical = canonical_provider_name(provider_name)
        return self.provider_specs.get(canonical)

    def get_mode_config(self, mode: str) -> ModeProviderConfig | None:
        """Get configuration for a specific mode."""
        return self.mode_config.providers.get(mode)

    def is_privacy_mode(self, mode: str) -> bool:
        """Check if mode requires privacy-safe (local) provider."""
        return mode in self.mode_config.privacy_modes

    def record_cost(
        self,
        mode: str,
        provider: str,
        model: str,
        tokens_prompt: int = 0,
        tokens_completion: int = 0,
    ) -> None:
        """Record cost metrics for a request."""
        key = f"{mode}:{provider}:{model}"
        if key not in self.cost_tracking:
            self.cost_tracking[key] = ProviderCostEntry(
                mode=mode, provider=provider, model=model
            )
        entry = self.cost_tracking[key]
        entry.tokens_prompt += tokens_prompt
        entry.tokens_completion += tokens_completion
        entry.request_count += 1

    def get_cost_summary(self, mode: str | None = None) -> dict[str, Any]:
        """Get cost summary, optionally filtered by mode."""
        if mode:
            entries = [e for e in self.cost_tracking.values() if e.mode == mode]
        else:
            entries = list(self.cost_tracking.values())

        return {
            "total_requests": sum(e.request_count for e in entries),
            "total_tokens_prompt": sum(e.tokens_prompt for e in entries),
            "total_tokens_completion": sum(e.tokens_completion for e in entries),
            "by_mode": {
                m: {
                    "requests": sum(e.request_count for e in entries if e.mode == m),
                    "tokens_prompt": sum(
                        e.tokens_prompt for e in entries if e.mode == m
                    ),
                    "tokens_completion": sum(
                        e.tokens_completion for e in entries if e.mode == m
                    ),
                }
                for m in {e.mode for e in entries}
            },
        }

    async def close(self) -> None:
        """Close provider resources when providers expose close hooks."""
        for provider in self.providers.values():
            close_fn = getattr(provider, "close", None)
            if not callable(close_fn):
                continue
            result = close_fn()
            if inspect.isawaitable(result):
                await result

    @classmethod
    def from_env(cls, providers: dict[str, LLMProvider]) -> "ProviderRouter":
        """Create router from environment configuration."""
        import json
        import os

        default_provider = os.getenv("LLM_PROVIDER", "openrouter")

        # Parse MODE_PROVIDERS config
        mode_providers: dict[str, ModeProviderConfig] = {}
        mode_fallbacks: dict[str, list[str]] = {}
        privacy_modes: set[str] = set()

        mode_providers_json = os.getenv("MODE_PROVIDERS", "")
        if mode_providers_json:
            try:
                cfg = json.loads(mode_providers_json)
                for mode, spec in cfg.items():
                    if isinstance(spec, str):
                        # Simple format: "provider/model" or just "provider"
                        parts = spec.split("/", 1)
                        provider = parts[0]
                        model = parts[1] if len(parts) > 1 else None
                        mode_providers[mode] = ModeProviderConfig(
                            provider=provider,
                            model=model,
                        )
                    elif isinstance(spec, dict):
                        mode_providers[mode] = ModeProviderConfig(
                            provider=spec.get("provider", default_provider),
                            model=spec.get("model"),
                            privacy_safe=spec.get("privacy_safe", False),
                            cost_tier=spec.get("cost_tier", "standard"),
                        )
                        if spec.get("fallbacks"):
                            mode_fallbacks[mode] = spec["fallbacks"]
                        if spec.get("privacy_safe"):
                            privacy_modes.add(mode)
            except (json.JSONDecodeError, ValueError):
                pass  # Invalid config, use defaults

        # Default creative/logic modes if not configured
        if "creative" not in mode_providers:
            mode_providers["creative"] = ModeProviderConfig(
                provider="openai",
                model="gpt-4",
            )
        if "logic" not in mode_providers:
            mode_providers["logic"] = ModeProviderConfig(
                provider="anthropic",
                model="claude-3-opus",
            )

        mode_config = ModeRoutingConfig(
            providers=mode_providers,
            fallbacks=mode_fallbacks,
            privacy_modes=privacy_modes,
        )

        return cls(
            default_provider_name=default_provider,
            providers=providers,
            persona_provider_map={},
            provider_specs=None,
            mode_config=mode_config,
        )


class LegacyLLMProvider(LLMProvider):
    def __init__(self, llm: LLMInterface) -> None:
        self.llm = llm

    async def chat(
        self,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        request_hints: ProviderRequestHints | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        del tools, stream, request_hints, kwargs
        payload = [{"role": m.role, "content": m.content} for m in messages]
        content = await self.llm.chat(messages=payload)
        return LLMResponse(content=content)

    async def stream_chat(
        self,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None = None,
        request_hints: ProviderRequestHints | None = None,
        **kwargs: Any,
    ):
        response = await self.chat(
            messages=messages,
            tools=tools,
            stream=True,
            request_hints=request_hints,
            **kwargs,
        )
        if response.content:
            yield LLMStreamChunk(kind="text_delta", text=response.content)
        yield LLMStreamChunk(kind="response", response=response, raw=dict(response.raw))
