# Task A3: Implement Configuration for Hardcoded Values

## Task Description

Based on code analysis, multiple hardcoded timeout and threshold values need to be moved to configuration for better maintainability and production deployment.

## Hardcoded Values to Configure

### 1. Logging Configuration
- **File**: `utils/logging_config.py:98`
- **Issue**: `Config.LOG_LEVEL` referenced but not imported
- **Fix**: Import config properly and add missing config values

### 2. Timeouts and Thresholds
From the codebase analysis:

**Chat/Message Handling**:
- Typing delays: `min_delay=0.5, max_delay=2.0`
- Response lengths: token limits (50, 100, 200, 350, 500)
- Cooldown periods: 300 seconds, 600 seconds

**Analytics Dashboard**:
- Update intervals: 2 seconds
- WebSocket timeout values
- API key authentication settings

**Memory Systems**:
- RAG query thresholds
- Cache expiration times
- Profile save intervals

**Persona Systems**:
- Mood decay rates: 30 minutes
- Evolution milestones: 50, 100, 500, 1000, 5000 messages
- Conflict severity changes: +0.2, -0.1 per hour

## Implementation Tasks

1. **Add missing config values to `config.py`**:
   ```python
   # Logging
   LOG_LEVEL = "INFO"
   LOG_FORMAT = "json"
   LOG_FILE_PATH = "logs/bot.log"

   # Chat timing
   TYPING_MIN_DELAY = 0.5
   TYPING_MAX_DELAY = 2.0

   # Response lengths
   TOKEN_LIMITS = {
       "very_short": 50,
       "short": 100,
       "medium": 200,
       "long": 350,
       "very_long": 500
   }

   # Persona behavior
   MOOD_DECAY_MINUTES = 30
   EVOLUTION_MILESTONES = [50, 100, 500, 1000, 5000]
   CONFLICT_ESCALATION_RATE = 0.2
   CONFLICT_DECAY_RATE = 0.1
   ```

2. **Fix Config import in logging_config.py**:
   - Properly import from config
   - Add missing config values

3. **Replace hardcoded values**:
   - Search for hardcoded timeouts and thresholds
   - Replace with config references
   - Update `.env.example` with new config options

4. **Environment variable support**:
   - Allow override via environment variables
   - Add validation for config values

## Files to Modify

- `config.py` - Add new configuration values
- `utils/logging_config.py` - Fix import and use config
- `.env.example` - Add new environment variables
- Any files with hardcoded timeouts/thresholds

## Success Criteria

- [ ] All hardcoded timeouts and thresholds are configurable
- [ ] Config import issues resolved
- [ ] Environment variable override support added
- [ ] Configuration validation implemented
- [ ] Documentation updated with new config options

## Priority: MEDIUM (Maintainability & Production Readiness)