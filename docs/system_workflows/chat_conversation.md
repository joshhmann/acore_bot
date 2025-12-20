# Chat Conversation System Workflow

This document describes the complete chat conversation system in acore_bot, from message processing through response delivery and post-processing.

## Overview

The chat conversation system is the **core interaction loop** of the bot, handling AI-powered conversations with multiple personas, context management, and intelligent response generation.

## Architecture

### Component Structure
```
cogs/chat/
├── main.py              # Core ChatCog class and message routing
├── commands.py          # Slash command handlers
├── message_handler.py   # Message processing and trigger logic
├── helpers.py           # Text processing utilities
├── session_manager.py   # Conversation session tracking
└── voice_integration.py # TTS response integration
```

### Service Dependencies
```
Services Used:
├── OllamaService (LLM generation)
├── PersonaSystem (Character management)
├── PersonaRouter (Multi-character selection)
├── ContextRouter (Smart context retrieval)
├── ContextManager (Token-aware context building)
├── BehaviorEngine (Autonomous behaviors)
├── UserProfileService (User learning)
├── RAGService (Knowledge retrieval)
├── WebSearchService (Real-time search)
├── LorebookService (Context injection)
├── ConversationSummarizer (Long-term memory)
├── MetricsService (Performance tracking)
└── VoiceIntegration (TTS responses)
```

## Message Processing Flow

### 1. Entry Point
```python
# main.py:on_message()
async def on_message(self, message):
    # Process commands first
    await self.process_commands(message)

    # Hand off to ChatCog for natural conversation
    chat_cog = self.get_cog("ChatCog")
    if chat_cog:
        await chat_cog.check_and_handle_message(message)
```

### 2. Message Handler Pipeline
**File**: `cogs/chat/message_handler.py:191-562`

#### 2.1 Filtering Stage
```python
# Basic Filters
if message.author == bot.user: return False
if bot_muted: return False
if message.author.bot and not is_persona_message: return False
if message.content.startswith(bot.command_prefix): return False
if "#ignore" in message.content.lower(): return False

# Duplicate Prevention
if message_key in processed_messages: return True

# Loop Prevention (Persona Interactions)
if is_persona_message:
    if persona_name == author_name: return False  # Self-reply prevention
    if random.random() > 0.5: return False  # 50% decay
```

#### 2.2 Trigger Detection (Priority Order)
```python
# Priority 1: Direct Mention
if bot.user in message.mentions:
    should_respond = True
    response_reason = "mentioned"

# Priority 2: Reply to Bot
elif message.reference and ref_msg.author == bot.user:
    should_respond = True
    response_reason = "reply_to_bot"

# Priority 3: Name Trigger
elif any(name in message.content.lower() for name in bot_names):
    should_respond = True
    response_reason = "name_trigger"

# Priority 4: Image Question
elif "what is this" in content and (message.attachments or recent_image):
    should_respond = True
    response_reason = "image_question"

# Priority 5: Behavior Engine (AI-driven)
elif behavior_engine.handle_message(message):
    should_respond = True
    response_reason = "behavior_engine:curiosity"

# Priority 6: Conversation Context
elif last_response_within_5_minutes:
    should_respond = True
    response_reason = "conversation_context"

# Priority 7: Ambient Channels
elif channel_id in Config.AMBIENT_CHANNELS:
    if random.random() < Config.GLOBAL_RESPONSE_CHANCE:
        should_respond = True
        response_reason = "ambient_channel"
```

### 3. Response Generation Pipeline

#### 3.1 Persona Selection
```python
# For banter responses, pick DIFFERENT persona
if response_reason == "persona_banter":
    other_personas = [p for p in all_personas if p.character.display_name != speaker_name]
    selected_persona = random.choice(other_personas)
else:
    # Default routing based on content and channel stickiness
    selected_persona = persona_router.select_persona(message_content, channel_id)
```

