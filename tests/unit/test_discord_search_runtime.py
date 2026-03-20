"""Unit tests for Discord search commands runtime routing (runtime-only).

Tests verify that:
1. /ask command routes through GestaltRuntime when available
2. /search command routes through GestaltRuntime when available
3. Commands return error when runtime is not available (runtime-only)
4. No direct ollama calls are made (legacy removed)
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock, AsyncMock

pytestmark = pytest.mark.unit


class TestSearchCommandsRuntimeRouting:
    """Test that search commands route through runtime only."""

    @pytest.mark.asyncio
    async def test_ask_command_uses_runtime_when_available(self, mock_interaction):
        """Verify /ask routes through gestalt_runtime.handle_event()."""
        from adapters.discord.commands.search import SearchCommandsCog
        from core.schemas import Response

        # Setup mocks
        mock_bot = Mock()
        mock_web_search = Mock()
        mock_runtime = AsyncMock()
        mock_runtime.handle_event = AsyncMock(
            return_value=Response(text="Runtime-generated answer", persona_id="test")
        )

        # Create cog with runtime
        cog = SearchCommandsCog(
            bot=mock_bot,
            web_search=mock_web_search,
            system_prompt="Test system prompt",
            gestalt_runtime=mock_runtime,
        )

        # Execute ask command
        question = "What is the meaning of life?"
        await cog.ask.callback(cog, mock_interaction, question)

        # Verify runtime was called
        assert mock_runtime.handle_event.called, "Runtime handle_event should be called"

        # Verify the runtime was called with correct event structure
        call_args = mock_runtime.handle_event.call_args
        event = call_args[0][0]
        assert event.type == "command"
        assert event.metadata["command"] == "ask"
        assert event.metadata["question"] == question

    @pytest.mark.asyncio
    async def test_ask_command_returns_error_when_runtime_none(self, mock_interaction):
        """Verify /ask returns error when runtime is None (runtime-only)."""
        from adapters.discord.commands.search import SearchCommandsCog

        # Setup mocks without runtime
        mock_bot = Mock()
        mock_web_search = Mock()

        # Create cog WITHOUT runtime (should error)
        cog = SearchCommandsCog(
            bot=mock_bot,
            web_search=mock_web_search,
            system_prompt="Test system prompt",
            gestalt_runtime=None,
        )

        # Execute ask command
        question = "What is the weather?"
        await cog.ask.callback(cog, mock_interaction, question)

        # Verify error message was sent
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        assert "Runtime not available" in call_args[0][
            0
        ] or "Runtime not available" in call_args[1].get("text", "")

    @pytest.mark.asyncio
    async def test_search_command_uses_runtime_when_available(self, mock_interaction):
        """Verify /search routes through gestalt_runtime.handle_event()."""
        from adapters.discord.commands.search import SearchCommandsCog
        from core.schemas import Response

        # Setup mocks
        mock_bot = Mock()
        mock_web_search = AsyncMock()
        mock_web_search.get_context = AsyncMock(
            return_value="Search results: Test result 1, Test result 2"
        )
        mock_runtime = AsyncMock()
        mock_runtime.handle_event = AsyncMock(
            return_value=Response(text="Search-based answer", persona_id="test")
        )

        # Create cog with runtime
        cog = SearchCommandsCog(
            bot=mock_bot,
            web_search=mock_web_search,
            system_prompt="Test system prompt",
            gestalt_runtime=mock_runtime,
        )

        # Execute search command
        query = "latest python version"
        await cog.search.callback(cog, mock_interaction, query)

        # Verify runtime was called
        assert mock_runtime.handle_event.called, "Runtime handle_event should be called"

        # Verify the runtime was called with correct event structure
        call_args = mock_runtime.handle_event.call_args
        event = call_args[0][0]
        assert event.type == "command"
        assert event.metadata["command"] == "search"
        assert event.metadata["query"] == query
        assert "search_context" in event.metadata

    @pytest.mark.asyncio
    async def test_search_command_returns_error_when_runtime_none(
        self, mock_interaction
    ):
        """Verify /search returns error when runtime is None (runtime-only)."""
        from adapters.discord.commands.search import SearchCommandsCog

        # Setup mocks without runtime
        mock_bot = Mock()
        mock_web_search = AsyncMock()
        mock_web_search.get_context = AsyncMock(return_value="Search results found")

        # Create cog WITHOUT runtime (should error)
        cog = SearchCommandsCog(
            bot=mock_bot,
            web_search=mock_web_search,
            system_prompt="Test system prompt",
            gestalt_runtime=None,
        )

        # Execute search command
        query = "latest news"
        await cog.search.callback(cog, mock_interaction, query)

        # Verify error message was sent (before search context would be processed)
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        assert "Runtime not available" in call_args[0][
            0
        ] or "Runtime not available" in call_args[1].get("text", "")


class TestSearchCommandsEventStructure:
    """Test that search commands create proper Event structures."""

    @pytest.mark.asyncio
    async def test_ask_command_event_metadata(self, mock_interaction):
        """Verify /ask creates Event with correct metadata."""
        from adapters.discord.commands.search import SearchCommandsCog
        from core.schemas import Response

        mock_bot = Mock()
        mock_web_search = Mock()
        mock_runtime = AsyncMock()
        mock_runtime.handle_event = AsyncMock(
            return_value=Response(text="Answer", persona_id="test")
        )

        cog = SearchCommandsCog(
            bot=mock_bot,
            web_search=mock_web_search,
            system_prompt="Test prompt",
            gestalt_runtime=mock_runtime,
        )

        question = "Test question?"
        await cog.ask.callback(cog, mock_interaction, question)

        event = mock_runtime.handle_event.call_args[0][0]

        # Verify event structure
        assert event.type == "command"
        assert event.kind == "command"
        assert event.metadata["command"] == "ask"
        assert event.metadata["question"] == question
        # Note: system_prompt comes from ChatCog mock, not the cog's system_prompt
        assert "system_prompt" in event.metadata
        assert event.metadata["user_id"] == str(mock_interaction.user.id)
        # search.py stores interaction.channel_id directly, not interaction.channel.id
        assert event.metadata["channel_id"] == str(mock_interaction.channel_id)

    @pytest.mark.asyncio
    async def test_search_command_event_metadata(self, mock_interaction):
        """Verify /search creates Event with correct metadata including search context."""
        from adapters.discord.commands.search import SearchCommandsCog
        from core.schemas import Response

        mock_bot = Mock()
        mock_web_search = AsyncMock()
        search_context = "Web results: Python 3.12 released"
        mock_web_search.get_context = AsyncMock(return_value=search_context)
        mock_runtime = AsyncMock()
        mock_runtime.handle_event = AsyncMock(
            return_value=Response(text="Search answer", persona_id="test")
        )

        cog = SearchCommandsCog(
            bot=mock_bot,
            web_search=mock_web_search,
            system_prompt="Test prompt",
            gestalt_runtime=mock_runtime,
        )

        query = "python 3.12"
        await cog.search.callback(cog, mock_interaction, query)

        event = mock_runtime.handle_event.call_args[0][0]

        # Verify event structure
        assert event.type == "command"
        assert event.kind == "command"
        assert event.metadata["command"] == "search"
        assert event.metadata["query"] == query
        assert event.metadata["search_context"] == search_context
        assert "prompt" in event.metadata
        assert event.metadata["user_id"] == str(mock_interaction.user.id)


class TestSearchCommandsSetup:
    """Test that setup() properly passes gestalt_runtime from ChatCog."""

    @pytest.mark.asyncio
    async def test_setup_passes_runtime_from_chat_cog(self):
        """Verify setup() extracts gestalt_runtime from ChatCog."""
        from adapters.discord.commands.search import setup, SearchCommandsCog

        # Create mock bot with ChatCog that has gestalt_runtime
        mock_bot = Mock()
        mock_chat_cog = Mock()
        mock_chat_cog.web_search = Mock()
        mock_chat_cog.system_prompt = "Test prompt"
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

    @pytest.mark.asyncio
    async def test_setup_handles_missing_runtime_gracefully(self):
        """Verify setup() works even if ChatCog doesn't have gestalt_runtime."""
        from adapters.discord.commands.search import setup

        # Create mock bot with ChatCog WITHOUT gestalt_runtime
        # Use spec to prevent auto-creation of gestalt_runtime attribute
        mock_bot = Mock()
        mock_chat_cog = Mock(spec=["web_search", "system_prompt"])
        mock_chat_cog.web_search = Mock()
        mock_chat_cog.system_prompt = "Test prompt"
        # No gestalt_runtime attribute due to spec

        mock_bot.get_cog.return_value = mock_chat_cog

        # Patch add_cog to capture the cog instance
        added_cog = None

        async def capture_add_cog(cog):
            nonlocal added_cog
            added_cog = cog

        mock_bot.add_cog = capture_add_cog

        # Run setup - should not raise
        await setup(mock_bot)

        # Verify cog was created with None runtime
        assert added_cog is not None
        assert added_cog.gestalt_runtime is None


class TestNoLegacyFallbackPath:
    """Verify legacy fallback path has been removed."""

    def test_no_ollama_parameter_in_init(self):
        """Verify SearchCommandsCog no longer accepts ollama parameter."""
        import inspect
        from adapters.discord.commands.search import SearchCommandsCog

        sig = inspect.signature(SearchCommandsCog.__init__)
        param_names = list(sig.parameters.keys())

        assert "ollama" not in param_names, (
            "ollama parameter should be removed from SearchCommandsCog.__init__"
        )

    def test_no_ollama_generate_in_source(self):
        """Verify no direct ollama.generate calls remain in source."""
        import inspect
        from adapters.discord.commands.search import SearchCommandsCog

        source = inspect.getsource(SearchCommandsCog)

        assert "ollama.generate" not in source, (
            "Direct ollama.generate calls should be removed"
        )

    def test_runtime_check_returns_error_when_none(self):
        """Verify code checks for runtime and returns error if None."""
        import inspect
        from adapters.discord.commands.search import SearchCommandsCog

        # Get source of the ask callback
        source = inspect.getsource(SearchCommandsCog.ask.callback)

        # The code should check for gestalt_runtime first and return error if None
        assert "self.gestalt_runtime is None" in source
        assert "Runtime not available" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
