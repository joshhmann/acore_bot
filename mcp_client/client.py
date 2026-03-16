from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import MCPToolSpec, MCPTransport


@dataclass(slots=True)
class MCPClient:
    name: str
    transport: MCPTransport
    connected: bool = False

    async def connect(self) -> None:
        self.connected = True

    async def list_tools(self) -> list[MCPToolSpec]:
        if not self.connected:
            await self.connect()
        return await self.transport.list_tools()

    async def call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if not self.connected:
            await self.connect()
        return await self.transport.call_tool(name=name, args=args)

    async def close(self) -> None:
        close_fn = getattr(self.transport, "aclose", None)
        if callable(close_fn):
            await close_fn()
        self.connected = False