#### 3.2 Context Building
```python
async def _prepare_final_messages():
    # 1. Load history via ContextRouter
    context_result = await context_router.get_context(channel, user, message_content)
    history = context_result.history
    context_summary = context_result.summary

    # 2. Build context strings
    user_context_str = ""

    # User Profile (learning and affection)
    if user_profiles:
        user_context = await user_profiles.get_user_context(user_id)
        affection = user_profiles.get_affection_context(user_id)
        user_context_str += f"User Profile: {user_context}\nRelationship: {affection}"

    # Memory Summarizer (long-term context)
    if summarizer:
        memory = await summarizer.build_memory_context(message_content)
        user_context_str += f"\n\nMemories:\n{memory}"

    # Conversation Summary
    if context_summary:
        user_context_str += f"\n\n[Earlier Conversation Summary]:\n{context_summary}"

    # RAG Context (persona-filtered)
    persona_categories = None
    if selected_persona and hasattr(selected_persona.character, 'knowledge_domain'):
        cats = selected_persona.character.knowledge_domain.get('rag_categories')
        if isinstance(cats, list) and cats:
            persona_categories = cats
        rag_content = rag.get_context(message_content, categories=persona_categories)

    # Web Search (if triggered)
    if web_search.should_search(message_content):
        search_results = await web_search.get_context(message_content)
        rag_context_str += f"\n\n[WEB SEARCH RESULTS]\n{search_results}"

    # Lorebook (keyword-triggered)
    lore_entries = lorebook_service.scan_for_triggers(scan_text, active_lorebooks)

    # 3. Build final messages using ContextManager
    final_messages = await context_manager.build_context(
        persona=selected_persona,
        history=history,
        model_name=current_model,
        lore_entries=lore_entries,
        rag_content=rag_context_str,
        user_context=user_context_str,
        llm_service=ollama
    )
```

#### 3.3 LLM Generation
```python
# Vision Processing
if recent_image_url and Config.VISION_ENABLED:
    response = await ollama.chat(final_messages, temperature=temperature)
    return response

# Agentic Tools (ReAct loop)
if agentic_tools:
    response = await agentic_tools.process_with_tools(
        llm_generate_func=llm_chat,
        user_message=message_content,
        system_prompt=system_prompt,
        max_iterations=3
    )

# Streaming with TTS
if Config.RESPONSE_STREAMING_ENABLED:
    if voice_client and AUTO_REPLY_WITH_VOICE:
        # Parallel streaming: Text to Discord + Audio to Voice
        llm_stream = ollama.chat_stream(final_messages)
        multiplexer = StreamMultiplexer(llm_stream)
        text_stream = multiplexer.create_consumer()
        tts_stream = multiplexer.create_consumer()

        results = await asyncio.gather(
            _stream_to_discord(text_stream, interaction, guild),
            streaming_tts.process_stream(tts_stream, voice_client, speed=kokoro_speed)
        )
        return results[0]

    # Standard non-streaming
else:
    response = await ollama.chat(final_messages, max_tokens=max_tokens)
    return response
```

#### 3.4 Response Delivery
```python
# 1. Clean response for Discord
discord_response, tts_response = _prepare_response_content(response, channel)

# 2. Send via Webhook (Persona spoofing)
if isinstance(channel, discord.TextChannel):
    webhooks = await channel.webhooks()
    webhook = next((w for w in webhooks if w.name == "PersonaBot_Proxy"), None)
    if not webhook:
        webhook = await channel.create_webhook(name="PersonaBot_Proxy")

    await webhook.send(
        content=discord_response,
        username=selected_persona.character.display_name,
        avatar_url=selected_persona.character.avatar_url
    )
else:
    # Fallback: Standard message with prefix
    await channel.send(f"**[{display_name}]**: {discord_response}")
```

#### 3.5 Post-Response Actions
```python
# 1. Sticky Persona Tracking
persona_router.record_response(channel_id, selected_persona)

# 2. Persona Relationships (inter-persona affinity)
if original_message.webhook_id:  # Persona-to-persona interaction
    await persona_relationships.record_interaction(
        speaker=speaker_name,
        responder=responder_name,
        affinity_change=2
    )

# 3. Voice Reply (environmental TTS)
if Config.AUTO_REPLY_WITH_VOICE and voice_client.is_connected():
    await voice_integration.speak_response_in_voice(guild, tts_response)

# 4. Metrics Recording
bot.metrics.record_response_time(duration_ms)
bot.metrics.record_message(user_id, channel_id)

# 5. Background Learning (user profiles)
if not is_webhook_message:
    _create_background_task(
        user_profiles.learn_from_conversation(user_id, username, user_message, bot_response)
    )

    _create_background_task(
        user_profiles.update_affection(user_id, message, bot_response)
    )
```

## Key Features

### 1. Multi-Character Support
- **Persona Router**: Intelligent character selection based on mentions, context, and relationships
- **Sticky Context**: Remembers last responder per channel (5-minute window)
- **Inter-Persona Dynamics**: Characters can interact with each other with relationship tracking
- **Banter System**: Affinity-based probability for character conversations

