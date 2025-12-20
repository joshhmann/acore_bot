# Persona & Behavior Enhancement Roadmap

**Status**: 🟡 Planning Phase
**Last Updated**: 2025-12-10
**Total Features**: 13 major enhancements
**Total Tasks**: 30 implementation + review tasks

---

## Overview

This roadmap outlines advanced persona and behavior features to transform acore_bot from static character responses into a **living, adaptive AI ecosystem** with emotional intelligence, learning capabilities, and emergent inter-character dynamics.

### Design Philosophy

- ✅ **No Duplication**: All features verified against existing codebase
- ✅ **Incremental Enhancement**: Build on existing BehaviorEngine, PersonaSystem, and PersonaRelationships
- ✅ **Backwards Compatible**: Existing characters continue working without migration
- ✅ **Performance Conscious**: All features designed with token budgets and API costs in mind

---

## Feature Categories

### Tier 1: Core Intelligence (High Priority)
- Dynamic Mood System
- Context-Aware Verbosity
- Per-Persona Memory Isolation
- Curiosity-Driven Questions
- Topic Interest Filtering

### Tier 2: Adaptive Behavior (Medium Priority)
- Adaptive Ambient Timing
- Character Evolution
- Persona Conflicts
- Activity-Based Routing

### Tier 3: Advanced Systems (Lower Priority)
- Framework Blending
- Emotional Contagion
- Analytics Dashboard
- Semantic Lorebook Triggering

### Tier 4: Documentation (Final Phase)
- Schema Updates
- Migration Guides

---

## Implementation Plan

### Phase 1: Core Intelligence (Weeks 1-2)

#### T1-T2: Dynamic Mood System ✅ Complete
**Status**: 🟢 Complete
**Completed**: 2025-12-10
**Developer Agent**: Implementation
**Code Reviewer Agent**: Review
**Priority**: High
**Developer Agent**: Implementation
**Code Reviewer Agent**: Review
**Priority**: High

**Description**:
Add emotional state tracking (frustration, excitement, boredom, sadness) affecting response tone, proactive engagement probability, and reaction selection.

**Technical Details**:
- Store mood per persona in `BehaviorState.mood_state`
- Integrate with `BehaviorEngine` decision-making
- Mood affects: response tone, engagement probability, reaction selection
- Mood states: neutral, excited, frustrated, sad, bored, curious
- Mood transitions: gradual, sentiment-influenced

**Files to Modify**:
- `services/persona/behavior.py` - Add mood tracking
- `prompts/PERSONA_SCHEMA.md` - Document mood config

**Acceptance Criteria**:
- [ ] Mood state tracked per persona
- [ ] Mood affects response generation
- [ ] Mood transitions are gradual
- [ ] No personality inconsistencies
- [ ] Performance impact < 10ms per message

---

#### T3-T4: Context-Aware Response Length ✅ Complete
**Status**: 🟢 Complete
**Completed**: 2025-12-10
**Priority**: High

**Description**:
Extend BehaviorEngine to analyze conversation depth and adjust max_tokens dynamically.

**Technical Details**:
- Add `verbosity_by_context` config to PERSONA_SCHEMA
- Context types: casual_chat, detailed_question, storytelling, quick_reply
- Analyze: message length, question depth, topic complexity
- Dynamic token allocation: short (50-100), medium (100-300), long (300-500)

**Files to Modify**:
- `services/persona/behavior.py` - Add context analyzer
- `cogs/chat/helpers.py` - Add verbosity calculator
- `prompts/PERSONA_SCHEMA.md` - Document verbosity_by_context

**Acceptance Criteria**:
- [ ] Verbosity adjusts based on conversation depth
- [ ] Token budget doesn't overflow
- [ ] Works with ContextManager limits
- [ ] No jarring length changes

**Dependencies**: None

---

#### T5-T6: Enhance Persona Memory Isolation ✅ Complete
**Status**: 🟢 Complete
**Completed**: 2025-12-10
**Priority**: High

