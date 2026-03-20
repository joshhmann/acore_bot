# Engineering Operating Model

**Last Updated**: 2026-03-10

## Purpose

This document defines the operating model for building Gestalt without drifting again.

It turns the high-level rules in `docs/DEVELOPMENT_FLOW.md` into a practical cycle that can be followed for every slice of work.

## Core Principle

Gestalt work happens on two tracks:

- `product track`
- `research track`

They are not the same thing.

Research can inform product.
Research does not become product truth automatically.

## Product Track

Use the product track for:

- runtime
- CLI
- TUI
- web runtime
- Discord migration
- providers
- tools
- MCP
- memory
- TTS/STT integration work that is meant to ship

### Product Slice Rules

Each slice must have:

- one clear problem
- one bounded outcome
- one maintained surface
- explicit non-goals

Each slice must end with:

- code
- verification
- documentation truth update if needed

### Product Slice Size

Default slice size:

- `1 to 2 days` of implementation effort

Avoid:

- broad multi-subsystem dumps
- giant architectural jumps hidden inside one branch
- mixing product cleanup with unrelated research

### Product Slice Template

Before starting, write down:

- `problem`
- `scope`
- `surface`
- `runtime boundary`
- `non-goals`
- `verification plan`

If any of those are unclear, the slice is not ready.

## Research Track

Use the research track for:

- RL
- VRM scene learning
- RuneScape experiments
- self-improvement experiments
- speculative social/behavior systems
- new embodied interaction ideas

### Research Rules

Each research spike must define:

- `hypothesis`
- `environment`
- `action space`
- `success signal`
- `adoption criteria`

Research code must not:

- redefine canonical product docs
- land in `core/*` as if it is active platform behavior
- be described as shipped capability

Research should live in:

- explicit experimental namespaces
- clearly marked docs
- quarantined subsystems

## Standard Development Cycle

### Step 1: Shape

Define a single bet.

Required:

- the exact problem
- why it matters now
- the surface it affects
- what will not be done in this slice

If the problem statement still sounds like a roadmap theme instead of a deliverable, keep shaping.

### Step 2: Vision Check

Read:

- `docs/VISION.md`
- `docs/GROUND_TRUTH.md`
- `docs/FEATURES.md`

Decide whether the work is:

- canonical product work
- legacy maintenance
- research

If the answer is not clear, do not proceed as canonical work.

### Step 3: Boundary Check

State what layer owns the change:

- runtime
- adapter
- provider
- tools/MCP
- memory
- legacy seam
- research namespace

Hard rule:

- runtime owns behavior, state, policy, and decisions
- adapters own parsing, transport, and rendering

### Step 4: Decision Record

If the slice changes architecture, ownership, or a canonical interface, add or update an ADR.

Use an ADR for:

- new canonical surfaces
- runtime contract changes
- provider/tool/memory ownership changes
- major migration decisions
- research adoption into product

Do not write an ADR for:

- simple bug fixes
- isolated refactors with no boundary change
- styling or wording only

### Step 5: Build One Vertical Slice

Complete the full slice:

- implementation
- wiring
- focused tests
- docs changes only if needed for truth

Do not stop at:

- plan only
- docs only
- scaffold only

unless the work is explicitly labeled research or audit.

### Step 6: Verify

Verification should match the slice:

- targeted unit tests
- focused smoke checks
- lint/type checks if the surface warrants it

Completion claims are blocked unless:

- the code path exists
- the path is on a maintained surface
- the verification result is known

If tests are missing, say so explicitly.

### Step 7: Truth Update

Update only what changed.

Canonical docs to consider:

- `docs/FEATURES.md`
- `docs/STATUS.md`
- `docs/REFACTORING_PLAN.md`
- one migration map if the slice was refactor/migration work

Do not create a new victory document for a normal slice.

### Step 8: Close the Slice

End every slice with one of:

- `done`
- `partial`
- `blocked`
- `cancelled`

No vague state like “basically done” or “phase complete” without evidence.

## ADR Policy

ADR usage is mandatory when:

- a change affects runtime authority
- a new canonical adapter or transport is introduced
- a legacy subsystem is adopted or retired
- research becomes product work
- a public or cross-layer contract changes

ADR usage is optional when:

- documenting rationale would prevent likely future drift

ADR usage is unnecessary when:

- the change is purely local and behaviorally obvious

## Drift Prevention Rules

### Rule 1: One Active Product Bet

Only one major product slice should be active at a time.

Parallel work is allowed for:

- bug fixes
- small docs truth updates
- independent research spikes

Parallel product bets are how scope drift starts.

### Rule 2: No Status Inflation

No doc or commit should imply completion unless:

- implemented
- verified
- aligned with product truth

### Rule 3: No Research in Canonical Clothing

Research cannot sit in:

- `core/*`
- canonical README language
- `docs/FEATURES.md` as shipped capability

unless it has been explicitly adopted.

### Rule 4: No Duplicate Authority

If runtime already owns a behavior, do not recreate it in:

- Discord
- browser client
- TUI
- legacy services

### Rule 5: No Giant Scope Dumps

If a change touches too many unrelated areas at once, stop and split it.

Good slices are easier to audit, test, and reason about.

## Success Criteria

The cycle is working if:

- the maintained product surface stays small and legible
- new features land with clear ownership
- docs remain believable
- research stays valuable without distorting the product
- refactors reduce ambiguity instead of creating new parallel systems

## Current Application To Gestalt

The immediate product-track order should remain:

1. runtime stabilization
2. surface consolidation
3. memory and learning architecture
4. autonomy/action quality
5. provider/TTS/STT/MCP ecosystem quality
6. Discord and other adapter refinement on top of the maintained runtime contract

Research-track work should stay separate:

- RL
- scenes
- VRM embodiment
- RuneScape
- self-improvement experiments
