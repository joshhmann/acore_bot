# PROJECT KNOWLEDGE BASE

**Generated:** 2025-01-07 09:53:40 PM
**Parent:** ./AGENTS.md

## OVERVIEW

Performance benchmarking, pipeline timing analysis, and migration scripts for persona formats.

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Performance testing | `scripts/benchmark_optimizations.py` | Optimization validation |
| Pipeline timing | `scripts/test_pipeline_timing.py` | API call timing analysis |
| Test runner | `scripts/test_runner.sh` | Interactive test menu |
| Persona migration | `scripts/migrate_persona_profiles.py` | .txt to .json conversion |
| Format normalization | `scripts/normalize_character_formats.py` | Character file standardization |

## CONVENTIONS

**No API Dependencies**: Performance tests run without external services
**Interactive Menus**: Test runner provides CLI for tier selection
**Migration Safety**: Backup creation before format conversions
**Timing Analysis**: Detailed logs of API call performance

## ANTI-PATTERNS (THIS PROJECT)

**No Production Data**: Scripts work with test data only
**No Silent Failures**: All migrations report status
**No Hardcoded Paths**: Use config or parameters
**No Backup Overwrites**: Migrations create new files