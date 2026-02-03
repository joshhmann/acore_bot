"""Turn management and termination logic for bot-to-bot conversations."""

import random
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from services.conversation.state import ConversationState, ConversationStatus

logger = logging.getLogger(__name__)


class TurnStrategy(Enum):
    """Available turn-taking strategies."""

    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    AFFINITY_WEIGHTED = "affinity_weighted"
    ROLE_HIERARCHY = "role_hierarchy"


@dataclass
class RoleConfig:
    """Configuration for role-based turn selection."""

    role: str
    weight: float  # 0.0 to 1.0, higher = more speaking time


class TurnManager:
    """Manages turn-taking in bot-to-bot conversations."""

    def __init__(self, strategy: TurnStrategy = TurnStrategy.AFFINITY_WEIGHTED):
        self.strategy = strategy
        self.role_configs: Dict[str, RoleConfig] = {}
        self._setup_default_roles()

    def _setup_default_roles(self):
        """Setup default role weights."""
        self.role_configs = {
            "leader": RoleConfig("leader", 0.40),
            "ceo": RoleConfig("ceo", 0.40),
            "manager": RoleConfig("manager", 0.35),
            "speaker": RoleConfig("speaker", 0.30),
            "member": RoleConfig("member", 0.25),
            "employee": RoleConfig("employee", 0.25),
            "outsider": RoleConfig("outsider", 0.15),
            "newbie": RoleConfig("newbie", 0.15),
        }

    def select_next_speaker(
        self,
        state: ConversationState,
        persona_roles: Optional[Dict[str, str]] = None,
        affinity_scores: Optional[Dict[str, Dict[str, int]]] = None,
    ) -> Optional[str]:
        """Select the next speaker based on configured strategy."""

        current = state.current_speaker
        participants = state.participants

        if not participants:
            return None

        if len(participants) == 1:
            return participants[0]

        # Don't let same speaker go twice in a row (unless forced)
        available = [p for p in participants if p != current]
        if not available:
            return current  # Only one participant

        if self.strategy == TurnStrategy.ROUND_ROBIN:
            return self._round_robin(available, state)
        elif self.strategy == TurnStrategy.RANDOM:
            return self._random_selection(available)
        elif self.strategy == TurnStrategy.AFFINITY_WEIGHTED:
            return self._affinity_weighted(available, current, affinity_scores)
        elif self.strategy == TurnStrategy.ROLE_HIERARCHY:
            return self._role_hierarchy(available, persona_roles)
        else:
            return self._random_selection(available)

    def _round_robin(self, available: List[str], state: ConversationState) -> str:
        """Simple round-robin selection."""
        # Find index of last speaker
        if not state.messages:
            return available[0]

        last_speaker = state.messages[-1].speaker
        try:
            last_idx = state.participants.index(last_speaker)
            next_idx = (last_idx + 1) % len(state.participants)
            return state.participants[next_idx]
        except ValueError:
            return available[0]

    def _random_selection(self, available: List[str]) -> str:
        """Pure random selection."""
        return random.choice(available)

    def _affinity_weighted(
        self,
        available: List[str],
        current: Optional[str],
        affinity_scores: Optional[Dict[str, Dict[str, int]]],
    ) -> str:
        """Select based on relationship affinity."""

        if not current or not affinity_scores:
            return random.choice(available)

        # Get affinity scores from current speaker to others
        weights = []
        for participant in available:
            # Get affinity (default 50 if not found)
            affinity = affinity_scores.get(current, {}).get(participant, 50)
            # Add randomness (0-20)
            weight = affinity + random.randint(0, 20)
            weights.append(weight)

        # Weighted random selection
        total = sum(weights)
        if total == 0:
            return random.choice(available)

        r = random.uniform(0, total)
        cumulative = 0
        for participant, weight in zip(available, weights):
            cumulative += weight
            if r <= cumulative:
                return participant

        return available[-1]

    def _role_hierarchy(
        self, available: List[str], persona_roles: Optional[Dict[str, str]]
    ) -> str:
        """Select based on role hierarchy."""

        if not persona_roles:
            return random.choice(available)

        # Get weights for each available participant
        weights = []
        for participant in available:
            role = persona_roles.get(participant, "member")
            config = self.role_configs.get(role, RoleConfig("member", 0.25))
            # Convert weight (0-1) to selection weight (add randomness)
            weight = (config.weight * 100) + random.randint(0, 20)
            weights.append(weight)

        # Weighted random selection
        total = sum(weights)
        if total == 0:
            return random.choice(available)

        r = random.uniform(0, total)
        cumulative = 0
        for participant, weight in zip(available, weights):
            cumulative += weight
            if r <= cumulative:
                return participant

        return available[-1]

    def should_soft_warn(self, state: ConversationState) -> bool:
        """Check if we should warn about approaching turn limit."""
        return state.turn_count == state.max_turns - 2  # Warn at max-2

    def get_soft_warning_message(self) -> str:
        """Get soft warning message."""
        warnings = [
            "I should probably wrap this up soon.",
            "We're getting close to the end of our discussion.",
            "Let me think about concluding this conversation.",
            "I have a few more thoughts before we finish.",
        ]
        return random.choice(warnings)


