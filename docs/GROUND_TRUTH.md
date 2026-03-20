# Ground Truth Documentation

**Last Updated**: 2026-03-10

## Purpose

This document defines which files are authoritative for product direction, status, and development decisions.

When repository documents disagree, use this order.

## Order of Truth

1. Code and tests
2. `docs/FEATURES.md`
3. `docs/VISION.md`
4. `docs/STATUS.md`
5. `AGENTS.md`
6. historical docs, plans, reports, and notes

## Canonical Documents

### Product Direction

- `docs/VISION.md`

Defines:

- what Gestalt is
- what Gestalt is not
- the intended framework direction
- the current and future product shape

### Platform Maturity / Status

- `docs/FEATURES.md`
- `docs/STATUS.md`

`FEATURES.md` is the current source of truth for what is actually active and test-backed.

`STATUS.md` is the short operator-facing summary.

### Runtime Architecture

- `docs/ARCHITECTURE.md`
- `docs/RUNTIME_API.md`

`ARCHITECTURE.md` is the canonical current architecture reference.

`RUNTIME_API.md` is the canonical adapter-facing contract reference.

### Development Governance

- `AGENTS.md`
- `docs/DEVELOPMENT_FLOW.md`
- `docs/ENGINEERING_OPERATING_MODEL.md`
- `docs/adr/`

These define how work should be performed and verified.

## Documents That Are Not Ground Truth

These may be useful context, but they are not authoritative:

- historical reports
- completion summaries
- planning artifacts
- old roadmap docs
- large codebase-summary docs describing legacy breadth

If one of those conflicts with code/tests or canonical docs, it loses.

## Evidence Rule

A claim about current functionality should only be made as `Verified active` if:

1. the relevant code exists
2. the feature is on the maintained product path
3. there is test evidence, or the document explicitly says `Test coverage: missing`

## Scope Rule

The existence of code in the repository does not automatically mean:

- it is current product
- it is maintained
- it is loaded by default
- it should appear in public-facing product status

## Use

Before changing architecture, docs, or product status:

1. read `docs/VISION.md`
2. read `docs/FEATURES.md`
3. verify code/tests
4. follow `docs/DEVELOPMENT_FLOW.md`
5. use `docs/ENGINEERING_OPERATING_MODEL.md` for slice discipline and ADR triggers
