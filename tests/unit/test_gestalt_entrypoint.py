from __future__ import annotations

import pytest

from gestalt import cli_entry


pytestmark = pytest.mark.unit


class _FakeStdin:
    def __init__(self, tty: bool) -> None:
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def test_default_tty_dispatches_to_tui(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, bool] = {"tui": False}

    def _fake_tui(args):
        del args
        called["tui"] = True
        return 0

    monkeypatch.setattr(cli_entry.sys, "stdin", _FakeStdin(True))
    monkeypatch.setattr(cli_entry, "_run_tui", _fake_tui)

    code = cli_entry._dispatch([])
    assert code == 0
    assert called["tui"] is True


def test_non_tty_dispatches_to_cli_non_interactive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def _fake_cli(argv):
        calls.append(list(argv or []))
        return 0

    monkeypatch.setattr(cli_entry.sys, "stdin", _FakeStdin(False))
    monkeypatch.setattr(cli_entry.cli_main, "cli", _fake_cli)

    code = cli_entry._dispatch([])
    assert code == 0
    assert calls
    assert "--no-interactive" in calls[0]


def test_auth_login_list_logout(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    class _Store:
        def __init__(self):
            self.tokens: dict[str, str] = {}
            self.base_urls: dict[str, str] = {}
            self.models: dict[str, str] = {}

        def upsert_provider(
            self,
            provider: str,
            token: str = "",
            api_key: str = "",
            base_url: str = "",
            model: str = "",
        ) -> None:
            if token:
                self.tokens[provider] = token
            if api_key:
                self.tokens[provider] = api_key
            if base_url:
                self.base_urls[provider] = base_url
            if model:
                self.models[provider] = model

        def list_providers(self) -> list[str]:
            keys = (
                set(self.tokens.keys())
                | set(self.base_urls.keys())
                | set(self.models.keys())
            )
            return sorted(keys)

        def list_provider_summaries(self) -> list[dict[str, object]]:
            out: list[dict[str, object]] = []
            for provider in self.list_providers():
                out.append(
                    {
                        "provider": provider,
                        "base_url": self.base_urls.get(provider, ""),
                        "model": self.models.get(provider, ""),
                        "has_api_key": provider in self.tokens,
                        "has_token": provider in self.tokens,
                    }
                )
            return out

        def get_last_used_provider(self) -> str:
            return ""

        def remove_provider(self, provider: str) -> bool:
            return self.tokens.pop(provider, None) is not None

    store = _Store()
    monkeypatch.setattr(cli_entry, "AuthStore", lambda: store)

    assert (
        cli_entry._dispatch(
            [
                "auth",
                "login",
                "openai",
                "--api-key",
                "super-secret-abcd",
                "--base-url",
                "https://api.openai.com/v1",
                "--model",
                "gpt-4o-mini",
            ]
        )
        == 0
    )
    assert cli_entry._dispatch(["auth", "list"]) == 0
    out = capsys.readouterr().out
    assert "openai" in out
    assert "super-secret-abcd" not in out
    assert "****" in out

    assert cli_entry._dispatch(["auth", "logout", "openai"]) == 0
    out = capsys.readouterr().out
    assert "removed openai" in out


def test_auth_list_long_shows_metadata_without_secret(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    class _Store:
        def list_provider_summaries(self):
            return [
                {
                    "provider": "openrouter",
                    "base_url": "https://openrouter.ai/api/v1",
                    "model": "openai/gpt-4o-mini",
                    "has_api_key": True,
                    "has_token": False,
                }
            ]

    monkeypatch.setattr(cli_entry, "AuthStore", lambda: _Store())
    assert cli_entry._dispatch(["auth", "list", "--long"]) == 0
    out = capsys.readouterr().out
    assert "openrouter" in out
    assert "base_url=https://openrouter.ai/api/v1" in out
    assert "secret=yes" in out


def test_runtime_stdio_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"run": False}

    async def _fake_stdio() -> int:
        called["run"] = True
        return 0

    monkeypatch.setattr(
        "gestalt.runtime_stdio.run_stdio_server",
        _fake_stdio,
    )
    code = cli_entry._dispatch(["runtime", "--stdio"])
    assert code == 0
    assert called["run"] is True


def test_auth_login_without_provider_uses_selector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Store:
        def __init__(self):
            self.saved: dict[str, str] = {}

        def upsert_provider(
            self,
            provider: str,
            token: str = "",
            api_key: str = "",
            base_url: str = "",
            model: str = "",
        ) -> None:
            del token, base_url, model
            self.saved[provider] = api_key

        def remove_provider(self, provider: str) -> bool:
            return self.saved.pop(provider, None) is not None

        def list_providers(self) -> list[str]:
            return sorted(self.saved.keys())

        def list_provider_summaries(self) -> list[dict[str, object]]:
            return []

        def get_last_used_provider(self) -> str:
            return ""

    store = _Store()
    monkeypatch.setattr(cli_entry, "AuthStore", lambda: store)
    monkeypatch.setattr(cli_entry, "_auth_interactive_enabled", lambda _args: True)
    monkeypatch.setattr(
        cli_entry,
        "_select_provider_interactive",
        lambda *args, **kwargs: "openrouter",
    )
    monkeypatch.setattr(cli_entry, "_prompt_with_default", lambda _l, d: d)
    monkeypatch.setattr(cli_entry, "_prompt_model", lambda _m, d: d)

    code = cli_entry._dispatch(["auth", "login", "--api-key", "super-secret-abcd"])
    assert code == 0
    assert store.saved["openrouter"] == "super-secret-abcd"


def test_auth_login_non_interactive_without_provider_errors(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setattr(cli_entry, "_auth_interactive_enabled", lambda _args: False)
    code = cli_entry._dispatch(["auth", "login"])
    assert code == 2
    out = capsys.readouterr().out
    assert "Non-interactive auth login requires provider" in out


def test_auth_login_output_redacts_secret(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    class _Store:
        def upsert_provider(
            self,
            provider: str,
            token: str = "",
            api_key: str = "",
            base_url: str = "",
            model: str = "",
        ) -> None:
            del provider, token, api_key, base_url, model

        def list_providers(self) -> list[str]:
            return []

        def list_provider_summaries(self) -> list[dict[str, object]]:
            return []

        def remove_provider(self, provider: str) -> bool:
            del provider
            return False

        def get_last_used_provider(self) -> str:
            return ""

    monkeypatch.setattr(cli_entry, "AuthStore", lambda: _Store())
    monkeypatch.setattr(cli_entry, "_auth_interactive_enabled", lambda _args: False)
    code = cli_entry._dispatch(
        ["auth", "login", "openrouter", "--api-key", "super-secret-abcd"]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "super-secret-abcd" not in out
    assert "****abcd" in out


def test_openrouter_login_skips_model_and_base_url_prompts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Store:
        def upsert_provider(
            self,
            provider: str,
            token: str = "",
            api_key: str = "",
            base_url: str = "",
            model: str = "",
        ) -> None:
            assert provider == "openrouter"
            assert api_key == "super-secret-abcd"
            assert base_url == ""
            assert model == ""
            del token

        def list_providers(self) -> list[str]:
            return []

        def list_provider_summaries(self) -> list[dict[str, object]]:
            return []

        def remove_provider(self, provider: str) -> bool:
            del provider
            return False

        def get_last_used_provider(self) -> str:
            return "openrouter"

    monkeypatch.setattr(cli_entry, "AuthStore", lambda: _Store())
    monkeypatch.setattr(cli_entry, "_auth_interactive_enabled", lambda _args: True)

    def _no_prompt(*args, **kwargs):
        raise AssertionError("OpenRouter login should not prompt for base_url/model")

    monkeypatch.setattr(cli_entry, "_prompt_with_default", _no_prompt)
    monkeypatch.setattr(cli_entry, "_prompt_model", _no_prompt)

    code = cli_entry._dispatch(
        ["auth", "login", "openrouter", "--api-key", "super-secret-abcd"]
    )
    assert code == 0
