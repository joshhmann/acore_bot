# ACORE BOT AGENT GUIDE

Last updated: 2026-03-22 PST
Scope: root-level instructions for coding agents.

## Purpose
This file is the operating contract for agentic coding tools in this repository.
It emphasizes:
- exact build/lint/test commands (including single-test workflows)
- enforceable style conventions grounded in repo tooling and real code patterns

## Repo Snapshot
- Language: Python (async-heavy)
- Tooling: `uv`, `pytest`, `ruff`, `mypy`, `pre-commit`
- Architecture is dual-path:
  - legacy: `main.py` + `services/` + Discord command surface
  - runtime-first: `launcher.py` + `core/` + `adapters/`

## Build / Run Commands
```bash
# Install dependencies
uv sync

# Run legacy Discord bot path
uv run python main.py

# Run runtime-first launcher (Discord/CLI/Web by env flags)
uv run python launcher.py

# Run CLI adapter directly
uv run python -m adapters.cli
```

## Lint / Format / Typecheck Commands
```bash
# Lint
uv run ruff check .

# Lint with autofix
uv run ruff check . --fix

# Format (preferred formatter)
uv run ruff format .

# Type checking (matches pre-commit settings)
uv run mypy . --ignore-missing-imports --no-strict-optional

# Run all hooks
pre-commit run --all-files
```

## Test Commands (Canonical)
```bash
# Fast unit gate (used by pre-commit + CI unit job)
uv run pytest -m unit -v --tb=short

# Full test run
uv run pytest -v --tb=short

# Coverage threshold gate (70%)
uv run pytest --cov=. --cov-report=html --cov-report=term --cov-fail-under=70

# Tiered helper script
./scripts/test_runner.sh --fast
./scripts/test_runner.sh --integration
./scripts/test_runner.sh --e2e
./scripts/test_runner.sh --slow
./scripts/test_runner.sh --all
./scripts/test_runner.sh --coverage
```

## Single-Test Workflows (Use These)
```bash
# One test file
uv run pytest tests/unit/test_foo.py -v --tb=short

# One test function
uv run pytest tests/unit/test_foo.py::test_bar -v --tb=short

# Pattern match if exact node id is unknown
uv run pytest tests/unit -k "bar" -v --tb=short
```

Notes:
- `pyproject.toml` explicitly registers only marker `unit`.
- Scripts/docs mention `integration`, `e2e`, `slow`, but those markers are not fully standardized in config.
- `scripts/run_all_tests.sh` is for optimization/perf script flows, not the main pytest suite.

## Code Style Guidelines

### Imports
- Order imports as: standard library, third-party, local modules.
- Keep platform SDK imports in `adapters/*`, not `core/*`.
- Prefer explicit imports; avoid wildcard imports.
- Use `if TYPE_CHECKING:` for type-only imports where needed.

### Formatting
- Use `ruff format` as source of truth for formatting.
- Keep edits consistent with nearby style and structure.
- Add comments only when behavior is not obvious.
- Keep docstrings concise and practical.

### Types
- Add type annotations for new/modified public functions and methods.
- Include explicit return types (`-> None` or concrete type).
- Follow existing modern patterns: `from __future__ import annotations`, `X | None`, `dict[str, Any]`.
- Use `Any` only at unavoidable boundaries (external payloads/adapters).

### Naming
- Classes: `PascalCase`
- Functions/methods/variables: `snake_case`
- Constants/env keys: `UPPER_SNAKE_CASE`
- Internal helpers/private members: `_leading_underscore`

### Async / Concurrency
- Keep I/O and external service paths async end-to-end.
- Use `await`; do not introduce blocking wrappers in hot paths.
- Use `asyncio.create_task` only for intentional background work with lifecycle tracking.

### Error Handling and Logging
- Prefer specific exception types over broad `Exception` where practical.
- If broad catches are required at boundaries, log context-rich messages.
- Never silently swallow exceptions.
- Use module-level logger pattern: `logger = logging.getLogger(__name__)`.
- Preserve graceful-degradation patterns for optional integrations.

### Testing Expectations for Changes
- During iteration, run the smallest relevant tests first (single-file/single-test).
- Before finalizing non-trivial changes, run `uv run pytest -m unit -v --tb=short` at minimum.
- For command/tooling changes, run impacted scripts under `scripts/`.

