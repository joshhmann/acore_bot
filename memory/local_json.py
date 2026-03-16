from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import MemoryNamespace, MemoryStore


class LocalJsonMemoryStore(MemoryStore):
    def __init__(self, root_dir: str | Path = "data/gestalt_memory") -> None:
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def _file_path(self, namespace: MemoryNamespace) -> Path:
        safe_persona = namespace.persona_id.replace("/", "_")
        safe_room = namespace.room_id.replace("/", "_")
        room_dir = self.root / safe_persona
        room_dir.mkdir(parents=True, exist_ok=True)
        return room_dir / f"{safe_room}.json"

    def _read(self, namespace: MemoryNamespace) -> dict[str, Any]:
        path = self._file_path(namespace)
        if not path.exists():
            return {"short_term": [], "long_term_summary": "", "state": {}}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"short_term": [], "long_term_summary": "", "state": {}}

    def _write(self, namespace: MemoryNamespace, payload: dict[str, Any]) -> None:
        path = self._file_path(namespace)
        path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8"
        )

    async def append_short_term(
        self, namespace: MemoryNamespace, message: dict[str, Any]
    ) -> None:
        payload = self._read(namespace)
        st = list(payload.get("short_term") or [])
        st.append(message)
        payload["short_term"] = st[-100:]
        self._write(namespace, payload)

    async def get_short_term(
        self,
        namespace: MemoryNamespace,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        payload = self._read(namespace)
        st = list(payload.get("short_term") or [])
        return st[-max(1, limit) :]

    async def get_long_term_summary(self, namespace: MemoryNamespace) -> str:
        payload = self._read(namespace)
        return str(payload.get("long_term_summary") or "")

    async def set_long_term_summary(
        self, namespace: MemoryNamespace, summary: str
    ) -> None:
        payload = self._read(namespace)
        payload["long_term_summary"] = summary
        self._write(namespace, payload)

    async def get_state(self, namespace: MemoryNamespace) -> dict[str, Any]:
        payload = self._read(namespace)
        return dict(payload.get("state") or {})

    async def set_state(
        self, namespace: MemoryNamespace, state: dict[str, Any]
    ) -> None:
        payload = self._read(namespace)
        payload["state"] = state
        self._write(namespace, payload)
