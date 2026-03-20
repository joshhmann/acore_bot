# Kimi Phase 3 Slice Pack

**Last Updated**: 2026-03-20

## Purpose

This document provides bounded implementation slices for Phase 3 that can be
handed to Kimi one at a time.

These are implementation handoff prompts, not canonical product truth.

Canonical direction remains:

- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/RUNTIME_API.md`
- `docs/VISION.md`

## Recommended Order

1. Adapter SDK formalization
2. Trace emitter hardening
3. Memory coordinator + memory scoping
4. Tool policy + approval / action record foundation
5. Web operator surface expansion
6. Security hardening

Parallelism:

- Slice 1 can run in parallel with Slice 2
- Slices 2, 3, and 4 should not run in parallel because they are likely to
  overlap in runtime ownership and `core/runtime.py`
- Slice 5 depends on slices 2-4
- Slice 6 should come after slices 2-5

## Shared Instructions For Kimi

Paste this before any slice prompt:

```text
You are working in the Gestalt repo:
https://github.com/joshhmann/acore_bot

Treat these as canonical:
- docs/STATUS.md -> Phase 3 Focus
- docs/ARCHITECTURE.md -> Immediate Direction
- docs/RUNTIME_API.md -> maintained runtime contract
- docs/VISION.md -> product direction

Treat these as supporting research only:
- docs/research/research_runtime_synthesis.md
- docs/research/research_gestalt_brief.md
- docs/research/research_deep_report.md

