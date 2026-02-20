# Framework Refinement Plan

## Current State Assessment

### ✅ What's Complete
- Core types (`AcoreMessage`, `AcoreContext`, etc.)
- Adapter interfaces (`InputAdapter`, `OutputAdapter`, `EventBus`)
- Discord adapter (full implementation)
- Service decoupling (ContextRouter, BehaviorEngine, Orchestrator, RL)
- Launcher entry point
- Architecture documentation

### 🔧 What Needs Refinement

#### 1. CLI Adapter (High Priority)
**Current**: Skeleton/stub implementation
**Needed**: Full working implementation
- Real stdin reading with asyncio
- Message parsing (@persona format)
- Proper event emission
- Interactive REPL mode

#### 2. Documentation Gaps (High Priority)
**Missing**:
- API Reference (all public methods/classes)
- Configuration guide (how to configure adapters)
- Troubleshooting guide
- Migration checklist
- Testing guide for adapter developers

#### 3. Framework Utilities (Medium Priority)
**Missing**:
- Adapter testing utilities/helpers
- Example/mock adapters
- Validation tools
- Debug/logging utilities

#### 4. Integration (Medium Priority)
**Needed**:
- Update main README.md with framework info
- Better launcher integration
- Configuration schema
- Environment variable documentation

## Refinement Tasks

### Phase 1: CLI Adapter Completion
- [ ] Implement full stdin reading loop
- [ ] Add message parsing (@persona message format)
- [ ] Create interactive REPL
- [ ] Add proper signal handling
- [ ] Test end-to-end

### Phase 2: Documentation
- [ ] Create docs/API_REFERENCE.md
- [ ] Create docs/CONFIGURATION.md
- [ ] Create docs/TROUBLESHOOTING.md
- [ ] Create docs/TESTING.md
- [ ] Update docs/ARCHITECTURE.md with refinements

### Phase 3: Framework Utilities
- [ ] Create core/testing.py with adapter test helpers
- [ ] Create examples/mock_adapter.py
- [ ] Add validation utilities

### Phase 4: Integration & Polish
- [ ] Update README.md
- [ ] Add configuration schema
- [ ] Create quickstart guide
- [ ] Add diagrams/visualizations

## Success Criteria

1. CLI adapter works end-to-end (can chat with personas via terminal)
2. Complete API documentation for all public interfaces
3. New adapter can be created in <30 minutes using docs
4. All configuration options documented
5. Common issues covered in troubleshooting guide
