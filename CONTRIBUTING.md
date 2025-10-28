# Contributing to Discord AI Bot

Thank you for your interest in contributing! This guide will help you get started.

## Development Setup

### 1. Fork & Clone

```bash
git clone https://github.com/YOUR_USERNAME/acore_bot.git
cd acore_bot
```

### 2. Create Virtual Environment

```bash
python -m venv .venv311
source .venv311/bin/activate  # Linux/Mac
# or
.venv311\Scripts\activate  # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings
```

### 5. Install Ollama & Model

```bash
# Install Ollama from https://ollama.ai
ollama serve
ollama pull l3-8b-stheno-v3.2
```

## Project Structure

```
acore_bot/
├── main.py              # Bot entry point
├── config.py            # Configuration management
├── cogs/                # Discord command groups
│   ├── chat.py         # Chat & AI commands
│   └── voice.py        # Voice & TTS commands
├── services/            # Core services
│   ├── ollama.py       # LLM integration
│   ├── kokoro_tts.py   # TTS service
│   ├── rvc_http.py     # Voice conversion
│   └── user_profiles.py # User memory system
├── utils/               # Utilities
│   ├── helpers.py      # Chat history
│   ├── persona_loader.py # Persona management
│   └── system_context.py # Context injection
├── prompts/             # Persona prompt files
├── docs/                # Documentation
│   ├── setup/          # Setup guides
│   └── features/       # Feature docs
└── tests/              # Test scripts
```

## Making Changes

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Your Changes

- Follow existing code style
- Add docstrings to functions/classes
- Keep commits focused and atomic
- Write clear commit messages

### 3. Test Your Changes

```bash
# Run the bot
python main.py

# Test specific features
python tests/test_bot.py
```

### 4. Commit & Push

```bash
git add .
git commit -m "Add: brief description of changes"
git push origin feature/your-feature-name
```

### 5. Create Pull Request

- Go to GitHub and create a PR
- Describe your changes clearly
- Link any related issues

## Code Style

- **Python**: Follow PEP 8
- **Imports**: Standard library → Third party → Local imports
- **Naming**:
  - Classes: `PascalCase`
  - Functions/variables: `snake_case`
  - Constants: `UPPER_CASE`
- **Docstrings**: Use for all public methods

## Adding Features

### New Commands

Add commands to appropriate cog (`cogs/chat.py` or `cogs/voice.py`):

```python
@app_commands.command(name="mycommand", description="My new command")
async def my_command(self, interaction: discord.Interaction):
    await interaction.response.send_message("Hello!")
```

### New Services

Create new service in `services/`:

```python
class MyService:
    """Service for doing something."""

    def __init__(self):
        """Initialize service."""
        pass

    async def do_something(self) -> str:
        """Do something useful."""
        return "result"
```

### New Personas

Create `prompts/persona_name.txt`:

```
You are [Character Name], a [description].

Personality traits:
- Trait 1
- Trait 2

Example responses:
User: Hello!
Assistant: [Response in character]
```

## Testing

### Manual Testing

1. Start bot: `python main.py`
2. Test commands in Discord
3. Check logs for errors

### Test Scripts

Located in `tests/`:
- `test_bot.py` - Full integration test
- `test_rvc_http.py` - RVC conversion test
- `check_bot_status.py` - Service health check

## Documentation

When adding features:

1. Update relevant docs in `docs/`
2. Add to README.md if major feature
3. Include usage examples

## Commit Message Format

```
Type: Brief description

Detailed explanation if needed

Examples:
- Add: New feature implementation
- Fix: Bug fix description
- Update: Improve existing feature
- Docs: Documentation changes
- Refactor: Code restructuring
```

## Questions?

- Open an issue for bugs
- Discussions for questions
- PRs for contributions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
