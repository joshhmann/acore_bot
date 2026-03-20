# Original Plan Fact Check

**Last Updated**: 2026-03-10

## Purpose

This document answers a narrow question:

Did the originally important work actually get done?

It does not use completion reports, checklist waves, or final-status docs as
proof. It uses:

- original plan files in `.sisyphus/plans/*`
- current code in the repository
- current test files in `tests/*`

This document focuses on the original pre-drift priority set identified in
[ALIGNMENT_REVIEW.md](/root/acore_bot/docs/historical/ALIGNMENT_REVIEW.md):

- `MCPBRIDGE-1`
- `discord-legacy-migration`
- `behavior-engine-improvements`
- `web-adapter`
- `gestalt-terminal-v1-spec`

## Judgment Labels

- `Implemented`
  The work is materially present in code.
- `Partially implemented`
  Important parts exist, but the intended cleanup or productization is not done.
- `Documented only`
  The plan/report language exists, but the code/test evidence does not support a
  strong completion claim.
- `Verified`
  There is direct code and current test evidence in the repo.
- `Test coverage: missing`
  The feature may exist in code, but current test evidence is missing or too
  thin to support a strong verification claim.

## Executive Judgment

The original work queue was not imaginary. Real work happened.

But the later repo narrative overstated the level of completion.

Current truth:

- `web-adapter`: implemented
- `gestalt-terminal-v1-spec`: partially implemented
- `behavior-engine-improvements`: partially implemented
- `discord-legacy-migration`: partially implemented
- `MCPBRIDGE-1`: partially implemented, with important parts living outside the
  main Gestalt runtime tree

The failure was not "nothing was built."

The failure was treating a mixed state of:

- implemented
- partially migrated
- under-tested
- experimental

as if it were uniformly complete.

## Plan-by-Plan Fact Check

### 1. Web Adapter

Plan source:

- `.sisyphus/plans/web-adapter.md`

Planned outcome:

- a FastAPI-based web adapter
- HTTP routes
- websocket support
- health/persona/chat surface
- runtime or framework exposure through a web interface

Current code evidence:

- `adapters/web/adapter.py`
- `adapters/web/routes.py`
- `adapters/web/websocket.py`
- `adapters/web/auth.py`
- `adapters/web/api_schema.py`
- `launcher.py`

What is clearly real:

- there is a real FastAPI-backed web adapter in `adapters/web/adapter.py`
- there is a runtime websocket mounted at `adapters/web/adapter.py:174`
- there are runtime-oriented HTTP routes in `adapters/web/routes.py`
- web auth exists in `adapters/web/auth.py`
- the web adapter builds or accepts a `GestaltRuntime`

What is not clean:

- the adapter still exposes the legacy websocket path at
  `adapters/web/adapter.py:180`
- the older simple websocket handler still exists in
  `adapters/web/websocket.py:652`
- this means the web surface is real, but not fully consolidated

Current test evidence:

- no dedicated current `tests/unit/test_web_*` or `tests/integration/test_web_*`
  files are present in the active test tree

Judgment:

- `Implemented`
- `Partially implemented` relative to cleanup/consolidation goals
- `Test coverage: missing`

Truth statement:

The web adapter was genuinely built, but it is not honestly "fully done" in the
sense implied by the later completion wave.

### 2. Gestalt Terminal V1

Plan source:

- `.sisyphus/plans/gestalt-terminal-v1-spec.md`

Planned outcome:

- terminal-first assistant
- command-driven workflow
- strong memory visibility
- command palette/help flow
- safety/diff/memory/project-context UX
- provider-agnostic runtime-backed experience

Current code evidence:

- `adapters/tui/app.py`
- `adapters/tui/routing.py`
- `adapters/tui/presence.py`
- `adapters/cli/__main__.py`
- `adapters/cli/play.py`
- `core/runtime.py`

What is clearly real:

- there is a real TUI app in `adapters/tui/app.py`
- the TUI uses the runtime command registry through
  `self.runtime.list_commands()` in `adapters/tui/app.py:124`
- the TUI has a command palette/help/status/trace structure
- the CLI exists and builds the runtime through `adapters/cli/__main__.py`
- CLI play mode has real MCP-aware behavior in `adapters/cli/play.py`

What is only partly supported:

- the original spec included broader V1 productization goals than the current
  maintained tests prove
- some of the strongest V1 claims were about integrated memory/product polish,
  diff review, and multi-model self-check behavior, but the active test tree is
  too small to verify the full specification

Current test evidence:

- `tests/unit/test_gestalt_v1_runtime.py`
- `tests/unit/test_gestalt_v1_features.py`

What those tests actually verify:

- runtime/provider/tool/memory basics
- autonomy scheduler behavior
- some presence defaults
- some provider/router behavior
- strict-mode helper import from Discord path

What they do not prove:

- full terminal V1 parity with the spec
- broad TUI regression coverage
- full memory and review UX claims

Judgment:

- `Partially implemented`
- `Verified` for the runtime foundation pieces covered by current tests
- `Test coverage: missing` for large parts of the full V1 spec

Truth statement:

Gestalt Terminal V1 was directionally built, but the full V1 specification was
not proven complete by the current code-and-test surface.

### 3. Behavior Engine Improvements

Plan source:

