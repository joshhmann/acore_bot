from __future__ import annotations

import os
import stat

import pytest

from core.auth import AuthStore, default_auth_path


pytestmark = pytest.mark.unit


def test_auth_store_round_trip(tmp_path) -> None:
    store = AuthStore(path=tmp_path / "auth.json")
    store.upsert_provider(
        "openai_compat",
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
    )

    assert store.get_token("openai_compat") == "test-key"
    assert store.list_providers() == ["openai"]
    config = store.get_provider_config("openai_compat")
    assert config["base_url"] == "https://api.openai.com/v1"
    assert config["model"] == "gpt-4o-mini"


def test_auth_store_logout(tmp_path) -> None:
    store = AuthStore(path=tmp_path / "auth.json")
    store.set_token("openai_compat", "test-token")

    assert store.remove_provider("openai_compat") is True
    assert store.get_token("openai_compat") == ""


def test_auth_store_file_mode_0600(tmp_path) -> None:
    store = AuthStore(path=tmp_path / "auth.json")
    store.set_token("openai_compat", "test-token")
    if os.name == "nt":
        return
    mode = stat.S_IMODE(os.stat(store.path).st_mode)
    assert mode == 0o600


def test_auth_store_does_not_leak_tokens_in_list(tmp_path) -> None:
    store = AuthStore(path=tmp_path / "auth.json")
    store.set_token("openai_compat", "super-secret")
    listed = store.list_providers()
    assert "super-secret" not in " ".join(listed)


def test_auth_store_long_summary_redacts_secrets(tmp_path) -> None:
    store = AuthStore(path=tmp_path / "auth.json")
    store.upsert_provider(
        "openrouter",
        token="sk-secret",
        base_url="https://openrouter.ai/api/v1",
        model="openai/gpt-4o-mini",
    )
    summaries = store.list_provider_summaries()
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary["provider"] == "openrouter"
    assert summary["has_token"] is True
    assert "sk-secret" not in str(summary)


def test_default_auth_path_prefers_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/gestalt-config")
    path = default_auth_path()
    assert str(path).endswith("/tmp/gestalt-config/gestalt/auth.json")
