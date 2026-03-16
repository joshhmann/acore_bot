# TOOLS KNOWLEDGE BASE

Last updated: 2026-03-09 PST
Scope: `tools/*`.

## Overview
Runtime tool infrastructure: registry, policy, execution runner, shell/file ops, and MCP source integration.

## Where To Look
| Task | Location | Notes |
|------|----------|-------|
| Tool contracts | `tools/registry.py` | Tool registration and metadata |
| Policy/budget | `tools/policy.py` | Authorization and limits |
| Execution | `tools/runner.py` | Tool dispatch and accounting |
| MCP source | `tools/mcp_source.py` | External MCP server tool loading |

## Anti-Patterns
- Bypassing policy checks before tool execution.
- Returning unnormalized tool output payloads.
- Adapter-side direct imports of tool internals.
