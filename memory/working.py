from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class WorkingMemory:
    """Ephemeral working memory for active task context.

    Not persisted - lives only for the duration of a session/task.
    Used to maintain temporary context, scratchpad notes, and active task state.
    """

    active_task: str | None = None
    context_buffer: dict[str, Any] = field(default_factory=dict)
    scratchpad: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def set_task(self, task: str | None) -> None:
        """Set or clear the active task."""
        self.active_task = task

    def add_context(self, key: str, value: Any) -> None:
        """Add a key-value pair to the context buffer."""
        self.context_buffer[key] = value

    def get_context(self, key: str) -> Any | None:
        """Retrieve a value from the context buffer by key."""
        return self.context_buffer.get(key)

    def append_scratchpad(self, text: str) -> None:
        """Append text to the scratchpad with a newline separator."""
        if self.scratchpad:
            self.scratchpad += "\n"
        self.scratchpad += text

    def clear(self) -> None:
        """Clear all working memory state (except created_at)."""
        self.active_task = None
        self.context_buffer.clear()
        self.scratchpad = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize working memory to a dictionary."""
        return {
            "active_task": self.active_task,
            "context_buffer": self.context_buffer.copy(),
            "scratchpad": self.scratchpad,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkingMemory:
        """Deserialize working memory from a dictionary."""
        return cls(
            active_task=data.get("active_task"),
            context_buffer=data.get("context_buffer", {}).copy(),
            scratchpad=data.get("scratchpad", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
        )
