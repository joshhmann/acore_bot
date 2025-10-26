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
    OLLAMA_TEMPERATURE: float = float(os.getenv("OLLAMA_TEMPERATURE", "0.7"))
    OLLAMA_MAX_TOKENS: int = int(os.getenv("OLLAMA_MAX_TOKENS", "500"))

    # Chat
    CHAT_HISTORY_ENABLED: bool = os.getenv("CHAT_HISTORY_ENABLED", "true").lower() == "true"
    CHAT_HISTORY_MAX_MESSAGES: int = int(os.getenv("CHAT_HISTORY_MAX_MESSAGES", "20"))
    AUTO_REPLY_ENABLED: bool = os.getenv("AUTO_REPLY_ENABLED", "false").lower() == "true"
    AUTO_REPLY_CHANNELS: List[int] = [
        int(x.strip()) for x in os.getenv("AUTO_REPLY_CHANNELS", "").split(",") if x.strip()
    ]

    # Voice/TTS
    DEFAULT_TTS_VOICE: str = os.getenv("DEFAULT_TTS_VOICE", "en-US-AriaNeural")
    TTS_RATE: str = os.getenv("TTS_RATE", "+0%")
    TTS_VOLUME: str = os.getenv("TTS_VOLUME", "+0%")

    # RVC
    RVC_ENABLED: bool = os.getenv("RVC_ENABLED", "true").lower() == "true"
    RVC_MODEL_PATH: Path = Path(os.getenv("RVC_MODEL_PATH", "./data/voice_models"))
    DEFAULT_RVC_MODEL: str = os.getenv("DEFAULT_RVC_MODEL", "default")

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
