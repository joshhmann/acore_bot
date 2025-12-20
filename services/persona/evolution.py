"""Character Evolution System - Track interaction milestones and unlock behaviors.

T13: Character Evolution System
- Tracks interaction milestones (total messages, topics, relationship depth)
- Unlocks new behaviors/quirks at thresholds
- Gradual evolution based on accumulated interactions
- Storage: data/persona_evolution/{persona_id}.json
"""

import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class EvolutionStage:
    """Defines an evolution stage with milestone and unlocks."""

    milestone: int  # Number of messages to reach this stage
    unlocks: Dict[str, Any]  # What gets unlocked: tone, quirks, knowledge_expansion
    achieved_at: Optional[datetime] = None  # When this stage was reached


@dataclass
class EvolutionState:
    """Current evolution state for a persona."""

    persona_id: str
    total_messages: int = 0
    topics_discussed: Set[str] = field(default_factory=set)
    first_interaction: Optional[datetime] = None
    last_interaction: Optional[datetime] = None

    # Relationship depth metrics
    unique_users: Set[str] = field(default_factory=set)
    conversation_depth: int = 0  # Total turns in conversations
    meaningful_interactions: int = 0  # Interactions longer than 3 turns

    # Achieved stages
    achieved_stages: List[int] = field(default_factory=list)

    # Active evolution effects
    active_tone_shifts: List[str] = field(default_factory=list)
    active_quirks: List[str] = field(default_factory=list)
    active_knowledge: List[str] = field(default_factory=list)


