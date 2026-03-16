from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from mcp_client.client import MCPClient
from mcp_client.http import HTTPMCPTransport
from mcp_client.stdio import StdioMCPTransport
from tools.policy import ToolPolicy, ToolRiskTier
from tools.registry import ToolRegistry


@dataclass(slots=True)
class MCPServerConfig:
    name: str
    transport: str
    command: str | None = None
    args: list[str] | None = None
    cwd: str | None = None
    url: str | None = None
    env: dict[str, str] | None = None


class MCPToolSource:
    def __init__(
        self,
        servers: list[MCPServerConfig],
        safe_name_allowlist: set[str] | None = None,
    ):
        self.servers = servers
        self.safe_name_allowlist = safe_name_allowlist or {
            "ping",
            "health",
            "time",
            "status",
        }

    @classmethod
    def from_env(cls) -> "MCPToolSource":
        raw = os.getenv("GESTALT_MCP_SERVERS", "").strip()
        if not raw:
            return cls(servers=[])
        try:
            parsed = json.loads(raw)
        except Exception:
            return cls(servers=[])
        servers: list[MCPServerConfig] = []
        for item in parsed if isinstance(parsed, list) else []:
            servers.append(
                MCPServerConfig(
                    name=str(item.get("name") or ""),
                    transport=str(item.get("transport") or "http"),
                    command=item.get("command"),
                    args=[str(arg) for arg in list(item.get("args") or [])],
                    cwd=(str(item.get("cwd")) if item.get("cwd") else None),
                    url=item.get("url"),
                    env=dict(item.get("env") or {}),
                )
            )
        return cls(servers=servers)

    def enabled(self) -> bool:
        if os.getenv("GESTALT_MCP_ENABLED", "false").lower() != "true":
            return False
        return len(self.servers) > 0

    async def register(
        self,
        registry: ToolRegistry,
        policy: ToolPolicy,
        allowlists_by_env: dict[str, set[str]],
    ) -> list[str]:
        if not self.enabled():
            return []

        registered_names: list[str] = []
        for server in self.servers:
            client = self._build_client(server)
            if client is None:
                continue
            tools = await client.list_tools()
            for spec in tools:
                namespaced = f"mcp:{server.name}:{spec.name}"
                underlying_name = spec.name

                async def _handler(
                    arguments: dict[str, Any],
                    *,
                    c: MCPClient = client,
                    tool_name: str = underlying_name,
                ) -> str:
                    try:
                        result = await c.call_tool(name=tool_name, args=arguments)
                        if isinstance(result, dict) and bool(result.get("isError")):
                            text_parts: list[str] = []
                            content = result.get("content")
                            if isinstance(content, list):
                                for item in content:
                                    if isinstance(item, dict):
                                        text = item.get("text")
                                        if isinstance(text, str) and text.strip():
                                            text_parts.append(text.strip())
                            message = (
                                "\n".join(text_parts)
                                if text_parts
                                else "MCP tool call failed"
                            )
                            raise RuntimeError(message)
                        return json.dumps(result, ensure_ascii=True)
                    finally:
                        if isinstance(c.transport, StdioMCPTransport):
                            await c.close()

                registry.register_tool(
                    name=namespaced,
                    schema={
                        "name": namespaced,
                        "description": spec.description,
                        "parameters": spec.input_schema or {"type": "object"},
                    },
                    handler=_handler,
                    metadata={
                        "origin": "mcp",
                        "server": server.name,
                        "underlying_tool": spec.name,
                    },
                )

                risk = (
                    ToolRiskTier.SAFE.value
                    if spec.name in self.safe_name_allowlist
                    else ToolRiskTier.NETWORK.value
                )
                policy.tool_risk_tiers[namespaced] = risk
                for env_name in ("discord", "cli", "web"):
                    allowlists_by_env.setdefault(env_name, set()).add(namespaced)
                registered_names.append(namespaced)
            await client.close()
        return registered_names

    def _build_client(self, server: MCPServerConfig) -> MCPClient | None:
        if server.transport.lower() == "http" and server.url:
            return MCPClient(
                name=server.name, transport=HTTPMCPTransport(base_url=server.url)
            )
        if server.transport.lower() == "stdio" and server.command:
            return MCPClient(
                name=server.name,
                transport=StdioMCPTransport(
                    command=server.command,
                    args=list(server.args or []),
                    env=dict(server.env or {}),
                    cwd=server.cwd,
                ),
            )
        return None
