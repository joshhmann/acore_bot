from __future__ import annotations

from memory.base import MemoryNamespace
from memory.manager import MemoryManager
from personas.loader import PersonaDefinition
from personas.state import PersonaState


class PersonaEngine:
    def __init__(self, memory_manager: MemoryManager) -> None:
        self.memory_manager = memory_manager

    async def build_system_prompt(
        self,
        persona: PersonaDefinition,
        namespace: MemoryNamespace,
        summary: str,
        rag_context: str,
    ) -> str:
        state = await self.memory_manager.get_persona_state(namespace)
        mood = state.mood
        parts = [
            f"You are {persona.display_name}.",
            persona.description,
            persona.personality,
            persona.scenario,
            persona.system_prompt,
            f"Current mood: {mood}.",
        ]
        if summary:
            parts.append(f"Conversation summary:\n{summary}")
        if rag_context:
            parts.append(f"Relevant knowledge:\n{rag_context}")
        return "\n\n".join([p for p in parts if p])

    async def update_state(
        self,
        persona: PersonaDefinition,
        namespace: MemoryNamespace,
        user_text: str,
        response_text: str,
    ) -> None:
        del persona
        state = await self.memory_manager.get_persona_state(namespace)
        msg_count = state.message_count + 1
        affinity = state.affinity
        if "thanks" in user_text.lower() or "love" in user_text.lower():
            affinity = min(100, affinity + 1)
        if "hate" in user_text.lower() or "stupid" in user_text.lower():
            affinity = max(0, affinity - 1)

        mood = "neutral"
        lower = response_text.lower()
        if "!" in response_text:
            mood = "energized"
        if any(word in lower for word in ("sorry", "sad", "unfortunately")):
            mood = "somber"

        updated = PersonaState(
            mood=mood,
            affinity=affinity,
            message_count=msg_count,
            evolution_stage="new",
        )
        if msg_count >= 5000:
            updated.evolution_stage = "legendary"
        elif msg_count >= 1000:
            updated.evolution_stage = "veteran"
        elif msg_count >= 100:
            updated.evolution_stage = "experienced"

        await self.memory_manager.set_persona_state(namespace, updated)
