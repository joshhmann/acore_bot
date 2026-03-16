from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class MemoryNamespace:
    persona_id: str
    room_id: str

    def key(self) -> str:
        return f"{self.persona_id}:{self.room_id}"


class MemoryStore(Protocol):
    async def append_short_term(
        self, namespace: MemoryNamespace, message: dict[str, Any]
    ) -> None: ...

    async def get_short_term(
        self,
        namespace: MemoryNamespace,
        limit: int = 12,
    ) -> list[dict[str, Any]]: ...

    async def get_long_term_summary(self, namespace: MemoryNamespace) -> str: ...

    async def set_long_term_summary(
        self, namespace: MemoryNamespace, summary: str
    ) -> None: ...

    async def get_state(self, namespace: MemoryNamespace) -> dict[str, Any]: ...

    async def set_state(
        self, namespace: MemoryNamespace, state: dict[str, Any]
    ) -> None: ...
