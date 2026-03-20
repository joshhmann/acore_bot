# Subsystem Classification

**Last Updated**: 2026-03-10

## Purpose

This document assigns each major subsystem in the repository to one of four buckets:

- `Keep`
- `Refactor`
- `Quarantine`
- `Delete`

This is the first concrete decision layer after:

- [VISION.md](/root/acore_bot/docs/VISION.md)
- [GROUND_TRUTH.md](/root/acore_bot/docs/GROUND_TRUTH.md)
- [ENGINEERING_OPERATING_MODEL.md](/root/acore_bot/docs/ENGINEERING_OPERATING_MODEL.md)

It is intended to drive cleanup work.

## Classification Rules

### Keep

The subsystem is part of the canonical Gestalt product today.

### Refactor

The subsystem belongs in the intended product, but its current shape or boundaries are wrong.

### Quarantine

The subsystem may have future value, but it should not currently define product architecture or status.

### Delete

The subsystem or files are repository mistakes, generated output, redundant artifacts, or product-hostile clutter.

## Core

### Keep

- `core/runtime.py`
- `core/commands.py`
- `core/schemas.py`
- `core/router.py`
- `core/persona_engine.py`
- `core/autonomy.py`
- `core/auth.py`

Reason:

These are the runtime-first heart of Gestalt.

### Refactor

- `core/context_budget.py`
- `core/self_check.py`
- `core/workspace.py`
- `core/interfaces.py`
- `core/types.py`

Reason:

These may still support the intended framework, but they need validation against the canonical runtime path and clearer ownership.

### Quarantine

- `core/agentic/*`
- `core/planner/*`
- `core/social_intelligence/*`
- `core/agent_protocol.py`
- `core/agent_selector.py`
- `core/capabilities.py`
- `core/collaboration.py`
- `core/consensus.py`
- `core/delegation.py`
- `core/message_bus.py`
- `core/pubsub.py`
- `core/review_prompts.py`

Reason:

These represent speculative or expanded frameworks that may have value, but they currently widen `core` beyond what the maintained product can honestly support.

### Delete

- `core/__pycache__/*`

Reason:

Generated artifacts do not belong in source control.

## Adapters

### Keep

- `adapters/runtime_factory.py`
- `adapters/cli/*`
- `adapters/tui/*`
- `adapters/discord/discord_bot.py`
- `adapters/discord/commands/runtime_chat.py`
- `adapters/discord/commands/help.py`
- `adapters/discord/commands/system.py`
- `adapters/discord/commands/social.py`
- `adapters/discord/commands/profile.py`
- `adapters/discord/commands/search.py`
- `adapters/web/adapter.py`
- `adapters/web/routes.py`
- `adapters/web/websocket.py`
- `adapters/web/auth.py`
- `adapters/web/api_schema.py`

Reason:

These are the maintained runtime-first surfaces and runtime composition path.

### Refactor

- `adapters/runtime_factory.py`
- `adapters/web/output.py`
- `adapters/web/static/index.html`
- `adapters/desktop/src/*`
- `adapters/desktop/src-tauri/src/main.rs`
- `adapters/discord/adapter.py`
- `adapters/discord/output.py`
- `adapters/discord/chat.py`
- `adapters/discord/review.py`

Reason:

- `runtime_factory.py` is canonical but still carries compatibility seams.
- the browser/desktop client is strategically right but not yet a canonical product surface.
- Discord is now maintained through a runtime-first startup path, but several legacy or duplicate Discord modules still need quarantine or removal.

### Quarantine

- `adapters/runescape/*`
- `adapters/desktop/public/avatars/*`
- `adapters/desktop/public/motions/*`

Reason:

RuneScape is a side track, not current Gestalt product.

The VRM/motion assets are not inherently bad, but the current asset pile is too large and too loosely governed for the present product stage.

### Delete

- `adapters/desktop/node_modules/*`
- `adapters/desktop/dist/*`
- `adapters/desktop/src-tauri/target/*`
- generated desktop schema/build output under `adapters/desktop/src-tauri/gen/*` if reproducible from build

Reason:

These are generated artifacts and local build output, not source.

## Providers

### Keep

- `providers/base.py`
- `providers/router.py`
- `providers/registry.py`
- `providers/openai_compat.py`

Reason:

Canonical runtime provider layer.

### Refactor

- `providers/embeddings.py`

Reason:

Potentially important for the long-term learning/memory story, but needs explicit integration and ownership.

### Delete

- `providers/__pycache__/*`

## Tools and MCP

### Keep

- `tools/policy.py`
- `tools/registry.py`
- `tools/runner.py`
- `tools/mcp_source.py`
- `tools/file_ops.py`
- `tools/shell_exec.py`

Reason:

Canonical Gestalt action/tool layer.

### Delete

- `tools/__pycache__/*`

## Memory

### Keep

- `memory/base.py`
- `memory/local_json.py`
- `memory/manager.py`
- `memory/summary.py`
- `memory/rag.py`

Reason:

