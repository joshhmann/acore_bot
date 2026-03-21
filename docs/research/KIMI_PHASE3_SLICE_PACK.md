# Kimi Phase 3 Slice Pack

**Last Updated**: 2026-03-21

## Purpose

This document provides bounded implementation slices for Phase 3 that can be
handed to Kimi one at a time.

These are implementation handoff prompts, not canonical product truth.

Canonical direction remains:

- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/RUNTIME_API.md`
- `docs/VISION.md`

Known corrective review artifact:

- `docs/research/KIMI_SLICE_1_2_REVIEW.md`

## Recommended Order

1. Adapter SDK formalization
2. Trace emitter hardening
3. Memory coordinator + memory scoping
4. Tool policy + approval / action record foundation
5. Web operator surface expansion
6. Security hardening

Parallelism:

- Slice 1 should be completed and reviewed before Slice 2 is merged
- Slices 2, 3, and 4 should not run in parallel because they are likely to
  overlap in runtime ownership and `core/runtime.py`
- Slice 5 depends on slices 2-4
- Slice 6 should come after slices 2-5

## Non-Negotiable Invariants

These invariants apply to every Phase 3 slice:

- Single authority rule:
  - if a concept already exists canonically in `core/*`, extend it there
  - do not define a second authority for the same concept in adapters, helpers,
    or tests
- Signature match rule:
  - all new helper or subsystem integrations must match real function and method
    signatures in code
  - do not infer parameter names; verify them against the current implementation
- Maintained path rule:
  - a slice is not complete unless at least one maintained runtime path exercises
    it
  - isolated helper tests are not enough
- No silent semantic drift:
  - do not change the meaning of a shared contract method in only one adapter or
    subsystem
  - if a shared contract must change, update it centrally and update every
    affected implementation, test, and doc
- Preserve maintained behavior:
  - if an existing maintained path has environment-driven, config-driven, or
    runtime-driven behavior, do not hardcode a different default in a new path

## Forbidden Patterns

The following are slice failures unless explicitly requested:

- defining duplicate dataclasses, enums, contracts, or schema types for an
  existing concept
- introducing a second abstraction stack beside the maintained runtime path
- adapter-local policy ownership
- web-only or adapter-only exceptions to shared runtime contracts
- changing public contract semantics without centralizing the change
- broad rewrites justified as "cleanup" when the slice is bounded

## Required Preflight And Postflight Checks

Every Kimi slice must include these checks before claiming completion:

### Preflight

- read the relevant canonical docs for the slice before making changes
- list the canonical files that already own the concepts being changed
- list the maintained paths that must continue to work after the slice
- state which shared contracts are being extended, if any

### Postflight

- re-check the relevant canonical docs and confirm the implementation still
  matches them, or update them if product truth changed
- duplicate-authority grep:
  - run `rg` for new or modified canonical type names to confirm there is only
    one authority unless intentional compatibility types already existed
- signature check:
  - list touched public methods and confirm all new call sites match the actual
    signatures
- maintained-path validation:
  - run at least one maintained runtime integration test or endpoint test that
    exercises the new behavior
- behavior-drift check:
  - explicitly state whether any maintained default behavior changed
  - if yes, justify it and update canonical docs
- API/surface check:
  - if a new subsystem emits data for operators, prove that the maintained API
    or maintained surface can actually see it

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

Read the relevant canonical docs before making changes.
Re-check the relevant canonical docs before claiming completion.

Treat these as supporting research only:
- docs/research/research_runtime_synthesis.md
- docs/research/research_gestalt_brief.md
- docs/research/research_deep_report.md

If you are working on Slice 1 or Slice 2, also read:
- docs/research/KIMI_SLICE_1_2_REVIEW.md

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
- preserve single authority for canonical types and contracts
- do not define duplicate dataclasses, enums, or ABCs for the same concept
- do not change shared contract semantics in only one implementation
- verify new call sites against real method signatures before completion
- prove maintained-path integration, not only isolated helper tests

Required output:
1. what changed
2. changed files
3. tests run
4. remaining gaps or follow-ups
5. canonical files extended
6. duplicate-authority grep results
7. maintained-path validation performed
8. whether any maintained behavior changed

Verification expectations:
- run the smallest relevant tests first
- run focused unit tests for the touched surface
- run ruff on touched Python files
- run at least one maintained-path test for the touched surface
- verify no duplicate type or contract authorities were introduced
- verify all new call sites match touched public method signatures
```

## Corrective Guidance For Slice 1 And Slice 2

The first attempted implementations of Slice 1 and Slice 2 produced concrete
architectural failures that must not be repeated.

Before attempting a corrective pass for Slice 1 or Slice 2, read:

- `docs/research/KIMI_SLICE_1_2_REVIEW.md`

Corrective priorities:

- Slice 1:
  - centralize adapter-contract authority in `core/interfaces.py`
  - preserve maintained CLI behavior
  - do not let web redefine shared contract semantics locally
- Slice 2:
  - centralize trace-model authority
  - verify runtime call sites against emitter signatures
  - ensure emitted traces are visible through the maintained trace API

Corrective output must explicitly state:

- which duplicate authorities were removed or avoided
- which maintained-path behaviors were preserved
- which maintained runtime/API tests proved the fix

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
- do not define `RuntimeDecision`, `AdapterConfig`, or
  `AdapterLifecycleContract` outside `core/interfaces.py`
- do not change maintained default persona behavior unless explicitly requested

Acceptance criteria:
- existing contract is clearer and more strongly typed
- RUNTIME_API docs match code truth
- focused adapter/runtime boundary tests pass
- existing maintained adapters remain compatible
- no duplicate adapter SDK authorities exist outside `core/interfaces.py`
- maintained CLI and web behavior remain consistent with canonical defaults

Report back with:
- what changed
- changed files
- tests run
- any contract gaps still left for later slices
- exact grep results proving no duplicate SDK authorities exist
- how maintained-path behavior was preserved
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
- do not create a second trace schema authority beside the maintained trace
  model
- do not add emitter-only traces that are invisible to the maintained trace API
- do not add runtime call sites unless their argument names are verified against
  emitter signatures

Acceptance criteria:
- trace events are more consistent and operator-useful
- trace snapshot surfaces remain maintained and clearer
- focused runtime/web/stdio trace tests pass
- no maintained adapter gains policy ownership
- maintained trace APIs actually surface the new emitted traces
- no duplicate trace schema/model authority exists

Report back with:
- what changed
- changed files
- tests run
- trace taxonomy added or standardized
- exact maintained-path tests that exercised emitted traces
- exact grep results proving trace model authority is not duplicated
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
- do not create duplicate memory model types if equivalent canonical types
  already exist

Acceptance criteria:
- memory ownership is clearer and more runtime-centered
- per-persona vs shared-memory scope is explicit in code
- focused memory/runtime tests pass
- prompt/context work becomes easier for later slices
- maintained runtime context assembly still works after the refactor

Report back with:
- what changed
- changed files
- tests run
- what memory types and scopes are now explicit
- how maintained prompt/context behavior was verified
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
- do not create approval or action-record models in multiple canonical places

Acceptance criteria:
- tool policy is more explicit and safer
- effectful operations can be traced and reviewed as action records
- runtime has approval-ready state for later UI work
- focused tool/runtime tests pass
- maintained runtime surfaces can inspect the new approval/action-record state

Report back with:
- what changed
- changed files
- tests run
- what approval/action-record surfaces now exist
- how maintained runtime surfaces were validated
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
- do not reconstruct runtime state locally in the browser if the runtime can
  expose it directly

Acceptance criteria:
- default operator view answers:
  - what is running
  - what it is doing
  - what needs approval
  - what changed
- focused web runtime tests pass
- the UI uses runtime truth instead of local reconstruction
- at least one maintained API test proves the UI-facing data is coming from the
  runtime contract

Report back with:
- what changed
- changed files
- tests run
- what operator capabilities the web UI now exposes
- which maintained endpoints/snapshots the UI now depends on
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
- do not leak secrets in traces, snapshots, or operator-facing structured output

Acceptance criteria:
- operator-visible traces/logs redact sensitive values
- untrusted tool/MCP content is treated more defensively
- actor/session attribution is clearer in maintained paths
- focused runtime/web tests pass
- maintained trace and operator surfaces were explicitly checked for redaction

Report back with:
- what changed
- changed files
- tests run
- what concrete security boundaries are now enforced
- where redaction/trust-boundary checks were verified
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
- no duplicate canonical authorities created
- maintained-path behavior explicitly preserved and verified
