"""Review workflow for bot-to-bot conversations.

Handles posting conversation summaries to review channels and tracking
human reactions (feedback) on the conversations.
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path

import discord

from services.conversation.state import ConversationState
from config import Config

logger = logging.getLogger(__name__)


class ReviewReaction:
    """Reaction feedback from human reviewers."""

    FUNNY = "😂"  # Conversation was funny
    INTENSE = "🔥"  # Conversation was intense
    BORING = "😴"  # Conversation was boring
    SMOOTH = "✅"  # Conversation went smoothly
    AWKWARD = "⚠️"  # Conversation was awkward

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
    """Service for posting conversations to review channel and tracking feedback."""

    def __init__(self, review_channel_id: Optional[int] = None):
        """Initialize review service.

        Args:
            review_channel_id: Discord channel ID for review posts (optional)
        """
        self.review_channel_id = review_channel_id
        self.reaction_counts: Dict[
            str, Dict[str, int]
        ] = {}  # conversation_id -> {emoji: count}

    async def post_for_review(
        self,
        state: ConversationState,
        channel: discord.TextChannel,
    ) -> Optional[discord.Message]:
        """Post conversation summary to review channel with reaction options.

        Args:
            state: Completed conversation state
            channel: Original channel where conversation took place

        Returns:
            Review message if posted, None otherwise
        """
        if not self.review_channel_id:
            logger.debug("No review channel configured, skipping review post")
            return None

        try:
            # Get review channel
            review_channel = channel.guild.get_channel(self.review_channel_id)
            if not review_channel:
                logger.warning(f"Review channel {self.review_channel_id} not found")
                return None

            # Build summary message
            summary = self._build_summary(state)

            # Create embed
            embed = discord.Embed(
                title="🤖 Bot Conversation Completed",
                description=summary,
                color=discord.Color.blue(),
                timestamp=datetime.now(),
            )

            # Add conversation details
            embed.add_field(
                name="Participants", value=", ".join(state.participants), inline=False
            )

            embed.add_field(name="Topic", value=state.topic, inline=False)

            embed.add_field(
                name="Stats",
                value=f"Turns: {state.turn_count}/{state.max_turns}\n"
                f"Duration: {self._format_duration(state)}\n"
                f"Ended: {state.termination_reason}",
                inline=False,
            )

            # Add metrics if available
            if state.metrics:
                metrics_text = (
                    f"Avg Latency: {state.metrics.avg_latency:.2f}s\n"
                    f"Quality Score: {state.metrics.quality_score:.2f}"
                )
                embed.add_field(name="Metrics", value=metrics_text, inline=False)
                embed.add_field(name="Metrics", value=metrics_text, inline=False)

            # Add link to original channel
            embed.add_field(name="Channel", value=channel.mention, inline=True)

            embed.set_footer(text=f"Conversation ID: {state.conversation_id}")

            # Post to review channel
            review_message = await review_channel.send(embed=embed)

            # Add reaction buttons for feedback
            for reaction in ReviewReaction.ALL_REACTIONS:
                await review_message.add_reaction(reaction)

            # Initialize reaction tracking
            self.reaction_counts[state.conversation_id] = {
                emoji: 0 for emoji in ReviewReaction.ALL_REACTIONS
            }

            # Store metadata in conversation state
            if not state.metadata:
                state.metadata = {}
            state.metadata["review_message_id"] = review_message.id
            state.metadata["review_channel_id"] = review_channel.id

            logger.info(f"Posted conversation {state.conversation_id} for review")
            return review_message

        except Exception as e:
            logger.error(f"Failed to post conversation for review: {e}")
            return None

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
