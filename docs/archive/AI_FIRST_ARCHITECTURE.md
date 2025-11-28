# AI-First Architecture Proposal

## Current Problems
- **Hardcoded behaviors**: Event reactions, ambient messages, trigger words all hardcoded
- **Inflexible**: Changing personas requires code changes
- **Scattered logic**: Behavior rules spread across multiple files
- **Not AI-native**: LLM is used to fill templates, not make decisions

## New Architecture: Tool-Based AI-First Design

### Core Principle
**Give the LLM context and tools, let it decide when/how to act**

Instead of:
```python
if random.random() < 0.1:  # Hardcoded chance
    await send("Hardcoded message")  # Hardcoded response
```

Do:
```python
# LLM receives context, decides if/how to respond
context = {
    "user_activity": "started playing Fortnite",
    "conversation_active": True,
    "user_profile": {...}
}
response = await llm.decide_action(context, tools)
```

---

## Architecture Components

### 1. **Context Provider System**
Gather all relevant context for the LLM to make informed decisions.

**Context Types:**
- **User Context**: Profile, conversation history, current activity
- **Server Context**: Active users, voice states, recent messages
- **Bot State**: Current mood, recent actions, cooldowns
- **Temporal Context**: Time of day, day of week

**Implementation:**
```python
class ContextProvider:
    async def get_context(self, event_type: str, **kwargs) -> Dict:
        """Gather all relevant context for an event."""
        return {
            "user": await self.get_user_context(kwargs.get('user_id')),
            "server": await self.get_server_context(kwargs.get('guild_id')),
            "bot_state": self.get_bot_state(),
            "temporal": self.get_temporal_context(),
            "event": {
                "type": event_type,
                "data": kwargs
            }
        }
```

### 2. **Tool Registry** (Expand Existing)
Tools the LLM can use to gather info and take actions.

**Query Tools** (Read-only):
- `get_user_info(user_id)` - Profile, affection, preferences
- `get_conversation_state(channel_id)` - Active conversation?
- `get_recent_messages(channel_id, limit)` - Context
- `check_cooldown(action_type)` - Prevent spam
- `get_voice_state(user_id)` - Voice channel info
- `search_memory(query)` - RAG for relevant past interactions

**Action Tools** (Write operations):
- `send_message(channel_id, content)` - Send a message
- `react_with_emoji(message_id, emoji)` - Add reaction
- `set_cooldown(action_type, seconds)` - Rate limiting
- `log_interaction(type, data)` - Track behaviors

**Decision Tools** (Help LLM decide):
- `should_react(context)` - Helper for decision-making
- `get_persona_guidance(situation)` - Persona-specific hints

### 3. **Event Handler with LLM Decision Layer**

Instead of hardcoded reactions, ask the LLM:

```python
async def on_presence_update(before, after):
    """User changed game/activity."""

    # Gather context
    context = await context_provider.get_context(
        event_type="presence_update",
        user_id=after.id,
        before_activity=before.activity,
        after_activity=after.activity
    )

    # Ask LLM: Should I react? How?
    decision = await llm.decide(
        system_prompt=persona.system_prompt,
        context=context,
        tools=tool_registry.get_tools(),
        decision_prompt="""
        A user's activity just changed. Based on the context:

        1. Should you react to this? Consider:
           - Are you in an active conversation with this user?
           - Have you commented on this recently (check cooldown)?
           - Is this activity interesting/relevant to your persona?

        2. If yes, how should you react?
           - Use tools to check state and send messages
           - Be natural and in-character
           - Don't force reactions

        Think step by step, then take action (or don't).
        """
    )

    # LLM executes tools (or does nothing)
    await tool_executor.execute(decision.tool_calls)
```

### 4. **Structured Output for Reliability**

To prevent hallucinations, use structured output:

```python
class ReactionDecision(BaseModel):
    """Structured decision format."""
    should_react: bool
    reasoning: str  # Chain of thought
    action: Optional[str]  # None, "message", "emoji", "ignore"
    message_content: Optional[str]
    cooldown_seconds: int = 300

# LLM returns structured decision
decision = await llm.decide_structured(
    context=context,
    output_schema=ReactionDecision
)
```

### 5. **Persona as System Context, Not Hardcoded Responses**

Instead of hardcoded trigger reactions, the persona provides:

