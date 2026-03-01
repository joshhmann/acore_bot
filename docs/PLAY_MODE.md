# Play Mode (CLI Demo)

This demo runs a bounded, manual step loop where a persona can control 2004scape through MCP tools.

Scope:
- CLI-only (no Discord play mode)
- no server/process management in Gestalt
- tool execution goes through `ToolRunner` and `ToolPolicy`

## Prerequisites

Assume your MCP bridge is already running externally (for example `rs-mcp-bridge`).
Gestalt does not start game servers, gateways, clients, or bot processes.

## Environment

```bash
GESTALT_MCP_ENABLED=true
GESTALT_MCP_NETWORK_ENABLED=true
GESTALT_MCP_SERVERS='[
  {
    "name": "rs",
    "transport": "http",
    "url": "https://HOST:7007/mcp",
    "api_key": "..."
  }
]'
```

Expected MCP tools (namespaced in Gestalt):
- `mcp:rs:get_state`
- `mcp:rs:walk_to`
- `mcp:rs:interact` (optional but recommended)

## Command

```bash
uv run python -m adapters.cli play \
  --persona dagoth_ur \
  --room world_1 \
  --server rs \
  --bot mybot \
  --steps 10 \
  --tick-seconds 1 \
  --enable-network-tools
```

Flags:
- `--steps` default: `10`
- `--tick-seconds` default: `1.0`
- `--enable-network-tools` default: off
- `--dry-run` prints planned calls but does not execute
- `--verbose` prints tool calls and result summaries per step

## Loop Behavior

For each step:
1. Calls `mcp:<server>:get_state`
2. Chooses a safe action (heuristic):
   - if entities exist and interact tool is present: `interact`
   - otherwise: `walk_to` (small movement)
3. Executes via `ToolRunner` (policy + budget enforced)
4. Prints in-character commentary line
5. Sleeps for `tick-seconds`

No background autonomy threads are started.
The run is bounded by `--steps` and user-invoked.

## Troubleshooting

### Missing MCP tools

If startup says required tools are missing, verify:
- `GESTALT_MCP_ENABLED=true`
- `GESTALT_MCP_SERVERS` contains a valid JSON list with the `name` used by `--server`
- the MCP bridge actually exposes `get_state` and `walk_to`

### Network-tier blocked

If tools are blocked by policy:
- pass `--enable-network-tools`, or
- set `GESTALT_MCP_NETWORK_ENABLED=true` before runtime creation