Canonical current memory system.

### Refactor

- `memory/episodes.py`
- `memory/auto_summary.py`
- `memory/recall_tuner.py`
- `memory/summary_generator.py`
- `memory/working.py`
- `memory/chroma_store.py`

Reason:

These may support the intended learning/memory future, but they need explicit decisions about whether they are current product or future work.

### Delete

- `memory/__pycache__/*`

## Services

### Refactor

- `services/core/*`
- `services/discord/*`
- `services/llm/*`
- `services/memory/*`
- `services/persona/*` excluding `services/persona/rl/*`
- `services/voice/*`
- `services/analytics/dashboard.py`

Reason:

These are where the old product breadth lives. Some of this may be migrated or retained, but it should not currently define architecture truth.

The likely long-term outcome is mixed:

- some pieces migrate into runtime-owned systems
- some remain legacy-only
- some get removed

### Quarantine

- `services/persona/rl/*`
- `services/agents/*`
- `services/interfaces/*`
- `services/clients/*`

Reason:

- RL is a future direction, not current product authority.
- `services/agents/*` represents another agent framework layer competing with runtime.
- interfaces/clients here likely reflect older decomposition that should not expand further until the main product boundary is stable.

### Delete

- `services/__pycache__/*`

## Cogs

### Refactor

- all of `cogs/*`

Reason:

The repo still wants Discord as part of Gestalt, but the legacy cog ecosystem should not define architecture truth.

The likely future split is:

- runtime-first Discord path kept
- useful command surfaces migrated or wrapped
- legacy-only or duplicate cogs retired

### Delete

- `cogs/__pycache__/*`

## Docs

### Keep

- `docs/VISION.md`
- `docs/GROUND_TRUTH.md`
- `docs/DEVELOPMENT_FLOW.md`
- `docs/ENGINEERING_OPERATING_MODEL.md`
- `docs/SUBSYSTEM_CLASSIFICATION.md`
- `docs/FEATURES.md`
- `docs/STATUS.md`
- `docs/adr/*`
- `docs/README.md`

Reason:

These are the canonical documentation set for realignment.

### Refactor

- `docs/ARCHITECTURE.md`
- `docs/CLI.md`
- `docs/COMMANDS.md`
- `docs/CONFIGURATION.md`
- `docs/DEPLOYMENT.md`
- `docs/TRACE.md`
- `docs/CONTRIBUTING.md`
- `docs/REFACTORING_PLAN.md`
- `docs/TECH_DEBT.md`

Reason:

These should survive, but need to be rewritten to match the real kept system after pruning decisions are executed.

### Quarantine

- `docs/AGENTIC_FRAMEWORK_PHASE1.md`
- `docs/BEHAVIOR_ENGINE.md`
- `docs/COGNITIVE_MODES.md`
- `docs/LEARNED_BEHAVIORS.md`
- `docs/SOCIAL_INTELLIGENCE.md`
- `docs/RL_CONFIGURATION.md`
- `docs/RL_LEARNING.md`
- `docs/PERSONA_BEHAVIOR_ROADMAP.md`
- `docs/codebase_summary/*`
- `docs/features/*`
- `docs/guides/*`
- `docs/system_workflows/*`
- `docs/setup/*`
- historical legacy-oriented or breadth-oriented docs such as:
  - `docs/BOT_CONVERSATIONS.md`
  - `docs/BOT_CONVERSATIONS_ARCHITECTURE.md`
  - `docs/PERSONAS.md`
  - `docs/RAG_PERSONA_FILTERING.md`
  - `docs/PRODUCTION_*`

Reason:

These docs may contain useful historical or legacy context, but they should not be treated as current product documentation.

### Delete

- any regenerated or duplicate docs that are purely artifacts of prior completion-report waves

## Top-Level Repo Hygiene

### Delete

- `adapters/desktop/src-tauri/target/*`
- `adapters/desktop/dist/*`
- `adapters/desktop/node_modules/*`
- `__pycache__` trees across the repo
- any equivalent generated build output

### Refactor

- `.gitignore`

Reason:

Current ignore rules do not protect the repo from exactly the generated output that has already been committed.

## Immediate Execution Order

### First Cleanup Slice

- delete generated desktop build output
- update ignore rules
- keep docs aligned

### Second Cleanup Slice

- quarantine experimental `core/*` areas in documentation and structure
- stop treating them as canonical architecture

### Third Cleanup Slice

- refactor web to one canonical protocol
- clarify browser scaffold status

### Fourth Cleanup Slice

- continue runtime hardening and memory/learning boundary cleanup
- keep Discord legacy seams quarantined instead of extending them

### Fifth Cleanup Slice

- classify `services/*` more deeply into migrate/retain/delete

## Decision Notes

This classification is intentionally conservative:

- `Refactor` means “worth serious consideration”
- `Quarantine` means “not part of current product truth”
- `Delete` means “remove from source control or planned repo footprint”

It is better to quarantine first and adopt later than to keep claiming broad architecture ownership without a clean product boundary.
