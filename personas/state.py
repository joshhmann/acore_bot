from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class PersonaState:
    mood: str = "neutral"
    affinity: int = 50
    message_count: int = 0
    evolution_stage: str = "new"

    def to_dict(self) -> dict[str, Any]:
        return {
            "mood": self.mood,
            "affinity": self.affinity,
            "message_count": self.message_count,
            "evolution_stage": self.evolution_stage,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PersonaState":
        return cls(
            mood=str(payload.get("mood") or "neutral"),
            affinity=int(payload.get("affinity") or 50),
            message_count=int(payload.get("message_count") or 0),
            evolution_stage=str(payload.get("evolution_stage") or "new"),
        )
