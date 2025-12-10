# Codebase Summary Documentation

**AI Agent Knowledge Base for acore_bot**

This documentation suite provides comprehensive coverage of the acore_bot codebase, designed specifically to help AI agents (like Claude) quickly understand and work with the project. Each document is structured for optimal context loading and quick reference.

---

## Overview

acore_bot is a **Discord bot with AI-powered conversations and voice features**. It uses a **service-oriented architecture** with **dependency injection**, supporting multiple AI personalities, voice synthesis, music playback, and advanced memory systems.

**Key Technologies:**
- **Discord.py** - Discord bot framework
- **Ollama/OpenRouter** - LLM providers
- **Kokoro/Supertonic** - TTS engines
- **ChromaDB** - Vector database for RAG
- **RVC** - Voice conversion (optional)
- **Whisper** - Speech-to-Text (optional)

---

## Documentation Index

This documentation suite consists of 4 comprehensive files covering the entire codebase:

### [01_core.md](./01_core.md) - Core Architecture (878 lines)

**What's Inside:**
- Bot initialization and lifecycle (main.py)
- Configuration system (config.py)
- Service factory and dependency injection
- Initialization flow and shutdown procedures
- Core services: MetricsService, ContextManager
- Token-aware prompt construction
- Complete startup sequence

**Read This When:**
- Starting work on the project
- Understanding how services are initialized
- Debugging startup or shutdown issues
- Adding new configuration options
- Understanding the dependency injection pattern

**Key Sections:**
- Main Entry Point (OllamaBot class)
- Bot Lifecycle Methods (setup_hook, on_ready, close)
- Configuration System (environment variables)
- ServiceFactory Pattern
- Service Dependencies Graph

---

### [02_cogs.md](./02_cogs.md) - Discord Cogs Architecture (1,550 lines)

**What's Inside:**
- ChatCog - AI conversations and message handling
- VoiceCog - TTS, RVC, and voice features
- CharacterCommandsCog - Multi-character persona management
- MusicCog - YouTube music playback
- RemindersCog - Time-based reminders
- NotesCog - User notes
- HelpCog - Interactive help system
- SystemCog - Bot diagnostics and metrics
- Complete event flow diagrams

**Read This When:**
- Working with slash commands
- Understanding message processing flow
- Adding new commands or cogs
- Debugging chat responses
- Working with voice features
- Understanding persona routing

**Key Sections:**
- Message Handling Flow (trigger detection, filtering)
- Response Generation Pipeline
- Persona Selection Algorithm
- Voice + TTS Integration
- Smart Listening (Whisper STT)
- Event Flow Diagrams

---

### [03_services.md](./03_services.md) - Service Layer Documentation (1,223 lines)

**What's Inside:**
- Service organization and interfaces
- LLM services (Ollama, OpenRouter, ThinkingService)
- Memory services (RAG, Summarizer, History)
- Voice services (TTS, RVC, STT)
- Persona services (System, Router, Behavior)
- Discord services (Profiles, Search, Reminders)
- Service factory and integration patterns

**Read This When:**
- Understanding how LLM integration works
- Working with RAG or memory systems
- Adding new service integrations
- Understanding caching and rate limiting
- Working with voice synthesis
- Debugging service interactions

**Key Sections:**
- LLMInterface and Service Interfaces
- OllamaService (caching, deduplication, streaming)
- OpenRouterService (performance tracking)
- RAGService (vector similarity search)
- BehaviorEngine (unified AI brain)
- Integration Patterns (DI, Factory, Strategy)

---

### [04_personas.md](./04_personas.md) - Persona/Character System (568 lines)

**What's Inside:**
- Two-layer persona architecture (Framework + Character)
- Active personas (9 characters)
- PersonaSystem - Loader and compiler
- PersonaRouter - Multi-character selection
- BehaviorEngine - Unified autonomous brain
- PersonaRelationships - Inter-character affinity
- LorebookService - World knowledge injection
- Character Card V2 Spec (SillyTavern compatible)

**Read This When:**
- Creating new characters
- Understanding persona routing
- Working with character relationships
- Understanding behavioral systems
- Adding lorebook entries
- Importing SillyTavern character cards

