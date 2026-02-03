"""Voice, TTS, and audio configuration."""

from pathlib import Path
from .base import BaseConfig


class TTSConfig(BaseConfig):
    """Text-to-Speech configuration."""

    ENGINE: str = BaseConfig._get_env("TTS_ENGINE", "kokoro_api")

    # Audio Quality
    BITRATE: int = BaseConfig._get_env_int("AUDIO_BITRATE", 96)
    SAMPLE_RATE: int = BaseConfig._get_env_int("AUDIO_SAMPLE_RATE", 48000)


class KokoroConfig(BaseConfig):
    """Kokoro TTS configuration."""

    VOICE: str = BaseConfig._get_env("KOKORO_VOICE", "am_adam")
    SPEED: float = BaseConfig._get_env_float("KOKORO_SPEED", 1.0)
    API_URL: str = BaseConfig._get_env("KOKORO_API_URL", "http://localhost:8880")

    # Character-specific voices
    VOICE_CHIEF: str = BaseConfig._get_env("KOKORO_VOICE_CHIEF", "am_onyx")
    VOICE_ARBY: str = BaseConfig._get_env("KOKORO_VOICE_ARBY", "bm_george")


class SupertonicConfig(BaseConfig):
    """Supertonic TTS configuration."""

    VOICE: str = BaseConfig._get_env("SUPERTONIC_VOICE", "M1")
    STEPS: int = BaseConfig._get_env_int("SUPERTONIC_STEPS", 5)
    SPEED: float = BaseConfig._get_env_float("SUPERTONIC_SPEED", 1.05)


class RVCConfig(BaseConfig):
    """RVC (Voice Conversion) configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("RVC_ENABLED", False)
    MODE: str = BaseConfig._get_env("RVC_MODE", "webui")
    DEVICE: str = BaseConfig._get_env("RVC_DEVICE", "cpu")
    MODEL_PATH: Path = BaseConfig._get_env_path("RVC_MODEL_PATH", "./data/voice_models")
    DEFAULT_MODEL: str = BaseConfig._get_env("DEFAULT_RVC_MODEL", "GOTHMOMMY")
    WEBUI_URL: str = BaseConfig._get_env("RVC_WEBUI_URL", "http://localhost:7865")

    # Voice Tuning
    PITCH_SHIFT: int = BaseConfig._get_env_int("RVC_PITCH_SHIFT", 0)
    PROTECT: float = BaseConfig._get_env_float("RVC_PROTECT", 0.33)
    INDEX_RATE: float = BaseConfig._get_env_float("RVC_INDEX_RATE", 0.75)


class STTConfig(BaseConfig):
    """Speech-to-Text configuration."""

    ENGINE: str = BaseConfig._get_env("STT_ENGINE", "whisper")


class WhisperConfig(BaseConfig):
    """Whisper STT configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("WHISPER_ENABLED", False)
    MODEL_SIZE: str = BaseConfig._get_env("WHISPER_MODEL_SIZE", "base")
    DEVICE: str = BaseConfig._get_env("WHISPER_DEVICE", "auto")
    LANGUAGE: str = BaseConfig._get_env("WHISPER_LANGUAGE", "en")
    SILENCE_THRESHOLD: float = BaseConfig._get_env_float(
        "WHISPER_SILENCE_THRESHOLD", 1.0
    )
    MAX_RECORDING_DURATION: int = BaseConfig._get_env_int("MAX_RECORDING_DURATION", 30)


class ParakeetConfig(BaseConfig):
    """Parakeet STT configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("PARAKEET_ENABLED", False)
    API_URL: str = BaseConfig._get_env("PARAKEET_API_URL", "http://localhost:8890")
    MODEL: str = BaseConfig._get_env("PARAKEET_MODEL", "nvidia/parakeet-tdt-0.6b-v3")
    DEVICE: str = BaseConfig._get_env("PARAKEET_DEVICE", "auto")
    LANGUAGE: str = BaseConfig._get_env("PARAKEET_LANGUAGE", "en")


class VoiceListenerConfig(BaseConfig):
    """Voice listener configuration."""

    ENERGY_THRESHOLD: int = BaseConfig._get_env_int("VOICE_ENERGY_THRESHOLD", 500)
    BOT_TRIGGER_WORDS: list = BaseConfig._get_env_list(
        "VOICE_BOT_TRIGGER_WORDS", ["bot", "assistant", "hey", "help", "question"]
    )
