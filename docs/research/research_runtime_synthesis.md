# Gestalt Runtime Research Synthesis

**Last Updated**: 2026-03-20

## Purpose

This document is the near-term runtime-focused synthesis of the current
research pass.

It is not a generic research summary. It is a decision-oriented brief for the
next implementation phase.

Primary research inputs:
- `docs/research/research_gestalt_brief.md`
- `docs/research/research_deep_report.md`

Secondary input:
- `docs/research/research_runtime_architecture_brief.pdf`

This document is non-canonical research synthesis.

When it conflicts with code, tests, or canonical docs, this document loses.

## Executive Summary

The research converges on one clear conclusion:

- Gestalt's runtime-first direction is correct
- the next phase is formalization and hardening, not reinvention
- the runtime must remain the single authority for sessions, memory, provider
  routing, tool policy, traces, persona/session state, and context assembly
- adapters must remain thin translators and renderers
- the web UI should mature into the primary operator surface

Near-term work should focus on:
- runtime architecture hardening
- memory/context coordination
- bounded autonomy and approval policy
- adapter SDK formalization
- web operator visibility
- security/trust boundaries

Embodiment, VRM, and environment bridges remain part of the long-term vision,
but are intentionally deferred from the current implementation priorities.

## Consensus Findings

The current research reports strongly agree on these points:

1. Runtime authority must be explicit.
   - No adapter, plugin, or UI should own orchestration or response policy.

2. Adapters are translators, not policy engines.
   - Parse input
   - normalize platform facts/events
   - submit to runtime
   - render runtime outputs

3. Memory needs one runtime-owned coordinator.
   - Working memory, summaries, facts, preferences, procedures, and action
     outcomes should flow through one orchestration layer.
   - Default memory scope should remain per-persona, with a separate
     runtime-owned shared-memory tier for relationship and social state.

4. Context assembly and caching should be first-class runtime systems.
   - Stable-prefix prompt construction and cache-aware assembly are the biggest
     near-term cost and latency optimizations.

5. Tool execution requires explicit policy.
   - Risk tiers, budgets, approval gates, and action logging are prerequisites
     for useful autonomy.

6. Trace emission is non-negotiable.
   - Every runtime decision should produce structured trace data for debugging,
     operator UI, and later evaluation.

7. Security boundaries must be designed early.
   - Secrets, tool trust, MCP boundaries, untrusted content handling, and
     session identity all get harder to fix later.

## Final Architecture Direction

The next phase should standardize this ownership model:

- `RuntimeHost`
  - process lifecycle
  - runtime startup/shutdown
  - surface registration

- `GestaltRuntime`
  - session lifecycle
  - provider routing
  - tool policy and approvals
  - memory coordination
  - context assembly and cache lifecycle
  - persona/session/social state
  - trace emission

- `Subsystems`
  - providers
  - tools
  - memory
  - plugins/MCP
  - all consumed by runtime policy, never as second authorities

- `Adapters`
  - web
  - CLI
  - Discord
  - future Slack/Telegram/environment bridges
  - all limited to transport hygiene, normalized ingress, and rendering

## Interface Decisions To Lock

### 1. Runtime Session Model

Define one runtime-owned session object with:

- `session_id`
- `surface_refs`
- `persona_id`
- `policy_state`
- `memory_state_refs`
- `trace_root_id`
- `lifecycle_state`

Required lifecycle states:

- `ready`
- `running`
- `suspended`
- `draining`
- `stopped`

Adapters may reference sessions, but only the runtime creates, mutates, and
destroys them.

### 2. Memory and Context Model

Standardize these memory types:

- `ShortTermTurn`
- `Episode`
- `Fact`
- `Preference`
- `Procedure`
- `ActionRecord`

Standardize memory scoping:

- default scope is per-persona
- shared memory is a separate tier, not an implicit merge
- shared memory is reserved for relationship, social, and explicitly shared
  user/environment context
- runtime owns access control between persona-local and shared memory

Standardize prompt assembly into segments:

