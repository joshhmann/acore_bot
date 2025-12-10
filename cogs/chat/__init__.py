"""Chat cog package - refactored from monolithic 2,576-line chat.py for maintainability.

## Refactoring Summary (Phase 3)

Original structure:
- cogs/chat.py: 2,576 lines (monolithic file)

New modular structure:
- main.py: Core ChatCog orchestrator (Facade)
- response_handler.py: LLM response generation logic
- context_builder.py: Context construction (history, RAG, etc.)
- message_handler.py: Message routing and side-effects
- commands.py: Slash command implementations
- helpers.py: Text processing utilities
- session_manager.py: Conversation session lifecycle
- voice_integration.py: Voice and TTS integration

## Module Responsibilities

**response_handler.py** - Response Generation
- _handle_chat_response() - Main response logic

**context_builder.py** - Context Management
- build_context() - Assemble system prompt + history + data

**message_handler.py** - Message Processing
- check_and_handle_message() - Main entry point for messages
- _track_interesting_topic() - Background topic tracking
- _safe_learn_from_conversation() - Background learning

**commands.py** - Commands
- chat(), ambient(), end_session() implementations

**main.py** - Orchestration
- Component initialization
- Event listening (on_message)
- Delegation

## Benefits
- ✓ Improved code organization and readability
- ✓ Better separation of concerns
- ✓ Significantly reduced main.py size (~1200 lines)
"""

from .main import ChatCog

__all__ = ["ChatCog"]
