Behavior metrics enhancements implemented in metrics.py (2026-02-04).
- Added two new state stores: `behavior_decisions` and `engagement_stats`.
- Implemented methods: `record_behavior_decision`, `record_engagement`, `get_behavior_stats`.
- Designed to be backward-compatible and non-breaking for existing stats.

Follow-up ideas:
- Add per-channel breakdowns for engagement if needed.
- Extend tests to cover new API surface and edge cases (zero data, unknown decision_type).