**Description**:
Extend UserProfileService to create separate memory stores per persona, preventing memory cross-contamination.

**Technical Details**:
- New structure: `data/profiles/{persona_id}/{user_id}.json`
- Each persona maintains independent user profiles
- Migrate existing profiles to default persona
- Memory retrieval scoped to active persona

**Files to Modify**:
- `services/discord/profiles.py` - Add persona-scoped storage
- Migration script for existing profiles

**Acceptance Criteria**:
- [ ] Separate memory per persona
- [ ] No memory bleed between personas
- [ ] Backwards compatible with existing profiles
- [ ] File I/O performance acceptable (< 50ms)

**Dependencies**: None

---

#### T7-T8: Curiosity-Driven Follow-Up Questions ⏳ Not Started
**Status**: 🔴 Not Started
**Priority**: High

**Description**:
Extend BehaviorEngine to detect when persona should ask follow-up questions based on curiosity_level config.

**Technical Details**:
- Use ThinkingService to identify interesting topics
- Curiosity levels: low (10%), medium (30%), high (60%), maximum (80%)
- Cooldown tracking: max 1 question per 5 minutes
- Topic memory: remember what was already asked

**Files to Modify**:
- `services/persona/behavior.py` - Add curiosity system
- `prompts/PERSONA_SCHEMA.md` - Document curiosity_level

**Acceptance Criteria**:
- [ ] Follow-up questions feel natural
- [ ] Cooldowns prevent spam
- [ ] Max 3 questions per 15-minute window
- [ ] Questions relevant to conversation

**Dependencies**: T4 (Context-Aware Verbosity)

---

#### T9-T10: Topic Interest Filtering ⏳ Not Started
**Status**: 🔴 Not Started
**Priority**: High

**Description**:
Add topic_interests and topic_avoidances to Character.knowledge_domain for selective proactive engagement.

**Technical Details**:
- Add fields to Character schema: `topic_interests`, `topic_avoidances`
- Lightweight keyword matching or ThinkingService classification
- Check topics before proactive engagement
- Performance target: < 50ms topic detection

**Files to Modify**:
- `services/persona/system.py` - Add topic fields to Character
- `services/persona/behavior.py` - Add topic filtering
- `prompts/PERSONA_SCHEMA.md` - Document topic fields

**Acceptance Criteria**:
- [ ] Topics filter proactive engagement
- [ ] False positive rate < 5%
- [ ] Performance < 50ms
- [ ] Doesn't block legitimate engagement

**Dependencies**: T2 (Mood System)

---

### Phase 2: Adaptive Behavior (Weeks 3-4)

#### T11-T12: Adaptive Ambient Timing ⏳ Not Started
**Status**: 🔴 Not Started
**Priority**: Medium

**Description**:
Replace fixed ambient_interval_min with ChannelActivityProfiler that learns channel patterns.

**Technical Details**:
- Track: peak hours, avg msg frequency, silence periods
- Adjust ambient triggers per-channel based on learned patterns
- Storage: `data/channel_activity_profiles.json`
- Learning window: 7 days rolling

**Files to Create**:
- `services/persona/channel_profiler.py` - Activity learning

**Files to Modify**:
- `services/persona/behavior.py` - Use learned thresholds

**Acceptance Criteria**:
- [ ] Learns channel patterns within 7 days
- [ ] No spam during activity surges
- [ ] Dead channels handled gracefully
- [ ] Highly active channels don't get spammed

**Dependencies**: T6 (Persona Memory Isolation)

---

#### T13-T14: Character Evolution System ⏳ Not Started
**Status**: 🔴 Not Started
**Priority**: Medium

**Description**:
Track interaction milestones and unlock new behaviors/quirks at thresholds.

**Technical Details**:
- Track: total messages, topics discussed, relationship depth
- Milestones: 50, 100, 500, 1000, 5000 messages
- Evolution stages unlock: tone shifts, new quirks, expanded knowledge
- Storage: `data/persona_evolution/{persona_id}.json`

