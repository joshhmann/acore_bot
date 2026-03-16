# MEMORY RUNTIME KNOWLEDGE BASE

Last updated: 2026-03-09 PST
Scope: `memory/*`.

## Overview
Runtime memory primitives: local storage backends, episodic memory, recall tuning, summaries, and manager orchestration.

## Where To Look
| Task | Location | Notes |
|------|----------|-------|
| Manager entry | `memory/manager.py` | Memory orchestration |
| Episodic storage | `memory/episodes.py` | Similarity/retrieval flow |
| Recall tuning | `memory/recall_tuner.py` | Confidence/quality filters |
| Local backend | `memory/local_json.py` | Persistent local store |

## Anti-Patterns
- Mixing adapter transport concerns into memory modules.
- Inconsistent memory payload schema between stores and manager.
- Silent fallback behavior without traceability.