class TerminationDetector:
    """Detects when a conversation should naturally end."""

    def __init__(self):
        self.farewell_keywords = [
            "goodbye",
            "farewell",
            "bye",
            "see you",
            "talk later",
            "until next time",
            "take care",
            "later",
            "cya",
        ]

        self.conclusion_keywords = [
            "in conclusion",
            "to summarize",
            "wrapping up",
            "final thoughts",
            "in summary",
            "to conclude",
        ]

        self.question_indicators = ["?", "what do you think", "your thoughts"]

    def should_terminate(self, state: ConversationState) -> tuple[bool, str]:
        """Check if conversation should end. Returns (should_end, reason)."""

        # Check turn limit
        if state.turn_count >= state.max_turns:
            return True, "turn_limit"

        if not state.messages:
            return False, ""

        last_message = state.messages[-1].content.lower()

        # Check for farewells
        if self._contains_farewell(last_message):
            return True, "natural_end"

        # Check for conclusion indicators
        if self._contains_conclusion(last_message):
            return True, "natural_end"

        # Check for topic exhaustion (no questions in last 3 messages)
        if state.turn_count >= 6 and not self._has_recent_questions(state, 3):
            return True, "topic_exhaustion"

        return False, ""

    def _contains_farewell(self, text: str) -> bool:
        """Check if text contains farewell keywords."""
        return any(keyword in text for keyword in self.farewell_keywords)

    def _contains_conclusion(self, text: str) -> bool:
        """Check if text contains conclusion keywords."""
        return any(keyword in text for keyword in self.conclusion_keywords)

    def _has_recent_questions(self, state: ConversationState, lookback: int) -> bool:
        """Check if recent messages contain questions."""
        recent = state.messages[-lookback:]
        for msg in recent:
            if any(
                indicator in msg.content.lower()
                for indicator in self.question_indicators
            ):
                return True
        return False

    def is_timeout(self, state: ConversationState, timeout_seconds: int) -> bool:
        """Check if conversation has timed out."""
        from datetime import datetime

        if not state.messages:
            return False

        last_message_time = state.messages[-1].timestamp
        elapsed = (datetime.now() - last_message_time).total_seconds()
        return elapsed > timeout_seconds


# Convenience function
def create_turn_manager(strategy: str = "affinity_weighted") -> TurnManager:
    """Factory function to create turn manager."""
    strategy_map = {
        "round_robin": TurnStrategy.ROUND_ROBIN,
        "random": TurnStrategy.RANDOM,
        "affinity_weighted": TurnStrategy.AFFINITY_WEIGHTED,
        "role_hierarchy": TurnStrategy.ROLE_HIERARCHY,
    }

    turn_strategy = strategy_map.get(strategy, TurnStrategy.AFFINITY_WEIGHTED)
    return TurnManager(strategy=turn_strategy)
