"""Configuration management for Discord Ollama Bot."""
import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Bot configuration."""

    # Discord
    DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
    COMMAND_PREFIX: str = os.getenv("COMMAND_PREFIX", "!")

    # Ollama
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2")
    OLLAMA_TEMPERATURE: float = float(os.getenv("OLLAMA_TEMPERATURE", "1.17"))
    OLLAMA_MAX_TOKENS: int = int(os.getenv("OLLAMA_MAX_TOKENS", "500"))
    OLLAMA_MIN_P: float = float(os.getenv("OLLAMA_MIN_P", "0.075"))
    OLLAMA_TOP_K: int = int(os.getenv("OLLAMA_TOP_K", "50"))
    OLLAMA_REPEAT_PENALTY: float = float(os.getenv("OLLAMA_REPEAT_PENALTY", "1.1"))
    
    # Advanced Sampling (SillyTavern-style)
    LLM_FREQUENCY_PENALTY: float = float(os.getenv("LLM_FREQUENCY_PENALTY", "0.0"))
    LLM_PRESENCE_PENALTY: float = float(os.getenv("LLM_PRESENCE_PENALTY", "0.0"))
    LLM_TOP_P: float = float(os.getenv("LLM_TOP_P", "1.0"))

    # LLM Provider (ollama or openrouter)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama").lower()

    # OpenRouter
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "nousresearch/hermes-3-llama-3.1-405b")
    OPENROUTER_URL: str = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1")

    # Chat
    CLEAN_THINKING_OUTPUT: bool = os.getenv("CLEAN_THINKING_OUTPUT", "true").lower() == "true"
    CHAT_HISTORY_ENABLED: bool = os.getenv("CHAT_HISTORY_ENABLED", "true").lower() == "true"
    CHAT_HISTORY_MAX_MESSAGES: int = int(os.getenv("CHAT_HISTORY_MAX_MESSAGES", "20"))
    AUTO_REPLY_ENABLED: bool = os.getenv("AUTO_REPLY_ENABLED", "false").lower() == "true"
    AUTO_REPLY_CHANNELS: List[int] = [
        int(x.strip()) for x in os.getenv("AUTO_REPLY_CHANNELS", "").split(",") if x.strip()
    ]
    AUTO_REPLY_WITH_VOICE: bool = os.getenv("AUTO_REPLY_WITH_VOICE", "true").lower() == "true"

    # Conversation Session Settings
    CONVERSATION_TIMEOUT: int = int(os.getenv("CONVERSATION_TIMEOUT", "300"))  # 5 minutes default

    # System Prompt / Personality
    SYSTEM_PROMPT_FILE: str = os.getenv("SYSTEM_PROMPT_FILE", "./prompts/default.txt")
    SYSTEM_PROMPT: str = os.getenv("SYSTEM_PROMPT", "")  # Override from env if provided

    # AI-First Persona System
    USE_PERSONA_SYSTEM: bool = os.getenv("USE_PERSONA_SYSTEM", "true").lower() == "true"
    CHARACTER: str = os.getenv("CHARACTER", "dagoth_ur")
    FRAMEWORK: str = os.getenv("FRAMEWORK", "neuro")

    # RAG (Retrieval-Augmented Generation)
    RAG_ENABLED: bool = os.getenv("RAG_ENABLED", "false").lower() == "true"
    RAG_VECTOR_STORE: str = os.getenv("RAG_VECTOR_STORE", "./data/vector_store")
    RAG_DOCUMENTS_PATH: str = os.getenv("RAG_DOCUMENTS_PATH", "./data/documents")
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "3"))
    RAG_IN_CHAT: bool = os.getenv("RAG_IN_CHAT", "true").lower() == "true"  # Use RAG context in conversations

    # MCP (Model Context Protocol) - ARCHIVED (service never implemented)
    # MCP_ENABLED: bool = os.getenv("MCP_ENABLED", "false").lower() == "true"
    # MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL", "http://localhost:8080")

    # User Profiles
    USER_PROFILES_ENABLED: bool = os.getenv("USER_PROFILES_ENABLED", "true").lower() == "true"
    USER_PROFILES_PATH: Path = Path(os.getenv("USER_PROFILES_PATH", "./data/user_profiles"))
    USER_PROFILES_AUTO_LEARN: bool = os.getenv("USER_PROFILES_AUTO_LEARN", "true").lower() == "true"  # AI-powered automatic learning
    USER_AFFECTION_ENABLED: bool = os.getenv("USER_AFFECTION_ENABLED", "true").lower() == "true"
    USER_CONTEXT_IN_CHAT: bool = os.getenv("USER_CONTEXT_IN_CHAT", "true").lower() == "true"

    # Web Search
    WEB_SEARCH_ENABLED: bool = os.getenv("WEB_SEARCH_ENABLED", "true").lower() == "true"
    WEB_SEARCH_ENGINE: str = os.getenv("WEB_SEARCH_ENGINE", "duckduckgo")
    WEB_SEARCH_MAX_RESULTS: int = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "3"))

    # Voice/TTS
    TTS_ENGINE: str = os.getenv("TTS_ENGINE", "edge")  # "edge", "kokoro", or "supertonic"

    # Edge TTS Settings
    DEFAULT_TTS_VOICE: str = os.getenv("DEFAULT_TTS_VOICE", "en-US-AriaNeural")
    TTS_RATE: str = os.getenv("TTS_RATE", "+0%")
    TTS_VOLUME: str = os.getenv("TTS_VOLUME", "+0%")

    # Kokoro TTS Settings
    KOKORO_VOICE: str = os.getenv("KOKORO_VOICE", "am_adam")
    KOKORO_SPEED: float = float(os.getenv("KOKORO_SPEED", "1.0"))
    KOKORO_VOICE_CHIEF: str = os.getenv("KOKORO_VOICE_CHIEF", "am_onyx")
    KOKORO_VOICE_ARBY: str = os.getenv("KOKORO_VOICE_ARBY", "bm_george")

    # Supertonic TTS Settings
    SUPERTONIC_VOICE: str = os.getenv("SUPERTONIC_VOICE", "M1")  # M1, M2, F1, F2, or aliases like "male", "female"
    SUPERTONIC_STEPS: int = int(os.getenv("SUPERTONIC_STEPS", "5"))  # Denoising steps (1-20, higher = better quality)
    SUPERTONIC_SPEED: float = float(os.getenv("SUPERTONIC_SPEED", "1.05"))  # Speech speed multiplier

    # RVC
    RVC_ENABLED: bool = os.getenv("RVC_ENABLED", "false").lower() == "true"
    RVC_MODE: str = os.getenv("RVC_MODE", "webui")  # "inferpy" or "webui"
    RVC_MODEL_PATH: Path = Path(os.getenv("RVC_MODEL_PATH", "./data/voice_models"))
    DEFAULT_RVC_MODEL: str = os.getenv("DEFAULT_RVC_MODEL", "GOTHMOMMY")
    RVC_DEVICE: str = os.getenv("RVC_DEVICE", "cpu")
    RVC_WEBUI_URL: str = os.getenv("RVC_WEBUI_URL", "http://localhost:7865")
    RVC_PITCH_SHIFT: int = int(os.getenv("RVC_PITCH_SHIFT", "0"))
    RVC_PROTECT: float = float(os.getenv("RVC_PROTECT", "0.33"))
    RVC_INDEX_RATE: float = float(os.getenv("RVC_INDEX_RATE", "0.75"))

    # Audio
    AUDIO_BITRATE: int = int(os.getenv("AUDIO_BITRATE", "96"))
    AUDIO_SAMPLE_RATE: int = int(os.getenv("AUDIO_SAMPLE_RATE", "48000"))

    # Paths
    DATA_DIR: Path = Path("./data")
    CHAT_HISTORY_DIR: Path = DATA_DIR / "chat_history"
    VOICE_MODELS_DIR: Path = DATA_DIR / "voice_models"
    TEMP_DIR: Path = DATA_DIR / "temp"
    SUMMARY_DIR: Path = DATA_DIR / "conversation_summaries"

    # Memory Management
    MEMORY_CLEANUP_ENABLED: bool = os.getenv("MEMORY_CLEANUP_ENABLED", "true").lower() == "true"
    MEMORY_CLEANUP_INTERVAL_HOURS: int = int(os.getenv("MEMORY_CLEANUP_INTERVAL_HOURS", "6"))
    MAX_TEMP_FILE_AGE_HOURS: int = int(os.getenv("MAX_TEMP_FILE_AGE_HOURS", "24"))
    MAX_HISTORY_AGE_DAYS: int = int(os.getenv("MAX_HISTORY_AGE_DAYS", "30"))

    # Response Streaming
    RESPONSE_STREAMING_ENABLED: bool = os.getenv("RESPONSE_STREAMING_ENABLED", "true").lower() == "true"
    STREAM_UPDATE_INTERVAL: float = float(os.getenv("STREAM_UPDATE_INTERVAL", "1.0"))  # Seconds between updates

    # Conversation Summarization
    CONVERSATION_SUMMARIZATION_ENABLED: bool = os.getenv("CONVERSATION_SUMMARIZATION_ENABLED", "true").lower() == "true"
    AUTO_SUMMARIZE_THRESHOLD: int = int(os.getenv("AUTO_SUMMARIZE_THRESHOLD", "30"))  # Messages before auto-summarize
    STORE_SUMMARIES_IN_RAG: bool = os.getenv("STORE_SUMMARIES_IN_RAG", "true").lower() == "true"

    # Voice Activity Detection (Whisper STT)
    WHISPER_ENABLED: bool = os.getenv("WHISPER_ENABLED", "false").lower() == "true"
    WHISPER_MODEL_SIZE: str = os.getenv("WHISPER_MODEL_SIZE", "base")  # tiny, base, small, medium, large
    WHISPER_DEVICE: str = os.getenv("WHISPER_DEVICE", "auto")  # auto, cpu, cuda
    WHISPER_LANGUAGE: str = os.getenv("WHISPER_LANGUAGE", "en")
    WHISPER_SILENCE_THRESHOLD: float = float(os.getenv("WHISPER_SILENCE_THRESHOLD", "1.0"))
    MAX_RECORDING_DURATION: int = int(os.getenv("MAX_RECORDING_DURATION", "30"))

    # Enhanced Voice Listener Settings
    VOICE_ENERGY_THRESHOLD: int = int(os.getenv("VOICE_ENERGY_THRESHOLD", "500"))  # Audio energy threshold for VAD
    VOICE_BOT_TRIGGER_WORDS: str = os.getenv("VOICE_BOT_TRIGGER_WORDS", "bot,assistant,hey,help,question")  # Comma-separated

    # Ambient Mode Settings
    AMBIENT_MODE_ENABLED: bool = os.getenv("AMBIENT_MODE_ENABLED", "true").lower() == "true"
    AMBIENT_CHANNELS: List[int] = [
        int(x.strip()) for x in os.getenv("AMBIENT_CHANNELS", "").split(",") if x.strip()
    ]  # Channel IDs for ambient messages (empty = all channels)
    AMBIENT_IGNORE_USERS: List[int] = [
        int(x.strip()) for x in os.getenv("AMBIENT_IGNORE_USERS", "").split(",") if x.strip()
    ]  # User IDs to ignore for ambient features (reactions, activity comments)

    # Global user ignore list
    IGNORED_USERS: List[int] = [
        int(x.strip()) for x in os.getenv("IGNORED_USERS", "").split(",") if x.strip()
    ]  # User IDs to completely ignore (bot won't respond to them at all)

    AMBIENT_LULL_TIMEOUT: int = int(os.getenv("AMBIENT_LULL_TIMEOUT", "300"))  # Seconds of silence before lull trigger
    AMBIENT_MIN_INTERVAL: int = int(os.getenv("AMBIENT_MIN_INTERVAL", "600"))  # Min seconds between ambient messages
    AMBIENT_CHANCE: float = float(os.getenv("AMBIENT_CHANCE", "0.3"))  # Chance to trigger on each check (0.0-1.0)

    # Proactive Engagement Settings
    PROACTIVE_ENGAGEMENT_ENABLED: bool = os.getenv("PROACTIVE_ENGAGEMENT_ENABLED", "true").lower() == "true"
    PROACTIVE_MIN_MESSAGES: int = int(os.getenv("PROACTIVE_MIN_MESSAGES", "3"))  # Min messages before bot can jump in
    PROACTIVE_COOLDOWN: int = int(os.getenv("PROACTIVE_COOLDOWN", "180"))  # Seconds between proactive engagements

    # Naturalness Settings
    NATURALNESS_ENABLED: bool = os.getenv("NATURALNESS_ENABLED", "true").lower() == "true"
    REACTIONS_ENABLED: bool = os.getenv("REACTIONS_ENABLED", "true").lower() == "true"
    REACTIONS_CHANCE_MULTIPLIER: float = float(os.getenv("REACTIONS_CHANCE_MULTIPLIER", "1.0"))  # Multiplier for reaction chances
    ACTIVITY_AWARENESS_ENABLED: bool = os.getenv("ACTIVITY_AWARENESS_ENABLED", "true").lower() == "true"
    ACTIVITY_COMMENT_CHANCE: float = float(os.getenv("ACTIVITY_COMMENT_CHANCE", "0.1"))  # Chance to comment on activity changes
    ACTIVITY_COOLDOWN_SECONDS: int = int(os.getenv("ACTIVITY_COOLDOWN_SECONDS", "300"))  # Cooldown period (in seconds) before commenting on same activity type again

    # Natural Timing Settings
    NATURAL_TIMING_ENABLED: bool = os.getenv("NATURAL_TIMING_ENABLED", "true").lower() == "true"
    NATURAL_TIMING_MIN_DELAY: float = float(os.getenv("NATURAL_TIMING_MIN_DELAY", "0.5"))  # Minimum delay in seconds
    NATURAL_TIMING_MAX_DELAY: float = float(os.getenv("NATURAL_TIMING_MAX_DELAY", "2.0"))  # Maximum delay in seconds

    # Mood System Settings
    MOOD_SYSTEM_ENABLED: bool = os.getenv("MOOD_SYSTEM_ENABLED", "true").lower() == "true"
    MOOD_UPDATE_FROM_INTERACTIONS: bool = os.getenv("MOOD_UPDATE_FROM_INTERACTIONS", "true").lower() == "true"  # Auto-update mood from user interactions
    MOOD_TIME_BASED: bool = os.getenv("MOOD_TIME_BASED", "true").lower() == "true"  # Use time of day for mood

    # Self-Awareness Settings
    SELF_AWARENESS_ENABLED: bool = os.getenv("SELF_AWARENESS_ENABLED", "true").lower() == "true"
    HESITATION_CHANCE: float = float(os.getenv("HESITATION_CHANCE", "0.15"))  # Chance to add hesitations (0.0-1.0)
    META_COMMENT_CHANCE: float = float(os.getenv("META_COMMENT_CHANCE", "0.10"))  # Chance for self-aware comments (0.0-1.0)
    SELF_CORRECTION_ENABLED: bool = os.getenv("SELF_CORRECTION_ENABLED", "true").lower() == "true"  # Allow bot to correct itself

    # Reminders
    REMINDERS_ENABLED: bool = os.getenv("REMINDERS_ENABLED", "true").lower() == "true"
    MAX_REMINDERS_PER_USER: int = int(os.getenv("MAX_REMINDERS_PER_USER", "10"))

    # Vision/Image Understanding
    VISION_ENABLED: bool = os.getenv("VISION_ENABLED", "true").lower() == "true"
    VISION_MODEL: str = os.getenv("VISION_MODEL", "llava")  # llava, llava-llama3, bakllava, etc.

    # Trivia Games
    TRIVIA_ENABLED: bool = os.getenv("TRIVIA_ENABLED", "true").lower() == "true"

    # Natural Language Understanding
    INTENT_RECOGNITION_ENABLED: bool = os.getenv("INTENT_RECOGNITION_ENABLED", "true").lower() == "true"
    NATURAL_LANGUAGE_REMINDERS: bool = os.getenv("NATURAL_LANGUAGE_REMINDERS", "true").lower() == "true"

    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration."""
        if not cls.DISCORD_TOKEN:
            raise ValueError("DISCORD_TOKEN is required")

        # Validate Ollama parameters
        if not (0.0 <= cls.OLLAMA_TEMPERATURE <= 2.0):
            raise ValueError(f"OLLAMA_TEMPERATURE must be between 0.0 and 2.0, got {cls.OLLAMA_TEMPERATURE}")

        if cls.OLLAMA_MAX_TOKENS < 1:
            raise ValueError(f"OLLAMA_MAX_TOKENS must be at least 1, got {cls.OLLAMA_MAX_TOKENS}")

        if not (0.0 <= cls.OLLAMA_MIN_P <= 1.0):
            raise ValueError(f"OLLAMA_MIN_P must be between 0.0 and 1.0, got {cls.OLLAMA_MIN_P}")

        if cls.OLLAMA_TOP_K < 1:
            raise ValueError(f"OLLAMA_TOP_K must be at least 1, got {cls.OLLAMA_TOP_K}")

        if cls.OLLAMA_REPEAT_PENALTY < 0.0:
            raise ValueError(f"OLLAMA_REPEAT_PENALTY must be non-negative, got {cls.OLLAMA_REPEAT_PENALTY}")

        # Validate chat history settings
        if cls.CHAT_HISTORY_MAX_MESSAGES < 1:
            raise ValueError(f"CHAT_HISTORY_MAX_MESSAGES must be at least 1, got {cls.CHAT_HISTORY_MAX_MESSAGES}")

        # Validate timing settings
        if cls.NATURAL_TIMING_MIN_DELAY < 0:
            raise ValueError(f"NATURAL_TIMING_MIN_DELAY must be non-negative, got {cls.NATURAL_TIMING_MIN_DELAY}")

        if cls.NATURAL_TIMING_MAX_DELAY < cls.NATURAL_TIMING_MIN_DELAY:
            raise ValueError(f"NATURAL_TIMING_MAX_DELAY must be >= NATURAL_TIMING_MIN_DELAY")

        # Validate probability values
        if not (0.0 <= cls.HESITATION_CHANCE <= 1.0):
            raise ValueError(f"HESITATION_CHANCE must be between 0.0 and 1.0, got {cls.HESITATION_CHANCE}")

        if not (0.0 <= cls.META_COMMENT_CHANCE <= 1.0):
            raise ValueError(f"META_COMMENT_CHANCE must be between 0.0 and 1.0, got {cls.META_COMMENT_CHANCE}")

        if not (0.0 <= cls.ACTIVITY_COMMENT_CHANCE <= 1.0):
            raise ValueError(f"ACTIVITY_COMMENT_CHANCE must be between 0.0 and 1.0, got {cls.ACTIVITY_COMMENT_CHANCE}")

        # Create necessary directories with error handling
        try:
            cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
            cls.CHAT_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
            cls.VOICE_MODELS_DIR.mkdir(parents=True, exist_ok=True)
            cls.TEMP_DIR.mkdir(parents=True, exist_ok=True)
            cls.SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            raise ValueError(f"Permission denied creating directories: {e}")
        except Exception as e:
            raise ValueError(f"Failed to create directories: {e}")

        return True

# Validate on import
Config.validate()
