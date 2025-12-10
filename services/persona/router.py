"""Persona Router Service - Manages multiple active personas and routes messages to them.

Handles probabilistic selection of which character responds to a message.
"""
import logging
import random
import asyncio
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from datetime import datetime, timedelta

from config import Config
from services.persona.system import PersonaSystem, CompiledPersona

logger = logging.getLogger(__name__)

class PersonaRouter:
    """Routes messages to one of multiple active personas."""

    def __init__(self, profiles_dir: str):
        self.profiles_dir = Path(profiles_dir)
        self.personas: Dict[str, CompiledPersona] = {}
        self.loaded = False
        
        # Track last responder per channel for "sticky" conversations
        # {channel_id: {"persona": CompiledPersona, "time": datetime}}
        self.last_responder: Dict[int, Dict] = {}
        self.sticky_timeout = 300  # 5 minutes - stick to same persona
        
        # Core system for compiling/loading individual personas
        # PersonaSystem expects base_path containing 'characters/' subdir
        # profiles_dir is .../characters, so we pass parent (.../prompts)
        self.persona_system = PersonaSystem(self.profiles_dir.parent)

    async def initialize(self):
        """Load all active personas."""
        if self.loaded:
            return

        logger.info("Initializing Multi-Persona Router...")
        
        active_list = Config.ACTIVE_PERSONAS
        if not active_list:
            logger.warning("No ACTIVE_PERSONAS configured! Falling back to dagoth_ur.json")
            active_list = ["dagoth_ur.json"]

        count = 0
        for filename in active_list:
            try:
                # We reuse PersonaSystem to load each one
                # Note: PersonaSystem is designed for single-use, but we can reuse its static logic
                # or just use it as a loader helper.
                
                # Effectively we are creating a CompiledPersona for each
                # Let's check how PersonaSystem loads - it takes 'framework' and 'character_file'
                
                # We need to construct the full path
                char_path = self.profiles_dir / filename
                if not char_path.exists():
                     logger.warning(f"Character file not found: {char_path}")
                     continue

                # Extract ID (e.g. 'scav.json' -> 'scav')
                char_id = Path(filename).stem

                # Load & Compile (Synchronous)
                persona = self.persona_system.compile_persona(
                    character_id=char_id,
                    framework_id=None # Use embedded/default
                )
                
                if persona:
                    self.personas[filename] = persona
                    logger.info(f"Loaded persona: {persona.character.display_name} ({filename})")
                    count += 1
            except Exception as e:
                logger.error(f"Failed to load persona {filename}: {e}")

        logger.info(f"Persona Router initialized with {count} active characters.")
        self.loaded = True

    def select_persona(self, message_content: str, channel_id: int = None) -> Optional[CompiledPersona]:
        """Select a persona to respond to this message.
        
        Priority:
        1. Explicit name mention in message
        2. Sticky: Same persona that last responded (within timeout)
        3. Random selection (only if no context)
        
        Args:
            message_content: The message text
            channel_id: Channel ID for sticky persona tracking
        """
        if not self.personas:
            return None

        content_lower = message_content.lower()
        
        # Sort by name length desc to match "Dagoth Ur" before "Dagoth"
        sorted_personas = sorted(
            self.personas.values(), 
            key=lambda p: len(p.character.display_name), 
            reverse=True
        )

        # Phase 1: Full Name Match (explicit mention)
        for p in sorted_personas:
            name = p.character.display_name.lower()
            if name in content_lower:
                logger.info(f"Routing to {p.character.display_name} (full name mentioned)")
                return p
        
        # Phase 2: First Name / Nickname Match (for "Dagoth" -> "Dagoth Ur")
        for p in sorted_personas:
            display_name = p.character.display_name.lower()
            if " " in display_name:
                first_name = display_name.split(" ")[0]
                # Ensure first name is not too short to avoid matching common words
                if len(first_name) >= 3 and first_name in content_lower:
                    logger.info(f"Routing to {p.character.display_name} (first name mentioned)")
                    return p

        # Phase 3: STICKY - Use last responder for this channel if recent
        if channel_id and channel_id in self.last_responder:
            last = self.last_responder[channel_id]
            time_since = (datetime.now() - last["time"]).total_seconds()
            
            if time_since < self.sticky_timeout:
                persona = last["persona"]
                logger.info(f"Routing to {persona.character.display_name} (sticky - last responder)")
                return persona

        # Phase 4: Random Selection (no context, first message)
        candidate_key = random.choice(list(self.personas.keys()))
        candidate = self.personas[candidate_key]
        logger.info(f"Routing to {candidate.character.display_name} (random selection)")
        
        return candidate

    def record_response(self, channel_id: int, persona: CompiledPersona):
        """Record that a persona responded in a channel (for sticky tracking)."""
        self.last_responder[channel_id] = {
            "persona": persona,
            "time": datetime.now()
        }

    def get_all_personas(self) -> List[CompiledPersona]:
        return list(self.personas.values())

    def get_persona_by_name(self, name: str) -> Optional[CompiledPersona]:
        """Get persona by display name or filename (fuzzy)."""
        name_lower = name.lower()
        
        # Exact match first
        for key, p in self.personas.items():
            if key == name or p.character.display_name.lower() == name_lower:
                return p
        
        # Partial match (for "Dagoth" -> "Dagoth Ur")
        for key, p in self.personas.items():
            if name_lower in p.character.display_name.lower():
                return p
            if name_lower in key.lower():
                return p
                
        return None
