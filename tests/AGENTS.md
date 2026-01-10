# PROJECT KNOWLEDGE BASE

**Generated:** 2025-01-07 09:53:40 PM
**Parent:** ./AGENTS.md

## OVERVIEW

Tiered testing system with 4 levels, extensive mocking fixtures, and 70% coverage requirement.

## STRUCTURE

```
tests/
├── conftest.py         # Comprehensive pytest configuration with 15+ fixtures
├── unit/               # Fast tests (<5s) with 11 files
├── integration/        # Service interaction tests (5-30s)
└── standalone/         # Full pipeline tests (30s+)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add unit test | `tests/unit/` | Fast, <5s execution |
| Mock Discord objects | `tests/conftest.py` | 15+ fixtures available |
| Run tiered tests | `scripts/test_runner.sh` | 4-tier system |
| Performance testing | `scripts/test_runner.sh --coverage` | Coverage analysis |

## CONVENTIONS

**Tiered Execution**: unit (fast) → integration (5-30s) → e2e (30s+) → slow (weekly)
**Extensive Mocking**: All external services mocked via conftest.py fixtures
**Coverage Minimum**: 70% required before merges
**uv Integration**: Use `uv run pytest` instead of direct pytest

## ANTI-PATTERNS (THIS PROJECT)

**No External Dependencies**: Tests run without services due to mocking
**No Slow Tests in CI**: Only unit/integration run on PR, e2e pre-deploy
**No Coverage Gaps**: Below 70% blocks merges