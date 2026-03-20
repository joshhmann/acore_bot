"""Modular configuration system for Acore Bot.

This package provides a clean, organized way to manage configuration settings
across different subsystems of the bot.

Usage:
    from config import Config

    # Access settings
    if Config.rl.ENABLED:
        print(f"RL data dir: {Config.rl.DATA_DIR}")

    # Old style still works for backward compatibility
    if Config.RL_ENABLED:
        print(f"RL data dir: {Config.RL_DATA_DIR}")
"""

# ruff: noqa: E402

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import all config modules
from .base import BaseConfig
from .discord import DiscordConfig
from .llm import LLMConfig, OllamaConfig, OpenRouterConfig, ThinkingConfig, ChatConfig
from .persona import (
    PersonaConfig,
    EvolutionConfig,
    ConflictConfig,
    ActivityRoutingConfig,
    MoodConfig,
    CuriosityConfig,
    SelfAwarenessConfig,
    SemanticLorebookConfig,
)
from .rag import (
    RAGConfig,
    HybridSearchConfig,
    RerankerConfig,
    RealtimeIndexingConfig,
    QueryProcessingConfig,
    UserProfilesConfig,
)
from .voice import (
    TTSConfig,
    KokoroConfig,
    SupertonicConfig,
    RVCConfig,
    STTConfig,
    WhisperConfig,
    ParakeetConfig,
    VoiceListenerConfig,
    LuxTTSConfig,
    Qwen3TTSConfig,
)
from .rl import RLConfig
from .analytics import AnalyticsConfig, DashboardConfig
from .logging import LoggingConfig
from .agents import AgentConfig
from .features import (
    MemoryConfig,
    ConversationConfig,
    NaturalnessConfig,
    TimingConfig,
    VisionConfig,
    WebSearchConfig,
    TriviaConfig,
    NotesConfig,
    RemindersConfig,
    PerformanceConfig,
)


