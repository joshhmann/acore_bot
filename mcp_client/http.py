from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aiohttp

from .base import MCPToolSpec, MCPTransport


@dataclass(slots=True)
class HTTPMCPTransport(MCPTransport):
    base_url: str
    timeout_seconds: int = 15

    async def list_tools(self) -> list[MCPToolSpec]:
        url = f"{self.base_url.rstrip('/')}/tools"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds),
            ) as response:
                payload = await response.json()
        tools = payload.get("tools") or []
        specs: list[MCPToolSpec] = []
        for item in tools:
            specs.append(
                MCPToolSpec(
                    name=str(item.get("name") or ""),
                    description=str(item.get("description") or ""),
                    input_schema=dict(
                        item.get("input_schema") or item.get("inputSchema") or {}
                    ),
                )
            )
        return specs

    async def call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/tools/call"
        body = {"name": name, "arguments": args}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=body,
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds),
            ) as response:
                return await response.json()
