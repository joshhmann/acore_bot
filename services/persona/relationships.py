"""Persona Relationships Service - Tracks affinity and memories between personas."""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import aiofiles

logger = logging.getLogger(__name__)


class PersonaRelationships:
    """Manages relationships between personas (affinity, memories, stages)."""

    RELATIONSHIP_STAGES = {
        0: "strangers",
        20: "acquaintances",
        40: "frenemies",
        60: "friends",
        80: "besties",
    }

    def __init__(self, data_path: Path = Path("./data/persona_relationships.json")):
        """Initialize the relationships service.
        
        Args:
            data_path: Path to the relationships JSON file
        """
        self.data_path = Path(data_path)
        self.relationships: Dict[str, dict] = {}
        self._dirty = False
        
    async def initialize(self):
        """Load relationships from disk."""
        if self.data_path.exists():
            try:
                async with aiofiles.open(self.data_path, "r") as f:
                    content = await f.read()
                    self.relationships = json.loads(content)
                logger.info(f"Loaded {len(self.relationships)} persona relationships")
            except Exception as e:
                logger.error(f"Failed to load persona relationships: {e}")
                self.relationships = {}
        else:
            # Ensure parent directory exists
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
            self.relationships = {}
            logger.info("Initialized empty persona relationships")

    def _get_pair_key(self, persona_a: str, persona_b: str) -> str:
        """Get a consistent key for a pair of personas (alphabetically sorted).
        
        Args:
            persona_a: First persona ID or display name
            persona_b: Second persona ID or display name
            
        Returns:
            Sorted pair key like "dagoth_ur_toad"
        """
        # Normalize to lowercase and sort alphabetically
        a = persona_a.lower().replace(" ", "_")
        b = persona_b.lower().replace(" ", "_")
        return f"{min(a, b)}_{max(a, b)}"

    def _get_stage(self, affinity: int) -> str:
        """Get relationship stage based on affinity score.
        
        Args:
            affinity: Affinity score (0-100)
            
        Returns:
            Relationship stage string
        """
        stage = "strangers"
        for threshold, stage_name in sorted(self.RELATIONSHIP_STAGES.items()):
            if affinity >= threshold:
                stage = stage_name
        return stage

    def get_relationship(self, persona_a: str, persona_b: str) -> dict:
        """Get the relationship between two personas.
        
        Args:
            persona_a: First persona ID or display name
            persona_b: Second persona ID or display name
            
        Returns:
            Relationship dict with affinity, stage, memories, etc.
        """
        key = self._get_pair_key(persona_a, persona_b)
        
        if key not in self.relationships:
            # Initialize new relationship
            self.relationships[key] = {
                "personas": sorted([persona_a, persona_b]),
                "affinity": 0,
                "stage": "strangers",
                "interaction_count": 0,
                "shared_memories": [],
                "last_interaction": None,
                "created_at": datetime.utcnow().isoformat(),
            }
            self._dirty = True
            
        return self.relationships[key]

    def get_affinity(self, persona_a: str, persona_b: str) -> int:
        """Get affinity score between two personas.
        
        Args:
            persona_a: First persona
            persona_b: Second persona
            
        Returns:
            Affinity score (0-100)
        """
        rel = self.get_relationship(persona_a, persona_b)
        return rel.get("affinity", 0)

    def get_banter_chance(self, persona_a: str, persona_b: str, base_chance: float = 0.05) -> float:
        """Calculate banter probability based on affinity.
        
        Formula: base_chance + (affinity / 100) * 0.15
        Range: 5% (strangers) to 20% (besties)
        
        Args:
            persona_a: Persona considering responding
            persona_b: Persona who sent the message
            base_chance: Base probability (default 5%)
            
        Returns:
            Probability (0.0 to 1.0)
        """
        affinity = self.get_affinity(persona_a, persona_b)
        affinity_bonus = (affinity / 100) * 0.15  # Up to +15%
        return min(base_chance + affinity_bonus, 0.25)  # Cap at 25%

    async def record_interaction(
        self, 
        speaker: str, 
        responder: str, 
        affinity_change: int = 2,
        memory: Optional[str] = None
    ):
        """Record an interaction between two personas.
        
        Args:
            speaker: Persona who spoke first
            responder: Persona who responded
            affinity_change: How much to change affinity (default +2)
            memory: Optional memorable moment to store
        """
        rel = self.get_relationship(speaker, responder)
        
        # Update affinity (clamped to 0-100)
        rel["affinity"] = max(0, min(100, rel["affinity"] + affinity_change))
        rel["stage"] = self._get_stage(rel["affinity"])
        rel["interaction_count"] += 1
        rel["last_interaction"] = datetime.utcnow().isoformat()
        
        # Add memory if provided (keep last 10)
        if memory:
            rel["shared_memories"].append({
                "memory": memory,
                "timestamp": datetime.utcnow().isoformat(),
                "context": f"{speaker} → {responder}"
            })
            # Keep only last 10 memories
            if len(rel["shared_memories"]) > 10:
                rel["shared_memories"] = rel["shared_memories"][-10:]
        
        self._dirty = True
        logger.debug(
            f"Persona interaction: {speaker} → {responder} | "
            f"Affinity: {rel['affinity']} ({rel['stage']})"
        )

    def get_relationship_context(self, persona_a: str, persona_b: str) -> str:
        """Get context string about the relationship for LLM prompts.
        
        Args:
            persona_a: Current persona
            persona_b: Other persona
            
        Returns:
            Context string describing the relationship
        """
        rel = self.get_relationship(persona_a, persona_b)
        affinity = rel["affinity"]
        stage = rel["stage"]
        count = rel["interaction_count"]
        
        if count == 0:
            return f"You have never interacted with {persona_b} before."
        
        context = f"Your relationship with {persona_b}: {stage} (talked {count} times). "
        
        # Add stage-specific flavor
        stage_flavor = {
            "strangers": "You don't know them well yet.",
            "acquaintances": "You've chatted a few times.",
            "frenemies": "You have a love-hate dynamic with them.",
            "friends": "You enjoy their company.",
            "besties": "You're great friends! Inside jokes are welcome.",
        }
        context += stage_flavor.get(stage, "")
        
        # Add recent shared memories
        if rel["shared_memories"]:
            recent = rel["shared_memories"][-2:]
            memories_str = "; ".join([m["memory"] for m in recent])
            context += f" Recent memories: {memories_str}"
        
        return context

    async def save(self):
        """Save relationships to disk."""
        if not self._dirty:
            return
            
        try:
            async with aiofiles.open(self.data_path, "w") as f:
                await f.write(json.dumps(self.relationships, indent=2))
            self._dirty = False
            logger.debug(f"Saved {len(self.relationships)} persona relationships")
        except Exception as e:
            logger.error(f"Failed to save persona relationships: {e}")

    def get_all_relationships(self) -> Dict[str, dict]:
        """Get all relationships for debugging/display.
        
        Returns:
            All relationship data
        """
        return self.relationships.copy()

    def get_friends_of(self, persona: str, min_affinity: int = 40) -> List[Tuple[str, int]]:
        """Get list of personas this persona is friends with.
        
        Args:
            persona: Persona to check
            min_affinity: Minimum affinity to be considered a friend
            
        Returns:
            List of (persona_name, affinity) tuples
        """
        friends = []
        persona_lower = persona.lower().replace(" ", "_")
        
        for key, rel in self.relationships.items():
            if persona_lower in key and rel["affinity"] >= min_affinity:
                # Find the other persona in the relationship
                other = [p for p in rel["personas"] if p.lower().replace(" ", "_") != persona_lower]
                if other:
                    friends.append((other[0], rel["affinity"]))
        
        return sorted(friends, key=lambda x: x[1], reverse=True)