class Config:
    """Main configuration class providing access to all sub-configs.

    This class maintains backward compatibility with the old flat config structure
    while providing a new organized namespace approach.
    """

    # Sub-configurations (new organized way)
    discord = DiscordConfig()
    llm = LLMConfig()
    ollama = OllamaConfig()
    openrouter = OpenRouterConfig()
    thinking = ThinkingConfig()
    chat = ChatConfig()

    persona = PersonaConfig()
    evolution = EvolutionConfig()
    conflict = ConflictConfig()
    activity_routing = ActivityRoutingConfig()
    mood = MoodConfig()
    curiosity = CuriosityConfig()
    self_awareness = SelfAwarenessConfig()
    semantic_lorebook = SemanticLorebookConfig()

    rag = RAGConfig()
    hybrid_search = HybridSearchConfig()
    reranker = RerankerConfig()
    realtime_indexing = RealtimeIndexingConfig()
    query_processing = QueryProcessingConfig()
    user_profiles = UserProfilesConfig()

    voice = TTSConfig()
    kokoro = KokoroConfig()
    supertonic = SupertonicConfig()
    rvc = RVCConfig()
    stt = STTConfig()
    whisper = WhisperConfig()
    parakeet = ParakeetConfig()
    voice_listener = VoiceListenerConfig()
    luxtts = LuxTTSConfig()
    qwen3tts = Qwen3TTSConfig()

    rl = RLConfig()

    analytics = AnalyticsConfig()
    dashboard = DashboardConfig()

    logging = LoggingConfig()

    agent = AgentConfig()

    memory = MemoryConfig()
    conversation = ConversationConfig()
    naturalness = NaturalnessConfig()
    timing = TimingConfig()
    vision = VisionConfig()
    web_search = WebSearchConfig()
    trivia = TriviaConfig()
    notes = NotesConfig()
    reminders = RemindersConfig()
    performance = PerformanceConfig()

    # =========================================================================
    # BACKWARD COMPATIBILITY - Old flat config structure
    # =========================================================================

    # Discord
    DISCORD_TOKEN = discord.TOKEN
    COMMAND_PREFIX = discord.COMMAND_PREFIX
    AUTO_REPLY_ENABLED = discord.AUTO_REPLY_ENABLED
    AUTO_REPLY_CHANNELS = discord.AUTO_REPLY_CHANNELS
    NAME_TRIGGER_CHANNELS = discord.NAME_TRIGGER_CHANNELS
    AUTO_REPLY_WITH_VOICE = discord.AUTO_REPLY_WITH_VOICE
    BOT_MODE = discord.BOT_MODE
    CONVERSATION_TIMEOUT = discord.CONVERSATION_TIMEOUT
    IGNORED_USERS = discord.IGNORED_USERS
    DISCORD_LEGACY_OPERATOR_ENABLED = discord.DISCORD_LEGACY_OPERATOR_ENABLED
    DISCORD_LEGACY_PERSONA_ADMIN_ENABLED = discord.DISCORD_LEGACY_PERSONA_ADMIN_ENABLED
    DISCORD_LEGACY_CHAT_AMBIENT_ENABLED = discord.DISCORD_LEGACY_CHAT_AMBIENT_ENABLED
    DISCORD_LEGACY_CHAT_SESSION_ENABLED = discord.DISCORD_LEGACY_CHAT_SESSION_ENABLED
    DISCORD_LEGACY_CHAT_FALLBACK_ENABLED = discord.DISCORD_LEGACY_CHAT_FALLBACK_ENABLED
    DISCORD_LEGACY_SOCIAL_MODE_FOOTER_ENABLED = (
        discord.DISCORD_LEGACY_SOCIAL_MODE_FOOTER_ENABLED
    )
    DISCORD_LEGACY_SOCIAL_INSIGHTS_ENABLED = (
        discord.DISCORD_LEGACY_SOCIAL_INSIGHTS_ENABLED
    )
    DISCORD_VOICE_ENABLED = discord.DISCORD_VOICE_ENABLED

    # LLM
    LLM_PROVIDER = llm.PROVIDER
    USE_FUNCTION_CALLING = llm.USE_FUNCTION_CALLING
    LLM_CACHE_ENABLED = llm.CACHE_ENABLED
    LLM_CACHE_MAX_SIZE = llm.CACHE_MAX_SIZE
    LLM_CACHE_TTL_SECONDS = llm.CACHE_TTL_SECONDS
    LLM_FALLBACK_ENABLED = llm.FALLBACK_ENABLED
    LLM_FALLBACK_MODELS = llm.FALLBACK_MODELS
    LLM_FREQUENCY_PENALTY = llm.FREQUENCY_PENALTY
    LLM_PRESENCE_PENALTY = llm.PRESENCE_PENALTY
    LLM_TOP_P = llm.TOP_P

    # Ollama
    OLLAMA_HOST = ollama.HOST
    OLLAMA_MODEL = ollama.MODEL
    OLLAMA_TEMPERATURE = ollama.TEMPERATURE
    OLLAMA_MAX_TOKENS = ollama.MAX_TOKENS
    OLLAMA_MIN_P = ollama.MIN_P
    OLLAMA_TOP_K = ollama.TOP_K
    OLLAMA_REPEAT_PENALTY = ollama.REPEAT_PENALTY

    # LLM (aliases for backward compatibility with di_container.py)
    LLM_TEMPERATURE = ollama.TEMPERATURE
    LLM_MAX_TOKENS = ollama.MAX_TOKENS

    # OpenRouter
    OPENROUTER_API_KEY = openrouter.API_KEY
    OPENROUTER_MODEL = openrouter.MODEL
    OPENROUTER_URL = openrouter.URL
    OPENROUTER_TIMEOUT = openrouter.TIMEOUT
    OPENROUTER_STREAM_TIMEOUT = openrouter.STREAM_TIMEOUT

    # Thinking
    THINKING_MODEL = thinking.MODEL
    THINKING_MODEL_PROVIDER = thinking.MODEL_PROVIDER

    # Chat
    CLEAN_THINKING_OUTPUT = chat.CLEAN_THINKING_OUTPUT
    CHAT_HISTORY_ENABLED = chat.HISTORY_ENABLED
    CHAT_HISTORY_MAX_MESSAGES = chat.HISTORY_MAX_MESSAGES
    CONTEXT_MESSAGE_LIMIT = chat.CONTEXT_MESSAGE_LIMIT
    MAX_CONTEXT_TOKENS = chat.MAX_CONTEXT_TOKENS
    MODEL_CONTEXT_LIMITS = chat.MODEL_CONTEXT_LIMITS
    RESPONSE_STREAMING_ENABLED = chat.STREAMING_ENABLED
    STREAM_UPDATE_INTERVAL = chat.STREAM_UPDATE_INTERVAL
    RESPONSE_TOKENS_VERY_SHORT = chat.TOKENS_VERY_SHORT
    RESPONSE_TOKENS_SHORT = chat.TOKENS_SHORT
    RESPONSE_TOKENS_MEDIUM = chat.TOKENS_MEDIUM
    RESPONSE_TOKENS_LONG = chat.TOKENS_LONG
    RESPONSE_TOKENS_VERY_LONG = chat.TOKENS_VERY_LONG

    # Persona
    CHARACTERS_DIR = persona.CHARACTERS_DIR
    USE_PERSONA_SYSTEM = persona.USE_PERSONA_SYSTEM
    CHARACTER = persona.CHARACTER
    FRAMEWORK = persona.FRAMEWORK
    SYSTEM_PROMPT_FILE = persona.SYSTEM_PROMPT_FILE
    SYSTEM_PROMPT = persona.SYSTEM_PROMPT
    PERSONA_WEIGHTS = persona.WEIGHTS
    ACTIVE_PERSONAS = persona.ACTIVE_PERSONAS
    GLOBAL_RESPONSE_CHANCE = persona.GLOBAL_RESPONSE_CHANCE

    # Evolution
    PERSONA_EVOLUTION_ENABLED = evolution.ENABLED
    PERSONA_EVOLUTION_PATH = evolution.PATH
    PERSONA_EVOLUTION_MILESTONES = evolution.MILESTONES
    PERSONA_STICKY_TIMEOUT = evolution.STICKY_TIMEOUT
    PERSONA_FOLLOWUP_COOLDOWN = evolution.FOLLOWUP_COOLDOWN

    # Conflicts
    PERSONA_CONFLICTS_ENABLED = conflict.ENABLED
    CONFLICT_DECAY_RATE = conflict.DECAY_RATE
    CONFLICT_ESCALATION_AMOUNT = conflict.ESCALATION_AMOUNT

    # Activity Routing
    ACTIVITY_ROUTING_ENABLED = activity_routing.ENABLED
    ACTIVITY_ROUTING_PRIORITY = activity_routing.PRIORITY

    # Mood
    MOOD_SYSTEM_ENABLED = mood.ENABLED
    MOOD_UPDATE_FROM_INTERACTIONS = mood.UPDATE_FROM_INTERACTIONS
    MOOD_TIME_BASED = mood.TIME_BASED
    MOOD_DECAY_MINUTES = mood.DECAY_MINUTES
    MOOD_MAX_INTENSITY_SHIFT = mood.MAX_INTENSITY_SHIFT
    MOOD_CHECK_INTERVAL_SECONDS = mood.CHECK_INTERVAL_SECONDS
    MOOD_BOREDOM_TIMEOUT_SECONDS = mood.BOREDOM_TIMEOUT_SECONDS

    # Curiosity
    CURIOSITY_ENABLED = curiosity.ENABLED
    CURIOSITY_INDIVIDUAL_COOLDOWN_SECONDS = curiosity.INDIVIDUAL_COOLDOWN_SECONDS
    CURIOSITY_WINDOW_LIMIT_SECONDS = curiosity.WINDOW_LIMIT_SECONDS
    CURIOSITY_TOPIC_MEMORY_SIZE = curiosity.TOPIC_MEMORY_SIZE

    # Self-Awareness
    SELF_AWARENESS_ENABLED = self_awareness.ENABLED
    HESITATION_CHANCE = self_awareness.HESITATION_CHANCE
    META_COMMENT_CHANCE = self_awareness.META_COMMENT_CHANCE
    SELF_CORRECTION_ENABLED = self_awareness.SELF_CORRECTION_ENABLED

    # Semantic Lorebook
    SEMANTIC_LOREBOOK_ENABLED = semantic_lorebook.ENABLED
    SEMANTIC_LOREBOOK_THRESHOLD = semantic_lorebook.THRESHOLD
    SEMANTIC_LOREBOOK_CACHE_SIZE = semantic_lorebook.CACHE_SIZE

    # RAG
    RAG_ENABLED = rag.ENABLED
    RAG_VECTOR_STORE = rag.VECTOR_STORE
    RAG_DOCUMENTS_PATH = rag.DOCUMENTS_PATH
    RAG_TOP_K = rag.TOP_K
    RAG_IN_CHAT = rag.IN_CHAT
    RAG_RELEVANCE_THRESHOLD = rag.RELEVANCE_THRESHOLD

    # RAG backward compatibility aliases for di_container.py
    RAG_KNOWLEDGE_DIR = rag.DOCUMENTS_PATH
    RAG_COLLECTION_NAME = BaseConfig._get_env("RAG_COLLECTION_NAME", "default")

    # Hybrid Search
    RAG_HYBRID_SEARCH_ENABLED = hybrid_search.ENABLED
    RAG_KEYWORD_WEIGHT = hybrid_search.KEYWORD_WEIGHT
    RAG_SEMANTIC_WEIGHT = hybrid_search.SEMANTIC_WEIGHT
    RAG_KEYWORD_MATCH_THRESHOLD = hybrid_search.KEYWORD_MATCH_THRESHOLD
    RAG_BM25_ENABLED = hybrid_search.BM25_ENABLED
    RAG_BM25_K1 = hybrid_search.BM25_K1
    RAG_BM25_B = hybrid_search.BM25_B
    RAG_RRF_K = hybrid_search.RRF_K
    RAG_VECTOR_WEIGHT = hybrid_search.VECTOR_WEIGHT

    # Reranker
    RAG_RERANKER_ENABLED = reranker.ENABLED
    RAG_RERANKER_MODEL = reranker.MODEL
    RAG_RERANKER_TOP_K_MULTIPLIER = reranker.TOP_K_MULTIPLIER
    RAG_RERANKER_BATCH_SIZE = reranker.BATCH_SIZE
    RAG_RERANK_BATCH_SIZE = reranker.BATCH_SIZE
    RAG_RERANK_INITIAL_K = reranker.INITIAL_K
    RAG_RERANKER_CACHE_SIZE = reranker.CACHE_SIZE

    # Realtime Indexing
    RAG_REALTIME_INDEXING_ENABLED = realtime_indexing.ENABLED
    RAG_REALTIME_INDEXING = realtime_indexing.ENABLED
    RAG_INDEXING_DEBOUNCE_SECONDS = realtime_indexing.DEBOUNCE_SECONDS
    RAG_INDEXING_BATCH_SIZE = realtime_indexing.BATCH_SIZE
    RAG_INDEXING_QUEUE_SIZE = realtime_indexing.QUEUE_SIZE
    RAG_SUPPORTED_EXTENSIONS = realtime_indexing.SUPPORTED_EXTENSIONS

    # Query Processing
    RAG_QUERY_EXPANSION_ENABLED = query_processing.EXPANSION_ENABLED
    RAG_QUERY_EXPANSION = query_processing.EXPANSION
    RAG_QUERY_EXPANSION_TECHNIQUES = query_processing.EXPANSION_TECHNIQUES
    RAG_MAX_QUERY_EXPANSIONS = query_processing.MAX_EXPANSIONS
    RAG_SUB_QUERY_COUNT = query_processing.SUB_QUERY_COUNT

    # User Profiles
    USER_PROFILES_ENABLED = user_profiles.ENABLED
    USER_PROFILES_PATH = user_profiles.PATH
    USER_PROFILES_AUTO_LEARN = user_profiles.AUTO_LEARN
    USER_AFFECTION_ENABLED = user_profiles.AFFECTION_ENABLED
    USER_CONTEXT_IN_CHAT = user_profiles.CONTEXT_IN_CHAT
    PROFILE_SAVE_INTERVAL_SECONDS = user_profiles.SAVE_INTERVAL_SECONDS

    # Voice
    TTS_ENGINE = voice.ENGINE
    AUDIO_BITRATE = voice.BITRATE
    AUDIO_SAMPLE_RATE = voice.SAMPLE_RATE

    # Kokoro
    KOKORO_VOICE = kokoro.VOICE
    KOKORO_SPEED = kokoro.SPEED
    KOKORO_API_URL = kokoro.API_URL
    KOKORO_VOICE_CHIEF = kokoro.VOICE_CHIEF
    KOKORO_VOICE_ARBY = kokoro.VOICE_ARBY

    # Supertonic
    SUPERTONIC_VOICE = supertonic.VOICE
    SUPERTONIC_STEPS = supertonic.STEPS
    SUPERTONIC_SPEED = supertonic.SPEED

    # RVC
    RVC_ENABLED = rvc.ENABLED
    RVC_MODE = rvc.MODE
    RVC_DEVICE = rvc.DEVICE
    RVC_MODEL_PATH = rvc.MODEL_PATH
    DEFAULT_RVC_MODEL = rvc.DEFAULT_MODEL
    RVC_WEBUI_URL = rvc.WEBUI_URL
    RVC_PITCH_SHIFT = rvc.PITCH_SHIFT
    RVC_PROTECT = rvc.PROTECT
    RVC_INDEX_RATE = rvc.INDEX_RATE

    # STT
    STT_ENGINE = stt.ENGINE

    # Whisper
    WHISPER_ENABLED = whisper.ENABLED
    WHISPER_MODEL_SIZE = whisper.MODEL_SIZE
    WHISPER_DEVICE = whisper.DEVICE
    WHISPER_LANGUAGE = whisper.LANGUAGE
    WHISPER_SILENCE_THRESHOLD = whisper.SILENCE_THRESHOLD
    MAX_RECORDING_DURATION = whisper.MAX_RECORDING_DURATION

    # Parakeet
    PARAKEET_ENABLED = parakeet.ENABLED
    PARAKEET_API_URL = parakeet.API_URL
    PARAKEET_MODEL = parakeet.MODEL
    PARAKEET_DEVICE = parakeet.DEVICE
    PARAKEET_LANGUAGE = parakeet.LANGUAGE

    # Voice Listener
    VOICE_ENERGY_THRESHOLD = voice_listener.ENERGY_THRESHOLD
    VOICE_BOT_TRIGGER_WORDS = voice_listener.BOT_TRIGGER_WORDS

    # LuxTTS
    LUXTTS_API_URL = luxtts.API_URL
    LUXTTS_VOICE = luxtts.VOICE
    LUXTTS_SPEED = luxtts.SPEED

    # Qwen3TTS
    QWEN3TTS_API_URL = qwen3tts.API_URL
    QWEN3TTS_VOICE = qwen3tts.VOICE
    QWEN3TTS_LANGUAGE = qwen3tts.LANGUAGE
    QWEN3TTS_SPEED = qwen3tts.SPEED

    # RL
    RL_ENABLED = rl.ENABLED
    RL_DATA_DIR = rl.DATA_DIR
    RL_EPSILON_START = rl.EPSILON_START
    RL_EPSILON_END = rl.EPSILON_END
    RL_EPSILON_DECAY = rl.EPSILON_DECAY
    RL_Q_INIT = rl.Q_INIT
    RL_LEARNING_RATE = rl.LEARNING_RATE
    RL_DISCOUNT_FACTOR = rl.DISCOUNT_FACTOR
    RL_PERSIST_INTERVAL = rl.PERSIST_INTERVAL
    RL_LOCK_TIMEOUT = rl.LOCK_TIMEOUT
    RL_MAX_LATENCY_SEC = rl.MAX_LATENCY_SEC
    RL_REWARD_SPEED_THRESHOLD = rl.REWARD_SPEED_THRESHOLD
    RL_ALGORITHM = rl.ALGORITHM
    RL_REPLAY_BUFFER_SIZE = rl.REPLAY_BUFFER_SIZE
    RL_BATCH_SIZE = rl.BATCH_SIZE
    RL_WARMUP_STEPS = rl.WARMUP_STEPS
    RL_TRAIN_EVERY = rl.TRAIN_EVERY
    RL_STATE_DIM = rl.STATE_DIM
    RL_USE_HIERARCHICAL = rl.USE_HIERARCHICAL
    RL_USE_TRANSFER = rl.USE_TRANSFER
    RL_USE_MULTI_OBJECTIVE = rl.USE_MULTI_OBJECTIVE
    RL_OFFLINE_PRETRAINING = rl.OFFLINE_PRETRAINING
    RL_REWARD_LONG_MSG_CHAR = rl.REWARD_LONG_MSG_CHAR
    RL_CONTEXT_MAX_AGE = rl.CONTEXT_MAX_AGE
    RL_MAX_AGENTS_PER_CHANNEL = rl.MAX_AGENTS_PER_CHANNEL

    # Analytics
    METRICS_ENABLED = analytics.ENABLED
    METRICS_SAVE_INTERVAL_MINUTES = analytics.SAVE_INTERVAL_MINUTES
    METRICS_RETENTION_DAYS = analytics.RETENTION_DAYS
    ANALYTICS_WEBSOCKET_UPDATE_INTERVAL = analytics.WEBSOCKET_UPDATE_INTERVAL
    ERROR_SPIKE_WINDOW_SECONDS = analytics.ERROR_SPIKE_WINDOW_SECONDS

    # Dashboard
    ANALYTICS_DASHBOARD_ENABLED = dashboard.ENABLED
    ANALYTICS_DASHBOARD_PORT = dashboard.PORT
    ANALYTICS_PASSWORD = dashboard.PASSWORD

    # Logging
    LOG_LEVEL = logging.LEVEL
    LOG_TO_FILE = logging.TO_FILE
    LOG_FILE_PATH = logging.FILE_PATH
    LOG_MAX_BYTES = logging.MAX_BYTES
    LOG_BACKUP_COUNT = logging.BACKUP_COUNT
    LOG_FORMAT = logging.FORMAT
    LOG_COMPRESS = logging.COMPRESS
    LOG_PERFORMANCE = logging.PERFORMANCE
    LOG_LLM_REQUESTS = logging.LLM_REQUESTS
    LOG_TTS_REQUESTS = logging.TTS_REQUESTS

    # Memory
    MEMORY_CLEANUP_ENABLED = memory.CLEANUP_ENABLED
    MEMORY_CLEANUP_INTERVAL_HOURS = memory.CLEANUP_INTERVAL_HOURS
    MAX_TEMP_FILE_AGE_HOURS = memory.MAX_TEMP_FILE_AGE_HOURS
    MAX_HISTORY_AGE_DAYS = memory.MAX_HISTORY_AGE_DAYS

    # Conversation
    CONVERSATION_SUMMARIZATION_ENABLED = conversation.SUMMARIZATION_ENABLED
    AUTO_SUMMARIZE_THRESHOLD = conversation.AUTO_SUMMARIZE_THRESHOLD
    STORE_SUMMARIES_IN_RAG = conversation.STORE_SUMMARIES_IN_RAG
    BOTCONV_RL_TRAINING_ENABLED = conversation.BOTCONV_RL_TRAINING_ENABLED

    # Naturalness
    NATURALNESS_ENABLED = naturalness.ENABLED
    REACTIONS_ENABLED = naturalness.REACTIONS_ENABLED
    REACTIONS_CHANCE_MULTIPLIER = naturalness.REACTIONS_CHANCE_MULTIPLIER
    ACTIVITY_AWARENESS_ENABLED = naturalness.ACTIVITY_AWARENESS_ENABLED
    ACTIVITY_COMMENT_CHANCE = naturalness.ACTIVITY_COMMENT_CHANCE
    ACTIVITY_COOLDOWN_SECONDS = naturalness.ACTIVITY_COOLDOWN_SECONDS

    # Backward-compatibility: Behavior (new unified namespace)
    BEHAVIOR_REACTION_PROBABILITY = naturalness.REACTION_PROBABILITY
    BEHAVIOR_PROACTIVE_PROBABILITY = naturalness.PROACTIVE_PROBABILITY
    BEHAVIOR_COOLDOWN_SECONDS = naturalness.COOLDOWN_SECONDS
    BEHAVIOR_MOOD_SHIFT_MAX = naturalness.MOOD_SHIFT_MAX

    # Timing
    NATURAL_TIMING_ENABLED = timing.ENABLED
    NATURAL_TIMING_MIN_DELAY = timing.MIN_DELAY
    NATURAL_TIMING_MAX_DELAY = timing.MAX_DELAY
    TYPING_INDICATOR_MIN_DELAY = timing.TYPING_MIN_DELAY
    TYPING_INDICATOR_MAX_DELAY = timing.TYPING_MAX_DELAY

    # Proactive (merged into Naturalness)
    PROACTIVE_ENGAGEMENT_ENABLED = naturalness.PROACTIVE_ENABLED
    PROACTIVE_MIN_MESSAGES = naturalness.PROACTIVE_MIN_MESSAGES
    PROACTIVE_COOLDOWN = naturalness.PROACTIVE_COOLDOWN

    # Adaptive Timing (merged into Timing)
    ADAPTIVE_TIMING_ENABLED = timing.ADAPTIVE_ENABLED
    ADAPTIVE_TIMING_LEARNING_WINDOW_DAYS = timing.LEARNING_WINDOW_DAYS
    CHANNEL_ACTIVITY_PROFILE_PATH = timing.CHANNEL_PROFILE_PATH

    # Vision
    VISION_ENABLED = vision.ENABLED
    VISION_MODEL = vision.MODEL

    # Web Search
    WEB_SEARCH_ENABLED = web_search.ENABLED
    WEB_SEARCH_ENGINE = web_search.ENGINE
    WEB_SEARCH_MAX_RESULTS = web_search.MAX_RESULTS
    WEB_SEARCH_RATE_LIMIT_DELAY = web_search.RATE_LIMIT_DELAY

    # Trivia
    TRIVIA_ENABLED = trivia.ENABLED

    # Notes
    NOTES_ENABLED = notes.ENABLED

    # Reminders
    REMINDERS_ENABLED = reminders.ENABLED
    MAX_REMINDERS_PER_USER = reminders.MAX_PER_USER

    # Performance
    USE_STREAMING_FOR_LONG_RESPONSES = performance.USE_STREAMING_FOR_LONG_RESPONSES
    STREAMING_TOKEN_THRESHOLD = performance.STREAMING_TOKEN_THRESHOLD
    DYNAMIC_MAX_TOKENS = performance.DYNAMIC_MAX_TOKENS
    SERVICE_CLEANUP_TIMEOUT = performance.SERVICE_CLEANUP_TIMEOUT

    # Agent Orchestration
    AGENT_ROUTING_ENABLED = agent.ROUTING_ENABLED
    AGENT_ROUTING_STRATEGY = agent.ROUTING_STRATEGY
    AGENT_MIN_CONFIDENCE = agent.MIN_CONFIDENCE
    AGENT_CHAINING_ENABLED = agent.CHAINING_ENABLED
    AGENT_MAX_CHAIN_LENGTH = agent.MAX_CHAIN_LENGTH
    AGENT_HEALTH_CHECK_INTERVAL = agent.HEALTH_CHECK_INTERVAL
    AGENT_TIMEOUT_SECONDS = agent.TIMEOUT_SECONDS

    # Paths (backward compatibility)
    DATA_DIR: Path = Path("./data")
    CHAT_HISTORY_DIR: Path = DATA_DIR / "chat_history"
    VOICE_MODELS_DIR: Path = DATA_DIR / "voice_models"
    TEMP_DIR: Path = DATA_DIR / "temp"
    SUMMARY_DIR: Path = DATA_DIR / "conversation_summaries"

    # Image Generation (backward compatibility)
    IMAGE_GENERATION_ENABLED: bool = (
        os.getenv("IMAGE_GENERATION_ENABLED", "false").lower() == "true"
    )
    IMAGE_GENERATION_API_KEY: str = os.getenv("IMAGE_GENERATION_API_KEY", "")
    IMAGE_PROVIDER: str = os.getenv("IMAGE_PROVIDER", "openai").lower()
    IMAGE_SIZE_DEFAULT: str = os.getenv("IMAGE_SIZE_DEFAULT", "1024x1024")
    IMAGE_QUALITY_DEFAULT: str = os.getenv("IMAGE_QUALITY_DEFAULT", "standard")
    IMAGE_STYLE_DEFAULT: str = os.getenv("IMAGE_STYLE_DEFAULT", "vivid")
    COMFYUI_SERVER_URL: str = os.getenv("COMFYUI_SERVER_URL", "http://127.0.0.1:8188")
    COMFYUI_WORKFLOW_ID: Optional[str] = os.getenv("COMFYUI_WORKFLOW_ID")
    LITELLM_API_KEY: str = os.getenv("LITELLM_API_KEY", "dummy")
    LITELLM_BASE_URL: str = os.getenv("LITELLM_BASE_URL", "")
    LITELLM_IMAGE_MODEL: str = os.getenv("LITELLM_IMAGE_MODEL", "dall-e-3")
    KOBOLDCPP_URL: str = os.getenv("KOBOLDCPP_URL", "http://127.0.0.1:5001")
    KOBOLDCPP_STEPS: int = int(os.getenv("KOBOLDCPP_STEPS", "30"))
    KOBOLDCPP_CFG_SCALE: float = float(os.getenv("KOBOLDCPP_CFG_SCALE", "7.0"))
    KOBOLDCPP_SAMPLER: str = os.getenv("KOBOLDCPP_SAMPLER", "Euler a")

    # Code Execution (backward compatibility)
    CODE_EXECUTION_ENABLED: bool = (
        os.getenv("CODE_EXECUTION_ENABLED", "false").lower() == "true"
    )
    CODE_EXECUTION_TIMEOUT: int = int(os.getenv("CODE_EXECUTION_TIMEOUT", "30"))
    CODE_SANDBOX_ENABLED: bool = (
        os.getenv("CODE_SANDBOX_ENABLED", "true").lower() == "true"
    )
    CODE_MAX_OUTPUT_SIZE: int = int(os.getenv("CODE_MAX_OUTPUT_SIZE", "10000"))

    # Bot-to-Bot Conversation Settings (backward compatibility)
    BOT_CONVERSATION_ENABLED: bool = (
        os.getenv("BOT_CONVERSATION_ENABLED", "true").lower() == "true"
    )
    BOT_CONVERSATION_MAX_TURNS: int = int(os.getenv("BOT_CONVERSATION_MAX_TURNS", "10"))
    BOT_CONVERSATION_TIMEOUT_MINUTES: int = int(
        os.getenv("BOT_CONVERSATION_TIMEOUT_MINUTES", "30")
    )
    BOT_CONVERSATION_DETAILED_METRICS: bool = (
        os.getenv("BOT_CONVERSATION_DETAILED_METRICS", "false").lower() == "true"
    )

    # RL Exploration Mode (backward compatibility)
    RL_EXPLORATION_MODE: bool = (
        os.getenv("RL_EXPLORATION_MODE", "false").lower() == "true"
    )
    RL_EXPLORATION_ACTIVITY_THRESHOLD: int = int(
        os.getenv("RL_EXPLORATION_ACTIVITY_THRESHOLD", "5")
    )
    RL_EXPLORATION_BONUS_MAX: float = float(
        os.getenv("RL_EXPLORATION_BONUS_MAX", "3.0")
    )
    RL_EPSILON_BOOST_FACTOR: float = float(os.getenv("RL_EPSILON_BOOST_FACTOR", "2.0"))
    RL_EPSILON_BOOST_DECAY: float = float(os.getenv("RL_EPSILON_BOOST_DECAY", "0.999"))

    @classmethod
    def validate(cls):
        """Validate configuration and create necessary directories."""
        # Create data directories
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.CHAT_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        cls.VOICE_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        cls.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        cls.SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

        # Create RL data directory if RL is enabled
        if cls.RL_ENABLED:
            cls.RL_DATA_DIR.mkdir(parents=True, exist_ok=True)

        return True
