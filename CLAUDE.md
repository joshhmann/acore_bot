# AI Assistant Instructions

**IMPORTANT: Copy or merge this file into your project's CLAUDE.md file to activate agent personas.**

## 🚨 MANDATORY PERSONA SELECTION

**CRITICAL: You MUST adopt one of the specialized personas before proceeding with any work.**

**BEFORE DOING ANYTHING ELSE**, you must read and adopt one of these personas:

1. **Developer Agent** - Read `.promptx/personas/agent-developer.md` - For coding, debugging, and implementation tasks
2. **Code Reviewer Agent** - Read `.promptx/personas/agent-code-reviewer.md` - For reviewing code changes and quality assurance
3. **Rebaser Agent** - Read `.promptx/personas/agent-rebaser.md` - For cleaning git history and rebasing changes
4. **Merger Agent** - Read `.promptx/personas/agent-merger.md` - For merging code across branches
5. **Multiplan Manager Agent** - Read `.promptx/personas/agent-multiplan-manager.md` - For orchestrating parallel work and creating plans

**DO NOT PROCEED WITHOUT SELECTING A PERSONA.** Each persona has specific rules, workflows, and tools that you MUST follow exactly.

## How to Choose Your Persona

- **Asked to write code, fix bugs, or implement features?** → Use Developer Agent
- **Asked to review code changes?** → Use Code Reviewer Agent  
- **Asked to clean git history or rebase changes?** → Use Rebaser Agent
- **Asked to merge branches or consolidate work?** → Use Merger Agent
- **Asked to coordinate multiple tasks, build plans, or manage parallel work?** → Use Multiplan Manager Agent

## Project Context

This project uses:
- **Language/Framework**: **Python (3.11+)** using **discord.py** for the bot interface and **Ollama/Kokoro** for AI/Voice services.
- **Build Tool**: **`uv`** for dependency management and execution.
- **Testing**: **`pytest`** via `uv run pytest`.
- **Architecture**: **Component-based Bot** structure with core logic in `main.py`, commands in `cogs/`, and integrations in `services/`.

## Core Principles (All Personas)

1. **READ FIRST**: Always read at least 1500 lines to understand context fully
2. **DELETE MORE THAN YOU ADD**: Complexity compounds into disasters
3. **FOLLOW EXISTING PATTERNS**: Don't invent new approaches
4. **BUILD AND TEST**: Run your build and test commands after changes
5. **COMMIT FREQUENTLY**: Every 5-10 minutes for meaningful progress

## File Structure Reference

acore_bot/ ├── main.py # Bot entry point ├── config.py # Configuration management ├── cogs/ # Discord commands/cogs │ ├── chat.py

│ └── voice.py

├── services/ # External API integrations (Ollama, Kokoro) │ ├── ollama.py

│ └── kokoro_tts.py

├── utils/ # Helper functions ├── prompts/ # Persona prompt files (.txt) ├── tests/ # Test scripts └── CLAUDE.md # This file


## Common Commands (All Personas)

```bash
# Install dependencies
uv sync

# Run project locally
uv run python main.py

# Run tests
uv run pytest                    # Run all tests
uv run pytest tests/unit/        # Run unit tests only
uv run pytest -k test_name        # Run specific test
uv run pytest -v                  # Verbose output
uv run pytest --cov=             # Run with coverage

# Performance testing
./scripts/run_all_tests.sh        # Interactive test menu
uv run python scripts/test_optimizations.py  # Quick validation (no API)
uv run python scripts/test_pipeline_timing.py  # Pipeline timing (API calls)

# Deploy locally (Systemd)
sudo ./install_service.sh
```

## Code Style Guidelines

### Imports & Formatting
- Use `uv run python -m ruff check .` for linting (if ruff is added)
- Standard library imports first, then third-party, then local imports
- Use `from typing import Optional, Dict, List` for type hints
- Maximum line length: 100 characters

### Naming Conventions
- Classes: `PascalCase` (e.g., `ChatHistoryManager`)
- Functions/variables: `snake_case` (e.g., `get_history_file`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `DISCORD_TOKEN`)
- Private methods: prefix with `_` (e.g., `_cache_cleanup`)

### Error Handling
- Use specific exception types (`ValueError`, `KeyError`, etc.)
- Log errors with `logger.error()` before raising
- Use `try/except` blocks for external API calls
- Return `Optional[T]` for functions that may not return a value

### Async/Await
- All Discord interactions and external API calls must be async
- Use `async def` for coroutine functions
- Use `await` for async operations
- Use `asyncio.gather()` for concurrent operations

### Documentation
- Module docstrings at top of every file
- Class docstrings explaining purpose and usage
- Method docstrings with Args/Returns sections
- Use `"""Triple quotes"""` for docstrings

## Documentation Strategy

**CRITICAL RULE: STOP CREATING NEW DOC FILES.**
We avoid clutter ("a ton of docs laying around") by updating central, living documentation.

1.  **Do NOT create new implementation summary files** (e.g., `T05_Implementation_Summary.md`) for every small task.
2.  **Update Existing Docs**:
    *   **Features**: Update files in `docs/features/` with new details.
    *   **Status**: Update `docs/STATUS.md` to reflect progress.
    *   **Reports**: Only use `docs/reports/` for immutable snapshots (reviews, major checkpoints).
3.  **Temporary Files**: If you create a plan (`.agent/plan.md`), **DELETE IT** when the task is done.
4.  **Code is Documentation**: Prioritize excellent docstrings and type hints over external markdown files.


# CRITICAL REMINDER
You CANNOT proceed without adopting a persona. Each persona has:

Specific workflows and rules

Required tools and commands  

Success criteria and verification steps

Commit and progress requirements

Choose your persona now and follow its instructions exactly.

Generated by promptx - Agent personas are in .promptx/personas/