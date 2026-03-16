"""Migration layer from behavior.py to Social Intelligence Layer.

Provides backward-compatible APIs while migrating to SIL.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
import warnings

# SIL imports
from core.social_intelligence.modes import CognitiveMode, get_mode_config
from core.social_intelligence.router import ModeRouter
from core.social_intelligence.triggers import get_trigger_learning
from core.social_intelligence.adaptation import get_adaptation_manager
from core.social_intelligence.feedback import get_feedback_collector
from core.social_intelligence.config import get_config_manager

logger = logging.getLogger(__name__)


class BehaviorMigrationWrapper:
    """Wrapper that bridges old behavior.py APIs to new SIL system.

    This provides backward compatibility while gradually migrating
    functionality to the Social Intelligence Layer.
    """

    def __init__(self):
        self._mode_router = ModeRouter()
        self._config_manager = get_config_manager()
        self._migration_warnings = True

    def get_mood(self, message: str, persona_id: str) -> dict[str, Any]:
        """Get mood - migrated to use SIL sentiment analysis.

        DEPRECATED: Use SIL sentiment directly in new code.
        """
        if self._migration_warnings:
            warnings.warn(
                "get_mood() is deprecated. Use SIL sentiment analysis.",
                DeprecationWarning,
                stacklevel=2,
            )

        # Use SIL mode router to detect mood context
        decision = self._mode_router.select_mode(
            event={"content": message}, social_context={"persona_id": persona_id}
        )

        # Map mode to mood
        mood_map = {
            CognitiveMode.CREATIVE: "creative",
            CognitiveMode.LOGIC: "analytical",
            CognitiveMode.FACILITATOR: "neutral",
        }

        return {
            "mood": mood_map.get(decision.mode, "neutral"),
            "confidence": decision.confidence,
            "source": "sil_migration",
        }

    def get_framework_blend(
        self,
        message: str,
        persona_id: str,
        user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get framework blend - migrated to use SIL modes.

        DEPRECATED: Use SIL mode selection directly.
        """
        if self._migration_warnings:
            warnings.warn(
                "get_framework_blend() is deprecated. Use SIL mode selection.",
                DeprecationWarning,
                stacklevel=2,
            )

        # Use SIL to select mode
        decision = self._mode_router.select_mode(
            event={"content": message},
            social_context={
                "persona_id": persona_id,
                "user_id": user_id,
            },
        )

        # Convert mode to framework blend
        framework_map = {
            CognitiveMode.CREATIVE: {
                "assistant": 0.3,
                "creative": 0.7,
                "logic": 0.0,
            },
            CognitiveMode.LOGIC: {
                "assistant": 0.3,
                "creative": 0.0,
                "logic": 0.7,
            },
            CognitiveMode.FACILITATOR: {
                "assistant": 0.7,
                "creative": 0.15,
                "logic": 0.15,
            },
        }

        return {
            "blend": framework_map.get(
                decision.mode, framework_map[CognitiveMode.FACILITATOR]
            ),
            "mode": decision.mode.name.lower(),
            "confidence": decision.confidence,
            "source": "sil_migration",
        }

    def should_proactively_engage(
        self,
        user_id: str,
        channel_id: str,
        context: dict[str, Any],
    ) -> bool:
        """Check if should proactively engage - migrated to SIL triggers.

        DEPRECATED: Use TriggerLearningLoop directly.
        """
        if self._migration_warnings:
            warnings.warn(
                "should_proactively_engage() is deprecated. Use SIL triggers.",
                DeprecationWarning,
                stacklevel=2,
            )

        trigger = get_trigger_learning()

        # Get user config for preferences
        config = self._config_manager.get_user_config(user_id)

        decision = trigger.should_proactively_engage(
            user_id=user_id,
            social_context=context,
            user_preferences={
                "muted": not config.enable_proactive_engagement,
                "quiet_mode": config.quiet_hours is not None,
            },
        )

        return decision.should_engage

    def record_feedback(
        self,
        user_id: str,
        feedback_type: str,
        score: float,
        context: Optional[dict] = None,
    ) -> None:
        """Record feedback - migrated to SIL feedback collector.

        DEPRECATED: Use FeedbackCollector directly.
        """
        if self._migration_warnings:
            warnings.warn(
                "record_feedback() is deprecated. Use SIL feedback collector.",
                DeprecationWarning,
                stacklevel=2,
            )

        collector = get_feedback_collector()

        if feedback_type == "explicit":
            collector.add_explicit_feedback(
                user_id=user_id, score=score, context=context or {}
            )
        else:
            # Map old feedback types to new
            collector.collect_from_message(
                user_id=user_id, message=context.get("message", ""), context=context
            )

    def get_user_preferences(self, user_id: str) -> dict[str, Any]:
        """Get user preferences - migrated to SIL adaptation manager.

        DEPRECATED: Use AdaptationManager directly.
        """
        if self._migration_warnings:
            warnings.warn(
                "get_user_preferences() is deprecated. Use SIL adaptation manager.",
                DeprecationWarning,
                stacklevel=2,
            )

        manager = get_adaptation_manager()
        prefs = manager.get_preferences(user_id)

        return {
            "optimal_hours": prefs.get_best_hours(),
            "preferred_mode": prefs.get_preferred_mode(),
            "trigger_sensitivity": prefs.trigger_sensitivity,
            "total_interactions": prefs.total_interactions,
            "source": "sil_migration",
        }

    def disable_migration_warnings(self) -> None:
        """Disable deprecation warnings (for production)."""
        self._migration_warnings = False

    def enable_migration_warnings(self) -> None:
        """Enable deprecation warnings (for development)."""
        self._migration_warnings = True


