"""CRITICAL FIXES: Memory Management for Persona System

These fixes address memory leaks and unbounded growth issues.
Apply these changes immediately to prevent production crashes.
"""

from dataclasses import dataclass, field
from collections import deque
from datetime import datetime, timedelta
import logging
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FixedBehaviorState:
    """Fixed version of BehaviorState with bounded memory."""

    # Activity
    last_message_time: datetime = field(default_factory=datetime.now)
    last_bot_message_time: datetime = field(default_factory=datetime.now)
    message_count: int = 0

    # Context
    recent_topics: deque = field(default_factory=lambda: deque(maxlen=10))
    recent_users: deque = field(default_factory=lambda: deque(maxlen=50))  # Bounded

    # Timers
    last_ambient_trigger: datetime = field(default_factory=datetime.now)
    last_proactive_trigger: datetime = field(default_factory=datetime.now)

    # Memory - BOUNDED COLLECTIONS
    short_term_memories: deque = field(
        default_factory=lambda: deque(maxlen=100)  # FIXED: Bounded to 100 items
    )

    # Add periodic cleanup
    last_cleanup: datetime = field(default_factory=datetime.now)

    def cleanup_old_data(self, max_age_hours=1):
        """Clean up old data to prevent memory bloat."""
        now = datetime.now()
        if (now - self.last_cleanup).total_seconds() > 3600:  # 1 hour
            # Clean old short-term memories
            cutoff = now - timedelta(hours=max_age_hours)
            # Filter deque by removing expired items
            temp_list = list(self.short_term_memories)
            self.short_term_memories.clear()
            self.short_term_memories.extend(
                item
                for item in temp_list
                if datetime.fromisoformat(item["timestamp"]) > cutoff
            )
            self.last_cleanup = now
            logger.debug(f"Cleaned up old behavior data for channel {id(self)}")


@dataclass
class FixedEvolutionState:
    """Fixed version of EvolutionState with bounded memory."""

    persona_id: str
    total_messages: int = 0

    # FIXED: Bounded topic tracking with sliding window
    recent_topics: deque = field(default_factory=lambda: deque(maxlen=500))
    topic_counts: dict = field(default_factory=dict)  # Track frequency instead

    # FIXED: Bounded user tracking with activity window
    active_users: dict = field(default_factory=dict)  # user_id -> last_seen

    # Relationship depth metrics
    conversation_depth: int = 0
    meaningful_interactions: int = 0

    first_interaction: Optional[datetime] = None
    last_interaction: Optional[datetime] = None

    # Add cleanup tracking
    last_cleanup: datetime = field(default_factory=datetime.now)

    def add_topic(self, topic: str):
        """Add topic with bounded tracking."""
        # Update frequency count
        self.topic_counts[topic] = self.topic_counts.get(topic, 0) + 1

        # Add to recent deque (automatically bounded)
        self.recent_topics.append(
            {
                "topic": topic,
                "timestamp": datetime.now().isoformat(),
                "count": self.topic_counts[topic],
            }
        )

    def add_user(self, user_id: str):
        """Add user with activity tracking."""
        self.active_users[user_id] = datetime.now()

    def cleanup_inactive_users(self, inactive_days=30):
        """Remove users inactive for specified period."""
        now = datetime.now()
        cutoff = now - timedelta(days=inactive_days)

        inactive_users = [
            user_id
            for user_id, last_seen in self.active_users.items()
            if last_seen < cutoff
        ]

        for user_id in inactive_users:
            del self.active_users[user_id]

        if inactive_users:
            logger.debug(
                f"Cleaned {len(inactive_users)} inactive users from {self.persona_id}"
            )

    def cleanup_old_data(self):
        """Periodic cleanup of old data."""
        now = datetime.now()
        if (now - self.last_cleanup).total_seconds() > 3600:  # 1 hour
            self.cleanup_inactive_users()
            self.last_cleanup = now


class BoundedCache:
    """LRU cache with size limits for persona system."""

    def __init__(self, max_size=1000, ttl_seconds=3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache = {}
        self.access_order = []

    def get(self, key: str):
        """Get item from cache."""
        if key not in self.cache:
            return None

        item, timestamp = self.cache[key]

        # Check TTL
        if (datetime.now() - timestamp).total_seconds() > self.ttl_seconds:
            del self.cache[key]
            self.access_order.remove(key)
            return None

        # Move to end (most recently used)
        self.access_order.remove(key)
        self.access_order.append(key)

        return item

    def put(self, key: str, value):
        """Put item in cache with size limit."""
        # Remove existing if present
        if key in self.cache:
            self.access_order.remove(key)

        # Add new item
        self.cache[key] = (value, datetime.now())
        self.access_order.append(key)

        # Enforce size limit
        while len(self.cache) > self.max_size:
            # Remove least recently used
            oldest_key = self.access_order.pop(0)
            del self.cache[oldest_key]

    def clear(self):
        """Clear all cached items."""
        self.cache.clear()
        self.access_order.clear()


# Apply these fixes by replacing the original classes:
# services/persona/behavior.py line 26: Replace BehaviorState with FixedBehaviorState
# services/persona/evolution.py line 32: Replace EvolutionState with FixedEvolutionState
# services/persona/system.py line 106-108: Replace dicts with BoundedCache

print("Persona System Memory Fixes Created")
print("Apply these changes to prevent memory leaks in production!")
