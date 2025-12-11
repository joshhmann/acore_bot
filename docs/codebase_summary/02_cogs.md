# Discord Cogs Architecture

This document provides a comprehensive overview of all Discord cogs in the acore_bot project, their architecture, interactions, and command flows.

## Table of Contents

1. [Overview](#overview)
2. [ChatCog - Main Conversation Handler](#chatcog)
3. [VoiceCog - TTS & Voice Features](#voicecog)
4. [CharacterCommandsCog - Persona Management](#charactercommandscog)
5. [MusicCog - YouTube Playback](#musiccog)
6. [RemindersCog - Time-Based Reminders](#reminderscog)
7. [NotesCog - User Notes](#notescog)
8. [HelpCog - Interactive Help](#helpcog)
9. [SystemCog - Bot Status & Metrics](#systemcog)
10. [Event Flow Diagrams](#event-flow-diagrams)

---

## Overview

The bot uses Discord.py's **Cog system** to modularize functionality. Each cog is responsible for a specific domain:

- **ChatCog**: AI-powered conversations, context management, persona routing
- **VoiceCog**: Text-to-speech, voice channel management, RVC voice conversion
- **CharacterCommandsCog**: Multi-character persona switching and interaction
- **MusicCog**: YouTube music playback
- **RemindersCog**: Scheduled reminders
- **NotesCog**: User note storage
- **HelpCog**: Interactive help system
- **SystemCog**: Bot health, metrics, logging

All cogs are loaded dynamically in `/root/acore_bot/main.py` during bot initialization.

---

## ChatCog

**Location**: `/root/acore_bot/cogs/chat/main.py`

**Purpose**: Handles all AI-powered conversations with advanced context management, persona routing, and multi-channel support.

### Architecture

ChatCog is **modularized into 6 files**:

```
cogs/chat/
├── main.py              # Core ChatCog class, initialization, message routing
├── commands.py          # Slash command handlers (/chat, /ambient, /end_session)
├── message_handler.py   # on_message event processing, trigger logic
├── helpers.py           # Text processing utilities
├── session_manager.py   # Conversation session tracking
└── voice_integration.py # TTS response integration
```

### Key Components

#### 1. ChatCog Class (`main.py`)

**Initialization Flow** (lines 54-164):
- Synchronous `__init__`: Sets up basic properties, creates async init task
- Asynchronous `_async_init`: Initializes services (ContextManager, BehaviorEngine, PersonaRouter)
- Loads default persona (Dagoth Ur) and starts BehaviorEngine background task

**Core Services**:
- `self.ollama`: LLM service (OllamaService or OpenRouter)
- `self.history`: Chat history manager
- `self.context_router`: Smart context retrieval (history + summary)
- `self.context_manager`: Builds optimized LLM context
- `self.behavior_engine`: AI-driven reactions, proactive engagement, mood
- `self.persona_router`: Multi-character persona selection
- `self.lorebook_service`: Lorebook entries for context enhancement
- `self.user_profiles`: User memory & affection tracking
- `self.rag`: RAG knowledge base integration
- `self.web_search`: Real-time web search

#### 2. Message Handling Flow

**Entry Point**: `check_and_handle_message(message)` (line 595)
- Delegates to `MessageHandler.check_and_handle_message()`

**MessageHandler Logic** (`message_handler.py`, lines 191-562):

```python
# 1. FILTERING
if message.author == bot.user: return False  # Ignore self
if bot_muted: return False  # Global mute
if message.author.bot and not is_persona_message: return False  # Ignore bots
if message.content.startswith(bot.command_prefix): return False  # Ignore prefix commands
if "#ignore" in message.content.lower(): return False  # Manual ignore

# 2. DUPLICATE PREVENTION
if message_key in processed_messages: return True  # Already handled

# 3. LOOP PREVENTION (Persona Interactions)
if is_persona_message:
    if persona_name == author_name: return False  # Self-reply prevention
    if random.random() > 0.5: return False  # 50% decay to prevent loops

# 4. TRIGGER DETECTION
should_respond = False

# Priority 1: Direct mention
if bot.user in message.mentions:
    should_respond = True
    response_reason = "mentioned"

# Priority 2: Reply to bot
elif message.reference and ref_msg.author == bot.user:
    should_respond = True
    response_reason = "reply_to_bot"

# Priority 3: Name trigger (any persona name)
elif any(name in message.content.lower() for name in bot_names):
    should_respond = True
    response_reason = "name_trigger"

# Priority 4: Image question
elif "what is this" in content and (message.attachments or recent_image):
    should_respond = True
    response_reason = "image_question"

# Priority 5: Behavior Engine (AI-driven decision)
elif behavior_engine.handle_message(message):
    should_respond = True
    response_reason = "behavior_engine:curiosity"

# Priority 6: Conversation context (recent activity)
elif last_response_within_5_minutes:
    if is_persona_message:
        # Affinity-based banter chance (5% base, higher for close personas)
        banter_chance = persona_relationships.get_banter_chance(current, speaker)
        if random.random() < banter_chance:
            should_respond = True
            response_reason = "persona_banter"
    else:
        should_respond = True
        response_reason = "conversation_context"

# Priority 7: Ambient channels (random chance)
elif channel_id in Config.AMBIENT_CHANNELS:
    if random.random() < Config.GLOBAL_RESPONSE_CHANCE:
        should_respond = True
        response_reason = "ambient_channel"
```

#### 3. Response Generation Flow

**Core Method**: `_handle_chat_response()` (lines 599-1040)

**Step 1: Persona Selection** (lines 556-593):
```python
# For BANTER responses, pick a DIFFERENT persona
if response_reason == "persona_banter":
    other_personas = [p for p in all_personas if p.character.display_name != speaker_name]
    selected_persona = random.choice(other_personas)
else:
    # Default: Route based on message content and channel stickiness
    selected_persona = persona_router.select_persona(message_content, channel_id)
```

**Step 2: Context Building** (lines 407-553):
```python
async def _prepare_final_messages():
    # 1. Load history (via ContextRouter)
    context_result = await context_router.get_context(channel, user, message_content)
    history = context_result.history
    context_summary = context_result.summary

    # 2. Build context strings
    user_context_str = ""

    # User Profile
    if user_profiles:
        user_context = await user_profiles.get_user_context(user_id)
        affection = user_profiles.get_affection_context(user_id)
        user_context_str += f"User Profile: {user_context}\nRelationship: {affection}"

    # Memory Summarizer
    if summarizer:
        memory = await summarizer.build_memory_context(message_content)
        user_context_str += f"\n\nMemories:\n{memory}"

    # Conversation Summary
    if context_summary:
        user_context_str += f"\n\n[Earlier Conversation Summary]:\n{context_summary}"

    # RAG Context - **UPDATED 2025-12-10** with persona filtering
    persona_categories = None
    if selected_persona and hasattr(selected_persona.character, 'knowledge_domain'):
        cats = selected_persona.character.knowledge_domain.get('rag_categories')
        # Validate rag_categories must be a list
        if isinstance(cats, list) and cats:
            persona_categories = cats
        elif cats:
            logger.warning(f"Invalid rag_categories type: {type(cats)}. Expected list.")
        rag_content = rag.get_context(message_content, categories=persona_categories)
        rag_context_str = rag_content

    # Web Search
    if web_search.should_search(message_content):
        search_results = await web_search.get_context(message_content)
        rag_context_str += f"\n\n[WEB SEARCH RESULTS]\n{search_results}"

    # Lorebook
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

    return final_messages
```

**Step 3: LLM Generation** (lines 262-345):
```python
async def _generate_response(final_messages, channel, interaction, max_tokens, recent_image_url):
    # 1. Vision Processing (if image attached)
    if recent_image_url and Config.VISION_ENABLED:
        response = await ollama.chat(final_messages, temperature=temperature)
        return response

    # 2. Agentic Tools (ReAct loop with tool calling)
    if agentic_tools:
        response = await agentic_tools.process_with_tools(
            llm_generate_func=llm_chat,
            user_message=message_content,
            system_prompt=system_prompt,
            max_iterations=3
        )
        return response

    # 3. Streaming with TTS
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
        else:
            # Standard text streaming
            stream = ollama.chat_stream(final_messages)
            response = await _stream_to_discord(stream, interaction, guild)
            return response

    # 4. Standard non-streaming
    response = await ollama.chat(final_messages, max_tokens=max_tokens)
    return response
```

**Step 4: Response Delivery** (lines 1006-1039):
```python
# 1. Clean response
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

# 3. Record Interaction (metrics, learning, voice)
await _record_interaction(user, channel, message_content, response, start_time, original_message, selected_persona)
```

**Step 5: Post-Response Actions** (lines 1093-1139):
```python
async def _record_interaction():
    # 1. Sticky Persona Tracking (remember last persona per channel)
    persona_router.record_response(channel_id, selected_persona)

    # 2. Persona Relationships (banter affinity)
    if original_message.webhook_id:  # Persona-to-persona interaction
        await persona_relationships.record_interaction(
            speaker=speaker_name,
            responder=responder_name,
            affinity_change=2
        )

    # 3. Voice Reply (environmental TTS)
    if Config.AUTO_REPLY_WITH_VOICE and voice_client.is_connected():
        await voice_integration.speak_response_in_voice(guild, tts_response)

    # 4. Metrics
    bot.metrics.record_response_time(duration_ms)
    bot.metrics.record_message(user_id, channel_id)

    # 5. User Profile Learning (background task)
    if not is_webhook_message:  # Skip for persona messages
        _create_background_task(
            user_profiles.learn_from_conversation(user_id, username, user_message, bot_response)
        )

        # Affection update
        _create_background_task(
            user_profiles.update_affection(user_id, message, bot_response)
        )
```

### Slash Commands

#### `/chat <message>` (`commands.py`, lines 16-23)
- Directly invokes `_handle_chat_response()` with interaction context
- Skips message filtering (always responds)
- Shows "thinking..." indicator

#### `/ambient <action>` (`commands.py`, lines 25-88)
- **Status**: Shows BehaviorEngine state (running, channels, trigger chance)
- **Enable**: Starts BehaviorEngine background task
- **Disable**: Stops BehaviorEngine

#### `/end_session` (`commands.py`, lines 90-113)
- Ends conversation session for the channel
- Clears chat history
- Forces new context window on next message

### Helper Utilities

#### ChatHelpers (`helpers.py`)

```python
# Mention Processing
replace_mentions_with_names(content, message, bot_user_id)  # <@123> -> @Username (for LLM)
restore_mentions(content, guild)                             # @Username -> <@123> (for Discord)
clean_for_tts(content, guild)                                # <@123> -> Username (for TTS)

# Response Cleaning
clean_response(content)  # Remove <think> tags, prevent @everyone pings
clean_for_history(content)  # Remove TOOL: lines for history storage

# Sentiment Analysis
analyze_sentiment(text)  # Returns {"compound": 0.0, "pos": 0, "neg": 0, "neu": 1.0}

# Token Calculation
calculate_max_tokens(messages, model_name)  # Dynamic max_tokens based on context
```

#### SessionManager (`session_manager.py`)

**Purpose**: Track conversation sessions to maintain context continuity

```python
async def start_session(channel_id, user_id)  # Start/refresh session
async def refresh_session(channel_id)         # Update last_activity timestamp
async def is_session_active(channel_id)       # Check if session exists & not timed out
async def end_session(channel_id)             # Manually end session
def update_response_time(channel_id)          # Track last bot response
def get_last_response_time(channel_id)        # Check recent activity
```

**Session Timeout**: `Config.CONVERSATION_TIMEOUT` (default: 10 minutes)

#### VoiceIntegration (`voice_integration.py`)

**Purpose**: Handle TTS responses when bot is in voice channel

```python
async def speak_response_in_voice(guild, text):
    # 1. Check if bot is connected to voice
    voice_client = guild.voice_client
    if not voice_client or not voice_client.is_connected(): return

    # 2. Don't interrupt existing playback
    if voice_client.is_playing(): return

    # 3. Analyze sentiment for voice modulation
    sentiment = analyze_sentiment(text)
    kokoro_speed = 1.1 if sentiment == "positive" else 0.9 if sentiment == "negative" else 1.0

    # 4. Generate TTS
    audio_file = await voice_cog.tts.generate(text, speed=kokoro_speed)

    # 5. Apply RVC (voice conversion)
    if voice_cog.rvc and Config.RVC_ENABLED:
        audio_file = await voice_cog.rvc.convert(audio_file, model_name=Config.DEFAULT_RVC_MODEL)

    # 6. Play audio
    audio_source = discord.FFmpegPCMAudio(str(audio_file), options="...")
    voice_client.play(audio_source, after=cleanup_callback)
```

### Configuration

**Environment Variables** (`.env`):
```bash
# Core Settings
CHAT_HISTORY_ENABLED=true
CONVERSATION_TIMEOUT=600  # 10 minutes
RESPONSE_STREAMING_ENABLED=true
STREAM_UPDATE_INTERVAL=2.0  # Update every 2 seconds

# Context Features
USER_CONTEXT_IN_CHAT=true
USER_PROFILES_AUTO_LEARN=true
USER_AFFECTION_ENABLED=true
RAG_IN_CHAT=true

# Ambient Mode
AMBIENT_CHANNELS=[123456789]  # List of always-respond channels
GLOBAL_RESPONSE_CHANCE=0.166  # 1/6 chance in ambient channels

# Voice
AUTO_REPLY_WITH_VOICE=true
VISION_ENABLED=true  # Image analysis
```

---

## VoiceCog

**Location**: `/root/acore_bot/cogs/voice/main.py`

**Purpose**: Text-to-speech, voice channel management, RVC voice conversion, and smart listening (Whisper STT).

### Architecture

```
cogs/voice/
├── main.py      # Core VoiceCog class, TTS integration
├── commands.py  # Slash command handlers
└── manager.py   # Voice client management
```

### Key Features

#### 1. TTS Engines

**Supported Engines** (`Config.TTS_ENGINE`):
- **kokoro**: Local Kokoro TTS (high-quality, multi-voice)
- **kokoro_api**: Kokoro via API
- **supertonic**: Supertonic TTS
- **edge**: Microsoft Edge TTS (fallback)

**Voice Selection**:
- 11+ pre-defined voices (am_adam, af_bella, bf_emma, etc.)
- Configurable speed, pitch, rate
- Per-character voice settings (via persona `legacy_config.voice`)

#### 2. RVC (Retrieval-based Voice Conversion)

**Purpose**: Convert TTS output to match a target voice (e.g., game character)

**Service**: `UnifiedRVCService` (`services/voice/rvc.py`)

```python
# Configuration
Config.RVC_ENABLED = true
Config.DEFAULT_RVC_MODEL = "dagoth_ur.pth"
Config.RVC_PITCH_SHIFT = 0
Config.RVC_INDEX_RATE = 0.5
Config.RVC_PROTECT = 0.33

# Usage
audio_file = await tts.generate(text, audio_file)
if rvc.is_enabled():
    rvc_file = await rvc.convert(
        input_file=audio_file,
        output_file=rvc_file,
        model_name=Config.DEFAULT_RVC_MODEL,
        pitch_shift=Config.RVC_PITCH_SHIFT,
        index_rate=Config.RVC_INDEX_RATE,
        protect=Config.RVC_PROTECT
    )
    audio_file = rvc_file  # Use converted audio
```

**Models Location**: `data/voice_models/*.pth`

#### 3. Smart Listening (Whisper STT)

**Service**: `EnhancedVoiceListener` (`services/voice/listener.py`)

**Features**:
- **Automatic silence detection**: Transcribes after 2 seconds of silence
- **Smart response triggers**: Detects questions, bot mentions, commands
- **Music command support**: "Play X", "Skip", "Stop", etc.
- **Continuous listening**: Real-time audio buffering

**Flow**:
```python
# 1. User runs /listen
await enhanced_listener.start_smart_listen(
    guild_id=guild_id,
    voice_client=voice_client,
    on_transcription=callback_transcription,
    on_bot_response_needed=callback_response
)

# 2. Audio is buffered and monitored for silence
# 3. After silence threshold (2s), Whisper transcribes the audio
# 4. on_transcription callback sends transcription to channel
# 5. If transcription contains question/mention, on_bot_response_needed triggers ChatCog
```

**Whisper Configuration**:
```bash
WHISPER_ENABLED=true
WHISPER_MODEL=base  # tiny, base, small, medium, large
WHISPER_DEVICE=cpu  # cpu or cuda
WHISPER_LANGUAGE=en  # Auto-detect if empty
WHISPER_SILENCE_THRESHOLD=2.0  # Seconds of silence before transcription
```

### Slash Commands

#### `/join` (`commands.py`)
- Joins user's voice channel
- Creates voice client for guild

#### `/leave` (`commands.py`)
- Disconnects from voice channel
- Cleans up music player state

#### `/tts <text>` (`commands.py`)
- Generates TTS audio for text
- Applies RVC if enabled
- Plays in voice channel

#### `/voices` (`main.py`, lines 71-130)
- Lists current TTS voice
- Lists available RVC models
- Shows engine details (Kokoro/Edge/Supertonic)

#### `/set_voice <voice>` (`main.py`, lines 135-175)
- Changes default TTS voice
- Validates voice exists for current engine
- Updates `tts.kokoro_voice` or `tts.edge_voice`

#### `/list_kokoro_voices` (`main.py`, lines 244-335)
- Shows all Kokoro voices with descriptions
- Grouped by gender/region (Male, Female, British)
- Current voice indicator

#### `/listen` (`main.py`, lines 340-716)
- Starts smart voice detection
- Transcribes speech after silence
- Responds to questions/mentions
- Handles music commands ("Play X", "Skip", etc.)

#### `/stop_listening` (`main.py`, lines 722-795)
- Stops smart listener
- Transcribes any remaining audio
- Shows session duration

#### `/stt_status` (`main.py`, lines 799-888)
- Shows Whisper STT status
- Model size, device (CPU/GPU)
- Memory usage estimate
- Current listening state

### Voice Manager (`manager.py`)

**Purpose**: Centralized voice client management across guilds

```python
class VoiceManager:
    def __init__(self, bot):
        self.voice_clients = {}  # {guild_id: voice_client}

    def get_voice_client(self, guild_id) -> discord.VoiceClient:
        return self.voice_clients.get(guild_id)

    async def join_channel(self, channel: discord.VoiceChannel):
        voice_client = await channel.connect()
        self.voice_clients[channel.guild.id] = voice_client
        return voice_client

    async def leave_channel(self, guild_id):
        if guild_id in self.voice_clients:
            await self.voice_clients[guild_id].disconnect()
            del self.voice_clients[guild_id]

    async def cleanup_guild(self, guild_id):
        # Called on guild removal (on_guild_remove event)
        await self.leave_channel(guild_id)
```

### TTS + RVC Integration

**Standard TTS Flow**:
```python
# 1. Generate TTS
audio_file = Config.TEMP_DIR / f"tts_{uuid.uuid4()}.wav"
await tts.generate(text, audio_file, speed=kokoro_speed, rate=edge_rate)

# 2. Apply RVC (optional)
if rvc and rvc.is_enabled() and Config.RVC_ENABLED:
    rvc_file = Config.TEMP_DIR / f"rvc_{uuid.uuid4()}.wav"
    audio_file = await rvc.convert(audio_file, rvc_file, model_name=Config.DEFAULT_RVC_MODEL)

# 3. Play audio
audio_source = discord.FFmpegPCMAudio(
    str(audio_file),
    options="-vn -af aresample=48000,aformat=sample_fmts=s16:channel_layouts=stereo"
)
voice_client.play(audio_source, after=cleanup_callback)
```

**Sentiment-Based Voice Modulation**:
```python
sentiment = ChatHelpers.analyze_sentiment(text)
kokoro_speed = 1.1 if sentiment == "positive" else 0.9 if sentiment == "negative" else 1.0
edge_rate = "+10%" if sentiment == "positive" else "-10%" if sentiment == "negative" else "+0%"
```

---

## CharacterCommandsCog

**Location**: `/root/acore_bot/cogs/character_commands.py`

**Purpose**: Multi-character persona switching, character imports (SillyTavern cards), and inter-character interactions.

### Key Features

#### 1. Persona Switching

**Command**: `/set_character <character> <framework>` (lines 27-173)

**Flow**:
```python
# 1. Auto-select framework if not provided
framework_map = {
    "dagoth_ur": "neuro",
    "gothmommy": "caring",
    "chief": "chaotic",
    "arbiter": "assistant"
}
framework = framework or framework_map.get(character, "neuro")

# 2. Compile persona (character + framework)
compiled_persona = bot.persona_system.compile_persona(character, framework, force_recompile=True)

# 3. Update all subsystems
bot.current_persona = compiled_persona
chat_cog.compiled_persona = compiled_persona
chat_cog.system_prompt = compiled_persona.system_prompt
behavior_engine.set_persona(compiled_persona)

# 4. Apply voice settings (if available)
if legacy_config and 'voice' in legacy_config:
    voice_cog.tts.kokoro_voice = legacy_config['voice']['kokoro_voice']
    voice_cog.tts.kokoro_speed = legacy_config['voice']['kokoro_speed']

# 5. Apply RVC settings (if available)
if legacy_config and 'rvc' in legacy_config:
    Config.DEFAULT_RVC_MODEL = legacy_config['rvc']['model']
```

**Example**:
```
/set_character dagoth_ur neuro
  -> Character: Dagoth Ur
  -> Framework: Neuro (analytical, thoughtful)
  -> Voice: am_adam
  -> RVC: dagoth_ur.pth
  -> Tools: time, web_search, rag_search
```

#### 2. Character Interaction

**Command**: `/interact <initiator> <target> <topic>` (lines 175-251)

**Purpose**: Force two personas to interact with each other (simulated conversation)

**Flow**:
```python
# 1. Resolve persona names (fuzzy matching)
p1 = find_persona(initiator)  # "dagoth" -> Dagoth Ur persona
p2 = find_persona(target)     # "scav" -> Scav persona

# 2. Generate starter message (as p1)
prompt = f"""You are {p1.character.display_name}.
Start a conversation with {p2.character.display_name} about: {topic}.
IMPORTANT: Mention them by name ("{p2.character.display_name}") so they hear you.
Keep it in character, short (under 200 chars), and engaging."""

response = await ollama.generate(prompt, max_tokens=200)

# 3. Send via Webhook (spoofing as p1)
webhook = await channel.create_webhook(name="PersonaBot_Proxy")
await webhook.send(
    content=response,
    username=p1.character.display_name,
    avatar_url=p1.character.avatar_url
)

# 4. This triggers MessageHandler for p2 (name-based trigger)
# If p2's name is mentioned in the message, they auto-respond
```

**Example**:
```
!interact toad dagoth scream at him
  -> Toad: "DAGOTH UR! WHAT ARE YOU DOING IN MY SWAMP?!"
  -> (Dagoth Ur auto-responds because his name was mentioned)
```

**Prefix Command**: `!interact <char1> <char2> <topic>` (lines 253-319)
- Same as slash command but uses prefix syntax
- Useful for quick interactions

#### 3. Character Import (SillyTavern Cards)

**Service**: `CharacterCardImporter` (`services/persona/character_importer.py`)

**Command**: `!import` (attach PNG) (lines 414-485)

**Flow**:
```python
# 1. User attaches SillyTavern character card PNG
# 2. Download PNG to temp directory
temp_path = temp_dir / attachment.filename
await attachment.save(temp_path)

# 3. Import card (extracts embedded JSON)
importer = CharacterCardImporter()
result = importer.import_card(temp_path)  # Returns path to created character.json

# 4. Read imported character
with open(result, 'r') as f:
    char_data = json.load(f)

# 5. Notify user
embed.add_field(
    name="Next Steps",
    value=f"1. Add \"{char_data['id']}.json\" to ACTIVE_PERSONAS in config.py\n"
          f"2. Restart the bot or use !reload_characters\n"
          f"3. Use /set_character {char_data['id']}"
)
```

**Batch Import**: `!import_folder` (lines 507-563)
- Imports all PNGs from `data/import_cards/`
- Processes multiple cards at once

**Character Card Format**:
- SillyTavern V2 cards (PNG with embedded JSON metadata)
- Extracted fields: `name`, `description`, `personality`, `scenario`, `first_mes`, `mes_example`
- Converted to acore_bot character schema

#### 4. Character Reload

**Command**: `!reload_characters` (lines 487-505)

**Purpose**: Reload all characters from disk without restarting bot

```python
await chat_cog.persona_router.initialize()  # Re-scans prompts/characters/*.json
personas = chat_cog.persona_router.get_all_personas()
names = [p.character.display_name for p in personas]
await ctx.send(f"Reloaded {len(personas)} characters: {', '.join(names)}")
```

#### 5. List Characters

**Command**: `/list_characters` (lines 321-389)

**Output**:
```
Characters:
• dagoth_ur
• gothmommy
• chief
• arbiter
• scav
• toad

Frameworks:
• neuro (analytical)
• caring (empathetic)
• chaotic (unpredictable)
• assistant (helpful)

Examples:
/set_character dagoth_ur neuro
/set_character gothmommy caring
```

### Character Schema

**Location**: `prompts/characters/<character_id>.json`

**Format**:
```json
{
  "id": "dagoth_ur",
  "display_name": "Dagoth Ur",
  "avatar_url": "https://...",
  "description": "The immortal leader of the Sixth House...",
  "personality": "Charismatic, philosophical, delusional...",
  "knowledge_domain": {
    "topics": ["Morrowind lore", "CHIM", "Dwemer"],
    "expertise_level": "deity",
    "rag_categories": ["morrowind", "elder_scrolls"]
  },
  "communication_style": {
    "formality": 0.8,
    "verbosity": 0.7,
    "humor": 0.3,
    "emoji_usage": 0.1
  },
  "legacy_config": {
    "voice": {
      "kokoro_voice": "am_adam",
      "kokoro_speed": 1.0,
      "edge_voice": "en-US-GuyNeural"
    },
    "rvc": {
      "enabled": true,
      "model": "dagoth_ur.pth"
    }
  }
}
```

---

## MusicCog

**Location**: `/root/acore_bot/cogs/music.py`

**Purpose**: YouTube music playback with queue management, playlists, and voice integration.

### Architecture

**Service**: `MusicPlayer` (`services/discord/music.py`)

**Features**:
- YouTube search and playback (via yt-dlp)
- Queue management (FIFO)
- Loop modes (song, queue, off)
- Volume control
- Playlist import

### Slash Commands

#### `/play <query>` (lines 59-138)

**Single Song**:
```python
# 1. Search YouTube
song = await music_player.search_song(query, requester=user.display_name)

# 2. Add to queue
position = await music_player.add_to_queue(guild_id, song)

# 3. Start playing (if idle)
state = music_player.get_state(guild_id)
if not state.is_playing:
    await music_player.play_next(guild_id, voice_client)
```

**Playlist**:
```python
# 1. Detect playlist URL
is_playlist = 'list=' in query and 'youtube.com' in query

# 2. Fetch all songs
songs = await music_player.search_playlist(query, requester=user.display_name)

# 3. Add all to queue
for song in songs:
    await music_player.add_to_queue(guild_id, song)

# 4. Start playing
await music_player.play_next(guild_id, voice_client)
```

#### `/skip` (lines 140-161)
- Skips current song
- Starts next song in queue
- If looping song, continues loop

#### `/stop` (lines 163-180)
- Stops playback
- Clears queue
- Resets player state

#### `/pause` / `/resume` (lines 182-228)
- Pauses/resumes current song
- Maintains queue state

#### `/nowplaying` (lines 230-264)
- Shows current song info (title, duration, requester)
- Shows loop status

#### `/queue` (lines 266-311)
- Lists next 10 songs
- Shows total queue duration
- Current song highlighted

#### `/volume <0-100>` (lines 313-337)
- Sets playback volume (0.0 - 1.0)
- Persists across songs

#### `/shuffle` (lines 339-354)
- Randomizes queue order
- Doesn't affect current song

#### `/loop <mode>` (lines 373-400)
- **song**: Repeat current song indefinitely
- **queue**: Repeat entire queue
- **off**: Disable looping

#### `/remove <position>` (lines 402-427)
- Removes song at queue position
- 1-indexed (1 = first in queue)

#### `/disconnect` (lines 429-449)
- Disconnects from voice
- Cleans up music state

### Music Player State

**Data Structure**:
```python
@dataclass
class Song:
    title: str
    url: str
    duration: int  # Seconds
    duration_str: str  # "3:45"
    thumbnail: str
    requester: str

@dataclass
class MusicState:
    queue: deque[Song]
    current: Optional[Song]
    volume: float  # 0.0 - 1.0
    loop: bool  # Loop current song
    loop_queue: bool  # Loop entire queue
    is_playing: bool
    is_paused: bool
```

### Auto-Disconnect

**Event**: `on_voice_state_update` (lines 451-485)

**Logic**:
```python
# If bot is alone in voice channel for 30 seconds, disconnect
if voice_client.channel.members == [bot]:
    await asyncio.sleep(30)
    # Check again (user might have rejoined)
    if voice_client.channel.members == [bot]:
        music_player.cleanup(guild_id)
        await voice_client.disconnect()
```

---

## RemindersCog

**Location**: `/root/acore_bot/cogs/reminders.py`

**Purpose**: Time-based reminders with natural language parsing.

### Architecture

**Service**: `RemindersService` (`services/discord/reminders.py`)

**Features**:
- Natural language time parsing ("in 30 minutes", "tomorrow at 9am")
- LLM fallback parsing for complex expressions
- Background task checking (every 30 seconds)
- Per-user reminder limits

### Slash Commands

#### `/remind <reminder>` (lines 28-94)

**Examples**:
- "in 30 minutes to check the oven"
- "in 2 hours to call mom"
- "at 5pm to start cooking"
- "tomorrow at 9am to submit report"

**Parsing Flow**:
```python
# 1. Regex parsing (TimeParser)
trigger_time = TimeParser.parse(reminder)  # Extracts datetime
message = TimeParser.extract_message(reminder)  # Extracts message

# 2. LLM fallback (if regex fails)
if not trigger_time:
    prompt = f"Extract time and message from: '{reminder}'. Current time: {datetime.now()}"
    response = await ollama.generate(prompt)
    data = json.loads(response)
    trigger_time = datetime.fromisoformat(data['trigger_time'])
    message = data['message']

# 3. Add reminder
reminder_id = await reminders.add_reminder(user_id, channel_id, message, trigger_time)
```

**TimeParser Regex Patterns**:
- `in X minutes/hours/days`
- `at HH:MM [am/pm]`
- `tomorrow/next week at HH:MM`
- Relative: `next Monday`, `in 3 days`

#### `/reminders` (lines 138-183)
- Lists all active reminders for user
- Sorted by trigger time (soonest first)
- Shows ID, time until, and message

#### `/cancel_reminder <id>` (lines 185-210)
- Cancels a specific reminder by ID
- Verifies ownership (user can only cancel their own)

#### `/clear_reminders` (lines 212-242)
- Clears all reminders for user
- Confirmation (no undo)

### Reminder Storage

**Format** (`data/reminders.json`):
```json
{
  "reminders": [
    {
      "id": "abc123",
      "user_id": 123456789,
      "channel_id": 987654321,
      "message": "Check the oven",
      "trigger_time": "2025-12-10T15:30:00",
      "created_at": "2025-12-10T15:00:00"
    }
  ]
}
```

**Max Reminders**: `Config.MAX_REMINDERS_PER_USER` (default: 10)

### Background Task

**Method**: `RemindersService.check_reminders()` (runs every 30 seconds)

```python
async def check_reminders():
    while True:
        now = datetime.now()
        for reminder in reminders:
            if reminder['trigger_time'] <= now:
                # Send reminder
                channel = bot.get_channel(reminder['channel_id'])
                user = bot.get_user(reminder['user_id'])
                await channel.send(f"<@{user.id}> Reminder: {reminder['message']}")

                # Remove from list
                reminders.remove(reminder)
                save_reminders()

        await asyncio.sleep(30)
```

---

## NotesCog

**Location**: `/root/acore_bot/cogs/notes.py`

**Purpose**: Simple note-taking system with categories.

### Architecture

**Service**: `NotesService` (`services/discord/notes.py`)

### Slash Commands

#### `/note <content> [category]` (lines 27-65)
- Saves a note with optional category
- Max 50 notes per user
- Auto-generated ID

#### `/notes [category]` (lines 67-121)
- Lists all notes (or filtered by category)
- Sorted by creation time (newest first)
- Shows max 10 notes

#### `/delnote <id>` (lines 123-148)
- Deletes a note by ID
- Verifies ownership

#### `/clearnotes` (lines 150-174)
- Deletes all notes for user
- Returns count deleted

### Note Storage

**Format** (`data/notes.json`):
```json
{
  "notes": [
    {
      "id": "xyz789",
      "user_id": 123456789,
      "content": "Remember to backup database",
      "category": "work",
      "created_at": "2025-12-10T10:00:00"
    }
  ]
}
```

**Max Notes**: 50 per user

---

## HelpCog

**Location**: `/root/acore_bot/cogs/help.py`

**Purpose**: Interactive help menu with dropdown navigation.

### Architecture

**Components**:
- `HelpSelect`: Dropdown menu (discord.ui.Select)
- `HelpView`: View container (discord.ui.View)
- `HelpCog`: Cog that registers `/help` command

### Slash Commands

#### `/help` (lines 95-106)

**Flow**:
```python
# 1. Create embed
embed = discord.Embed(
    title="Bot Help Center",
    description="Select a category below to see available commands."
)

# 2. Create view with dropdown
view = HelpView(bot)  # Contains HelpSelect dropdown

# 3. Send message
await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# 4. User selects category from dropdown
# 5. HelpSelect.callback updates embed with category commands
```

**Categories**:
1. **General**: Basic commands (/help, /chat, /clear)
2. **Music**: Music playback (/play, /skip, /queue, /volume)
3. **Voice & TTS**: Voice features (/join, /tts, /listen)
4. **Games & Fun**: Interactive games (/trivia, /wouldyourather)
5. **Utility**: Tools (/remind, /search, /note)
6. **System**: Bot status (/botstatus, /metrics, /logs)

### Dropdown Callback

**Method**: `HelpSelect.callback()` (lines 26-79)

```python
async def callback(self, interaction: discord.Interaction):
    category = self.values[0]  # Selected category

    # Build category-specific embed
    if category == "Music":
        embed.description = """
        /play <query> - Play a song
        /skip - Skip current song
        /queue - Show queue
        """
    elif category == "Voice & TTS":
        embed.description = """
        /join - Join voice channel
        /tts <text> - Speak text
        /listen - Start listening
        """
    # ... etc

    # Update message with new embed
    await interaction.response.edit_message(embed=embed, view=self.view)
```

**Timeout**: 180 seconds (3 minutes)

---

## SystemCog

**Location**: `/root/acore_bot/cogs/system.py`

**Purpose**: Bot health monitoring, performance metrics, and system diagnostics.

### Slash Commands

#### `/botstatus` (lines 30-73)

**Displays**:
- Uptime
- Latency (WebSocket ping)
- Guild count
- User count (across all guilds)
- Active voice connections
- CPU usage (psutil)
- Memory usage (RAM %)
- Python version
- LLM provider & model

**Example Output**:
```
System Status
⏱️ Uptime: 2 days, 5:32:10
📶 Latency: 45ms
🏠 Guilds: 3
👥 Users: 1,234
🔊 Voice: 1 active
💻 CPU: 12.3%
🧠 Memory: 45% (512MB)
🐍 Python: 3.11.5
🤖 LLM: openrouter (anthropic/claude-3.5-sonnet)
```

#### `/metrics` (lines 75-141)

**Displays**:
- **Response Times**: Avg, P95, Max (milliseconds)
- **Token Usage**: Total, Prompt, Completion
- **Errors**: Total count, error rate
- **Cache Hits**: History cache, RAG cache (hit rate %)
- **Activity**: Messages processed, commands executed

**Requires**: `bot.metrics` service (`services/monitoring/metrics.py`)

#### `/errors` (lines 143-179)

**Displays**:
- Last 5 errors
- Timestamp, error type, message
- Formatted as code blocks

#### `/logs <lines>` (lines 181-218)

**Displays**:
- Last N lines from log file (`Config.LOG_FILE_PATH`)
- Max 50 lines
- Admin-only (should add permission check)

**Example**:
```
/logs 20
  -> Shows last 20 lines from logs/bot.log
```

### Metrics Service

**Location**: `services/monitoring/metrics.py`

**Tracked Metrics**:
- Response times (LLM latency)
- Token usage (prompt + completion)
- Error counts (by type)
- Cache hit rates
- Command usage
- Message processing

**Methods**:
```python
metrics.record_response_time(duration_ms)
metrics.record_tokens(prompt_tokens, completion_tokens)
metrics.record_error(error_type, message)
metrics.record_cache_hit(cache_name)
metrics.record_message(user_id, channel_id)
metrics.get_summary()  # Returns dict of all metrics
```

---

## Event Flow Diagrams

### Message Processing Flow

```
User sends message
    ↓
on_message event (main.py)
    ↓
ChatCog.check_and_handle_message()
    ↓
MessageHandler.check_and_handle_message()
    ↓
[FILTERING]
├─ Self message? → Ignore
├─ Bot muted? → Ignore (unless unmute)
├─ Prefix command? → Ignore
├─ #ignore tag? → Ignore
├─ Duplicate? → Ignore
└─ Bot message (not persona)? → Ignore
    ↓
[LOOP PREVENTION]
├─ Persona message?
│   ├─ Self-reply (same name)? → Abort
│   └─ Random decay (50%)? → Abort
└─ Continue
    ↓
[TRIGGER DETECTION]
├─ Priority 1: Direct mention → RESPOND
├─ Priority 2: Reply to bot → RESPOND
├─ Priority 3: Name trigger → RESPOND
├─ Priority 4: Image question → RESPOND
├─ Priority 5: BehaviorEngine → RESPOND (if AI decides)
├─ Priority 6: Conversation context → RESPOND (if recent activity)
└─ Priority 7: Ambient channel → RESPOND (random chance)
    ↓
[PERSONA SELECTION]
├─ Banter response? → Pick different persona
└─ Default → Route by content/stickiness
    ↓
[CONTEXT BUILDING]
├─ Load history (ContextRouter)
├─ Build user context (profiles, affection, memory)
├─ Fetch RAG context (knowledge base)
├─ Fetch web search (if applicable)
├─ Scan lorebook (trigger-based lore)
└─ Assemble final_messages (ContextManager)
    ↓
[LLM GENERATION]
├─ Vision? → ollama.chat (with image)
├─ Agentic tools? → ReAct loop (3 iterations)
├─ Streaming + Voice? → Parallel TTS + Discord
└─ Standard → ollama.chat
    ↓
[RESPONSE DELIVERY]
├─ Clean response (remove <think>, artifacts)
├─ Prepare Discord version (restore mentions)
├─ Prepare TTS version (clean for speech)
├─ Send via Webhook (persona spoofing)
└─ Fallback: Standard message with prefix
    ↓
[POST-RESPONSE]
├─ Record sticky persona (channel memory)
├─ Update persona relationships (affinity)
├─ Speak in voice (if connected)
├─ Record metrics (response time, tokens)
└─ Background: Learn from conversation, update affection
```

### Persona Interaction Flow

```
User: !interact toad dagoth yell at him
    ↓
CharacterCommandsCog.interact_cmd()
    ↓
[PERSONA RESOLUTION]
├─ Find persona: "toad" → Toad persona
└─ Find persona: "dagoth" → Dagoth Ur persona
    ↓
[STARTER GENERATION]
prompt = "You are Toad. Start a conversation with Dagoth Ur about: yell at him.
          IMPORTANT: Mention them by name so they hear you."
    ↓
response = await ollama.generate(prompt)
  → "DAGOTH UR! WHAT ARE YOU DOING IN MY SWAMP?!"
    ↓
[WEBHOOK SEND]
await webhook.send(
    content=response,
    username="Toad",
    avatar_url="https://toad.png"
)
    ↓
[TRIGGER AUTO-RESPONSE]
on_message event sees webhook message
    ↓
MessageHandler: Is persona message? Yes
    ↓
MessageHandler: Name "Dagoth Ur" in message? Yes
    ↓
should_respond = True (name_trigger)
    ↓
Persona selected: Dagoth Ur (mentioned in message)
    ↓
LLM generates Dagoth's response
    ↓
Dagoth's response sent via webhook
    ↓
[AFFINITY UPDATE]
persona_relationships.record_interaction(
    speaker="Toad",
    responder="Dagoth Ur",
    affinity_change=2
)
    ↓
Future banter chance increased (5% → 7% for these two)
```

### Voice + TTS Flow

```
User: /tts Hello world
    ↓
VoiceCog.tts_command()
    ↓
[TTS GENERATION]
├─ Select engine (Kokoro/Edge/Supertonic)
├─ Select voice (am_adam, af_bella, etc.)
├─ Analyze sentiment → Adjust speed/pitch
└─ Generate audio file
    ↓
audio_file = await tts.generate(
    text="Hello world",
    output_file="tts_123.wav",
    speed=1.0
)
    ↓
[RVC CONVERSION] (if enabled)
├─ Load RVC model (dagoth_ur.pth)
├─ Convert voice
└─ Replace audio_file
    ↓
rvc_file = await rvc.convert(
    input_file=audio_file,
    output_file="rvc_123.wav",
    model_name="dagoth_ur.pth",
    pitch_shift=0
)
    ↓
[PLAYBACK]
├─ Check if bot is in voice channel
├─ Create FFmpegPCMAudio source
└─ voice_client.play(audio_source)
    ↓
[CLEANUP]
await asyncio.sleep(duration)
os.unlink(audio_file)  # Delete temp files
```

### Smart Listening Flow

```
User: /listen
    ↓
VoiceCog.start_listening_session()
    ↓
[START LISTENER]
await enhanced_listener.start_smart_listen(
    guild_id=guild_id,
    voice_client=voice_client,
    on_transcription=callback_transcription,
    on_bot_response_needed=callback_response
)
    ↓
[AUDIO BUFFERING]
voice_client receives audio packets
    ↓
Enhanced listener buffers audio
    ↓
[SILENCE DETECTION]
├─ Audio level < threshold for 2 seconds
└─ Trigger transcription
    ↓
[WHISPER TRANSCRIPTION]
├─ Convert audio to WAV
├─ Run Whisper model
└─ Extract text + language
    ↓
transcription = "Hey bot, play some music"
    ↓
[CALLBACK: on_transcription]
├─ Send embed to channel
└─ Show transcription + language
    ↓
[SMART RESPONSE DETECTION]
├─ Is question? ("?")
├─ Mentions bot name?
├─ Is command? ("play", "skip", "stop")
└─ If yes → Trigger on_bot_response_needed
    ↓
[CALLBACK: on_bot_response_needed]
├─ Parse for music commands
├─ If music command:
│   ├─ Execute (play, skip, etc.)
│   └─ Speak response ("Playing X")
└─ Else:
    ├─ Generate AI response (ChatCog)
    ├─ Send to channel
    └─ Speak response (TTS)
    ↓
[LOOP]
Continue buffering audio until /stop_listening
```

---

## Summary

### Cog Responsibilities

| Cog | Purpose | Commands | Services |
|-----|---------|----------|----------|
| **ChatCog** | AI conversations | /chat, /ambient, /end_session | OllamaService, ContextManager, BehaviorEngine, PersonaRouter |
| **VoiceCog** | TTS & Voice | /join, /tts, /listen, /voices | TTSService, RVCService, EnhancedVoiceListener |
| **CharacterCommandsCog** | Persona management | /set_character, /interact, /import, /list_characters | PersonaRouter, CharacterCardImporter |
| **MusicCog** | Music playback | /play, /skip, /queue, /volume | MusicPlayer |
| **RemindersCog** | Reminders | /remind, /reminders, /cancel_reminder | RemindersService |
| **NotesCog** | Notes | /note, /notes, /delnote | NotesService |
| **HelpCog** | Help menu | /help | - |
| **SystemCog** | Diagnostics | /botstatus, /metrics, /errors, /logs | MetricsService |

### Key Patterns

1. **Modular Design**: ChatCog split into 6 files for maintainability
2. **Service Injection**: Cogs receive services via dependency injection in `main.py`
3. **Async/Await**: All I/O operations are async (LLM, Discord API, file I/O)
4. **Background Tasks**: Long-running tasks tracked via `_background_tasks` set
5. **Error Handling**: Try/except blocks with logging and user-friendly error messages
6. **Webhook Spoofing**: Persona messages sent via webhooks for custom names/avatars
7. **Context Management**: Smart context building with history, RAG, user profiles, lorebook
8. **Trigger System**: Multi-level priority triggers for message responses

### Configuration Hierarchy

1. **Environment Variables** (`.env`) - User-configurable settings
2. **Config Class** (`config.py`) - Centralized config access
3. **Persona Files** (`prompts/characters/*.json`) - Per-character settings
4. **Legacy Config** (embedded in persona) - Voice/RVC overrides

---

**Next Steps**: See `03_services.md` for detailed service architecture and `04_message_flow.md` for complete message processing pipeline.
