"""Type definitions for the Social Intelligence Layer.

This module defines dataclasses and enums for social signals, user patterns,
conversation state, and relationship tracking. All types are JSON-serializable
and platform-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import json
import uuid


class SignalType(str, Enum):
    """Types of social signals that can be detected."""

    SENTIMENT = "sentiment"
    FORMALITY = "formality"
    URGENCY = "urgency"
    RELATIONSHIP_CUE = "relationship_cue"
    TOPIC_INTEREST = "topic_interest"
    ENGAGEMENT_LEVEL = "engagement_level"
    EMOTIONAL_STATE = "emotional_state"


class ConversationPhase(str, Enum):
    """Phases of a conversation lifecycle."""

    INITIATION = "initiation"
    RAPPORT_BUILDING = "rapport_building"
    EXPLORATION = "exploration"
    DEEPENING = "deepening"
    CONCLUSION = "conclusion"
    PAUSE = "pause"
    RESUMING = "resuming"


@dataclass(slots=True)
class SocialSignal:
    """A detected social signal from message or context analysis.

    Attributes:
        signal_type: The type of signal detected.
        value: The signal value (typically -1.0 to 1.0 or 0.0 to 1.0).
        confidence: Confidence score for the detection (0.0 to 1.0).
        source: Where the signal was detected (e.g., "message_text", "timing").
        timestamp: When the signal was detected.
        metadata: Additional signal-specific data.
    """

    signal_type: SignalType
    value: float
    confidence: float = 0.5
    source: str = "unknown"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "signal_type": self.signal_type.value,
            "value": self.value,
            "confidence": self.confidence,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SocialSignal:
        """Create from dictionary."""
        return cls(
            signal_type=SignalType(data["signal_type"]),
            value=data["value"],
            confidence=data.get("confidence", 0.5),
            source=data.get("source", "unknown"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
        )


@dataclass(slots=True)
class VibeProfile:
    """The emotional and social atmosphere of a conversation.

    Uses the PAD (Pleasure-Arousal-Dominance) emotion model as the foundation,
    extended with social dimensions like formality and engagement.

    Attributes:
        pleasure: Pleasure dimension (-1.0 to 1.0, negative=unpleasant, positive=pleasant).
        arousal: Arousal dimension (-1.0 to 1.0, negative=calm, positive=excited).
        dominance: Dominance dimension (-1.0 to 1.0, negative=submissive, positive=dominant).
        formality: Formality level (0.0=casual, 1.0=formal).
        engagement: Engagement level (0.0=disengaged, 1.0=highly engaged).
        confidence: Confidence in the vibe assessment (0.0 to 1.0).
    """

    pleasure: float = 0.0
    arousal: float = 0.0
    dominance: float = 0.0
    formality: float = 0.5
    engagement: float = 0.5
    confidence: float = 0.5

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for JSON serialization."""
        return {
            "pleasure": self.pleasure,
            "arousal": self.arousal,
            "dominance": self.dominance,
            "formality": self.formality,
            "engagement": self.engagement,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> VibeProfile:
        """Create from dictionary."""
        return cls(
            pleasure=data.get("pleasure", 0.0),
            arousal=data.get("arousal", 0.0),
            dominance=data.get("dominance", 0.0),
            formality=data.get("formality", 0.5),
            engagement=data.get("engagement", 0.5),
            confidence=data.get("confidence", 0.5),
        )


@dataclass(slots=True)
class UserPattern:
    """A learned pattern about a user's behavior or preferences.

    Attributes:
        pattern_type: Type of pattern (e.g., "response_time", "topic_preference").
        pattern_id: Unique identifier for this pattern.
        user_id: The user this pattern applies to.
        value: The pattern value (type depends on pattern_type).
        confidence: Confidence in the pattern (0.0 to 1.0).
        sample_count: Number of observations supporting this pattern.
        first_observed: When the pattern was first detected.
        last_updated: When the pattern was last updated.
        metadata: Additional pattern-specific data.
    """

    pattern_type: str
    pattern_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    value: Any = None
    confidence: float = 0.0
    sample_count: int = 0
    first_observed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "pattern_type": self.pattern_type,
            "pattern_id": self.pattern_id,
            "user_id": self.user_id,
            "value": self.value,
            "confidence": self.confidence,
            "sample_count": self.sample_count,
            "first_observed": self.first_observed.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> UserPattern:
        """Create from dictionary."""
        return cls(
            pattern_type=data["pattern_type"],
            pattern_id=data.get("pattern_id", str(uuid.uuid4())),
            user_id=data.get("user_id", ""),
            value=data.get("value"),
            confidence=data.get("confidence", 0.0),
            sample_count=data.get("sample_count", 0),
            first_observed=datetime.fromisoformat(data["first_observed"])
            if "first_observed" in data
            else datetime.now(timezone.utc),
            last_updated=datetime.fromisoformat(data["last_updated"])
            if "last_updated" in data
            else datetime.now(timezone.utc),
            metadata=data.get("metadata", {}),
        )


@dataclass(slots=True)
class ConversationState:
    """The current state of a conversation.

    Attributes:
        conversation_id: Unique identifier for the conversation.
        phase: Current phase of the conversation.
        turn_count: Number of turns completed.
        participant_ids: List of user IDs participating.
        last_activity: Timestamp of last message.
        topic: Current or most recent topic (if identified).
        context_summary: Brief summary of conversation context.
        metadata: Additional conversation metadata.
    """

    conversation_id: str
    phase: ConversationPhase = ConversationPhase.INITIATION
    turn_count: int = 0
    participant_ids: List[str] = field(default_factory=list)
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    topic: Optional[str] = None
    context_summary: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "conversation_id": self.conversation_id,
            "phase": self.phase.value,
            "turn_count": self.turn_count,
            "participant_ids": self.participant_ids,
            "last_activity": self.last_activity.isoformat(),
            "topic": self.topic,
            "context_summary": self.context_summary,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConversationState:
        """Create from dictionary."""
        return cls(
            conversation_id=data["conversation_id"],
            phase=ConversationPhase(data.get("phase", "initiation")),
            turn_count=data.get("turn_count", 0),
            participant_ids=data.get("participant_ids", []),
            last_activity=datetime.fromisoformat(data["last_activity"])
            if "last_activity" in data
            else datetime.now(timezone.utc),
            topic=data.get("topic"),
            context_summary=data.get("context_summary", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass(slots=True)
class RelationshipProfile:
    """Relationship state between a persona and a user.

    Attributes:
        user_id: The user ID.
        persona_id: The persona ID.
        affinity_score: Relationship affinity (-1.0 to 1.0).
        interaction_count: Total number of interactions.
        first_interaction: Timestamp of first interaction.
        last_interaction: Timestamp of last interaction.
        shared_topics: Topics discussed together.
        user_preferences: Learned user preferences.
        metadata: Additional relationship data.
    """

    user_id: str
    persona_id: str
    affinity_score: float = 0.0
    interaction_count: int = 0
    first_interaction: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_interaction: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    shared_topics: List[str] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "user_id": self.user_id,
            "persona_id": self.persona_id,
            "affinity_score": self.affinity_score,
            "interaction_count": self.interaction_count,
            "first_interaction": self.first_interaction.isoformat(),
            "last_interaction": self.last_interaction.isoformat(),
            "shared_topics": self.shared_topics,
            "user_preferences": self.user_preferences,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RelationshipProfile:
        """Create from dictionary."""
        return cls(
            user_id=data["user_id"],
            persona_id=data["persona_id"],
            affinity_score=data.get("affinity_score", 0.0),
            interaction_count=data.get("interaction_count", 0),
            first_interaction=datetime.fromisoformat(data["first_interaction"])
            if "first_interaction" in data
            else datetime.now(timezone.utc),
            last_interaction=datetime.fromisoformat(data["last_interaction"])
            if "last_interaction" in data
            else datetime.now(timezone.utc),
            shared_topics=data.get("shared_topics", []),
            user_preferences=data.get("user_preferences", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass(slots=True)
class EngagementOpportunity:
    """An opportunity for proactive engagement.

    Attributes:
        opportunity_id: Unique identifier.
        opportunity_type: Type of opportunity (e.g., "user_frustrated", "topic_change").
        priority: Priority score (0.0 to 1.0, higher = more important).
        confidence: Confidence that this is a real opportunity.
        suggested_action: Recommended action to take.
        context: Context explaining why this opportunity exists.
        expires_at: When this opportunity expires.
        metadata: Additional opportunity data.
    """

    opportunity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    opportunity_type: str = ""
    priority: float = 0.5
    confidence: float = 0.5
    suggested_action: str = ""
    context: str = ""
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "opportunity_id": self.opportunity_id,
            "opportunity_type": self.opportunity_type,
            "priority": self.priority,
            "confidence": self.confidence,
            "suggested_action": self.suggested_action,
            "context": self.context,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EngagementOpportunity:
        """Create from dictionary."""
        expires_at = None
        if data.get("expires_at"):
            expires_at = datetime.fromisoformat(data["expires_at"])
        return cls(
            opportunity_id=data.get("opportunity_id", str(uuid.uuid4())),
            opportunity_type=data.get("opportunity_type", ""),
            priority=data.get("priority", 0.5),
            confidence=data.get("confidence", 0.5),
            suggested_action=data.get("suggested_action", ""),
            context=data.get("context", ""),
            expires_at=expires_at,
            metadata=data.get("metadata", {}),
        )


@dataclass(slots=True)
class SocialContext:
    """Comprehensive social context for decision-making.

    This is the primary data structure passed through the Social Intelligence Layer,
    containing all relevant social signals, patterns, and state for making
    proactive behavior decisions.

    Attributes:
        context_id: Unique identifier for this context snapshot.
        timestamp: When this context was captured.
        vibe: The current vibe/atmosphere profile.
        conversation: Current conversation state.
        relationship: Relationship profile for the primary user.
        recent_signals: List of recently detected social signals.
        user_patterns: Learned patterns for the user.
        engagement_opportunities: Detected opportunities for engagement.
        metadata: Additional context data.
    """

    context_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    vibe: VibeProfile = field(default_factory=VibeProfile)
    conversation: Optional[ConversationState] = None
    relationship: Optional[RelationshipProfile] = None
    recent_signals: List[SocialSignal] = field(default_factory=list)
    user_patterns: List[UserPattern] = field(default_factory=list)
    engagement_opportunities: List[EngagementOpportunity] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "context_id": self.context_id,
            "timestamp": self.timestamp.isoformat(),
            "vibe": self.vibe.to_dict(),
            "conversation": self.conversation.to_dict() if self.conversation else None,
            "relationship": self.relationship.to_dict() if self.relationship else None,
            "recent_signals": [s.to_dict() for s in self.recent_signals],
            "user_patterns": [p.to_dict() for p in self.user_patterns],
            "engagement_opportunities": [
                o.to_dict() for o in self.engagement_opportunities
            ],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SocialContext:
        """Create from dictionary."""
        return cls(
            context_id=data.get("context_id", str(uuid.uuid4())),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if "timestamp" in data
            else datetime.now(timezone.utc),
            vibe=VibeProfile.from_dict(data["vibe"])
            if "vibe" in data
            else VibeProfile(),
            conversation=ConversationState.from_dict(data["conversation"])
            if data.get("conversation")
            else None,
            relationship=RelationshipProfile.from_dict(data["relationship"])
            if data.get("relationship")
            else None,
            recent_signals=[
                SocialSignal.from_dict(s) for s in data.get("recent_signals", [])
            ],
            user_patterns=[
                UserPattern.from_dict(p) for p in data.get("user_patterns", [])
            ],
            engagement_opportunities=[
                EngagementOpportunity.from_dict(o)
                for o in data.get("engagement_opportunities", [])
            ],
            metadata=data.get("metadata", {}),
        )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, json_str: str) -> SocialContext:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass(slots=True)
class SocialEvent:
    """An event processed by the Social Intelligence Layer.

    Wraps a runtime event with social context for analysis.

    Attributes:
        event_id: Unique identifier.
        source_event_id: ID of the original runtime event.
        event_type: Type of social event.
        user_id: The user involved.
        channel_id: The channel/room where it occurred.
        timestamp: When the event occurred.
        raw_content: Original message content (if applicable).
        social_context: Computed social context for this event.
        metadata: Additional event data.
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_event_id: str = ""
    event_type: str = ""
    user_id: str = ""
    channel_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_content: Optional[str] = None
    social_context: Optional[SocialContext] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_id": self.event_id,
            "source_event_id": self.source_event_id,
            "event_type": self.event_type,
            "user_id": self.user_id,
            "channel_id": self.channel_id,
            "timestamp": self.timestamp.isoformat(),
            "raw_content": self.raw_content,
            "social_context": self.social_context.to_dict()
            if self.social_context
            else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SocialEvent:
        """Create from dictionary."""
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            source_event_id=data.get("source_event_id", ""),
            event_type=data.get("event_type", ""),
            user_id=data.get("user_id", ""),
            channel_id=data.get("channel_id", ""),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if "timestamp" in data
            else datetime.now(timezone.utc),
            raw_content=data.get("raw_content"),
            social_context=SocialContext.from_dict(data["social_context"])
            if data.get("social_context")
            else None,
            metadata=data.get("metadata", {}),
        )
