"""Chat cog package - refactored from monolithic 2,576-line chat.py for maintainability.

## Refactoring Summary (Phase 3)

Original structure:
- cogs/chat.py: 2,576 lines (monolithic file)

New modular structure:
- main.py: 2,207 lines (core ChatCog with response handling)
- helpers.py: 193 lines (text processing utilities)
- session_manager.py: 126 lines (conversation session lifecycle)
- voice_integration.py: 154 lines (TTS and voice channel integration)

## Module Responsibilities

**helpers.py** - Text processing and utility functions
- ChatHelpers.replace_mentions_with_names() - Convert Discord mentions to @username
- ChatHelpers.restore_mentions() - Convert @username back to Discord mentions
- ChatHelpers.clean_for_tts() - Clean text for natural TTS pronunciation
- ChatHelpers.analyze_sentiment() - Simple sentiment analysis
- ChatHelpers.load_system_prompt() - Load prompt from file or default

**session_manager.py** - Conversation session management
- SessionManager.start_session() - Start/refresh conversation session
- SessionManager.refresh_session() - Extend session timeout
- SessionManager.is_session_active() - Check session status
- SessionManager.end_session() - Manually end session
- SessionManager.update_response_time() - Track last response time
- SessionManager.get_last_response_time() - Get last response timestamp

**voice_integration.py** - Voice and TTS integration
- VoiceIntegration.speak_response_in_voice() - Generate and play TTS in voice channel

**main.py** - Core ChatCog orchestrator
- Slash commands (/chat, /ambient, /end_session)
- Implicit message handling (check_and_handle_message)
- Response generation (_handle_chat_response)
- Multi-service integration (LLM, RAG, profiles, etc.)

## Benefits
- ✓ Improved code organization and readability
- ✓ Better separation of concerns
- ✓ Easier to test individual components
- ✓ Reduced cognitive load when navigating code
- ✓ Main file reduced by 369 lines (14.3% reduction)
"""

from .main import ChatCog

__all__ = ["ChatCog"]
