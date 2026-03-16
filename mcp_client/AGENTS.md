# MCP CLIENT KNOWLEDGE BASE

Last updated: 2026-03-09 PST
Scope: `mcp_client/*`.

## Overview
Model Context Protocol client layer providing stdio/http transports and normalized client operations for tool source integration.

## Where To Look
| Task | Location | Notes |
|------|----------|-------|
| Client facade | `mcp_client/client.py` | High-level client operations |
| STDIO transport | `mcp_client/stdio.py` | Process-backed MCP transport |
| HTTP transport | `mcp_client/http.py` | Network transport implementation |

## Anti-Patterns
- Transport-specific behavior leaking past client abstraction.
- Non-deterministic subprocess lifecycle handling.
- Unbounded retries/timeouts in transport paths.
