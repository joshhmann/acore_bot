# New Features Documentation

This document describes the newly implemented features and how to use them.

## Table of Contents

1. [Memory Management](#1-memory-management)
2. [Enhanced Dynamic Context Injection](#2-enhanced-dynamic-context-injection)
3. [Multi-User Conversation Awareness](#3-multi-user-conversation-awareness)
4. [Response Streaming](#4-response-streaming)
5. [Conversation Summarization with RAG](#5-conversation-summarization-with-rag)
6. [Voice Activity Detection (Whisper STT)](#6-voice-activity-detection-whisper-stt)

---

## 1. Memory Management

### Overview
Automatic cleanup and archival system for chat history and temporary files, keeping your bot running efficiently.

### Features
- **Automatic temp file cleanup**: Removes old audio/TTS files older than 24 hours (configurable)
- **Conversation archival**: Archives old chat history to save space
- **Background cleanup task**: Runs every 6 hours automatically
- **Memory statistics**: Track storage usage

### Configuration (.env)
```bash
MEMORY_CLEANUP_ENABLED=true
MEMORY_CLEANUP_INTERVAL_HOURS=6
MAX_TEMP_FILE_AGE_HOURS=24
MAX_HISTORY_AGE_DAYS=30
```

### Usage
Memory management runs automatically in the background. No commands needed.

### API
```python
from services.memory_manager import MemoryManager

# Initialize
memory_mgr = MemoryManager(
    temp_dir=Config.TEMP_DIR,
    chat_history_dir=Config.CHAT_HISTORY_DIR
)

# Manual cleanup
stats = await memory_mgr.cleanup_temp_files()
archive_stats = await memory_mgr.archive_old_conversations()

# Get statistics
stats = await memory_mgr.get_memory_stats()

# Start background cleanup
asyncio.create_task(memory_mgr.start_background_cleanup())
```

---

## 2. Enhanced Dynamic Context Injection

### Overview
Provides richer contextual information to the AI based on time of day, user activity, and server context.

### Features
- **Time-of-day awareness**: Bot behavior adapts to morning/afternoon/evening/night
- **Activity-based context**: Tracks relationship stages (first meeting, friends, close companions)
- **Server context**: Includes Discord server and channel information
- **Enhanced mood matching**: Bot's energy matches the time of day

### Configuration
No additional configuration needed - works automatically.

### Context Examples

**Morning (5 AM - 12 PM)**
```
[Current time: 09:30 AM, Monday, October 29, 2025 - morning (fresh and energetic)]
```

**Evening (5 PM - 9 PM)**
```
[Current time: 07:45 PM, Monday, October 29, 2025 - evening (relaxed and conversational)]
```

**Late Night (9 PM - 5 AM)**
```
[Current time: 02:15 AM, Tuesday, October 30, 2025 - late night (calm and introspective)]
```

### API
```python
from utils.system_context import SystemContextProvider

# Get time-based context
time_context = SystemContextProvider.get_time_of_day_context()

# Get activity context
activity = SystemContextProvider.get_activity_context(
    interaction_count=25,
    last_interaction="2025-10-29T10:00:00"
)

# Get server context
server_ctx = SystemContextProvider.get_server_context(
    guild_name="My Server",
    channel_name="general"
)
```

---

## 3. Multi-User Conversation Awareness

### Overview
Bot now tracks multiple users in group conversations, remembering who said what and building context accordingly.

### Features
- **User attribution**: Messages tagged with username and user ID
- **Participant tracking**: Bot knows who's in the conversation
- **Group context building**: "Talking with Alice, Bob, and Charlie"
- **Per-user relationships**: Maintains separate affection scores for each user

### Usage
Works automatically in channels with multiple users. Bot will reference previous speakers:

```
User1: What's the weather like?
Bot: It's sunny outside!
User2: Can we go to the park?
Bot: That sounds great, User2! As User1 asked about the weather, it's perfect for the park.
```

### API
```python
from utils.helpers import ChatHistoryManager

# Add message with user attribution
await history.add_message(
    channel_id=123,
    role="user",
    content="Hello!",
    username="Alice",
    user_id=456
)

# Get conversation participants
participants = history.get_conversation_participants(messages)
# Returns: [{"user_id": 456, "username": "Alice", "message_count": 5}, ...]

# Build multi-user context
context = history.build_multi_user_context(messages)
# Returns: "Group conversation with: Alice, Bob, Charlie"
```

---

## 4. Response Streaming

### Overview
Stream LLM responses word-by-word instead of waiting for the complete response, dramatically improving perceived latency.

### Features
- **Token-by-token streaming**: See responses as they're generated
- **Periodic updates**: Discord message updates every 1 second (configurable)
- **Better UX**: Feels much faster and more responsive
- **Typing indicators**: Bot shows it's "thinking"

### Configuration (.env)
```bash
RESPONSE_STREAMING_ENABLED=true
STREAM_UPDATE_INTERVAL=1.0  # Update every 1 second
```

### Usage
No changes needed - `/chat` and mentions will automatically use streaming when enabled.

### Example Implementation (for custom integrations)
```python
from services.ollama import OllamaService

ollama = OllamaService(...)

# Stream responses
full_response = ""
message = None

async for chunk in ollama.chat_stream(messages, system_prompt=prompt):
    full_response += chunk

    # Update Discord message periodically
    if not message:
        message = await interaction.followup.send(full_response)
    else:
        await message.edit(content=full_response)

    await asyncio.sleep(1.0)  # Throttle updates
```

---

## 5. Conversation Summarization with RAG

### Overview
Automatically summarize old conversations and store them in RAG for long-term memory recall. The bot can remember and reference past conversations!

### Features
- **AI-powered summarization**: Uses Ollama to create concise summaries
- **RAG storage**: Summaries stored in vector database for semantic search
- **Automatic summarization**: Triggers after N messages (configurable)
- **Memory recall**: Bot retrieves relevant past conversations during chat
- **Archival**: Summaries saved to files for backup

### Configuration (.env)
```bash
CONVERSATION_SUMMARIZATION_ENABLED=true
AUTO_SUMMARIZE_THRESHOLD=30  # Summarize after 30 messages
STORE_SUMMARIES_IN_RAG=true
RAG_ENABLED=true
RAG_DOCUMENTS_PATH=./data/documents
```

### Commands (to be added in future update)
```
/summarize_conversation - Manually summarize current conversation
/recall <query> - Search past conversation summaries
/list_summaries - View all stored summaries
```

### API
```python
from services.conversation_summarizer import ConversationSummarizer

# Initialize
summarizer = ConversationSummarizer(
    ollama=ollama_service,
    rag=rag_service,
    summary_dir=Config.SUMMARY_DIR
)

# Summarize and store
summary = await summarizer.summarize_and_store(
    messages=conversation_messages,
    channel_id=channel_id,
    participants=["Alice", "Bob"],
    store_in_rag=True
)

# Retrieve relevant memories
memories = await summarizer.retrieve_relevant_memories(
    query="What did we discuss about pizza last week?"
)

# Build memory context for current message
context = await summarizer.build_memory_context(
    current_message="Remember what we talked about?"
)
```

### Summary Format
```
Conversation Summary - Channel 123456
Date: 2025-10-29T15:30:00
Participants: Alice, Bob, Charlie
Messages: 45

SUMMARY:
The conversation focused on planning a gaming session for this weekend.
Key decisions:
- Meeting Saturday at 3 PM
- Playing Halo co-op campaign
- Alice will host the server
- Bob will bring snacks

Notable moments:
- Charlie shared a funny story about his previous gaming fail
- Group agreed on trying the Legendary difficulty

[Stored: 2025-10-29T16:00:00]
```

---

## 6. Voice Activity Detection (Whisper STT)

### Overview
Speech-to-text capabilities using OpenAI Whisper, allowing the bot to "listen" to users in voice channels and transcribe speech.

### Features
- **Whisper STT**: State-of-the-art speech recognition
- **Multiple model sizes**: tiny, base, small, medium, large
- **90+ languages**: Supports most major languages
- **GPU acceleration**: CUDA support for faster transcription
- **Voice commands**: Users can talk naturally to the bot

### Installation
```bash
# Install Whisper
pip install openai-whisper

# Optional: For GPU acceleration
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### Configuration (.env)
```bash
WHISPER_ENABLED=true
WHISPER_MODEL_SIZE=base  # tiny, base, small, medium, large
WHISPER_DEVICE=auto  # auto, cpu, cuda
WHISPER_LANGUAGE=en  # or auto-detect
WHISPER_SILENCE_THRESHOLD=2.0  # Seconds of silence before stopping
MAX_RECORDING_DURATION=30  # Max recording length in seconds
```

### Model Sizes & Performance

| Model  | Parameters | RAM Required | VRAM Required | Speed  | Accuracy |
|--------|-----------|--------------|---------------|---------|----------|
| tiny   | 39 M      | ~400 MB      | ~1 GB        | ~10x   | Good     |
| base   | 74 M      | ~500 MB      | ~1.5 GB      | ~7x    | Better   |
| small  | 244 M     | ~1 GB        | ~2.5 GB      | ~4x    | Great    |
| medium | 769 M     | ~2.5 GB      | ~5 GB        | ~2x    | Excellent|
| large  | 1550 M    | ~5 GB        | ~10 GB       | ~1x    | Best     |

**Recommendation**: Use `base` for most cases - good balance of speed and accuracy.

### Commands (to be added to voice.py)
```
/listen - Start listening to voice channel
/stop_listening - Stop listening
/transcribe <audio_file> - Transcribe an audio file
/stt_status - Check STT service status
```

### API
```python
from services.whisper_stt import WhisperSTTService, VoiceActivityDetector

# Initialize Whisper
whisper = WhisperSTTService(
    model_size="base",
    device="auto",
    language="en"
)

# Transcribe file
result = await whisper.transcribe_file(
    audio_path=Path("recording.wav"),
    language="en"
)
print(result["text"])

# Voice activity detection
vad = VoiceActivityDetector(
    whisper_stt=whisper,
    temp_dir=Config.TEMP_DIR
)

# Start recording
await vad.start_recording(guild_id, user_id, voice_client)

# Stop and transcribe
result = await vad.stop_recording(guild_id)
print(f"User said: {result['text']}")
```

### Example Workflow
1. User joins voice channel
2. User uses `/listen` command
3. Bot starts recording audio
4. User speaks: "Hey bot, what's the weather?"
5. After 2 seconds of silence, bot transcribes
6. Bot responds to the transcribed text

---

## Integration Examples

### Full Conversation Flow with All Features

```python
# In chat command
async def chat(interaction, message):
    # 1. Load history with multi-user tracking
    history = await history_manager.load_history(channel_id)

    # 2. Add message with user attribution
    await history_manager.add_message(
        channel_id=channel_id,
        role="user",
        content=message,
        username=str(interaction.user.name),
        user_id=interaction.user.id
    )

    # 3. Build enhanced context
    context_parts = [
        SystemContextProvider.get_compact_context(),  # Time-aware
        history_manager.build_multi_user_context(history),  # Multi-user
    ]

    # 4. Add memory recall
    if summarizer:
        memory_context = await summarizer.build_memory_context(message)
        if memory_context:
            context_parts.append(memory_context)

    # 5. Build final prompt
    full_prompt = "\n".join(context_parts) + "\n\n" + system_prompt

    # 6. Stream response
    full_response = ""
    response_message = None

    async for chunk in ollama.chat_stream(history, system_prompt=full_prompt):
        full_response += chunk

        # Update every 1 second
        if not response_message:
            response_message = await interaction.followup.send(full_response)
        else:
            await response_message.edit(content=full_response)

        await asyncio.sleep(Config.STREAM_UPDATE_INTERVAL)

    # 7. Save to history
    await history_manager.add_message(channel_id, "assistant", full_response)

    # 8. Check if we should summarize
    if len(history) >= Config.AUTO_SUMMARIZE_THRESHOLD:
        participants = history_manager.get_conversation_participants(history)
        await summarizer.summarize_and_store(
            messages=history,
            channel_id=channel_id,
            participants=[p["username"] for p in participants]
        )
```

---

## Performance Considerations

### Memory Management
- Background cleanup runs every 6 hours (low impact)
- Archival is asynchronous and non-blocking

### Response Streaming
- Network bandwidth: ~1 KB/s during streaming
- Discord rate limits: Max 5 edits per 5 seconds (our 1s interval is safe)

### Conversation Summarization
- CPU intensive: Uses Ollama for summarization
- Runs asynchronously - doesn't block chat
- Recommended: Run on channels with >30 messages

### Whisper STT
- **GPU highly recommended** for real-time transcription
- `tiny` model: ~10 seconds for 30s audio (CPU)
- `base` model: ~15 seconds for 30s audio (CPU)
- `tiny` model: ~1 second for 30s audio (CUDA)
- `base` model: ~2 seconds for 30s audio (CUDA)

---

## Troubleshooting

### Memory Management
**Issue**: Cleanup not running
- Check `MEMORY_CLEANUP_ENABLED=true`
- Verify background task started in logs

### Response Streaming
**Issue**: Responses not streaming
- Check `RESPONSE_STREAMING_ENABLED=true`
- Verify Ollama supports streaming (it does)
- Check Discord rate limits

### Conversation Summarization
**Issue**: Summaries not appearing in RAG
- Verify `RAG_ENABLED=true`
- Check `STORE_SUMMARIES_IN_RAG=true`
- Ensure RAG documents path exists

### Whisper STT
**Issue**: "Whisper not available"
```bash
pip install openai-whisper
```

**Issue**: Slow transcription
- Use smaller model size (tiny/base)
- Enable GPU: `WHISPER_DEVICE=cuda`
- Reduce recording duration

**Issue**: Out of memory
- Use smaller model:  `WHISPER_MODEL_SIZE=tiny`
- Switch to CPU: `WHISPER_DEVICE=cpu`

---

## Future Enhancements

### Planned Features
- [ ] Web dashboard for memory statistics
- [ ] `/recall` command for searching past conversations
- [ ] Voice commands integration (`/listen` command)
- [ ] Conversation export/import
- [ ] Smart summarization triggers (not just message count)
- [ ] Multi-language auto-detection for Whisper
- [ ] Real-time voice command processing
- [ ] Conversation branching and timeline views

---

## Credits

**Implemented Features**:
- Memory Management System
- Dynamic Context Injection
- Multi-User Conversation Tracking
- Response Streaming
- Conversation Summarization with RAG
- Voice Activity Detection (Whisper STT)

**Technologies Used**:
- OpenAI Whisper (Speech Recognition)
- Ollama (LLM & Summarization)
- Discord.py (Bot Framework)
- aiohttp (Async HTTP)
- psutil (System Monitoring)

---

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the configuration options
3. Check the logs for error messages
4. Open an issue on GitHub

**Generated with Claude Code** 🤖
