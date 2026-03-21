# Kimi Slice 1 And Slice 2 Review

**Date**: 2026-03-21
**Status**: Review complete, corrective pass required
**Scope**:
- Phase 3 Slice 1: Adapter SDK formalization
- Phase 3 Slice 2: Trace emitter hardening

## Purpose

This document records the concrete review findings from the first Kimi pass on
Slice 1 and Slice 2.

It is not canonical product truth.
It is a corrective implementation artifact intended to guide follow-up work.

Canonical authority remains:

- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/RUNTIME_API.md`
- `docs/VISION.md`

## Slice 1 Review

### Summary

Slice 1 moved in the right direction, but it did not satisfy the core
architectural constraint of centralizing adapter-contract authority.

The main failure mode was not "missing features." The main failure mode was
contract drift:

- duplicate SDK authority
- behavior drift between old and new maintained paths
- inconsistent method semantics across adapters

### Findings

#### 1. Duplicate adapter SDK authority

`core/interfaces.py` now defines the canonical adapter SDK types:

- `RuntimeDecision`
- `AdapterConfig`
- `AdapterLifecycleContract`

But `adapters/cli/adapter.py` also defines local copies of those same concepts.

Why this is a failure:

- the repo now has two authorities for one contract
- future changes will drift immediately
- tests may pass while the architecture decays

Required fix:

- remove duplicate SDK definitions from `adapters/cli/adapter.py`
- import and use the canonical types from `core/interfaces.py`

#### 2. CLI default persona drift

The maintained legacy CLI path resolves a no-mention persona through
`get_cli_default_persona()`.

The new contract-based `CLIAdapter.parse()` path fell back to `"default"`.

Why this is a failure:

- the same user input produces different behavior depending on which code path
  is used
- the new SDK path no longer preserves maintained behavior

Required fix:

- unify the default persona behavior
- the new contract path must match the maintained CLI default-resolution path

#### 3. Web adapter changed shared contract semantics locally

The base adapter lifecycle contract defines `render(...)` as the transport phase.

The web adapter changed `render(...)` into a JSON-returning data-shaping helper,
and routes depend on that adapter-specific return value.

Why this is a failure:

- the same shared method now means different things in different adapters
- the contract is no longer actually formalized
- web-specific behavior leaked into the shared contract model

Required fix:

- preserve one canonical meaning for `render(...)`
- preferred approach:
  - keep `render(...)` as transport/output
  - move JSON payload shaping into a separate helper used by web routes
- alternative approach:
  - change the contract centrally, then update all implementations/docs/tests

### Slice 1 Acceptance Gate For Corrective Pass

Slice 1 is not complete until all of the following are true:

- no duplicate SDK authorities exist outside `core/interfaces.py`
- CLI default persona behavior is consistent across maintained paths
- shared lifecycle semantics are centralized and consistent
- maintained CLI and maintained web paths still work
- tests enforce the boundary, not only the helper classes

## Slice 2 Review

### Summary

Slice 2 introduced useful trace ideas, but the first pass is not safe to merge.

The main failure mode was not taxonomy quality. The main failure mode was
runtime integration drift:

- runtime calls do not match emitter signatures
- emitted traces are not actually visible through the maintained trace API
- duplicate trace models now exist in multiple canonical places

### Findings

#### 1. Runtime call sites do not match emitter signatures

The new runtime integration calls the emitter using argument names that the
emitter methods do not accept.

Examples of mismatch categories:

- memory trace call-site args do not match `emit_memory_assembly(...)`
- provider trace call-site args do not match `emit_provider_request(...)`
- provider response call-site args do not match `emit_provider_response(...)`
- error trace call-site args do not match `emit_error(...)`

Why this is a failure:

- maintained chat/runtime paths can raise `TypeError`
- unit tests for the emitter are not enough if integration call sites are wrong

Required fix:

- align emitter signatures and runtime call sites
- verify every new emitter call against the actual function signature
- add maintained runtime-path tests that exercise those call sites

#### 2. Emitter-only traces are not surfaced by the maintained trace API

The new emitter stores trace spans in its own snapshot store.

But the maintained runtime trace snapshot still rebuilds from
`session.trace_spans`.

Why this is a failure:

- operators cannot see much of the newly emitted trace data
- the trace API and the trace emitter are not actually integrated
- this creates a parallel observability path instead of strengthening the
  maintained one

Required fix:

- unify the maintained trace surface with the new emitter output
- either:
  - make the maintained trace API read from the emitter-backed snapshot store
  - or ensure emitter-produced traces are appended to the maintained session
    trace store in a consistent way

#### 3. Duplicate trace model authority

Slice 2 introduced trace model concepts in multiple places:

- `core/schemas.py`
- `core/trace.py`

That includes overlapping concepts like:

- `TraceSpan`
- `TraceSummary`

Why this is a failure:

- two trace schema authorities now exist
- later slices will drift against whichever one they happen to import
- serialization and runtime/operator APIs will become unstable

Required fix:

- centralize trace model authority in one canonical place
- make helper modules consume the canonical types instead of redefining them

### Slice 2 Acceptance Gate For Corrective Pass

Slice 2 is not complete until all of the following are true:

- emitter method signatures and runtime call sites match
- maintained runtime paths execute the emitter successfully
- maintained trace APIs expose the emitted traces
- no duplicate trace schema/model authorities remain
- tests cover real runtime integration, not only emitter internals

## Cross-Slice Lessons

These failures have a shared pattern:

- helper-level work passed in isolation
- maintained-path integration was not strong enough
- canonical authority was not protected tightly enough

The fix is not just "write more tests." The fix is:

- centralize authority
- verify signatures against real code
- require maintained-path validation
- forbid duplicate canonical models

## Corrective Pass Order

Use this order for follow-up work:

1. Fix Slice 1 first
2. Re-review Slice 1
3. Fix Slice 2 against the corrected Slice 1 baseline
4. Re-review Slice 2

Do not continue to later Phase 3 slices on top of unresolved Slice 1 and Slice 2
drift.

## Required Inputs For Corrective Kimi Pass

Any corrective Kimi prompt for these slices should explicitly point to:

- `docs/research/KIMI_PHASE3_SLICE_PACK.md`
- `docs/research/KIMI_SLICE_1_2_REVIEW.md`

And should require Kimi to state:

- how canonical authority was preserved
- how maintained behavior was preserved
- what maintained-path tests exercised the fix