# Global migration wrapper instance
_migration_wrapper: Optional[BehaviorMigrationWrapper] = None


def get_migration_wrapper() -> BehaviorMigrationWrapper:
    """Get global migration wrapper instance."""
    global _migration_wrapper
    if _migration_wrapper is None:
        _migration_wrapper = BehaviorMigrationWrapper()
    return _migration_wrapper


def migrate_user_data(user_id: str) -> bool:
    """Migrate user data from old format to SIL format.

    Args:
        user_id: User to migrate

    Returns:
        True if migration successful
    """
    try:
        # Load old user data (if exists)
        old_data_path = f"data/users/{user_id}.json"
        import os
        import json

        if not os.path.exists(old_data_path):
            logger.info(f"No old data to migrate for user {user_id}")
            return True

        with open(old_data_path, "r") as f:
            old_data = json.load(f)

        # Migrate to SIL format
        config_manager = get_config_manager()
        adaptation_manager = get_adaptation_manager()

        # Migrate config
        user_config = config_manager.get_user_config(user_id)

        if "preferences" in old_data:
            prefs = old_data["preferences"]
            if "proactive_enabled" in prefs:
                user_config.enable_proactive_engagement = prefs["proactive_enabled"]
            if "learning_enabled" in prefs:
                user_config.enable_learning = prefs["learning_enabled"]

        config_manager.save_user_config(user_id, user_config)

        # Migrate interaction history
        if "interactions" in old_data:
            for interaction in old_data["interactions"]:
                adaptation_manager.record_interaction(
                    user_id=user_id,
                    timestamp=interaction.get("timestamp", 0),
                    mode=interaction.get("mode", "creative"),
                    positive=interaction.get("positive", True),
                )

        logger.info(f"Successfully migrated user {user_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to migrate user {user_id}: {e}")
        return False


def check_migration_needed(user_id: str) -> bool:
    """Check if user needs migration.

    Args:
        user_id: User to check

    Returns:
        True if migration needed
    """
    import os

    old_path = f"data/users/{user_id}.json"
    new_path = f"data/social_intelligence/config/users/{user_id}.yaml"

    # Migration needed if old exists but new doesn't
    return os.path.exists(old_path) and not os.path.exists(new_path)


# Deprecation notices for old functions
_DEPRECATED_FUNCTIONS = {
    "get_mood": "Use SIL sentiment analysis",
    "get_framework_blend": "Use SIL mode selection",
    "should_proactively_engage": "Use TriggerLearningLoop",
    "record_feedback": "Use FeedbackCollector",
    "get_user_preferences": "Use AdaptationManager",
}


def warn_deprecated(old_func_name: str, new_approach: str) -> None:
    """Warn about deprecated function.

    Args:
        old_func_name: Name of deprecated function
        new_approach: What to use instead
    """
    warnings.warn(
        f"{old_func_name}() is deprecated. {new_approach}.",
        DeprecationWarning,
        stacklevel=3,
    )
