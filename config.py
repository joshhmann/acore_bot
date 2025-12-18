"""Configuration management for Discord Ollama Bot."""

import os
from pathlib import Path
from typing import List, Dict
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
    OPENROUTER_MODEL: str = os.getenv(
        "OPENROUTER_MODEL", "nousresearch/hermes-3-llama-3.1-405b"
    )
    OPENROUTER_URL: str = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_TIMEOUT: int = int(
        os.getenv("OPENROUTER_TIMEOUT", "180")
    )  # API timeout in seconds
    OPENROUTER_STREAM_TIMEOUT: int = int(
        os.getenv("OPENROUTER_STREAM_TIMEOUT", "180")
    )  # Streaming timeout in seconds

    # Thinking/Decision Model (cheap/fast model for internal decisions like spam detection, routing)
    THINKING_MODEL: str = os.getenv("THINKING_MODEL", "")  # If empty, uses main model
    THINKING_MODEL_PROVIDER: str = os.getenv(
        "THINKING_MODEL_PROVIDER", ""
    )  # ollama or openrouter

    # Chat
    CLEAN_THINKING_OUTPUT: bool = (
        os.getenv("CLEAN_THINKING_OUTPUT", "true").lower() == "true"
    )
    CHAT_HISTORY_ENABLED: bool = (
        os.getenv("CHAT_HISTORY_ENABLED", "true").lower() == "true"
    )
    CHAT_HISTORY_MAX_MESSAGES: int = int(os.getenv("CHAT_HISTORY_MAX_MESSAGES", "100"))
    CONTEXT_MESSAGE_LIMIT: int = int(os.getenv("CONTEXT_MESSAGE_LIMIT", "20"))
    MAX_CONTEXT_TOKENS: int = int(os.getenv("MAX_CONTEXT_TOKENS", "8192"))

    # Model specific context limits (override MAX_CONTEXT_TOKENS)
    MODEL_CONTEXT_LIMITS: Dict[str, int] = {
        "llama3.2": 128000,
        "mistral": 32000,
        "gpt-4": 8192,
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
        "claude-3-opus-20240229": 200000,
        "claude-3-sonnet-20240229": 200000,
        "claude-3-haiku-20240307": 200000,
        "nousresearch/hermes-3-llama-3.1-405b": 128000,
    }

    AUTO_REPLY_ENABLED: bool = (
        os.getenv("AUTO_REPLY_ENABLED", "false").lower() == "true"
    )
    AUTO_REPLY_CHANNELS: List[int] = [
        int(x.strip())
        for x in os.getenv("AUTO_REPLY_CHANNELS", "").split(",")
        if x.strip()
    ]
    AUTO_REPLY_WITH_VOICE: bool = (
        os.getenv("AUTO_REPLY_WITH_VOICE", "true").lower() == "true"
    )

    # Conversation Session Settings
    CONVERSATION_TIMEOUT: int = int(
        os.getenv("CONVERSATION_TIMEOUT", "300")
    )  # 5 minutes default

    # --- Persona Settings ---
    CHARACTERS_DIR: Path = Path(os.getenv("CHARACTERS_DIR", "./prompts/characters"))

    # List of active character card filenames in prompts/characters/
    # If empty, loads ALL available characters
    ACTIVE_PERSONAS = [
        "dagoth_ur.json",
        "scav.json",
        "zenos.json",
        "maury.json",
        "hal9000.json",
        "toad.json",
        "jc.json",
        "toadette.json",
        "joseph_stalin.json",
        "Biblical_Jesus_Christ.json",
    ]

    # Probability (0.0 to 1.0) that ANY bot will respond to a message
    # 1.0 = Always respond (if selected)
    # Scaled down to 1/6th effectively if we split probability or just use this as a gate
    # The user asked for "1/6 current response rate"
    # If we have 6 bots and want them to effectively respond at 1/6th rate EACH,
    # we can treat them as independent agents or just route 1/6th of messages to each.
    # Let's set a global gate.
    GLOBAL_RESPONSE_CHANCE = 1.0

    # Specific weights for persona selection (optional)
    # Default is equal 1/N chance for each active persona
    PERSONA_WEIGHTS: Dict[str, float] = {}

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
    RAG_IN_CHAT: bool = (
        os.getenv("RAG_IN_CHAT", "true").lower() == "true"
    )  # Use RAG context in conversations
    ANONYMIZED_TELEMETRY: bool = (
        os.getenv("ANONYMIZED_TELEMETRY", "false").lower() == "true"
    )

    # MCP (Model Context Protocol) - ARCHIVED (service never implemented)
    # MCP_ENABLED: bool = os.getenv("MCP_ENABLED", "false").lower() == "true"
    # MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL", "http://localhost:8080")

    # User Profiles
    USER_PROFILES_ENABLED: bool = (
        os.getenv("USER_PROFILES_ENABLED", "true").lower() == "true"
    )
    USER_PROFILES_PATH: Path = Path(
        os.getenv("USER_PROFILES_PATH", "./data/user_profiles")
    )
    USER_PROFILES_AUTO_LEARN: bool = (
        os.getenv("USER_PROFILES_AUTO_LEARN", "true").lower() == "true"
    )  # AI-powered automatic learning
    USER_AFFECTION_ENABLED: bool = (
        os.getenv("USER_AFFECTION_ENABLED", "true").lower() == "true"
    )
    USER_CONTEXT_IN_CHAT: bool = (
        os.getenv("USER_CONTEXT_IN_CHAT", "true").lower() == "true"
    )

    # Web Search
    WEB_SEARCH_ENABLED: bool = os.getenv("WEB_SEARCH_ENABLED", "true").lower() == "true"
    WEB_SEARCH_ENGINE: str = os.getenv("WEB_SEARCH_ENGINE", "duckduckgo")
    WEB_SEARCH_MAX_RESULTS: int = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "3"))

    # Voice/TTS
    TTS_ENGINE: str = os.getenv(
        "TTS_ENGINE", "kokoro_api"
    )  # "kokoro", "kokoro_api", or "supertonic"

    # Kokoro TTS Settings
    KOKORO_VOICE: str = os.getenv("KOKORO_VOICE", "am_adam")
    KOKORO_SPEED: float = float(os.getenv("KOKORO_SPEED", "1.0"))
    KOKORO_API_URL: str = os.getenv(
        "KOKORO_API_URL", "http://localhost:8880"
    )  # Kokoro-FastAPI URL
    KOKORO_VOICE_CHIEF: str = os.getenv("KOKORO_VOICE_CHIEF", "am_onyx")
    KOKORO_VOICE_ARBY: str = os.getenv("KOKORO_VOICE_ARBY", "bm_george")

    # Supertonic TTS Settings
    SUPERTONIC_VOICE: str = os.getenv(
        "SUPERTONIC_VOICE", "M1"
    )  # M1, M2, F1, F2, or aliases like "male", "female"
    SUPERTONIC_STEPS: int = int(
        os.getenv("SUPERTONIC_STEPS", "5")
    )  # Denoising steps (1-20, higher = better quality)
    SUPERTONIC_SPEED: float = float(
        os.getenv("SUPERTONIC_SPEED", "1.05")
    )  # Speech speed multiplier

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
    MEMORY_CLEANUP_ENABLED: bool = (
        os.getenv("MEMORY_CLEANUP_ENABLED", "true").lower() == "true"
    )
    MEMORY_CLEANUP_INTERVAL_HOURS: int = int(
        os.getenv("MEMORY_CLEANUP_INTERVAL_HOURS", "6")
    )
    MAX_TEMP_FILE_AGE_HOURS: int = int(os.getenv("MAX_TEMP_FILE_AGE_HOURS", "24"))
    MAX_HISTORY_AGE_DAYS: int = int(os.getenv("MAX_HISTORY_AGE_DAYS", "30"))

    # Response Streaming
    RESPONSE_STREAMING_ENABLED: bool = (
        os.getenv("RESPONSE_STREAMING_ENABLED", "true").lower() == "true"
    )
    STREAM_UPDATE_INTERVAL: float = float(
        os.getenv("STREAM_UPDATE_INTERVAL", "1.0")
    )  # Seconds between updates

    # Conversation Summarization
    CONVERSATION_SUMMARIZATION_ENABLED: bool = (
        os.getenv("CONVERSATION_SUMMARIZATION_ENABLED", "true").lower() == "true"
    )
    AUTO_SUMMARIZE_THRESHOLD: int = int(
        os.getenv("AUTO_SUMMARIZE_THRESHOLD", "30")
    )  # Messages before auto-summarize
    STORE_SUMMARIES_IN_RAG: bool = (
        os.getenv("STORE_SUMMARIES_IN_RAG", "true").lower() == "true"
    )

    # Voice Activity Detection (STT)
    STT_ENGINE: str = os.getenv("STT_ENGINE", "whisper")  # "whisper" or "parakeet"

    # Whisper STT Settings
    WHISPER_ENABLED: bool = os.getenv("WHISPER_ENABLED", "false").lower() == "true"
    WHISPER_MODEL_SIZE: str = os.getenv(
        "WHISPER_MODEL_SIZE", "base"
    )  # tiny, base, small, medium, large
    WHISPER_DEVICE: str = os.getenv("WHISPER_DEVICE", "auto")  # auto, cpu, cuda
    WHISPER_LANGUAGE: str = os.getenv("WHISPER_LANGUAGE", "en")
    WHISPER_SILENCE_THRESHOLD: float = float(
        os.getenv("WHISPER_SILENCE_THRESHOLD", "1.0")
    )
    MAX_RECORDING_DURATION: int = int(os.getenv("MAX_RECORDING_DURATION", "30"))

    # Parakeet STT Settings
    PARAKEET_ENABLED: bool = os.getenv("PARAKEET_ENABLED", "false").lower() == "true"
    PARAKEET_API_URL: str = os.getenv(
        "PARAKEET_API_URL", "http://localhost:8890"
    )  # External API
    PARAKEET_MODEL: str = os.getenv(
        "PARAKEET_MODEL", "nvidia/parakeet-tdt-0.6b-v3"
    )  # Legacy, used if no API
    PARAKEET_DEVICE: str = os.getenv("PARAKEET_DEVICE", "auto")  # Legacy
    PARAKEET_LANGUAGE: str = os.getenv("PARAKEET_LANGUAGE", "en")

    # Enhanced Voice Listener Settings
    VOICE_ENERGY_THRESHOLD: int = int(
        os.getenv("VOICE_ENERGY_THRESHOLD", "500")
    )  # Audio energy threshold for VAD
    VOICE_BOT_TRIGGER_WORDS: str = os.getenv(
        "VOICE_BOT_TRIGGER_WORDS", "bot,assistant,hey,help,question"
    )  # Comma-separated

    # Ambient Mode Settings
    AMBIENT_MODE_ENABLED: bool = (
        os.getenv("AMBIENT_MODE_ENABLED", "true").lower() == "true"
    )
    AMBIENT_CHANNELS: List[int] = [
        int(x.strip())
        for x in os.getenv("AMBIENT_CHANNELS", "").split(",")
        if x.strip()
    ]  # Channel IDs for ambient messages (empty = all channels)
    AMBIENT_IGNORE_USERS: List[int] = [
        int(x.strip())
        for x in os.getenv("AMBIENT_IGNORE_USERS", "").split(",")
        if x.strip()
    ]  # User IDs to ignore for ambient features (reactions, activity comments)

    # Global user ignore list
    IGNORED_USERS: List[int] = [
        int(x.strip()) for x in os.getenv("IGNORED_USERS", "").split(",") if x.strip()
    ]  # User IDs to completely ignore (bot won't respond to them at all)

    AMBIENT_LULL_TIMEOUT: int = int(
        os.getenv("AMBIENT_LULL_TIMEOUT", "300")
    )  # Seconds of silence before lull trigger
    AMBIENT_MIN_INTERVAL: int = int(
        os.getenv("AMBIENT_MIN_INTERVAL", "600")
    )  # Min seconds between ambient messages
    AMBIENT_CHANCE: float = float(
        os.getenv("AMBIENT_CHANCE", "0.3")
    )  # Chance to trigger on each check (0.0-1.0)

    # Proactive Engagement Settings
    PROACTIVE_ENGAGEMENT_ENABLED: bool = (
        os.getenv("PROACTIVE_ENGAGEMENT_ENABLED", "true").lower() == "true"
    )
    PROACTIVE_MIN_MESSAGES: int = int(
        os.getenv("PROACTIVE_MIN_MESSAGES", "3")
    )  # Min messages before bot can jump in
    PROACTIVE_COOLDOWN: int = int(
        os.getenv("PROACTIVE_COOLDOWN", "180")
    )  # Seconds between proactive engagements

    # Naturalness Settings
    NATURALNESS_ENABLED: bool = (
        os.getenv("NATURALNESS_ENABLED", "true").lower() == "true"
    )
    MOOD_SYSTEM_ENABLED: bool = (
        os.getenv("MOOD_SYSTEM_ENABLED", "false").lower() == "true"
    )  # Dynamic mood states
    REACTIONS_ENABLED: bool = os.getenv("REACTIONS_ENABLED", "true").lower() == "true"
    REACTIONS_CHANCE_MULTIPLIER: float = float(
        os.getenv("REACTIONS_CHANCE_MULTIPLIER", "1.0")
    )  # Multiplier for reaction chances
    ACTIVITY_AWARENESS_ENABLED: bool = (
        os.getenv("ACTIVITY_AWARENESS_ENABLED", "true").lower() == "true"
    )
    ACTIVITY_COMMENT_CHANCE: float = float(
        os.getenv("ACTIVITY_COMMENT_CHANCE", "0.1")
    )  # Chance to comment on activity changes
    ACTIVITY_COOLDOWN_SECONDS: int = int(
        os.getenv("ACTIVITY_COOLDOWN_SECONDS", "300")
    )  # Cooldown period (in seconds) before commenting on same activity type again

    # Natural Timing Settings
    NATURAL_TIMING_ENABLED: bool = (
        os.getenv("NATURAL_TIMING_ENABLED", "true").lower() == "true"
    )
    NATURAL_TIMING_MIN_DELAY: float = float(
        os.getenv("NATURAL_TIMING_MIN_DELAY", "0.5")
    )  # Minimum delay in seconds
    NATURAL_TIMING_MAX_DELAY: float = float(
        os.getenv("NATURAL_TIMING_MAX_DELAY", "2.0")
    )  # Maximum delay in seconds

    # --- Persona & Behavior Enhancement Features ---

    # T1-T2: Dynamic Mood System Settings
    # Note: MOOD_SYSTEM_ENABLED is already defined above at line 329
    MOOD_UPDATE_FROM_INTERACTIONS: bool = (
        os.getenv("MOOD_UPDATE_FROM_INTERACTIONS", "true").lower() == "true"
    )  # Auto-update mood from user interactions
    MOOD_TIME_BASED: bool = (
        os.getenv("MOOD_TIME_BASED", "true").lower() == "true"
    )  # Use time of day for mood
    MOOD_DECAY_MINUTES: int = int(
        os.getenv("MOOD_DECAY_MINUTES", "30")
    )  # Minutes before mood decays to neutral
    MOOD_MAX_INTENSITY_SHIFT: float = float(
        os.getenv("MOOD_MAX_INTENSITY_SHIFT", "0.1")
    )  # Max mood change per message

    # T7-T8: Curiosity-Driven Follow-Up Questions
    CURIOSITY_ENABLED: bool = os.getenv("CURIOSITY_ENABLED", "true").lower() == "true"
    CURIOSITY_INDIVIDUAL_COOLDOWN_SECONDS: int = int(
        os.getenv("CURIOSITY_INDIVIDUAL_COOLDOWN_SECONDS", "300")
    )
    CURIOSITY_WINDOW_LIMIT_SECONDS: int = int(
        os.getenv("CURIOSITY_WINDOW_LIMIT_SECONDS", "900")
    )
    CURIOSITY_TOPIC_MEMORY_SIZE: int = int(
        os.getenv("CURIOSITY_TOPIC_MEMORY_SIZE", "20")
    )

    # T11-T12: Adaptive Ambient Timing
    ADAPTIVE_TIMING_ENABLED: bool = (
        os.getenv("ADAPTIVE_TIMING_ENABLED", "true").lower() == "true"
    )
    ADAPTIVE_TIMING_LEARNING_WINDOW_DAYS: int = int(
        os.getenv("ADAPTIVE_TIMING_LEARNING_WINDOW_DAYS", "7")
    )
    CHANNEL_ACTIVITY_PROFILE_PATH: Path = Path(
        os.getenv(
            "CHANNEL_ACTIVITY_PROFILE_PATH", "./data/channel_activity_profiles.json"
        )
    )

    # T13-T14: Character Evolution System
    PERSONA_EVOLUTION_ENABLED: bool = (
        os.getenv("PERSONA_EVOLUTION_ENABLED", "true").lower() == "true"
    )
    PERSONA_EVOLUTION_PATH: Path = Path(
        os.getenv("PERSONA_EVOLUTION_PATH", "./data/persona_evolution")
    )

    # T15-T16: Persona Conflict System
    PERSONA_CONFLICTS_ENABLED: bool = (
        os.getenv("PERSONA_CONFLICTS_ENABLED", "true").lower() == "true"
    )
    CONFLICT_DECAY_RATE: float = float(os.getenv("CONFLICT_DECAY_RATE", "0.1"))
    CONFLICT_ESCALATION_AMOUNT: float = float(
        os.getenv("CONFLICT_ESCALATION_AMOUNT", "0.2")
    )

    # T17-T18: Activity-Based Persona Switching
    ACTIVITY_ROUTING_ENABLED: bool = (
        os.getenv("ACTIVITY_ROUTING_ENABLED", "true").lower() == "true"
    )
    ACTIVITY_ROUTING_PRIORITY: int = int(os.getenv("ACTIVITY_ROUTING_PRIORITY", "100"))

    # T25-T26: Semantic Lorebook Triggering
    SEMANTIC_LOREBOOK_ENABLED: bool = (
        os.getenv("SEMANTIC_LOREBOOK_ENABLED", "true").lower() == "true"
    )
    SEMANTIC_LOREBOOK_THRESHOLD: float = float(
        os.getenv("SEMANTIC_LOREBOOK_THRESHOLD", "0.65")
    )
    SEMANTIC_LOREBOOK_CACHE_SIZE: int = int(
        os.getenv("SEMANTIC_LOREBOOK_CACHE_SIZE", "1000")
    )

    # T23-T24: Real-Time Analytics Dashboard
    ANALYTICS_DASHBOARD_ENABLED: bool = (
        os.getenv("ANALYTICS_DASHBOARD_ENABLED", "false").lower() == "true"
    )
    ANALYTICS_DASHBOARD_PORT: int = int(os.getenv("ANALYTICS_DASHBOARD_PORT", "8080"))
    ANALYTICS_API_KEY: str = os.getenv("ANALYTICS_API_KEY", "change_me_in_production")

    # Self-Awareness Settings
    SELF_AWARENESS_ENABLED: bool = (
        os.getenv("SELF_AWARENESS_ENABLED", "true").lower() == "true"
    )
    HESITATION_CHANCE: float = float(
        os.getenv("HESITATION_CHANCE", "0.15")
    )  # Chance to add hesitations (0.0-1.0)
    META_COMMENT_CHANCE: float = float(
        os.getenv("META_COMMENT_CHANCE", "0.10")
    )  # Chance for self-aware comments (0.0-1.0)
    SELF_CORRECTION_ENABLED: bool = (
        os.getenv("SELF_CORRECTION_ENABLED", "true").lower() == "true"
    )  # Allow bot to correct itself

    # Reminders
    REMINDERS_ENABLED: bool = os.getenv("REMINDERS_ENABLED", "true").lower() == "true"
    MAX_REMINDERS_PER_USER: int = int(os.getenv("MAX_REMINDERS_PER_USER", "10"))

    # Vision/Image Understanding
    VISION_ENABLED: bool = os.getenv("VISION_ENABLED", "true").lower() == "true"
    VISION_MODEL: str = os.getenv(
        "VISION_MODEL", "llava"
    )  # llava, llava-llama3, bakllava, etc.

    # Trivia Games
    TRIVIA_ENABLED: bool = os.getenv("TRIVIA_ENABLED", "true").lower() == "true"

    # Natural Language Understanding
    INTENT_RECOGNITION_ENABLED: bool = (
        os.getenv("INTENT_RECOGNITION_ENABLED", "true").lower() == "true"
    )
    NATURAL_LANGUAGE_REMINDERS: bool = (
        os.getenv("NATURAL_LANGUAGE_REMINDERS", "true").lower() == "true"
    )

    # Notes
    NOTES_ENABLED: bool = os.getenv("NOTES_ENABLED", "true").lower() == "true"

    # Logging Configuration
    LOG_LEVEL: str = os.getenv(
        "LOG_LEVEL", "INFO"
    ).upper()  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_TO_FILE: bool = os.getenv("LOG_TO_FILE", "true").lower() == "true"
    LOG_FILE_PATH: str = os.getenv("LOG_FILE_PATH", "logs/bot.log")
    LOG_MAX_BYTES: int = int(
        os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024))
    )  # 10MB default
    LOG_BACKUP_COUNT: int = int(
        os.getenv("LOG_BACKUP_COUNT", "5")
    )  # Keep 5 backup files
    LOG_FORMAT: str = os.getenv(
        "LOG_FORMAT", "text"
    )  # "json" or "text" for structured logging
    LOG_COMPRESS: bool = (
        os.getenv("LOG_COMPRESS", "true").lower() == "true"
    )  # Compress old logs

    # Chat Timing Configuration
    TYPING_INDICATOR_MIN_DELAY: float = float(
        os.getenv("TYPING_INDICATOR_MIN_DELAY", "0.5")
    )  # Minimum typing delay in seconds
    TYPING_INDICATOR_MAX_DELAY: float = float(
        os.getenv("TYPING_INDICATOR_MAX_DELAY", "2.0")
    )  # Maximum typing delay in seconds

    # Response Token Limits by Context
    RESPONSE_TOKENS_VERY_SHORT: int = int(os.getenv("RESPONSE_TOKENS_VERY_SHORT", "50"))
    RESPONSE_TOKENS_SHORT: int = int(os.getenv("RESPONSE_TOKENS_SHORT", "100"))
    RESPONSE_TOKENS_MEDIUM: int = int(os.getenv("RESPONSE_TOKENS_MEDIUM", "200"))
    RESPONSE_TOKENS_LONG: int = int(os.getenv("RESPONSE_TOKENS_LONG", "350"))
    RESPONSE_TOKENS_VERY_LONG: int = int(os.getenv("RESPONSE_TOKENS_VERY_LONG", "500"))

    # Performance Logging
    LOG_PERFORMANCE: bool = os.getenv("LOG_PERFORMANCE", "true").lower() == "true"
    LOG_LLM_REQUESTS: bool = os.getenv("LOG_LLM_REQUESTS", "true").lower() == "true"
    LOG_TTS_REQUESTS: bool = os.getenv("LOG_TTS_REQUESTS", "true").lower() == "true"

    # Analytics & Monitoring Configuration
    ANALYTICS_WEBSOCKET_UPDATE_INTERVAL: float = float(
        os.getenv("ANALYTICS_WEBSOCKET_UPDATE_INTERVAL", "2.0")
    )  # WebSocket update interval in seconds
    ERROR_SPIKE_WINDOW_SECONDS: int = int(
        os.getenv("ERROR_SPIKE_WINDOW_SECONDS", "300")
    )  # Time window for error spike detection (5 minutes)

    # Memory & Profile Configuration
    PROFILE_SAVE_INTERVAL_SECONDS: int = int(
        os.getenv("PROFILE_SAVE_INTERVAL_SECONDS", "60")
    )  # Profile auto-save interval
    RAG_RELEVANCE_THRESHOLD: float = float(
        os.getenv("RAG_RELEVANCE_THRESHOLD", "0.5")
    )  # Minimum relevance score for RAG results

    # Persona Behavior Timeouts
    PERSONA_STICKY_TIMEOUT: int = int(
        os.getenv("PERSONA_STICKY_TIMEOUT", "300")
    )  # Sticky persona timeout in seconds (5 minutes)
    PERSONA_FOLLOWUP_COOLDOWN: int = int(
        os.getenv("PERSONA_FOLLOWUP_COOLDOWN", "300")
    )  # Cooldown between followup questions (5 minutes)
    PERSONA_EVOLUTION_MILESTONES: List[int] = [
        int(x.strip())
        for x in os.getenv(
            "PERSONA_EVOLUTION_MILESTONES", "50,100,500,1000,5000"
        ).split(",")
        if x.strip()
    ]  # Message count milestones for evolution

    # Mood System Advanced Configuration
    MOOD_CHECK_INTERVAL_SECONDS: int = int(
        os.getenv("MOOD_CHECK_INTERVAL_SECONDS", "60")
    )  # How often to check/update mood
    MOOD_BOREDOM_TIMEOUT_SECONDS: int = int(
        os.getenv("MOOD_BOREDOM_TIMEOUT_SECONDS", "600")
    )  # Time before boredom kicks in (10 minutes)

    # Web Search Configuration
    WEB_SEARCH_RATE_LIMIT_DELAY: float = float(
        os.getenv("WEB_SEARCH_RATE_LIMIT_DELAY", "2.0")
    )  # Minimum delay between search requests

    # Service Cleanup Timeouts
    SERVICE_CLEANUP_TIMEOUT: float = float(
        os.getenv("SERVICE_CLEANUP_TIMEOUT", "2.0")
    )  # Timeout for service cleanup operations

    # Metrics Configuration
    METRICS_ENABLED: bool = os.getenv("METRICS_ENABLED", "true").lower() == "true"
    METRICS_SAVE_INTERVAL_MINUTES: int = int(
        os.getenv("METRICS_SAVE_INTERVAL_MINUTES", "60")
    )  # Default: hourly
    METRICS_RETENTION_DAYS: int = int(
        os.getenv("METRICS_RETENTION_DAYS", "30")
    )  # Keep 30 days

    # Performance Optimization Settings
    USE_STREAMING_FOR_LONG_RESPONSES: bool = (
        os.getenv("USE_STREAMING_FOR_LONG_RESPONSES", "true").lower() == "true"
    )
    STREAMING_TOKEN_THRESHOLD: int = int(
        os.getenv("STREAMING_TOKEN_THRESHOLD", "300")
    )  # Use streaming if > 300 tokens
    DYNAMIC_MAX_TOKENS: bool = (
        os.getenv("DYNAMIC_MAX_TOKENS", "false").lower() == "true"
    )  # Adjust max_tokens based on query

    # LLM Response Caching
    LLM_CACHE_ENABLED: bool = (
        os.getenv("LLM_CACHE_ENABLED", "true").lower() == "true"
    )  # Cache LLM responses to reduce API calls
    LLM_CACHE_MAX_SIZE: int = int(
        os.getenv("LLM_CACHE_MAX_SIZE", "1000")
    )  # Maximum cached responses (LRU eviction)
    LLM_CACHE_TTL_SECONDS: int = int(
        os.getenv("LLM_CACHE_TTL_SECONDS", "3600")
    )  # Cache entry lifetime (1 hour default)

    # LLM Model Fallback (LiteLLM-style)
    LLM_FALLBACK_ENABLED: bool = (
        os.getenv("LLM_FALLBACK_ENABLED", "false").lower() == "true"
    )  # Enable model fallback chain
    LLM_FALLBACK_MODELS: str = os.getenv(
        "LLM_FALLBACK_MODELS", ""
    )  # Comma-separated list: "model1:free,model2:paid"
    # Example: "x-ai/grok-beta:free,anthropic/claude-3.5-sonnet:paid"

    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration."""
        if not cls.DISCORD_TOKEN:
            raise ValueError("DISCORD_TOKEN is required")

        # Validate Ollama parameters
        if not (0.0 <= cls.OLLAMA_TEMPERATURE <= 2.0):
            raise ValueError(
                f"OLLAMA_TEMPERATURE must be between 0.0 and 2.0, got {cls.OLLAMA_TEMPERATURE}"
            )

        if cls.OLLAMA_MAX_TOKENS < 1:
            raise ValueError(
                f"OLLAMA_MAX_TOKENS must be at least 1, got {cls.OLLAMA_MAX_TOKENS}"
            )

        if not (0.0 <= cls.OLLAMA_MIN_P <= 1.0):
            raise ValueError(
                f"OLLAMA_MIN_P must be between 0.0 and 1.0, got {cls.OLLAMA_MIN_P}"
            )

        if cls.OLLAMA_TOP_K < 1:
            raise ValueError(f"OLLAMA_TOP_K must be at least 1, got {cls.OLLAMA_TOP_K}")

        if cls.OLLAMA_REPEAT_PENALTY < 0.0:
            raise ValueError(
                f"OLLAMA_REPEAT_PENALTY must be non-negative, got {cls.OLLAMA_REPEAT_PENALTY}"
            )

        # Validate chat history settings
        if cls.CHAT_HISTORY_MAX_MESSAGES < 1:
            raise ValueError(
                f"CHAT_HISTORY_MAX_MESSAGES must be at least 1, got {cls.CHAT_HISTORY_MAX_MESSAGES}"
            )

        # Validate timing settings
        if cls.NATURAL_TIMING_MIN_DELAY < 0:
            raise ValueError(
                f"NATURAL_TIMING_MIN_DELAY must be non-negative, got {cls.NATURAL_TIMING_MIN_DELAY}"
            )

        if cls.NATURAL_TIMING_MAX_DELAY < cls.NATURAL_TIMING_MIN_DELAY:
            raise ValueError(
                "NATURAL_TIMING_MAX_DELAY must be >= NATURAL_TIMING_MIN_DELAY"
            )

        # Validate typing indicator delays
        if cls.TYPING_INDICATOR_MIN_DELAY < 0:
            raise ValueError(
                f"TYPING_INDICATOR_MIN_DELAY must be non-negative, got {cls.TYPING_INDICATOR_MIN_DELAY}"
            )

        if cls.TYPING_INDICATOR_MAX_DELAY < cls.TYPING_INDICATOR_MIN_DELAY:
            raise ValueError(
                "TYPING_INDICATOR_MAX_DELAY must be >= TYPING_INDICATOR_MIN_DELAY"
            )

        # Validate token limits
        for token_var in [
            "RESPONSE_TOKENS_VERY_SHORT",
            "RESPONSE_TOKENS_SHORT",
            "RESPONSE_TOKENS_MEDIUM",
            "RESPONSE_TOKENS_LONG",
            "RESPONSE_TOKENS_VERY_LONG",
        ]:
            val = getattr(cls, token_var)
            if val < 1:
                raise ValueError(f"{token_var} must be at least 1, got {val}")

        # Validate RAG relevance threshold
        if not (0.0 <= cls.RAG_RELEVANCE_THRESHOLD <= 1.0):
            raise ValueError(
                f"RAG_RELEVANCE_THRESHOLD must be between 0.0 and 1.0, got {cls.RAG_RELEVANCE_THRESHOLD}"
            )

        # Validate timeouts
        if cls.PERSONA_STICKY_TIMEOUT < 0:
            raise ValueError(
                f"PERSONA_STICKY_TIMEOUT must be non-negative, got {cls.PERSONA_STICKY_TIMEOUT}"
            )

        if cls.SERVICE_CLEANUP_TIMEOUT < 0:
            raise ValueError(
                f"SERVICE_CLEANUP_TIMEOUT must be non-negative, got {cls.SERVICE_CLEANUP_TIMEOUT}"
            )

        # Validate probability values
        if not (0.0 <= cls.HESITATION_CHANCE <= 1.0):
            raise ValueError(
                f"HESITATION_CHANCE must be between 0.0 and 1.0, got {cls.HESITATION_CHANCE}"
            )

        if not (0.0 <= cls.META_COMMENT_CHANCE <= 1.0):
            raise ValueError(
                f"META_COMMENT_CHANCE must be between 0.0 and 1.0, got {cls.META_COMMENT_CHANCE}"
            )

        if not (0.0 <= cls.ACTIVITY_COMMENT_CHANCE <= 1.0):
            raise ValueError(
                f"ACTIVITY_COMMENT_CHANCE must be between 0.0 and 1.0, got {cls.ACTIVITY_COMMENT_CHANCE}"
            )

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
