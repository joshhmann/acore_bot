"""SIL Compatibility Shim for behavior.py

This module provides drop-in replacements for behavior.py functions
that use the new Social Intelligence Layer.

Usage in behavior.py:
    from core.social_intelligence.compat import get_mood, get_framework_blend

    # These calls now use SIL under the hood
    mood = get_mood(message, persona_id)
    blend = get_framework_blend(message, persona_id)
"""

from __future__ import annotations

import warnings
from typing import Any, Optional

# Import migration wrapper
from core.social_intelligence.migration import get_migration_wrapper

# Re-export with deprecation warnings
_migration = get_migration_wrapper()


def get_mood(message: str, persona_id: str) -> dict[str, Any]:
    """Get mood for message - SIL compatible version.

    DEPRECATED: Use SIL sentiment analysis directly.
    This function is provided for backward compatibility.
    """
    return _migration.get_mood(message, persona_id)


def get_framework_blend(
    message: str,
    persona_id: str,
    user_id: Optional[str] = None,
) -> dict[str, Any]:
    """Get framework blend - SIL compatible version.

    DEPRECATED: Use SIL mode selection directly.
    This function is provided for backward compatibility.
    """
    return _migration.get_framework_blend(message, persona_id, user_id)


def should_proactively_engage(
    user_id: str,
    channel_id: str,
    context: dict[str, Any],
) -> bool:
    """Check if should proactively engage - SIL compatible version.

    DEPRECATED: Use TriggerLearningLoop directly.
    This function is provided for backward compatibility.
    """
    return _migration.should_proactively_engage(user_id, channel_id, context)


def record_feedback(
    user_id: str,
    feedback_type: str,
    score: float,
    context: Optional[dict] = None,
) -> None:
    """Record feedback - SIL compatible version.

    DEPRECATED: Use FeedbackCollector directly.
    This function is provided for backward compatibility.
    """
    return _migration.record_feedback(user_id, feedback_type, score, context)


def get_user_preferences(user_id: str) -> dict[str, Any]:
    """Get user preferences - SIL compatible version.

    DEPRECATED: Use AdaptationManager directly.
    This function is provided for backward compatibility.
    """
    return _migration.get_user_preferences(user_id)


# Disable warnings in production (call this after imports)
def disable_warnings() -> None:
    """Disable deprecation warnings for production use."""
    _migration.disable_migration_warnings()


# Enable warnings in development
def enable_warnings() -> None:
    """Enable deprecation warnings for development."""
    _migration.enable_migration_warnings()
