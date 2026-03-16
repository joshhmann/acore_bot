from __future__ import annotations

from tools.mcp_source import MCPToolSource


def register(ctx) -> None:
    source = MCPToolSource.from_env()
    if not source.enabled():
        return
    ctx.tools.register_tool_source(source)
