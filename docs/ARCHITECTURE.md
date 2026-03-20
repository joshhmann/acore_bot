# Gestalt Architecture

This document describes the current, maintained architecture for Gestalt.

## Summary

Gestalt is a runtime-first system.

The maintained product path is:

- surfaces parse input
- surfaces normalize into shared runtime events/facts
- `GestaltRuntime` owns orchestration and policy
- surfaces render runtime outputs

The canonical composition root is `gestalt/runtime_bootstrap.py`.

## Layers

### 1. Runtime Core

Primary ownership:

- `core/runtime.py`
- `core/commands.py`
- `core/schemas.py`
- `core/interfaces.py`

Runtime owns:

- session state
- command handling
- provider selection
- tool policy and execution budgets
- memory coordination
- trace emission
- social state
- context-cache lifecycle

No maintained surface should re-own these concerns.

### 2. Runtime Assembly

Primary ownership:

- `gestalt/runtime_bootstrap.py`

Maintained assembly responsibilities:

- load persona catalog
- construct provider router
- construct memory manager and RAG store
- construct tool registry, policy, and runner
- create `GestaltRuntime`
- expose `RuntimeHost` for shared lifecycle

`adapters/runtime_factory.py` remains a compatibility seam. It is not the long-term
canonical authority.

### 3. Capability Subsystems

Maintained capability packages:

- `providers/*`
- `tools/*`
- `memory/*`
- `personas/*`
- `plugins/*`
- `mcp_client/*`

These packages are runtime-owned dependencies, not independent product surfaces.

### 4. Surface Adapters

Maintained surface packages:

- `adapters/cli/*`
- `adapters/web/*`
- runtime-host startup via `launcher.py`

Expected adapter contract:

1. parse platform input
2. build normalized runtime facts/events
3. call runtime
4. render runtime outputs

Adapters may compute platform facts.
Adapters may not own provider, tool, persona, memory, or response policy.

## Startup Model

### Canonical startup

Maintained startup should flow through:

- `launcher.py`
- `gestalt/runtime_bootstrap.create_runtime_host()`

Current maintained launcher status:

- CLI: runtime-backed
- Web: runtime-backed
- Discord: runtime-host-backed and runtime-native on the maintained startup path

### Deprecated startup

- `main.py` is deprecated legacy Discord startup

It remains in the repo for compatibility, but it is not the maintained product
entrypoint.

## Surface Status

### CLI

Status: `Verified active`

- default CLI event handling now routes through runtime
- play mode also routes through runtime bootstrap

### Web

Status: `Verified active`

- HTTP and websocket ingress are runtime-backed
- web is the clearest maintained reference surface today

### Discord

Status: `Verified active`

- startup now has a runtime-host-backed module at `adapters/discord/discord_bot.py`
- maintained startup loads runtime-native chat/help/system/social/profile/search cogs
- legacy Discord chat, voice, conversation, and persona-admin modules remain quarantined outside maintained startup

## Legacy And Quarantine

Legacy or non-canonical areas:

- `services/*`
- old event-bus adapter flows
- legacy Discord command ownership
- research and speculative subsystems not explicitly adopted into product truth

These areas may remain in the repo, but they are not architecture authority for
maintained surfaces.

## Enforcement Rules

- maintained startup paths must not require `ServiceFactory`
- maintained adapter hot paths should not import `services/*`
- docs may only claim maintained status when code and tests support it
- if a surface is hybrid, docs must call it hybrid

## Immediate Direction

The next architecture cuts should prioritize:

1. finishing launcher/runtime-host ownership cleanup
2. keeping CLI and web on shared runtime contracts
3. reducing Discord hybrid seams
4. shrinking legacy `services/*` authority in maintained paths
