# Development Flow

**Last Updated**: 2026-03-10

## Purpose

This document is the anti-drift workflow for Gestalt.

Use it whenever adding features, refactoring architecture, updating status docs, or expanding surfaces.

For the day-to-day operating model, also read:

- `docs/ENGINEERING_OPERATING_MODEL.md`
- `docs/adr/README.md`

## Core Rule

No feature is “real” in Gestalt until all of the following are true:

1. the runtime or canonical surface code exists
2. the behavior is verified with appropriate tests
3. the status/docs describe it honestly

If any one of those is missing, the feature is not complete.

## Canonical Flow

### Phase 1: Vision Check

Before coding:

1. read `docs/VISION.md`
2. read `docs/FEATURES.md`
3. identify whether the change belongs to:
   - canonical product
   - legacy maintenance
   - experiment

If unclear, do not proceed as if it is canonical product work.

Also classify the work as:

- `product track`
- `research track`

Do not mix the two in one slice.

### Phase 2: Boundary Check

Decide where the change belongs:

- runtime
- adapter
- provider
- tool/MCP
- memory
- experimental module

Hard rule:

- runtime owns behavior and policy
- adapters render and transport

If the change affects ownership or cross-layer contracts, write or update an ADR.

### Phase 3: Small Vertical Slice

For a non-trivial change, complete the full slice:

1. code
2. tests
3. docs

Do not ship only the doc or only the scaffold unless it is explicitly labeled experimental.

Default appetite:

- `1 to 2 days` of implementation effort

### Phase 4: Evidence Check

Before updating `docs/FEATURES.md`, verify:

1. code path exists
2. it is actually on the maintained surface
3. tests exist

If tests do not exist:

- do not label it `Verified active`
- mark `Test coverage: missing` where appropriate

### Phase 5: Surface Consolidation Check

Before adding a new surface, protocol, or adapter behavior, ask:

1. does this duplicate an existing path?
2. is there already a runtime-backed surface for this?
3. are we creating a second authority layer?

Default answer should be to extend an existing canonical path, not create a competing one.

### Phase 6: Experimental Containment

Experimental work must be clearly marked as one of:

- `Present but unused`
- `Not implemented`
- separate experimental namespace or document

Experimental work must not:

- be described as shipped platform truth
- be inserted into core authority paths without clear adoption

If experimentation needs long-term tracking, keep it on the research track and define:

- hypothesis
- environment
- success signal
- adoption criteria

## Documentation Rules

### Allowed Canonical Status Labels

- `Verified active`
- `Present but not loaded`
- `Present but unused`
- `Deprecated candidate`
- `Not implemented`

### Not Allowed

- vague or inflated completion language
- “production ready” without current evidence
- “100% complete” based on plans or checklists

### Required Source-of-Truth Docs

Keep these aligned:

- `docs/VISION.md`
- `docs/FEATURES.md`
- `docs/STATUS.md`
- `README.md`

## Release Gate for Feature Work

Before considering work complete, verify:

1. code implemented
2. focused tests pass
3. unit gate passes when the change is non-trivial
4. docs updated if user-facing or architectural behavior changed
5. `docs/FEATURES.md` remains honest

## Audit Cycle

When drift is suspected:

1. audit current code paths
2. compare against `docs/VISION.md`
3. compare against `docs/FEATURES.md`
4. downgrade docs before upgrading claims
5. quarantine experiments and duplicates

## Operating Rules

1. one active product bet at a time
2. no “complete” language without implementation and verification
3. no research in canonical product clothing
4. no duplicate authority between runtime and surfaces
5. no giant multi-subsystem scope dumps when the work can be split

## Decision Filters

A proposed change should be approved if it does one or more of:

- strengthens runtime authority
- improves canonical surfaces
- improves memory, autonomy, or action systems
- expands provider/MCP/media support cleanly
- improves learning infrastructure within governed boundaries

A proposed change should be rejected or deferred if it:

- broadens scope without a maintained surface
- introduces unclear ownership
- duplicates transport or runtime logic
- encourages status inflation

## Current Priorities

1. runtime stability
2. web/CLI/TUI coherence
3. memory and learning architecture
4. autonomy and action quality
5. provider/MCP/TTS/STT extensibility
6. embodiment only after the above are stable