**Files to Create**:
- `services/persona/evolution.py` - Evolution tracker

**Files to Modify**:
- `prompts/PERSONA_SCHEMA.md` - Document evolution_stages

**Acceptance Criteria**:
- [ ] Evolution feels gradual not sudden
- [ ] Milestones balanced (not too fast/slow)
- [ ] Backwards compatible
- [ ] No personality inconsistencies

**Dependencies**: T5 (Persona Memory), T10 (Topic Filtering)

---

#### T15-T16: Persona Conflict System ⏳ Not Started
**Status**: 🔴 Not Started
**Priority**: Medium

**Description**:
Add conflict_triggers to PersonaRelationships creating dynamic relationship arcs.

**Technical Details**:
- Conflict triggers: specific topics causing tension
- When triggered: reduce banter_chance temporarily, add argumentative modifiers
- Resolution: conflicts decay over time if topic avoided
- Storage: integrated into `data/persona_relationships.json`

**Files to Modify**:
- `services/persona/relationships.py` - Add conflict tracking
- `cogs/chat/message_handler.py` - Apply conflict modifiers

**Acceptance Criteria**:
- [ ] Conflicts enhance roleplay
- [ ] Don't derail conversations
- [ ] Resolution mechanics work
- [ ] Entertainment value high

**Dependencies**: T13 (Character Evolution)

---

#### T17-T18: Activity-Based Persona Switching ⏳ Not Started
**Status**: 🔴 Not Started
**Priority**: Medium

**Description**:
Extend PersonaRouter to consider user Discord activity (playing game X → prefer persona interested in game X).

**Technical Details**:
- Add `activity_preferences` to Character.knowledge_domain
- Match Discord activity types: gaming, listening, streaming, watching
- Fallback to sticky routing if no match
- Activity detection from `discord.Member.activity`

**Files to Modify**:
- `services/persona/router.py` - Add activity-based selection
- `services/persona/system.py` - Add activity_preferences to Character

**Acceptance Criteria**:
- [ ] Activity-based routing works
- [ ] Fallback behavior correct
- [ ] Sticky routing preserved
- [ ] Activity detection accurate

**Dependencies**: T9 (Topic Interest Filtering)

---

### Phase 3: Advanced Systems (Weeks 5-6)

#### T19-T20: Dynamic Framework Blending ⏳ Not Started
**Status**: 🔴 Not Started
**Priority**: Low

**Description**:
Allow personas to blend multiple frameworks based on context.

**Technical Details**:
- Create `FrameworkBlender` service
- Blend rules: context triggers → framework weights
- Merge prompt templates dynamically
- Example: questions → 70% assistant + 30% current framework

**Files to Create**:
- `services/persona/framework_blender.py` - Blending service

**Files to Modify**:
- `services/persona/system.py` - Add framework_blend_rules
- `prompts/PERSONA_SCHEMA.md` - Document blending rules

**Acceptance Criteria**:
- [ ] Blended prompts coherent
- [ ] No contradictory instructions
- [ ] Token budget impact acceptable
- [ ] Context detection accurate

**Dependencies**: T14 (Character Evolution)

---

#### T21-T22: Emotional Contagion System ⏳ Not Started
**Status**: 🔴 Not Started
**Priority**: Low

**Description**:
Personas gradually adjust their mood based on user sentiment patterns.

**Technical Details**:
- Track conversation sentiment trends in `BehaviorState.sentiment_history`
- Window: last 10 messages
- Mood adjustment: prolonged negative → more empathetic/supportive
- Contagion strength: configurable per persona

**Files to Modify**:
- `services/persona/behavior.py` - Add sentiment tracking and contagion
- `prompts/PERSONA_SCHEMA.md` - Document emotional_contagion settings

