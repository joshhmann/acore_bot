"""Proactive Callbacks System - remembers past topics and brings them up naturally."""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import random

logger = logging.getLogger(__name__)


@dataclass
class TopicMemory:
    """Stores a remembered topic for later callback."""
    topic: str
    context: str  # What was being discussed
    users: List[str]  # Who was involved
    channel_id: int
    timestamp: datetime
    brought_up_count: int = 0
    last_brought_up: Optional[datetime] = None
    importance: float = 0.5  # 0.0 to 1.0, how interesting/important this topic is
    sentiment: str = "neutral"  # positive, negative, neutral, excited
    keywords: List[str] = field(default_factory=list)

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat() if self.timestamp else None
        data['last_brought_up'] = self.last_brought_up.isoformat() if self.last_brought_up else None
        return data

    @staticmethod
    def from_dict(data: dict) -> 'TopicMemory':
        """Create from dictionary."""
        data['timestamp'] = datetime.fromisoformat(data['timestamp']) if data.get('timestamp') else datetime.now()
        data['last_brought_up'] = datetime.fromisoformat(data['last_brought_up']) if data.get('last_brought_up') else None
        data['keywords'] = data.get('keywords', [])
        return TopicMemory(**data)


class ProactiveCallbacksSystem:
    """Manages topic memory and proactive callbacks."""

    def __init__(self, data_dir: Path = None):
        """Initialize the proactive callbacks system.

        Args:
            data_dir: Directory to store topic memories
        """
        from config import Config
        self.data_dir = data_dir or (Config.DATA_DIR / "callbacks")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Topic memories organized by channel
        self.memories: Dict[int, List[TopicMemory]] = defaultdict(list)

        # Configuration
        self.max_memories_per_channel = 50  # Keep top 50 memories per channel
        self.min_importance_threshold = 0.3  # Only store topics with importance >= 0.3
        self.callback_cooldown = timedelta(hours=6)  # Don't callback same topic within 6 hours
        self.memory_retention = timedelta(days=30)  # Keep memories for 30 days

        # Load existing memories
        self._load_memories()

        logger.info("Proactive callbacks system initialized")

    def _load_memories(self):
        """Load topic memories from disk."""
        memories_file = self.data_dir / "topic_memories.json"
        if memories_file.exists():
            try:
                with open(memories_file, 'r') as f:
                    data = json.load(f)

                    for channel_id_str, memories_list in data.items():
                        channel_id = int(channel_id_str)
                        self.memories[channel_id] = [
                            TopicMemory.from_dict(m) for m in memories_list
                        ]

                total_memories = sum(len(mems) for mems in self.memories.values())
                logger.info(f"Loaded {total_memories} topic memories from {len(self.memories)} channels")

            except Exception as e:
                logger.error(f"Failed to load topic memories: {e}")

    def _save_memories(self):
        """Save topic memories to disk."""
        memories_file = self.data_dir / "topic_memories.json"
        try:
            data = {
                str(channel_id): [m.to_dict() for m in memories]
                for channel_id, memories in self.memories.items()
            }

            with open(memories_file, 'w') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save topic memories: {e}")

    def add_topic_memory(
        self,
        topic: str,
        context: str,
        users: List[str],
        channel_id: int,
        importance: float = 0.5,
        sentiment: str = "neutral",
        keywords: Optional[List[str]] = None
    ) -> TopicMemory:
        """Add a new topic to memory.

        Args:
            topic: Brief description of the topic
            context: Fuller context of what was discussed
            users: List of users involved
            channel_id: Discord channel ID
            importance: How important/interesting (0.0 to 1.0)
            sentiment: Emotional tone (positive, negative, neutral, excited)
            keywords: List of keywords for matching

        Returns:
            The created TopicMemory
        """
        # Don't store unimportant topics
        if importance < self.min_importance_threshold:
            logger.debug(f"Skipping topic (low importance {importance}): {topic}")
            return None

        memory = TopicMemory(
            topic=topic,
            context=context,
            users=users,
            channel_id=channel_id,
            timestamp=datetime.now(),
            importance=importance,
            sentiment=sentiment,
            keywords=keywords or []
        )

        self.memories[channel_id].append(memory)

        # Prune old/low-importance memories
        self._prune_memories(channel_id)

        # Save to disk
        self._save_memories()

        logger.info(f"Stored topic memory (importance {importance:.2f}): {topic[:50]}")
        return memory

    def _prune_memories(self, channel_id: int):
        """Prune old or low-importance memories for a channel.

        Args:
            channel_id: Discord channel ID
        """
        if channel_id not in self.memories:
            return

        now = datetime.now()
        memories = self.memories[channel_id]

        # Remove expired memories
        memories = [
            m for m in memories
            if (now - m.timestamp) < self.memory_retention
        ]

        # Sort by importance (descending) and keep top N
        memories.sort(key=lambda m: m.importance, reverse=True)
        self.memories[channel_id] = memories[:self.max_memories_per_channel]

        logger.debug(f"Pruned memories for channel {channel_id}, kept {len(self.memories[channel_id])}")

    def get_callback_candidate(
        self,
        channel_id: int,
        current_context: Optional[str] = None,
        excluded_users: Optional[List[str]] = None
    ) -> Optional[TopicMemory]:
        """Get a topic memory suitable for callback.

        Args:
            channel_id: Discord channel ID
            current_context: Current conversation context (optional)
            excluded_users: Users to exclude from callback topics

        Returns:
            TopicMemory to bring up, or None
        """
        if channel_id not in self.memories or not self.memories[channel_id]:
            return None

        now = datetime.now()
        excluded_users = excluded_users or []

        # Filter candidates
        candidates = []
        for memory in self.memories[channel_id]:
            # Skip if recently brought up
            if memory.last_brought_up:
                if (now - memory.last_brought_up) < self.callback_cooldown:
                    continue

            # Skip if involves excluded users
            if any(user in memory.users for user in excluded_users):
                continue

            # Skip very recent memories (let them age a bit)
            if (now - memory.timestamp) < timedelta(hours=1):
                continue

            candidates.append(memory)

        if not candidates:
            return None

        # Weight by importance and recency
        def calculate_score(m: TopicMemory) -> float:
            age_hours = (now - m.timestamp).total_seconds() / 3600
            # Sweet spot: 6-48 hours old
            age_score = 1.0 if 6 <= age_hours <= 48 else 0.5
            # Penalize if brought up before
            callback_penalty = 0.9 ** m.brought_up_count
            return m.importance * age_score * callback_penalty

        # Calculate scores
        scored_candidates = [(m, calculate_score(m)) for m in candidates]
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # Weighted random selection from top 5
        top_candidates = scored_candidates[:5]
        if not top_candidates:
            return None

        # Select with weighted probability
        total_score = sum(score for _, score in top_candidates)
        if total_score == 0:
            return random.choice([m for m, _ in top_candidates])

        rand_val = random.uniform(0, total_score)
        cumulative = 0
        for memory, score in top_candidates:
            cumulative += score
            if rand_val <= cumulative:
                return memory

        return top_candidates[0][0]  # Fallback to top candidate

    def mark_callback_used(self, memory: TopicMemory):
        """Mark that a topic memory was used for callback.

        Args:
            memory: The topic memory that was brought up
        """
        memory.brought_up_count += 1
        memory.last_brought_up = datetime.now()
        self._save_memories()
        logger.info(f"Marked callback used: {memory.topic[:50]} (count: {memory.brought_up_count})")

    def get_stats(self) -> Dict:
        """Get callback system statistics.

        Returns:
            Statistics dictionary
        """
        total_memories = sum(len(mems) for mems in self.memories.values())

        # Calculate averages
        if total_memories > 0:
            all_memories = [m for mems in self.memories.values() for m in mems]
            avg_importance = sum(m.importance for m in all_memories) / total_memories
            avg_callback_count = sum(m.brought_up_count for m in all_memories) / total_memories

            # Sentiment distribution
            sentiment_counts = defaultdict(int)
            for m in all_memories:
                sentiment_counts[m.sentiment] += 1
        else:
            avg_importance = 0
            avg_callback_count = 0
            sentiment_counts = {}

        return {
            "total_memories": total_memories,
            "channels_tracked": len(self.memories),
            "avg_importance": avg_importance,
            "avg_callback_count": avg_callback_count,
            "sentiment_distribution": dict(sentiment_counts),
            "config": {
                "max_memories_per_channel": self.max_memories_per_channel,
                "callback_cooldown_hours": self.callback_cooldown.total_seconds() / 3600,
                "retention_days": self.memory_retention.days,
            }
        }

    def search_memories(
        self,
        query: str,
        channel_id: Optional[int] = None,
        limit: int = 10
    ) -> List[TopicMemory]:
        """Search topic memories by query.

        Args:
            query: Search query
            channel_id: Optional channel to limit search to
            limit: Maximum results

        Returns:
            List of matching topic memories
        """
        query_lower = query.lower()
        matches = []

        channels_to_search = [channel_id] if channel_id else self.memories.keys()

        for cid in channels_to_search:
            if cid not in self.memories:
                continue

            for memory in self.memories[cid]:
                # Check if query matches topic, context, or keywords
                if (query_lower in memory.topic.lower() or
                    query_lower in memory.context.lower() or
                    any(query_lower in kw.lower() for kw in memory.keywords)):
                    matches.append(memory)

        # Sort by importance
        matches.sort(key=lambda m: m.importance, reverse=True)
        return matches[:limit]
