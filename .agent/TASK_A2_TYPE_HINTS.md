# Task A2: Add Missing Type Hints to Public Methods

## Task Description

Based on code analysis, numerous public methods and classes are missing type hints. This violates Python typing best practices and makes the code harder to maintain.

## Files Requiring Type Hints

1. **Main module files with type issues**:
   - `main.py` - Missing type hints for bot attributes and service injection
   - `services/analytics/dashboard.py` - FastAPI types not imported
   - `services/core/factory.py` - RAGService None handling
   - `services/llm/ollama.py` - Method signature mismatches

2. **Chat module issues**:
   - `cogs/chat/main.py` - Multiple attribute access errors, missing types
   - `cogs/chat/message_handler.py` - Extensive attribute access issues

3. **Service layer issues**:
   - `services/memory/rag.py` - ChromaDB type mismatches
   - `services/voice/tts.py` - Missing import types
   - `services/discord/profiles.py` - Unbound variables

## Implementation Tasks

1. **Add proper type imports** for:
   - FastAPI types (FastAPI, WebSocket, etc.)
   - Discord.py types (Guild, Message, etc.)
   - Service interface types

2. **Fix method signatures** to match parent classes:
   - LLMInterface.chat_stream return type
   - TTSInterface.generate parameter compatibility

3. **Add type hints** to all public methods:
   - Class constructors (__init__)
   - Public API methods
   - Async methods

4. **Handle None types properly**:
   - Add Optional[T] where services may be None
   - Add proper None checks

## Success Criteria

- [ ] All public methods have proper type hints
- [ ] All class signatures match parent interfaces
- [ ] No more "Cannot access attribute" type errors
- [ ] All imports resolve correctly
- [ ] mypy type checking passes without errors

## Priority: HIGH (Code Quality & Maintainability)