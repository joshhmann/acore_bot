# System Workflows Documentation

This directory contains comprehensive documentation for acore_bot's system workflows and feature implementations.

## Overview

The acore_bot uses a **modular system architecture** with clear separation of concerns across different feature domains. Each feature is implemented as a self-contained module with its own services, commands, and documentation.

## Document Structure

```
system_workflows/
├── README.md                    # This file - Overview and index
├── chat_conversation.md          # Chat and conversation system workflows
├── voice_audio.md              # Voice, TTS, and audio processing workflows
├── music_media.md              # Music playback and media management workflows
├── persona_management.md        # Persona system and character management workflows
├── user_management.md           # User profiles and learning system workflows
├── system_administration.md    # Bot administration and system command workflows
├── monitoring_analytics.md      # Performance monitoring and analytics workflows
├── games_entertainment.md       # Games and entertainment feature workflows
├── utilities_tools.md          # Utility commands and helper tool workflows
├── api_integrations.md         # External API integration workflows
├── deployment_operations.md     # Deployment and operational procedures
└── troubleshooting.md           # Common issues and troubleshooting procedures
```

## Quick Reference

| Workflow | Status | Key Components | Primary Files |
|----------|--------|------------------|-------------|
| Chat & Conversation | ✅ Complete | ChatCog, LLM, Memory, Persona | `cogs/chat/`, `services/llm/`, `services/memory/` |
| Voice & Audio | ✅ Complete | VoiceCog, TTS, RVC, STT | `cogs/voice/`, `services/voice/` |
| Music & Media | ✅ Complete | MusicCog, YouTube Integration | `cogs/music.py`, `services/music_player.py` |
| Persona Management | ✅ Complete | PersonaRouter, Character Importer | `services/persona/`, `cogs/character_commands.py` |
| User Management | ✅ Complete | User Profiles, Affection System | `services/discord/profiles.py` |
| System Admin | ✅ Complete | SystemCog, Health Checks | `cogs/system.py` |
| Monitoring | ✅ Complete | Metrics Service, Analytics Dashboard | `services/core/metrics.py`, `services/analytics/` |
| Games & Entertainment | ⚠️ Partial | Trivia, Reaction System | `cogs/trivia.py` |
| Utilities | ✅ Complete | Reminders, Notes, Web Search | Multiple service files |
| API Integrations | ✅ Complete | OpenRouter, External APIs | `services/llm/openrouter.py` |

## Feature Architecture Patterns

### 1. Service-Oriented Architecture
All features follow the **Service Factory Pattern**:

```python
# Services created in dependency order
class ServiceFactory:
    def create_services(self):
        self._init_core()      # Metrics, Context, Rate Limiting
        self._init_llm()       # LLM providers
        self._init_audio()     # TTS, RVC, STT
        self._init_memory()    # RAG, History, Profiles
        self._init_features()  # Search, Reminders, Notes
        self._init_ai_systems() # Persona, Tools, Evolution
        return self.services
```

### 2. Cog-Based Discord Integration
Features are exposed through Discord cogs with dependency injection:

```python
# Cog constructor receives all dependencies
class ChatCog(commands.Cog):
    def __init__(self, bot, ollama, persona_system, user_profiles, ...):
        self.bot = bot
        self.ollama = ollama
        self.persona_system = persona_system
        # ... other dependencies
```

### 3. Async-First Design
All I/O operations use async/await patterns:

```python
# LLM calls
response = await ollama.chat(messages)

# File operations
async with aiofiles.open(path, 'r') as f:
    content = await f.read()

# HTTP requests
async with aiohttp.ClientSession() as session:
    async with session.get(url) as resp:
        data = await resp.json()
```

### 4. Configuration-Driven Behavior
All features controlled via environment variables:

```python
# Feature flags
CHAT_HISTORY_ENABLED = os.getenv("CHAT_HISTORY_ENABLED", "true").lower() == "true"
VOICE_ENABLED = os.getenv("VOICE_ENABLED", "true").lower() == "true"
PERSONA_SYSTEM_ENABLED = os.getenv("USE_PERSONA_SYSTEM", "true").lower() == "true"

# Service configuration
TTS_ENGINE = os.getenv("TTS_ENGINE", "kokoro_api")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
```

## Implementation Guidelines

### 1. Adding New Features
1. Create service interface in `services/interfaces/`
2. Implement service class inheriting from interface
3. Register service in `ServiceFactory._init_*()`
4. Create cog class with dependency injection
5. Register cog in main.py
6. Add configuration options
7. Write comprehensive tests
8. Update documentation

### 2. Service Development Pattern
```python
# 1. Define interface
class MyFeatureService(ABC):
    @abstractmethod
    async def process(self, data: Dict) -> Any:
        pass

# 2. Implement service
class MyFeatureService(MyFeatureService):
    def __init__(self, config: Dict):
        self.config = config
    
    async def process(self, data: Dict) -> Any:
        # Implementation
        return result

# 3. Register in factory
def _init_features(self):
    if Config.MY_FEATURE_ENABLED:
        self.services['my_feature'] = MyFeatureService(
            host=Config.MY_FEATURE_HOST,
            port=Config.MY_FEATURE_PORT
        )
```

### 3. Cog Development Pattern
```python
# 1. Create cog with dependency injection
class MyFeatureCog(commands.Cog):
    def __init__(self, bot, my_service, other_deps):
        self.bot = bot
        self.my_service = my_service
        self.other_deps = other_deps

# 2. Add slash commands
    @app_commands.command()
    async def my_command(self, ctx, arg: str):
        result = await self.my_service.process({"arg": arg})
        await ctx.respond(f"Result: {result}")

# 3. Register in main.py
await self.add_cog(MyFeatureCog(
    bot,
    my_service=self.services.get('my_feature'),
    other_deps=self.services.get('other_service')
))
```

### 4. Error Handling Pattern
```python
# 1. Specific exceptions
try:
    result = await risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    raise MyFeatureError(f"Could not process: {e}")
except Exception as e:
    logger.error(f"Unexpected error in my_feature: {e}")
    # Fallback handling
    fallback_result = await self.fallback_service.process(data)
    return fallback_result
```

### 5. Testing Strategy
```python
# 1. Unit tests for services
@pytest.mark.asyncio
async def test_my_service_success():
    service = MyFeatureService(test_config)
    result = await service.process({"test": "data"})
    assert result["success"] is True

# 2. Integration tests for cogs
@pytest.mark.asyncio
async def test_my_cog_command():
    cog = MyFeatureCog(mock_bot, mock_service, {})
    result = await cog.my_command(ctx_mock, "test")
    assert result == "Expected result"
```

## Getting Started

1. **Read This Overview**: Understand the system architecture
2. **Choose Workflow Document**: Select the relevant workflow document for your feature area
3. **Follow Implementation Guidelines**: Use the established patterns for consistency
4. **Consult Feature Documentation**: Refer to specific workflow documents for detailed implementation guidance
5. **Test Thoroughly**: Ensure comprehensive test coverage
6. **Update Documentation**: Keep documentation in sync with code changes

## Support

For questions about specific features or workflows:
- 📧 Check the relevant workflow document
- 🔧 Consult the service implementation directly
- 🐛 Review the cog and service code for patterns
- 📋 Use the troubleshooting guide for common issues

---

**Last Updated**: 2025-12-16
**Architecture Version**: 2.1
**Bot Version**: 4.5.0