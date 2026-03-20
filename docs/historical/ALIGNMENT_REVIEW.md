# Codebase Alignment Review

**Last Updated**: 2026-03-10

## Purpose

This document reviews the major parts of the repository against the current
Gestalt vision in [VISION.md](/root/acore_bot/docs/VISION.md).

It answers four questions:

1. what is in the repo now
2. whether it aligns with Gestalt as a personal runtime-first agentic framework
3. what should be kept, refactored, quarantined, or deleted
4. what pruning work should happen next

This is more specific than [REPO_AUDIT.md](/root/acore_bot/docs/historical/REPO_AUDIT.md)
and more execution-oriented than
[CODEBASE_REVIEW.md](/root/acore_bot/docs/historical/CODEBASE_REVIEW.md).

## Review Standard

The current Gestalt vision is:

- one runtime-first agentic framework
- multi-persona by design
- memory, learning, action, and autonomy
- MCP-first extensibility
- multiple model, TTS, and STT providers
- CLI, web, and Discord as major surfaces
- future embodiment through browser-first VRM/scene systems

Subsystems are aligned when they strengthen that runtime-first framework.

Subsystems are misaligned when they:

- create competing authority layers
- introduce speculative framework breadth into canonical namespaces
- duplicate transport or orchestration
- add product claims that the codebase cannot yet support honestly
- commit generated artifacts or repository noise

## Top-Level Repo Facts

Top-level directory count is not the problem by itself. The problem is which
directories currently define the product versus which ones distort it.

Approximate file counts:

- `core`: `102`
- `adapters`: `288` source files if generated desktop output is excluded
- `services`: `188`
- `cogs`: `30`
- `providers`: `12`
- `memory`: `23`
- `tools`: `15`
- `mcp_client`: `11`
- `docs`: `85`
- `tests`: `245`

Size highlights:

- `adapters`: `3.0G`
- `adapters/desktop`: `2.7G`
- `core`: `1.6M`
- `services`: `3.1M`
- `docs`: `1.4M`

The desktop adapter size is overwhelmingly inflated by tracked generated
artifacts:

- tracked files under `adapters/desktop/src-tauri/target/**`: `5020`
- tracked files under `adapters/desktop/node_modules/**`: `4087`

That means part of the repo's apparent complexity is real architecture drift,
and part of it is plain repository hygiene failure.

## Review of Work Done

The work done in this repository was not uniformly wrong.

### Pre-Drift Focus Set

Before the repo broadened too far, the active work queue was centered on:

- `MCPBRIDGE-1`
- `discord-legacy-migration`
- `behavior-engine-improvements`
- `web-adapter`
- `gestalt-terminal-v1-spec`

There were also lower-priority exploratory tracks:

- `agentic-framework-implementation`
- `partner-in-crime-architecture`
- `runescape-agent`
- `rl-enhancement-master-plan`
- `rl_autonomy`
- `framework-expansion`

This matters because the first group is much closer to the real Gestalt product
than the second.

The pre-drift focus was basically:

- clean up Discord and legacy seams
- improve persona and behavior quality
- add a runtime-backed web surface
- build a usable terminal surface
- strengthen MCP integration

That is still a coherent roadmap for Gestalt.

The later drift happened when the exploratory tracks began to land as if they
were part of the same immediate product scope.

### What Was Directionally Right

- building a runtime-first center in `core/runtime.py`
- introducing normalized command and adapter flows
- supporting multiple providers through `providers/*`
- keeping tool policy and MCP in the runtime/tool layer
- creating a browser path as a future major surface
- treating memory and autonomy as part of the core product direction

These are consistent with Gestalt.

### What Went Wrong

- too much work was landed in one oversized expansion wave
- speculative systems were added directly under `core/*`
- legacy `services/*` remains deeply entangled with runtime assembly
- the web surface has overlapping protocols
- docs and status claims got ahead of code and test truth
- generated artifacts and asset piles were committed into the repo

The main issue is not lack of ambition. The issue is lack of architectural
containment.

### Original Focus vs Drift

The original focus was mostly surface and runtime maturation:

- Discord cleanup
- behavior quality
- web adapter
- terminal/TUI
- MCP bridge

The drift happened when the repo started trying to land all of these at once:

- broad agentic framework layers
- planner systems
- social-intelligence subsystems
- RL scaffolding
- RuneScape agent work
- browser embodiment and VRM experimentation
- large documentation/report waves claiming full completion

Those exploratory areas are not wrong in themselves. They were wrong to treat as
current platform truth at the same time.

## Subsystem Review

### 1. Runtime Core

