"""Persona Relationships Service - Tracks affinity and memories between personas."""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import aiofiles
import re

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

        # T15: Conflict System - Define conflict triggers per persona pair
        # Format: {pair_key: [trigger_topics]}
        self.conflict_triggers: Dict[str, List[str]] = {}

        # T15: Active conflicts tracker
        # Format: {pair_key: {topic: str, severity: float, timestamp: datetime, last_mention: datetime}}
        self.active_conflicts: Dict[str, Dict] = {}

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
                # T15: Conflict data
                "conflict_triggers": [],  # Topics that cause tension
                "active_conflict": None,  # Current conflict state
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

    def get_banter_chance(
        self, persona_a: str, persona_b: str, base_chance: float = 0.05
    ) -> float:
        """Calculate banter probability based on affinity and conflicts.

        Formula: (base_chance + affinity_bonus) * conflict_multiplier
        Range: 5% (strangers) to 20% (besties), reduced if in conflict

        Args:
            persona_a: Persona considering responding
            persona_b: Persona who sent the message
            base_chance: Base probability (default 5%)

        Returns:
            Probability (0.0 to 1.0)
        """
        affinity = self.get_affinity(persona_a, persona_b)
        affinity_bonus = (affinity / 100) * 0.15  # Up to +15%
        base_banter = min(base_chance + affinity_bonus, 0.25)  # Cap at 25%

        # T15: Apply conflict modifier
        conflict_mod = self.get_conflict_modifier(persona_a, persona_b)
        final_chance = base_banter * conflict_mod["banter_multiplier"]

        if conflict_mod["in_conflict"]:
            logger.debug(
                f"Banter chance reduced by conflict: {base_banter:.2%} → {final_chance:.2%} "
                f"(severity: {conflict_mod['severity']:.2f})"
            )

        return final_chance

    async def record_interaction(
        self,
        speaker: str,
        responder: str,
        affinity_change: int = 2,
        memory: Optional[str] = None,
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
            rel["shared_memories"].append(
                {
                    "memory": memory,
                    "timestamp": datetime.utcnow().isoformat(),
                    "context": f"{speaker} → {responder}",
                }
            )
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
        rel["affinity"]
        stage = rel["stage"]
        count = rel["interaction_count"]

        if count == 0:
            return f"You have never interacted with {persona_b} before."

        context = (
            f"Your relationship with {persona_b}: {stage} (talked {count} times). "
        )

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

    def get_friends_of(
        self, persona: str, min_affinity: int = 40
    ) -> List[Tuple[str, int]]:
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
                other = [
                    p
                    for p in rel["personas"]
                    if p.lower().replace(" ", "_") != persona_lower
                ]
                if other:
                    friends.append((other[0], rel["affinity"]))

        return sorted(friends, key=lambda x: x[1], reverse=True)

    # ===== T15: CONFLICT SYSTEM =====

    def set_conflict_triggers(
        self, persona_a: str, persona_b: str, triggers: List[str]
    ):
        """Set conflict trigger topics for a persona pair.

        Args:
            persona_a: First persona
            persona_b: Second persona
            triggers: List of topics that cause tension (e.g., ["politics", "religion"])
        """
        rel = self.get_relationship(persona_a, persona_b)
        rel["conflict_triggers"] = triggers
        self._dirty = True
        logger.debug(f"Set conflict triggers for {persona_a}-{persona_b}: {triggers}")

    def detect_conflict_trigger(
        self,
        persona_a: str,
        persona_b: str,
        message: str,
        topics: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Detect if a message contains a conflict trigger topic.

        Performance target: <5ms

        Args:
            persona_a: First persona
            persona_b: Second persona
            message: Message content to scan
            topics: Optional pre-detected topics from behavior engine

        Returns:
            Triggered topic or None
        """
        rel = self.get_relationship(persona_a, persona_b)
        triggers = rel.get("conflict_triggers", [])

        if not triggers:
            return None

        message_lower = message.lower()

        # Check pre-detected topics first (fastest)
        if topics:
            for topic in topics:
                for trigger in triggers:
                    if (
                        trigger.lower() in topic.lower()
                        or topic.lower() in trigger.lower()
                    ):
                        logger.debug(f"Conflict trigger detected via topic: {trigger}")
                        return trigger

        # Fallback: keyword matching in message content
        for trigger in triggers:
            # Simple keyword matching with word boundaries
            pattern = r"\b" + re.escape(trigger.lower()) + r"\b"
            if re.search(pattern, message_lower):
                logger.debug(f"Conflict trigger detected via message: {trigger}")
                return trigger

        return None

    def escalate_conflict(
        self, persona_a: str, persona_b: str, topic: str, escalation_amount: float = 0.2
    ):
        """Escalate conflict severity when trigger topic is mentioned.

        Args:
            persona_a: First persona
            persona_b: Second persona
            topic: Conflict topic
            escalation_amount: How much to increase severity (default +0.2)
        """
        rel = self.get_relationship(persona_a, persona_b)
        now = datetime.utcnow()

        conflict = rel.get("active_conflict")

        if conflict and conflict.get("topic") == topic:
            # Escalate existing conflict
            old_severity = conflict["severity"]
            conflict["severity"] = min(1.0, old_severity + escalation_amount)
            conflict["last_mention"] = now.isoformat()
            logger.info(
                f"Conflict escalated: {persona_a}-{persona_b} on '{topic}' "
                f"({old_severity:.2f} → {conflict['severity']:.2f})"
            )
        else:
            # Start new conflict
            rel["active_conflict"] = {
                "topic": topic,
                "severity": min(1.0, escalation_amount),
                "timestamp": now.isoformat(),
                "last_mention": now.isoformat(),
            }
            logger.info(
                f"Conflict started: {persona_a}-{persona_b} on '{topic}' "
                f"(severity: {escalation_amount:.2f})"
            )

        self._dirty = True

    def decay_conflicts(self, decay_rate: float = 0.1):
        """Decay all active conflicts over time.

        Called periodically (e.g., hourly) to reduce conflict severity.
        Conflicts resolve completely when severity reaches 0.0.

        Args:
            decay_rate: Amount to reduce severity per hour (default -0.1)
        """
        now = datetime.utcnow()
        resolved_conflicts = []

        for key, rel in self.relationships.items():
            conflict = rel.get("active_conflict")
            if not conflict:
                continue

            last_mention = datetime.fromisoformat(conflict["last_mention"])
            hours_since_mention = (now - last_mention).total_seconds() / 3600

            if hours_since_mention >= 1.0:
                # Decay severity
                decay_amount = decay_rate * hours_since_mention
                conflict["severity"] = max(0.0, conflict["severity"] - decay_amount)

                if conflict["severity"] <= 0.0:
                    # Conflict resolved
                    rel["active_conflict"] = None
                    resolved_conflicts.append((key, conflict["topic"]))
                    logger.info(f"Conflict resolved: {key} on '{conflict['topic']}'")
                else:
                    logger.debug(
                        f"Conflict decayed: {key} on '{conflict['topic']}' "
                        f"(severity: {conflict['severity']:.2f})"
                    )

                self._dirty = True

        return resolved_conflicts

    def get_conflict_state(self, persona_a: str, persona_b: str) -> Optional[Dict]:
        """Get current conflict state for a persona pair.

        Args:
            persona_a: First persona
            persona_b: Second persona

        Returns:
            Conflict dict or None
        """
        rel = self.get_relationship(persona_a, persona_b)
        return rel.get("active_conflict")

    def get_conflict_modifier(self, persona_a: str, persona_b: str) -> Dict[str, Any]:
        """Get conflict-based modifiers for persona interactions.

        Returns banter chance reduction and argumentative prompt text.

        Args:
            persona_a: Current persona (who might respond)
            persona_b: Other persona (who sent message)

        Returns:
            Dict with banter_multiplier and prompt_modifier
        """
        conflict = self.get_conflict_state(persona_a, persona_b)

        if not conflict or conflict["severity"] <= 0.0:
            return {
                "banter_multiplier": 1.0,
                "prompt_modifier": "",
                "in_conflict": False,
            }

        severity = conflict["severity"]
        topic = conflict["topic"]

        # Reduce banter chance based on severity
        # Formula: base_chance * (1.0 - severity * 0.8)
        # At max severity (1.0): 20% of normal banter
        banter_multiplier = 1.0 - (severity * 0.8)

        # Generate argumentative prompt modifier
        intensity_desc = "slightly tense"
        if severity > 0.7:
            intensity_desc = "in strong disagreement"
        elif severity > 0.4:
            intensity_desc = "in disagreement"

        prompt_modifier = (
            f"\n[RELATIONSHIP CONTEXT]\n"
            f"You are currently {intensity_desc} with {persona_b} about {topic}. "
            f"Your responses may be more argumentative, defensive, or critical when this topic arises. "
            f"However, you can still be civil in other conversations."
        )

        return {
            "banter_multiplier": banter_multiplier,
            "prompt_modifier": prompt_modifier,
            "in_conflict": True,
            "severity": severity,
            "topic": topic,
        }
