# Task 15: Discord Regression Tests - Completion Summary

## Created File
- `tests/test_regression_discord.py` - 31 regression tests

## Test Categories

### 1. Core Service Isolation (2 tests)
- `test_no_discord_imports_in_core_services` - Verifies core services don't import Discord
- `test_discord_imports_limited_to_expected_files` - Tracks known violations

Known violations tracked:
- `services/persona/router.py` - webhook functionality
- `services/conversation/review.py` - embed functionality  
- `services/core/factory.py` - adapter creation
- `services/voice/streaming_tts.py` - voice pipeline (expected)

### 2. Adapter Imports (6 tests)
- Discord adapter import and interface verification
- CLI adapter import (verifies no Discord deps)
- Interface method verification

### 3. JSON Serialization (5 tests)
- AcoreMessage
- AcoreUser
- AcoreChannel
- PersonaSpokeEvent
- ConversationSummaryEvent

### 4. EventBus (5 tests)
- Event emission
- Multiple handlers
- Unsubscribe
- Async handler support
- No-handler graceful handling

### 5. Discord Functionality with Mocks (5 tests)
- Message conversion
- User conversion
- Channel conversion
- Output adapter send
- Output adapter embed

### 6. Bot Behavior (2 tests)
- Mention response
- Persona event messaging

### 7. Command Framework (2 tests)
- Character commands existence
- Chat command handler existence

### 8. Framework Interfaces (3 tests)
- InputAdapter abstract
- OutputAdapter abstract
- EventBus abstract

### 9. Type System (2 tests)
- AcoreContext.reply
- Dataclass defaults

## Test Results
All 31 tests pass (0 failures)

## Evidence
- Test output saved to: `.sisyphus/evidence/task-15-test-results.txt`

## Notes
- No real Discord connection required (all mocked)
- Tests run in <1 second
- Uses pytest markers: `unit`, `regression`