- stable prefix
- pinned session/user/persona memory
- recent window
- retrieved context
- turn-specific volatile input

Standardize cache behavior:

- cache stable prefixes only
- track revision/invalidation explicitly
- expose cache telemetry in runtime status and operator UI

### 3. Autonomy and Tool Policy Model

Every autonomous or tool-driven loop must be budgeted with:

- `max_steps`
- `max_tool_calls`
- `max_wall_time_ms`
- `max_tokens_in`
- `max_tokens_out`
- `max_cost_usd`

Every effectful tool/action must produce an `ActionRecord` with:

- action type
- normalized inputs
- outcome
- side effects
- approval state
- optional rollback metadata

### 4. Adapter Contract Model

Standardize the existing runtime contract instead of inventing a parallel one.

Near-term work should extend the current `PlatformFacts`-based ingress model and
the current runtime API contract documented in `docs/RUNTIME_API.md`.

Standardize and type:

- normalized ingress built from `PlatformFacts`
- runtime event construction through the maintained event-builder seam
- runtime response envelope / decision shape already described by the runtime
  API docs
- adapter capability declaration
- explicit separation between:
  - transport hygiene
  - runtime policy

Near-term implementation should formalize the current contract, not replace it
with a second abstraction stack.

Adapters must never own:

- prompt assembly
- persona policy
- provider routing
- tool selection policy
- memory coordination
- response decision policy

### 5. Web Operator Surface Model

The web operator surface should expose:

- runtime health
- active sessions
- traces and recent events
- tool activity
- approval queue
- memory/context inspection
- provider/cache telemetry

The default dashboard should answer:

- what is running
- what it is doing
- what needs approval
- what changed

### 6. Security Boundary Model

Security policy should assume:

- runtime owns secrets
- adapters are less trusted than runtime
- tool and MCP outputs are untrusted input
- long-term memory writes require provenance
- approvals are runtime-owned, UI-rendered

## Prioritized Near-Term Implementation

1. Formalize the adapter SDK and normalized runtime event/response contract.
2. Build the runtime trace emitter and make it the backbone of operator
   introspection.
3. Implement a runtime-owned memory coordinator over typed memory classes.
4. Harden prompt assembly into a cache-aware context pipeline.
5. Implement tool risk tiers, action logging, and approval queue semantics.
6. Finish removing `services/*` authority from maintained paths.
7. Expand the web operator surface around session, trace, memory, and approval
   visibility.
8. Standardize session lifecycle behavior across all maintained surfaces.
9. Add security-focused runtime enforcement:
   - secret redaction
   - trust zones
   - untrusted-content handling
10. Defer embodiment and environment bridges to explicit future slices.

## Explicit Defer List

These are intentionally not part of the current implementation pass:

- VRM or embodiment renderer implementation
- scene systems
- game/environment bridges
- RL-style embodied learning
- broad multi-agent orchestration expansion
- fine-tuning/distillation pipelines

They remain valid long-term directions, but should not distort near-term
runtime hardening work.

## Anti-Patterns To Avoid

Do not adopt these patterns:

- adapter-local intelligence
- service-layer second authority
- prompt assembly outside runtime
- invisible autonomy without trace or approval records
- memory writes without provenance and revision
- UI-driven orchestration that acts like a second runtime
- plugin systems that own policy instead of exposing capabilities
- architecture decisions driven by demos instead of stable boundaries

## Acceptance Criteria For The Next Phase

The next implementation phase should be considered aligned only if:

- runtime ownership is clearer after the change, not blurrier
- adapters become thinner, not smarter
- context/memory/tool policy become more typed and inspectable
- web operator surfaces gain real runtime visibility
- security boundaries become more explicit and enforceable
- deferred embodiment work does not leak back into current runtime priorities

## Assumptions

- The two markdown research reports are sufficient for the first synthesis pass.
- The PDF may contain useful context but is not required to unblock decisions.
- The current priority is near-term runtime work, not full vision execution.
- Embodiment remains part of the vision but is intentionally deferred from this
  implementation brief.
