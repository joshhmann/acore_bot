"""CRITICAL FIXES: Concurrency Safety for Persona System

These fixes address race conditions in multi-threaded Discord bot environment.
Apply these changes immediately to prevent data corruption.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class ConcurrencySafePersonaRouter:
    """Thread-safe version of PersonaRouter."""

    def __init__(self):
        # Per-channel locks for fine-grained concurrency
        self._channel_locks: Dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        # Global lock for persona operations
        self._persona_lock = asyncio.Lock()
        # Lock for shared state
        self._state_lock = asyncio.Lock()

        self.last_responder: Dict[int, Dict] = {}
        self.personas: Dict[str, Any] = {}

    async def record_response(self, channel_id: int, persona: Any):
        """Thread-safe recording of persona responses."""
        async with self._channel_locks[channel_id]:
            self.last_responder[channel_id] = {
                "persona": persona,
                "time": datetime.now(),
            }

    async def get_last_responder(self, channel_id: int) -> Optional[Dict]:
        """Thread-safe access to last responder."""
        async with self._channel_locks[channel_id]:
            return self.last_responder.get(channel_id)

    async def update_persona(self, persona_id: str, persona_data: Any):
        """Thread-safe persona update."""
        async with self._persona_lock:
            self.personas[persona_id] = persona_data

    async def get_persona(self, persona_id: str) -> Optional[Any]:
        """Thread-safe persona access."""
        async with self._persona_lock:
            return self.personas.get(persona_id)


class AtomicStateManager:
    """Atomic state manager for behavioral states."""

    def __init__(self):
        self._states: Dict[int, Dict] = {}
        self._locks: Dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._global_lock = asyncio.Lock()

    async def update_state(self, channel_id: int, updates: Dict[str, Any]):
        """Atomically update channel state."""
        async with self._locks[channel_id]:
            if channel_id not in self._states:
                self._states[channel_id] = {
                    "last_message_time": datetime.now(),
                    "message_count": 0,
                    "mood_state": "neutral",
                    "mood_intensity": 0.5,
                }

            # Apply all updates atomically
            for key, value in updates.items():
                if key in [
                    "last_message_time",
                    "last_bot_message_time",
                    "last_ambient_trigger",
                    "last_proactive_trigger",
                    "last_mood_update",
                ]:
                    self._states[channel_id][key] = value
                elif key == "message_count":
                    self._states[channel_id][key] += value
                elif key in ["mood_state", "mood_intensity"]:
                    self._states[channel_id][key] = value
                else:
                    self._states[channel_id][key] = value

    async def get_state(self, channel_id: int) -> Dict[str, Any]:
        """Thread-safe state access."""
        async with self._locks[channel_id]:
            return self._states.get(channel_id, {}).copy()

    async def atomic_increment(self, channel_id: int, field: str, value: int = 1):
        """Atomically increment a counter field."""
        async with self._locks[channel_id]:
            if channel_id not in self._states:
                self._states[channel_id] = {}
            current = self._states[channel_id].get(field, 0)
            self._states[channel_id][field] = current + value


class RelationshipManager:
    """Thread-safe relationship management."""

    def __init__(self):
        self._relationships: Dict[str, Dict] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._global_lock = asyncio.Lock()

    def _get_pair_key(self, persona_a: str, persona_b: str) -> str:
        """Generate consistent pair key."""
        a, b = sorted([persona_a.lower(), persona_b.lower()])
        return f"{a}_{b}"

    async def update_affinity(
        self, persona_a: str, persona_b: str, affinity_change: int
    ):
        """Thread-safe affinity update."""
        key = self._get_pair_key(persona_a, persona_b)
        async with self._locks[key]:
            if key not in self._relationships:
                self._relationships[key] = {
                    "affinity": 0,
                    "interaction_count": 0,
                    "last_interaction": None,
                }

            rel = self._relationships[key]
            rel["affinity"] = max(0, min(100, rel["affinity"] + affinity_change))
            rel["interaction_count"] += 1
            rel["last_interaction"] = datetime.now()

    async def get_relationship(self, persona_a: str, persona_b: str) -> Dict:
        """Thread-safe relationship access."""
        key = self._get_pair_key(persona_a, persona_b)
        async with self._locks[key]:
            return self._relationships.get(
                key, {"affinity": 0, "interaction_count": 0, "stage": "strangers"}
            ).copy()

    async def batch_update_relationships(self, updates: list):
        """Atomically update multiple relationships."""
        # Group by keys to minimize lock contention
        grouped = {}
        for update in updates:
            key = self._get_pair_key(update["persona_a"], update["persona_b"])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(update)

        # Apply updates with minimal locking
        for key, key_updates in grouped.items():
            async with self._locks[key]:
                if key not in self._relationships:
                    self._relationships[key] = {
                        "affinity": 0,
                        "interaction_count": 0,
                        "last_interaction": None,
                    }

                rel = self._relationships[key]
                for update in key_updates:
                    if "affinity_change" in update:
                        rel["affinity"] = max(
                            0, min(100, rel["affinity"] + update["affinity_change"])
                        )
                    if "interaction" in update:
                        rel["interaction_count"] += 1
                    rel["last_interaction"] = datetime.now()


# Implementation Guide:
#
# 1. Replace PersonaRouter with ConcurrencySafePersonaRouter:
#    - In services/persona/router.py, inherit from ConcurrencySafePersonaRouter
#    - Replace direct dict access with async methods
#
# 2. Replace BehaviorState with AtomicStateManager:
#    - In services/persona/behavior.py, use AtomicStateManager
#    - Replace state.direct_field = value with await state.update_state(channel_id, {"direct_field": value})
#
# 3. Replace PersonaRelationships with RelationshipManager:
#    - In services/persona/relationships.py, use RelationshipManager methods
#    - Replace direct affinity updates with await update_affinity()
#
# 4. Update all call sites:
#    - Change router.record_response(channel_id, persona) to await router.record_response(...)
#    - Change state.field = value to await state.update_state(channel_id, {"field": value})
#    - Change relationships.record_interaction(...) to await relationships.update_affinity(...)

print("Persona System Concurrency Fixes Created")
print("Apply these changes to prevent race conditions in production!")
