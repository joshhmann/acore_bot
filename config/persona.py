"""Persona and character configuration."""

from pathlib import Path
from .base import BaseConfig


class PersonaConfig(BaseConfig):
    """Persona system configuration."""

    CHARACTERS_DIR: Path = BaseConfig._get_env_path(
        "CHARACTERS_DIR", "./prompts/characters"
    )

    # AI-First Persona System
    USE_PERSONA_SYSTEM: bool = BaseConfig._get_env_bool("USE_PERSONA_SYSTEM", True)
    CHARACTER: str = BaseConfig._get_env("CHARACTER", "dagoth_ur")
    FRAMEWORK: str = BaseConfig._get_env("FRAMEWORK", "neuro")

    # System Prompt
    SYSTEM_PROMPT_FILE: Path = BaseConfig._get_env_path(
        "SYSTEM_PROMPT_FILE", "./prompts/default.txt"
    )
    SYSTEM_PROMPT: str = BaseConfig._get_env("SYSTEM_PROMPT", "")

    # Persona weights for selection
    WEIGHTS: dict = {}

    # Active personas list (all 16 personas)
    ACTIVE_PERSONAS: list = [
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
        "arbiter.json",
        "chief.json",
        "fred.json",
        "gothmommy.json",
        "tom.json",
    ]

    # Global response chance
    GLOBAL_RESPONSE_CHANCE: float = 1.0


class EvolutionConfig(BaseConfig):
    """Character evolution system configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("PERSONA_EVOLUTION_ENABLED", True)
    PATH: Path = BaseConfig._get_env_path(
        "PERSONA_EVOLUTION_PATH", "./data/persona_evolution"
    )
    MILESTONES: list = BaseConfig._get_env_int_list(
        "PERSONA_EVOLUTION_MILESTONES", [50, 100, 500, 1000, 5000]
    )

    # Timeouts
    STICKY_TIMEOUT: int = BaseConfig._get_env_int("PERSONA_STICKY_TIMEOUT", 30)
    FOLLOWUP_COOLDOWN: int = BaseConfig._get_env_int("PERSONA_FOLLOWUP_COOLDOWN", 60)


class ConflictConfig(BaseConfig):
    """Persona conflict system configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("PERSONA_CONFLICTS_ENABLED", True)
    DECAY_RATE: float = BaseConfig._get_env_float("CONFLICT_DECAY_RATE", 0.1)
    ESCALATION_AMOUNT: float = BaseConfig._get_env_float(
        "CONFLICT_ESCALATION_AMOUNT", 0.2
    )


class ActivityRoutingConfig(BaseConfig):
    """Activity-based persona routing configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("ACTIVITY_ROUTING_ENABLED", True)
    PRIORITY: int = BaseConfig._get_env_int("ACTIVITY_ROUTING_PRIORITY", 100)


class MoodConfig(BaseConfig):
    """Mood system configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("MOOD_SYSTEM_ENABLED", True)
    UPDATE_FROM_INTERACTIONS: bool = BaseConfig._get_env_bool(
        "MOOD_UPDATE_FROM_INTERACTIONS", True
    )
    TIME_BASED: bool = BaseConfig._get_env_bool("MOOD_TIME_BASED", True)
    DECAY_MINUTES: int = BaseConfig._get_env_int("MOOD_DECAY_MINUTES", 30)
    MAX_INTENSITY_SHIFT: float = BaseConfig._get_env_float(
        "MOOD_MAX_INTENSITY_SHIFT", 0.1
    )
    CHECK_INTERVAL_SECONDS: int = BaseConfig._get_env_int(
        "MOOD_CHECK_INTERVAL_SECONDS", 60
    )
    BOREDOM_TIMEOUT_SECONDS: int = BaseConfig._get_env_int(
        "MOOD_BOREDOM_TIMEOUT_SECONDS", 600
    )


class CuriosityConfig(BaseConfig):
    """Curiosity-driven follow-up questions configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("CURIOSITY_ENABLED", True)
    INDIVIDUAL_COOLDOWN_SECONDS: int = BaseConfig._get_env_int(
        "CURIOSITY_INDIVIDUAL_COOLDOWN_SECONDS", 300
    )
    WINDOW_LIMIT_SECONDS: int = BaseConfig._get_env_int(
        "CURIOSITY_WINDOW_LIMIT_SECONDS", 900
    )
    TOPIC_MEMORY_SIZE: int = BaseConfig._get_env_int("CURIOSITY_TOPIC_MEMORY_SIZE", 20)


class SelfAwarenessConfig(BaseConfig):
    """Self-awareness configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("SELF_AWARENESS_ENABLED", True)
    HESITATION_CHANCE: float = BaseConfig._get_env_float("HESITATION_CHANCE", 0.15)
    META_COMMENT_CHANCE: float = BaseConfig._get_env_float("META_COMMENT_CHANCE", 0.10)
    SELF_CORRECTION_ENABLED: bool = BaseConfig._get_env_bool(
        "SELF_CORRECTION_ENABLED", True
    )


class SemanticLorebookConfig(BaseConfig):
    """Semantic lorebook configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("SEMANTIC_LOREBOOK_ENABLED", True)
    THRESHOLD: float = BaseConfig._get_env_float("SEMANTIC_LOREBOOK_THRESHOLD", 0.65)
    CACHE_SIZE: int = BaseConfig._get_env_int("SEMANTIC_LOREBOOK_CACHE_SIZE", 1000)