```json
{
  "name": "Dagoth Ur",
  "personality_traits": [
    "Sarcastic and condescending",
    "Divine superiority complex",
    "References Morrowind lore",
    "Judges mortals harshly but with wit"
  ],
  "interaction_guidelines": {
    "when_to_react": [
      "User you're talking with changes activity",
      "Interesting topics related to games/culture",
      "Direct questions or mentions"
    ],
    "reaction_style": [
      "Witty and biting observations",
      "Connect to Morrowind/fantasy themes when possible",
      "Show amusement at mortal behavior",
      "Don't force reactions - silence is powerful"
    ]
  },
  "tools_usage": {
    "preferred_tools": ["get_user_info", "search_memory"],
    "avoid_spam": "Always check cooldowns before reacting"
  }
}
```

The LLM reads this and embodies it naturally, not matching hardcoded strings.

---

## Model Selection (Under 8GB)

**Recommended Models:**

1. **Qwen2.5-7B-Instruct** (Best overall)
   - 7B params, ~4.5GB VRAM (Q4)
   - Excellent instruction following
   - Good tool use
   - Strong reasoning

2. **Llama-3.2-3B-Instruct** (Lightweight)
   - 3B params, ~2GB VRAM (Q4)
   - Fast inference
   - Good for simpler decisions
   - Tool calling support

3. **Hermes-3-Llama-3.1-8B** (Advanced tool use)
   - 8B params, ~5GB VRAM (Q4)
   - Excellent function calling
   - Strong reasoning
   - Good persona adherence

4. **Phi-3.5-Mini-Instruct** (Efficient)
   - 3.8B params, ~2.5GB VRAM (Q4)
   - Surprisingly capable
   - Fast
   - Good for constrained generation

**Configuration:**
- Use Q4_K_M quantization for efficiency
- Enable structured output/grammar constraints
- Tune temperature: 0.7-0.9 for decisions, 1.0-1.2 for creative responses

---

## Migration Strategy

### Phase 1: Add Tools (Non-breaking)
1. Expand tool registry with query/action tools
2. Add context provider system
3. Test tools work correctly

### Phase 2: Parallel System (A/B test)
1. Create AI-first event handler alongside old one
2. Use config flag to switch: `AI_FIRST_MODE=true`
3. Test and tune prompts

### Phase 3: Replace Hardcoded Logic
1. Remove hardcoded reactions from event_listeners.py
2. Remove hardcoded triggers from naturalness_enhancer.py
3. Convert to context-based prompts

### Phase 4: Optimize
1. Profile LLM call frequency
2. Add intelligent caching
3. Batch decisions when possible
4. Fine-tune prompts for efficiency

---

## Benefits

✅ **Flexible**: Change personas without code changes
✅ **Natural**: LLM makes context-aware decisions
✅ **Maintainable**: Less hardcoded logic
✅ **Extensible**: Add tools, don't edit core logic
✅ **Reliable**: Structured output prevents hallucinations
✅ **Efficient**: Models under 8GB, smart caching

---

## Example: AI-First Activity Reaction

**Before (Hardcoded):**
```python
if random.random() < 0.1 and "fortnite" in activity.lower():
    await channel.send("Fortnite? Really? That's what we're doing now?")
```

**After (AI-First):**
```python
context = await provider.get_context(
    event_type="activity_change",
    user_id=user.id,
    activity=activity.name
)

decision = await llm.decide_structured(
    system=persona.system_prompt,
    context=context,
    tools=tool_registry,
    schema=ReactionDecision
)

if decision.should_react:
    await tools.execute(decision.tool_calls)
```

The LLM sees:
- User is in active conversation ✓
- No recent cooldown ✓
- Activity: "Fortnite"
- Persona: Sarcastic god who judges mortals

LLM decides: "Yes, make a witty comment" and generates appropriate response in-character.

---

## Questions to Consider

1. **Latency**: LLM calls add latency (~500ms-2s). Is this acceptable for reactions?
   - Mitigation: Use smaller models (3-7B), batch decisions, cache common patterns

2. **Cost**: More LLM calls = more compute. How to balance?
   - Mitigation: Smart filtering (only call LLM for "interesting" events), cooldowns

3. **Consistency**: Will responses vary too much?
   - Mitigation: Structured output, persona guidelines, temperature tuning

4. **Debugging**: Harder to debug AI decisions than hardcoded logic.
   - Mitigation: Extensive logging, reasoning traces, A/B testing

---

## Next Steps

1. **Prototype**: Build minimal context provider + decision layer
2. **Test**: Single event type (e.g., activity changes) with AI-first approach
3. **Measure**: Latency, response quality, resource usage
4. **Iterate**: Tune prompts, model selection, caching
5. **Expand**: Roll out to more event types

Would you like me to start implementing this architecture?
