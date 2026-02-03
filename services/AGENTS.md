# SERVICES ARCHITECTURE

**Generated:** 2025-01-23 08:30:06 PM

## OVERVIEW
Core business logic layer with 21 services for LLM, persona, memory, and voice systems.

## STRUCTURE
```
services/
├── agents/          # AI agent management
├── analytics/       # Real-time metrics dashboard
├── clients/         # External API clients
├── core/           # Factory pattern and foundations
├── discord/        # Discord-specific services
├── interfaces/     # Abstract interfaces
├── llm/            # LLM providers and caching
├── memory/         # User profiles and RAG
├── persona/        # Character behavior and relationships
└── voice/          # TTS/STT/RVC pipeline
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Service creation | `core/factory.py` | All services via ServiceFactory |
| AI behavior | `persona/behavior.py` | Personality engine |
| Character routing | `persona/router.py` | Dynamic persona selection |
| Memory management | `memory/profiles.py` | User learning system |
| Voice processing | `voice/` | TTS/STT/RVC pipeline |

## CONVENTIONS
**Factory Pattern**: All services created via `ServiceFactory.get_service()`
**Async Interfaces**: All service methods must be async/await
**Dependency Injection**: Services declare dependencies in constructors
**Error Handling**: Use service-specific exceptions with retry logic
**Lifecycle Management**: Services implement startup/shutdown hooks

## ANTI-PATTERNS
**Never instantiate services directly** - Use ServiceFactory
**Never sync calls in services** - All methods must be async
**Never import services circularly** - Use interface abstractions
**Never store state in service classes** - Use external storage