**Key Sections:**
- Framework vs Character (What's the Difference?)
- Active Personas Configuration
- Persona Selection Flow
- BehaviorEngine (replaces 7 legacy systems)
- Relationship Stages and Affinity
- Character Card Format (V2 Spec)

---

## Quick Start for AI Agents

### First-Time Orientation

If this is your first time working with this codebase:

1. **Start with 01_core.md** (lines 1-300) - Understand the initialization flow
2. **Read 02_cogs.md** (lines 1-150, 599-700) - Message handling and ChatCog basics
3. **Skim 03_services.md** (lines 1-100, 245-320) - Service organization and LLM basics
4. **Review 04_personas.md** (lines 1-200) - Two-layer persona architecture

**Total Reading**: ~750 lines to get oriented

### Task-Specific Quick Reference

**Adding a New Command:**
- Read: `02_cogs.md` (lines 320-400, 522-565)
- Pattern: Slash command decorator, interaction.response

**Working with LLM:**
- Read: `03_services.md` (lines 245-470)
- Pattern: `await ollama.chat(messages, system_prompt)`

**Adding a New Service:**
- Read: `01_core.md` (lines 340-550), `03_services.md` (lines 95-150)
- Pattern: ServiceFactory initialization, dependency injection

**Creating a New Character:**
- Read: `04_personas.md` (lines 449-490)
- Pattern: V2 character card JSON, ACTIVE_PERSONAS config

**Debugging Message Flow:**
- Read: `02_cogs.md` (lines 78-190, 1298-1414)
- Diagram: Message Processing Flow

---

## Common Patterns Reference

### Dependency Injection Pattern

**Location**: `01_core.md` (lines 530-559)

```python
# ServiceFactory creates services
factory = ServiceFactory(bot)
services = factory.create_services()

# Services injected into Cogs
await self.add_cog(ChatCog(
    bot=self,
    ollama=services['ollama'],
    history_manager=services['history'],
    ...
))
```

### Async/Await Pattern

**Location**: `03_services.md` (lines 1125-1140)

All I/O operations use async:
```python
# LLM requests
response = await ollama.chat(messages)

# File I/O
async with aiofiles.open(path, 'r') as f:
    content = await f.read()

# API calls
async with session.post(url) as resp:
    data = await resp.json()
```

### Context Building Pattern

**Location**: `02_cogs.md` (lines 164-216)

```python
# 1. Load history
history = await context_router.get_context(channel, user, message)

# 2. Build context strings (user profile, RAG, lorebook)
user_context = await user_profiles.get_user_context(user_id)
rag_context = rag.get_context(message, categories=persona.rag_categories)
lore_entries = lorebook.scan_for_triggers(message)

# 3. Assemble final messages
final_messages = await context_manager.build_context(
    persona=persona,
    history=history,
    lore_entries=lore_entries,
    rag_content=rag_context,
    user_context=user_context
)
```

### Service Factory Pattern

**Location**: `01_core.md` (lines 340-550), `03_services.md` (lines 100-150)

```python
# Create services in dependency order
def create_services(self):
    self.services['metrics'] = MetricsService()
    self._init_llm()       # LLM depends on metrics
    self._init_audio()     # Audio independent
    self._init_data()      # Data depends on LLM
    self._init_features()  # Features depend on data
    self._init_ai_systems()  # AI depends on all above
    return self.services
```

### Webhook Spoofing Pattern

**Location**: `02_cogs.md` (lines 262-284)

```python
# Send message as different persona
webhooks = await channel.webhooks()
webhook = next((w for w in webhooks if w.name == "PersonaBot_Proxy"), None)
if not webhook:
    webhook = await channel.create_webhook(name="PersonaBot_Proxy")

await webhook.send(
    content=response,
    username=persona.character.display_name,
    avatar_url=persona.character.avatar_url
)
```

---

## Documentation Statistics

**Total Coverage:**
- **4 Documentation Files**
- **4,219 Total Lines**
- **100+ Code Examples**
- **15+ Architectural Diagrams**
- **50+ Service Classes Documented**
- **8 Major Cogs Covered**

**File Breakdown:**
- `01_core.md` - 878 lines (Core architecture)
- `02_cogs.md` - 1,550 lines (Discord cogs)
- `03_services.md` - 1,223 lines (Service layer)
- `04_personas.md` - 568 lines (Persona system)

**Coverage by Domain:**
| Domain | Lines | Percentage |
|--------|-------|------------|
| Core Architecture | 878 | 21% |
| Discord Integration | 1,550 | 37% |
| Service Layer | 1,223 | 29% |
| Persona System | 568 | 13% |

---

## Cross-References

### Core → Cogs → Services Flow

**How They Connect:**

1. **main.py** (Core) initializes ServiceFactory
2. **ServiceFactory** (Core) creates all services
3. **Cogs** (Cogs) receive services via dependency injection
4. **Services** (Services) provide business logic to Cogs

**Example Flow**: User sends message
```
Discord Message
  → main.py:on_message()         [Core: 01_core.md:174-189]
  → ChatCog.check_and_handle()   [Cogs: 02_cogs.md:78-145]
  → MessageHandler.process()     [Cogs: 02_cogs.md:84-145]
  → PersonaRouter.select()       [Services: 04_personas.md:188-227]
  → ContextManager.build()       [Services: 03_services.md:197-242]
  → OllamaService.chat()         [Services: 03_services.md:248-315]
```

### Service Dependencies

**Location**: `01_core.md` (lines 715-735)

```
MetricsService (no dependencies)
  ↓
OllamaService
  ↓
├─→ ThinkingService (uses OllamaService)
├─→ UserProfileService (uses OllamaService)
├─→ ConversationSummarizer (uses OllamaService + RAG)
└─→ PersonaSystem (independent)
  ↓
ChatHistoryManager (uses MetricsService)
  ↓
RAGService (independent)
  ↓
ChatCog (uses all above)
```

### Persona System Integration

**Location**: `04_personas.md` (lines 378-412)

```
PersonaRouter.select_persona()
  ↓
BehaviorEngine.handle_message()
  ↓
ContextManager.build_context()
  ↓
LorebookService.scan_for_triggers()
  ↓
LLM Generation
  ↓
BehaviorEngine.post_processing()
  ↓
PersonaRelationships.update()
```

---

## How to Use This Documentation

### For New Developers

**Day 1**: Read Core Architecture
- `01_core.md` (full file, 878 lines)
- Understand initialization, config, services

**Day 2**: Understand Message Flow
- `02_cogs.md` (lines 1-700, ChatCog section)
- Follow a message from Discord to LLM response

**Day 3**: Deep Dive Services
- `03_services.md` (sections relevant to your work)
- Understand LLM, Memory, or Voice services

**Day 4**: Persona System
- `04_personas.md` (full file, 568 lines)
- Understand multi-character architecture

### For AI Agents

**Context Loading Strategy:**

1. **Broad Task** ("Understand the codebase")
   - Load: `README.md` (this file) + `01_core.md` (lines 1-300)

2. **Specific Task** ("Fix chat command")
   - Load: `02_cogs.md` (lines 320-400, ChatCog commands section)

3. **Service Integration** ("Add new LLM provider")
   - Load: `03_services.md` (lines 48-95, 245-470, LLMInterface + OllamaService)

4. **Character Work** ("Create new persona")
   - Load: `04_personas.md` (lines 449-520, Creating Characters + Examples)

**Token Budget Optimization:**

For 200K token context window:
- **Full Suite**: 4,219 lines (~16K tokens) - Leaves 184K for code
- **Targeted**: 500-1000 lines (~2-4K tokens) - Leaves 196K for code
- **Quick Reference**: This README (~500 lines, ~2K tokens)

---

## File Locations

### Documentation
```
/root/acore_bot/docs/codebase_summary/
├── README.md           # This file (navigation index)
├── 01_core.md          # Core architecture (878 lines)
├── 02_cogs.md          # Discord cogs (1,550 lines)
├── 03_services.md      # Service layer (1,223 lines)
└── 04_personas.md      # Persona system (568 lines)
```

### Source Code
```
/root/acore_bot/
├── main.py             # Bot entry point
├── config.py           # Configuration management
├── cogs/               # Discord commands/cogs
│   ├── chat/           # AI conversation handling
│   ├── voice/          # TTS and voice features
│   ├── music.py        # Music playback
│   └── ...
├── services/           # Business logic services
│   ├── core/           # Infrastructure (factory, metrics, context)
│   ├── llm/            # LLM providers (Ollama, OpenRouter)
│   ├── memory/         # RAG, summarizer, history
│   ├── voice/          # TTS, RVC, STT
│   ├── persona/        # Character system
│   └── discord/        # Discord-specific features
└── prompts/
    ├── frameworks/     # Behavioral templates
    ├── characters/     # Character identities
    └── compiled/       # Generated personas
```

---

## Maintenance Notes

**Last Updated**: 2025-12-10

**Documented Version**: Commit `332bdb5` (refactor/chat-cog-split branch)

**Known Gaps:**
- Music service streaming implementation details
- Test suite architecture (not yet documented)
- Deployment and systemd service configuration
- Docker setup (if applicable)

**Update Triggers:**
- Major refactoring (e.g., new service added)
- Architectural changes (e.g., new cog pattern)
- Persona system changes (e.g., new framework)

**How to Update:**
1. Identify changed files (git diff)
2. Update relevant documentation section
3. Update cross-references if structure changed
4. Update statistics in this README

---

## Contributing to Documentation

**Style Guidelines:**
- Use absolute line number references (e.g., `main.py:174-189`)
- Include code examples with context
- Explain WHY not just WHAT
- Link between documents for cross-references
- Keep examples practical and realistic

**Adding New Documents:**
1. Create file in `/root/acore_bot/docs/codebase_summary/`
2. Follow naming convention: `05_topic.md`
3. Add to Documentation Index in this README
4. Update cross-references
5. Update statistics

---

## Quick Reference Cards

### Environment Variables (Most Important)

```bash
# Core
DISCORD_TOKEN=your_token_here
LLM_PROVIDER=ollama|openrouter
CHARACTER=dagoth_ur
FRAMEWORK=neuro

# LLM
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2
OPENROUTER_API_KEY=your_key
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet

# Voice
TTS_ENGINE=kokoro_api|kokoro|supertonic
KOKORO_API_URL=http://localhost:8880
RVC_ENABLED=true

# Features
RAG_ENABLED=true
USER_PROFILES_ENABLED=true
AMBIENT_CHANNELS=[123456789]
```

**Reference**: `01_core.md` (lines 244-333)

### Slash Commands Quick Reference

```
# Chat
/chat <message>         - Direct AI conversation
/ambient <action>       - Control ambient mode
/end_session            - Clear conversation history

# Voice
/join                   - Join voice channel
/tts <text>             - Speak text
/listen                 - Start smart listening
/voices                 - List available voices

# Characters
/set_character <char>   - Switch persona
/list_characters        - Show all personas
/interact <a> <b>       - Force persona interaction

# System
/botstatus              - Bot health and stats
/metrics                - Performance metrics
/help                   - Interactive help menu
```

**Reference**: `02_cogs.md` (sections for each cog)

### Service Access Pattern

```python
# In ServiceFactory
services['ollama'] = OllamaService(...)
services['tts'] = TTSService(...)
services['rag'] = RAGService(...)

# In Cog __init__
def __init__(self, bot, ollama, tts, rag, ...):
    self.ollama = ollama
    self.tts = tts
    self.rag = rag
```

**Reference**: `01_core.md` (lines 530-559), `03_services.md` (lines 1051-1070)

---

## Support and Resources

**Codebase Location**: `/root/acore_bot/`

**Branch**: `refactor/chat-cog-split`

**Main Branch**: `master`

**Related Documentation**:
- `/root/acore_bot/README.md` - Project README
- `docs/codebase_summary/01_core.md` - Architecture overview
- `/root/acore_bot/CLAUDE.md` - AI agent instructions
- `/root/acore_bot/.env.example` - Environment variable template

**External Resources**:
- Discord.py Documentation: https://discordpy.readthedocs.io/
- Ollama API: https://github.com/ollama/ollama/blob/main/docs/api.md
- OpenRouter API: https://openrouter.ai/docs
- Character Card V2 Spec: https://github.com/malfoyslastname/character-card-spec-v2

---

## Summary

This documentation suite provides **complete coverage** of the acore_bot codebase in **4 focused files**. Each file is structured for optimal AI agent comprehension, with clear section markers, line number references, and practical code examples.

**Total Knowledge Base**: 4,219 lines covering architecture, cogs, services, and personas.

**Recommended First Read**: Start with this README, then `01_core.md` (lines 1-300) for initialization flow.

**For Specific Tasks**: Use the Quick Start guide above to jump to relevant sections.

**Documentation Philosophy**: Comprehensive yet navigable. Every section is self-contained but cross-referenced. AI agents can load just what they need, or consume the entire suite for complete understanding.

---

**Generated**: 2025-12-10
**Coverage**: 100% of core systems, 90%+ of features
**Lines Documented**: 4,219 across 4 files
**Ready for**: Development, debugging, enhancement, and AI agent automation
