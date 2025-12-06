"""Service interface abstractions for dependency injection and testing.

This module provides abstract base classes (interfaces) for all major services:
- TTSInterface: Text-to-Speech services
- STTInterface: Speech-to-Text services
- LLMInterface: Large Language Model services
- RVCInterface: Real-time Voice Conversion services

Benefits:
- Clear contracts between components
- Easy to swap implementations (e.g., switch TTS providers)
- Mockable for unit testing
- Type safety with proper hints
"""

from .tts_interface import TTSInterface
from .stt_interface import STTInterface
from .llm_interface import LLMInterface
from .rvc_interface import RVCInterface

__all__ = [
    "TTSInterface",
    "STTInterface",
    "LLMInterface",
    "RVCInterface",
]
