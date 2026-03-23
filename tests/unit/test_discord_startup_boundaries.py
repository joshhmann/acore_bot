from __future__ import annotations

from pathlib import Path

import pytest

import main


pytestmark = pytest.mark.unit


def test_discord_rl_commands_are_not_loaded_when_rl_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main.Config, "RL_ENABLED", False)

    assert main.OllamaBot._should_load_rl_commands() is False


def test_discord_rl_commands_remain_opt_in_when_rl_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main.Config, "RL_ENABLED", True)

    assert main.OllamaBot._should_load_rl_commands() is True


def test_discord_conversation_commands_are_not_loaded_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main.Config, "BOT_CONVERSATION_ENABLED", False)

    assert main.OllamaBot._should_load_conversation_commands() is False


def test_discord_conversation_commands_remain_opt_in_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main.Config, "BOT_CONVERSATION_ENABLED", True)

    assert main.OllamaBot._should_load_conversation_commands() is True


def test_discord_voice_cog_is_not_loaded_when_voice_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = object.__new__(main.OllamaBot)
    bot.tts = object()
    monkeypatch.setattr(main.Config, "DISCORD_VOICE_ENABLED", False)

    assert bot._should_load_voice_cog() is False


def test_discord_voice_cog_requires_tts_even_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = object.__new__(main.OllamaBot)
    bot.tts = None
    monkeypatch.setattr(main.Config, "DISCORD_VOICE_ENABLED", True)

    assert bot._should_load_voice_cog() is False


def test_discord_voice_cog_remains_opt_in_when_enabled_with_tts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = object.__new__(main.OllamaBot)
    bot.tts = object()
    monkeypatch.setattr(main.Config, "DISCORD_VOICE_ENABLED", True)

    assert bot._should_load_voice_cog() is True


def test_discord_legacy_flags_remain_default_false_in_config_source() -> None:
    text = Path("config/discord.py").read_text(encoding="utf-8")

    expected = (
        "DISCORD_LEGACY_OPERATOR_ENABLED",
        "DISCORD_LEGACY_PERSONA_ADMIN_ENABLED",
        "DISCORD_LEGACY_CHAT_AMBIENT_ENABLED",
        "DISCORD_LEGACY_CHAT_SESSION_ENABLED",
        "DISCORD_LEGACY_CHAT_FALLBACK_ENABLED",
        "DISCORD_LEGACY_SOCIAL_MODE_FOOTER_ENABLED",
        "DISCORD_LEGACY_SOCIAL_INSIGHTS_ENABLED",
    )

    for flag in expected:
        assert f'"{flag}", False' in text