Important constraints:
- Gestalt is runtime-first
- do not create a second architecture beside the runtime
- adapters must stay thin
- extend the existing PlatformFacts + Runtime API contract
- do not invent a parallel adapter stack
- do not move policy into adapters or web UI
- do not touch embodiment / VRM / scene systems in this slice
- do not broaden into multi-agent orchestration in this slice
- do not reintroduce services/* authority in maintained paths
- update canonical docs only if code truth changes
- keep docs honest; do not claim work is complete if it is partial

Required output:
1. what changed
2. changed files
3. tests run
4. remaining gaps or follow-ups

Verification expectations:
- run the smallest relevant tests first
- run focused unit tests for the touched surface
- run ruff on touched Python files
```

## Slice 1: Adapter SDK Formalization

```text
Implement Phase 3 Slice 1: Adapter SDK formalization.

Use the shared instructions already provided.

Mission:
Formalize the existing maintained adapter contract without inventing a parallel
architecture.

Ground truth:
- docs/STATUS.md -> Phase 3 Focus
- docs/ARCHITECTURE.md -> Immediate Direction
- docs/RUNTIME_API.md -> current maintained contract
- core/interfaces.py -> current PlatformFacts/event-builder seam

What to build:
- strengthen the typed adapter contract around the existing PlatformFacts-based
  ingress path
- add or refine types, protocols, or capability declarations that make the
  maintained adapter contract more explicit
- keep the existing event-builder seam as canonical
- add or strengthen tests that enforce:
  - adapters parse -> normalize -> runtime -> render
  - maintained adapters do not own provider/tool/persona/memory policy
  - no second abstraction stack is introduced

Constraints:
- additive only where possible
- do not broad-rewrite adapters
- do not change runtime authority
- do not redesign transports
- do not touch embodiment or scene systems

Acceptance criteria:
- existing contract is clearer and more strongly typed
- RUNTIME_API docs match code truth
- focused adapter/runtime boundary tests pass
- existing maintained adapters remain compatible

Report back with:
- what changed
- changed files
- tests run
- any contract gaps still left for later slices
```

## Slice 2: Trace Emitter Hardening

```text
Implement Phase 3 Slice 2: Runtime trace emitter hardening.

Use the shared instructions already provided.

Mission:
Strengthen the runtime-owned trace system so it becomes the backbone of
operator introspection.

Ground truth:
- docs/STATUS.md -> Phase 3 Focus
- docs/ARCHITECTURE.md -> runtime owns trace emission
- docs/RUNTIME_API.md -> existing trace snapshot surfaces
- core/runtime.py -> existing TraceOutput and trace snapshot behavior

What to build:
- centralize trace emission so runtime events produce consistent structured
  trace records
- standardize trace taxonomy for:
  - adapter ingress
  - session lifecycle
  - provider request/response
  - tool call/result
  - command/action dispatch
  - memory/context assembly events
  - approval events when relevant
  - error/failure cases
- strengthen trace snapshot shape for operator consumption
- keep traces runtime-owned; adapters may render but not author policy

Constraints:
- extend the current trace system; do not replace it wholesale
- avoid changing adapter contracts unless necessary for trace exposure
- do not broaden into approval queue UI or memory redesign

Acceptance criteria:
- trace events are more consistent and operator-useful
- trace snapshot surfaces remain maintained and clearer
- focused runtime/web/stdio trace tests pass
- no maintained adapter gains policy ownership

Report back with:
- what changed
- changed files
- tests run
- trace taxonomy added or standardized
```

## Slice 3: Memory Coordinator + Memory Scoping

```text
Implement Phase 3 Slice 3: Memory coordinator and scoped memory model.

Use the shared instructions already provided.

Mission:
Strengthen the runtime-owned memory layer so memory, context assembly, and
scoping are clearer and more typed.

Ground truth:
- docs/STATUS.md -> Phase 3 Focus
- docs/ARCHITECTURE.md -> runtime owns memory coordination
- docs/research/research_runtime_synthesis.md -> supporting rationale only
- memory/manager.py -> current MemoryContextBundle path

What to build:
- strengthen the memory coordinator around typed memory concepts:
  - ShortTermTurn
  - Episode
  - Fact
  - Preference
  - Procedure
  - ActionRecord
- standardize memory scoping as:
  - per-persona by default
  - separate runtime-owned shared-memory tier for relationship/social/explicitly shared context
- improve MemoryContextBundle or surrounding types so prompt assembly has
  clearer inputs
- keep context revision/invalidation explicit

Constraints:
- do not redesign the entire memory stack from scratch
- do not move memory policy into adapters
- do not build embodiment memory or game/environment memory
- do not overreach into unrelated legacy service migration

Acceptance criteria:
- memory ownership is clearer and more runtime-centered
- per-persona vs shared-memory scope is explicit in code
- focused memory/runtime tests pass
- prompt/context work becomes easier for later slices

Report back with:
- what changed
- changed files
- tests run
- what memory types and scopes are now explicit
```

## Slice 4: Tool Policy + Approval / Action Record Foundation

```text
Implement Phase 3 Slice 4: Tool policy, approval foundation, and action records.

Use the shared instructions already provided.

Mission:
Build the runtime foundations for bounded autonomy by strengthening tool
policy, approval semantics, and action recording.

Ground truth:
- docs/STATUS.md -> Phase 3 Focus
- docs/ARCHITECTURE.md -> runtime owns tool policy and execution budgets
- docs/RUNTIME_API.md -> runtime-owned surfaces
- tools/policy.py and tools/runner.py -> current baseline

What to build:
- strengthen tool risk tiers beyond the current minimal model where needed
- add a runtime-owned approval queue or approval-ready data model
- add action-record structures for effectful tool executions
- ensure action records capture:
  - action type
  - normalized inputs
  - outcome
  - side effects
  - approval state
  - optional rollback metadata
- expose enough runtime snapshot data that the operator surface can render
  approvals later

Constraints:
- do not build a full autonomy system in this slice
- do not create adapter-owned approval behavior
- do not bury approvals inside web-only logic
- do not redesign the adapter contract here

Acceptance criteria:
- tool policy is more explicit and safer
- effectful operations can be traced and reviewed as action records
- runtime has approval-ready state for later UI work
- focused tool/runtime tests pass

Report back with:
- what changed
- changed files
- tests run
- what approval/action-record surfaces now exist
```

## Slice 5: Web Operator Surface Expansion

```text
Implement Phase 3 Slice 5: Web operator surface expansion.

Use the shared instructions already provided.

Mission:
Expand the maintained web surface into a better operator cockpit over the
runtime.

Ground truth:
- docs/STATUS.md -> Phase 3 Focus
- docs/ARCHITECTURE.md -> web as operator surface
- docs/RUNTIME_API.md -> existing maintained endpoints
- current web routes/static UI -> existing runtime telemetry and chat UI

What to build:
- improve the web operator surface around:
  - runtime health
  - active sessions
  - traces
  - memory/context inspection
  - approvals or approval-ready data
  - provider/cache telemetry
- prefer using existing runtime endpoints and maintained contracts
- add only the minimum new runtime-facing surfaces needed for operator
  usefulness
- keep the UI runtime-first, not UI-as-runtime

Constraints:
- do not build VRM, scene, or embodiment UI
- do not add adapter-local policy logic
- do not invent a second orchestration layer in the browser
- do not turn this into a design-only refactor with no operator value

Acceptance criteria:
- default operator view answers:
  - what is running
  - what it is doing
  - what needs approval
  - what changed
- focused web runtime tests pass
- the UI uses runtime truth instead of local reconstruction

Report back with:
- what changed
- changed files
- tests run
- what operator capabilities the web UI now exposes
```

## Slice 6: Security Hardening

```text
Implement Phase 3 Slice 6: Runtime-first security hardening.

Use the shared instructions already provided.

Mission:
Strengthen the runtime-owned security boundaries needed for the current
Phase 3 path.

Ground truth:
- docs/STATUS.md -> Phase 3 Focus
- docs/ARCHITECTURE.md -> runtime authority
- docs/RUNTIME_API.md -> current maintained runtime surfaces
- current auth/session/trace/runtime code paths

What to build:
- harden secret handling and redaction in operator-visible trace/log surfaces
- strengthen handling of untrusted tool and MCP outputs
- improve actor/session attribution where runtime owns identity
- make trust boundaries clearer in maintained runtime/API behavior

Constraints:
- do not redesign the whole auth system unless required
- do not build multi-tenant architecture in this slice
- do not shift trust decisions into adapters
- do not broaden into general infra/security theory

Acceptance criteria:
- operator-visible traces/logs redact sensitive values
- untrusted tool/MCP content is treated more defensively
- actor/session attribution is clearer in maintained paths
- focused runtime/web tests pass

Report back with:
- what changed
- changed files
- tests run
- what concrete security boundaries are now enforced
```

## Review Protocol

After each Kimi slice, send back:

- summary
- changed files
- tests run
- commit hash or patch
- unresolved notes

Review criteria:

- runtime authority preserved
- no adapter-local policy drift
- canonical docs still truthful
- no scope creep into deferred embodiment or broad autonomy work