- `.sisyphus/plans/behavior-engine-improvements.md`

Planned outcome:

- simplify the behavior pipeline
- make conversations less robotic
- increase engagement rates
- simplify prompt construction
- preserve compatibility while improving feel

Current code evidence:

- `services/persona/behavior.py`
- `services/core/context.py`
- `config.py`

Strong evidence that real work happened:

- `services/persona/behavior.py` remains a substantial behavior system
- `services/core/context.py` was the target of a focused, specific change in
  commit `5424004`
- the plan goal of prompt simplification has corresponding code movement in the
  context path

What is uncertain:

- the current repo does not have a visible active `tests/unit/test_behavior_engine.py`
- many later claims about "all behavior tasks complete" depend on report waves,
  not on a current dedicated test file
- the behavior layer is still deeply embedded in the legacy `services/*`
  architecture rather than being cleanly absorbed into the runtime-first core

Current test evidence:

- no active dedicated behavior-engine unit test file was found in the current
  test tree

Judgment:

- `Partially implemented`
- `Test coverage: missing`

Truth statement:

Behavior-engine work was real, and some of it was likely useful, but the later
completion language overstated how verified and productized it actually is.

### 4. Discord Legacy Migration

Plan source:

- `.sisyphus/plans/discord-legacy-migration.md`

Planned outcome:

- remove hardfail runtime bypasses
- route Discord interactions through the runtime
- harden fallback seams
- eliminate direct provider use in the adapter path

Current code evidence:

- `adapters/discord/commands/chat/main.py`
- `adapters/runtime_factory.py`
- `core/runtime.py`

What is clearly real:

- Discord now does construct and use a `GestaltRuntime` in
  `adapters/discord/commands/chat/main.py:164`
- strict mode and fallback governance are present in
  `adapters/discord/commands/chat/main.py`
- Discord is not purely living on the old direct-chat path anymore

What is clearly not finished:

- Discord still imports legacy service-layer systems directly:
  - `services/core/context.py`
  - `services/persona/lorebook.py`
  - `services/persona/behavior.py`
- `adapters/runtime_factory.py` still builds runtime seams from legacy services
- the migration plan was about fully removing runtime bypass architecture, but
  the current shape is still hybrid

Current test evidence:

- no active dedicated Discord migration or Discord runtime regression test files
  were found in the present test tree

Judgment:

- `Partially implemented`
- `Test coverage: missing`

Truth statement:

Discord moved toward runtime-first architecture, but the legacy seam was not
fully retired. The migration improved the system, but it did not complete the
architectural cleanup the plan described.

### 5. MCPBRIDGE-1

Plan source:

- active work queue reference only

Planned outcome:

- build `rs-mcp-bridge` MCP proxy service

Current code evidence:

- `external/rs-mcp-bridge/README.md`
- `external/rs-mcp-bridge/src/mcp/server.ts`
- `tools/mcp_source.py`
- `adapters/runtime_factory.py`
- `core/runtime.py`
- `adapters/cli/play.py`

What is clearly real:

- an `rs-mcp-bridge` project exists under `external/rs-mcp-bridge`
- MCP is genuinely wired into the Gestalt runtime/tool path
- CLI play mode expects MCP-backed tools in `adapters/cli/play.py`
- runtime snapshots expose MCP server state in `core/runtime.py`

What is not proven:

- the fact that `rs-mcp-bridge` exists externally does not prove the original
  plan was completed as an integrated, verified Gestalt product slice
- the current active test tree does not include dedicated bridge tests

Judgment:

- `Partially implemented`
- `Test coverage: missing`

Truth statement:

The MCP bridge direction is real and useful, but the repo does not currently
prove that `MCPBRIDGE-1` reached the kind of verified completion later status
docs implied.

## Truth Table

| Plan | Code Present | Verified by Current Tests | Honest Status |
|------|--------------|---------------------------|---------------|
| `web-adapter` | Yes | Weak / missing dedicated tests | Implemented, still needs cleanup |
| `gestalt-terminal-v1-spec` | Yes | Partial | Partially implemented |
| `behavior-engine-improvements` | Yes | Missing dedicated current tests | Partially implemented |
| `discord-legacy-migration` | Yes | Missing dedicated current tests | Partially implemented |
| `MCPBRIDGE-1` | Yes, partly external | Missing dedicated current tests | Partially implemented |

## What This Means

The original roadmap was not fake.

But the later story that all of it was fully complete and verified was not
supported by the current repository state.

The repo currently contains:

- real runtime and surface work
- real migration work
- real MCP direction
- real TUI/web progress

It also contains:

- hybrid legacy seams
- incomplete cleanup
- thin current verification
- status language that ran ahead of the actual proof

## Required Documentation Rule Going Forward

For these original plan areas, documentation should now use language like:

- `implemented but still hybrid`
- `partially implemented`
- `verified foundation only`
- `test coverage: missing`

It should not use language like:

- `complete`
- `fully verified`
- `100% done`

unless new code-and-test evidence is added.

## Recommended Next Steps

1. Use this fact check as the truth layer for pruning and refactor order.
2. Clean the generated artifacts and duplicate transport paths first.
3. Re-audit each original focus area only after the repo footprint is cleaner.
4. Expand tests only after the architecture boundary for each area is clear.
