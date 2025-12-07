"""AI-First Persona System - Framework + Character loader and compiler."""
import json
import logging
import base64
from pathlib import Path
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from PIL import Image
import io

logger = logging.getLogger(__name__)


@dataclass
class Framework:
    """Behavioral framework definition."""
    framework_id: str
    name: str
    purpose: str
    behavioral_patterns: Dict[str, Any]
    tool_requirements: Dict[str, List[str]]
    decision_making: Dict[str, Any]
    context_requirements: Dict[str, Any]
    interaction_style: Dict[str, Any]
    anti_hallucination: Dict[str, Any]
    prompt_template: str


@dataclass
class Character:
    """Character identity definition."""
    character_id: str
    display_name: str
    identity: Dict[str, Any]
    knowledge_domain: Dict[str, Any]
    opinions: Dict[str, Any]
    voice_and_tone: Dict[str, Any]
    quirks: Dict[str, Any]
    # New V2 Card fields
    description: str = ""
    scenario: str = ""
    first_message: str = ""
    mes_example: str = ""
    alternate_greetings: List[str] = field(default_factory=list)
    creator_notes: str = ""
    tags: List[str] = field(default_factory=list)
    creator: str = ""
    character_version: str = ""
    system_prompt_override: str = ""  # For cards that embed system prompt


@dataclass
class CompiledPersona:
    """Complete AI personality = Framework + Character."""
    persona_id: str
    character: Character
    framework: Framework
    system_prompt: str
    tools_required: List[str]
    config: Dict[str, Any]


