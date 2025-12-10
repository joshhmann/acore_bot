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
    # Visuals
    avatar_url: Optional[str] = None
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
                # Inspect JSON to see if it's V2 or Legacy
                with open(character_file, 'r') as f:
                    data = json.load(f)
                
                # Check for V2 spec signatures
                if "spec" in data and "data" in data:
                    # It's a V2 card in JSON format
                    character = self._parse_v2_data(data, character_id)
                    self.characters[character_id] = character
                    logger.info(f"Loaded V2 character (JSON): {character_id}")
                    return character
                else:
                    logger.error(f"Legacy character format not supported for {character_id}. Please migrate to V2.")
                    return None

        except Exception as e:
            logger.error(f"Error loading character {character_id}: {e}")
            return None



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

            character = self._parse_v2_data(card_data, character_id)

            # Cache it
            self.characters[character_id] = character
            logger.info(f"Loaded V2 character card: {character_id}")
            return character

        except Exception as e:
            logger.error(f"Failed to parse V2 card {filepath}: {e}")
            raise

    def _parse_v2_data(self, card_data: Dict[str, Any], character_id: str) -> Character:
        """Parse V2 character card data into Character object."""
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
            system_prompt_override=data.get('system_prompt', ''),
            avatar_url=data.get('avatar_url')
        )
        return character

    def compile_persona(
        self,
        character_id: str,
        framework_id: str = None,
        force_recompile: bool = False
    ) -> Optional[CompiledPersona]:
        """
        Compile character (+ optional framework) into complete persona.

        Args:
            character_id: Character to use
            framework_id: Framework to apply (optional, uses card's system_prompt if None)
            force_recompile: Recompile even if cached

        Returns:
            CompiledPersona or None if compilation fails
        """
        persona_id = f"{character_id}_{framework_id}" if framework_id else character_id

        # Check cache unless forced
        if not force_recompile and persona_id in self.compiled_personas:
            return self.compiled_personas[persona_id]

        # Load character
        character = self.load_character(character_id)
        if not character:
            logger.error(f"Cannot compile persona: character {character_id} not found")
            return None

        # Load framework (optional)
        framework = None
        if framework_id:
            framework = self.load_framework(framework_id)
            if not framework:
                logger.warning(f"Framework {framework_id} not found, using character card only")

        # Create a minimal framework wrapper if none provided (or if ignoring)
        if not framework:
             framework = Framework(
                framework_id="none",
                name="No Framework",
                purpose="Pure Character Card",
                behavioral_patterns={},
                tool_requirements={},
                decision_making={},
                context_requirements={},
                interaction_style={},
                anti_hallucination={},
                prompt_template=""
            )

        try:
            # Build system prompt
            if framework:
                # Legacy: combine character + framework
                system_prompt = self._build_system_prompt(character, framework)
                tools_required = framework.tool_requirements.get("required", [])
                tools_required.extend(framework.tool_requirements.get("optional", []))
                config = {
                    "character": character.character_id,
                    "framework": framework.framework_id,
                    "behavioral_patterns": framework.behavioral_patterns,
                    "decision_making": framework.decision_making,
                    "interaction_style": framework.interaction_style,
                    "anti_hallucination": framework.anti_hallucination,
                    "context_needs": framework.context_requirements,
                }
            else:
                # V2 Card: use card's system_prompt directly
                if character.system_prompt_override:
                    system_prompt = character.system_prompt_override
                else:
                    # Build from V2 card fields
                    system_prompt = self._build_v2_system_prompt(character)
                
                tools_required = []
                config = {
                    "character": character.character_id,
                    "framework": None,
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

            logger.info(f"Compiled persona: {persona_id} (framework: {framework_id or 'none'})")

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



    def _build_v2_system_prompt(self, character: Character) -> str:
        """Build system prompt from V2 character card fields (SillyTavern style)."""
        prompt = f"""You are {character.display_name}.

=== DESCRIPTION ===
{character.description}

=== PERSONALITY ===
{character.identity.get('personality', '')}

=== SCENARIO ===
{character.scenario}
"""
        # Add example dialogue if provided
        if character.mes_example:
            prompt += f"""
=== EXAMPLE DIALOGUE ===
{character.mes_example}
"""
        
        # Add response_style if in legacy character
        if character.voice_and_tone.get('response_style'):
            prompt += f"""
=== RESPONSE STYLE ===
{character.voice_and_tone['response_style']}
"""
        
        return prompt



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
                    
                    if "spec" in data and "data" in data:
                        # V2 Character
                        v2_data = data["data"]
                        characters.append({
                            "id": file.stem,
                            "name": v2_data.get("name", file.stem),
                            "from": "V2 Card"
                        })
                    else:
                        pass # Skip legacy files
            except Exception as e:
                logger.warning(f"Could not read character {file}: {e}")

        return characters
