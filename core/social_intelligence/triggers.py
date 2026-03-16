"""Trigger Decision Learning Loop.

Integrates contextual bandit learning into proactive engagement decisions.
Learns optimal timing and actions for engaging users based on outcomes.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from core.social_intelligence.learning.bandit import (
    BanditContext,
    LinUCB,
    UserBanditManager,
)

logger = logging.getLogger(__name__)


@dataclass
class TriggerDecision:
    """Decision about whether to engage."""

    should_engage: bool
    action: str
    confidence: float
    reason: str
    exploration: bool = False


class TriggerLearningLoop:
    """Learning loop for proactive engagement decisions.

    Uses contextual bandit to learn:
    - When to engage (timing)
    - How to engage (action type)
    - What works for each user

    Respects user preferences:
    - Mute/quiet settings
    - Explicit feedback
    - Historical response patterns
    """

    def __init__(
        self,
        bandit_manager: UserBanditManager | None = None,
        exploration_rate: float = 0.2,
        min_confidence: float = 0.5,
    ):
        self.bandit_manager = bandit_manager or UserBanditManager()
        self.exploration_rate = exploration_rate
        self.min_confidence = min_confidence

        # Pending decisions awaiting outcome
        self._pending_decisions: dict[str, dict[str, Any]] = {}

    def should_proactively_engage(
        self,
        user_id: str,
        social_context: dict[str, Any],
        user_preferences: dict[str, Any] | None = None,
    ) -> TriggerDecision:
        """Decide whether to proactively engage user.

        Args:
            user_id: User to potentially engage
            social_context: Current social context
            user_preferences: User's mute/quiet settings

        Returns:
            TriggerDecision with engagement recommendation
        """
        user_preferences = user_preferences or {}

        # Check if user has muted or set quiet mode
        if user_preferences.get("muted", False):
            return TriggerDecision(
                should_engage=False,
                action="wait",
                confidence=1.0,
                reason="User is muted",
            )

        if user_preferences.get("quiet_mode", False):
            return TriggerDecision(
                should_engage=False,
                action="wait",
                confidence=1.0,
                reason="User has quiet mode enabled",
            )

        # Get user's bandit
        bandit = self.bandit_manager.get_bandit(user_id)

        # Build context
        context = self._build_context(social_context)

        # Get bandit recommendation
        action, confidence = bandit.select_action(context)

        # Decide whether to explore
        import random

        is_exploration = random.random() < self.exploration_rate

        if is_exploration:
            # Random action for exploration
            action = random.choice(list(bandit.ACTIONS))
            confidence = 0.5
            reason = f"Exploration: trying '{action}'"
        else:
            reason = f"Bandit selected '{action}' (confidence: {confidence:.2f})"

        # Determine if we should engage
        should_engage = action != "wait" and confidence >= self.min_confidence

        decision = TriggerDecision(
            should_engage=should_engage,
            action=action,
            confidence=confidence,
            reason=reason,
            exploration=is_exploration,
        )

        # Store pending decision for later reward calculation
        if should_engage:
            self._pending_decisions[user_id] = {
                "timestamp": time.time(),
                "action": action,
                "context": context,
                "decision": decision,
            }

        return decision

    def _build_context(self, social_context: dict[str, Any]) -> BanditContext:
        """Build bandit context from social context."""
        return BanditContext(
            sentiment=social_context.get("sentiment", 0.0),
            time_of_day=social_context.get("time_of_day", 12),
            relationship_depth=social_context.get("relationship_depth", 0.5),
            conversation_phase=social_context.get("conversation_phase", 0.5),
            user_active=social_context.get("user_active", True),
            recent_engagement=social_context.get("recent_engagement", 0.5),
        )

    def record_outcome(
        self,
        user_id: str,
        user_responded: bool,
        response_time_seconds: float | None = None,
        response_quality: float = 0.5,
        user_feedback: float | None = None,
    ) -> None:
        """Record outcome of engagement and update bandit.

        Args:
            user_id: User who was engaged
            user_responded: Did user respond
            response_time_seconds: How long until response
            response_quality: Quality of response
            user_feedback: Explicit feedback if provided (-1 to 1)
        """
        if user_id not in self._pending_decisions:
            logger.warning(f"No pending decision for user {user_id}")
            return

        pending = self._pending_decisions[user_id]
        action = pending["action"]
        context = pending["context"]

        # Calculate reward
        bandit = self.bandit_manager.get_bandit(user_id)

        if user_feedback is not None:
            # Use explicit feedback
            reward = user_feedback
        else:
            # Calculate from behavior
            reward = bandit.calculate_reward(
                user_responded=user_responded,
                response_time_seconds=response_time_seconds,
                response_quality=response_quality,
            )

        # Update bandit
        bandit.update(action, context, reward)

        # Remove pending decision
        del self._pending_decisions[user_id]

        logger.debug(
            f"Updated bandit for {user_id}: action={action}, reward={reward:.2f}"
        )

    def record_explicit_feedback(
        self,
        user_id: str,
        feedback: float,  # -1 (bad) to 1 (good)
    ) -> None:
        """Record explicit user feedback about engagement.

        Args:
            user_id: User providing feedback
            feedback: Feedback score (-1 to 1)
        """
        self.record_outcome(
            user_id=user_id,
            user_responded=True,
            user_feedback=feedback,
        )

    def get_user_stats(self, user_id: str) -> dict[str, Any]:
        """Get learning statistics for a user."""
        bandit = self.bandit_manager.get_bandit(user_id)
        return bandit.get_performance()

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get learning statistics for all users."""
        return self.bandit_manager.get_all_stats()

    def save_state(self) -> None:
        """Save all bandit states."""
        self.bandit_manager.save_all()
        logger.info("Saved bandit states")

    def adjust_exploration(self, user_id: str, interactions: int) -> None:
        """Adjust exploration rate based on user interaction count.

        Reduces exploration as we learn more about the user.

        Args:
            user_id: User to adjust for
            interactions: Number of interactions so far
        """
        bandit = self.bandit_manager.get_bandit(user_id)

        # Gradually reduce exploration
        if interactions < 50:
            # High exploration for new users
            self.exploration_rate = 0.3
        elif interactions < 200:
            # Medium exploration
            self.exploration_rate = 0.2
        elif interactions < 500:
            # Low exploration
            self.exploration_rate = 0.1
        else:
            # Minimal exploration for well-known users
            self.exploration_rate = 0.05

        logger.debug(
            f"Adjusted exploration for {user_id}: {self.exploration_rate:.2f} "
            f"({interactions} interactions)"
        )


# Global instance
trigger_learning: TriggerLearningLoop | None = None


def get_trigger_learning() -> TriggerLearningLoop:
    """Get global trigger learning instance."""
    global trigger_learning
    if trigger_learning is None:
        trigger_learning = TriggerLearningLoop()
    return trigger_learning
