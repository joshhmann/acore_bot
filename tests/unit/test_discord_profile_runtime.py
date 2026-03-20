"""Unit tests for Discord profile commands runtime-only routing.

Tests verify that:
1. /status command routes through GestaltRuntime (runtime-only)
2. Direct ollama calls are NOT present in source
3. Runtime=None returns error message
4. Event structure is correct for status command
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock, AsyncMock

pytestmark = pytest.mark.unit


class TestProfileCommandsRuntimeOnly:
    """Test that profile commands are runtime-only (no legacy fallback)."""

    @pytest.mark.asyncio
    async def test_status_command_requires_runtime(self, mock_interaction):
        """Verify /status returns error when runtime is None."""
        from adapters.discord.commands.profile import ProfileCommandsCog

        # Setup mocks without runtime
        mock_bot = Mock()
        mock_bot.user.name = "TestBot"
        mock_user_profiles = AsyncMock()

        # Create cog WITHOUT runtime
        cog = ProfileCommandsCog(
            bot=mock_bot,
            user_profiles=mock_user_profiles,
            gestalt_runtime=None,
        )

        # Execute status command
        await cog.status.callback(cog, mock_interaction)

        # Verify error message was sent
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        assert "Runtime not available" in call_args[0][
            0
        ] or "Runtime not available" in str(call_args[1].get("content", ""))

    @pytest.mark.asyncio
    async def test_status_command_uses_runtime_when_available(self, mock_interaction):
        """Verify /status routes through gestalt_runtime.handle_event()."""
        from adapters.discord.commands.profile import ProfileCommandsCog
        from core.schemas import Response

        # Setup mocks
        mock_bot = Mock()
        mock_bot.user.name = "TestBot"
        mock_user_profiles = AsyncMock()
        mock_runtime = AsyncMock()
        mock_runtime.handle_event = AsyncMock(
            return_value=Response(
                text="Status: OK", persona_id="test", metadata={"outputs": []}
            )
        )

        # Create cog with runtime (no ollama parameter)
        cog = ProfileCommandsCog(
            bot=mock_bot,
            user_profiles=mock_user_profiles,
            gestalt_runtime=mock_runtime,
        )

        # Execute status command
        await cog.status.callback(cog, mock_interaction)

        # Verify runtime was called
        assert mock_runtime.handle_event.called, "Runtime handle_event should be called"

        # Verify the runtime was called with correct event structure
        call_args = mock_runtime.handle_event.call_args
        event = call_args[0][0]
        assert event.type == "command"
        assert event.metadata["command"] == "status"


class TestProfileCommandsEventStructure:
    """Test that profile commands create proper Event structures."""

    @pytest.mark.asyncio
    async def test_status_command_event_metadata(self, mock_interaction):
        """Verify /status creates Event with correct metadata."""
        from adapters.discord.commands.profile import ProfileCommandsCog
        from core.schemas import Response

        mock_bot = Mock()
        mock_bot.user.name = "TestBot"
        mock_user_profiles = AsyncMock()
        mock_runtime = AsyncMock()
        mock_runtime.handle_event = AsyncMock(
            return_value=Response(
                text="Status: OK", persona_id="test", metadata={"outputs": []}
            )
        )

        cog = ProfileCommandsCog(
            bot=mock_bot,
            user_profiles=mock_user_profiles,
            gestalt_runtime=mock_runtime,
        )

        await cog.status.callback(cog, mock_interaction)

        event = mock_runtime.handle_event.call_args[0][0]

        # Verify event structure
        assert event.type == "command"
        assert event.kind == "command"
        assert event.metadata["command"] == "status"
        assert event.metadata["user_id"] == str(mock_interaction.user.id)
        assert event.metadata["channel_id"] == str(mock_interaction.channel_id)
        assert event.metadata["guild_id"] == str(mock_interaction.guild_id)


class TestProfileCommandsSetup:
    """Test that setup() properly passes gestalt_runtime from ChatCog."""

    @pytest.mark.asyncio
    async def test_setup_passes_runtime_from_chat_cog(self):
        """Verify setup() extracts gestalt_runtime from ChatCog."""
        from adapters.discord.commands.profile import setup, ProfileCommandsCog

        # Create mock bot with ChatCog that has gestalt_runtime
        mock_bot = Mock()
        mock_chat_cog = Mock()
        mock_chat_cog.user_profiles = AsyncMock()
        mock_chat_cog.gestalt_runtime = AsyncMock()

        mock_bot.get_cog.return_value = mock_chat_cog

        # Patch add_cog to capture the cog instance
        added_cog = None

        async def capture_add_cog(cog):
            nonlocal added_cog
            added_cog = cog

        mock_bot.add_cog = capture_add_cog

        # Run setup
        await setup(mock_bot)

        # Verify cog was created with runtime
        assert added_cog is not None
        assert added_cog.gestalt_runtime is mock_chat_cog.gestalt_runtime


class TestNoLegacyFallbackPath:
    """Verify no legacy fallback code remains in profile.py."""

    def test_no_ollama_parameter_in_init(self):
        """Verify __init__ does not accept ollama parameter."""
        import inspect
        from adapters.discord.commands.profile import ProfileCommandsCog

        sig = inspect.signature(ProfileCommandsCog.__init__)
        params = list(sig.parameters.keys())

        assert "ollama" not in params, (
            "ollama parameter should be removed from __init__"
        )
        assert "gestalt_runtime" in params, "gestalt_runtime parameter should exist"

    def test_no_ollama_check_health_in_source(self):
        """Verify no direct ollama.check_health() calls in source."""
        import inspect
        from adapters.discord.commands.profile import ProfileCommandsCog

        source = inspect.getsource(ProfileCommandsCog)

        assert "ollama.check_health" not in source, (
            "ollama.check_health should not be in source"
        )
        assert "self.ollama" not in source, "self.ollama references should be removed"

    def test_runtime_none_check_returns_error(self):
        """Verify status command checks for runtime None and returns error."""
        import inspect
        from adapters.discord.commands.profile import ProfileCommandsCog

        source = inspect.getsource(ProfileCommandsCog.status.callback)

        assert "if self.gestalt_runtime is None:" in source
        assert "Runtime not available" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
