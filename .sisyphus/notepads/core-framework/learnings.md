# Core Framework Wave 1 - Learnings

## Task 1: Platform-Agnostic Types

### Approach
Created pure stdlib dataclasses in `core/types.py` to replace Discord-specific types.
Used dataclass with field(default_factory=...) for mutable defaults.

### Key Decisions
1. Used `datetime.utcnow` as default for timestamp - ensures consistent serialization
2. Used `List[Dict[str, Any]]` for attachments - flexible for different platforms
3. Used `Dict[str, Any]` for metadata - allows platform-specific extensions
4. Callable return type is `Any` - adapters decide return type

### QA Verification
- All imports work correctly
- JSON serialization via `__dict__` works with `default=str` for datetime
- `reply()` method properly delegates to callback
- No external dependencies - stdlib only

### Files Created
- `/root/acore_bot/core/__init__.py` - Package init with exports
- `/root/acore_bot/core/types.py` - Core dataclasses
- `/root/acore_bot/.sisyphus/evidence/task-1-core-types.txt` - QA evidence
