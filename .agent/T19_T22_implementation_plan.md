# T19-T22 Implementation Plan

**Features**: Dynamic Framework Blending (T19-T20) + Emotional Contagion (T21-T22)  
**Start Date**: 2025-12-11  
**Priority**: HIGH - Both are high-impact features  
**Estimated Time**: 3-4 hours total

---

## Implementation Order

### Phase 1: Emotional Contagion (T21-T22) - 1-2 hours
**Why First**: Lower complexity, immediate user impact, quick win

### Phase 2: Framework Blending (T19-T20) - 2-3 hours
**Why Second**: More complex, builds on existing persona system

---

## T21-T22: Emotional Contagion System

### 📋 Feature Description

The bot detects and adapts to the user's emotional state over time:
- User consistently sad → Bot becomes more empathetic and supportive
- User consistently happy → Bot becomes more energetic and enthusiastic
- User neutral → Bot maintains balanced tone

### 🎯 Implementation Steps

#### Step 1: Extend BehaviorState
**File**: `services/persona/behavior.py`

Add sentiment tracking:
```python
@dataclass
class BehaviorState:
    # ... existing fields ...
    
    # T21: Emotional Contagion
    sentiment_history: deque = field(default_factory=lambda: deque(maxlen=10))
    contagion_active: bool = False
    contagion_modifier: str = "neutral"  # empathetic, enthusiastic, balanced
```

#### Step 2: Track User Sentiment
**File**: `services/persona/behavior.py`

Add to `update_mood()` method:
```python
def update_mood(self, message_content: str, bot_response: str = ""):
    # ... existing mood update logic ...
    
    # T21: Track user sentiment for emotional contagion
    if message_content:
        sentiment = self._analyze_sentiment(message_content)
        state.sentiment_history.append(sentiment)
        
        # Update contagion if enough history
        if len(state.sentiment_history) >= 5:
            self._update_emotional_contagion(state)
```

#### Step 3: Calculate Contagion
**File**: `services/persona/behavior.py`

New method:
```python
def _update_emotional_contagion(self, state: BehaviorState):
    """Calculate emotional contagion based on user sentiment trends.
    
    T21: Emotional Contagion System
    - Analyzes last 10 user messages
    - Detects prolonged emotional states
    - Adjusts bot's emotional tone accordingly
    """
    avg_sentiment = sum(state.sentiment_history) / len(state.sentiment_history)
    
    if avg_sentiment < -0.3:  # Consistently negative
        state.contagion_active = True
        state.contagion_modifier = "empathetic"
    elif avg_sentiment > 0.3:  # Consistently positive
        state.contagion_active = True
        state.contagion_modifier = "enthusiastic"
    else:
        state.contagion_active = False
        state.contagion_modifier = "balanced"
```

#### Step 4: Apply Contagion to Prompts
**File**: `services/core/context.py`

Add contagion modifier to system prompt:
```python
def build_context(...):
    # ... existing context building ...
    
    # T21: Emotional Contagion modifier
    if behavior_state and behavior_state.contagion_active:
        contagion_text = self._get_contagion_prompt(behavior_state.contagion_modifier)
        system_prompt += f"\n\n{contagion_text}"
```

#### Step 5: Add Persona Config
**File**: `prompts/PERSONA_SCHEMA.md`

Document new fields:
```markdown
## Emotional Contagion (T21-T22)

emotional_contagion:
  enabled: true
  sensitivity: 0.7  # 0.0-1.0, how quickly to adapt
  threshold: 0.3    # Sentiment diff required to trigger
  modifiers:
    empathetic: "TONE: Be more gentle, supportive, and understanding."
    enthusiastic: "TONE: Be more energetic, positive, and engaging."
```

---

## T19-T20: Dynamic Framework Blending

### 📋 Feature Description

Allows personas to blend multiple behavioral frameworks based on context:
- Base framework: Neuro (analytical)
- Emotional support question → Blend 70% Caring framework
- Creative task → Blend 50% Chaotic framework
- Smooth, coherent personality transitions

### 🎯 Implementation Steps

#### Step 1: Create FrameworkBlender Service
**File**: `services/persona/framework_blender.py` (NEW)

```python
class FrameworkBlender:
    """Blends multiple persona frameworks based on context.
    
    T19: Dynamic Framework Blending
    - Detects context triggers (emotional_support, creative, analytical)
    - Merges framework prompts with weighting
    - Ensures coherent blended personalities
    """
    
    def detect_context(self, message: str) -> Optional[str]:
        """Detect context type from message."""
        
    def blend_frameworks(self, base: Framework, blend: Framework, weight: float) -> str:
        """Merge two framework prompts with weighting."""
```

#### Step 2: Add Blend Rules to Character Schema
**File**: `services/persona/system.py`

Extend Character dataclass:
```python
@dataclass
class Character:
    # ... existing fields ...
    
    # T19: Framework Blending
    framework_blending: Optional[Dict[str, Any]] = None
    # {
    #   "enabled": true,
    #   "base_framework": "neuro",
    #   "blend_rules": [
    #     {"context": "emotional_support", "framework": "caring", "weight": 0.7},
    #     {"context": "creative_task", "framework": "chaotic", "weight": 0.5}
    #   ]
    # }
```

