"""Voice cog package - refactored for maintainability.

New modular structure:
- main.py: Core VoiceCog orchestrator
- manager.py: Voice client connection management
- commands.py: Voice command implementations
- listening_handler.py: Voice listening and transcription
- tts_handler.py: TTS generation and playback

This package consolidates all voice, TTS, and RVC functionality.
"""

from .main import VoiceCog

__all__ = ["VoiceCog"]
