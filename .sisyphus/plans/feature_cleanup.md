# Work Plan: Feature Cleanup & Consolidation

## Overview
Remove redundant features and consolidate overlapping systems to improve maintainability.

## Current Issues
1. **Ambient Mode** - Deprecated, conflicts with AI-first persona system
2. **Proactive Engagement** - Overlaps with Naturalness system
3. **RAG Configuration** - Too granular (6 separate toggles)
4. **Metrics vs Analytics** - Should be merged
5. **Timing Systems** - 3 overlapping systems

---

## Phase 1: Remove Ambient Mode (HIGH PRIORITY)

### Task 1.1: Remove from config/features.py
- [x] Delete `AmbientConfig` class (lines 69-76)

### Task 1.2: Remove from config/__init__.py  
- [x] Remove `AmbientConfig` import
- [x] Remove `ambient = AmbientConfig()` instance
- [x] Remove backward compatibility aliases:
  - AMBIENT_MODE_ENABLED
  - AMBIENT_CHANNELS
  - AMBIENT_IGNORE_USERS
  - AMBIENT_LULL_TIMEOUT
  - AMBIENT_MIN_INTERVAL
  - AMBIENT_CHANCE

### Task 1.3: Remove from services/persona/behavior.py
- [ ] Remove `ambient_interval_min` and `ambient_chance` attributes
- [ ] Remove ambient-related logic from `_tick_loop()` if present

### Task 1.4: Remove from cogs/chat/message_handler.py
- [ ] Remove ambient mode check (lines ~585-640)
- [ ] Remove "ambient_channel" response reason

### Task 1.5: Update .env.example
- [ ] Remove all AMBIENT_* environment variables
- [ ] Add note: "Ambient mode removed - use Naturalness/Proactive instead"

---

## Phase 2: Merge Proactive into Naturalness (HIGH PRIORITY)

### Task 2.1: Update config/features.py
- [ ] Move `ProactiveConfig` settings into `NaturalnessConfig`
- [ ] Add `PROACTIVE_ENABLED` to NaturalnessConfig
- [ ] Add `PROACTIVE_COOLDOWN` to NaturalnessConfig
- [ ] Add `PROACTIVE_MIN_MESSAGES` to NaturalnessConfig
- [ ] Delete `ProactiveConfig` class

### Task 2.2: Update config/__init__.py
- [ ] Remove `ProactiveConfig` import
- [ ] Remove `proactive = ProactiveConfig()` instance
- [ ] Remove backward compatibility aliases (keep as deprecated warnings)
- [ ] Add proactive settings to naturalness namespace

### Task 2.3: Update services/persona/behavior.py
- [ ] Change `self.proactive_enabled` to use `Config.naturalness.PROACTIVE_ENABLED`
- [ ] Change `self.proactive_cooldown` to use `Config.naturalness.PROACTIVE_COOLDOWN`

### Task 2.4: Update .env.example
- [ ] Move PROACTIVE_* variables under Naturalness section
- [ ] Add deprecation comments for old variable names

---

## Phase 3: Simplify RAG Configuration (MEDIUM PRIORITY)

### Task 3.1: Update config/rag.py
- [ ] Add `MODE: str = BaseConfig._get_env("RAG_MODE", "simple")`
- [ ] Keep all sub-features but document that MODE="simple" disables advanced features
- [ ] Add logic: if MODE == "simple", override advanced features to False

### Task 3.2: Update config/__init__.py
- [ ] Add `RAG_MODE = rag.MODE`

### Task 3.3: Update .env.example
- [ ] Add RAG_MODE=simple
- [ ] Group RAG settings under clear sections:
  - Basic: RAG_ENABLED, RAG_MODE
  - Advanced (only used when MODE=advanced): hybrid, reranker, etc.

---

## Phase 4: Merge Metrics and Analytics (MEDIUM PRIORITY)

### Task 4.1: Update config/analytics.py
- [ ] Merge `AnalyticsConfig` into `DashboardConfig`
- [ ] Move all analytics settings under dashboard namespace
- [ ] Keep backward compatibility for METRICS_* variables