Representative files:

- `core/runtime.py`
- `core/commands.py`
- `core/router.py`
- `core/autonomy.py`
- `core/persona_engine.py`
- `core/auth.py`

Alignment:

- strongly aligned

Reasoning:

- this is the runtime authority layer
- it matches the intended Gestalt identity
- it is the part of the repo that most clearly acts like a framework instead of
  a feature pile

Problems:

- `core/runtime.py` still reaches into experimental social-intelligence code at
  `core/runtime.py:512`
- adjacent `core/*` namespaces are crowded with speculative framework layers

Decision:

- `Keep` the canonical runtime files
- `Refactor` runtime seams that still pull in experimental or legacy behavior
- `Quarantine` speculative neighboring framework layers so `core` stops meaning
  "everything"

Pruning impact:

- do not prune the runtime backbone
- prune the illusion that all of `core/*` is equally canonical

### 2. Experimental Core Expansion

Representative areas:

- `core/agentic/*`
- `core/planner/*`
- `core/social_intelligence/*`
- `core/agent_protocol.py`
- `core/agent_selector.py`
- `core/collaboration.py`
- `core/consensus.py`
- `core/delegation.py`
- `core/message_bus.py`
- `core/pubsub.py`

Alignment:

- partially aligned in theme
- misaligned in current placement and maturity

Reasoning:

- these areas point toward real long-term goals: planning, collaboration,
  learning, embodied action, richer autonomy
- but they currently overstate the maintained product surface
- placing them under `core/*` makes them look like runtime authority instead of
  experiments or future tracks

Concrete concerns:

- `core/social_intelligence/*` is already wired into canonical paths:
  - `core/runtime.py:512`
  - `adapters/web/websocket.py:390`
- `core/agentic/vrm_controller.py` is not the real embodiment layer, but it
  reads like core product runtime ownership
- `core/planner/*` is large and ambitious, but not yet part of the honest
  canonical Gestalt surface

Decision:

- `Quarantine`

Pruning impact:

- keep the code for reference or future adoption
- remove it from architecture truth
- stop documenting it as active platform capability unless specifically loaded,
  tested, and product-owned

### 3. Adapters: CLI and TUI

Representative areas:

- `adapters/cli/*`
- `adapters/tui/*`

Alignment:

- aligned

Reasoning:

- CLI/TUI are legitimate operator surfaces for a runtime-first framework
- they fit the "personal agentic framework" vision
- they are useful even if the web UI becomes the primary cockpit

Problems:

- they should remain runtime-only adapters and not re-grow local logic
- TUI/browser parity should not create new authority layers

Decision:

- `Keep`

Pruning impact:

- no structural pruning needed
- continue checking for adapter-side authority drift

### 4. Adapters: Web Runtime Surface

Representative files:

- `adapters/web/adapter.py`
- `adapters/web/routes.py`
- `adapters/web/websocket.py`
- `adapters/web/auth.py`

Alignment:

- aligned in direction
- not yet clean enough in structure

Reasoning:

- a web runtime surface fits the current Gestalt vision
- browser-based interaction is now a core long-term direction
- runtime-backed HTTP + websocket transport is the right model

Problems:

- there are still two websocket protocols mounted:
  - runtime websocket at `adapters/web/adapter.py:174`
  - legacy simple websocket at `adapters/web/adapter.py:180`
- the older simple handler still exists at
  `adapters/web/websocket.py:652`
- that means the product has not fully chosen one canonical web transport

Decision:

- `Keep` as a product surface
- `Refactor` to one canonical runtime protocol

Pruning impact:

- prune duplicated or legacy web transport behavior
- keep the web runtime as one of the main Gestalt surfaces

### 5. Adapters: Browser/Desktop Client

Representative areas:

- `adapters/desktop/src/*`
- `adapters/desktop/src-tauri/*`
- `adapters/desktop/public/avatars/*`
- `adapters/desktop/public/motions/*`

Alignment:

- strategically aligned
- operationally overgrown

Reasoning:

- browser-first interaction and eventual Tauri packaging fit Gestalt
- VRM/VRMA experimentation fits the embodiment direction
- this is the right place for future scene systems

Problems:

- the adapter footprint is dominated by tracked generated artifacts
- asset volume currently exceeds product maturity
- Tauri packaging work can easily distract from runtime clarity

Concrete facts:

- `adapters/desktop` currently occupies `2.7G`
- tracked files under `src-tauri/target/**`: `5020`
- tracked files under `node_modules/**`: `4087`

Decision:

- `Refactor` the source client
- `Quarantine` large motion/avatar asset piles until there is a governed asset
  policy
