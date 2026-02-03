# Task 5 Implementation Guide: Turn Management + Termination Logic

## Overview
Implement turn-taking strategies and conversation termination detection.

## Files to Create

### 1. `services/conversation/turn_manager.py`

```python
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
        affinity_scores: Optional[Dict[str, Dict[str, int]]] = None
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
    
    def _round_robin(
        self,
        available: List[str],
        state: ConversationState
    ) -> str:
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
        affinity_scores: Optional[Dict[str, Dict[str, int]]]
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
        self,
        available: List[str],
        persona_roles: Optional[Dict[str, str]]
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
            "I have a few more thoughts before we finish."
        ]
        return random.choice(warnings)


class TerminationDetector:
    """Detects when a conversation should naturally end."""
    
    def __init__(self):
        self.farewell_keywords = [
            "goodbye", "farewell", "bye", "see you", "talk later",
            "until next time", "take care", "later", "cya"
        ]
        
        self.conclusion_keywords = [
            "in conclusion", "to summarize", "wrapping up",
            "final thoughts", "in summary", "to conclude"
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
            if any(indicator in msg.content.lower() for indicator in self.question_indicators):
                return True
        return False
    
    def is_timeout(
        self,
        state: ConversationState,
        timeout_seconds: int
    ) -> bool:
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
```

### 2. `tests/unit/test_turn_management.py`

```python
"""Tests for turn management and termination logic."""

import pytest
from datetime import datetime, timedelta

from services.conversation.turn_manager import (
    TurnManager, TurnStrategy, TerminationDetector, create_turn_manager
)
from services.conversation.state import ConversationState, ConversationStatus, Message


class TestTurnManager:
    def test_round_robin_selection(self):
        manager = TurnManager(strategy=TurnStrategy.ROUND_ROBIN)
        
        state = ConversationState(
            conversation_id="test",
            participants=["bot1", "bot2", "bot3"],
            status=ConversationStatus.ACTIVE,
            current_speaker="bot1"
        )
        
        # Add a message from bot1
        state.messages.append(Message("bot1", "Hello", datetime.now(), 1))
        
        next_speaker = manager.select_next_speaker(state)
        assert next_speaker == "bot2"
    
    def test_random_selection(self):
        manager = TurnManager(strategy=TurnStrategy.RANDOM)
        
        state = ConversationState(
            conversation_id="test",
            participants=["bot1", "bot2", "bot3"],
            status=ConversationStatus.ACTIVE,
            current_speaker="bot1"
        )
        
        next_speaker = manager.select_next_speaker(state)
        assert next_speaker in ["bot2", "bot3"]
        assert next_speaker != "bot1"
    
    def test_affinity_weighted(self):
        manager = TurnManager(strategy=TurnStrategy.AFFINITY_WEIGHTED)
        
        state = ConversationState(
            conversation_id="test",
            participants=["bot1", "bot2", "bot3"],
            status=ConversationStatus.ACTIVE,
            current_speaker="bot1"
        )
        
        # High affinity with bot2, low with bot3
        affinity_scores = {
            "bot1": {"bot2": 90, "bot3": 10}
        }
        
        # Run multiple times to verify weighting (bot2 should be selected more often)
        selections = []
        for _ in range(100):
            speaker = manager.select_next_speaker(state, affinity_scores=affinity_scores)
            selections.append(speaker)
        
        bot2_count = selections.count("bot2")
        bot3_count = selections.count("bot3")
        
        # bot2 should be selected significantly more often
        assert bot2_count > bot3_count * 2
    
    def test_role_hierarchy(self):
        manager = TurnManager(strategy=TurnStrategy.ROLE_HIERARCHY)
        
        state = ConversationState(
            conversation_id="test",
            participants=["ceo", "manager", "employee"],
            status=ConversationStatus.ACTIVE,
            current_speaker="manager"
        )
        
        persona_roles = {
            "ceo": "ceo",
            "manager": "manager",
            "employee": "employee"
        }
        
        # Run multiple times
        selections = []
        for _ in range(100):
            speaker = manager.select_next_speaker(state, persona_roles=persona_roles)
            selections.append(speaker)
        
        # CEO should speak most often (40% weight vs 35% and 25%)
        ceo_count = selections.count("ceo")
        assert ceo_count > 30  # Should be around 40%


class TestTerminationDetector:
    def test_farewell_detection(self):
        detector = TerminationDetector()
        
        state = ConversationState(
            conversation_id="test",
            participants=["bot1", "bot2"],
            status=ConversationStatus.ACTIVE,
            turn_count=5
        )
        
        # No farewell
        state.messages.append(Message("bot1", "That's interesting", datetime.now(), 5))
        should_end, reason = detector.should_terminate(state)
        assert not should_end
        
        # With farewell
        state.messages.append(Message("bot2", "Well, goodbye then!", datetime.now(), 6))
        should_end, reason = detector.should_terminate(state)
        assert should_end
        assert reason == "natural_end"
    
    def test_turn_limit(self):
        detector = TerminationDetector()
        
        state = ConversationState(
            conversation_id="test",
            participants=["bot1", "bot2"],
            status=ConversationStatus.ACTIVE,
            turn_count=10,
            max_turns=10
        )
        
        should_end, reason = detector.should_terminate(state)
        assert should_end
        assert reason == "turn_limit"
    
    def test_timeout(self):
        detector = TerminationDetector()
        
        state = ConversationState(
            conversation_id="test",
            participants=["bot1", "bot2"],
            status=ConversationStatus.ACTIVE
        )
        
        # Old message
        old_time = datetime.now() - timedelta(seconds=301)
        state.messages.append(Message("bot1", "Hello", old_time, 1))
        
        is_timeout = detector.is_timeout(state, timeout_seconds=300)
        assert is_timeout


class TestTurnManagerFactory:
    def test_create_turn_manager(self):
        manager = create_turn_manager("round_robin")
        assert manager.strategy == TurnStrategy.ROUND_ROBIN
        
        manager = create_turn_manager("affinity_weighted")
        assert manager.strategy == TurnStrategy.AFFINITY_WEIGHTED
        
        # Invalid strategy defaults to affinity_weighted
        manager = create_turn_manager("invalid")
        assert manager.strategy == TurnStrategy.AFFINITY_WEIGHTED
```

## Integration with Orchestrator

```python
# In BotConversationOrchestrator.__init__:
from services.conversation.turn_manager import create_turn_manager, TerminationDetector

self.turn_manager = create_turn_manager("affinity_weighted")
self.termination_detector = TerminationDetector()

# In _run_conversation loop:
next_speaker = self.turn_manager.select_next_speaker(
    state,
    persona_roles=self._get_persona_roles(state.participants),
    affinity_scores=self._get_affinity_scores(state.participants)
)

# Check termination
should_end, reason = self.termination_detector.should_terminate(state)
if should_end:
    state.termination_reason = reason
    break
```

## Verification

```bash
# Run tests
uv run pytest tests/unit/test_turn_management.py -v
```
