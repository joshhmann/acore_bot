# CORE RUNTIME KNOWLEDGE BASE

**Generated:** 2026-02-28 06:31:42 PM PST
**Parent:** `./AGENTS.md`

## OVERVIEW

Platform-agnostic runtime layer for persona routing, context assembly, provider/tool orchestration, and structured responses.

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Runtime request lifecycle | `core/runtime.py` | `handle_event` is the canonical orchestration flow |
| Event/response contracts | `core/schemas.py` | `Event`, `Response`, `ToolCall`, `ToolResult` |
| Platform abstraction contracts | `core/interfaces.py` | `InputAdapter`, `OutputAdapter`, `EventBus` |
| Persona selection logic | `core/router.py` | Mention/metadata/default persona resolution |
| Persona prompt/state behavior | `core/persona_engine.py` | System prompt build and state updates |

## CONVENTIONS

Keep `core/*` free from platform SDK dependencies.
Use schema objects from `core/schemas.py` for all runtime interactions.
Use `Router` and `PersonaEngine` for persona choice and prompt assembly; avoid ad-hoc selection logic.
Prefer deterministic state changes in `PersonaEngine` and persist through memory manager.

## ANTI-PATTERNS

Do not import `discord`, `fastapi`, or adapter modules into `core/*`.
Do not bypass `ProviderRouter` or `ToolRunner` in runtime orchestration.
Do not mutate cross-platform payload shapes outside schema/dataclass boundaries.
Do not fork alternate runtime flows that diverge from `GestaltRuntime.handle_event`.

## NOTES

The runtime is v1-oriented and coexists with legacy service flows; changes here must preserve adapter compatibility and migration seams.
