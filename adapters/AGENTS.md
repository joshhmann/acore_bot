# ADAPTERS KNOWLEDGE BASE

**Generated:** 2026-02-28 06:31:42 PM PST
**Parent:** `./AGENTS.md`

## OVERVIEW

Platform boundary layer: convert Discord/CLI/Web IO into runtime-safe events and responses.

## STRUCTURE

```
adapters/
├── runtime_factory.py         # Composes GestaltRuntime (core + memory + providers + tools)
├── discord/                   # Discord input/output adapters + command surfaces
├── cli/                       # Terminal adapter and entrypoint
└── web/                       # FastAPI adapter and WebSocket API
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Wire runtime dependencies | `adapters/runtime_factory.py` | Main composition root; plugin and tool policy wiring |
| Add Discord platform behavior | `adapters/discord/` | Keep Discord SDK usage here, not in `core/` |
| Extend CLI behavior | `adapters/cli/adapter.py` | Input parsing and stdout output contracts |
| Extend Web API behavior | `adapters/web/adapter.py` | HTTP and WebSocket event mapping |
| Add Discord chat command behavior | `adapters/discord/commands/chat/main.py` | Runtime-first path with legacy fallback seam |

## CONVENTIONS

Keep platform SDK imports (`discord`, `fastapi`) inside `adapters/*`.
Map all external payloads to `core.schemas.Event` or `core.interfaces.AcoreEvent` before orchestration.
Treat `runtime_factory.py` as the single place to wire runtime dependencies and plugin/tool setup.
Preserve async behavior end-to-end across adapter event handlers.

## ANTI-PATTERNS

Do not import adapter modules from `core/*`.
Do not duplicate runtime orchestration logic in adapter handlers.
Do not add new Discord command flow under legacy `cogs/` when active path is `adapters/discord/commands/`.
Do not bypass tool policy or provider routing from adapter code.

## NOTES

`main.py` still loads Discord command cogs through `adapters/discord/commands/*`; `launcher.py` is the multi-surface entrypoint for Discord/CLI/Web.
