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
from services.llm.ollama import OllamaService
from services.core.context import ContextManager
from services.persona.lorebook import LorebookService

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
        lorebook_service: LorebookService = None,
        thinking_service = None
    ):
        self.bot = bot
        self.ollama = ollama
        self.context_manager = context_manager
        self.lorebook_service = lorebook_service
        self.thinking_service = thinking_service  # Cheap/fast LLM for decisions

        # State tracking
        self.states: Dict[int, BehaviorState] = defaultdict(BehaviorState)
        self.voice_states: Dict[int, Dict] = {} # guild_id -> voice state info

        # Configuration (from Config)
        from config import Config
        self.reaction_chance = 0.15
        self.ambient_interval_min = Config.AMBIENT_MIN_INTERVAL  # Default 600s, should be higher
        self.ambient_chance = Config.AMBIENT_CHANCE  # Default 0.3, reduce to prevent spam
        self.proactive_enabled = Config.PROACTIVE_ENGAGEMENT_ENABLED
        self.proactive_cooldown = Config.PROACTIVE_COOLDOWN  # Seconds between proactive engagements

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
        reaction_emoji = await self._decide_reaction(message)
        
        # 3. Decision: Proactive Reply? (Jump in)
        # Only if not mentioned (handled by ChatCog) and not a reply to bot
        engagement = None
        if not self.bot.user in message.mentions and not (message.reference and message.reference.resolved and message.reference.resolved.author == self.bot.user):
             engagement = await self._decide_proactive_engagement(message, state)

        if reaction_emoji or engagement:
            return {
                "should_respond": bool(engagement),
                "reaction": reaction_emoji,
                "reply": engagement,
                "reason": "proactive" if engagement else "reaction",
                "suggested_style": None
            }

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
        # Skip if proactive engagement is disabled
        if not self.proactive_enabled:
            return
            
        now = datetime.now()
        silence_duration = (now - state.last_message_time).total_seconds()

        # Lull Detection: Only trigger after LONG silence (1+ hours, but < 8 hours)
        # Much more conservative than before to prevent spam
        if silence_duration > 3600 and silence_duration < 28800:  # 1-8 hours
            time_since_last_ambient = (now - state.last_ambient_trigger).total_seconds()

            # Only allow ambient message every 6+ hours minimum
            if time_since_last_ambient > max(self.ambient_interval_min, 21600):  # At least 6 hours
                # 1/6 chance to speak (as requested by user)
                if random.random() < (1/6):  # ~16.7%
                    channel = self.bot.get_channel(channel_id)
                    if channel and isinstance(channel, discord.TextChannel):
                        # AI-FIRST SPAM CHECK: Let thinking model decide if speaking would be annoying
                        try:
                            recent_msgs = [msg async for msg in channel.history(limit=6)]
                            if recent_msgs:
                                # Build context for LLM to evaluate
                                history_summary = []
                                for msg in reversed(recent_msgs):
                                    author_type = "BOT" if (msg.author.bot or msg.webhook_id) else "HUMAN"
                                    history_summary.append(f"[{author_type}] {msg.author.display_name}: {msg.content[:100]}")
                                
                                history_text = "\n".join(history_summary)
                                
                                decision_prompt = f"""You are evaluating whether to send an ambient/proactive message in a Discord channel.

Here are the last few messages in the channel:
{history_text}

Question: Should you (the bot) send a casual message to spark conversation, or would that be annoying/spammy?

Consider:
- If the last several messages are ALL from bots with no human response, you're probably being ignored
- If a human recently spoke, it might be okay to engage
- If you already sent multiple messages with no response, STOP

Respond with ONLY one word: YES or NO"""

                                # Use thinking service if available, else fall back to main LLM
                                if self.thinking_service:
                                    should_speak = await self.thinking_service.decide(decision_prompt, default=False)
                                else:
                                    decision = await self.ollama.generate(decision_prompt, max_tokens=10)
                                    should_speak = "YES" in decision.strip().upper()
                                
                                if not should_speak:
                                    logger.info(f"AI decided NOT to send ambient message in {channel.name} (spam prevention)")
                                    return
                                    
                        except Exception as e:
                            logger.warning(f"AI spam check failed, using fallback: {e}")
                            # Fallback: simple check for any human in last 5
                            human_found = any(not m.author.bot and not m.webhook_id for m in recent_msgs[:5])
                            if not human_found:
                                return
                        
                        msg = await self._generate_ambient_thought(channel, state)
                        if msg:
                            # Send via webhook to appear as persona
                            await self._send_as_persona(channel, msg)
                            state.last_ambient_trigger = now
                            logger.info(f"Sent ambient lull message in {channel.name}")

    async def _send_as_persona(self, channel: discord.TextChannel, message: str):
        """Send a message via webhook as the current persona."""
        try:
            # Use internal persona state first
            persona = self.current_persona
            
            # Fallback to ChatCog if missing
            if not persona:
                chat_cog = self.bot.get_cog("ChatCog")
                if chat_cog:
                    persona = chat_cog.current_persona
            
            if not persona:
                # Fallback to regular send if no persona
                await channel.send(message)
                return
            display_name = persona.character.display_name
            avatar_url = persona.character.avatar_url
            
            # Get or create webhook
            webhooks = await channel.webhooks()
            webhook = next((w for w in webhooks if w.name == "PersonaBot_Proxy"), None)
            if not webhook:
                webhook = await channel.create_webhook(name="PersonaBot_Proxy")
            
            await webhook.send(
                content=message,
                username=display_name,
                avatar_url=avatar_url
            )
        except Exception as e:
            logger.error(f"Failed to send ambient message via webhook: {e}")
            # Fallback to regular send
            await channel.send(message)

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
