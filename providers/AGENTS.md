# PROVIDERS KNOWLEDGE BASE

Last updated: 2026-03-09 PST
Scope: `providers/*`.

## Overview
Provider abstraction and routing layer used by runtime to resolve model/provider selection per mode/persona.

## Where To Look
| Task | Location | Notes |
|------|----------|-------|
| Routing logic | `providers/router.py` | Provider selection chain |
| Provider contracts | `providers/base.py` | Interface and normalized response shape |
| OpenAI-compat implementation | `providers/openai_compat.py` | Upstream API mapping |

## Anti-Patterns
- Provider selection logic duplicated outside router.
- Leaking provider-specific response payloads across boundaries.
- Runtime bypasses that skip provider registry/routing.
