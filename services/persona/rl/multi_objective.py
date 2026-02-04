"""Multi-objective reward decomposition for RL.

This module implements multi-objective RL (MORL) reward decomposition,
breaking down the single reward signal into multiple components that
the agent can optimize simultaneously.

Components:
- Engagement: Message length, response time, emoji reactions
- Quality: Sentiment positivity, conversation coherence
- Affinity: Relationship score change
- Curiosity: Topic novelty, question diversity
"""

import math
import re
from dataclasses import dataclass
from typing import Dict, Optional, Any, Set
from collections import deque

import discord

from services.persona.rl.constants import (
    REWARD_WEIGHT_ENGAGEMENT,
    REWARD_WEIGHT_QUALITY,
    REWARD_WEIGHT_AFFINITY,
    REWARD_WEIGHT_CURIOSITY,
    REWARD_CLIP_COMPONENT,
    REWARD_CLIP_TOTAL,
    RL_REWARD_SPEED_THRESHOLD,
    RL_REWARD_LONG_MSG_CHAR,
)


@dataclass
class RewardComponents:
    """Container for individual reward components and total reward.

    Attributes:
        engagement: Engagement component score [-5, 5]
        quality: Quality component score [-5, 5]
        affinity: Affinity component score [-5, 5]
        curiosity: Curiosity component score [-5, 5]
        total: Weighted total reward [-10, 10]
    """

    engagement: float
    quality: float
    affinity: float
    curiosity: float
    total: float


