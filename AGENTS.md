# PROJECT KNOWLEDGE BASE

**Generated:** 2025-01-23 08:30:06 PM
**Commit:** b9c24a1
**Branch:** master

## OVERVIEW

Discord bot with multi-agent AI persona system, voice capabilities, and sophisticated memory/relationship tracking.

## STRUCTURE

```
./
├── main.py                    # Bot entry point
├── config.py                  # Configuration management
├── cogs/                      # Discord extensions (commands, voice)
├── services/                  # Core business logic (LLM, persona, memory)
├── utils/                     # Helper utilities
├── prompts/                   # Character definitions and frameworks
├── tests/                     # Tiered testing system
├── scripts/                   # Performance and migration scripts
└── docs/                      # Comprehensive documentation
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Bot startup | `main.py` | Discord.py client initialization |
| Add Discord command | `cogs/chat/commands.py` | Slash commands |
| Service architecture | `services/core/factory.py` | Factory pattern |
| Persona behavior | `services/persona/behavior.py` | AI personality engine |
| Voice features | `services/voice/` | TTS/STT/RVC pipeline |
| Testing | `tests/conftest.py` | Extensive mocking fixtures |
| Performance | `scripts/` | Benchmarking tools |

## CONVENTIONS

**Factory Pattern**: All services via `ServiceFactory` in `services/core/`
**Async First**: Discord interactions must be async
**Tiered Testing**: 4 levels (unit/integration/e2e/slow) with 70% coverage minimum
**Persona System**: JSON character definitions with relationship tracking
**No Runtime Data**: User data belongs in `~/.acore_bot/`, not git

## ANTI-PATTERNS (THIS PROJECT)

**Never import from `services/deprecated/`** - Legacy code, replaced by BehaviorEngine
**Never commit runtime data** - `data/`, `logs/`, `.venv/` belong in gitignore
**Never break character** - Roleplaying rules enforced in response validation
**Never sync calls in async context** - All Discord/external calls must be async
**Never guess facts** - Use tools: time, calculate, convert, search

## UNIQUE STYLES

**Multi-Agent Routing**: Bot selects persona based on context/mentions
**Relationship Evolution**: Characters build affinity (0-100) over time
**Memory Isolation**: Each persona maintains separate memories
**Voice Conversion**: RVC for character voice transformation
**Analytics Dashboard**: Real-time metrics web UI

## COMMANDS

```bash
# Development
uv sync                              # Install dependencies  
uv run python main.py                # Run bot
uv run pytest                        # Run tests
uv run python scripts/test_runner.sh # Tiered testing

# Production
sudo ./install_service.sh            # Systemd service
sudo systemctl status discordbot      # Check status
```

## NOTES

**AI Agents**: Must adopt persona from `.promptx/personas/` before working
**Performance**: <5ms overhead per message for all persona features
**Migration**: Legacy .txt persona files auto-convert to JSON
**Monitoring**: Analytics dashboard at `http://localhost:8080` when enabled