- `Delete` generated build output from source control

Pruning impact:

- remove tracked build artifacts immediately
- keep the client source
- treat embodiment as future-facing, not current architecture truth

### 6. Adapters: Discord

Representative areas:

- `adapters/discord/*`
- `adapters/discord/commands/*`

Alignment:

- aligned in product vision
- mixed in implementation

Reasoning:

- Discord is still part of Gestalt's intended surface area
- multi-persona interaction in Discord fits the framework
- it matters for the "many personas" part of the vision

Problems:

- Discord paths still pull in legacy service-layer dependencies
- some command paths are runtime-first, some are not cleanly separated

Concrete examples:

- `adapters/discord/commands/chat/main.py` uses
  `adapters.runtime_factory` and also imports legacy service-layer components
- `adapters/discord/chat.py` and `adapters/discord/commands/social.py`
  reference legacy persona facilitation layers

Decision:

- `Refactor`

Pruning impact:

- prune the legacy dependency surface inside Discord
- keep Discord as a real Gestalt surface

### 7. Adapters: RuneScape

Representative area:

- `adapters/runescape/*`

Alignment:

- aligned with long-term learning experimentation
- misaligned with current product identity

Reasoning:

- a bounded environment where Gestalt learns actions can fit long-term goals
- RuneScape can be a sandbox track for action learning
- but it is not part of the honest core product today

Problems:

- it arrived during the same expansion wave that widened architecture too far
- it competes with the main Gestalt identity instead of extending it cleanly

Decision:

- `Quarantine`

Pruning impact:

- keep it as an experiment
- remove it from the current product definition

### 8. Providers

Representative area:

- `providers/*`

Alignment:

- strongly aligned

Reasoning:

- many model providers are part of the core vision
- provider routing is one of Gestalt's real strengths
- this area already fits the runtime-first framework model well

Problems:

- embeddings support exists but needs a clearer maturity story

Decision:

- `Keep`
- `Refactor` embeddings to explicit product ownership

Pruning impact:

- no major pruning

### 9. Tools and MCP

Representative areas:

- `tools/*`
- `mcp_client/*`

Alignment:

- strongly aligned

Reasoning:

- MCP should be first-class in Gestalt
- the tool layer is central to autonomy, action, and connectors
- this is part of the actual framework identity, not an edge feature

Problems:

- the long-term connector story still needs clearer documentation
- some future app/home integrations are not yet represented cleanly

Decision:

- `Keep`

Pruning impact:

- no major pruning
- expand carefully, not broadly

### 10. Memory

Representative areas:

- `memory/*`

Alignment:

- aligned

Reasoning:

- memory is one of Gestalt's defining capabilities
- RAG, summaries, episodic recall, and future procedural memory all fit the
  intended direction

Problems:

- not every memory-related module is equally mature
- some modules look like future capability rather than current product truth

Decision:

- `Keep` the base memory stack
- `Refactor` the broader memory experiments

Pruning impact:

- keep the memory story central
- prune maturity claims, not the entire area

### 11. Legacy Services

Representative areas:

- `services/core/*`
- `services/conversation/*`
- `services/persona/*`
- `services/llm/*`
- `services/memory/*`
- `services/voice/*`
- `services/agents/*`
- `services/interfaces/*`
- `services/clients/*`

Alignment:

- mixed

Reasoning:

- this directory contains real legacy implementation value
- it also contains the strongest architectural pull away from the runtime-first
  framework

Concrete concerns:

- `launcher.py` still imports `ServiceFactory` at `launcher.py:27`
- `main.py` still uses `ServiceFactory` and `services.interfaces.llm_interface`
- `adapters/runtime_factory.py` still composes the runtime from legacy service
  components:
  - `services.persona.router`
  - `services.memory.context_router`
  - `services.conversation.orchestrator`
  - `services.conversation.persistence`
  - `services.conversation.review`
- `services/core/factory.py` is still a broad old-world composition root
- `services/agents/*` is effectively a second agent framework

Decision:

- `Refactor` legacy services that still feed the runtime
- `Quarantine` agent-framework and RL-heavy side layers

Pruning impact:

- this is one of the most important medium-term cleanup targets
- the goal is not "delete services"
- the goal is "stop services from defining Gestalt's architecture"

### 12. Legacy Cogs

Representative area:

- `cogs/*`

Alignment:

- partially aligned as legacy Discord surface
- not aligned as architecture truth

Reasoning:

- Discord remains important
- the legacy cog tree should not continue to define system design

Decision:

- `Refactor`

