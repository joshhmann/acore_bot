# PROJECT KNOWLEDGE BASE

**Generated:** 2025-01-07 09:53:40 PM
**Parent:** ./AGENTS.md

## OVERVIEW

Helper utilities including error handlers, DI container, logging config, and system context managers.

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Error handling | `utils/error_handlers.py` | Custom exception handlers |
| Dependency injection | `utils/di_container.py` | Service container pattern |
| Logging setup | `utils/logging_config.py` | Structured logging configuration |
| Persona loading | `utils/persona_loader.py` | JSON character loading |
| System context | `utils/system_context.py` | Roleplaying rules enforcement |

## CONVENTIONS

**Utility Pattern**: Pure functions, no external dependencies
**Error Handling**: Specific exception types with proper logging
**Type Safety**: Full type hints throughout
**No Side Effects**: Utilities don't modify global state

## ANTI-PATTERNS (THIS PROJECT)

**No State Mutation**: Utilities must be pure functions
**No Service Dependencies**: Never import from services/
**No Config Assumptions**: Use parameters, not global config
**No Roleplaying Violations**: system_context.py enforces character rules