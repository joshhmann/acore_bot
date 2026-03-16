"""Cognitive Mode Definitions for Partner in Crime Architecture.

This module defines the three cognitive modes:
- Creative: Brainstorming, generation, artistic, exploratory
- Logic: Analysis, coding, debugging, factual reasoning
- Facilitator: Orchestrates between modes, decides routing
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any


class CognitiveMode(Enum):
    """Cognitive modes for different thinking styles."""

    CREATIVE = auto()
    LOGIC = auto()
    FACILITATOR = auto()

    def __str__(self) -> str:
        return self.name.lower()


@dataclass
class ModeConfig:
    """Configuration for a cognitive mode.

    Attributes:
        mode: The cognitive mode this config applies to
        prompt_template: Path to the prompt template file
        temperature: Sampling temperature (0.0 - 2.0)
        max_tokens: Maximum tokens to generate
        provider_preference: Ordered list of preferred providers
        system_prompt_modifier: Additional system prompt context
        stop_sequences: Sequences that stop generation
    """

    mode: CognitiveMode
    prompt_template: str
    temperature: float = 0.7
    max_tokens: int = 2048
    provider_preference: list[str] = field(
        default_factory=lambda: ["openai", "anthropic"]
    )
    system_prompt_modifier: str = ""
    stop_sequences: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate configuration."""
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError(
                f"Temperature must be between 0.0 and 2.0, got {self.temperature}"
            )
        if self.max_tokens < 1:
            raise ValueError(f"max_tokens must be positive, got {self.max_tokens}")
        if not self.provider_preference:
            raise ValueError("provider_preference cannot be empty")


class ModeConfigRegistry:
    """Registry for mode configurations."""

    def __init__(self, config_path: str = "prompts/modes"):
        self.config_path = Path(config_path)
        self._configs: dict[CognitiveMode, ModeConfig] = {}
        self._load_default_configs()

    def _load_default_configs(self) -> None:
        """Load default configurations for all modes."""
        # Creative mode - high temperature for brainstorming
        self._configs[CognitiveMode.CREATIVE] = ModeConfig(
            mode=CognitiveMode.CREATIVE,
            prompt_template=str(self.config_path / "creative.txt"),
            temperature=0.9,
            max_tokens=2048,
            provider_preference=["openai/gpt-4", "anthropic/claude-3-opus"],
            system_prompt_modifier="You are in creative mode. Think expansively, generate novel ideas, explore possibilities.",
        )

        # Logic mode - low temperature for precision
        self._configs[CognitiveMode.LOGIC] = ModeConfig(
            mode=CognitiveMode.LOGIC,
            prompt_template=str(self.config_path / "logic.txt"),
            temperature=0.3,
            max_tokens=2048,
            provider_preference=["anthropic/claude-3-opus", "openai/gpt-4"],
            system_prompt_modifier="You are in logic mode. Analyze carefully, reason step by step, be precise and factual.",
        )

        # Facilitator mode - medium temperature for balanced decision-making
        self._configs[CognitiveMode.FACILITATOR] = ModeConfig(
            mode=CognitiveMode.FACILITATOR,
            prompt_template=str(self.config_path / "facilitator.txt"),
            temperature=0.5,
            max_tokens=1024,
            provider_preference=["openai/gpt-4", "anthropic/claude-3-sonnet"],
            system_prompt_modifier="You are in facilitator mode. Orchestrate between approaches, make balanced decisions, route appropriately.",
        )

    def get_config(self, mode: CognitiveMode) -> ModeConfig:
        """Get configuration for a cognitive mode."""
        if mode not in self._configs:
            raise KeyError(f"No configuration found for mode: {mode}")
        return self._configs[mode]

    def set_config(self, mode: CognitiveMode, config: ModeConfig) -> None:
        """Set configuration for a cognitive mode."""
        self._configs[mode] = config

    def get_prompt_template(self, mode: CognitiveMode) -> str:
        """Load and return the prompt template for a mode."""
        config = self.get_config(mode)
        template_path = Path(config.prompt_template)

        if template_path.exists():
            return template_path.read_text()

        # Return default template if file doesn't exist
        return self._get_default_template(mode)

    def _get_default_template(self, mode: CognitiveMode) -> str:
        """Get default template content for a mode."""
        templates = {
            CognitiveMode.CREATIVE: """You are in creative mode. Let your imagination flow.

Approach this with:
- Open-minded exploration
- Novel idea generation
- Artistic and lateral thinking
- Brainstorming multiple possibilities
- Challenging assumptions

Current context: {context}
User request: {request}

Generate creative ideas and approaches:""",
            CognitiveMode.LOGIC: """You are in logic mode. Think analytically and precisely.

Approach this with:
- Step-by-step reasoning
- Evidence-based analysis
- Logical deduction
- Attention to detail
- Factual accuracy

Current context: {context}
User request: {request}

Provide logical analysis:""",
            CognitiveMode.FACILITATOR: """You are in facilitator mode. Orchestrate and decide.

Your role:
- Assess which mode (Creative or Logic) is most appropriate
- Consider context and user needs
- Make routing decisions
- Balance multiple perspectives

Current context: {context}
User request: {request}

Recommended approach:""",
        }
        return templates.get(mode, "")

    def list_modes(self) -> list[CognitiveMode]:
        """List all available cognitive modes."""
        return list(self._configs.keys())


# Global registry instance
_mode_registry: ModeConfigRegistry | None = None


def get_mode_registry() -> ModeConfigRegistry:
    """Get the global mode registry instance."""
    global _mode_registry
    if _mode_registry is None:
        _mode_registry = ModeConfigRegistry()
    return _mode_registry


def get_mode_config(mode: CognitiveMode) -> ModeConfig:
    """Get configuration for a cognitive mode."""
    return get_mode_registry().get_config(mode)


def get_prompt_template(mode: CognitiveMode) -> str:
    """Get prompt template for a cognitive mode."""
    return get_mode_registry().get_prompt_template(mode)
