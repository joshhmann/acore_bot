# PLUGINS KNOWLEDGE BASE

Last updated: 2026-03-09 PST
Scope: `plugins/*`.

## Overview
Runtime plugin loading and composition layer for builtins and optional external plugin sources.

## Where To Look
| Task | Location | Notes |
|------|----------|-------|
| Loader flow | `plugins/loader.py` | Discovery, ordering, strict mode handling |
| Plugin context | `plugins/context.py` | Runtime context passed to plugins |
| Builtin core tools plugin | `plugins/builtins/core_tools/plugin.py` | Core tool registration |
| MCP tool source plugin | `plugins/builtins/mcp_tool_source/plugin.py` | MCP-backed tool source |

## Conventions
- Keep plugin loading deterministic and traceable.
- Preserve strict/non-strict plugin behavior flags.
- Keep plugin side effects explicit at registration time.

## Anti-Patterns
- Plugin mutation of runtime state outside declared interfaces.
- Non-deterministic load ordering.
- Silent plugin failures without governance flags.
