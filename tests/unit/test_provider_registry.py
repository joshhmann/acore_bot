from __future__ import annotations

import pytest

from providers.registry import canonical_provider_name, provider_names, provider_spec


pytestmark = pytest.mark.unit


def test_provider_registry_contains_required_providers() -> None:
    names = provider_names()
    assert "openai" in names
    assert "openrouter" in names
    assert "ollama" in names


def test_provider_alias_openai_compat_maps_to_openai() -> None:
    assert canonical_provider_name("openai_compat") == "openai"
    spec = provider_spec("openai_compat")
    assert spec is not None
    assert spec.name == "openai"


def test_openrouter_default_model_is_kimi_k25() -> None:
    spec = provider_spec("openrouter")
    assert spec is not None
    assert spec.default_model == "moonshotai/kimi-k2.5"
    assert "moonshotai/kimi-k2.5" in spec.available_models