### Task 4.2: Update config/__init__.py
- [ ] Remove `analytics = AnalyticsConfig()` instance
- [ ] Move analytics settings under dashboard
- [ ] Keep backward compatibility aliases

### Task 4.3: Update .env.example
- [ ] Group all analytics/metrics under single section
- [ ] Document that METRICS_ENABLED implies dashboard analytics

---

## Phase 5: Unify Timing Systems (MEDIUM PRIORITY)

### Task 5.1: Update config/features.py
- [ ] Expand `TimingConfig` to include adaptive timing
- [ ] Add `MODE: str = BaseConfig._get_env("TIMING_MODE", "natural")`
- [ ] Add mode options: static, natural, adaptive
- [ ] Merge adaptive timing settings into TimingConfig

### Task 5.2: Update config/__init__.py
- [ ] Remove `adaptive_timing = AdaptiveTimingConfig()` instance
- [ ] Add adaptive settings to timing namespace
- [ ] Keep backward compatibility

### Task 5.3: Update services/persona/behavior.py
- [ ] Update timing initialization to use unified config
- [ ] Add logic to select timing mode

---

## Phase 6: Testing & Validation (HIGH PRIORITY)

### Task 6.1: Syntax Validation
- [ ] Run `python -m py_compile` on all modified files
- [ ] Check for import errors

### Task 6.2: Import Testing
- [ ] Test `from config import Config` works
- [ ] Test backward compatibility: `Config.AMBIENT_MODE_ENABLED` raises deprecation warning
- [ ] Test new style: `Config.naturalness.PROACTIVE_ENABLED`

### Task 6.3: Integration Testing
- [ ] Start bot with new config
- [ ] Verify all features still work
- [ ] Check logs for deprecation warnings

---

## Files to Modify

### Config Files (11 files)
1. `config/features.py` - Remove AmbientConfig, merge Proactive into Naturalness, unify timing
2. `config/rag.py` - Add MODE preset
3. `config/analytics.py` - Merge Metrics into Dashboard
4. `config/__init__.py` - Update imports and backward compatibility
5. `config.py` (old) - Add deprecation warnings

### Service Files (2 files)
6. `services/persona/behavior.py` - Remove ambient, update config references
7. `cogs/chat/message_handler.py` - Remove ambient mode logic

### Documentation (1 file)
8. `.env.example` - Update environment variable organization

### Testing (1 file)
9. Create `tests/test_config.py` - Verify config loading works

---

## Estimated Effort
- **Phase 1**: 30 minutes (safe removal)
- **Phase 2**: 45 minutes (merging features)
- **Phase 3**: 30 minutes (RAG presets)
- **Phase 4**: 30 minutes (merge metrics)
- **Phase 5**: 45 minutes (unify timing)
- **Phase 6**: 30 minutes (testing)

**Total**: ~3.5 hours

---

## Success Criteria
- [ ] All Ambient Mode references removed
- [ ] Proactive merged into Naturalness
- [ ] RAG has simple/advanced presets
- [ ] Metrics merged into Analytics
- [ ] Timing systems unified
- [ ] All tests pass
- [ ] Bot starts successfully
- [ ] No breaking changes for existing .env files

---

## Backward Compatibility Strategy

All changes maintain backward compatibility:
1. Old `Config.AMBIENT_MODE_ENABLED` will raise DeprecationWarning but still work temporarily
2. Old `Config.PROACTIVE_ENGAGEMENT_ENABLED` will map to `Config.naturalness.PROACTIVE_ENABLED`
3. Environment variables keep working even if reorganized internally
4. After 1 release cycle, remove deprecated aliases

---

## Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking existing configs | Maintain backward compatibility aliases |
| Missing ambient references | Comprehensive grep search before removal |
| Feature conflicts | Test each phase separately |
| User confusion | Update .env.example with clear migration notes |

---

## Post-Cleanup Benefits

- **-500 lines** of dead code
- **-30%** config complexity
- **Clear separation** between engagement systems
- **Simpler RAG** configuration for users
- **Unified timing** reduces confusion
