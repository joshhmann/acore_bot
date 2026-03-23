"""Typed memory concepts for the Gestalt memory coordinator.

Phase 3 Slice 3: Memory Coordinator + Memory Scoping
Implements strongly-typed memory classes for runtime-owned memory coordination.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from memory.episodes import Episode


class MemoryScope(str, Enum):
    """Memory scoping: persona-private vs shared tiers.

    - PERSONA: Per-persona memory (default)
    - SHARED: Runtime-owned shared-memory tier for relationship and social state
    """

    PERSONA = "persona"
    SHARED = "shared"


@dataclass(slots=True)
class ShortTermTurn:
    """A single turn in short-term conversation memory.

    Captures individual messages/exchanges for recent context window
    without requiring full episode storage.

    Attributes:
        turn_id: Unique identifier for the turn
        timestamp: When the turn occurred
        role: Speaker role ("user", "assistant", or "system")
        content: The message content
        persona_id: Owning persona identifier
        session_id: Session identifier for grouping
        metadata: Additional turn metadata
    """

    turn_id: str
    timestamp: datetime
    role: str  # "user" | "assistant" | "system"
    content: str
    persona_id: str
    session_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Fact:
    """A discrete fact stored in memory.

    Facts capture learned information with provenance and confidence
    for use in persona behavior and context assembly.

    Attributes:
        fact_id: Unique identifier for the fact
        content: The fact content (what was learned)
        source: Origin of the fact (conversation, tool output, etc.)
        persona_id: Owning persona identifier
        scope: Memory scope ("persona" for private, "shared" for global)
        created_at: When the fact was recorded
        confidence: Reliability score (0.0-1.0)
        metadata: Additional fact metadata
    """

    fact_id: str
    content: str
    source: str
    persona_id: str
    scope: str  # "persona" | "shared"
    created_at: datetime
    confidence: float = 1.0  # 0.0-1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Preference:
    """A user or persona preference stored in memory.

    Preferences capture configurable behaviors, topic interests,
    and style choices that persist across sessions.

    Attributes:
        preference_id: Unique identifier for the preference
        key: Preference key/name (e.g., "communication_style")
        value: Preference value (any type)
        user_id: Associated user identifier
        persona_id: Owning persona identifier
        scope: Memory scope ("persona" for private, "shared" for global)
        category: Preference category (e.g., "style", "topic", "behavior")
        updated_at: When the preference was last modified
    """

    preference_id: str
    key: str
    value: Any
    user_id: str
    persona_id: str
    scope: str  # "persona" | "shared"
    category: str  # e.g., "style", "topic", "behavior"
    updated_at: datetime


@dataclass(slots=True)
class Procedure:
    """A learned procedure or workflow stored in memory.

    Procedures capture successful patterns of action that can be
    retrieved and applied to similar future situations.

    Attributes:
        procedure_id: Unique identifier for the procedure
        name: Human-readable procedure name
        description: What the procedure does and when to use it
        steps: Ordered list of procedure steps
        persona_id: Owning persona identifier
        scope: Memory scope ("persona" for private, "shared" for global)
        success_count: Times this procedure has succeeded
        created_at: When the procedure was recorded
    """

    procedure_id: str
    name: str
    description: str
    steps: list[str]
    persona_id: str
    scope: str  # "persona" | "shared"
    success_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class ActionRecord:
    """A record of an action taken by the system.

    Action records capture tool calls, memory writes, and other
    operations for accountability, debugging, and approval workflows.

    Attributes:
        action_id: Unique identifier for the action
        action_type: Category of action ("tool_call", "memory_write", etc.)
        tool_name: Specific tool name if applicable
        inputs: Action inputs/parameters
        output: Action output/result
        outcome: Execution result ("success", "error", "pending")
        persona_id: Acting persona identifier
        session_id: Session in which action occurred
        timestamp: When the action was taken
        approval_state: For Slice 4: approval queue state
    """

    action_id: str
    action_type: str  # "tool_call", "memory_write", etc.
    tool_name: str | None
    inputs: dict[str, Any]
    output: str
    outcome: str  # "success" | "error" | "pending"
    persona_id: str
    session_id: str
    timestamp: datetime
    approval_state: str | None = None  # For Slice 4 approval queues


@dataclass(slots=True)
class TypedMemoryContext:
    """Enhanced context bundle using typed memory concepts.

    Replaces/adapts MemoryContextBundle with strongly-typed memory
    classes for better runtime memory coordination and scoping.

    All fields use typed memory classes rather than raw dicts/strings
    where applicable. Episodes are imported from memory.episodes.

    Attributes:
        recent_turns: Recent conversation turns (short-term memory)
        facts: Learned facts relevant to current context
        preferences: Active preferences for behavior shaping
        procedures: Available procedures for task completion
        action_history: Recent actions for accountability
        episodes: Relevant past episodes (imported from episodes module)
        revision: Content hash for cache invalidation
    """

    recent_turns: list[ShortTermTurn]
    facts: list[Fact]
    preferences: list[Preference]
    procedures: list[Procedure]
    action_history: list[ActionRecord]
    episodes: list[Episode]
    revision: str
