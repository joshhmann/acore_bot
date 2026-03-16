"""Configuration System for Social Intelligence Layer.

Supports:
- Per-user configuration: learning settings, mode preferences, privacy
- Per-persona configuration: mode preferences, allowed modes, providers
- Global configuration: system-wide defaults and feature flags
- Hot-reload: changes apply without restart
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional
import yaml


@dataclass
class UserConfig:
    """Per-user SIL configuration."""

    user_id: str

    # Learning settings
    enable_learning: bool = True
    enable_adaptation: bool = True
    exploration_rate: float = 0.2

    # Mode preferences
    preferred_mode: Optional[str] = None  # "creative", "logic", "facilitator"
    allowed_modes: list[str] = field(
        default_factory=lambda: ["creative", "logic", "facilitator"]
    )

    # Privacy settings
    share_learning_data: bool = True
    allow_personalization: bool = True

    # Trigger settings
    enable_proactive_engagement: bool = True
    max_engagements_per_hour: int = 3
    quiet_hours: Optional[tuple[int, int]] = None  # (start, end) in 24h format

    # Feedback settings
    enable_implicit_feedback: bool = True
    enable_explicit_feedback: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserConfig":
        """Create from dictionary."""
        # Handle quiet_hours tuple
        if "quiet_hours" in data and data["quiet_hours"] is not None:
            if isinstance(data["quiet_hours"], list):
                data["quiet_hours"] = tuple(data["quiet_hours"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class PersonaConfig:
    """Per-persona SIL configuration."""

    persona_id: str

    # Mode settings
    default_mode: str = "creative"
    allowed_modes: list[str] = field(
        default_factory=lambda: ["creative", "logic", "facilitator"]
    )
    can_switch_modes: bool = True

    # Provider preferences
    preferred_provider: str = "auto"  # "auto", "openai", "anthropic", etc.
    fallback_providers: list[str] = field(
        default_factory=lambda: ["openai", "anthropic"]
    )

    # Style settings
    default_enthusiasm: float = 0.5
    default_emoji_frequency: float = 0.5

    # Autonomy settings
    max_proactive_triggers_per_hour: int = 5
    enable_mood_tracking: bool = True
    enable_relationship_tracking: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PersonaConfig":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class GlobalConfig:
    """Global SIL configuration."""

    # Learning parameters
    default_exploration_rate: float = 0.2
    min_exploration_rate: float = 0.05
    learning_rate_decay: float = 0.995

    # Trigger parameters
    default_trigger_threshold: float = 0.6
    max_triggers_per_hour_global: int = 10

    # Feature flags
    enable_learning: bool = True
    enable_proactive_engagement: bool = True
    enable_mode_switching: bool = True
    enable_feedback_collection: bool = True
    enable_metrics: bool = True

    # Performance
    max_context_history: int = 100
    bandit_update_frequency: int = 1  # Update every N interactions

    # Debug
    debug_mode: bool = False
    log_all_decisions: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GlobalConfig":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SILConfigManager:
    """Manages SIL configuration with hot-reload support."""

    def __init__(self, config_dir: str = "data/social_intelligence/config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self._user_configs: dict[str, UserConfig] = {}
        self._persona_configs: dict[str, PersonaConfig] = {}
        self._global_config: GlobalConfig = GlobalConfig()

        # Hot-reload tracking
        self._last_reload: float = 0
        self._reload_interval: float = 30.0  # Check every 30 seconds
        self._file_mtimes: dict[str, float] = {}

        # Load initial configs
        self._load_all()

    def _load_all(self) -> None:
        """Load all configurations."""
        self._load_global_config()
        self._load_user_configs()
        self._load_persona_configs()
        self._last_reload = time.time()

    def _load_global_config(self) -> None:
        """Load global configuration."""
        config_path = self.config_dir / "global.yaml"
        if config_path.exists():
            with open(config_path, "r") as f:
                data = yaml.safe_load(f)
            if data:
                self._global_config = GlobalConfig.from_dict(data)
            self._file_mtimes[str(config_path)] = config_path.stat().st_mtime

    def _load_user_configs(self) -> None:
        """Load all user configurations."""
        user_dir = self.config_dir / "users"
        if not user_dir.exists():
            return

        for config_file in user_dir.glob("*.yaml"):
            user_id = config_file.stem
            with open(config_file, "r") as f:
                data = yaml.safe_load(f)
            if data:
                self._user_configs[user_id] = UserConfig.from_dict(data)
            self._file_mtimes[str(config_file)] = config_file.stat().st_mtime

    def _load_persona_configs(self) -> None:
        """Load all persona configurations."""
        persona_dir = self.config_dir / "personas"
        if not persona_dir.exists():
            return

        for config_file in persona_dir.glob("*.yaml"):
            persona_id = config_file.stem
            with open(config_file, "r") as f:
                data = yaml.safe_load(f)
            if data:
                self._persona_configs[persona_id] = PersonaConfig.from_dict(data)
            self._file_mtimes[str(config_file)] = config_file.stat().st_mtime

    def check_reload(self) -> bool:
        """Check if any config files have changed and reload if needed.

        Returns:
            True if any configs were reloaded
        """
        if time.time() - self._last_reload < self._reload_interval:
            return False

        reloaded = False

        # Check global config
        global_path = self.config_dir / "global.yaml"
        if global_path.exists():
            mtime = global_path.stat().st_mtime
            if (
                str(global_path) not in self._file_mtimes
                or mtime > self._file_mtimes[str(global_path)]
            ):
                self._load_global_config()
                reloaded = True

        # Check user configs
        user_dir = self.config_dir / "users"
        if user_dir.exists():
            for config_file in user_dir.glob("*.yaml"):
                mtime = config_file.stat().st_mtime
                if (
                    str(config_file) not in self._file_mtimes
                    or mtime > self._file_mtimes[str(config_file)]
                ):
                    self._load_user_configs()
                    reloaded = True
                    break

        # Check persona configs
        persona_dir = self.config_dir / "personas"
        if persona_dir.exists():
            for config_file in persona_dir.glob("*.yaml"):
                mtime = config_file.stat().st_mtime
                if (
                    str(config_file) not in self._file_mtimes
                    or mtime > self._file_mtimes[str(config_file)]
                ):
                    self._load_persona_configs()
                    reloaded = True
                    break

        self._last_reload = time.time()
        return reloaded

    def get_user_config(self, user_id: str) -> UserConfig:
        """Get configuration for a user."""
        self.check_reload()
        if user_id not in self._user_configs:
            # Create default config
            self._user_configs[user_id] = UserConfig(user_id=user_id)
        return self._user_configs[user_id]

    def get_persona_config(self, persona_id: str) -> PersonaConfig:
        """Get configuration for a persona."""
        self.check_reload()
        if persona_id not in self._persona_configs:
            # Create default config
            self._persona_configs[persona_id] = PersonaConfig(persona_id=persona_id)
        return self._persona_configs[persona_id]

    def get_global_config(self) -> GlobalConfig:
        """Get global configuration."""
        self.check_reload()
        return self._global_config

    def save_user_config(self, user_id: str, config: UserConfig) -> None:
        """Save user configuration."""
        user_dir = self.config_dir / "users"
        user_dir.mkdir(exist_ok=True)

        config_path = user_dir / f"{user_id}.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config.to_dict(), f, default_flow_style=False)

        self._user_configs[user_id] = config
        self._file_mtimes[str(config_path)] = config_path.stat().st_mtime

    def save_persona_config(self, persona_id: str, config: PersonaConfig) -> None:
        """Save persona configuration."""
        persona_dir = self.config_dir / "personas"
        persona_dir.mkdir(exist_ok=True)

        config_path = persona_dir / f"{persona_id}.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config.to_dict(), f, default_flow_style=False)

        self._persona_configs[persona_id] = config
        self._file_mtimes[str(config_path)] = config_path.stat().st_mtime

    def save_global_config(self, config: GlobalConfig) -> None:
        """Save global configuration."""
        config_path = self.config_dir / "global.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config.to_dict(), f, default_flow_style=False)

        self._global_config = config
        self._file_mtimes[str(config_path)] = config_path.stat().st_mtime

    def get_effective_config(
        self,
        user_id: str,
        persona_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get effective configuration combining user, persona, and global settings.

        Priority: User > Persona > Global

        Args:
            user_id: User ID
            persona_id: Optional persona ID

        Returns:
            Merged configuration dictionary
        """
        user_config = self.get_user_config(user_id)
        persona_config = self.get_persona_config(persona_id) if persona_id else None
        global_config = self.get_global_config()

        effective = {}

        # Start with global defaults
        effective.update(global_config.to_dict())

        # Override with persona settings
        if persona_config:
            effective.update(
                {
                    "default_mode": persona_config.default_mode,
                    "allowed_modes": persona_config.allowed_modes,
                    "preferred_provider": persona_config.preferred_provider,
                    "fallback_providers": persona_config.fallback_providers,
                }
            )

        # Override with user settings
        effective.update(
            {
                "enable_learning": user_config.enable_learning,
                "enable_adaptation": user_config.enable_adaptation,
                "exploration_rate": user_config.exploration_rate,
                "preferred_mode": user_config.preferred_mode
                or effective.get("default_mode"),
                "allowed_modes": user_config.allowed_modes,
                "enable_proactive_engagement": user_config.enable_proactive_engagement,
                "max_engagements_per_hour": user_config.max_engagements_per_hour,
                "quiet_hours": user_config.quiet_hours,
            }
        )

        return effective


# Global instance
_config_manager: Optional[SILConfigManager] = None


def get_config_manager() -> SILConfigManager:
    """Get global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = SILConfigManager()
    return _config_manager