**Acceptance Criteria**:
- [ ] Mood shifts feel natural
- [ ] Not jarring
- [ ] Sentiment analysis accurate
- [ ] No inappropriate mood changes

**Dependencies**: T1 (Mood System), T11 (Adaptive Ambient)

---

#### T23-T24: Real-Time Persona Analytics Dashboard ⏳ Not Started
**Status**: 🔴 Not Started
**Priority**: Low

**Description**:
Create web dashboard showing persona metrics with real-time updates.

**Technical Details**:
- Framework: Flask or FastAPI
- Metrics: message counts, affinity scores, topic distribution, mood trends, evolution progress
- Real-time: WebSocket support
- Security: Authentication required, no sensitive user data exposure

**Files to Create**:
- `services/web/analytics.py` - Dashboard backend
- `templates/analytics.html` - Dashboard frontend

**Acceptance Criteria**:
- [ ] Dashboard accessible via web browser
- [ ] Real-time updates work
- [ ] No sensitive data exposed
- [ ] Performance: async data aggregation

**Dependencies**: T1 (Mood), T5 (Memory), T13 (Evolution)

---

#### T25-T26: Intelligent Lorebook Auto-Triggering ⏳ Not Started
**Status**: 🔴 Not Started
**Priority**: Low

**Description**:
Enhance LorebookService with semantic similarity instead of keyword-only matching.

**Technical Details**:
- Use sentence-transformers for lore entry embeddings
- Trigger on conceptually related topics not just exact keywords
- Relevance threshold: 0.7 similarity
- Backwards compatible with keyword-based entries

**Files to Modify**:
- `services/persona/lorebook.py` - Add semantic triggering

**Acceptance Criteria**:
- [ ] Semantic triggering works
- [ ] Performance overhead acceptable (< 100ms)
- [ ] Relevance threshold prevents false positives
- [ ] Backwards compatible

**Dependencies**: T12 (Adaptive Ambient)

---

### Phase 4: Documentation (Week 7)

#### T27-T28: Update PERSONA_SCHEMA.md ⏳ Not Started
**Status**: 🔴 Not Started
**Priority**: High (for deployment)

**Description**:
Update PERSONA_SCHEMA.md with all new autonomous behavior fields.

**New Fields to Document**:
- `mood_state` - Mood configuration
- `verbosity_by_context` - Context-based response length
- `curiosity_level` - Follow-up question frequency
- `topic_interests` - Preferred topics
- `topic_avoidances` - Topics to avoid
- `evolution_stages` - Milestone unlocks
- `conflict_triggers` - Relationship tension topics
- `activity_preferences` - Discord activity matching
- `framework_blend_rules` - Multi-framework blending
- `emotional_contagion` - Mood contagion settings

**Files to Modify**:
- `prompts/PERSONA_SCHEMA.md` - Add all new fields with examples

**Acceptance Criteria**:
- [ ] All fields documented
- [ ] Examples copy-paste ready
- [ ] Match implementation
- [ ] Backwards compatible

**Dependencies**: T20 (Framework Blending)

---

#### T29-T30: Create Migration Guide ⏳ Not Started
**Status**: 🔴 Not Started
**Priority**: High (for deployment)

**Description**:
Create migration guide for enabling new features on existing characters.

**Contents**:
- Before/after config examples
- Troubleshooting section
- Performance optimization tips
- Common pitfalls
- Testing checklist

**Files to Create**:
- `docs/PERSONA_BEHAVIOR_MIGRATION.md` - Migration guide

**Acceptance Criteria**:
- [ ] Guide is clear and actionable
- [ ] Tested on dagoth_ur.json
- [ ] All examples work
- [ ] Troubleshooting covers common issues

**Dependencies**: T28 (Schema Documentation)

---

## Task Dependency Graph