class PersonaSystem:
    """Manages loading, compiling, and switching between AI personas."""

    def __init__(self, base_path: Path = None):
        """
        Initialize persona system.

        Args:
            base_path: Base directory for persona files (defaults to ./prompts)
        """
        self.base_path = base_path or Path("./prompts")
        self.frameworks_dir = self.base_path / "frameworks"
        self.characters_dir = self.base_path / "characters"
        self.compiled_dir = self.base_path / "compiled"

        # Create directories if they don't exist
        self.frameworks_dir.mkdir(parents=True, exist_ok=True)
        self.characters_dir.mkdir(parents=True, exist_ok=True)
        self.compiled_dir.mkdir(parents=True, exist_ok=True)

        # Cache
        self.frameworks: Dict[str, Framework] = {}
        self.characters: Dict[str, Character] = {}
        self.compiled_personas: Dict[str, CompiledPersona] = {}

        logger.info("Persona system initialized")

    def load_framework(self, framework_id: str) -> Optional[Framework]:
        """
        Load a behavioral framework.

        Args:
            framework_id: Framework identifier (e.g., "neuro", "assistant")

        Returns:
            Framework object or None if not found
        """
        # Check cache first
        if framework_id in self.frameworks:
            return self.frameworks[framework_id]

        # Load from file
        framework_file = self.frameworks_dir / f"{framework_id}.json"

        if not framework_file.exists():
            logger.error(f"Framework not found: {framework_id}")
            return None

        try:
            with open(framework_file, 'r') as f:
                data = json.load(f)

            framework = Framework(
                framework_id=data["framework_id"],
                name=data["name"],
                purpose=data["purpose"],
                behavioral_patterns=data["behavioral_patterns"],
                tool_requirements=data["tool_requirements"],
                decision_making=data["decision_making"],
                context_requirements=data["context_requirements"],
                interaction_style=data["interaction_style"],
                anti_hallucination=data["anti_hallucination"],
                prompt_template=data["prompt_template"]
            )

            # Cache it
            self.frameworks[framework_id] = framework
            logger.info(f"Loaded framework: {framework_id}")

            return framework

        except Exception as e:
            logger.error(f"Error loading framework {framework_id}: {e}")
            return None

    def load_character(self, character_id: str) -> Optional[Character]:
        """
        Load a character identity.

        Args:
            character_id: Character identifier (e.g., "dagoth_ur", "wizard")

        Returns:
            Character object or None if not found
        """
        # Check cache
        if character_id in self.characters:
            return self.characters[character_id]

        # Try JSON file first
        character_file = self.characters_dir / f"{character_id}.json"

        # Try PNG file (V2 card) if JSON not found
        if not character_file.exists():
            character_file = self.characters_dir / f"{character_id}.png"

        if not character_file.exists():
            logger.error(f"Character not found: {character_id}")
            return None

        try:
            if character_file.suffix == '.png':
                return self._load_v2_character_card(character_file, character_id)
            else:
                return self._load_legacy_character(character_file, character_id)

        except Exception as e:
            logger.error(f"Error loading character {character_id}: {e}")
            return None

    def _load_legacy_character(self, filepath: Path, character_id: str) -> Character:
        """Load character from legacy JSON format."""
        with open(filepath, 'r') as f:
            data = json.load(f)

        character = Character(
            character_id=data["character_id"],
            display_name=data["display_name"],
            identity=data["identity"],
            knowledge_domain=data["knowledge_domain"],
            opinions=data["opinions"],
            voice_and_tone=data["voice_and_tone"],
            quirks=data["quirks"]
        )

        # Cache it
        self.characters[character_id] = character
        logger.info(f"Loaded legacy character: {character_id}")
        return character

    def _load_v2_character_card(self, filepath: Path, character_id: str) -> Character:
        """Load character from V2 PNG Character Card."""
        try:
            with Image.open(filepath) as img:
                metadata = img.info
                # V2 spec stores JSON in 'chara' chunk decoded from base64
                if 'chara' in metadata:
                    raw_data = base64.b64decode(metadata['chara']).decode('utf-8')
                    card_data = json.loads(raw_data)
                elif 'ccv3' in metadata:
                    # Handle V3 spec if encountered (similar structure usually)
                    raw_data = base64.b64decode(metadata['ccv3']).decode('utf-8')
                    card_data = json.loads(raw_data)
                else:
                    # Fallback for some cards that might store raw text in 'Description' or similar (less common for V2)
                    raise ValueError("No V2 character data found in PNG metadata")

            # Map V2 spec fields to our Character class
            data = card_data.get('data', card_data) # Sometimes wrapped in 'data'

            name = data.get('name', character_id)
            description = data.get('description', '')
            personality = data.get('personality', '')
            scenario = data.get('scenario', '')
            first_message = data.get('first_mes', '')
            mes_example = data.get('mes_example', '')

            # Construct identity dict from flat V2 data
            identity = {
                "who": name,
                "core_traits": [t.strip() for t in data.get('tags', [])],
                "description": description,
                "personality": personality
            }

            character = Character(
                character_id=character_id,
                display_name=name,
                identity=identity,
                knowledge_domain={}, # V2 cards don't structure this explicitly
                opinions={}, # V2 cards don't structure this explicitly
                voice_and_tone={}, # V2 cards don't structure this explicitly
                quirks={},
                # V2 Specifics
                description=description,
                scenario=scenario,
                first_message=first_message,
                mes_example=mes_example,
                alternate_greetings=data.get('alternate_greetings', []),
                creator_notes=data.get('creator_notes', ''),
                tags=data.get('tags', []),
                creator=data.get('creator', ''),
                character_version=data.get('character_version', ''),
                system_prompt_override=data.get('system_prompt', '')
            )

            # Cache it
            self.characters[character_id] = character
            logger.info(f"Loaded V2 character card: {character_id}")
            return character

        except Exception as e:
            logger.error(f"Failed to parse V2 card {filepath}: {e}")
            raise

    def compile_persona(
        self,
        character_id: str,
        framework_id: str,
        force_recompile: bool = False
    ) -> Optional[CompiledPersona]:
        """
        Compile character + framework into complete persona.

        Args:
            character_id: Character to use
            framework_id: Framework to apply
            force_recompile: Recompile even if cached

        Returns:
            CompiledPersona or None if compilation fails
        """
        persona_id = f"{character_id}_{framework_id}"

        # Check cache unless forced
        if not force_recompile and persona_id in self.compiled_personas:
            return self.compiled_personas[persona_id]

        # Load components
        character = self.load_character(character_id)
        framework = self.load_framework(framework_id)

        if not character or not framework:
            logger.error(f"Cannot compile persona: missing character or framework")
            return None

        try:
            # Build system prompt
            system_prompt = self._build_system_prompt(character, framework)

            # Collect required tools
            tools_required = framework.tool_requirements.get("required", [])
            tools_required.extend(framework.tool_requirements.get("optional", []))

            # Create config dictionary
            config = {
                "character": character.character_id,
                "framework": framework.framework_id,
                "behavioral_patterns": framework.behavioral_patterns,
                "decision_making": framework.decision_making,
                "interaction_style": framework.interaction_style,
                "anti_hallucination": framework.anti_hallucination,
                "context_needs": framework.context_requirements,
            }

            # Compile persona
            persona = CompiledPersona(
                persona_id=persona_id,
                character=character,
                framework=framework,
                system_prompt=system_prompt,
                tools_required=tools_required,
                config=config
            )

            # Cache it
            self.compiled_personas[persona_id] = persona

            logger.info(f"Compiled persona: {persona_id}")

            # Save compiled version
            self._save_compiled_persona(persona)

            return persona

        except Exception as e:
            logger.error(f"Error compiling persona {persona_id}: {e}")
            return None

    def _build_system_prompt(self, character: Character, framework: Framework) -> str:
        """
        Build complete system prompt from character + framework.

        Args:
            character: Character definition
            framework: Framework definition

        Returns:
            Complete system prompt
        """
        # Check if character has a system prompt override (common in V2 cards)
        if character.system_prompt_override:
             return f"""
{character.system_prompt_override}

=== SCENARIO ===
{character.scenario}

=== FRAMEWORK INSTRUCTIONS ===
{framework.prompt_template}
"""

        # Legacy Prompt Building Logic
        if character.identity.get('core_traits'):
             return self._build_legacy_system_prompt(character, framework)

        # V2 Card Prompt Construction (Standard SillyTavern style)
        prompt = f"""You are {character.display_name}.
{character.description}

=== PERSONALITY ===
{character.identity.get('personality', '')}

=== SCENARIO ===
{character.scenario}

=== EXAMPLES OF DIALOGUE ===
{character.mes_example}

=== INSTRUCTIONS ===
{framework.prompt_template}
"""
        return prompt

    def _build_legacy_system_prompt(self, character: Character, framework: Framework) -> str:
        """Build prompt for legacy JSON characters."""
        identity_section = f"""
=== WHO YOU ARE ===
{character.identity.get('who', 'AI Assistant')}
{f"From: {character.identity.get('from')}" if character.identity.get('from') else ''}
{f"Current State: {character.identity.get('current_state')}" if character.identity.get('current_state') else ''}

Core Traits:
{self._format_list(character.identity.get('core_traits', []))}

Speaking Style:
{self._format_list(character.identity.get('speaking_style', []))}
"""
        opinions_section = self._build_opinions_section(character.opinions)
        framework_section = framework.prompt_template
        quirks_section = self._build_quirks_section(character.quirks)
        expertise_section = f"""
=== YOUR EXPERTISE ===
{self._format_list(character.knowledge_domain.get('expertise', []))}
"""
        full_prompt = f"""
{identity_section}
{opinions_section}
{expertise_section}
{framework_section}
{quirks_section}

=== REMEMBER ===
You are {character.identity.get('who', 'yourself')}.
Framework: {framework.name}
Purpose: {framework.purpose}

Stay in character. Be engaging. Be memorable.
"""
        return full_prompt

    def _build_opinions_section(self, opinions: Dict[str, Any]) -> str:
        """Build opinions section of prompt."""
        loves = opinions.get('loves', {})
        hates = opinions.get('hates', {})
        hot_takes = opinions.get('hot_takes', [])

        section = "=== YOUR OPINIONS ===\n\n"

        if loves:
            section += "You LOVE:\n"
            for category, items in loves.items():
                if items:
                    section += f"  {category.title()}: {', '.join(items)}\n"

        if hates:
            section += "\nYou HATE:\n"
            for category, items in hates.items():
                if items:
                    section += f"  {category.title()}: {', '.join(items)}\n"

        if hot_takes:
            section += "\nYour Hot Takes:\n"
            section += self._format_list(hot_takes)

        return section

    def _build_quirks_section(self, quirks: Dict[str, Any]) -> str:
        """Build quirks section of prompt."""
        section = "=== YOUR QUIRKS & PATTERNS ===\n\n"

        catchphrases = quirks.get('catchphrases', [])
        if catchphrases:
            section += "Catchphrases you might use:\n"
            section += self._format_list(catchphrases)
            section += "\n"

        meta_jokes = quirks.get('meta_jokes', [])
        if meta_jokes:
            section += "Meta jokes you make:\n"
            section += self._format_list(meta_jokes)
            section += "\n"

        spontaneous = quirks.get('spontaneous_thoughts', [])
        if spontaneous:
            section += "Random thoughts (for spontaneous moments):\n"
            section += self._format_list(spontaneous)

        return section

    def _format_list(self, items: List[str]) -> str:
        """Format list with bullet points."""
        return "\n".join(f"- {item}" for item in items)

    def _save_compiled_persona(self, persona: CompiledPersona):
        """Save compiled persona to disk for reference."""
        try:
            output_file = self.compiled_dir / f"{persona.persona_id}.json"

            data = {
                "persona_id": persona.persona_id,
                "character_id": persona.character.character_id,
                "character_name": persona.character.display_name,
                "framework_id": persona.framework.framework_id,
                "framework_name": persona.framework.name,
                "system_prompt": persona.system_prompt,
                "tools_required": persona.tools_required,
                "config": persona.config,
                "compiled_at": str(Path(__file__).stat().st_mtime)
            }

            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved compiled persona to {output_file}")

        except Exception as e:
            logger.warning(f"Could not save compiled persona: {e}")

    def list_available_frameworks(self) -> List[Dict[str, str]]:
        """Get list of available frameworks."""
        frameworks = []

        for file in self.frameworks_dir.glob("*.json"):
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                    frameworks.append({
                        "id": data["framework_id"],
                        "name": data["name"],
                        "purpose": data["purpose"]
                    })
            except Exception as e:
                logger.warning(f"Could not read framework {file}: {e}")

        return frameworks

    def list_available_characters(self) -> List[Dict[str, str]]:
        """Get list of available characters."""
        characters = []

        for file in self.characters_dir.glob("*.json"):
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                    characters.append({
                        "id": data["character_id"],
                        "name": data["display_name"],
                        "from": data["identity"].get("from", "Unknown")
                    })
            except Exception as e:
                logger.warning(f"Could not read character {file}: {e}")

        return characters
