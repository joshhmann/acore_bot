# PROJECT KNOWLEDGE BASE

**Generated:** 2025-01-07 09:53:40 PM
**Parent:** ./AGENTS.md

## OVERVIEW

Discord.py extension cogs with slash commands, message handling, voice integration, and multi-agent persona system.

## STRUCTURE

```
cogs/
├── chat/           # Main chat system (5 files)
├── voice/          # Voice commands and TTS
├── profile_commands.py    # User profile management
├── character_commands.py   # Character import/export
├── reminders.py     # Reminder system
├── search_commands.py  # Search integration
├── help.py          # Help system
├── music.py         # Music playback
├── notes.py         # Note taking
└── system.py        # Bot system commands
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add Discord command | `cogs/chat/commands.py` | Extend commands.Bot |
| Modify message handling | `cogs/chat/message_handler.py` | Response triggers |
| Update persona system | `cogs/chat/helpers.py` | Helper functions |
| Add voice command | `cogs/voice/commands.py` | Voice interaction |
| Debug TTS pipeline | `cogs/chat/main.py` | Webhook streaming |

## CONVENTIONS

**Discord.py Patterns:**
- Slash commands using `@app_commands.command()`
- Message handling via `on_message` event
- Webhook creation for persona responses
- Async/await patterns throughout

**Multi-Agent Support:**
- Persona routing via `PersonaRouter`
- Webhook integration for character responses
- Multi-persona interaction handling
- Conflict modifiers for persona relationships

## ANTI-PATTERNS (THIS PROJECT)

**Legacy Code:**
- Deprecated response handler (still referenced)
- Legacy ambient mode logic
- Old persona selection patterns

**Response Loops:**
- 50% decay for persona-to-persona responses
- Self-response prevention
- Multi-turn conversation tracking