```
T1 (Mood) ──────────────────────┐
  │                              │
  ├─→ T2 (Mood Review)           │
  │                              │
  └─→ T9 (Topic Filter) ─────────┼─→ T21 (Emotional Contagion)
         │                       │      │
         └─→ T10 (Review) ───────┤      └─→ T22 (Review)
                                 │
T3 (Verbosity) ────────────────┐ │
  │                            │ │
  ├─→ T4 (Review)              │ │
  │                            │ │
  └─→ T7 (Curiosity) ──────────┼─┤
         │                     │ │
         └─→ T8 (Review)       │ │
                               │ │
T5 (Memory Isolation) ─────────┼─┼─→ T23 (Analytics)
  │                            │ │      │
  ├─→ T6 (Review)              │ │      └─→ T24 (Review)
  │                            │ │
  └─→ T11 (Adaptive Ambient) ──┼─┤
  │      │                     │ │
  │      └─→ T12 (Review) ─────┤ │
  │                            │ │
  └─→ T13 (Evolution) ─────────┼─┤
         │                     │ │
         ├─→ T14 (Review)      │ │
         │                     │ │
         ├─→ T15 (Conflicts) ──┤ │
         │      │              │ │
         │      └─→ T16 (Review)│
         │                     │ │
         └─→ T19 (Blending) ───┼─┤
                │              │ │
                ├─→ T20 (Review)│
                │              │ │
                └─→ T27 (Docs) ┘ │
                       │          │
                       ├─→ T28 (Review)
                       │          │
                       └─→ T29 (Migration)
                              │
                              └─→ T30 (Review)

T17 (Activity Routing) ───────────┘
  │
  └─→ T18 (Review)

T25 (Semantic Lorebook) ──────────┐
  │                                │
  └─→ T26 (Review) ────────────────┘
```

---

## Progress Tracking

### Overall Progress
- **Total Tasks**: 30
- **Completed**: 0
- **In Progress**: 0
- **Not Started**: 30
- **Progress**: 20% ████████████░░░░░░░░░░░░░ 6/30

### By Phase
| Phase | Tasks | Completed | Progress |
|-------|-------|-----------|----------|
| Phase 1: Core Intelligence | 10 | 6 | 60% |
| Phase 2: Adaptive Behavior | 8 | 0 | 0% |
| Phase 3: Advanced Systems | 8 | 0 | 0% |
| Phase 4: Documentation | 4 | 0 | 0% |

### By Priority
| Priority | Tasks | Completed | Progress |
|----------|-------|-----------|----------|
| High | 14 | 6 | 43% |
| Medium | 8 | 0 | 0% |
| Low | 8 | 0 | 0% |

---

## Notes & Decisions

### Design Decisions

**2025-12-10**: Initial planning
- Removed duplicate features already implemented in codebase
- Prioritized per-persona memory isolation to prevent cross-contamination
- Chose semantic lorebook triggering over auto-population for better control

### Implementation Guidelines

1. **Always check existing code first** - Review codebase_summary docs before implementing
2. **Backwards compatibility required** - Existing characters must continue working
3. **Performance budgets**:
   - Per-message overhead: < 50ms
   - LLM calls: Use ThinkingService for quick decisions
   - Token budget: Respect ContextManager limits
4. **Testing requirements**:
   - Unit tests for all new systems
   - Integration tests with existing personas
   - Performance benchmarks

### Future Considerations

- **Voice Mood Modulation**: Adjust TTS speed/pitch based on mood (requires RVC integration)
- **Multi-User Conversations**: Group chat awareness and participation balancing
- **Scheduled Personality Events**: Time-based mood shifts (morning cheerful, night contemplative)
- **Dream Mode**: Offline persona thought generation and self-reflection

---

## Changelog

### 2025-12-10
- 🎉 Initial roadmap created
- ✅ De-duplicated features against existing codebase
- ✅ Organized into 4 phases
- ✅ Created 30-task implementation plan
- ✅ Added dependency graph

---

**Maintained by**: AI Development Team
**Review Cadence**: Weekly
**Next Review**: TBD after Phase 1 kickoff