class PersonaEvolutionTracker:
    """
    Tracks persona evolution through interactions and manages milestone unlocks.

    Performance target: <10ms per message tracking
    Storage: JSON files in data/persona_evolution/
    """

    # Default evolution stages (can be overridden by character config)
    DEFAULT_STAGES = [
        {
            "milestone": 50,
            "unlocks": {
                "tone": "slightly_familiar",
                "quirks": ["remembers_first_topics"],
                "knowledge_expansion": [],
            },
        },
        {
            "milestone": 100,
            "unlocks": {
                "tone": "more_casual",
                "quirks": ["uses_callback_references", "remembers_user_preferences"],
                "knowledge_expansion": ["expands_on_favorite_topics"],
            },
        },
        {
            "milestone": 500,
            "unlocks": {
                "tone": "comfortable_banter",
                "quirks": ["inside_jokes", "references_past_convos", "playful_teasing"],
                "knowledge_expansion": [
                    "deep_topic_knowledge",
                    "connects_related_concepts",
                ],
            },
        },
        {
            "milestone": 1000,
            "unlocks": {
                "tone": "fully_comfortable",
                "quirks": ["uses_slang", "personal_nicknames", "anticipates_reactions"],
                "knowledge_expansion": ["expert_level_topics", "creative_connections"],
            },
        },
        {
            "milestone": 5000,
            "unlocks": {
                "tone": "deep_familiarity",
                "quirks": [
                    "legendary_callbacks",
                    "knows_user_patterns",
                    "meta_awareness",
                ],
                "knowledge_expansion": ["mastery_of_topics", "philosophical_insights"],
            },
        },
    ]

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize evolution tracker.

        Args:
            base_path: Base directory for evolution data (defaults to ./data/persona_evolution)
        """
        self.base_path = base_path or Path("./data/persona_evolution")
        self.base_path.mkdir(parents=True, exist_ok=True)

        # In-memory cache
        self.states: Dict[str, EvolutionState] = {}
        self.stages_config: Dict[str, List[EvolutionStage]] = {}

        # Lock for thread-safe file operations
        self._file_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        logger.info(f"PersonaEvolutionTracker initialized (storage: {self.base_path})")

    async def load_state(self, persona_id: str) -> EvolutionState:
        """
        Load evolution state for a persona from disk.

        Args:
            persona_id: Persona identifier

        Returns:
            EvolutionState (existing or new)
        """
        # Check cache first
        if persona_id in self.states:
            return self.states[persona_id]

        state_file = self.base_path / f"{persona_id}.json"

        # Load from disk if exists
        if state_file.exists():
            try:
                async with self._file_locks[persona_id]:
                    with open(state_file, "r") as f:
                        data = json.load(f)

                    # Parse data into EvolutionState
                    state = EvolutionState(
                        persona_id=persona_id,
                        total_messages=data.get("total_messages", 0),
                        topics_discussed=set(data.get("topics_discussed", [])),
                        first_interaction=datetime.fromisoformat(
                            data["first_interaction"]
                        )
                        if data.get("first_interaction")
                        else None,
                        last_interaction=datetime.fromisoformat(
                            data["last_interaction"]
                        )
                        if data.get("last_interaction")
                        else None,
                        unique_users=set(data.get("unique_users", [])),
                        conversation_depth=data.get("conversation_depth", 0),
                        meaningful_interactions=data.get("meaningful_interactions", 0),
                        achieved_stages=data.get("achieved_stages", []),
                        active_tone_shifts=data.get("active_tone_shifts", []),
                        active_quirks=data.get("active_quirks", []),
                        active_knowledge=data.get("active_knowledge", []),
                    )

                    self.states[persona_id] = state
                    logger.debug(
                        f"Loaded evolution state for {persona_id}: {state.total_messages} messages"
                    )
                    return state

            except Exception as e:
                logger.error(f"Failed to load evolution state for {persona_id}: {e}")

        # Create new state
        state = EvolutionState(persona_id=persona_id)
        self.states[persona_id] = state
        logger.info(f"Created new evolution state for {persona_id}")
        return state

    async def save_state(self, persona_id: str):
        """
        Save evolution state to disk.

        Args:
            persona_id: Persona identifier
        """
        if persona_id not in self.states:
            return

        state = self.states[persona_id]
        state_file = self.base_path / f"{persona_id}.json"

        try:
            async with self._file_locks[persona_id]:
                data = {
                    "persona_id": state.persona_id,
                    "total_messages": state.total_messages,
                    "topics_discussed": list(state.topics_discussed),
                    "first_interaction": state.first_interaction.isoformat()
                    if state.first_interaction
                    else None,
                    "last_interaction": state.last_interaction.isoformat()
                    if state.last_interaction
                    else None,
                    "unique_users": list(state.unique_users),
                    "conversation_depth": state.conversation_depth,
                    "meaningful_interactions": state.meaningful_interactions,
                    "achieved_stages": state.achieved_stages,
                    "active_tone_shifts": state.active_tone_shifts,
                    "active_quirks": state.active_quirks,
                    "active_knowledge": state.active_knowledge,
                    "last_updated": datetime.now().isoformat(),
                }

                # Write atomically (write to temp, then rename)
                temp_file = state_file.with_suffix(".tmp")
                with open(temp_file, "w") as f:
                    json.dump(data, f, indent=2)
                temp_file.replace(state_file)

        except Exception as e:
            logger.error(f"Failed to save evolution state for {persona_id}: {e}")

    def load_evolution_stages(
        self, persona_id: str, stages_config: Optional[List[Dict]] = None
    ) -> List[EvolutionStage]:
        """
        Load evolution stages from character config or use defaults.

        Args:
            persona_id: Persona identifier
            stages_config: Optional stages configuration from character

        Returns:
            List of EvolutionStage objects
        """
        if persona_id in self.stages_config:
            return self.stages_config[persona_id]

        # Use provided config or defaults
        config = stages_config or self.DEFAULT_STAGES

        stages = []
        for stage_data in config:
            stage = EvolutionStage(
                milestone=stage_data["milestone"], unlocks=stage_data.get("unlocks", {})
            )
            stages.append(stage)

        # Sort by milestone
        stages.sort(key=lambda s: s.milestone)

        self.stages_config[persona_id] = stages
        logger.debug(f"Loaded {len(stages)} evolution stages for {persona_id}")
        return stages

    async def track_message(
        self,
        persona_id: str,
        user_id: str,
        topics: Optional[List[str]] = None,
        conversation_turn: int = 1,
    ) -> Optional[Dict[str, Any]]:
        """
        Track a message interaction and check for milestone achievements.

        Performance target: <10ms

        Args:
            persona_id: Persona identifier
            user_id: User who interacted
            topics: Optional list of topics discussed
            conversation_turn: Current turn number in conversation

        Returns:
            Evolution event dict if milestone achieved, None otherwise
        """
        now = datetime.now()

        # Load state
        state = await self.load_state(persona_id)

        # Update metrics
        state.total_messages += 1
        state.unique_users.add(user_id)
        state.conversation_depth += 1
        state.last_interaction = now

        if state.first_interaction is None:
            state.first_interaction = now

        # Track topics
        if topics:
            state.topics_discussed.update(topics)

        # Track meaningful interactions (3+ turns)
        if conversation_turn >= 3:
            state.meaningful_interactions += 1

        # Check for milestone achievements
        stages = self.load_evolution_stages(persona_id)
        evolution_event = None

        for stage in stages:
            if (
                stage.milestone <= state.total_messages
                and stage.milestone not in state.achieved_stages
            ):
                # Milestone achieved!
                state.achieved_stages.append(stage.milestone)
                stage.achieved_at = now

                # Apply unlocks
                if "tone" in stage.unlocks:
                    tone_shift = stage.unlocks["tone"]
                    if tone_shift not in state.active_tone_shifts:
                        state.active_tone_shifts.append(tone_shift)

                if "quirks" in stage.unlocks:
                    for quirk in stage.unlocks["quirks"]:
                        if quirk not in state.active_quirks:
                            state.active_quirks.append(quirk)

                if "knowledge_expansion" in stage.unlocks:
                    for knowledge in stage.unlocks["knowledge_expansion"]:
                        if knowledge not in state.active_knowledge:
                            state.active_knowledge.append(knowledge)

                evolution_event = {
                    "type": "milestone_achieved",
                    "milestone": stage.milestone,
                    "unlocks": stage.unlocks,
                    "timestamp": now.isoformat(),
                    "total_messages": state.total_messages,
                    "total_topics": len(state.topics_discussed),
                    "unique_users": len(state.unique_users),
                }

                logger.info(
                    f"🎉 Evolution milestone achieved for {persona_id}: "
                    f"{stage.milestone} messages (unlocks: {stage.unlocks})"
                )

        # Save state asynchronously (don't block)
        asyncio.create_task(self.save_state(persona_id))

        return evolution_event

    def get_evolution_effects(self, persona_id: str) -> Dict[str, Any]:
        """
        Get current evolution effects for a persona.

        Returns a dict with active tone shifts, quirks, and knowledge expansions.
        This is used to modify behavior and prompts.

        Args:
            persona_id: Persona identifier

        Returns:
            Dict with evolution effects
        """
        if persona_id not in self.states:
            return {
                "tone_shifts": [],
                "quirks": [],
                "knowledge_expansion": [],
                "total_messages": 0,
                "evolution_level": "new",
            }

        state = self.states[persona_id]

        # Determine evolution level
        evolution_level = "new"
        if state.total_messages >= 5000:
            evolution_level = "legendary"
        elif state.total_messages >= 1000:
            evolution_level = "veteran"
        elif state.total_messages >= 500:
            evolution_level = "experienced"
        elif state.total_messages >= 100:
            evolution_level = "familiar"
        elif state.total_messages >= 50:
            evolution_level = "acquainted"

        return {
            "tone_shifts": state.active_tone_shifts,
            "quirks": state.active_quirks,
            "knowledge_expansion": state.active_knowledge,
            "total_messages": state.total_messages,
            "unique_users": len(state.unique_users),
            "topics_count": len(state.topics_discussed),
            "evolution_level": evolution_level,
            "achieved_stages": state.achieved_stages,
        }

    def get_evolution_prompt_modifier(self, persona_id: str) -> str:
        """
        Generate a prompt modifier based on current evolution state.

        This text is appended to the system prompt to reflect character growth.

        Args:
            persona_id: Persona identifier

        Returns:
            Prompt modifier string
        """
        effects = self.get_evolution_effects(persona_id)

        if effects["evolution_level"] == "new":
            return ""

        # Build prompt modifier
        modifier_parts = []

        # Add evolution context
        modifier_parts.append(
            f"\n=== CHARACTER EVOLUTION ===\n"
            f"You have interacted with this community for {effects['total_messages']} messages "
            f"across {effects['unique_users']} users, discussing {effects['topics_count']} topics. "
            f"Evolution Level: {effects['evolution_level'].upper()}\n"
        )

        # Add tone shifts
        if effects["tone_shifts"]:
            tone_desc = self._describe_tone_shift(effects["tone_shifts"][-1])
            modifier_parts.append(f"Tone: {tone_desc}\n")

        # Add quirks
        if effects["quirks"]:
            quirks_desc = self._describe_quirks(effects["quirks"])
            modifier_parts.append(f"Behavioral Evolution: {quirks_desc}\n")

        # Add knowledge expansion
        if effects["knowledge_expansion"]:
            knowledge_desc = self._describe_knowledge(effects["knowledge_expansion"])
            modifier_parts.append(f"Knowledge Growth: {knowledge_desc}\n")

        return "".join(modifier_parts)

    def _describe_tone_shift(self, tone: str) -> str:
        """Convert tone identifier to natural language description."""
        tone_descriptions = {
            "slightly_familiar": "You're becoming slightly more familiar with the community, showing subtle warmth.",
            "more_casual": "You're more casual and comfortable now, engaging naturally.",
            "comfortable_banter": "You're fully comfortable with banter and playful exchanges.",
            "fully_comfortable": "You're deeply comfortable, using inside jokes and personal references.",
            "deep_familiarity": "You have a deep bond with this community, anticipating reactions and showing genuine affection.",
        }
        return tone_descriptions.get(tone, tone)

    def _describe_quirks(self, quirks: List[str]) -> str:
        """Convert quirk identifiers to natural language description."""
        quirk_descriptions = {
            "remembers_first_topics": "You remember the early topics you discussed.",
            "uses_callback_references": "You reference past conversations naturally.",
            "remembers_user_preferences": "You recall user preferences and interests.",
            "inside_jokes": "You have inside jokes with the community.",
            "references_past_convos": "You bring up past conversations organically.",
            "playful_teasing": "You engage in playful teasing with familiar users.",
            "uses_slang": "You've picked up community slang and expressions.",
            "personal_nicknames": "You use personal nicknames for regulars.",
            "anticipates_reactions": "You anticipate how users will react to topics.",
            "legendary_callbacks": "You make legendary callbacks to iconic moments.",
            "knows_user_patterns": "You recognize user behavior patterns.",
            "meta_awareness": "You show meta-awareness of your relationship with the community.",
        }

        active_descriptions = [quirk_descriptions.get(q, q) for q in quirks]
        return " ".join(active_descriptions)

    def _describe_knowledge(self, knowledge: List[str]) -> str:
        """Convert knowledge expansion identifiers to natural language description."""
        knowledge_descriptions = {
            "expands_on_favorite_topics": "You can expand deeply on favorite topics.",
            "deep_topic_knowledge": "You have deep knowledge of discussed topics.",
            "connects_related_concepts": "You connect related concepts across conversations.",
            "expert_level_topics": "You demonstrate expert-level understanding.",
            "creative_connections": "You make creative connections between ideas.",
            "mastery_of_topics": "You show mastery of community topics.",
            "philosophical_insights": "You offer philosophical insights on familiar themes.",
        }

        active_descriptions = [knowledge_descriptions.get(k, k) for k in knowledge]
        return " ".join(active_descriptions)

    async def get_stats(self, persona_id: str) -> Dict[str, Any]:
        """
        Get comprehensive evolution statistics for a persona.

        Args:
            persona_id: Persona identifier

        Returns:
            Dict with all evolution stats
        """
        state = await self.load_state(persona_id)
        effects = self.get_evolution_effects(persona_id)

        # Calculate progress to next milestone
        stages = self.load_evolution_stages(persona_id)
        next_milestone = None
        progress_pct = 100.0

        for stage in stages:
            if stage.milestone > state.total_messages:
                next_milestone = stage.milestone
                progress_pct = (state.total_messages / next_milestone) * 100
                break

        return {
            "persona_id": persona_id,
            "total_messages": state.total_messages,
            "unique_users": len(state.unique_users),
            "topics_discussed": len(state.topics_discussed),
            "conversation_depth": state.conversation_depth,
            "meaningful_interactions": state.meaningful_interactions,
            "evolution_level": effects["evolution_level"],
            "achieved_stages": state.achieved_stages,
            "next_milestone": next_milestone,
            "progress_to_next": f"{progress_pct:.1f}%",
            "active_effects": {
                "tone_shifts": effects["tone_shifts"],
                "quirks": effects["quirks"],
                "knowledge_expansion": effects["knowledge_expansion"],
            },
            "first_interaction": state.first_interaction.isoformat()
            if state.first_interaction
            else None,
            "last_interaction": state.last_interaction.isoformat()
            if state.last_interaction
            else None,
        }
