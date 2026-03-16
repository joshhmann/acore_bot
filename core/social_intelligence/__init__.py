"""Social Intelligence Layer (SIL) for the Acore framework.

This module provides the foundation for social intelligence capabilities,
including social context detection, user pattern learning, and
conversation state management.

The SIL enables personas to be proactive partners rather than just
reactive command-responders by learning from interactions and adapting
their behavior over time.
"""

from __future__ import annotations

from core.social_intelligence.types import (
    SocialContext,
    SocialSignal,
    VibeProfile,
    UserPattern,
    ConversationState,
    RelationshipProfile,
    SocialEvent,
    EngagementOpportunity,
    SignalType,
    ConversationPhase,
)
from core.social_intelligence.pipeline import ObservationPipeline
from core.social_intelligence.storage import LearnedStateStore, SocialMemoryStore

__all__ = [
    # Types
    "SocialContext",
    "SocialSignal",
    "VibeProfile",
    "UserPattern",
    "ConversationState",
    "RelationshipProfile",
    "SocialEvent",
    "EngagementOpportunity",
    "SignalType",
    "ConversationPhase",
    # Pipeline
    "ObservationPipeline",
    # Storage
    "LearnedStateStore",
    "SocialMemoryStore",
]

__version__ = "0.1.0"

# Runtime hooks for integration with core runtime
from core.social_intelligence.runtime_hooks import (
    SILHookConfig,
    SILObservationResult,
    SILRuntimeHooks,
    get_sil_hooks,
    reset_sil_hooks,
)

__all__.extend([
    "SILHookConfig",
    "SILObservationResult",
    "SILRuntimeHooks",
    "get_sil_hooks",
    "reset_sil_hooks",
])
