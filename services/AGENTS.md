# PROJECT KNOWLEDGE BASE

**Generated:** 2025-01-07 09:53:40 PM
**Parent:** ./AGENTS.md

## OVERVIEW

Business logic services with factory pattern, async interfaces, and deprecated legacy cleanup.

## STRUCTURE

```
services/
├── core/           # Service factory and context management
├── llm/            # LLM interfaces and caching
├── persona/          # Persona system, relationships, evolution
├── voice/            # TTS, STT, and RVC processing
├── memory/           # Conversation history and RAG
├── interfaces/        # Abstract interfaces
├── discord/          # Discord-specific services
└── deprecated/        # Legacy code for migration reference
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add new service | `services/` + update factory.py | Factory pattern |
| Implement async interface | `services/interfaces/` | Inherit from base |
| Add persona behavior | `services/persona/behavior.py` | Extend behavior engine |
| Modify caching layer | `services/llm/cache.py` | Token-aware caching |
| Update voice pipeline | `services/voice/` | Multi-stage processing |

## CONVENTIONS

**Factory Pattern**: All services initialized through `ServiceFactory` in `core/factory.py`
**Async First**: All external service calls must be async - no sync blocking
**Fallback Chain**: Services have 3-tier fallback (primary → secondary → deprecated)
**Interface Segregation**: Abstract interfaces in `interfaces/`, concrete implementations in service dirs

## ANTI-PATTERNS (THIS PROJECT)

**Legacy Dependencies**: `deprecated/` exists for migration reference - never import from here
**Sync Service Calls**: Blocking calls in async context forbidden
**Direct Instantiation**: Use factory, not direct service construction