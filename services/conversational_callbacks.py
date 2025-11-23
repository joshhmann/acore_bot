"""Conversational callbacks - references past conversations naturally."""
import logging
import random
from typing import Optional, List, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ConversationalCallbacks:
    """Manages callbacks to past conversations and topics."""

    def __init__(self, history_manager, summarizer=None):
        """Initialize conversational callbacks.

        Args:
            history_manager: Chat history manager
            summarizer: Conversation summarizer (optional)
        """
        self.history = history_manager
        self.summarizer = summarizer

        # Track topics discussed per channel
        self.channel_topics: Dict[int, List[Dict]] = {}  # channel_id -> list of topics

        logger.info("Conversational callbacks initialized")

    async def extract_topics(self, message: str) -> List[str]:
        """Extract key topics from a message.

        Args:
            message: Message text

        Returns:
            List of topics
        """
        # Simple keyword extraction (could be enhanced with NLP)
        topics = []

        # Common nouns/topics to look for
        keywords = {
            "gaming": ["game", "gaming", "play", "playing", "gamer"],
            "food": ["food", "eating", "dinner", "lunch", "breakfast", "hungry", "pizza", "burger"],
            "coding": ["code", "coding", "programming", "developer", "bug", "python", "javascript"],
            "music": ["music", "song", "album", "artist", "listening", "spotify"],
            "movies": ["movie", "film", "watch", "watching", "netflix"],
            "work": ["work", "working", "job", "office", "meeting", "boss"],
            "exercise": ["gym", "workout", "exercise", "running", "fitness"],
            "travel": ["travel", "trip", "vacation", "flight", "hotel"],
            "weather": ["weather", "rain", "snow", "sunny", "cold", "hot"],
        }

        message_lower = message.lower()
        for topic, words in keywords.items():
            if any(word in message_lower for word in words):
                topics.append(topic)

        return topics

    async def track_conversation_topic(self, channel_id: int, message: str, user_name: str):
        """Track topics discussed in conversation.

        Args:
            channel_id: Discord channel ID
            message: Message content
            user_name: Username who sent message
        """
        topics = await self.extract_topics(message)

        if not topics:
            return

        if channel_id not in self.channel_topics:
            self.channel_topics[channel_id] = []

        for topic in topics:
            self.channel_topics[channel_id].append({
                "topic": topic,
                "time": datetime.now(),
                "user": user_name,
                "snippet": message[:100],  # First 100 chars
            })

        # Keep only last 50 topics per channel
        if len(self.channel_topics[channel_id]) > 50:
            self.channel_topics[channel_id] = self.channel_topics[channel_id][-50:]

    async def get_callback_opportunity(self, channel_id: int, current_message: str) -> Optional[str]:
        """Check if there's an opportunity to callback to past conversation.

        Args:
            channel_id: Channel ID
            current_message: Current message being processed

        Returns:
            Callback prompt or None
        """
        if channel_id not in self.channel_topics:
            return None

        topics = self.channel_topics[channel_id]
        if not topics:
            return None

        # Extract current topics
        current_topics = await self.extract_topics(current_message)

        if not current_topics:
            return None

        # Find matching past topics (discussed earlier)
        now = datetime.now()
        for current_topic in current_topics:
            # Look for same topic discussed earlier
            for past_topic in reversed(topics[:-1]):  # Exclude very recent
                if past_topic["topic"] == current_topic:
                    time_diff = now - past_topic["time"]

                    # Topic from 5 minutes to 24 hours ago
                    if timedelta(minutes=5) < time_diff < timedelta(hours=24):
                        # Chance to callback (20%)
                        if random.random() < 0.2:
                            return self._generate_callback_prompt(current_topic, past_topic, time_diff)

        return None

    def _generate_callback_prompt(self, topic: str, past_topic: Dict, time_diff: timedelta) -> str:
        """Generate a callback prompt.

        Args:
            topic: Current topic
            past_topic: Past topic dict
            time_diff: Time since past topic

        Returns:
            Callback prompt
        """
        user = past_topic["user"]
        snippet = past_topic["snippet"]

        # Format time difference
        if time_diff < timedelta(hours=1):
            time_str = "earlier"
        elif time_diff < timedelta(hours=6):
            time_str = "a few hours ago"
        else:
            time_str = "earlier today"

        prompts = [
            f"[CALLBACK OPPORTUNITY: {user} mentioned {topic} {time_str}. You could naturally reference that if relevant.]",
            f"[CONTEXT: Earlier conversation about {topic} with {user}. Feel free to callback if it fits naturally.]",
            f"[NOTE: {topic} was discussed {time_str}. Consider mentioning it if appropriate.]",
        ]

        return random.choice(prompts)

    async def get_recent_context(self, channel_id: int, max_topics: int = 5) -> str:
        """Get recent conversation context.

        Args:
            channel_id: Channel ID
            max_topics: Max topics to include

        Returns:
            Context string
        """
        if channel_id not in self.channel_topics:
            return ""

        topics = self.channel_topics[channel_id][-max_topics:]

        if not topics:
            return ""

        # Build context
        topic_names = [t["topic"] for t in topics]
        unique_topics = list(dict.fromkeys(topic_names))  # Preserve order, remove duplicates

        return f"[Recent conversation topics: {', '.join(unique_topics)}]"

    async def find_related_memories(self, current_message: str, channel_id: int) -> Optional[str]:
        """Find related memories from conversation history.

        Args:
            current_message: Current message
            channel_id: Channel ID

        Returns:
            Memory context or None
        """
        if not self.summarizer:
            return None

        try:
            # Use summarizer's RAG to find relevant past conversations
            memories = await self.summarizer.retrieve_relevant_memories(
                query=current_message,
                max_results=2
            )

            if memories:
                # Format as callback context
                memory_text = "\n".join([f"- {m}" for m in memories[:2]])
                return f"[PAST CONVERSATIONS: You might recall:\n{memory_text}]"

        except Exception as e:
            logger.error(f"Error finding related memories: {e}")

        return None

    def generate_followup_question(self, topic: str, user: str) -> Optional[str]:
        """Generate a natural follow-up question about a past topic.

        Args:
            topic: Topic to ask about
            user: User who discussed it

        Returns:
            Follow-up question or None
        """
        # Low chance (10%)
        if random.random() > 0.1:
            return None

        questions = {
            "gaming": [
                f"How did that gaming session go, {user}?",
                f"Did you end up playing that game, {user}?",
                f"Still gaming, {user}?",
            ],
            "food": [
                f"Did you get that food you wanted, {user}?",
                f"How was the food, {user}?",
                f"End up eating something good, {user}?",
            ],
            "work": [
                f"How's work going, {user}?",
                f"Did that work thing get sorted out, {user}?",
            ],
            "coding": [
                f"Did you fix that bug, {user}?",
                f"How's the coding going, {user}?",
            ],
        }

        if topic in questions:
            return random.choice(questions[topic])

        return None

    async def should_ask_followup(self, channel_id: int) -> Optional[str]:
        """Check if bot should ask a follow-up about past topic.

        Args:
            channel_id: Channel ID

        Returns:
            Follow-up question or None
        """
        if channel_id not in self.channel_topics:
            return None

        topics = self.channel_topics[channel_id]
        if not topics:
            return None

        # Look at topics from 30 mins to 6 hours ago
        now = datetime.now()
        for topic_data in reversed(topics):
            time_diff = now - topic_data["time"]

            if timedelta(minutes=30) < time_diff < timedelta(hours=6):
                followup = self.generate_followup_question(
                    topic_data["topic"],
                    topic_data["user"]
                )
                if followup:
                    return followup

        return None

    def get_conversation_continuity_context(self, channel_id: int) -> str:
        """Get context about conversation continuity.

        Args:
            channel_id: Channel ID

        Returns:
            Context string
        """
        if channel_id not in self.channel_topics:
            return "[This is a new conversation]"

        topics = self.channel_topics[channel_id]
        if not topics:
            return "[This is a new conversation]"

        # Check last topic time
        last_topic_time = topics[-1]["time"]
        time_since = datetime.now() - last_topic_time

        if time_since < timedelta(minutes=5):
            return "[Ongoing conversation - context is fresh]"
        elif time_since < timedelta(hours=1):
            return "[Conversation resumed - some context from earlier]"
        elif time_since < timedelta(hours=6):
            return "[Conversation picking back up - there was a lull]"
        else:
            return "[Fresh conversation - previous topics are old]"

    def get_stats(self) -> Dict:
        """Get conversational callbacks statistics.

        Returns:
            Dict with stats
        """
        return {
            "tracked_channels": len(self.channel_topics),
            "total_topics_tracked": sum(len(topics) for topics in self.channel_topics.values()),
        }
