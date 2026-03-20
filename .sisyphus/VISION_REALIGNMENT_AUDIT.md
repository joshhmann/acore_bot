# Vision Realignment Audit (2026-03-10)

## Purpose
Re-anchor Gestalt to current reality and recent goals, remove stale status drift, and define execution priorities for autonomous in-scene VRM behavior.

## Source of Truth (Going Forward)
1. `.sisyphus/boulder.json` (program progress)
2. `.sisyphus/plans/*.md` (task/acceptance tracking)
3. `agent-tasks` registry (active execution queue)
4. CI/test outputs (functional health)

## Current Reality
- Runtime-first orchestration is present and operational (`core/runtime.py`).
- Social intelligence stack exists (`core/social_intelligence/*`) but is not fully driving avatar behavior.
- VRM rendering and frontend scene exist (`frontend/src/*`, desktop bridge), but behavior-learning-to-scene loop is incomplete.
- Unit test status: 490 passed (selected unit run).

## Confirmed Drift / Issues
1. **Doc status drift**: multiple stale completion/status docs with conflicting metrics (deleted in this audit pass).
2. **Web adapter code drift**: duplicated imports/routes and a `self._port` bug in `adapters/web/adapter.py` (fixed in this audit pass).
3. **Integration seam gap**: SIL/training output does not reliably flow to VRM action transport and scene state feedback.

## Vision (Realigned)
Gestalt should be a runtime-governed, multi-surface character framework where:
- social context and learning signals influence runtime decisions,
- runtime emits deterministic avatar action envelopes,
- web/desktop VRM scenes execute those actions,
- user response feeds back into learning/adaptation.

## Priority Decisions (Immediate)
1. Define a canonical `VRMActionMessage` envelope in runtime schemas.
2. Implement runtime-side intent/action classification bridge from social context to action mapping.
3. Extend websocket/runtime transport to deliver avatar action envelopes to web/desktop clients.
4. Add scene-state feedback ingestion path to learning/adaptation modules.
5. Add integration tests for full loop: event -> social context -> action envelope -> client render event -> feedback record.

## Next Sprint Scope (Execution)
- S1: transport + schema + runtime intent bridge
- S2: frontend/desktop action consumer + state transitions
- S3: feedback loop persistence + adaptation updates
- S4: e2e tests and metrics dashboard for behavior-learning efficacy

## Audit Actions Performed
- Removed stale docs:
  - `.sisyphus/COMPLETION_STATUS.md`
  - `.sisyphus/FINAL_STATUS.md`
  - `.sisyphus/IMPLEMENTATION_COMPLETE.txt`
  - `.sisyphus/PROJECT_COMPLETE.md`
  - `.sisyphus/VERIFICATION_REPORT.md`
- Fixed code drift in `adapters/web/adapter.py`:
  - removed duplicate FastAPI import fallback blocks
  - removed duplicate websocket route declarations
  - fixed `uvicorn.Config(... port=self.port ...)`

## Notes
Use this file as the canonical reset point for planning and implementation alignment.

## Documentation Pruning Policy (Applied)
- Keep active: `plans/*.md` technical specs, `evidence/*` implementation proof, and `notepads/*/learnings.md` or `decisions.md` context logs.
- Archive status noise: completion summaries and stale "project complete" assertions that conflict with this audit's integration-gap finding.
- Delete only duplicate top-level completion reports that provide no unique technical evidence.
- Treat this file as the status authority until end-to-end VRM learning loop tests pass.
