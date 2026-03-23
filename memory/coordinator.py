"""Memory coordinator for runtime-owned memory operations with typed scoping.

Phase 3 Slice 3: Memory Coordinator + Memory Scoping

This module provides a runtime-owned memory coordinator that:
- Wraps MemoryManager with typed memory operations
- Enforces separation between per-persona and shared memory scopes
- Converts between typed memory context and legacy bundles for backward compatibility

Architecture:
    Runtime -> MemoryCoordinator -> MemoryManager -> MemoryStore

Adapters do NOT call the coordinator directly; all memory operations flow through
the runtime, which owns memory coordination.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

from memory.base import MemoryNamespace
from memory.episodes import Episode
from memory.manager import MemoryContextBundle, MemoryManager
from memory.types import (
    ActionRecord,
    Fact,
    MemoryScope,
    Preference,
    Procedure,
    ShortTermTurn,
    TypedMemoryContext,
)


def create_persona_namespace(persona_id: str, room_id: str) -> MemoryNamespace:
    """Create a memory namespace for per-persona scoped memory.

    Args:
        persona_id: The persona identifier
        room_id: The room/scope identifier

    Returns:
        MemoryNamespace configured for persona scope
    """
    return MemoryNamespace(persona_id=persona_id, room_id=room_id)


def determine_scope(is_shared: bool) -> MemoryScope:
    """Determine memory scope from boolean flag.

    Args:
        is_shared: True for shared scope, False for persona scope

    Returns:
        MemoryScope enum value
    """
    return MemoryScope.SHARED if is_shared else MemoryScope.PERSONA


def _generate_id() -> str:
    """Generate a unique identifier."""
    return uuid.uuid4().hex[:16]


T = TypeVar("T")


def _dedupe_records_by_key(
    records: list[T],
    key_fn: Callable[[T], Any],
) -> list[T]:
    """Deduplicate records while preserving first-seen order."""
    seen: set[str] = set()
    deduped: list[T] = []
    for record in records:
        key = str(key_fn(record))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def _compute_typed_context_revision(typed_context: TypedMemoryContext) -> str:
    """Compute a content hash for cache invalidation.

    Args:
        typed_context: The typed memory context to hash

    Returns:
        Hex digest of content hash
    """
    content = {
        "turns": [
            {"id": t.turn_id, "content": t.content, "role": t.role}
            for t in typed_context.recent_turns
        ],
        "facts": [f.content for f in typed_context.facts],
        "preferences": [
            {"key": p.key, "value": str(p.value)} for p in typed_context.preferences
        ],
        "procedures": [p.name for p in typed_context.procedures],
        "actions": [
            {"type": a.action_type, "outcome": a.outcome}
            for a in typed_context.action_history
        ],
        "episodes": [e.episode_id for e in typed_context.episodes],
    }
    return hashlib.sha256(
        json.dumps(content, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()


@dataclass(slots=True)
class SharedMemoryTier:
    """Runtime-owned shared memory tier for relationship and social state.

    This class manages memory that is shared across personas within a room,
    such as social dynamics, relationship states, and cross-persona facts.

    The shared tier is owned by the runtime, not by any individual persona.

    Attributes:
        coordinator: Parent memory coordinator for storage operations
        room_id: The room/scope identifier for this shared tier
    """

    coordinator: "MemoryCoordinator"
    room_id: str

    def _namespace(self) -> MemoryNamespace:
        """Get the shared namespace for this room."""
        return self.coordinator.manager.get_shared_namespace(self.room_id)

    async def store_fact(
        self,
        content: str,
        source: str,
        confidence: float = 1.0,
    ) -> Fact:
        """Store a shared fact.

        Args:
            content: The fact content
            source: Origin of the fact
            confidence: Reliability score (0.0-1.0)

        Returns:
            The created Fact
        """
        return await self.coordinator.store_fact(
            namespace=self._namespace(),
            content=content,
            source=source,
            confidence=confidence,
            scope=MemoryScope.SHARED,
        )

    async def get_facts(self, limit: int = 50) -> list[Fact]:
        """Retrieve shared facts.

        Args:
            limit: Maximum number of facts to return

        Returns:
            List of shared Facts
        """
        return await self.coordinator.get_facts(
            namespace=self._namespace(),
            scope=MemoryScope.SHARED,
            limit=limit,
        )

    async def store_preference(
        self,
        key: str,
        value: Any,
        user_id: str,
        category: str = "general",
    ) -> Preference:
        """Store a shared preference.

        Args:
            key: Preference key/name
            value: Preference value
            user_id: Associated user identifier
            category: Preference category

        Returns:
            The created Preference
        """
        return await self.coordinator.store_preference(
            namespace=self._namespace(),
            key=key,
            value=value,
            user_id=user_id,
            category=category,
            scope=MemoryScope.SHARED,
        )

    async def get_preferences(self, user_id: str | None = None) -> list[Preference]:
        """Retrieve shared preferences.

        Args:
            user_id: Optional user filter (None for all shared preferences)

        Returns:
            List of shared Preferences
        """
        return await self.coordinator.get_preferences(
            namespace=self._namespace(),
            user_id=user_id or "_all_",
            scope=MemoryScope.SHARED,
        )

    async def store_procedure(
        self,
        name: str,
        steps: list[str],
        description: str = "",
    ) -> Procedure:
        """Store a shared procedure.

        Args:
            name: Procedure name
            steps: Ordered list of steps
            description: What the procedure does

        Returns:
            The created Procedure
        """
        return await self.coordinator.store_procedure(
            namespace=self._namespace(),
            name=name,
            steps=steps,
            scope=MemoryScope.SHARED,
        )

    async def get_procedures(self) -> list[Procedure]:
        """Retrieve shared procedures.

        Returns:
            List of shared Procedures
        """
        return await self.coordinator.get_procedures(
            namespace=self._namespace(),
            scope=MemoryScope.SHARED,
        )


@dataclass(slots=True)
class MemoryCoordinator:
    """Runtime-owned memory coordinator with typed operations and explicit scoping.

    The MemoryCoordinator wraps MemoryManager to provide:
    - Strongly-typed memory operations (ShortTermTurn, Fact, Preference, etc.)
    - Explicit scoping (per-persona vs shared memory tiers)
    - Conversion between typed memory context and legacy bundles

    Architecture:
        Runtime -> MemoryCoordinator -> MemoryManager -> MemoryStore

    The coordinator maintains separation between:
    - Per-persona memory: Private to each persona
    - Shared memory: Runtime-owned tier for relationship/social state

    Attributes:
        manager: The underlying MemoryManager for storage operations
        _shared_tiers: Cache of SharedMemoryTier instances by room_id
    """

    manager: MemoryManager
    _shared_tiers: dict[str, SharedMemoryTier] = field(default_factory=dict)

    async def _load_shared_records(
        self,
        namespace: MemoryNamespace,
        *,
        fact_limit: int,
        action_limit: int,
    ) -> tuple[list[Fact], list[Preference], list[Procedure], list[ActionRecord]]:
        """Load shared-tier records for a room when applicable."""
        if namespace.persona_id == "_shared_":
            return [], [], [], []

        shared_namespace = self.manager.get_shared_namespace(namespace.room_id)
        return (
            await self.manager.get_fact_records(shared_namespace, limit=fact_limit),
            await self.manager.get_preference_records(shared_namespace),
            await self.manager.get_procedure_records(shared_namespace),
            await self.manager.get_action_records(shared_namespace, limit=action_limit),
        )

    async def get_typed_context(
        self,
        namespace: MemoryNamespace,
        limit: int = 12,
    ) -> TypedMemoryContext:
        """Load typed memory context for a namespace.

        Retrieves recent turns, facts, preferences, procedures, and action history
        as strongly-typed objects.

        Args:
            namespace: Memory namespace (persona or shared)
            limit: Maximum number of recent turns to load

        Returns:
            TypedMemoryContext with all typed memory elements
        """
        # Load from underlying manager
        bundle = await self.manager.load_context(namespace, limit=limit)

        # Convert recent history to ShortTermTurn objects
        recent_turns: list[ShortTermTurn] = []
        for i, msg in enumerate(bundle.recent_history):
            turn_id = msg.get("turn_id") or msg.get("id") or f"turn_{i}"
            timestamp_str = msg.get("timestamp")
            try:
                timestamp = (
                    datetime.fromisoformat(timestamp_str)
                    if timestamp_str
                    else datetime.now(timezone.utc)
                )
            except (ValueError, TypeError):
                timestamp = datetime.now(timezone.utc)

            recent_turns.append(
                ShortTermTurn(
                    turn_id=turn_id,
                    timestamp=timestamp,
                    role=msg.get("role", "unknown"),
                    content=msg.get("content", ""),
                    persona_id=namespace.persona_id,
                    session_id=msg.get("session_id", ""),
                    metadata=msg.get("metadata", {}),
                )
            )

        # Get typed records from manager authority.
        persona_facts = await self.manager.get_fact_records(namespace, limit=50)
        persona_preferences = await self.manager.get_preference_records(namespace)
        persona_procedures = await self.manager.get_procedure_records(namespace)
        persona_action_history = await self.manager.get_action_records(
            namespace, limit=limit
        )

        (
            shared_facts,
            shared_preferences,
            shared_procedures,
            shared_action_history,
        ) = await self._load_shared_records(
            namespace,
            fact_limit=50,
            action_limit=limit,
        )

        # Preserve legacy facts already stored through MemoryManager.write_fact().
        legacy_facts = [
            Fact(
                fact_id=f"legacy_{hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]}",
                content=content,
                source="legacy_memory_manager",
                persona_id=namespace.persona_id,
                scope=MemoryScope.PERSONA.value,
                created_at=datetime.now(timezone.utc),
            )
            for content in bundle.facts
            if content.strip()
        ]

        facts = _dedupe_records_by_key(
            persona_facts + shared_facts + legacy_facts,
            lambda fact: (fact.scope, fact.content),
        )

        # Get episodes from manager's episodic memory
        episodes: list[Episode] = []
        if self.manager.episodic_memory:
            episodes = await self.manager.episodic_memory.get_episodes(
                namespace, limit=10
            )

        preferences = _dedupe_records_by_key(
            persona_preferences + shared_preferences,
            lambda pref: (pref.scope, pref.user_id, pref.key),
        )
        procedures = _dedupe_records_by_key(
            persona_procedures + shared_procedures,
            lambda proc: (proc.scope, proc.name),
        )
        action_history = _dedupe_records_by_key(
            persona_action_history + shared_action_history,
            lambda action: action.action_id,
        )

        # Build typed context
        typed_context = TypedMemoryContext(
            recent_turns=recent_turns,
            facts=facts,
            preferences=preferences,
            procedures=procedures,
            action_history=action_history,
            episodes=episodes,
            revision=bundle.revision,
        )

        # Recompute revision to ensure consistency with typed content
        typed_context.revision = _compute_typed_context_revision(typed_context)

        return typed_context

    async def record_turn(
        self,
        namespace: MemoryNamespace,
        role: str,
        content: str,
        session_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> ShortTermTurn:
        """Record a conversation turn.

        Args:
            namespace: Memory namespace
            role: Speaker role ("user", "assistant", or "system")
            content: The message content
            session_id: Session identifier for grouping
            metadata: Additional turn metadata

        Returns:
            The created ShortTermTurn
        """
        turn = ShortTermTurn(
            turn_id=_generate_id(),
            timestamp=datetime.now(timezone.utc),
            role=role,
            content=content,
            persona_id=namespace.persona_id,
            session_id=session_id,
            metadata=metadata or {},
        )

        # Store through underlying manager
        message = {
            "turn_id": turn.turn_id,
            "timestamp": turn.timestamp.isoformat(),
            "role": turn.role,
            "content": turn.content,
            "session_id": turn.session_id,
            "metadata": turn.metadata,
        }
        await self.manager.write_buffer_message(namespace, message)

        return turn

    async def store_fact(
        self,
        namespace: MemoryNamespace,
        content: str,
        source: str,
        confidence: float = 1.0,
        scope: MemoryScope = MemoryScope.PERSONA,
    ) -> Fact:
        """Store a fact.

        Args:
            namespace: Memory namespace
            content: The fact content (what was learned)
            source: Origin of the fact
            confidence: Reliability score (0.0-1.0)
            scope: Memory scope (PERSONA or SHARED)

        Returns:
            The created Fact
        """
        fact = Fact(
            fact_id=_generate_id(),
            content=content,
            source=source,
            persona_id=namespace.persona_id,
            scope=scope.value if isinstance(scope, MemoryScope) else scope,
            created_at=datetime.now(timezone.utc),
            confidence=confidence,
        )

        # Delegate to manager's typed storage
        await self.manager.store_fact_record(namespace, fact)

        # Also store raw text for backward compatibility
        await self.manager.write_fact(namespace, content)

        return fact

    async def get_facts(
        self,
        namespace: MemoryNamespace,
        scope: MemoryScope | None = None,
        limit: int = 50,
    ) -> list[Fact]:
        """Retrieve facts.

        Args:
            namespace: Memory namespace
            scope: Optional scope filter (None for all)
            limit: Maximum number of facts to return

        Returns:
            List of Facts matching the criteria
        """
        # Delegate to manager's typed storage
        scope_str = scope.value if scope else None
        return await self.manager.get_fact_records(
            namespace, scope=scope_str, limit=limit
        )

    async def store_preference(
        self,
        namespace: MemoryNamespace,
        key: str,
        value: Any,
        user_id: str,
        category: str = "general",
        scope: MemoryScope = MemoryScope.PERSONA,
    ) -> Preference:
        """Store a preference.

        Args:
            namespace: Memory namespace
            key: Preference key/name
            value: Preference value
            user_id: Associated user identifier
            category: Preference category (e.g., "style", "topic", "behavior")
            scope: Memory scope (PERSONA or SHARED)

        Returns:
            The created Preference
        """
        preference = Preference(
            preference_id=_generate_id(),
            key=key,
            value=value,
            user_id=user_id,
            persona_id=namespace.persona_id,
            scope=scope.value if isinstance(scope, MemoryScope) else scope,
            category=category,
            updated_at=datetime.now(timezone.utc),
        )

        # Delegate to manager's typed storage
        await self.manager.store_preference_record(namespace, preference)

        return preference

    async def get_preferences(
        self,
        namespace: MemoryNamespace,
        user_id: str | None = None,
        scope: MemoryScope | None = None,
    ) -> list[Preference]:
        """Retrieve preferences.

        Args:
            namespace: Memory namespace
            user_id: Optional user filter (None for all)
            scope: Optional scope filter

        Returns:
            List of Preferences matching the criteria
        """
        # Delegate to manager's typed storage
        scope_str = scope.value if scope else None
        return await self.manager.get_preference_records(
            namespace, user_id=user_id, scope=scope_str
        )

    async def store_procedure(
        self,
        namespace: MemoryNamespace,
        name: str,
        steps: list[str],
        scope: MemoryScope = MemoryScope.PERSONA,
        description: str = "",
    ) -> Procedure:
        """Store a procedure.

        Args:
            namespace: Memory namespace
            name: Human-readable procedure name
            steps: Ordered list of procedure steps
            scope: Memory scope (PERSONA or SHARED)
            description: What the procedure does

        Returns:
            The created Procedure
        """
        procedure = Procedure(
            procedure_id=_generate_id(),
            name=name,
            description=description,
            steps=steps,
            persona_id=namespace.persona_id,
            scope=scope.value if isinstance(scope, MemoryScope) else scope,
            success_count=0,
            created_at=datetime.now(timezone.utc),
        )

        # Delegate to manager's typed storage
        await self.manager.store_procedure_record(namespace, procedure)

        return procedure

    async def get_procedures(
        self,
        namespace: MemoryNamespace,
        scope: MemoryScope | None = None,
    ) -> list[Procedure]:
        """Retrieve procedures.

        Args:
            namespace: Memory namespace
            scope: Optional scope filter

        Returns:
            List of Procedures matching the criteria
        """
        # Delegate to manager's typed storage
        scope_str = scope.value if scope else None
        return await self.manager.get_procedure_records(namespace, scope=scope_str)

    async def record_action(
        self,
        namespace: MemoryNamespace,
        action_type: str,
        inputs: dict[str, Any],
        output: str,
        outcome: str,
        tool_name: str | None = None,
        session_id: str = "",
        approval_state: str | None = None,
    ) -> ActionRecord:
        """Record an action taken by the system.

        Args:
            namespace: Memory namespace
            action_type: Category of action ("tool_call", "memory_write", etc.)
            inputs: Action inputs/parameters
            output: Action output/result
            outcome: Execution result ("success", "error", "pending")
            tool_name: Specific tool name if applicable
            session_id: Session in which action occurred
            approval_state: Approval queue state, if applicable

        Returns:
            The created ActionRecord
        """
        action = ActionRecord(
            action_id=_generate_id(),
            action_type=action_type,
            tool_name=tool_name,
            inputs=inputs,
            output=output,
            outcome=outcome,
            persona_id=namespace.persona_id,
            session_id=session_id,
            timestamp=datetime.now(timezone.utc),
            approval_state=approval_state,
        )

        # Delegate to manager's typed storage
        await self.manager.store_action_record(namespace, action)

        return action

    async def get_action_history(
        self,
        namespace: MemoryNamespace,
        limit: int = 50,
    ) -> list[ActionRecord]:
        """Retrieve recent action history.

        Args:
            namespace: Memory namespace
            limit: Maximum number of actions to return

        Returns:
            List of ActionRecords, most recent first
        """
        # Delegate to manager's typed storage
        return await self.manager.get_action_records(namespace, limit=limit)

    def to_memory_context_bundle(
        self, typed_context: TypedMemoryContext
    ) -> MemoryContextBundle:
        """Convert TypedMemoryContext to legacy MemoryContextBundle.

        This enables backward compatibility with existing code that expects
        the legacy bundle format.

        Args:
            typed_context: The typed memory context to convert

        Returns:
            MemoryContextBundle for backward compatibility
        """
        # Convert ShortTermTurn objects to dicts
        recent_history = [
            {
                "turn_id": turn.turn_id,
                "timestamp": turn.timestamp.isoformat(),
                "role": turn.role,
                "content": turn.content,
                "session_id": turn.session_id,
                "metadata": turn.metadata,
            }
            for turn in typed_context.recent_turns
        ]

        # Convert Fact objects to strings
        facts = [fact.content for fact in typed_context.facts]

        # Build summary from episodes if available
        summary_parts = []
        if typed_context.episodes:
            for ep in typed_context.episodes[:3]:
                summary_parts.append(f"{ep.context} -> {ep.outcome}")
        summary = "; ".join(summary_parts) if summary_parts else ""

        # Use persona state from manager if available, or create default
        from personas.state import PersonaState

        persona_state = PersonaState()

        return MemoryContextBundle(
            recent_history=recent_history,
            summary=summary,
            facts=facts,
            persona_state=persona_state,
            revision=typed_context.revision,
        )

    def get_shared_tier(self, room_id: str) -> SharedMemoryTier:
        """Get or create the shared memory tier for a room.

        Args:
            room_id: The room identifier

        Returns:
            SharedMemoryTier for the room
        """
        if room_id not in self._shared_tiers:
            self._shared_tiers[room_id] = SharedMemoryTier(
                coordinator=self,
                room_id=room_id,
            )
        return self._shared_tiers[room_id]
