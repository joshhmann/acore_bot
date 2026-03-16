"""LLM-based conversation summary generator.

Provides async summary generation with confidence scoring and error handling.
Designed for non-blocking operation in the auto-summary pipeline.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class SummaryGenerationError(Exception):
    """Raised when summary generation fails."""

    pass


class LLMProvider(Protocol):
    """Protocol for LLM provider interface."""

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> Any: ...


@dataclass
class SummaryGenerator:
    """Generates conversation summaries using an LLM provider.

    Attributes:
        provider: LLM provider for generating summaries
        min_messages: Minimum number of messages required to generate summary
        max_summary_chars: Maximum length of generated summary
    """

    provider: LLMProvider
    min_messages: int = 3
    max_summary_chars: int = 500

    async def generate_summary(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate a summary of the conversation.

        Args:
            messages: List of conversation messages with 'role' and 'content' keys

        Returns:
            Dictionary with 'summary', 'confidence', and 'key_points' keys

        Raises:
            SummaryGenerationError: If LLM call fails
        """
        if len(messages) < self.min_messages:
            logger.debug(
                f"Too few messages for summary: {len(messages)} < {self.min_messages}"
            )
            return {"summary": "", "confidence": 0.0, "key_points": []}

        prompt = self._build_prompt(messages)

        try:
            response = await self.provider.chat(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a conversation summarizer. Analyze the conversation "
                            "and provide a concise summary with confidence scoring. "
                            "Respond in JSON format with keys: summary (string), "
                            "confidence (float 0-1), key_points (list of strings)."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,  # Lower temperature for consistent summaries
            )

            return self._parse_response(response)

        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            raise SummaryGenerationError(f"Failed to generate summary: {e}") from e

    def _build_prompt(self, messages: list[dict[str, Any]]) -> str:
        """Build the summarization prompt from messages.

        Args:
            messages: List of conversation messages

        Returns:
            Formatted prompt string
        """
        formatted_messages = self._format_messages(messages)

        return (
            f"Summarize the following conversation ({len(messages)} messages):\n\n"
            f"{formatted_messages}\n\n"
            f"Provide:\n"
            f"1. A concise summary (max {self.max_summary_chars} chars)\n"
            f"2. A confidence score (0.0-1.0) for the summary quality\n"
            f"3. 2-5 key points extracted from the conversation\n\n"
            f"Respond in valid JSON format."
        )

    def _format_messages(self, messages: list[dict[str, Any]]) -> str:
        """Format messages for the prompt.

        Args:
            messages: Raw message dictionaries

        Returns:
            Formatted message string
        """
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "").strip()
            name = msg.get("name", "")

            if not content:
                continue

            if name:
                lines.append(f"{name} ({role}): {content}")
            else:
                lines.append(f"{role}: {content}")

        return "\n".join(lines)

    def _parse_response(self, response: Any) -> dict[str, Any]:
        """Parse the LLM response into a structured summary.

        Args:
            response: LLM response object with 'content' attribute

        Returns:
            Parsed summary dictionary
        """
        content = getattr(response, "content", str(response)).strip()

        # Try to parse as JSON first
        try:
            data = json.loads(content)
            return {
                "summary": str(data.get("summary", "")).strip(),
                "confidence": float(data.get("confidence", 0.0)),
                "key_points": list(data.get("key_points", [])),
            }
        except json.JSONDecodeError:
            # Fallback: treat entire response as summary with low confidence
            logger.warning("Failed to parse JSON response, using plain text fallback")
            return {
                "summary": content[: self.max_summary_chars],
                "confidence": 0.3,  # Low confidence for unstructured response
                "key_points": self._extract_key_points_fallback(content),
            }

    def _extract_key_points_fallback(self, text: str) -> list[str]:
        """Extract key points from plain text as fallback.

        Args:
            text: Raw text response

        Returns:
            List of extracted key points
        """
        # Simple extraction: split by sentences and take first few
        sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 10]
        return sentences[:3]  # Return up to 3 key points
