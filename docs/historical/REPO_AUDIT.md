# Repository Audit

**Last Updated**: 2026-03-10

## Purpose

This is the first-pass inventory for bringing the repository back into alignment with the Gestalt vision.

It is not a claim that the repo has been fully cleaned up. It is the working map for:

- feature layout
- legacy identification
- mistake detection
- pruning decisions
- architecture truth work

Use this together with:

- [VISION.md](/root/acore_bot/docs/VISION.md)
- [GROUND_TRUTH.md](/root/acore_bot/docs/GROUND_TRUTH.md)
- [DEVELOPMENT_FLOW.md](/root/acore_bot/docs/DEVELOPMENT_FLOW.md)
- [FEATURES.md](/root/acore_bot/docs/FEATURES.md)

## Audit Summary

The repository currently contains four different kinds of material:

1. `Canonical product`
   Runtime-first Gestalt code that matches the actual product direction.

2. `Valuable but misaligned`
   Code that may matter later, but is not currently integrated into the maintained runtime-first surface.

3. `Experimental sprawl`
   Large subsystems that may be interesting, but currently distort the product boundary.

4. `Repository mistakes`
   Generated artifacts, stale docs, duplicated paths, or misleading surfaces that should not remain as product truth.

## Inventory Snapshot

Counts below exclude obvious `__pycache__` files and `AGENTS.md` files.

| Area | Approx. file count | First-pass classification |
|---|---:|---|
| `core/` | 61 | Mixed: canonical runtime + speculative subsystems |
| `adapters/` | 2386 | Mixed: canonical adapters + desktop artifacts + RuneScape side project |
| `providers/` | 6 | Canonical |
| `tools/` | 7 | Canonical |
| `memory/` | 12 | Canonical with some non-core extensions |
| `services/` | 96 | Mostly legacy/misaligned |
| `cogs/` | 20 | Legacy |
| `docs/` | 81 | Mixed: canonical docs + historical sprawl |

Important note:

- `adapters/` is artificially inflated by committed desktop build output and motion assets.
- This is a repository hygiene problem as well as a product-boundary problem.

## Canonical Product Areas

These are the parts of the repo that currently match the real Gestalt product and should be preserved as the primary architecture.

### Keep

- `core/runtime.py`
- `core/commands.py`
- `core/schemas.py`
- `core/router.py`
- `core/persona_engine.py`
- `core/autonomy.py`
- `providers/*`
- `tools/*`
- `mcp_client/*`
- `memory/base.py`
- `memory/local_json.py`
- `memory/manager.py`
- `memory/summary.py`
- `memory/rag.py`
- `adapters/runtime_factory.py`
- `adapters/cli/*`
- `adapters/tui/*`
- `adapters/web/adapter.py`
- `adapters/web/routes.py`
- `adapters/web/websocket.py`
- `gestalt/runtime_stdio.py`

Reason:

These define the runtime-first framework and its maintained user/operator surfaces.

## Valuable But Needs Refactor

These areas may contain useful capability, but they are not currently clean canonical product.

### Refactor

- `adapters/desktop/*`
  Browser client is directionally right, but should remain a runtime consumer and needs cleanup before it counts as primary product.

- `memory/episodes.py`
- `memory/auto_summary.py`
- `memory/recall_tuner.py`
- `memory/summary_generator.py`
  Potentially useful learning/memory features, but they need explicit ownership and verified integration.

- `adapters/discord/*`
  Discord is still part of the desired Gestalt surface, but the repo contains both newer adapter paths and legacy command/cog ecosystems.

Reason:

These match the vision, but not yet in a clean, fully governed form.

## Experimental Or Misaligned Subsystems

These are the major areas currently driving architectural drift.

### Quarantine

- `core/agentic/*`
  VRM/gesture/embodiment experiments in a high-authority namespace.

- `core/planner/*`
  Large planning/executor stack added to core without clear canonical adoption.

- `core/social_intelligence/*`
  Broad learning/adaptation system that may be valuable, but currently expands core authority faster than the maintained product surface justifies.

- `adapters/runescape/*`
  Interesting side project, but not part of the current canonical Gestalt surface.

- `services/persona/rl/*`
  Large RL stack that belongs to a separate track until there is a governed learning architecture around it.

Reason:

These areas may be worth revisiting later, but they should not currently define “what Gestalt is.”

## Legacy Areas

These are older systems that still exist in the repo, but should not define architecture truth.

### Legacy

- `services/*` broadly
- `cogs/*` broadly
- older Discord command and service patterns
- older analytics/dashboard/service-layer orchestration code

Reason:

These represent historical repo breadth rather than the current runtime-first product.

## Repository Mistakes

These are not architectural debates. They are cleanup targets.

### Delete or Remove From Tracking

- committed desktop build artifacts under `adapters/desktop/src-tauri/target/*`
- generated Rust dependency/build output under the desktop adapter
- oversized motion/media asset piles that are not part of a governed product slice
- stale historical completion and verification documents already identified and pruned

Reason:

These inflate repo size, confuse audits, and make the project feel more complete than it is.

## First-Pass Classification Table

| Area | Classification | Action |
|---|---|---|
| Runtime core | Keep | Preserve and strengthen |
| CLI/TUI/Web runtime surfaces | Keep | Preserve and improve |
| Browser desktop scaffold | Refactor | Keep as scaffold, not product truth |
| Discord adapter path | Refactor | Unify around runtime-first flow |
| Memory extensions | Refactor | Decide what is actually active |
| Planner / social intelligence / core agentic | Quarantine | Remove from product truth and review one by one |
| RuneScape adapter | Quarantine | Separate from main product until explicitly reintroduced |
| Services and cogs | Legacy | Triage into keep/migrate/delete |
| Generated build artifacts | Delete | Remove from repo tracking |

## Biggest Drift Drivers

### 1. Core Namespace Inflation

`core/` now contains:

- runtime-first essentials
- embodiment experiments
- planner stack
- social intelligence stack
- agent collaboration abstractions

This makes `core` look like the product boundary for every idea, which is not sustainable.

### 2. Surface Duplication

The repo contains:

- CLI
- TUI
- web runtime
- browser client
- Discord adapter
- legacy cogs
- older frontend demo code
- RuneScape side project

That is too many “surfaces” to maintain as if they are equal.

### 3. Documentation Breadth

`docs/` still reflects a much broader system than the current canonical product. Much of it should be treated as historical or legacy documentation, not present product truth.

## Recommended Pruning Sequence

### Phase 1

- remove committed generated desktop build artifacts
- keep canonical docs aligned
- freeze new subsystem expansion

Status:

- execution started on 2026-03-10
- tracked desktop build artifacts are being removed from source control
- `.gitignore` is being updated to prevent reintroduction of desktop build output

### Phase 2

- quarantine `core/agentic/*`
- quarantine `core/planner/*`
- quarantine `core/social_intelligence/*`
- mark those areas explicitly as experimental in architecture docs

Web transport consolidation note:

- the legacy simple `/ws` websocket path has been removed from
  `adapters/web/adapter.py`
- `/api/runtime/ws` is now the single maintained runtime websocket surface
- older demo usage has been updated to the canonical runtime websocket protocol

### Phase 3

- triage `services/*` and `cogs/*` into:
  - keep and migrate
  - keep as legacy
  - delete

### Phase 4

- rewrite architecture docs around only the kept/refactored system

## What This Audit Is Missing

This first pass is structural.

It does not yet contain:

- per-file deletion decisions
- dependency analysis for each subsystem
- execution order for code removal
- final architecture diagram for the post-prune repo

Those should be the next audit steps.
