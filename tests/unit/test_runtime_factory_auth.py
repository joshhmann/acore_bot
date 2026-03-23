from __future__ import annotations

import pytest

from adapters import runtime_factory
from providers.openai_compat import OpenAICompatProvider


pytestmark = pytest.mark.unit


def _fake_auth_store(profile: dict[str, dict[str, str]]):
    class _Store:
        def get_provider_config(self, provider: str):
            return dict(profile.get(provider, {}))

    return _Store()


def test_runtime_factory_uses_openrouter_auth_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GESTALT_PLUGINS_ENABLED", "false")
    monkeypatch.delenv("OPENAI_COMPAT_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_COMPAT_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_COMPAT_MODEL", raising=False)
    monkeypatch.setattr(runtime_factory.Config, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(
        runtime_factory,
        "AuthStore",
        lambda: _fake_auth_store(
            {
                "openrouter": {
                    "api_key": "or-key",
                    "base_url": "https://openrouter.ai/api/v1",
                    "model": "openai/gpt-4o-mini",
                }
            }
        ),
    )

    runtime = runtime_factory.build_gestalt_runtime(legacy_llm=None)
    provider = runtime.provider_router.providers["openrouter"]
    assert isinstance(provider, OpenAICompatProvider)
    assert provider.api_key == "or-key"
    assert provider.base_url == "https://openrouter.ai/api/v1"
    assert provider.model == "openai/gpt-4o-mini"


def test_runtime_factory_env_overrides_auth_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GESTALT_PLUGINS_ENABLED", "false")
    monkeypatch.setenv("OPENAI_COMPAT_BASE_URL", "https://env.example/v1")
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_COMPAT_MODEL", "env-model")
    monkeypatch.setattr(runtime_factory.Config, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(
        runtime_factory,
        "AuthStore",
        lambda: _fake_auth_store(
            {
                "openai": {
                    "api_key": "stored-key",
                    "base_url": "https://stored.example/v1",
                    "model": "stored-model",
                }
            }
        ),
    )

    runtime = runtime_factory.build_gestalt_runtime(legacy_llm=None)
    provider = runtime.provider_router.providers["openai"]
    assert isinstance(provider, OpenAICompatProvider)
    assert provider.api_key == "env-key"
    assert provider.base_url == "https://env.example/v1"
    assert provider.model == "env-model"