## External Agent Guardrails
Use this section for delegated coding agents such as Kimi or other sub-agents.

### Required Reading Before Editing
- Read the relevant canonical docs first:
  - `docs/STATUS.md`
  - `docs/ARCHITECTURE.md`
  - `docs/RUNTIME_API.md`
  - `docs/VISION.md` if the task touches product direction
- If the task comes from `docs/research/`, treat research docs as supporting context only.
- Re-check canonical docs before claiming completion if the change touches runtime contracts, memory, tracing, tools, auth, or adapter boundaries.

### Non-Negotiable Invariants
- The runtime is the single authority for sessions, memory coordination, provider routing, tool policy, traces, and persona/session state.
- Maintained adapters stay thin: parse -> normalize -> runtime -> render.
- Do not create a second authority for an existing concept.
  - If a canonical type/module already exists, extend it there.
  - Do not redefine runtime contracts, trace models, memory models, or adapter SDK types in adapter modules.
- Do not move policy into adapters, web UI, or helper wrappers.
- Do not reintroduce `services/*` authority into maintained runtime-first paths.
- Preserve maintained behavior unless the task explicitly calls for behavior change.

### Forbidden Patterns
- Do not define duplicate dataclasses/enums/contracts for concepts already owned in `core/*`, `memory/*`, `tools/*`, or other canonical modules.
- Do not change base-contract semantics in one implementation only.
  - If a shared interface changes, update the canonical interface centrally and keep implementations consistent.
- Do not hardcode defaults where the maintained path already uses config, environment, or runtime resolution.
- Do not broaden a slice into unrelated refactors under the guise of cleanup.
- Do not treat research docs as canonical product truth.

### Required Self-Checks Before Completion
- Run a duplicate-authority search for any core type you touched.
  - Example:
    - `rg -n "^class (RuntimeDecision|AdapterConfig|AdapterLifecycleContract|TraceSpan|TraceSummary)\\b" core adapters memory tools`
- Verify public/helper signatures against real call sites.
  - If you add or change a helper API, check every touched call site for exact argument compatibility.
- Confirm at least one maintained-path integration test exercises the new behavior.
  - Isolated unit tests for a helper module are not enough on their own.
- Explicitly review whether the change preserved existing maintained behavior at the runtime boundary.

### Required Output From Delegated Agents
- What changed
- Changed files
- Tests run
- Which canonical authority was extended
- Which maintained behavior was preserved
- Any remaining limitations or deferred follow-ups

### Scope Discipline
- Prefer the smallest change that centralizes authority and preserves maintained behavior.
- For runtime-core work, avoid parallel slices that touch the same authority surfaces:
  - `core/runtime.py`
  - `core/interfaces.py`
  - `core/schemas.py`
  - `memory/manager.py`
  - `tools/*`
- If a task would require inventing a second abstraction stack to “make progress,” stop and extend the canonical authority instead.

## CI / Hook Ground Truth
- `.github/workflows/test.yml` runs:
  - unit tests (`-m unit`)
  - integration tests (`-m integration` on PR)
  - coverage gate (70%)
  - ruff lint
- `.pre-commit-config.yaml` runs:
  - `ruff --fix`
  - `ruff-format`
  - `uv run pytest -m unit --tb=short -q`
  - `mypy --ignore-missing-imports --no-strict-optional`

## Cursor / Copilot Rules
Checked and currently absent in this repository:
- `.cursor/rules/` (not found)
- `.cursorrules` (not found)
- `.github/copilot-instructions.md` (not found)

If these files are added later, treat them as higher-priority agent instructions and merge their constraints here.

## High-Risk Anti-Patterns in This Repo
- Do not assume older docs about flat `cogs/` layout are current.
- Do not move platform SDK logic into `core/` runtime modules.
- Do not rely on unregistered pytest markers as hard gates.
- Do not commit runtime artifacts (`data/`, `logs/`, caches, generated state).

## Practical File Targets
- Runtime orchestration: `core/runtime.py`
- Runtime composition: `adapters/runtime_factory.py`
- Service graph wiring: `services/core/factory.py`
- Discord command seam: `adapters/discord/commands/chat/main.py`
- Shared test fixtures: `tests/conftest.py`
