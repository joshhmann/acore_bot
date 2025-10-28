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

    # Chat
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

    # RAG (Retrieval-Augmented Generation)
    RAG_ENABLED: bool = os.getenv("RAG_ENABLED", "false").lower() == "true"
    RAG_VECTOR_STORE: str = os.getenv("RAG_VECTOR_STORE", "./data/vector_store")
    RAG_DOCUMENTS_PATH: str = os.getenv("RAG_DOCUMENTS_PATH", "./data/documents")
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "3"))

    # MCP (Model Context Protocol)
    MCP_ENABLED: bool = os.getenv("MCP_ENABLED", "false").lower() == "true"
    MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL", "http://localhost:8080")

    # User Profiles
    USER_PROFILES_ENABLED: bool = os.getenv("USER_PROFILES_ENABLED", "true").lower() == "true"
    USER_PROFILES_PATH: Path = Path(os.getenv("USER_PROFILES_PATH", "./data/user_profiles"))
    USER_PROFILES_AUTO_LEARN: bool = os.getenv("USER_PROFILES_AUTO_LEARN", "true").lower() == "true"  # AI-powered automatic learning
    USER_AFFECTION_ENABLED: bool = os.getenv("USER_AFFECTION_ENABLED", "true").lower() == "true"
    USER_CONTEXT_IN_CHAT: bool = os.getenv("USER_CONTEXT_IN_CHAT", "true").lower() == "true"

    # Web Search
    WEB_SEARCH_ENABLED: bool = os.getenv("WEB_SEARCH_ENABLED", "false").lower() == "true"
    WEB_SEARCH_ENGINE: str = os.getenv("WEB_SEARCH_ENGINE", "duckduckgo")
    WEB_SEARCH_MAX_RESULTS: int = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "3"))

    # Voice/TTS
    TTS_ENGINE: str = os.getenv("TTS_ENGINE", "edge")  # "edge" or "kokoro"

    # Edge TTS Settings
    DEFAULT_TTS_VOICE: str = os.getenv("DEFAULT_TTS_VOICE", "en-US-AriaNeural")
    TTS_RATE: str = os.getenv("TTS_RATE", "+0%")
    TTS_VOLUME: str = os.getenv("TTS_VOLUME", "+0%")

    # Kokoro TTS Settings
    KOKORO_VOICE: str = os.getenv("KOKORO_VOICE", "am_adam")
    KOKORO_SPEED: float = float(os.getenv("KOKORO_SPEED", "1.0"))
    KOKORO_VOICE_CHIEF: str = os.getenv("KOKORO_VOICE_CHIEF", "am_onyx")
    KOKORO_VOICE_ARBY: str = os.getenv("KOKORO_VOICE_ARBY", "bm_george")

    # RVC
    RVC_ENABLED: bool = os.getenv("RVC_ENABLED", "false").lower() == "true"
    RVC_MODE: str = os.getenv("RVC_MODE", "webui")  # "inferpy" or "webui"
    RVC_MODEL_PATH: Path = Path(os.getenv("RVC_MODEL_PATH", "./data/voice_models"))
    DEFAULT_RVC_MODEL: str = os.getenv("DEFAULT_RVC_MODEL", "GOTHMOMMY")
    RVC_DEVICE: str = os.getenv("RVC_DEVICE", "cpu")
    RVC_WEBUI_URL: str = os.getenv("RVC_WEBUI_URL", "http://localhost:7865")

    # Audio
    AUDIO_BITRATE: int = int(os.getenv("AUDIO_BITRATE", "96"))
    AUDIO_SAMPLE_RATE: int = int(os.getenv("AUDIO_SAMPLE_RATE", "48000"))

    # Paths
    DATA_DIR: Path = Path("./data")
    CHAT_HISTORY_DIR: Path = DATA_DIR / "chat_history"
    VOICE_MODELS_DIR: Path = DATA_DIR / "voice_models"
    TEMP_DIR: Path = DATA_DIR / "temp"

    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration."""
        if not cls.DISCORD_TOKEN:
            raise ValueError("DISCORD_TOKEN is required")

        # Create necessary directories
        cls.DATA_DIR.mkdir(exist_ok=True)
        cls.CHAT_HISTORY_DIR.mkdir(exist_ok=True)
        cls.VOICE_MODELS_DIR.mkdir(exist_ok=True)
        cls.TEMP_DIR.mkdir(exist_ok=True)

        return True

# Validate on import
Config.validate()
