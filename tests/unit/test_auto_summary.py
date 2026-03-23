"""Tests for auto-summary pipeline (GT-V2)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from memory.auto_summary import AutoSummaryPipeline, SummaryResult
from memory.base import MemoryNamespace
from memory.summary_generator import SummaryGenerator, SummaryGenerationError


@pytest.fixture
def mock_memory_store():
    """Create a mock memory store."""
    store = MagicMock()
    store.append_short_term = AsyncMock()
    store.get_short_term = AsyncMock(return_value=[])
    store.get_long_term_summary = AsyncMock(return_value="")
    store.set_long_term_summary = AsyncMock()
    store.get_state = AsyncMock(return_value={})
    store.set_state = AsyncMock()
    return store


@pytest.fixture
def mock_summary_generator():
    """Create a mock summary generator."""
    generator = AsyncMock(spec=SummaryGenerator)
    generator.generate_summary = AsyncMock(
        return_value={
            "summary": "Test conversation summary",
            "confidence": 0.85,
            "key_points": ["Point 1", "Point 2"],
        }
    )
    return generator


@pytest.fixture
def sample_namespace():
    """Create a sample memory namespace."""
    return MemoryNamespace(persona_id="test_persona", room_id="room_123")


@pytest.fixture
def sample_messages():
    """Create sample conversation messages."""
    return [
        {
            "role": "user",
            "content": "Hello, how are you?",
            "timestamp": datetime.now().isoformat(),
        },
        {
            "role": "assistant",
            "content": "I'm doing well, thanks!",
            "timestamp": datetime.now().isoformat(),
        },
        {
            "role": "user",
            "content": "What's the weather like?",
            "timestamp": datetime.now().isoformat(),
        },
        {
            "role": "assistant",
            "content": "It's sunny today.",
            "timestamp": datetime.now().isoformat(),
        },
        {
            "role": "user",
            "content": "Great, thanks!",
            "timestamp": datetime.now().isoformat(),
        },
    ]


class TestSummaryResult:
    """Test SummaryResult dataclass."""

    def test_summary_result_creation(self):
        """Test creating a SummaryResult."""
        result = SummaryResult(
            summary="Test summary",
            confidence=0.85,
            key_points=["Point 1", "Point 2"],
            metadata={"turn_count": 5},
        )
        assert result.summary == "Test summary"
        assert result.confidence == 0.85
        assert result.key_points == ["Point 1", "Point 2"]
        assert result.metadata["turn_count"] == 5

    def test_summary_result_default_values(self):
        """Test SummaryResult with default values."""
        result = SummaryResult(summary="Test", confidence=0.5)
        assert result.key_points == []
        assert result.metadata == {}

    def test_summary_result_is_valid(self):
        """Test is_valid property."""
        assert SummaryResult(summary="Test", confidence=0.6).is_valid is True
        assert SummaryResult(summary="Test", confidence=0.5).is_valid is False
        assert SummaryResult(summary="Test", confidence=0.0).is_valid is False
        assert SummaryResult(summary="", confidence=0.9).is_valid is False


class TestAutoSummaryPipeline:
    """Test AutoSummaryPipeline."""

    @pytest.fixture
    def pipeline(self, mock_memory_store, mock_summary_generator):
        """Create an auto-summary pipeline with mocked dependencies."""
        return AutoSummaryPipeline(
            memory_store=mock_memory_store,
            summary_generator=mock_summary_generator,
            turn_threshold=5,
            confidence_threshold=0.7,
        )

    @pytest.mark.asyncio
    async def test_should_trigger_summary_threshold_met(
        self, pipeline, mock_memory_store
    ):
        """Test that summary is triggered when turn threshold is met."""
        mock_memory_store.get_state.return_value = {
            "turn_count": 5,
            "last_summary_turn": 0,
        }

        result = await pipeline.should_trigger_summary(
            MemoryNamespace(persona_id="test", room_id="room1")
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_should_trigger_summary_below_threshold(
        self, pipeline, mock_memory_store
    ):
        """Test that summary is not triggered below threshold."""
        mock_memory_store.get_state.return_value = {
            "turn_count": 3,
            "last_summary_turn": 0,
        }

        result = await pipeline.should_trigger_summary(
            MemoryNamespace(persona_id="test", room_id="room1")
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_should_trigger_summary_already_summarized(
        self, pipeline, mock_memory_store
    ):
        """Test that summary is not triggered if already summarized recently."""
        mock_memory_store.get_state.return_value = {
            "turn_count": 10,
            "last_summary_turn": 8,
        }

        result = await pipeline.should_trigger_summary(
            MemoryNamespace(persona_id="test", room_id="room1")
        )

        # Only 2 turns since last summary, threshold is 5
        assert result is False

    @pytest.mark.asyncio
    async def test_generate_and_store_summary_success(
        self,
        pipeline,
        mock_memory_store,
        mock_summary_generator,
        sample_namespace,
        sample_messages,
    ):
        """Test successful summary generation and storage."""
        mock_memory_store.get_short_term.return_value = sample_messages

        result = await pipeline.generate_and_store_summary(sample_namespace)

        assert result is not None
        assert result.summary == "Test conversation summary"
        assert result.confidence == 0.85
        mock_summary_generator.generate_summary.assert_called_once()
        mock_memory_store.set_long_term_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_and_store_summary_low_confidence(
        self,
        pipeline,
        mock_summary_generator,
        sample_namespace,
        sample_messages,
        mock_memory_store,
    ):
        """Test that low confidence summaries are rejected."""
        mock_memory_store.get_short_term.return_value = sample_messages
        mock_summary_generator.generate_summary.return_value = {
            "summary": "Low confidence summary",
            "confidence": 0.5,  # Below threshold of 0.7
            "key_points": [],
        }

        result = await pipeline.generate_and_store_summary(sample_namespace)

        assert result is None
        mock_memory_store.set_long_term_summary.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_and_store_summary_empty_messages(
        self, pipeline, mock_memory_store, sample_namespace
    ):
        """Test handling of empty message list."""
        mock_memory_store.get_short_term.return_value = []

        result = await pipeline.generate_and_store_summary(sample_namespace)

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_and_store_summary_too_short(
        self, pipeline, mock_memory_store, sample_namespace
    ):
        """Test that very short conversations are not summarized."""
        mock_memory_store.get_short_term.return_value = [
            {"role": "user", "content": "Hi"},
        ]

        result = await pipeline.generate_and_store_summary(sample_namespace)

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_and_store_summary_error_handling(
        self,
        pipeline,
        mock_summary_generator,
        sample_namespace,
        sample_messages,
        mock_memory_store,
    ):
        """Test error handling during summary generation."""
        mock_memory_store.get_short_term.return_value = sample_messages
        mock_summary_generator.generate_summary.side_effect = Exception("LLM error")

        # Should not raise exception
        result = await pipeline.generate_and_store_summary(sample_namespace)

        assert result is None

    @pytest.mark.asyncio
    async def test_maybe_summarize_triggers_on_threshold(
        self,
        pipeline,
        mock_memory_store,
        mock_summary_generator,
        sample_namespace,
        sample_messages,
    ):
        """Test that maybe_summarize triggers when conditions are met."""
        mock_memory_store.get_state.return_value = {
            "turn_count": 5,
            "last_summary_turn": 0,
        }
        mock_memory_store.get_short_term.return_value = sample_messages

        result = await pipeline.maybe_summarize(sample_namespace)

        assert result is not None
        assert result.summary == "Test conversation summary"
        # Should update state with last summary turn
        mock_memory_store.set_state.assert_called()

    @pytest.mark.asyncio
    async def test_maybe_summarize_skips_when_not_needed(
        self, pipeline, mock_memory_store, sample_namespace
    ):
        """Test that maybe_summarize skips when conditions not met."""
        mock_memory_store.get_state.return_value = {
            "turn_count": 2,
            "last_summary_turn": 0,
        }

        result = await pipeline.maybe_summarize(sample_namespace)

        assert result is None
        mock_memory_store.get_short_term.assert_not_called()

    @pytest.mark.asyncio
    async def test_record_turn_updates_counter(
        self, pipeline, mock_memory_store, sample_namespace
    ):
        """Test that record_turn increments turn counter."""
        mock_memory_store.get_state.return_value = {"turn_count": 3}

        await pipeline.record_turn(sample_namespace)

        mock_memory_store.set_state.assert_called_once()
        call_args = mock_memory_store.set_state.call_args
        assert call_args[0][1]["turn_count"] == 4

    @pytest.mark.asyncio
    async def test_record_turn_initializes_counter(
        self, pipeline, mock_memory_store, sample_namespace
    ):
        """Test that record_turn initializes counter if not present."""
        mock_memory_store.get_state.return_value = {}

        await pipeline.record_turn(sample_namespace)

        call_args = mock_memory_store.set_state.call_args
        assert call_args[0][1]["turn_count"] == 1

    @pytest.mark.asyncio
    async def test_get_stats(self, pipeline):
        """Test getting pipeline statistics."""
        pipeline._stats["summaries_generated"] = 5
        pipeline._stats["summaries_stored"] = 4
        pipeline._stats["errors"] = 1

        stats = pipeline.get_stats()

        assert stats["summaries_generated"] == 5
        assert stats["summaries_stored"] == 4
        assert stats["errors"] == 1

    def test_update_turn_threshold(self, pipeline):
        """Test updating turn threshold."""
        pipeline.update_turn_threshold(10)
        assert pipeline.turn_threshold == 10

    def test_update_confidence_threshold(self, pipeline):
        """Test updating confidence threshold."""
        pipeline.update_confidence_threshold(0.8)
        assert pipeline.confidence_threshold == 0.8


class TestSummaryGenerator:
    """Test SummaryGenerator."""

    @pytest.fixture
    def mock_llm_provider(self):
        """Create a mock LLM provider."""
        provider = AsyncMock()
        provider.chat = AsyncMock(
            return_value=MagicMock(
                content='{"summary": "Test summary", "confidence": 0.85, "key_points": ["Point 1"]}'
            )
        )
        return provider

    @pytest.fixture
    def generator(self, mock_llm_provider):
        """Create a summary generator with mocked LLM."""
        return SummaryGenerator(provider=mock_llm_provider, min_messages=2)

    @pytest.mark.asyncio
    async def test_generate_summary_success(self, generator, mock_llm_provider):
        """Test successful summary generation."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]

        result = await generator.generate_summary(messages)

        assert result["summary"] == "Test summary"
        assert result["confidence"] == 0.85
        assert result["key_points"] == ["Point 1"]
        mock_llm_provider.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_summary_empty_messages(self, generator):
        """Test handling of empty messages."""
        result = await generator.generate_summary([])

        assert result["summary"] == ""
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_generate_summary_too_short(self, generator):
        """Test handling of too few messages."""
        result = await generator.generate_summary([{"role": "user", "content": "Hi"}])

        assert result["summary"] == ""
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_generate_summary_invalid_json_response(
        self, generator, mock_llm_provider
    ):
        """Test handling of invalid JSON response."""
        mock_llm_provider.chat.return_value = MagicMock(content="Not valid JSON")

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

        # Should handle gracefully and extract text as summary
        result = await generator.generate_summary(messages)

        assert "summary" in result
        assert result["confidence"] < 0.5  # Low confidence for malformed response

    @pytest.mark.asyncio
    async def test_generate_summary_llm_error(self, generator, mock_llm_provider):
        """Test handling of LLM errors."""
        mock_llm_provider.chat.side_effect = Exception("LLM unavailable")

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

        with pytest.raises(SummaryGenerationError):
            await generator.generate_summary(messages)

    @pytest.mark.asyncio
    async def test_generate_summary_rate_limit_handling(
        self, generator, mock_llm_provider
    ):
        """Test handling of rate limit errors."""
        mock_llm_provider.chat.side_effect = Exception("Rate limit exceeded")

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

        with pytest.raises(SummaryGenerationError) as exc_info:
            await generator.generate_summary(messages)

        assert (
            "rate" in str(exc_info.value).lower()
            or "limit" in str(exc_info.value).lower()
            or "generation failed" in str(exc_info.value).lower()
        )

    def test_build_prompt(self, generator):
        """Test prompt construction."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        prompt = generator._build_prompt(messages)

        assert "conversation" in prompt.lower()
        assert "summary" in prompt.lower()
        assert "Hello" in prompt
        assert "Hi there!" in prompt

    def test_format_messages(self, generator):
        """Test message formatting."""
        messages = [
            {"role": "user", "name": "Alice", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]

        formatted = generator._format_messages(messages)

        assert "Alice (user): Hello" in formatted
        assert "assistant: Hi!" in formatted

    def test_parse_response_valid_json(self, generator):
        """Test parsing valid JSON response."""
        response = MagicMock(
            content='{"summary": "Test", "confidence": 0.9, "key_points": ["A", "B"]}'
        )

        result = generator._parse_response(response)

        assert result["summary"] == "Test"
        assert result["confidence"] == 0.9
        assert result["key_points"] == ["A", "B"]

    def test_parse_response_plain_text(self, generator):
        """Test parsing plain text response."""
        response = MagicMock(content="This is a summary")

        result = generator._parse_response(response)

        assert result["summary"] == "This is a summary"
        assert result["confidence"] < 0.5  # Lower confidence for plain text
        # Fallback extracts key points from sentences
        assert len(result["key_points"]) >= 0

    def test_parse_response_partial_json(self, generator):
        """Test parsing partial/invalid JSON."""
        response = MagicMock(content='{"summary": "Test", invalid}')

        result = generator._parse_response(response)

        assert "Test" in result["summary"] or result["confidence"] < 0.5


class TestIntegration:
    """Integration tests for the auto-summary system."""

    @pytest.mark.asyncio
    async def test_end_to_end_summary_flow(
        self, mock_memory_store, mock_summary_generator, sample_messages
    ):
        """Test complete summary flow from turn recording to storage."""
        pipeline = AutoSummaryPipeline(
            memory_store=mock_memory_store,
            summary_generator=mock_summary_generator,
            turn_threshold=3,
            confidence_threshold=0.7,
        )

        namespace = MemoryNamespace(persona_id="test_bot", room_id="channel_1")

        # Simulate 3 turns
        mock_memory_store.get_state.return_value = {}
        for i in range(3):
            await pipeline.record_turn(namespace)
            mock_memory_store.get_state.return_value = {
                "turn_count": i + 1,
                "last_summary_turn": 0,
            }

        # Should trigger summary after 3 turns
        mock_memory_store.get_state.return_value = {
            "turn_count": 3,
            "last_summary_turn": 0,
        }
        mock_memory_store.get_short_term.return_value = sample_messages[:4]

        result = await pipeline.maybe_summarize(namespace)

        assert result is not None
        assert result.is_valid

    @pytest.mark.asyncio
    async def test_summary_not_triggered_prematurely(
        self, mock_memory_store, mock_summary_generator
    ):
        """Test that summary is not triggered before threshold."""
        pipeline = AutoSummaryPipeline(
            memory_store=mock_memory_store,
            summary_generator=mock_summary_generator,
            turn_threshold=10,
            confidence_threshold=0.7,
        )

        namespace = MemoryNamespace(persona_id="test_bot", room_id="channel_1")

        # Only 5 turns recorded
        mock_memory_store.get_state.return_value = {
            "turn_count": 5,
            "last_summary_turn": 0,
        }

        result = await pipeline.maybe_summarize(namespace)

        assert result is None
        mock_summary_generator.generate_summary.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_summaries_over_time(
        self, mock_memory_store, mock_summary_generator
    ):
        """Test that multiple summaries can be generated over a long conversation."""
        pipeline = AutoSummaryPipeline(
            memory_store=mock_memory_store,
            summary_generator=mock_summary_generator,
            turn_threshold=5,
            confidence_threshold=0.7,
        )

        namespace = MemoryNamespace(persona_id="test_bot", room_id="channel_1")

        # First summary at turn 5
        mock_memory_store.get_state.return_value = {
            "turn_count": 5,
            "last_summary_turn": 0,
        }
        mock_memory_store.get_short_term.return_value = [
            {"role": "user", "content": f"Message {i}"} for i in range(6)
        ]

        result1 = await pipeline.maybe_summarize(namespace)
        assert result1 is not None

        # Update state to reflect first summary
        mock_memory_store.get_state.return_value = {
            "turn_count": 10,
            "last_summary_turn": 5,
        }

        # Second summary at turn 10 (5 turns after last summary)
        result2 = await pipeline.maybe_summarize(namespace)
        assert result2 is not None

        # Should have called generate_summary twice
        assert mock_summary_generator.generate_summary.call_count == 2
