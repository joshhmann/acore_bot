# SOCIAL INTELLIGENCE KNOWLEDGE BASE

Last updated: 2026-03-09 PST
Scope: `core/social_intelligence/*`.

## Overview
Social intelligence subsystem for signal extraction, mode routing, adaptation, learning loops, and runtime hooks.

## Where To Look
| Task | Location | Notes |
|------|----------|-------|
| Core types | `core/social_intelligence/types.py` | Social signal/state contracts |
| Pipeline | `core/social_intelligence/pipeline.py` | Observation flow |
| Mode/router logic | `core/social_intelligence/facilitator.py`, `core/social_intelligence/router.py` | Mode decision behavior |
| Learning layer | `core/social_intelligence/learning/` | Bandit/style learning |
| Runtime integration | `core/social_intelligence/runtime_hooks.py` | Runtime hook seam |

## Conventions
- Keep SIL logic framework-agnostic and runtime-hook driven.
- Preserve low-latency hooks in runtime paths.
- Keep deprecated compatibility wrappers clearly separated.

## Anti-Patterns
- Introducing adapter/platform imports into SIL modules.
- Breaking mode decision determinism in tests without explicit fixtures.
- Reintroducing deprecated compat path usage as primary flow.
