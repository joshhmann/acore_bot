from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True)
class MCPToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


class MCPTransport(Protocol):
    async def list_tools(self) -> list[MCPToolSpec]: ...

    async def call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]: ...