Pruning impact:

- keep what still serves Discord product goals
- retire what only preserves legacy breadth

### 13. Frontend Prototype

Representative area:

- `frontend/*`

Alignment:

- thematically aligned
- structurally superseded

Reasoning:

- browser embodiment and scene ideas fit Gestalt
- but the main browser client path has moved into `adapters/desktop/*`
- keeping a parallel `frontend/*` surface increases ambiguity

Decision:

- `Quarantine`

Pruning impact:

- either archive as prototype history or remove once any useful code is
  migrated

### 14. Docs

Representative area:

- `docs/*`

Alignment:

- mixed

Reasoning:

- docs are where the repo most clearly drifted away from honest product truth
- but docs are also where the realignment is now being enforced

Current aligned set:

- `docs/VISION.md`
- `docs/GROUND_TRUTH.md`
- `docs/DEVELOPMENT_FLOW.md`
- `docs/FEATURES.md`
- `docs/STATUS.md`
- `docs/historical/REPO_AUDIT.md`
- `docs/historical/CODEBASE_REVIEW.md`
- `docs/SUBSYSTEM_CLASSIFICATION.md`

Misaligned or historical sets:

- broad completion artifacts
- old framework-breadth docs
- legacy setup and workflow documents
- large codebase-summary documents that imply stronger current ownership than
  the code supports

Decision:

- `Keep` canonical governance docs
- `Refactor` docs that should survive but need rewriting
- `Quarantine` historical breadth docs
- `Delete` duplicate/generated/report-wave artifacts

Pruning impact:

- documentation must now follow the product, not lead it

## High-Priority Misalignments

These are the most important mismatches between the current repo and the
intended Gestalt framework.

### P0: Generated Artifacts in Source Control

Examples:

- `adapters/desktop/src-tauri/target/**`
- `adapters/desktop/node_modules/**`

Why it matters:

- bloats the repo
- confuses source versus output
- makes audits noisier than they should be

Required action:

- delete tracked generated artifacts
- fix `.gitignore`

### P0: Runtime Composition Still Depends on Legacy Services

Examples:

- `launcher.py:27`
- `launcher.py:201`
- `adapters/runtime_factory.py:44`
- `adapters/runtime_factory.py:54`
- `adapters/runtime_factory.py:71`

Why it matters:

- the runtime-first architecture is still partially propped up by old service
  composition
- this blocks a clean statement of "what Gestalt is"

Required action:

- map every remaining service dependency
- decide which ones migrate into canonical runtime seams and which ones stay
  legacy

### P0: Web Protocol Duplication

Examples:

- `adapters/web/adapter.py:174`
- `adapters/web/adapter.py:180`
- `adapters/web/websocket.py:652`

Why it matters:

- two websocket paths means two mental models
- that breaks surface clarity

Required action:

- consolidate to one canonical runtime-backed web protocol

### P1: Experimental Core Areas Still Leak Into Canonical Paths

Examples:

- `core/runtime.py:512`
- `adapters/web/websocket.py:390`

Why it matters:

- quarantined areas are not actually quarantined if runtime and web import them

Required action:

- either fully adopt and test these areas as canonical
- or remove their runtime-path imports

## Pruning Plan

### Phase 1: Repository Hygiene

- remove tracked generated desktop artifacts
- update `.gitignore`
- remove equivalent caches and build output across the repo

### Phase 2: Surface Truth

- collapse web transport to one canonical runtime protocol
- document browser client maturity honestly
- keep CLI and TUI as canonical operator surfaces

### Phase 3: Runtime Boundary Cleanup

- review every `services/*` dependency pulled by `launcher.py` and
  `adapters/runtime_factory.py`
- separate required migration seams from legacy-only baggage

### Phase 4: Experimental Containment

- quarantine `core/agentic/*`
- quarantine `core/planner/*`
- quarantine `core/social_intelligence/*`
- quarantine `adapters/runescape/*`
- quarantine `frontend/*`

### Phase 5: Documentation Truth

- rewrite surviving historical docs only after code ownership is settled
- keep the canonical doc set small and strict

## Final Judgment

The codebase does contain the real Gestalt framework.

It lives mainly in:

- runtime
- providers
- tools and MCP
- memory
- CLI/TUI/web runtime surfaces

What went off track was everything around that center:

- speculative expansion
- legacy dependency drag
- multiple competing surfaces
- overstated documentation
- committed build output

The correct response is not to throw the project away.

The correct response is to:

1. preserve the real runtime-first center
2. prune or quarantine misleading breadth
3. migrate only the parts that truly support the Gestalt vision
