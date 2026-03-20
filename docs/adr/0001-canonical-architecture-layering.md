# ADR 0001: Canonical Architecture Layering

**Status**: Accepted
**Date**: 2026-03-10

## Context

Gestalt drifted because architecture direction lived partly in code, partly in
older v1 runtime docs, and partly in speculative plans.

That left major ownership questions underdefined:

- where identity and social behavior belong
- where embodiment belongs
- where RL belongs
- whether learning means personalization or model training
- whether connectors and MCP are central or peripheral

Without one explicit layering decision, new work can drift back into mixed
authority and speculative core sprawl.

## Decision

Gestalt adopts a canonical layered architecture:

- client / presence layer
- adapter layer
- runtime authority layer
- capability layer
- memory / learning layer
- training / research layer

The runtime remains the only authority for behavior, state, policy, memory
coordination, and action selection.

Gestalt also adopts these specific placements:

- each persona will have a runtime-owned identity core
- social behavior is runtime-owned
- MCP and connectors are first-class capability surfaces
- embodiment and scenes are client-side, runtime-driven surfaces
- RL belongs to bounded training and research environments
- user learning starts as personalization and memory, not model fine-tuning

## Boundary

Runtime owns:

- sessions
- persona, identity, and social state
- commands, policy, planning, and action selection
- provider routing
- memory coordination
- context optimization
- learning coordination

Adapters and clients own:

- transport
- parsing
- rendering
- avatar and scene presentation

Training and research own:

- experiments
- reward logic
- offline RL
- offline model adaptation

They do not become product truth without explicit adoption.

## Consequences

Simpler:

- Phase 2 migration work has a clear target
- social engine placement is no longer ambiguous
- future scene and RL work have an explicit home
- browser/VRM work can progress without trying to become the runtime

Still partial or deferred:

- identity layer is not fully implemented yet
- learning data pipeline is still architecture direction, not product truth
- RL remains research-path
- Discord maintained startup now matches this boundary, while legacy Discord seams remain quarantined

## Alternatives Considered

- Keep `docs/GESTALT_V1.md` as the only architecture reference
- Let architecture remain distributed across audit docs and plans

## Verification

This decision is reflected by:

- `docs/ARCHITECTURE.md`
- `docs/VISION.md`
- `docs/GROUND_TRUTH.md`
- `docs/README.md`

Future code/tests should verify this by:

- moving social and mode state into runtime-owned paths
- formalizing identity and action/observation contracts
- keeping RL and research work out of canonical serving paths
