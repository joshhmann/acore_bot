# Multiagent Implementation Plan - Next Phase

**Date**: 2025-12-11  
**Current Progress**: 40% (12/30 tasks complete)  
**Next Target**: 60% (18/30 tasks)  
**Focus**: High-impact features + integration fixes

---

## Priority 1: Fix Integration Issues (BLOCKING)

### Issue 1: Import Resolution Errors ⚠️
**Affected Files**:
- `services/persona/evolution.py`
- `services/persona/channel_profiler.py`
- `utils/stream_multiplexer` (missing)
- `services/voice/streaming_tts` (missing)

**Tasks**:
1. Verify import paths are correct
2. Check if files exist
3. Fix circular import issues
4. Add missing stub files if needed

### Issue 2: Attribute Access Errors in ChatCog ⚠️
**Affected Files**:
- `cogs/chat/main.py`
- `cogs/chat/message_handler.py`

**Tasks**:
1. Review service injection in `ChatCog.__init__`
2. Verify all services are properly passed
3. Check async initialization order
4. Add type hints for IDE support

### Issue 3: Type Safety Issues ⚠ 
**Affected Files**:
- `services/core/context.py`
- Multiple service constructors

**Tasks**:
1. Add proper Optional[] type hints where None is possible
2. Add null checks before attribute access
3. Fix type mismatches in function signatures

---

## Priority 2: Implement High-Impact Features

### T19-T20: Dynamic Framework Blending 🎯
**User Value**: HIGH - Allows personas to adapt behavior based on context  
**Complexity**: MEDIUM  
**Estimated Time**: 2-3 hours

**What It Does**:
- Persona can blend multiple frameworks (e.g., Neuro + Caring)
- Context-based framework switching (serious question → analytical, casual chat → friendly)
- Smooth personality transitions

**Implementation Plan**:
1. Create `services/persona/framework_blender.py`
2. Add `framework_blend_rules` to character schema
3. Modify `PersonaSystem.compile_persona()` to support blending
4. Update `ContextManager` to apply blended prompts
5. Test with multi-framework personas

**Example Config**:
```json
{
  "framework_blending": {
    "base_framework": "neuro",
    "blend_rules": [
      {"context": "emotional_support", "framework": "caring", "weight": 0.7},
      {"context": "creative_task", "framework": "chaotic", "weight": 0.5}
    ]
  }
}
```

---

### T21-T22: Emotional Contagion System 🎯
**User Value**: HIGH - More emotionally intelligent responses  
**Complexity**: LOW  
**Estimated Time**: 1-2 hours

**What It Does**:
- Bot picks up on user's emotional state over time
- Prolonged sadness → more empathetic responses
- Excitement → more energetic engagement
- Anger → calmer, de-escalating tone

**Implementation Plan**:
1. Extend `BehaviorState` with `sentiment_history` (last 10 messages)
2. Add `calculate_emotional_contagion()` to `BehaviorEngine`
3. Modify mood updates to incorporate user sentiment trends
4. Add contagion settings to persona config
5. Test with emotional conversations

**Algorithm**:
```python
def calculate_emotional_contagion(user_sentiment_history):
    # Average sentiment over last 10 messages
    avg_sentiment = sum(user_sentiment_history) / len(user_sentiment_history)
    
    if avg_sentiment < -0.5:  # User is consistently negative
        return {"mood_modifier": "empathetic", "tone": "supportive"}
    elif avg_sentiment > 0.5:  # User is consistently positive
        return {"mood_modifier": "excited", "tone": "enthusiastic"}
    else:
        return {"mood_modifier": "neutral", "tone": "balanced"}
```

---

### T25-T26: Semantic Lorebook Triggering 🎯
**User Value**: MEDIUM-HIGH - More intelligent lore matching  
**Complexity**: MEDIUM  
**Estimated Time**: 2-3 hours

**What It Does**:
- Current: Keyword-only matching ("Dagoth Ur" → triggers lore)
- New: Semantic matching ("the sixth house" → triggers Dagoth Ur lore)
- Uses sentence transformers for similarity

**Implementation Plan**:
1. Install `sentence-transformers` library
2. Create `services/memoria/semantic_lorebook.py`
3. Generate embeddings for all lore entries
4. Add similarity search (threshold: 0.7)
5. Fallback to keyword matching if semantic fails
6. Add caching for embeddings

**Performance Target**: <100ms per search

---

### T23-T24: Real-Time Analytics Dashboard (OPTIONAL)
**User Value**: MEDIUM - Nice monitoring but not essential  
**Complexity**: HIGH  
**Estimated Time**: 4-6 hours

**What It Does**:
- Web dashboard showing persona metrics
- Real-time updates via WebSocket
- Charts for mood trends, evolution progress, affinity scores

**Implementation Plan**:
1. Create `services/analytics/dashboard.py`
2. Use FastAPI for REST endpoints
3. WebSocket for real-time updates
4. Simple HTML/JS frontend with Chart.js
5. Authentication via API key