### 2. Advanced Context Management
- **Smart Context Router**: Combines conversation history and summaries for efficient long conversations
- **Persona-Filtered RAG**: Characters only access relevant knowledge domains
- **Dynamic Lorebook**: Keyword-triggered world information injection
- **Real-Time Web Search**: Integrated search for current information

### 3. Intelligent Behavior
- **Emotional Contagion**: Bot adapts tone based on user sentiment and relationship levels
- **Proactive Engagement**: AI-driven decisions to jump into conversations
- **Ambient Mode**: Anti-spam AI evaluation before speaking in lulls
- **Reaction System**: Natural emoji reactions to messages

### 4. Streaming and Voice Integration
- **Response Streaming**: Real-time text updates during generation
- **Parallel TTS**: Simultaneous audio generation while text streams
- **Voice Activity Detection**: Automatic transcription and response triggers

## Configuration

### Core Settings
```bash
# Chat Configuration
CHAT_HISTORY_ENABLED=true                    # Enable conversation memory
CONTEXT_MESSAGE_LIMIT=20                         # Messages in history
MAX_CONTEXT_TOKENS=8192                         # LLM context window
RESPONSE_STREAMING_ENABLED=true                  # Real-time updates
AUTO_REPLY_WITH_VOICE=true                        # Voice responses

# Context Features
USER_CONTEXT_IN_CHAT=true                        # Include user profiles
USER_PROFILES_AUTO_LEARN=true                   # AI learning from conversations
RAG_IN_CHAT=true                                # Knowledge retrieval
CONVERSATION_SUMMARIZATION_ENABLED=true        # Long-term memory

# Persona System
USE_PERSONA_SYSTEM=true                           # Multi-character support
ACTIVE_PERSONAS=["dagoth_ur.json", ...]       # Available characters

# Behavioral Settings
NATURALNESS_ENABLED=true                            # Human-like behaviors
REACTIONS_ENABLED=true                               # Emoji reactions
PROACTIVE_ENGAGEMENT_ENABLED=true                # Proactive conversations
```

## Performance Considerations

### 1. Response Time Optimization
- **Request Deduplication**: Identical concurrent requests share results
- **LLM Caching**: Frequently used responses cached with TTL
- **Smart Token Management**: Dynamic token limits based on model and context

### 2. Memory Efficiency
- **LRU Caches**: History and context management with bounded size
- **Background Cleanup**: Automatic cleanup of old data and temp files
- **Batch Operations**: Message batching for efficiency

### 3. Concurrency Handling
- **Rate Limiting**: Prevents API abuse and resource exhaustion
- **Task Management**: Proper tracking and cleanup of background tasks
- **Lock-Free Design**: Minimizes blocking operations

## Troubleshooting

### Common Issues
1. **Bot Not Responding**: Check if message meets trigger conditions
2. **Slow Responses**: Monitor LLM response times and check service health
3. **Persona Not Switching**: Verify character files are valid and loaded
4. **Voice Issues**: Check TTS engine configuration and voice client connections
5. **Context Loss**: Monitor history cache hit rates and summarizer effectiveness

### Debug Commands
```bash
/chat status                    # Show conversation system status
/botstatus                     # Overall bot status and metrics
/metrics                       # Performance metrics
/logs                          # Recent log entries
```

## Integration Points

### With Voice System
- **Voice Activity Detection**: Automatic transcription and response
- **TTS Responses**: Text-to-speech with personality-appropriate voice
- **Music Integration**: Can play music while handling conversations

### With User Management
- **Profile Learning**: Conversations automatically analyzed for user preferences
- **Relationship Tracking**: Affective levels influence character interactions
- **Memory Recall**: Past conversations searchable for context

### With Monitoring System
- **Performance Metrics**: All interactions tracked and analyzed
- **Health Checks**: Service health monitored in real-time
- **Error Tracking**: Issues automatically logged and categorized

---

## Files Reference

| File | Purpose | Key Functions |
|-------|---------|------------------|
| `cogs/chat/main.py` | Core ChatCog class and message routing |
| `cogs/chat/message_handler.py` | Message filtering and trigger logic |
| `cogs/chat/commands.py` | Slash command implementations |
| `cogs/chat/helpers.py` | Text processing utilities |
| `cogs/chat/session_manager.py` | Conversation session tracking |
| `cogs/chat/voice_integration.py` | TTS response integration |
| `services/persona/router.py` | Multi-character selection |
| `services/memory/context_router.py` | Smart context retrieval |
| `services/core/context.py` | Token-aware context building |

---

**Last Updated**: 2025-12-16
**Version**: 1.0