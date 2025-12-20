"""Persona configuration loader and manager."""
import json
import logging
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VoiceConfig:
    """Voice configuration for a persona."""
    kokoro_voice: str = "am_adam"
    kokoro_speed: float = 1.0
    edge_voice: str = "en-US-AriaNeural"
    edge_rate: str = "+0%"
    edge_volume: str = "+0%"


@dataclass
class RVCConfig:
    """RVC configuration for a persona."""
    enabled: bool = False
    model: Optional[str] = None
    pitch_shift: int = 0


@dataclass
class BehaviorConfig:
    """Behavior configuration for a persona."""
    clear_history_on_switch: bool = True
    auto_reply_enabled: bool = True
    affection_multiplier: float = 1.0


@dataclass
class PersonaConfig:
    """Complete persona configuration."""
    name: str
    display_name: str
    description: str
    prompt_file: str
    voice: VoiceConfig
    rvc: RVCConfig
    behavior: BehaviorConfig
    tags: list[str]
    rag_boost_category: Optional[str] = None  # Category to boost in RAG
    prompt_text: Optional[str] = None  # Loaded separately


class PersonaLoader:
    """Loads and manages persona configurations."""

    def __init__(self, prompts_dir: Path = Path("prompts")):
        """Initialize persona loader.

        Args:
            prompts_dir: Directory containing persona files
        """
        self.prompts_dir = Path(prompts_dir)
        self.personas: Dict[str, PersonaConfig] = {}
        self._load_all_personas()

    def _load_all_personas(self):
        """Load all persona configurations from the prompts directory."""
        if not self.prompts_dir.exists():
            logger.warning(f"Prompts directory not found: {self.prompts_dir}")
            return

        # Load JSON configs
        for config_file in self.prompts_dir.glob("*.json"):
            try:
                persona = self._load_persona_config(config_file)
                if persona:
                    self.personas[persona.name] = persona
                    logger.info(f"Loaded persona config: {persona.name}")
            except Exception as e:
                logger.error(f"Failed to load persona config {config_file}: {e}")

        # For backward compatibility: load .txt files without configs
        for txt_file in self.prompts_dir.glob("*.txt"):
            persona_name = txt_file.stem
            if persona_name not in self.personas:
                # Create default config for legacy persona
                persona = self._create_default_persona(persona_name, txt_file)
                self.personas[persona_name] = persona
                logger.info(f"Created default config for legacy persona: {persona_name}")

        logger.info(f"Loaded {len(self.personas)} personas total")

    def _load_persona_config(self, config_file: Path) -> Optional[PersonaConfig]:
        """Load a persona configuration from JSON file.

        Args:
            config_file: Path to JSON config file

        Returns:
            PersonaConfig object or None if failed
        """
        with open(config_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Load voice config
        voice_data = data.get("voice", {})
        voice = VoiceConfig(
            kokoro_voice=voice_data.get("kokoro_voice", "am_adam"),
            kokoro_speed=voice_data.get("kokoro_speed", 1.0),
            edge_voice=voice_data.get("edge_voice", "en-US-AriaNeural"),
            edge_rate=voice_data.get("edge_rate", "+0%"),
            edge_volume=voice_data.get("edge_volume", "+0%"),
        )

        # Load RVC config
        rvc_data = data.get("rvc", {})
        rvc = RVCConfig(
            enabled=rvc_data.get("enabled", False),
            model=rvc_data.get("model"),
            pitch_shift=rvc_data.get("pitch_shift", 0),
        )

        # Load behavior config
        behavior_data = data.get("behavior", {})
        behavior = BehaviorConfig(
            clear_history_on_switch=behavior_data.get("clear_history_on_switch", True),
            auto_reply_enabled=behavior_data.get("auto_reply_enabled", True),
            affection_multiplier=behavior_data.get("affection_multiplier", 1.0),
        )

        # Create persona config
        persona = PersonaConfig(
            name=data.get("name", config_file.stem),
            display_name=data.get("display_name", data.get("name", config_file.stem).title()),
            description=data.get("description", "No description"),
            prompt_file=data.get("prompt_file", f"{config_file.stem}.txt"),
            voice=voice,
            rvc=rvc,
            behavior=behavior,
            tags=data.get("tags", []),
            rag_boost_category=data.get("rag_boost_category"),
        )

        # Load prompt text
        prompt_path = self.prompts_dir / persona.prompt_file
        if prompt_path.exists():
            with open(prompt_path, 'r', encoding='utf-8') as f:
                persona.prompt_text = f.read().strip()
        else:
            logger.warning(f"Prompt file not found: {prompt_path}")

        return persona

    def _create_default_persona(self, name: str, txt_file: Path) -> PersonaConfig:
        """Create a default persona config for a legacy .txt file.

        Args:
            name: Persona name
            txt_file: Path to .txt file

        Returns:
            PersonaConfig with default settings
        """
        # Load prompt text
        prompt_text = None
        if txt_file.exists():
            with open(txt_file, 'r', encoding='utf-8') as f:
                prompt_text = f.read().strip()

        return PersonaConfig(
            name=name,
            display_name=name.title(),
            description=f"Legacy persona: {name}",
            prompt_file=txt_file.name,
            voice=VoiceConfig(),
            rvc=RVCConfig(),
            behavior=BehaviorConfig(),
            tags=[],
            prompt_text=prompt_text,
        )

    def get_persona(self, name: str) -> Optional[PersonaConfig]:
        """Get a persona configuration by name.

        Args:
            name: Persona name

        Returns:
            PersonaConfig or None if not found
        """
        return self.personas.get(name.lower())

    def list_personas(self) -> list[str]:
        """List all available persona names.

        Returns:
            List of persona names
        """
        return sorted(self.personas.keys())

    def get_personas_by_tag(self, tag: str) -> list[PersonaConfig]:
        """Get all personas with a specific tag.

        Args:
            tag: Tag to filter by

        Returns:
            List of matching PersonaConfig objects
        """
        return [p for p in self.personas.values() if tag.lower() in [t.lower() for t in p.tags]]

    def reload(self):
        """Reload all persona configurations from disk."""
        self.personas.clear()
        self._load_all_personas()

    def create_default_config(self, persona_name: str) -> str:
        """Generate a default JSON config for a persona.

        Args:
            persona_name: Name of the persona

        Returns:
            JSON string of default config
        """
        default_config = {
            "name": persona_name,
            "display_name": persona_name.title(),
            "description": f"{persona_name.title()} personality",
            "prompt_file": f"{persona_name}.txt",
            "voice": {
                "kokoro_voice": "am_adam",
                "kokoro_speed": 1.0,
                "edge_voice": "en-US-AriaNeural",
                "edge_rate": "+0%",
                "edge_volume": "+0%"
            },
            "rvc": {
                "enabled": False,
                "model": None,
                "pitch_shift": 0
            },
            "behavior": {
                "clear_history_on_switch": True,
                "auto_reply_enabled": True,
                "affection_multiplier": 1.0
            },
            "tags": []
        }
        return json.dumps(default_config, indent=2)
