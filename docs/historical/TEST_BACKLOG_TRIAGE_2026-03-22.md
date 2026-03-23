# Test Backlog Triage

Date: 2026-03-22
Status: Historical reference

## Purpose
This note records the first curation pass after fixing `.gitignore` so tracked
tests under `tests/**` are no longer hidden by the broad `test_*.py` pattern.

These classifications are operational, not canonical product truth. They exist
to keep the maintained runtime-first test surface clean while the older backlog
is reviewed in smaller slices.

## Adopted In This Pass
These tests were verified on the current maintained path and are suitable for
tracking immediately:

- `tests/unit/test_auth_store.py`
- `tests/unit/test_auto_summary.py`
- `tests/unit/test_file_ops_tool.py`
- `tests/unit/test_shell_exec_tool.py`

Verification:

```bash
uv run pytest \
  tests/unit/test_auth_store.py \
  tests/unit/test_auto_summary.py \
  tests/unit/test_file_ops_tool.py \
  tests/unit/test_shell_exec_tool.py \
  -q --tb=short
```

Result: `47 passed`

## Quarantine Candidates
These files are visible now, but they do not match current maintained repo
truth yet. Reasons include missing modules, stale architecture assertions, or
behavior expectations that no longer reflect the runtime-first path.

- `tests/unit/test_adapter_runtime_boundaries.py`
- `tests/unit/test_cli_play_mode.py`
- `tests/unit/test_default_provider_config.py`
- `tests/unit/test_discord_operator_boundaries.py`
- `tests/test_regression_discord.py`
- `tests/test_config.py`
- `tests/unit/test_circuit_breaker.py`
- `tests/unit/test_executor_react.py`
- `tests/unit/test_gestalt_packaging.py`
- `tests/unit/test_goal_dataclass.py`
- `tests/unit/test_goal_decomposer.py`
- `tests/unit/test_goal_utils.py`
- `tests/unit/test_plan_execution.py`
- `tests/unit/test_plan_executor.py`
- `tests/unit/test_plan_store.py`
- `tests/unit/test_planner_schemas.py`
- `tests/unit/test_reasoning_step.py`
- `tests/unit/test_self_check.py`
- `tests/unit/test_tui_ascii.py`
- `tests/unit/test_tui_routing.py`

## Broader Legacy / Experimental Buckets
These areas need dedicated review rather than ad hoc adoption:

- `tests/e2e/`
- `tests/integration/`
- `tests/rl/`
- `tests/scenarios/`
- `tests/standalone/`
- `tests/unit/rl/`
- tests with heavy `services/*` coupling that are not part of the maintained
  runtime-first product path

## Next Actions
1. Keep adding verified maintained tests in small batches.
2. Rework or delete quarantine candidates only when their owning subsystem is in
   scope.
3. Avoid sweeping legacy/service-layer tests into the maintained gate without a
   matching architecture decision.
