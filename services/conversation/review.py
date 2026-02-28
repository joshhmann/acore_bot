"""Review workflow for bot-to-bot conversations.

Handles tracking of human reactions (feedback) on conversations.
Platform-specific posting logic (Discord embeds, etc.) should be
implemented in platform adapters.
"""

import logging
from typing import Optional, Dict, List

from services.conversation.state import ConversationState

logger = logging.getLogger(__name__)


class ReviewReaction:
    """Reaction feedback from human reviewers."""

    FUNNY = "😂"
    INTENSE = "🔥"
    BORING = "😴"
    SMOOTH = "✅"
    AWKWARD = "⚠️"

    ALL_REACTIONS = [FUNNY, INTENSE, BORING, SMOOTH, AWKWARD]

    @classmethod
    def get_description(cls, emoji: str) -> str:
        """Get human-readable description of reaction."""
        descriptions = {
            cls.FUNNY: "Funny",
            cls.INTENSE: "Intense",
            cls.BORING: "Boring",
            cls.SMOOTH: "Smooth",
            cls.AWKWARD: "Awkward",
        }
        return descriptions.get(emoji, "Unknown")


class ConversationReviewService:
    """Service for tracking conversation reviews and reactions."""

    def __init__(self):
        """Initialize review service."""
        self.reaction_counts: Dict[str, Dict[str, int]] = {}

    def initialize_reaction_tracking(self, conversation_id: str):
        """Initialize reaction tracking for a conversation.

        Args:
            conversation_id: Conversation ID to track
        """
        self.reaction_counts[conversation_id] = {
            emoji: 0 for emoji in ReviewReaction.ALL_REACTIONS
        }
        logger.debug(f"Initialized reaction tracking for {conversation_id}")

    def _build_summary(self, state: ConversationState) -> str:
        """Build conversation summary text.

        Args:
            state: Conversation state

        Returns:
            Summary text
        """
        if not state.messages:
            return "No messages in conversation."

        # Show first and last message
        first_msg = state.messages[0]
        last_msg = state.messages[-1]

        summary = f"**First message** ({first_msg.speaker}):\n"
        summary += f"> {first_msg.content[:200]}...\n\n"

        if len(state.messages) > 1:
            summary += f"**Last message** ({last_msg.speaker}):\n"
            summary += f"> {last_msg.content[:200]}...\n\n"

        summary += f"Total messages: {len(state.messages)}"

        return summary

    def _format_duration(self, state: ConversationState) -> str:
        """Format conversation duration.

        Args:
            state: Conversation state

        Returns:
            Formatted duration string
        """
        if not state.ended_at or not state.started_at:
            return "Unknown"

        duration = (state.ended_at - state.started_at).total_seconds()

        if duration < 60:
            return f"{duration:.1f}s"
        elif duration < 3600:
            minutes = duration / 60
            return f"{minutes:.1f}m"
        else:
            hours = duration / 3600
            return f"{hours:.1f}h"

    async def update_reaction_count(self, conversation_id: str, emoji: str, count: int):
        """Update reaction count for a conversation.

        Args:
            conversation_id: Conversation ID
            emoji: Reaction emoji
            count: New reaction count
        """
        if conversation_id not in self.reaction_counts:
            self.reaction_counts[conversation_id] = {}

        self.reaction_counts[conversation_id][emoji] = count
        logger.debug(f"Updated reaction {emoji} for {conversation_id}: {count}")

    def get_reaction_counts(self, conversation_id: str) -> Dict[str, int]:
        """Get reaction counts for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            Dictionary of emoji -> count
        """
        return self.reaction_counts.get(conversation_id, {})

    def get_review_summary(self, conversation_id: str) -> str:
        """Get human-readable review summary.

        Args:
            conversation_id: Conversation ID

        Returns:
            Formatted summary of reactions
        """
        counts = self.get_reaction_counts(conversation_id)
        if not counts:
            return "No reviews yet"

        # Sort by count (descending)
        sorted_reactions = sorted(counts.items(), key=lambda x: x[1], reverse=True)

        # Build summary
        summary_parts = []
        for emoji, count in sorted_reactions:
            if count > 0:
                desc = ReviewReaction.get_description(emoji)
                summary_parts.append(f"{emoji} {desc}: {count}")

        if not summary_parts:
            return "No reactions yet"

        return "\n".join(summary_parts)
