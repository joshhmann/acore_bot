from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


ToolHandler = Callable[[dict[str, Any]], Awaitable[str]]


@dataclass(slots=True)
class ToolDefinition:
    name: str
    schema: dict[str, Any]
    handler: ToolHandler
    metadata: dict[str, Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register_tool(
        self,
        name: str,
        schema: dict[str, Any],
        handler: ToolHandler,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._tools[name] = ToolDefinition(
            name=name,
            schema=schema,
            handler=handler,
            metadata=metadata or {},
        )

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def schemas(self, allowlist: set[str] | None = None) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for name, definition in self._tools.items():
            if allowlist is not None and name not in allowlist:
                continue
            out.append(definition.schema)
        return out

    def definitions(self) -> list[ToolDefinition]:
        return [self._tools[name] for name in sorted(self._tools.keys())]