**Deferred**: This is lower priority than other features

---

## Recommended Implementation Order

### Week 1: Integration Fixes + Quick Wins
1. **Day 1**: Fix all integration issues (imports, attributes, types)
2. **Day 2**: Implement Emotional Contagion (T21-T22) - LOW complexity, HIGH impact
3. **Day 3**: Test integrated system, fix any new issues

### Week 2: Advanced Features
4. **Day 4-5**: Implement Framework Blending (T19-T20)
5. **Day 6-7**: Implement Semantic Lorebook (T25-T26)
6. **Day 8**: Testing and polish

### Week 3 (Optional): Analytics
7. **Day 9-11**: Real-Time Analytics Dashboard (T23-T24)
8. **Day 12-14**: Final integration testing and documentation

---

## Multiagent Task Breakdown

### Task 1: Integration Fixes (CRITICAL - DO FIRST)
```markdown
**Objective**: Fix all import resolution, attribute access, and type safety issues

**Files to Review**:
- services/persona/evolution.py
- services/persona/channel_profiler.py
- cogs/chat/main.py
- cogs/chat/message_handler.py
- services/core/context.py

**Steps**:
1. Find and fix import errors
2. Verify service injection paths
3. Add type hints for all None-possible parameters
4. Run linting to find remaining issues
5. Test imports in Python REPL

**Success Criteria**:
- No import errors
- No attribute access errors
- All type hints correct
- Bot starts without errors
```

### Task 2: Emotional Contagion (QUICK WIN)
```markdown
**Objective**: Implement emotional contagion system for empathetic responses

**New Files**:
- None (extends existing `BehaviorEngine`)

**Modified Files**:
- services/persona/behavior.py
- prompts/PERSONA_SCHEMA.md

**Steps**:
1. Add `sentiment_history: deque` to BehaviorState
2. Track user sentiment in `update_mood()`
3. Calculate avg sentiment over last 10 messages
4. Apply contagion modifiers to mood
5. Add contagion settings to schema

**Performance Target**: <1ms overhead

**Testing**:
- Send 5 sad messages, verify empathetic response
- Send 5 happy messages, verify enthusiastic response
- Test neutral baseline
```

### Task 3: Framework Blending (HIGH IMPACT)
```markdown
**Objective**: Allow personas to blend multiple frameworks based on context

**New Files**:
- services/persona/framework_blender.py

**Modified Files**:
- services/persona/system.py
- services/core/context.py
- prompts/PERSONA_SCHEMA.md

**Steps**:
1. Create FrameworkBlender class
2. Add blend_rules parsing to Character schema
3. Modify compile_persona() to detect blend triggers
4. Merge prompt templates with weighting
5. Add context detection (emotional_support, creative_task, etc.)

**Example**:
- Base: Neuro (analytical)
- User asks for emotional support → blend 70% Caring
- Result: Analytical + empathetic hybrid response
```

### Task 4: Semantic Lorebook (NICE TO HAVE)
```markdown
**Objective**: Enhance lorebook with semantic similarity matching

**New Files**:
- services/memoria/semantic_lorebook.py

**Dependencies**:
- sentence-transformers (pip install)

**Modified Files**:
- services/persona/lorebook.py

**Steps**:
1. Install sentence-transformers
2. Load model (all-MiniLM-L6-v2)
3. Generate embeddings for all lore entries
4. Store embeddings with entries
5. Use cosine similarity for matching
6. Fallback to keyword if semantic fails

**Performance Target**: <100ms
```

---

## Success Metrics

### Integration Fixes
- ✅ Bot starts without errors
- ✅ All services load correctly
- ✅ No type errors in IDE
- ✅ All imports resolve

### Emotional Contagion
- ✅ Mood adjusts to user sentiment
- ✅ Empathy increases with negative user mood
- ✅ Energy increases with positive user mood
- ✅ <1ms performance overhead

### Framework Blending
- ✅ Contexts trigger framework blends
- ✅ Blended prompts are coherent
- ✅ Smooth personality transitions
- ✅ Backwards compatible with single-framework personas

### Semantic Lorebook
- ✅ Conceptually related topics trigger lore
- ✅ Similarity threshold prevents false positives
- ✅ <100ms search performance
- ✅ Backwards compatible with keyword entries

---

## Deployment Checklist

Before deploying new features:
- [ ] All integration issues resolved
- [ ] All tests passing
- [ ] Performance targets met
- [ ] Documentation updated
- [ ] Backwards compatibility verified
- [ ] No breaking changes to existing personas

---

## What Should We Start With?

**Recommendation**: Start with Integration Fixes (Priority 1)

This unblocks everything else and ensures the 12 already-implemented features work correctly in production.

Then move to Emotional Contagion (Task 2) for a quick win with high user impact.

**Would you like me to**:
1. ✅ Fix integration issues first?
2. ✅ Then implement Emotional Contagion?
3. ⏸️ Move on to Framework Blending after?
4. ⏸️ Add Semantic Lorebook later?

Or would you prefer a different order?
