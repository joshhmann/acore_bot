from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ProviderSpec:
    name: str
    auth_required: bool
    streaming_supported: bool
    default_base_url: str
    default_model: str
    available_models: list[str]
    aliases: tuple[str, ...] = ()


PROVIDER_SPECS: dict[str, ProviderSpec] = {
    "openai": ProviderSpec(
        name="openai",
        auth_required=True,
        streaming_supported=True,
        default_base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        available_models=["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"],
        aliases=("openai_compat",),
    ),
    "openrouter": ProviderSpec(
        name="openrouter",
        auth_required=True,
        streaming_supported=True,
        default_base_url="https://openrouter.ai/api/v1",
        default_model="moonshotai/kimi-k2.5",
        available_models=[
            "moonshotai/kimi-k2.5",
            "openai/gpt-4o-mini",
            "anthropic/claude-3.5-sonnet",
            "google/gemini-2.0-flash-001",
        ],
        aliases=(),
    ),
    "ollama": ProviderSpec(
        name="ollama",
        auth_required=False,
        streaming_supported=True,
        default_base_url="http://localhost:11434/v1",
        default_model="llama3.2",
        available_models=["llama3.2", "qwen2.5", "deepseek-r1"],
        aliases=(),
    ),
}


def canonical_provider_name(name: str) -> str:
    probe = name.strip().lower()
    if not probe:
        return ""
    for canonical, spec in PROVIDER_SPECS.items():
        if probe == canonical or probe in spec.aliases:
            return canonical
    return probe


def provider_spec(name: str) -> ProviderSpec | None:
    canonical = canonical_provider_name(name)
    return PROVIDER_SPECS.get(canonical)


def provider_names() -> list[str]:
    return sorted(PROVIDER_SPECS.keys())
