# Codebase Review

**Last Updated**: 2026-03-10

## Purpose

This review evaluates the current repository against the intended Gestalt vision.

It answers four questions:

1. What did recent work get right?
2. What did it get wrong?
3. What are the highest-risk architectural problems right now?
4. What solution tracks should follow from the audit?

This is a codebase review, not a completion report.

## Executive Summary

The repository is not failing mechanically. The runtime-first core still exists, tests still pass, and several important product directions were correct:

- runtime authority
- command registry work
- TUI/web/browser runtime surfaces
- provider/tool/memory centralization
- browser-oriented future thinking

But the codebase drifted badly in scope and product definition.

The main problem is not one bug. It is that the repo absorbed too many futures at once:

- runtime platform
- browser client
- Discord product
- planner stack
- social intelligence stack
- RL stack
- VRM embodiment experiments
- RuneScape side project
- old service-layer system

The result is a repository where too many subsystems look like “the product” at the same time.

## What Recent Work Got Right

### 1. Runtime-First Center of Gravity

The most important positive is that the repo still has a real runtime-first backbone:

- `core/runtime.py`
- `core/commands.py`
- `core/schemas.py`
- `providers/*`
- `tools/*`
- `memory/*`

That is the right place for Gestalt to be anchored.

### 2. Runtime-Driven Surface Direction

The best surface work followed the correct rule:

- runtime defines commands and state
- adapters render and transport

This is visible in:

- `adapters/tui/*`
- `adapters/web/routes.py`
- `adapters/web/websocket.py`

That is still the correct pattern for future browser and Discord work.

### 3. MCP and Extensibility Direction

Keeping tool policy and MCP inside the runtime/tool layer was the right call.

That supports the long-term Gestalt vision:

- external connectors
- Home Assistant
- app automation
- future tool learning

### 4. Browser Direction Was Strategically Correct

Moving toward a browser-based runtime client was not a mistake.

It is the right long-term direction for:

- richer UX
- embodiment
- better operator visibility
- future scenes and presence

The mistake was not “browser.” The mistake was letting the browser/desktop branch create too much product ambiguity before the architecture was stabilized.

## What Recent Work Got Wrong

### 1. Scope Explosion

The single biggest problem was trying to advance too many product lines at once.

Instead of one Gestalt, the repo started acting like it was simultaneously:

- a runtime framework
- a Discord bot platform
- a browser agent product
- a VRM embodiment stack
- an RL research repo
- a RuneScape agent framework
- a social intelligence research branch

That destroyed clarity.

### 2. Core Namespace Abuse

The `core/` package became the landing zone for too many speculative systems:

- `core/agentic/*`
- `core/planner/*`
- `core/social_intelligence/*`

That is dangerous because `core/` implies architectural authority. Experimental code placed there looks canonical even when it is not.

### 3. Documentation Drift

The repo accumulated completion/status/report documentation that outpaced reality.

This encouraged the wrong behavior:

- plans became status
- reports became truth
- breadth of code was mistaken for product maturity

That is exactly the kind of failure that causes long-term drift.

### 4. Surface Duplication

The web surface currently has more than one conceptual protocol:

- canonical runtime websocket path
- older simple websocket path

Discord also exists in both:

- runtime-first adapter paths
- older cog/service command ecosystems

This duplicates maintenance and muddies authority.

### 5. Repository Hygiene Failure

The desktop adapter currently has committed generated build artifacts and very large media piles:

- `adapters/desktop/src-tauri/target`: about `2.6G`
- `adapters/desktop/public/motions`: about `77M`

This is a repository management mistake, not just an architectural issue.

## Findings

### P0: Generated desktop build output is committed to the repository

Evidence:

- `adapters/desktop/src-tauri/target` is tracked by git
- current size is about `2.6G`
- `.gitignore` does not exclude that target tree

References:

- [`.gitignore`](/root/acore_bot/.gitignore)
- [`adapters/desktop/src-tauri/target`](/root/acore_bot/adapters/desktop/src-tauri/target)

Why this matters:

- massively inflates repo size
- pollutes audits
- hides the real size and shape of the product
- encourages “build output as source” habits

Recommended action:

- remove `adapters/desktop/src-tauri/target` from version control
- ignore it explicitly
- treat built artifacts as ephemeral

### P0: Launcher and runtime assembly still depend heavily on legacy service-layer construction

Evidence:

- `launcher.py` still imports `ServiceFactory` from `services.core.factory`
- `adapters/runtime_factory.py` still reaches into legacy `services.*` modules for persona, memory, and conversation seams

References:

