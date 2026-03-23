import json

import pytest

from mcp_client.base import MCPToolSpec, MCPTransport
from mcp_client.client import MCPClient
from mcp_client.stdio import StdioMCPTransport
from tools.mcp_source import MCPServerConfig, MCPToolSource
from tools.policy import ToolPolicy, ToolRiskTier
from tools.registry import ToolRegistry
from tools.runner import ToolRunner
from core.schemas import ToolCall


pytestmark = pytest.mark.unit


class _FakeTransport(MCPTransport):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def list_tools(self) -> list[MCPToolSpec]:
        return [
            MCPToolSpec(
                name="move",
                description="Move character",
                input_schema={
                    "type": "object",
                    "properties": {"x": {"type": "integer"}},
                    "required": ["x"],
                },
            )
        ]

    async def call_tool(self, name: str, args: dict) -> dict:
        self.calls.append((name, args))
        return {"ok": True, "name": name, "args": args}


@pytest.mark.asyncio
async def test_mcp_tools_not_loaded_without_config(monkeypatch):
    monkeypatch.delenv("GESTALT_MCP_ENABLED", raising=False)
    monkeypatch.delenv("GESTALT_MCP_SERVERS", raising=False)
    source = MCPToolSource.from_env()
    assert source.enabled() is False

    registry = ToolRegistry()
    policy = ToolPolicy()
    registered = await source.register(registry, policy, allowlists_by_env={})
    assert registered == []


@pytest.mark.asyncio
async def test_mcp_tools_register_with_namespacing(monkeypatch):
    monkeypatch.setenv("GESTALT_MCP_ENABLED", "true")
    source = MCPToolSource(
        servers=[MCPServerConfig(name="scape", transport="http", url="https://unused")]
    )
    fake_client = MCPClient(name="scape", transport=_FakeTransport())
    source._build_client = lambda _server: fake_client  # type: ignore[method-assign]

    registry = ToolRegistry()
    policy = ToolPolicy(network_enabled=True)
    allowlists = {"discord": set()}
    names = await source.register(registry, policy, allowlists)

    assert names == ["mcp:scape:move"]
    tool = registry.get("mcp:scape:move")
    assert tool is not None
    assert tool.metadata["origin"] == "mcp"
    assert tool.metadata["server"] == "scape"
    assert "mcp:scape:move" in allowlists["discord"]


@pytest.mark.asyncio
async def test_mcp_tool_call_respects_policy_budget(monkeypatch):
    monkeypatch.setenv("GESTALT_MCP_ENABLED", "true")
    source = MCPToolSource(
        servers=[MCPServerConfig(name="scape", transport="http", url="https://unused")]
    )
    fake_transport = _FakeTransport()
    fake_client = MCPClient(name="scape", transport=fake_transport)
    source._build_client = lambda _server: fake_client  # type: ignore[method-assign]

    registry = ToolRegistry()
    policy = ToolPolicy(
        allowlist_by_environment={"discord": set()},
        network_enabled=False,
        max_tool_calls_per_turn=1,
    )
    allowlists = {"discord": set()}
    await source.register(registry, policy, allowlists)

    runner = ToolRunner(registry=registry, policy=policy)
    blocked = await runner.execute(
        persona_id="p1",
        environment="discord",
        tool_calls=[ToolCall(name="mcp:scape:move", arguments={"x": 1})],
    )
    assert blocked[0].error == "Tool not allowed by policy"

    policy.network_enabled = True
    allowlists["discord"].add("mcp:scape:move")
    policy.allowlist_by_environment["discord"] = set(allowlists["discord"])
    result = await runner.execute(
        persona_id="p1",
        environment="discord",
        tool_calls=[
            ToolCall(name="mcp:scape:move", arguments={"x": 1}),
            ToolCall(name="mcp:scape:move", arguments={"x": 2}),
        ],
    )
    assert len(result) == 1
    payload = json.loads(result[0].output)
    assert payload["ok"] is True
    assert fake_transport.calls == [("move", {"x": 1})]


@pytest.mark.asyncio
async def test_mcp_tool_error_payload_maps_to_tool_error(monkeypatch):
    monkeypatch.setenv("GESTALT_MCP_ENABLED", "true")

    class _ErrorTransport(MCPTransport):
        async def list_tools(self) -> list[MCPToolSpec]:
            return [
                MCPToolSpec(
                    name="move",
                    description="Move character",
                    input_schema={"type": "object", "properties": {}, "required": []},
                )
            ]

        async def call_tool(self, name: str, args: dict) -> dict:
            del name, args
            return {
                "isError": True,
                "content": [{"type": "text", "text": "Bot not connected"}],
            }

    source = MCPToolSource(
        servers=[MCPServerConfig(name="scape", transport="http", url="https://unused")]
    )
    fake_client = MCPClient(name="scape", transport=_ErrorTransport())
    source._build_client = lambda _server: fake_client  # type: ignore[method-assign]

    registry = ToolRegistry()
    policy = ToolPolicy(
        allowlist_by_environment={"discord": set()},
        network_enabled=True,
    )
    allowlists = {"discord": set()}
    await source.register(registry, policy, allowlists)
    allowlists["discord"].add("mcp:scape:move")
    policy.allowlist_by_environment["discord"] = set(allowlists["discord"])
    policy.tool_risk_tiers["mcp:scape:move"] = ToolRiskTier.NETWORK.value

    runner = ToolRunner(registry=registry, policy=policy)
    result = await runner.execute(
        persona_id="p1",
        environment="discord",
        tool_calls=[ToolCall(name="mcp:scape:move", arguments={})],
    )

    assert result[0].error is not None
    assert "Bot not connected" in result[0].error


def test_mcp_source_parses_stdio_server_config_from_env(monkeypatch):
    monkeypatch.setenv(
        "GESTALT_MCP_SERVERS",
        json.dumps(
            [
                {
                    "name": "rs",
                    "transport": "stdio",
                    "command": "bun",
                    "args": ["run", "mcp/server.ts"],
                    "cwd": "/root/rs-sdk",
                    "env": {"NODE_ENV": "production"},
                }
            ]
        ),
    )

    source = MCPToolSource.from_env()

    assert len(source.servers) == 1
    server = source.servers[0]
    assert server.name == "rs"
    assert server.transport == "stdio"
    assert server.command == "bun"
    assert server.args == ["run", "mcp/server.ts"]
    assert server.cwd == "/root/rs-sdk"
    assert server.env == {"NODE_ENV": "production"}


def test_mcp_source_builds_stdio_client():
    source = MCPToolSource(
        servers=[
            MCPServerConfig(
                name="rs",
                transport="stdio",
                command="bun",
                args=["run", "mcp/server.ts"],
                cwd="/root/rs-sdk",
                env={"NODE_ENV": "production"},
            )
        ]
    )

    client = source._build_client(source.servers[0])

    assert client is not None
    assert isinstance(client.transport, StdioMCPTransport)
    assert client.transport.command == "bun"
    assert client.transport.args == ["run", "mcp/server.ts"]
    assert client.transport.cwd == "/root/rs-sdk"
