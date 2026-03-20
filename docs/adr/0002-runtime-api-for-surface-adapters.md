# ADR 0002: Runtime API For Surface Adapters

**Status**: Accepted
**Date**: 2026-03-11

## Context

Gestalt had a runtime-first direction, but surface integrations were still too
easy to treat as special cases. The web client had become the most complete
runtime consumer, yet the adapter-facing contract was still implicit and
web-client-shaped rather than a documented platform decision.

That made it harder to:

- finish Discord migration cleanly
- add future communication surfaces
- keep adapters from drifting into second-runtime behavior

## Decision

Gestalt will use a formal `Runtime API` as the canonical contract for surface
adapters.

The web runtime becomes the reference implementation of that contract.

This contract includes:

- event submission
- runtime snapshots
- session bootstrap and listing
- runtime-owned social-state access and mutation
- live websocket streaming
- adapter-scoped session attribution through stable client scope metadata and
  explicit maintained user-id metadata
- runtime-owned surface response/persona decisions once platform facts are
  normalized by the adapter

## Boundary

Runtime owns:

- sessions
- persona, mode, and social state
- command execution
- provider/model routing
- tool and connector orchestration
- trace and presence state

Surface adapters own:

- input parsing
- transport
- rendering
- platform-specific UX
- platform fact extraction such as mentions, reply state, and channel metadata

Surface adapters do not own:

- provider calls
- tool policy
- memory writes
- social logic
- direct session mutation outside the Runtime API

## Consequences

This makes:

- web the reference client instead of a special client
- Discord migration target the same contract
- future Slack/Telegram/voice work easier to shape
- adapter session inventory attributable by stable client scope instead of raw
  platform-only grouping
- maintained request attribution can distinguish stable client scope from stable
  user identity
- maintained on-message Discord response selection target a runtime decision seam
  instead of adapter-local persona routing

This remains partial:

- the adapter SDK is not implemented yet
- maintained Discord startup now uses runtime-backed command surfaces, while legacy Discord seams remain quarantined
- identity-specific runtime API surfaces are still future work

## Alternatives Considered

- Keep the web client contract implicit and let each adapter integrate directly
- Treat Discord as the main adapter shape and generalize from there

## Verification

This decision is reflected by:

- runtime session summary/listing in `core/runtime.py`
- runtime adapter response decision in `core/runtime.py`
- web runtime routes for session and social snapshots in `adapters/web/routes.py`
- web auth/client-scope and user-id extraction in `adapters/web/auth.py`
- web websocket client-scope and user-id propagation in
  `adapters/web/websocket.py`
- stdio parity in `gestalt/runtime_stdio.py`
- browser bridge support in `adapters/desktop/src/runtimeBridge.ts`
- maintained Discord runtime startup in `adapters/discord/discord_bot.py`
- runtime-backed Discord chat in `adapters/discord/commands/runtime_chat.py`
- focused tests in `tests/unit/test_web_runtime_api.py`
- focused tests in `tests/unit/test_runtime_stdio.py`
- focused tests in `tests/unit/test_discord_runtime_chat.py`
- focused tests in `tests/unit/test_gestalt_v1_runtime.py`
- scaffold guardrail updates in `tests/unit/test_desktop_scaffold.py`
- canonical contract documentation in `docs/RUNTIME_API.md`
