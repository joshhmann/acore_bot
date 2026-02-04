"""Rich state feature engineering for RL agents.

Expands state representation from 3 simple bins to 16+ rich normalized features
for better context awareness and decision making.
"""

import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from collections import deque

from .types import RLAction


# Constants for normalization
MAX_MESSAGE_LENGTH = 2000  # Discord max
MAX_TURN_COUNT = 100
MAX_VELOCITY = 60  # messages per minute
MAX_TIME_SINCE = 3600  # 1 hour in seconds
MAX_DEPTH = 20  # conversation depth


@dataclass
class StateFeatures:
    """Rich state features for RL decision making.

    All features are normalized to [0, 1] or [-1, 1] for neural network compatibility.
    Total dimensionality: 16 base features (expandable to 128 with one-hot encodings).
    """

    # Time Features (4 features) - all [0, 1]
    hour_of_day: float = 0.0  # 0-23 normalized to [0, 1]
    day_of_week: float = 0.0  # 0-6 normalized to [0, 1]
    is_weekend: float = 0.0  # 0 or 1
    is_night: float = 0.0  # 0 or 1 (10pm - 6am)

    # Conversation Features (4 features) - all [0, 1]
    turn_count: float = 0.0  # Normalized message count in conversation
    message_velocity: float = 0.0  # Messages per minute, normalized
    time_since_last: float = 0.0  # Time since last message, normalized
    conversation_depth: float = 0.0  # How deep the conversation is

    # Content Features (4 features) - all [0, 1]
    message_length: float = 0.0  # Normalized message length
    has_question: float = 0.0  # 0 or 1
    has_url: float = 0.0  # 0 or 1
    has_attachment: float = 0.0  # 0 or 1

    # Context Features (4 features) - [-1, 1] or [0, 1]
    previous_action: int = 0  # Previous action as int (for one-hot encoding)
    sentiment_trend: float = 0.0  # [-1, 1] average sentiment direction
    topic_consistency: float = 0.0  # [0, 1] how consistent topics are
    channel_activity: float = 0.0  # [0, 1] normalized channel activity level

    def to_vector(self, include_one_hot: bool = False) -> List[float]:
        """Convert features to a flat vector for neural network input.

        Args:
            include_one_hot: If True, include one-hot encoding of previous_action
                           (adds 4 dimensions for 4 actions)

        Returns:
            List of normalized feature values
        """
        base_features = [
            # Time Features
            self.hour_of_day,
            self.day_of_week,
            self.is_weekend,
            self.is_night,
            # Conversation Features
            self.turn_count,
            self.message_velocity,
            self.time_since_last,
            self.conversation_depth,
            # Content Features
            self.message_length,
            self.has_question,
            self.has_url,
            self.has_attachment,
            # Context Features (excluding previous_action which needs special handling)
            self.sentiment_trend,
            self.topic_consistency,
            self.channel_activity,
        ]

        if include_one_hot:
            # One-hot encode previous_action (4 actions: WAIT, REACT, ENGAGE, INITIATE)
            one_hot = [0.0] * 4
            if 0 <= self.previous_action < 4:
                one_hot[self.previous_action] = 1.0
            base_features.extend(one_hot)
        else:
            # Just include action as normalized value
            base_features.append(self.previous_action / 3.0)  # Normalize to [0, 1]

        return base_features

    @property
    def dimensionality(self) -> int:
        """Return the total number of features."""
        return len(self.to_vector(include_one_hot=False))

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for serialization/logging."""
        return {
            "hour_of_day": self.hour_of_day,
            "day_of_week": self.day_of_week,
            "is_weekend": self.is_weekend,
            "is_night": self.is_night,
            "turn_count": self.turn_count,
            "message_velocity": self.message_velocity,
            "time_since_last": self.time_since_last,
            "conversation_depth": self.conversation_depth,
            "message_length": self.message_length,
            "has_question": self.has_question,
            "has_url": self.has_url,
            "has_attachment": self.has_attachment,
            "previous_action": float(self.previous_action),
            "sentiment_trend": self.sentiment_trend,
            "topic_consistency": self.topic_consistency,
            "channel_activity": self.channel_activity,
        }


class StateFeatureExtractor:
    """Extracts rich state features from conversation context.

    Performance target: < 1ms per extraction
    Dimensionality: 16 base features (configurable up to 128)
    """

    def __init__(self, max_dimensions: int = 128):
        """Initialize the feature extractor.

        Args:
            max_dimensions: Maximum allowed dimensionality (default: 128)
        """
        self.max_dimensions = max_dimensions

        # URL pattern for content feature extraction
        self._url_pattern = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+', re.IGNORECASE)

        # Question indicators
        self._question_pattern = re.compile(
            r"\?|^(?:who|what|when|where|why|how|can|could|would|should|is|are|do|does|did)\b",
            re.IGNORECASE,
        )

    def extract(
        self,
        message: Optional[Any] = None,
        behavior_state: Optional[Any] = None,
        history: Optional[List[Dict]] = None,
        previous_action: Optional[RLAction] = None,
        timestamp: Optional[datetime] = None,
    ) -> StateFeatures:
        """Extract rich state features from conversation context.

        Args:
            message: Discord message object (or mock with .content, .attachments)
            behavior_state: BehaviorState object from behavior.py
            history: Recent conversation history (list of message dicts)
            previous_action: Previous RLAction taken
            timestamp: Timestamp for time features (defaults to now)

        Returns:
            StateFeatures dataclass with all normalized features

        Performance: Target < 1ms
        """
        features = StateFeatures()
        ts = timestamp or datetime.now()

        # Extract time features
        self._extract_time_features(features, ts)

        # Extract conversation features
        self._extract_conversation_features(features, behavior_state, history, ts)

        # Extract content features
        self._extract_content_features(features, message)

        # Extract context features
        self._extract_context_features(
            features, behavior_state, history, previous_action
        )

        return features

    def _extract_time_features(
        self,
        features: StateFeatures,
        timestamp: datetime,
    ) -> None:
        """Extract time-based features.

        Features:
        - hour_of_day: Hour normalized to [0, 1]
        - day_of_week: Day normalized to [0, 1]
        - is_weekend: Binary (Saturday/Sunday)
        - is_night: Binary (10pm - 6am)
        """
        # Hour of day: 0-23 -> [0, 1]
        features.hour_of_day = timestamp.hour / 23.0

        # Day of week: 0 (Monday) - 6 (Sunday) -> [0, 1]
        features.day_of_week = timestamp.weekday() / 6.0

        # Is weekend: Saturday (5) or Sunday (6)
        features.is_weekend = 1.0 if timestamp.weekday() >= 5 else 0.0

        # Is night: 10pm (22) - 6am
        hour = timestamp.hour
        features.is_night = 1.0 if hour >= 22 or hour < 6 else 0.0

    def _extract_conversation_features(
        self,
        features: StateFeatures,
        behavior_state: Optional[Any],
        history: Optional[List[Dict]],
        timestamp: datetime,
    ) -> None:
        """Extract conversation-based features.

        Features:
        - turn_count: Number of messages in conversation
        - message_velocity: Messages per minute
        - time_since_last: Time since last message
        - conversation_depth: How deep the conversation is
        """
        # Turn count from behavior state or history
        if behavior_state and hasattr(behavior_state, "message_count"):
            turn_count = behavior_state.message_count
        elif history:
            turn_count = len(history)
        else:
            turn_count = 0
        features.turn_count = min(turn_count / MAX_TURN_COUNT, 1.0)

        # Message velocity (messages per minute)
        velocity = 0.0
        if behavior_state and hasattr(behavior_state, "last_message_time"):
            last_time = behavior_state.last_message_time
            if isinstance(last_time, datetime):
                time_diff = (timestamp - last_time).total_seconds()
                if time_diff > 0 and turn_count > 0:
                    # Estimate velocity from recent activity
                    # If we have 5 messages in last 60 seconds, velocity = 5
                    velocity = min(turn_count / max(time_diff / 60, 1), MAX_VELOCITY)
        features.message_velocity = min(velocity / MAX_VELOCITY, 1.0)

        # Time since last message
        time_since = MAX_TIME_SINCE  # Default to max if unknown
        if behavior_state and hasattr(behavior_state, "last_message_time"):
            last_time = behavior_state.last_message_time
            if isinstance(last_time, datetime):
                time_since = (timestamp - last_time).total_seconds()
        features.time_since_last = min(time_since / MAX_TIME_SINCE, 1.0)

        # Conversation depth (estimate from history complexity)
        depth = 0
        if history:
            # Count back-and-forth exchanges
            prev_role = None
            for msg in history[-MAX_DEPTH:]:
                role = msg.get("role", "")
                if role != prev_role:
                    depth += 1
                    prev_role = role
        features.conversation_depth = min(depth / MAX_DEPTH, 1.0)

    def _extract_content_features(
        self,
        features: StateFeatures,
        message: Optional[Any],
    ) -> None:
        """Extract content-based features from message.

        Features:
        - message_length: Normalized message length
        - has_question: Binary
        - has_url: Binary
        - has_attachment: Binary
        """
        if message is None:
            return

        # Get content
        content = ""
        if hasattr(message, "content"):
            content = message.content or ""
        elif isinstance(message, dict):
            content = message.get("content", "")
        elif isinstance(message, str):
            content = message

        # Message length normalized
        features.message_length = min(len(content) / MAX_MESSAGE_LENGTH, 1.0)

        # Has question
        if self._question_pattern.search(content):
            features.has_question = 1.0

        # Has URL
        if self._url_pattern.search(content):
            features.has_url = 1.0

        # Has attachment
        if hasattr(message, "attachments") and message.attachments:
            features.has_attachment = 1.0

    def _extract_context_features(
        self,
        features: StateFeatures,
        behavior_state: Optional[Any],
        history: Optional[List[Dict]],
        previous_action: Optional[RLAction],
    ) -> None:
        """Extract context-based features.

        Features:
        - previous_action: Previous action taken (for one-hot encoding)
        - sentiment_trend: Average sentiment direction [-1, 1]
        - topic_consistency: How consistent topics are [0, 1]
        - channel_activity: Normalized channel activity level [0, 1]
        """
        # Previous action
        if previous_action is not None:
            features.previous_action = int(previous_action)

        # Sentiment trend from behavior state
        if behavior_state and hasattr(behavior_state, "sentiment_history"):
            sentiments = list(behavior_state.sentiment_history)
            if sentiments:
                # Average sentiment as trend
                avg = sum(sentiments) / len(sentiments)
                features.sentiment_trend = max(-1.0, min(1.0, avg))

        # Topic consistency (estimate from recent_topics)
        if behavior_state and hasattr(behavior_state, "recent_topics"):
            topics = list(behavior_state.recent_topics)
            if len(topics) >= 2:
                # Count unique topics - fewer unique = more consistent
                unique_topics = len(set(topics))
                # If 1 unique topic in 10 messages = 1.0, if 10 unique = 0.0
                features.topic_consistency = max(
                    0.0, 1.0 - (unique_topics - 1) / max(len(topics) - 1, 1)
                )

        # Channel activity from behavior state
        if behavior_state and hasattr(behavior_state, "message_count"):
            # Normalize activity level
            activity = behavior_state.message_count
            # Assuming ~100 messages is high activity
            features.channel_activity = min(activity / 100.0, 1.0)

    def to_legacy_state(self, features: StateFeatures) -> Tuple[int, int, int]:
        """Convert rich features back to legacy RLState tuple.

        This provides backward compatibility with the existing tabular RL system.

        Args:
            features: StateFeatures to convert

        Returns:
            Legacy (sentiment_bin, time_bin, message_count_bin) tuple
        """
        # Sentiment bin: 0-3 based on sentiment_trend
        sentiment = features.sentiment_trend
        if sentiment < -0.5:
            sentiment_bin = 0  # Very Negative
        elif sentiment < 0.0:
            sentiment_bin = 1  # Negative
        elif sentiment < 0.5:
            sentiment_bin = 2  # Neutral
        else:
            sentiment_bin = 3  # Positive

        # Time bin: 0-4 based on time_since_last (denormalize)
        time_since = features.time_since_last * MAX_TIME_SINCE
        if time_since < 10:
            time_bin = 0
        elif time_since < 30:
            time_bin = 1
        elif time_since < 60:
            time_bin = 2
        elif time_since < 300:
            time_bin = 3
        else:
            time_bin = 4

        # Message count bin: 0-3 based on turn_count (denormalize)
        count = features.turn_count * MAX_TURN_COUNT
        if count > 50:
            count_bin = 3
        elif count > 20:
            count_bin = 2
        elif count > 5:
            count_bin = 1
        else:
            count_bin = 0

        return (sentiment_bin, time_bin, count_bin)

    def from_legacy_state(
        self,
        state: Tuple[int, int, int],
        fill_defaults: bool = True,
    ) -> StateFeatures:
        """Convert legacy RLState tuple to rich features.

        This provides forward compatibility during migration.

        Args:
            state: Legacy (sentiment_bin, time_bin, message_count_bin) tuple
            fill_defaults: If True, fill other features with neutral defaults

        Returns:
            StateFeatures with values derived from legacy state
        """
        sentiment_bin, time_bin, count_bin = state

        features = StateFeatures()

        # Convert sentiment bin to trend
        sentiment_map = {0: -0.75, 1: -0.25, 2: 0.25, 3: 0.75}
        features.sentiment_trend = sentiment_map.get(sentiment_bin, 0.0)

        # Convert time bin to normalized time_since_last
        time_map = {0: 5, 1: 20, 2: 45, 3: 180, 4: 600}
        time_since = time_map.get(time_bin, 600)
        features.time_since_last = min(time_since / MAX_TIME_SINCE, 1.0)

        # Convert count bin to turn_count
        count_map = {0: 2, 1: 12, 2: 35, 3: 75}
        count = count_map.get(count_bin, 2)
        features.turn_count = min(count / MAX_TURN_COUNT, 1.0)

        if fill_defaults:
            # Fill time features with reasonable defaults
            now = datetime.now()
            features.hour_of_day = now.hour / 23.0
            features.day_of_week = now.weekday() / 6.0
            features.is_weekend = 1.0 if now.weekday() >= 5 else 0.0
            features.is_night = 1.0 if now.hour >= 22 or now.hour < 6 else 0.0

            # Content features default to 0 (unknown)
            # Context features partially filled
            features.channel_activity = features.turn_count  # Approximate

        return features
