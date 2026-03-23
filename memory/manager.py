from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from memory.base import MemoryNamespace, MemoryStore
from memory.summary import DeterministicSummary
from memory.episodes import EpisodicMemory, Episode
from memory.types import ActionRecord, Fact, Preference, Procedure
from personas.state import PersonaState

MAX_TYPED_FACTS = 100
MAX_TYPED_PREFERENCES = 100
MAX_TYPED_PROCEDURES = 50
MAX_TYPED_ACTIONS = 100


@dataclass(slots=True)
class MemoryContextBundle:
    recent_history: list[dict[str, Any]]
    summary: str
    facts: list[str]
    persona_state: PersonaState
    revision: str


@dataclass(slots=True)
class MemoryManager:
    store: MemoryStore
    summary_engine: DeterministicSummary
    episodic_memory: EpisodicMemory | None = None

    def _state_namespace(self, namespace: MemoryNamespace) -> MemoryNamespace:
        return MemoryNamespace(
            persona_id=f"persona_state:{namespace.persona_id}",
            room_id=namespace.room_id,
        )

    def _typed_state_namespace(self, namespace: MemoryNamespace) -> MemoryNamespace:
        """Get namespace for typed state storage."""
        return MemoryNamespace(
            persona_id=f"typed_state:{namespace.persona_id}",
            room_id=namespace.room_id,
        )

    def get_shared_namespace(self, room_id: str) -> MemoryNamespace:
        """Get the canonical shared memory namespace for a room."""
        return MemoryNamespace(persona_id="_shared_", room_id=room_id)

    async def load_context(
        self,
        namespace: MemoryNamespace,
        limit: int = 12,
    ) -> MemoryContextBundle:
        history = await self.store.get_short_term(namespace, limit=limit)
        summary = await self.store.get_long_term_summary(namespace)
        payload = await self.store.get_state(self._state_namespace(namespace))
        facts = [
            str(item).strip()
            for item in list(payload.get("facts") or [])
            if str(item).strip()
        ][-12:]
        persona_state = PersonaState.from_dict(payload)
        revision = hashlib.sha256(
            json.dumps(
                {
                    "summary": summary,
                    "facts": facts,
                    "persona_state": persona_state.to_dict(),
                },
                sort_keys=True,
                ensure_ascii=True,
            ).encode("utf-8")
        ).hexdigest()
        return MemoryContextBundle(
            recent_history=history,
            summary=summary,
            facts=facts,
            persona_state=persona_state,
            revision=revision,
        )

    async def write_buffer_message(
        self,
        namespace: MemoryNamespace,
        message: dict[str, Any],
    ) -> None:
        await self.store.append_short_term(namespace, message)

    async def write_summary(
        self,
        namespace: MemoryNamespace,
        recent_messages: list[dict[str, str]],
    ) -> str:
        existing = await self.store.get_long_term_summary(namespace)
        updated = self.summary_engine.update(
            existing=existing, recent_messages=recent_messages
        )
        await self.store.set_long_term_summary(namespace, updated)
        return updated

    async def write_fact(
        self,
        namespace: MemoryNamespace,
        fact: str,
    ) -> None:
        if not fact.strip():
            return
        state_ns = self._state_namespace(namespace)
        payload = await self.store.get_state(state_ns)
        facts = list(payload.get("facts") or [])
        facts.append(fact.strip())
        payload["facts"] = facts[-100:]
        await self.store.set_state(state_ns, payload)

    async def get_persona_state(self, namespace: MemoryNamespace) -> PersonaState:
        payload = await self.store.get_state(self._state_namespace(namespace))
        return PersonaState.from_dict(payload)

    async def set_persona_state(
        self,
        namespace: MemoryNamespace,
        state: PersonaState,
    ) -> None:
        state_ns = self._state_namespace(namespace)
        payload = await self.store.get_state(state_ns)
        payload.update(state.to_dict())
        await self.store.set_state(state_ns, payload)

    # AF-2.9: Episodic Memory Integration

    async def record_episode(
        self,
        namespace: MemoryNamespace,
        context: str,
        actions: list[dict[str, Any]],
        outcome: str,
        metadata: dict[str, Any] | None = None,
    ) -> Episode | None:
        """Record a trajectory episode for few-shot learning.

        Args:
            namespace: Memory namespace for isolation
            context: Situation/context description
            actions: Sequence of actions taken
            outcome: Result of the actions
            metadata: Optional additional metadata

        Returns:
            The created Episode, or None if episodic memory not configured
        """
        if self.episodic_memory is None:
            return None

        return await self.episodic_memory.record_trajectory(
            namespace=namespace,
            context=context,
            actions=actions,
            outcome=outcome,
            metadata=metadata,
        )

    async def find_similar_episodes(
        self,
        namespace: MemoryNamespace,
        query: str,
        top_k: int = 3,
        success_only: bool = True,
    ) -> list[tuple[Episode, float]]:
        """Find similar past episodes for few-shot prompting.

        Args:
            namespace: Memory namespace to search
            query: Query to find similar episodes
            top_k: Maximum number of results
            success_only: Only return successful episodes

        Returns:
            List of (Episode, similarity_score) tuples
        """
        if self.episodic_memory is None:
            return []

        return await self.episodic_memory.search_similar(
            namespace=namespace,
            query=query,
            top_k=top_k,
            success_only=success_only,
        )

    async def get_few_shot_examples(
        self,
        namespace: MemoryNamespace,
        query: str,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """Get few-shot examples for prompting.

        Args:
            namespace: Memory namespace
            query: Query to find relevant examples
            top_k: Number of examples to return

        Returns:
            List of example dictionaries
        """
        if self.episodic_memory is None:
            return []

        return await self.episodic_memory.get_few_shot_examples(
            namespace=namespace,
            query=query,
            top_k=top_k,
            success_only=True,
        )

    async def initialize_episodic_memory(self, root_dir: str | None = None) -> None:
        """Initialize episodic memory with optional custom storage path.

        Args:
            root_dir: Optional custom directory for episode storage
        """
        from memory.episodes import EpisodicMemory, EpisodicMemoryConfig

        if root_dir:
            self.episodic_memory = EpisodicMemory(
                root_dir=root_dir,
                config=EpisodicMemoryConfig(),
            )
        elif self.episodic_memory is None:
            self.episodic_memory = EpisodicMemory(
                config=EpisodicMemoryConfig(),
            )

        await self.episodic_memory.initialize()

    # Step 3A: Typed persistence methods

    def _serialize_record(self, record: Any) -> dict[str, Any]:
        """Serialize a dataclass record to a dictionary, handling datetime."""
        data = asdict(record)

        def convert_datetime(obj: Any) -> Any:
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, dict):
                return {k: convert_datetime(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [convert_datetime(item) for item in obj]
            return obj

        return convert_datetime(data)

    def _deserialize_datetime(self, data: dict[str, Any]) -> dict[str, Any]:
        """Deserialize ISO format strings back to datetime where applicable."""
        datetime_fields = {"created_at", "updated_at", "timestamp"}

        for field in datetime_fields:
            if field in data and isinstance(data[field], str):
                try:
                    data[field] = datetime.fromisoformat(data[field])
                except ValueError:
                    pass  # Keep as string if parsing fails
        return data

    async def _load_typed_state(
        self, namespace: MemoryNamespace
    ) -> dict[str, list[dict[str, Any]]]:
        """Load the typed state container from storage."""
        state_ns = self._typed_state_namespace(namespace)
        payload = await self.store.get_state(state_ns)
        return {
            "facts": list(payload.get("facts") or []),
            "preferences": list(payload.get("preferences") or []),
            "procedures": list(payload.get("procedures") or []),
            "actions": list(payload.get("actions") or []),
        }

    async def _save_typed_state(
        self,
        namespace: MemoryNamespace,
        state: dict[str, list[dict[str, Any]]],
    ) -> None:
        """Save the typed state container to storage."""
        state_ns = self._typed_state_namespace(namespace)
        await self.store.set_state(state_ns, state)

    # Fact Records

    async def store_fact_record(
        self,
        namespace: MemoryNamespace,
        fact: Fact,
    ) -> None:
        """Store a typed Fact record with full metadata."""
        state = await self._load_typed_state(namespace)
        state["facts"].append(self._serialize_record(fact))
        state["facts"] = state["facts"][-MAX_TYPED_FACTS:]
        await self._save_typed_state(namespace, state)

    async def get_fact_records(
        self,
        namespace: MemoryNamespace,
        scope: str | None = None,
        limit: int = 100,
    ) -> list[Fact]:
        """Get typed Fact records, optionally filtered by scope."""
        state = await self._load_typed_state(namespace)
        facts_data = state["facts"][-limit:]

        records = []
        for data in facts_data:
            data = self._deserialize_datetime(data)
            if scope is None or data.get("scope") == scope:
                records.append(Fact(**data))
        return records

    # Preference Records

    async def store_preference_record(
        self,
        namespace: MemoryNamespace,
        preference: Preference,
    ) -> None:
        """Store a typed Preference record with full metadata."""
        state = await self._load_typed_state(namespace)
        state["preferences"].append(self._serialize_record(preference))
        state["preferences"] = state["preferences"][-MAX_TYPED_PREFERENCES:]
        await self._save_typed_state(namespace, state)

    async def get_preference_records(
        self,
        namespace: MemoryNamespace,
        user_id: str | None = None,
        scope: str | None = None,
    ) -> list[Preference]:
        """Get typed Preference records, optionally filtered by user_id and scope."""
        state = await self._load_typed_state(namespace)
        prefs_data = state["preferences"]

        records = []
        for data in prefs_data:
            data = self._deserialize_datetime(data)
            if user_id is not None and data.get("user_id") != user_id:
                continue
            if scope is not None and data.get("scope") != scope:
                continue
            records.append(Preference(**data))
        return records

    # Procedure Records

    async def store_procedure_record(
        self,
        namespace: MemoryNamespace,
        procedure: Procedure,
    ) -> None:
        """Store a typed Procedure record with full metadata."""
        state = await self._load_typed_state(namespace)
        state["procedures"].append(self._serialize_record(procedure))
        state["procedures"] = state["procedures"][-MAX_TYPED_PROCEDURES:]
        await self._save_typed_state(namespace, state)

    async def get_procedure_records(
        self,
        namespace: MemoryNamespace,
        scope: str | None = None,
    ) -> list[Procedure]:
        """Get typed Procedure records, optionally filtered by scope."""
        state = await self._load_typed_state(namespace)
        procs_data = state["procedures"]

        records = []
        for data in procs_data:
            data = self._deserialize_datetime(data)
            if scope is None or data.get("scope") == scope:
                records.append(Procedure(**data))
        return records

    # Action Records

    async def store_action_record(
        self,
        namespace: MemoryNamespace,
        action: ActionRecord,
    ) -> None:
        """Store a typed ActionRecord with full metadata."""
        state = await self._load_typed_state(namespace)
        state["actions"].append(self._serialize_record(action))
        state["actions"] = state["actions"][-MAX_TYPED_ACTIONS:]
        await self._save_typed_state(namespace, state)

    async def get_action_records(
        self,
        namespace: MemoryNamespace,
        limit: int = 100,
    ) -> list[ActionRecord]:
        """Get typed ActionRecord entries."""
        state = await self._load_typed_state(namespace)
        actions_data = state["actions"][-limit:]

        records = []
        for data in actions_data:
            data = self._deserialize_datetime(data)
            records.append(ActionRecord(**data))
        return records