#### Step 3: Modify Persona Compilation
**File**: `services/persona/system.py`

Update `compile_persona()`:
```python
def compile_persona(self, character_id: str, framework_id: str, ...):
    # ... existing compilation ...
    
    # T19: Check for framework blending
    if character.framework_blending and character.framework_blending.get("enabled"):
        # Store blend rules for runtime use
        compiled.blend_rules = character.framework_blending.get("blend_rules", [])
```

#### Step 4: Apply Blending at Runtime
**File**: `services/core/context.py`

Modify `build_context()`:
```python
def build_context(persona, ...):
    system_prompt = persona.system_prompt
    
    # T19: Apply framework blending if rules exist
    if hasattr(persona, 'blend_rules') and message_content:
        blender = FrameworkBlender()
        context = blender.detect_context(message_content)
        
        if context:
            for rule in persona.blend_rules:
                if rule['context'] == context:
                    blend_framework = self._load_framework(rule['framework'])
                    system_prompt = blender.blend_frameworks(
                        persona.framework,
                        blend_framework,
                        rule['weight']
                    )
                    break
```

#### Step 5: Document Schema
**File**: `prompts/PERSONA_SCHEMA.md`

Add framework blending docs:
```markdown
## Framework Blending (T19-T20)

framework_blending:
  enabled: true
  base_framework: "neuro"
  blend_rules:
    - context: "emotional_support"
      framework: "caring"
      weight: 0.7
      description: "Blend caring traits when user needs support"
    - context: "creative_task"
      framework: "chaotic"
      weight: 0.5
      description: "Add playful creativity for brainstorming"
```

---

## Test Plan

### T21-T22: Emotional Contagion Tests

```python
# Test 1: Negative Sentiment Contagion
user_messages = [
    "I'm feeling really sad today",
    "Nothing is going right",
    "I'm so frustrated",
    "This is terrible",
    "I can't handle this"
]
# Expected: Bot becomes empathetic after 5 messages

# Test 2: Positive Sentiment Contagion
user_messages = [
    "I'm so happy!",
    "This is amazing!",
    "Everything is great!",
    "Best day ever!",
    "I love this!"
]
# Expected: Bot becomes enthusiastic

# Test 3: Neutral/Mixed
user_messages = [
    "Hello",
    "How are you?",
    "What time is it?",
    "Tell me a fact",
    "Okay"
]
# Expected: Bot stays balanced
```

### T19-T20: Framework Blending Tests

```python
# Test 1: Emotional Support Trigger
message = "I'm going through a really tough time and need advice"
# Expected: Blend Caring framework (empathetic + analytical)

# Test 2: Creative Task Trigger
message = "Help me brainstorm crazy ideas for my project"
# Expected: Blend Chaotic framework (analytical + playful)

# Test 3: No Trigger
message = "What's 2+2?"
# Expected: Pure base framework (analytical only)
```

---

## Performance Targets

### T21-T22: Emotional Contagion
- Sentiment analysis: <1ms (using existing VADER)
- Contagion calculation: <0.1ms (simple average)
- Total overhead: <2ms per message

### T19-T20: Framework Blending
- Context detection: <5ms (keyword matching)
- Framework merging: <10ms (string interpolation)
- Total overhead: <15ms per message (only when blending active)

---

## Integration Points

### Files to Modify

**T21-T22 (Emotional Contagion)**:
1. `services/persona/behavior.py` - Add sentiment tracking and contagion logic
2. `services/core/context.py` - Apply contagion to prompts
3. `prompts/PERSONA_SCHEMA.md` - Document new fields

**T19-T20 (Framework Blending)**:
1. `services/persona/framework_blender.py` - NEW service
2. `services/persona/system.py` - Extend Character schema
3. `services/core/context.py` - Apply blending at runtime
4. `prompts/PERSONA_SCHEMA.md` - Document blend rules

---

## Success Criteria

### T21-T22 Complete When:
- [x] sentiment_history tracking implemented
- [x] Contagion calculation working
- [x] Prompt modifiers applied correctly
- [x] Tests pass (3 scenarios)
- [x] Performance <2ms overhead

### T19-T20 Complete When:
- [x] FrameworkBlender service created
- [x] Context detection working
- [x] Framework merging correct
- [x] Blend rules parseable from character JSON
- [x] Runtime blending functional
- [x] Tests pass (3 scenarios)
- [x] Performance <15ms overhead

---

## Timeline

**Total Estimated Time**: 3-4 hours

- **T21-T22 Implementation**: 1 hour
- **T21-T22 Testing**: 30 min
- **T19-T20 Implementation**: 1.5 hours
- **T19-T20 Testing**: 30 min
- **Integration Testing**: 30 min
- **Documentation**: 30 min

---

**Ready to Start**: YES  
**Next Action**: Implement T21-T22 first (quick win)