class MultiObjectiveReward:
    """Multi-objective reward decomposition calculator.

        Breaks down a single reward signal into multiple components that
    can be optimized simultaneously. Each component focuses on a different
        aspect of conversation quality and user engagement.

        Attributes:
            weights: Dictionary mapping component names to weights (sum to 1.0)
            _topic_history: Tracks recent topics for novelty calculation
            _question_history: Tracks recent questions for diversity calculation
    """

    # Default weights (must sum to 1.0)
    DEFAULT_WEIGHTS = {
        "engagement": REWARD_WEIGHT_ENGAGEMENT,
        "quality": REWARD_WEIGHT_QUALITY,
        "affinity": REWARD_WEIGHT_AFFINITY,
        "curiosity": REWARD_WEIGHT_CURIOSITY,
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """Initialize the multi-objective reward calculator.

        Args:
            weights: Optional custom weights dictionary. If provided,
                weights will be normalized to sum to 1.0.
        """
        if weights is None:
            self.weights = self.DEFAULT_WEIGHTS.copy()
        else:
            # Normalize weights to sum to 1.0
            total = sum(weights.values())
            if total == 0:
                self.weights = self.DEFAULT_WEIGHTS.copy()
            else:
                self.weights = {k: v / total for k, v in weights.items()}

        # Topic history for novelty tracking (channel_id -> deque of topics)
        self._topic_history: Dict[int, deque] = {}

        # Question history for diversity tracking (channel_id -> deque of questions)
        self._question_history: Dict[int, deque] = {}

        # Maximum history size for novelty/diversity calculations
        self._max_history_size = 50

    def calculate(
        self,
        message: discord.Message,
        response: str,
        state: Any,
        affinity_delta: float = 0.0,
        latency: float = 0.0,
    ) -> RewardComponents:
        """Calculate multi-objective reward components.

        Args:
            message: The Discord message that triggered the response
            response: The bot's response text
            state: BehaviorState containing conversation context
            affinity_delta: Change in user affinity score
            latency: Response latency in seconds

        Returns:
            RewardComponents containing all individual components and total
        """
        # Calculate each component
        engagement = self._calculate_engagement(message, response, latency)
        quality = self._calculate_quality(message, response, state)
        affinity = self._calculate_affinity(affinity_delta)
        curiosity = self._calculate_curiosity(message, state)

        # Clip individual components to [-5, 5]
        engagement = max(-REWARD_CLIP_COMPONENT, min(REWARD_CLIP_COMPONENT, engagement))
        quality = max(-REWARD_CLIP_COMPONENT, min(REWARD_CLIP_COMPONENT, quality))
        affinity = max(-REWARD_CLIP_COMPONENT, min(REWARD_CLIP_COMPONENT, affinity))
        curiosity = max(-REWARD_CLIP_COMPONENT, min(REWARD_CLIP_COMPONENT, curiosity))

        # Calculate weighted total
        total = (
            engagement * self.weights["engagement"]
            + quality * self.weights["quality"]
            + affinity * self.weights["affinity"]
            + curiosity * self.weights["curiosity"]
        )

        # Scale total to [-10, 10] range (components are [-5, 5], weighted sum is [-5, 5])
        # Multiply by 2 to get [-10, 10] range
        total = total * 2.0

        # Clip total to [-10, 10]
        total = max(-REWARD_CLIP_TOTAL, min(REWARD_CLIP_TOTAL, total))

        return RewardComponents(
            engagement=engagement,
            quality=quality,
            affinity=affinity,
            curiosity=curiosity,
            total=total,
        )

    def _calculate_engagement(
        self, message: discord.Message, response: str, latency: float
    ) -> float:
        """Calculate engagement reward component.

        Factors:
        - Message length (longer messages = higher engagement)
        - Response time (faster responses = bonus)
        - Emoji reactions (positive signal)

        Args:
            message: The user's message
            response: The bot's response
            latency: Response latency in seconds

        Returns:
            Engagement score [-5, 5]
        """
        reward = 0.0

        # Message length score (0 to 2.5)
        # Longer messages indicate higher engagement
        msg_length = len(message.content) if hasattr(message, "content") else 0
        if msg_length >= RL_REWARD_LONG_MSG_CHAR:
            reward += 2.5
        elif msg_length > 50:
            # Linear scaling between 50 and RL_REWARD_LONG_MSG_CHAR chars
            reward += 1.0 + (msg_length - 50) / (RL_REWARD_LONG_MSG_CHAR - 50) * 1.5
        elif msg_length > 10:
            # Small reward for any meaningful message
            reward += 0.5

        # Response time bonus (-1.0 to 1.0)
        # Faster responses get bonus, slow responses get penalty
        if latency < RL_REWARD_SPEED_THRESHOLD:
            reward += 1.0
        elif latency < RL_REWARD_SPEED_THRESHOLD * 2:
            reward += 0.5
        elif latency > RL_REWARD_SPEED_THRESHOLD * 5:
            reward -= 1.0

        # Emoji reaction detection in response (0 to 1.5)
        # If response contains positive emojis, it's engaging
        emoji_count = self._count_emojis(response)
        if emoji_count > 0:
            reward += min(1.5, emoji_count * 0.5)

        # Question detection (0 to 1.0)
        # Asking questions shows engagement
        if "?" in message.content if hasattr(message, "content") else False:
            reward += 1.0

        return reward

    def _calculate_quality(
        self, message: discord.Message, response: str, state: Any
    ) -> float:
        """Calculate quality reward component.

        Factors:
        - Sentiment positivity (positive sentiment = reward)
        - Topic consistency (staying on topic = reward)
        - Grammar/coherence indicators

        Args:
            message: The user's message
            response: The bot's response
            state: BehaviorState containing sentiment history

        Returns:
            Quality score [-5, 5]
        """
        reward = 0.0

        # Sentiment-based reward (-2.5 to 2.5)
        # Use sentiment from state if available
        if hasattr(state, "sentiment_history") and state.sentiment_history:
            current_sentiment = state.sentiment_history[-1]
            # Scale sentiment (-1 to 1) to reward (-2.5 to 2.5)
            reward += current_sentiment * 2.5

        # Topic consistency check (0 to 1.5)
        # Reward for maintaining conversation thread
        if hasattr(state, "recent_topics") and state.recent_topics:
            current_topics = self._extract_topics(
                message.content if hasattr(message, "content") else ""
            )
            recent_topics = set(state.recent_topics)

            if current_topics and recent_topics:
                overlap = current_topics & recent_topics
                if overlap:
                    # Reward for staying on topic
                    consistency_ratio = len(overlap) / len(current_topics)
                    reward += consistency_ratio * 1.5

        # Response quality indicators (0 to 1.0)
        # Check if response is substantial (not just "ok", "yes", etc.)
        response_lower = response.lower().strip()
        short_responses = {"ok", "yes", "no", "yeah", "nah", "k", "yep", "nope"}
        if response_lower not in short_responses and len(response) > 20:
            reward += 1.0

        # Penalty for very short or empty responses
        if len(response) < 10:
            reward -= 1.0

        return reward

    def _calculate_affinity(self, affinity_delta: float) -> float:
        """Calculate affinity reward component.

        Uses tanh to smoothly map affinity changes to reward range.
        Large positive changes give diminishing returns,
        large negative changes give diminishing penalties.

        Args:
            affinity_delta: Change in user affinity score

        Returns:
            Affinity score [-5, 5]
        """
        # Use tanh to smoothly map affinity changes
        # tanh(affinity_delta * 0.1) * 5.0 gives:
        # - Small changes: roughly linear mapping
        # - Large changes: diminishing returns
        # Range: [-5, 5]
        return math.tanh(affinity_delta * 0.1) * 5.0

    def _calculate_curiosity(self, message: discord.Message, state: Any) -> float:
        """Calculate curiosity reward component.

        Factors:
        - Topic novelty (new topics = reward for exploration)
        - Question diversity (asking different types of questions = reward)
        - Penalty for repeating same topics

        Args:
            message: The user's message
            state: BehaviorState containing conversation history

        Returns:
            Curiosity score [-5, 5]
        """
        reward = 0.0
        channel_id = message.channel.id if hasattr(message, "channel") else 0

        # Extract current topics
        content = message.content if hasattr(message, "content") else ""
        current_topics = self._extract_topics(content)

        # Initialize topic history for this channel
        if channel_id not in self._topic_history:
            self._topic_history[channel_id] = deque(maxlen=self._max_history_size)

        topic_history = self._topic_history[channel_id]

        # Topic novelty calculation
        if current_topics:
            # Check which topics are new vs. repeated
            history_set = set(topic_history)
            new_topics = current_topics - history_set
            repeated_topics = current_topics & history_set

            # Reward for new topics (exploration)
            if new_topics:
                novelty_reward = min(3.0, len(new_topics) * 1.5)
                reward += novelty_reward

            # Penalty for repeating topics (unless it's a follow-up)
            if repeated_topics and len(current_topics) == len(repeated_topics):
                # All topics are repeats
                reward -= 1.5

            # Update history with current topics
            for topic in current_topics:
                if topic not in topic_history:
                    topic_history.append(topic)

        # Question diversity
        questions = self._extract_questions(content)
        if questions:
            # Initialize question history for this channel
            if channel_id not in self._question_history:
                self._question_history[channel_id] = deque(
                    maxlen=self._max_history_size
                )

            question_history = self._question_history[channel_id]

            # Check for question diversity
            history_questions = set(question_history)
            new_questions = [q for q in questions if q not in history_questions]

            if new_questions:
                # Reward for asking novel questions
                reward += min(2.0, len(new_questions) * 1.0)

            # Update question history
            for q in questions:
                if q not in question_history:
                    question_history.append(q)

        # Curiosity level bonus from state
        if hasattr(state, "curiosity_level"):
            curiosity_map = {
                "low": -0.5,
                "medium": 0.0,
                "high": 1.0,
                "maximum": 2.0,
            }
            reward += curiosity_map.get(state.curiosity_level, 0.0)

        return reward

    def _count_emojis(self, text: str) -> int:
        """Count emoji characters in text.

        Args:
            text: Text to analyze

        Returns:
            Number of emoji characters found
        """
        # Simple emoji detection using Unicode ranges
        emoji_pattern = re.compile(
            "["
            "\U0001f600-\U0001f64f"  # emoticons
            "\U0001f300-\U0001f5ff"  # symbols & pictographs
            "\U0001f680-\U0001f6ff"  # transport & map symbols
            "\U0001f1e0-\U0001f1ff"  # flags
            "\U00002702-\U000027b0"
            "\U000024c2-\U0001f251"
            "]+",
            flags=re.UNICODE,
        )
        matches = emoji_pattern.findall(text)
        return len(matches)

    def _extract_topics(self, content: str) -> Set[str]:
        """Extract topics from message content.

        Uses keyword matching to identify conversation topics.

        Args:
            content: Message content

        Returns:
            Set of detected topics
        """
        if not content:
            return set()

        content_lower = content.lower()
        topics = set()

        # Topic patterns (same as in behavior.py)
        topic_patterns = {
            "gaming": r"\b(games?|gaming|play(ed|ing)?|gameplay|fps|rpg|mmo|steam|epic|nintendo|playstation|xbox)\b",
            "technology": r"\b(tech|software|hardware|computer|programming|code|app|phone|device|ai|machine learning)\b",
            "movies": r"\b(movie|film|cinema|watch(ed|ing)?|netflix|hbo|disney\+|stream|director|actor)\b",
            "music": r"\b(music|song|album|artist|band|concert|listen|spotify|apple music|playlist)\b",
            "sports": r"\b(sport|game|match|team|player|score|win|lose|championship|league|football|basketball|baseball)\b",
            "food": r"\b(food|eat|cooking|recipe|restaurant|meal|breakfast|lunch|dinner|delicious|taste)\b",
            "travel": r"\b(travel|trip|vacation|flight|hotel|visit|country|city|tour|destination)\b",
            "work": r"\b(work|job|career|office|boss|colleague|meeting|project|deadline|salary|hire)\b",
            "school": r"\b(school|college|university|class|study|exam|homework|degree|professor|student)\b",
            "health": r"\b(health|doctor|hospital|medicine|exercise|fitness|diet|sick|pain|treatment)\b",
            "relationships": r"\b(relationship|dating|love|friend|family|married|single|breakup|divorce)\b",
            "money": r"\b(money|cash|dollar|price|cost|expensive|cheap|buy|sell|invest|budget)\b",
            "weather": r"\b(weather|rain|snow|sunny|cold|hot|temperature|climate|forecast)\b",
            "pets": r"\b(pet|dog|cat|animal|puppy|kitten|vet|leash|toy|treat)\b",
            "books": r"\b(book|novel|read|reading|author|story|chapter|library|literature)\b",
            "politics": r"\b(politics|government|election|president|policy|vote|democrat|republican|congress)\b",
            "religion": r"\b(god|church|religion|pray|faith|bible|jesus|christian|muslim|islam)\b",
        }

        for topic, pattern in topic_patterns.items():
            if re.search(pattern, content_lower, re.IGNORECASE):
                topics.add(topic)

        return topics

    def _extract_questions(self, content: str) -> list:
        """Extract questions from message content.

        Args:
            content: Message content

        Returns:
            List of extracted question types
        """
        if not content:
            return []

        content_lower = content.lower()
        questions = []

        # Question type patterns
        question_patterns = {
            "what": r"\bwhat\b",
            "how": r"\bhow\b",
            "why": r"\bwhy\b",
            "when": r"\bwhen\b",
            "where": r"\bwhere\b",
            "who": r"\bwho\b",
            "which": r"\bwhich\b",
            "opinion": r"\b(think|thoughts|opinion|feel about|believe)\b",
            "preference": r"\b(favorite|prefer|like better|best)\b",
        }

        for q_type, pattern in question_patterns.items():
            if re.search(pattern, content_lower, re.IGNORECASE):
                questions.append(q_type)

        return questions

    def get_weights(self) -> Dict[str, float]:
        """Get current component weights.

        Returns:
            Dictionary of component names to weights
        """
        return self.weights.copy()

    def set_weights(self, weights: Dict[str, float]) -> None:
        """Set component weights (automatically normalized).

        Args:
            weights: Dictionary of component names to weights
        """
        total = sum(weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in weights.items()}

    def reset_history(self, channel_id: Optional[int] = None) -> None:
        """Reset topic and question history.

        Args:
            channel_id: Specific channel to reset, or None for all channels
        """
        if channel_id is not None:
            self._topic_history.pop(channel_id, None)
            self._question_history.pop(channel_id, None)
        else:
            self._topic_history.clear()
            self._question_history.clear()
