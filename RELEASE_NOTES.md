# Release Notes

## v0.2.0-phase3-runtime (2026-03-15)

### Highlights

- Runtime-owned context cache added for chat/streaming context reuse.
- Runtime context cache controls added:
  - command surface: `/context`, `/context reset`
  - web API: `/api/runtime/context`, `/api/runtime/context/reset`
  - stdio API: `get_context`, `reset_context`
- Runtime trace now includes context cache hit/miss metadata and token-saved estimates.
- CI hardened for maintained runtime paths:
  - blocking `ruff`
  - blocking docs-governance check
  - maintained runtime unit suite gate
- CD baseline added:
  - release artifact build workflow on tags (`v*`) and manual dispatch.

### Verification Snapshot

- Unit regressions (maintained runtime surfaces): passing
- Lint: passing
- Docs governance: passing
- Runtime Discord smoke startup/shutdown: passing

### Notes

- This milestone prioritizes runtime authority and adapter contract parity over legacy surface expansion.
- Legacy/transitional surfaces remain quarantined and opt-in.
