"""Behavior Engine - Central brain for bot autonomy and responsiveness.

Consolidates naturalness, ambient mode, proactive engagement, mood,
environmental awareness, callbacks, and curiosity into a single system.
"""
import logging
import random
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from collections import deque, defaultdict

import discord

from config import Config
from services.ollama import OllamaService
from services.context_manager import ContextManager
from services.lorebook_service import LorebookService

logger = logging.getLogger(__name__)

@dataclass
class BehaviorState:
    """Tracks behavioral state for a specific channel/context."""
    # Activity
    last_message_time: datetime = field(default_factory=datetime.now)
    last_bot_message_time: datetime = field(default_factory=datetime.now)
    message_count: int = 0

    # Context
    recent_topics: deque = field(default_factory=lambda: deque(maxlen=10))
    recent_users: Set[str] = field(default_factory=set)

    # Timers
    last_ambient_trigger: datetime = field(default_factory=datetime.now)
    last_proactive_trigger: datetime = field(default_factory=datetime.now)

    # Memory
    short_term_memories: List[Dict] = field(default_factory=list) # [{topic, timestamp, importance}]

class BehaviorEngine:
    """
    Central decision engine for bot behavior.

    Replaces:
    - NaturalnessEnhancer
    - AmbientMode
    - ProactiveEngagement
    - MoodSystem
    - EnvironmentalAwareness
    - ProactiveCallbacksSystem
    - CuriositySystem
    """

    def __init__(
        self,
        bot,
        ollama: OllamaService,
        context_manager: ContextManager,
        lorebook_service: LorebookService = None
    ):
        self.bot = bot
        self.ollama = ollama
        self.context_manager = context_manager
        self.lorebook_service = lorebook_service

        # State tracking
        self.states: Dict[int, BehaviorState] = defaultdict(BehaviorState)
        self.voice_states: Dict[int, Dict] = {} # guild_id -> voice state info

        # Configuration (derived from Config or defaults)
        self.reaction_chance = 0.15
        self.ambient_interval_min = 600 # 10 mins
        self.proactive_cooldown = 300   # 5 mins

        # Background task
        self._running = False
        self._task = None

        # Persona reference (set by ChatCog)
        self.current_persona = None

    async def start(self):
        """Start the behavior loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._tick_loop())
        logger.info("Behavior Engine started")

    async def stop(self):
        """Stop the behavior loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Behavior Engine stopped")

    def set_persona(self, persona):
        """Update the active persona."""
        self.current_persona = persona

    async def handle_message(self, message: discord.Message) -> Optional[Dict]:
        """
        Process a new message and decide on immediate reactions or replies.

        Returns:
            Dict containing action directives (e.g. {'reaction': '🔥', 'reply': '...'}) or None
        """
        if message.author.bot:
            return None

        state = self.states[message.channel.id]
        state.last_message_time = datetime.now()
        state.message_count += 1
        state.recent_users.add(message.author.display_name)

        # 1. Analyze Content (Topic Detection)
        # Simple keyword extraction for now
        # TODO: Use lightweight local NLP or regex if needed

        # 2. Decision: React?
        reaction = await self._decide_reaction(message)
        if reaction:
            await message.add_reaction(reaction)

        # 3. Decision: Proactive Reply? (Jump in)
        # Only if not mentioned (handled by ChatCog) and not a reply to bot
        if not self.bot.user in message.mentions and not (message.reference and message.reference.resolved and message.reference.resolved.author == self.bot.user):
             engagement = await self._decide_proactive_engagement(message, state)
             if engagement:
                 return {"reply": engagement, "reason": "proactive"}

        return None

    async def _tick_loop(self):
        """Periodic loop to check for ambient opportunities."""
        while self._running:
            try:
                await asyncio.sleep(60) # Check every minute
                for channel_id, state in list(self.states.items()):
                    await self._check_ambient_triggers(channel_id, state)
            except Exception as e:
                logger.error(f"Error in BehaviorEngine tick: {e}")

    async def _check_ambient_triggers(self, channel_id: int, state: BehaviorState):
        """Check if we should say something during a lull."""
        now = datetime.now()
        silence_duration = (now - state.last_message_time).total_seconds()

        # Lull Detection (> 10 mins silence, but < 2 hours)
        if silence_duration > 600 and silence_duration < 7200:
            time_since_last_ambient = (now - state.last_ambient_trigger).total_seconds()

            if time_since_last_ambient > self.ambient_interval_min:
                # 10% chance to speak
                if random.random() < 0.1:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        msg = await self._generate_ambient_thought(channel, state)
                        if msg:
                            await channel.send(msg)
                            state.last_ambient_trigger = now

    async def handle_voice_update(self, member, before, after):
        """Handle voice state changes (Environmental Awareness)."""
        if member.bot: return

        # Detect significant events: Join, Leave, Stream Start
        event_type = None
        if before.channel is None and after.channel is not None:
            event_type = "join"
        elif before.channel is not None and after.channel is None:
            event_type = "leave"
        elif not before.self_stream and after.self_stream:
            event_type = "stream_start"

        if event_type:
            # Chance to comment
            if random.random() < 0.3: # 30% chance
                # Find a text channel to comment in (usually the system channel or general)
                # For now, simplistic selection
                if member.guild.system_channel:
                    msg = await self._generate_environmental_comment(member, event_type)
                    if msg:
                        await member.guild.system_channel.send(msg)

    # --- Generative Methods ---

    async def _decide_reaction(self, message: discord.Message) -> Optional[str]:
        """Decide if and what emoji to react with."""
        if random.random() > self.reaction_chance:
            return None

        # Lightweight check: Basic sentiment/keyword map
        # Or lightweight LLM call if needed
        # For efficiency, let's use a simplified keyword map derived from the old Naturalness

        content = message.content.lower()
        if any(w in content for w in ["lol", "lmao", "haha"]): return "😂"
        if any(w in content for w in ["cool", "wow", "nice"]): return "🔥"
        if "?" in content: return "🤔"

        return None

    async def _decide_proactive_engagement(self, message: discord.Message, state: BehaviorState) -> Optional[str]:
        """Decide whether to jump into a conversation."""
        # 1. Check cooldown
        if (datetime.now() - state.last_proactive_trigger).total_seconds() < self.proactive_cooldown:
            return None

        # 2. Check Interest (LLM Fast Path)
        # We ask the LLM: "Is [Character] interested in this?"
        if not self.current_persona: return None

        prompt = f"""Message: "{message.content}"

As {self.current_persona.character.display_name}, is this a topic you would excitedly jump into?
Reply YES or NO."""

        try:
            res = await self.ollama.generate(prompt, max_tokens=5)
            if "YES" in res.upper():
                # Generate actual reply
                reply_prompt = f"""User said: "{message.content}"

Reply naturally as {self.current_persona.character.display_name}. Keep it short and casual."""
                reply = await self.ollama.generate(reply_prompt, max_tokens=100)
                state.last_proactive_trigger = datetime.now()
                return reply
        except:
            pass

        return None

    async def _generate_ambient_thought(self, channel, state: BehaviorState) -> Optional[str]:
        """Generate a random thought or callback."""
        if not self.current_persona: return None

        # Decide between random thought or callback
        prompt = f"""You are hanging out in #{channel.name}. It's been quiet for a while.

Say something to break the silence. It could be:
1. A random thought based on your personality.
2. A callback to a recent topic (if you remember one).

Keep it conversational and short."""

        return await self.ollama.generate(prompt, max_tokens=100)

    async def _generate_environmental_comment(self, member, event_type) -> Optional[str]:
        """Comment on voice activity."""
        if not self.current_persona: return None

        prompt = f"""{member.display_name} just {event_type}ed the voice channel.

Make a brief, friendly comment about it as {self.current_persona.character.display_name}."""

        return await self.ollama.generate(prompt, max_tokens=50)
