# Architecture Decision Records

## Purpose

This directory holds lightweight architecture decision records for Gestalt.

Use ADRs to record changes that affect:

- runtime authority
- canonical surfaces
- cross-layer contracts
- migration direction
- adoption of research into product

## When To Write One

Write an ADR when:

- a runtime boundary changes
- a new canonical adapter or protocol is introduced
- a legacy subsystem is adopted, quarantined, or retired
- a research subsystem is promoted into product truth
- a public contract or shared internal contract changes

Do not write ADRs for:

- small bug fixes
- local refactors with no ownership change
- documentation-only wording changes

## Naming

Use zero-padded numbering:

- `0001-<short-name>.md`
- `0002-<short-name>.md`

If no ADRs exist yet, start from `0001`.

## Format

Copy `docs/adr/0000-template.md` and replace the placeholders.

Keep ADRs short.
The goal is to preserve the decision and reasoning, not to create a design thesis.
