"""Discord-specific review service adapter.

Handles posting conversation summaries to Discord channels with embeds
and tracking reactions. Uses the generic ConversationReviewService for
core tracking logic.
"""

import logging
from datetime import datetime
from typing import Optional, TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from services.conversation.review import ConversationReviewService
    from services.conversation.state import ConversationState

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


class DiscordReviewService:
    """Discord-specific adapter for conversation review workflow.

    Handles Discord-specific operations like embeds, channel posting,
    and reaction management. Delegates tracking logic to the generic
    ConversationReviewService.
    """

    def __init__(
        self,
        bot: discord.Client,
        review_channel_id: Optional[int] = None,
        review_service: Optional["ConversationReviewService"] = None,
    ):
        """Initialize Discord review service adapter.

        Args:
            bot: Discord bot client
            review_channel_id: Discord channel ID for review posts
            review_service: Generic review service for tracking (optional)
        """
        self.bot = bot
        self.review_channel_id = review_channel_id
        self._review_service = review_service

    def _get_review_service(self) -> Optional["ConversationReviewService"]:
        """Get or create the underlying review service."""
        if self._review_service is None:
            from services.conversation.review import ConversationReviewService

            self._review_service = ConversationReviewService()
        return self._review_service

    async def post_for_review(
        self,
        state: "ConversationState",
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

            # Build summary using the generic service
            review_service = self._get_review_service()
            if not review_service:
                logger.error("Failed to initialize review service")
                return None

            summary = review_service._build_summary(state)

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
                f"Duration: {review_service._format_duration(state)}\n"
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

            # Add link to original channel
            embed.add_field(name="Channel", value=channel.mention, inline=True)

            embed.set_footer(text=f"Conversation ID: {state.conversation_id}")

            # Post to review channel
            review_message = await review_channel.send(embed=embed)

            # Add reaction buttons for feedback
            for reaction in ReviewReaction.ALL_REACTIONS:
                await review_message.add_reaction(reaction)

            # Initialize reaction tracking in the service
            review_service.initialize_reaction_tracking(state.conversation_id)

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

    async def update_reaction_count(self, conversation_id: str, emoji: str, count: int):
        """Update reaction count for a conversation.

        Args:
            conversation_id: Conversation ID
            emoji: Reaction emoji
            count: New reaction count
        """
        review_service = self._get_review_service()
        if review_service:
            await review_service.update_reaction_count(conversation_id, emoji, count)

    def get_reaction_counts(self, conversation_id: str) -> dict:
        """Get reaction counts for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            Dictionary of emoji -> count
        """
        review_service = self._get_review_service()
        if review_service:
            return review_service.get_reaction_counts(conversation_id)
        return {}

    def get_review_summary(self, conversation_id: str) -> str:
        """Get human-readable review summary.

        Args:
            conversation_id: Conversation ID

        Returns:
            Formatted summary of reactions
        """
        review_service = self._get_review_service()
        if not review_service:
            return "Review service not available"

        counts = review_service.get_reaction_counts(conversation_id)
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
