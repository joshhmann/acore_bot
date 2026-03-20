from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from memory.base import MemoryNamespace, MemoryStore
from memory.summary import DeterministicSummary
from memory.episodes import EpisodicMemory, Episode
from personas.state import PersonaState


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
