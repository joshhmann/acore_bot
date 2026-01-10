# PROJECT KNOWLEDGE BASE

**Generated:** 2025-01-07 09:53:40 PM
**Parent:** ./AGENTS.md

## OVERVIEW

Comprehensive documentation hub with feature guides, system workflows, and deployment materials.

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Feature documentation | `docs/features/` | Individual feature specs |
| System workflows | `docs/system_workflows/` | Process documentation |
| Production deployment | `docs/PRODUCTION_READINESS.md` | Complete deployment guide |
| Setup guides | `docs/setup/` | Component configuration |
| Codebase summary | `docs/codebase_summary/` | 4,824 lines of architecture docs |

## STRUCTURE

```
docs/
├── codebase_summary/        # Architecture documentation (4,824 lines)
├── features/               # Feature specifications and guides
├── system_workflows/       # Process and workflow documentation
├── guides/                # User and admin guides
├── reports/               # Review and checkpoint reports
├── setup/                 # Component setup instructions
└── PRODUCTION_READINESS.md # Complete deployment guide
```

## CONVENTIONS

**Living Documentation**: Update existing files instead of creating new ones
**Code Reference**: Use codebase_summary/ for technical details
**Feature Tracking**: Document new features in features/ with implementation status
**Production Focus**: All deployment materials centralized in PRODUCTION_READINESS.md

## ANTI-PATTERNS (THIS PROJECT)

**Don't create new doc files** - Update existing living documentation
**No implementation summaries** - Use codebase_summary instead
**No temporary docs** - Delete plan files when complete
**Code is documentation** - Prioritize docstrings and type hints