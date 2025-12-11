"""Context router for channel-aware context management."""

import discord
import logging
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ContextStrategy:
    """Strategy for managing context in different channel types."""
    channel_type: str  # "text", "thread", "dm", "voice"
    max_messages: int  # Message count before summarization
    idle_timeout_minutes: int  # Idle time before summarization
    inherit_parent: bool  # For threads: inherit parent context?
    ephemeral: bool  # Clear on disconnect (voice)


# Predefined strategies
CONTEXT_STRATEGIES = {
    "text": ContextStrategy("text", 50, 30, False, False),
    "thread": ContextStrategy("thread", 30, 15, True, False),
    "dm": ContextStrategy("dm", 20, 10, False, False),
    "voice": ContextStrategy("voice", 999, 999, False, True),  # Voice is ephemeral
}


@dataclass
class ContextResult:
    """Result from context router."""
    history: List[Dict[str, str]]  # Recent messages
    summary: Optional[str]  # Compressed older context
    participants: List[int]  # User IDs in conversation
    should_summarize: bool  # Whether summarization is needed
    strategy: ContextStrategy  # Applied strategy


class ContextRouter:
    """Routes context handling based on channel type and manages auto-summarization."""

    def __init__(self, history_manager, summarizer=None):
        """
        Initialize context router.
        
        Args:
            history_manager: ChatHistoryManager instance
            summarizer: ConversationSummarizer instance (optional)
        """
        self.history = history_manager
        self.summarizer = summarizer
        
        # Track last activity per channel
        self.last_activity: Dict[int, datetime] = {}
        
        # Track summaries per channel
        self.channel_summaries: Dict[int, str] = {}
        
        logger.info("Context router initialized")

    def detect_channel_type(self, channel: discord.abc.Messageable) -> str:
        """
        Detect channel type.
        
        Args:
            channel: Discord channel
            
        Returns:
            Channel type: "text", "thread", "dm", or "voice"
        """
        if isinstance(channel, discord.DMChannel):
            return "dm"
        elif isinstance(channel, discord.Thread):
            return "thread"
        elif isinstance(channel, discord.VoiceChannel):
            return "voice"
        else:
            # TextChannel or other
            return "text"

    async def get_context(
        self,
        channel: discord.abc.Messageable,
        user: discord.User,
        message_content: str
    ) -> ContextResult:
        """
        Get context for a message based on channel type.
        
        Args:
            channel: Discord channel
            user: Message author
            message_content: New message content
            
        Returns:
            ContextResult with history, summary, and metadata
        """
        channel_id = channel.id
        channel_type = self.detect_channel_type(channel)
        strategy = CONTEXT_STRATEGIES[channel_type]
        
        # Update last activity
        self.last_activity[channel_id] = datetime.now()
        
        # Load full history
        full_history = await self.history.load_history(channel_id)
        
        # Check if summarization is needed
        should_summarize = await self._should_summarize(
            channel_id,
            len(full_history),
            strategy
        )
        
        # Get or create summary
        summary = None
        if should_summarize and self.summarizer:
            summary = await self._get_or_create_summary(
                channel_id,
                full_history,
                strategy
            )
        
        # For threads, try to inherit parent context
        if strategy.inherit_parent and isinstance(channel, discord.Thread):
            parent_summary = await self._get_parent_summary(channel)
            if parent_summary:
                if summary:
                    summary = f"[Parent channel context]: {parent_summary}\n\n[This thread]: {summary}"
                else:
                    summary = f"[Parent channel context]: {parent_summary}"
        
        # Get participants
        participants = self.history.get_conversation_participants(full_history)
        participant_ids = [p.get("user_id") for p in participants if p.get("user_id")]
        
        return ContextResult(
            history=full_history,
            summary=summary,
            participants=participant_ids,
            should_summarize=should_summarize,
            strategy=strategy
        )

    async def _should_summarize(
        self,
        channel_id: int,
        message_count: int,
        strategy: ContextStrategy
    ) -> bool:
        """
        Determine if summarization is needed.
        
        Args:
            channel_id: Channel ID
            message_count: Current message count
            strategy: Context strategy
            
        Returns:
            True if summarization needed
        """
        # Check message count threshold
        if message_count >= strategy.max_messages:
            logger.info(f"Channel {channel_id}: {message_count} messages, triggering summarization")
            return True
        
        # Check idle timeout
        last_activity = self.last_activity.get(channel_id)
        if last_activity:
            idle_time = datetime.now() - last_activity
            idle_minutes = idle_time.total_seconds() / 60
            
            if idle_minutes >= strategy.idle_timeout_minutes:
                logger.info(f"Channel {channel_id}: {idle_minutes:.1f}min idle, triggering summarization")
                return True
        
        return False

    async def _get_or_create_summary(
        self,
        channel_id: int,
        history: List[Dict[str, str]],
        strategy: ContextStrategy
    ) -> Optional[str]:
        """
        Get existing summary or create new one.
        
        Args:
            channel_id: Channel ID
            history: Full message history
            strategy: Context strategy
            
        Returns:
            Summary text or None
        """
        # Check cache
        if channel_id in self.channel_summaries:
            return self.channel_summaries[channel_id]
        
        # Create new summary
        if len(history) < 10:
            return None  # Not enough to summarize
        
        # Summarize older half, keep recent half raw
        split_point = len(history) // 2
        to_summarize = history[:split_point]
        
        summary = await self.summarizer.summarize_conversation(
            messages=to_summarize,
            participants=self.history.get_conversation_participants(to_summarize)
        )
        
        # Cache it
        self.channel_summaries[channel_id] = summary
        logger.info(f"Created summary for channel {channel_id}: {len(summary)} chars")
        
        return summary

    async def _get_parent_summary(self, thread: discord.Thread) -> Optional[str]:
        """
        Get summary from parent channel for thread context.
        
        Args:
            thread: Discord thread
            
        Returns:
            Parent summary or None
        """
        try:
            parent_id = thread.parent_id
            if not parent_id:
                return None
            
            # Check if parent has a summary
            return self.channel_summaries.get(parent_id)
        
        except Exception as e:
            logger.error(f"Failed to get parent summary: {e}")
            return None

    def clear_voice_context(self, channel_id: int):
        """
        Clear ephemeral voice context.
        
        Args:
            channel_id: Voice channel ID
        """
        if channel_id in self.channel_summaries:
            del self.channel_summaries[channel_id]
        if channel_id in self.last_activity:
            del self.last_activity[channel_id]
        
        logger.info(f"Cleared ephemeral voice context for channel {channel_id}")
