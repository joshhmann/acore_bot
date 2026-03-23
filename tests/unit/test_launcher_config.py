from __future__ import annotations

import os

import pytest

from gestalt import cli_entry
from gestalt.env import detect_environment_profile
from launcher import (
    MODEL_PRESETS,
    _apply_env_profile,
    _apply_llm_overrides,
    _build_parser,
    _resolve_launch_config,
)


pytestmark = pytest.mark.unit


def _parse_args(argv: list[str]):
    return _build_parser().parse_args(argv)


def test_cli_profile_enables_only_cli() -> None:
    args = _parse_args(["--profile", "cli"])
    config = _resolve_launch_config(args)

    assert config.cli_enabled is True
    assert config.discord_enabled is False
    assert config.web_enabled is False


def test_flags_override_profile() -> None:
    args = _parse_args(["--profile", "cli", "--web", "--no-cli"])
    config = _resolve_launch_config(args)

    assert config.discord_enabled is False
    assert config.cli_enabled is False
    assert config.web_enabled is True


def test_no_adapters_enabled_raises() -> None:
    args = _parse_args(["--profile", "all", "--no-discord", "--no-cli", "--no-web"])

    with pytest.raises(ValueError, match="No adapters enabled"):
        _resolve_launch_config(args)


def test_apply_openrouter_model_preset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_COMPAT_MODEL", raising=False)

    args = _parse_args(["--model-preset", "claude"])
    _apply_llm_overrides(args)

    expected = MODEL_PRESETS["claude"]
    assert os.environ["OPENROUTER_MODEL"] == expected
    assert os.environ["OPENAI_COMPAT_MODEL"] == expected


def test_apply_ollama_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_COMPAT_MODEL", raising=False)

    args = _parse_args(["--model", "llama3.2"])
    _apply_llm_overrides(args)

    assert os.environ["OLLAMA_MODEL"] == "llama3.2"
    assert os.environ["OPENAI_COMPAT_MODEL"] == "llama3.2"


def test_provider_flag_sets_llm_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    args = _parse_args(["--provider", "openrouter"])
    _apply_llm_overrides(args)

    assert os.environ["LLM_PROVIDER"] == "openrouter"


def test_env_profile_flag_is_captured_and_applied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[str] = []

    monkeypatch.setattr(
        "launcher.load_environment_profile",
        lambda profile="": captured.append(profile) or [],
    )

    args = _parse_args(["--env-profile", "web"])
    config = _resolve_launch_config(args)
    _apply_env_profile(config.env_profile)

    assert config.env_profile == "web"
    assert captured == ["web"]


def test_detect_environment_profile_from_argv() -> None:
    assert detect_environment_profile(["--env-profile", "web"]) == "web"
    assert detect_environment_profile(["--env-profile=cli"]) == "cli"


def test_gestalt_cli_entry_applies_env_profile_before_cli_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[str, object]] = []

    class _FakeCliMain:
        @staticmethod
        def cli(argv):
            captured.append(("cli", list(argv)))
            return 0

    monkeypatch.setattr(
        cli_entry,
        "load_environment_profile",
        lambda profile="": captured.append(("env", profile)) or [],
    )
    monkeypatch.setattr(cli_entry, "_load_cli_main", lambda: _FakeCliMain)

    result = cli_entry._dispatch(["--env-profile", "web", "cli"])

    assert result == 0
    assert captured[0] == ("env", "web")