- [launcher.py](/root/acore_bot/launcher.py#L27)
- [launcher.py](/root/acore_bot/launcher.py#L199)
- [adapters/runtime_factory.py](/root/acore_bot/adapters/runtime_factory.py#L42)
- [adapters/runtime_factory.py](/root/acore_bot/adapters/runtime_factory.py#L52)
- [adapters/runtime_factory.py](/root/acore_bot/adapters/runtime_factory.py#L62)

Why this matters:

- prevents a clean runtime-first product boundary
- keeps legacy service graph logic central to startup
- makes it hard to know what the actual supported architecture is

Recommended action:

- split launcher paths into:
  - canonical runtime-first startup
  - legacy startup compatibility
- reduce `adapters/runtime_factory.py` dependence on `services/*`

### P0: Canonical web runtime path coexists with an older simple websocket surface

Evidence:

- `/api/runtime/ws` is the maintained runtime protocol
- `/ws` still exists as a separate simple websocket surface
- the simple websocket path still creates `AcoreEvent`, calls `event_callback`, and sends ad hoc `response` / `ack`

References:

- [adapters/web/adapter.py](/root/acore_bot/adapters/web/adapter.py#L173)
- [adapters/web/adapter.py](/root/acore_bot/adapters/web/adapter.py#L179)
- [adapters/web/websocket.py](/root/acore_bot/adapters/web/websocket.py#L652)
- [adapters/web/websocket.py](/root/acore_bot/adapters/web/websocket.py#L689)
- [adapters/web/websocket.py](/root/acore_bot/adapters/web/websocket.py#L704)

Why this matters:

- duplicated semantics
- duplicated maintenance
- unclear client contract
- reintroduces pre-runtime-style edge behavior

Recommended action:

- bless `/api/runtime/*` and `/api/runtime/ws` as canonical
- deprecate or quarantine `/ws`

### P1: Experimental social-intelligence code is already wired into canonical runtime paths

Evidence:

- runtime observation handling imports social-intelligence style learning directly
- web websocket runtime path imports `SILRuntimeHooks`

References:

- [core/runtime.py](/root/acore_bot/core/runtime.py#L511)
- [adapters/web/websocket.py](/root/acore_bot/adapters/web/websocket.py#L386)

Why this matters:

- makes `core/social_intelligence/*` more than just “present but unused”
- complicates efforts to quarantine or simplify core
- creates hidden behavior changes in canonical surfaces

Recommended action:

- decide whether social intelligence is:
  - canonical runtime extension
  - optional plugin-like extension
  - experiment to quarantine
- remove implicit imports from the hot path until that decision is made

### P1: `core/agentic/*` occupies a core namespace without clear product adoption

Evidence:

- `core/agentic/*` contains VRM controller, gestures, lip-sync, websocket client, action mapping
- this is embodiment-oriented infrastructure under `core/`
- it is not part of the current canonical surface definition

Reference:

- [core/agentic](/root/acore_bot/core/agentic)

Why this matters:

- implies core authority for an unfinished or unadopted subsystem
- confuses the product story
- makes future embodiment harder to stage cleanly

Recommended action:

- move to an explicit experimental namespace or quarantine decision
- do not leave embodiment experiments as implicit core product

### P1: Browser/desktop branch includes too many committed assets for its current maturity level

Evidence:

- large number of VRMA/BVH assets in `adapters/desktop/public/motions`
- browser/desktop is still only `Present but unused` in product truth

References:

- [adapters/desktop/public/motions](/root/acore_bot/adapters/desktop/public/motions)
- [docs/FEATURES.md](/root/acore_bot/docs/FEATURES.md)

Why this matters:

- browser scaffold is outweighed by asset mass
- signals false maturity
- complicates source control and review

Recommended action:

- keep only the minimal set of motions needed for the current validated UX
- move optional asset packs out of the main source tree or make them opt-in

### P2: Documentation surface is still broader than the canonical product

Evidence:

- many docs still describe social intelligence, RL, production readiness, codebase breadth, and legacy systems in detail
- current canonical docs are now correct, but the historical doc surface remains large

References:

- [docs](/root/acore_bot/docs)
- [docs/README.md](/root/acore_bot/docs/README.md)

Why this matters:

- people will continue to mistake repo breadth for current product
- future agents will drift if they read breadth before truth

Recommended action:

- gradually classify docs into:
  - canonical
  - historical
  - legacy
  - experimental

## What The Review Suggests We Keep

Strongest keep candidates:

- runtime-first orchestration
- command system
- provider registry/router
- tool policy and MCP
- memory manager and local memory primitives
- CLI/TUI/web runtime surfaces
- browser client as scaffold only
- Discord as a desired future/refactor surface

## What The Review Suggests We Refactor

- `adapters/runtime_factory.py`
- `launcher.py`
- browser desktop client surface
- Discord runtime/cog boundary
- memory extensions not clearly integrated

## What The Review Suggests We Quarantine

- `core/agentic/*`
- `core/planner/*`
- `core/social_intelligence/*`
- `adapters/runescape/*`
- `services/persona/rl/*`

## What The Review Suggests We Delete

- committed desktop build artifacts
- stale or redundant generated desktop files
- any remaining misleading status/report documents

## Solution Tracks

### Track 1: Repository Hygiene

- remove committed build output
- add missing ignore rules
- reduce tracked media weight where possible

### Track 2: Runtime Boundary Cleanup

- simplify `launcher.py`
- simplify `adapters/runtime_factory.py`
- reduce dependency on legacy services

### Track 3: Surface Consolidation

- make `/api/runtime/*` and `/api/runtime/ws` the only maintained web surface
- clearly separate browser scaffold from product truth
- decide the real Discord path

### Track 4: Experimental Containment

- quarantine planner, social intelligence, embodiment, and RuneScape tracks
- only reintroduce pieces through explicit adoption

### Track 5: Architecture Truth Rewrite

- after pruning decisions, rewrite architecture docs around only the kept system

## Recommended Next Step

The next concrete step should be a subsystem-by-subsystem classification document with explicit decisions for:

- `core/*`
- `adapters/*`
- `services/*`
- `cogs/*`
- `docs/*`

That should produce a final map of:

- keep
- refactor
- quarantine
- delete

and then we can execute the cleanup in safe vertical slices.
