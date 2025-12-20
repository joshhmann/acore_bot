"""Behavior Engine - Central brain for bot autonomy and responsiveness.

Consolidates naturalness, ambient mode, proactive engagement, mood,
environmental awareness, callbacks, and curiosity into a single system.
"""

import logging
import random
import asyncio
from datetime import datetime
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
    short_term_memories: List[Dict] = field(
        default_factory=list
    )  # [{topic, timestamp, importance}]

    # Mood System (T1: Dynamic Mood System)
    mood_state: str = (
        "neutral"  # States: neutral, excited, frustrated, sad, bored, curious
    )
    mood_intensity: float = 0.5  # 0.0-1.0 scale
    mood_history: deque = field(
        default_factory=lambda: deque(maxlen=10)
    )  # Track mood transitions
    last_mood_update: datetime = field(default_factory=datetime.now)

    # Curiosity System (T7: Curiosity-Driven Follow-Up Questions)
    curiosity_level: str = "medium"  # Levels: low, medium, high, maximum
    last_followup_time: datetime = field(default_factory=datetime.now)
    asked_topics: deque = field(
        default_factory=lambda: deque(maxlen=20)
    )  # Track asked topics to avoid repetition

    # T21-T22: Emotional Contagion System
    sentiment_history: deque = field(
        default_factory=lambda: deque(maxlen=10)
    )  # Track last 10 user sentiment scores (-1.0 to 1.0)
    contagion_active: bool = False  # Whether emotional contagion is currently active
    contagion_modifier: str = "balanced"  # empathetic, enthusiastic, balanced
    contagion_intensity: float = 0.0  # 0.0-1.0, strength of contagion effect


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
        lorebook_service: Optional[LorebookService] = None,
        thinking_service=None,
        evolution_tracker=None,
    ):
        self.bot = bot
        self.ollama = ollama
        self.context_manager = context_manager
        self.lorebook_service = lorebook_service
        self.thinking_service = thinking_service  # Cheap/fast LLM for decisions

        # State tracking
        self.states: Dict[int, BehaviorState] = defaultdict(BehaviorState)
        self.voice_states: Dict[int, Dict] = {}  # guild_id -> voice state info

        # T11: Adaptive Ambient Timing - Channel Activity Profiler
        self.channel_profiler = None  # Will be initialized in start() method

        # T13: Character Evolution System
        self.evolution_tracker = (
            evolution_tracker  # Will be initialized in start() if None
        )

        # Configuration (from Config)

        self.reaction_chance = 0.15
        self.ambient_interval_min = (
            Config.AMBIENT_MIN_INTERVAL
        )  # Default 600s, should be higher
        self.ambient_chance = (
            Config.AMBIENT_CHANCE
        )  # Default 0.3, reduce to prevent spam
        self.proactive_enabled = Config.PROACTIVE_ENGAGEMENT_ENABLED
        self.proactive_cooldown = (
            Config.PROACTIVE_COOLDOWN
        )  # Seconds between proactive engagements

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

        # T11: Initialize Channel Activity Profiler
        # For now, create a simple stub - will be replaced with proper import
        self.channel_profiler = None
        logger.info("Channel Activity Profiler disabled (import issue)")

        # T13: Initialize Evolution Tracker
        if self.evolution_tracker is None:
            from services.persona.evolution import PersonaEvolutionTracker

            self.evolution_tracker = PersonaEvolutionTracker()
            logger.info("PersonaEvolutionTracker initialized")

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

        # T11: Stop Channel Activity Profiler
        if self.channel_profiler:
            try:
                await self.channel_profiler.stop()
            except Exception as e:
                logger.error(f"Error stopping Channel Activity Profiler: {e}")

        logger.info("Behavior Engine stopped")

    def set_persona(self, persona):
        """Update the active persona."""
        self.current_persona = persona

    async def _analyze_message_topics(self, message: str) -> List[str]:
        """
        Analyze message content to extract topics using lightweight keyword matching.

        Performance target: < 50ms topic detection

        Args:
            message: The message content to analyze

        Returns:
            List of detected topics (lowercase, deduplicated)
        """
        import re
        from typing import Set

        # Convert to lowercase for matching
        content = message.lower()

        # Common topic indicators and patterns
        topic_patterns = {
            # Gaming topics
            "gaming": r"\b(games?|gaming|play(ed|ing)?|gameplay|fps|rpg|mmo|steam|epic|nintendo|playstation|xbox)\b",
            "technology": r"\b(tech|software|hardware|computer|programming|code|app|phone|device|ai|machine learning)\b",
            "movies": r"\b(movie|film|cinema|watch(ed|ing)?|netflix|hbo|disney\+|stream|director|actor)\b",
            "music": r"\b(music|song|album|artist|band|concert|listen|spotify|apple music|playlist)\b",
            "sports": r"\b(sport|game|match|team|player|score|win|lose|championship|league|football|basketball|baseball)\b",
            "food": r"\b(food|eat|cooking|recipe|restaurant|meal|breakfast|lunch|dinner|delicious|taste)\b",
            "travel": r"\b(travel|trip|vacation|flight|hotel|visit|country|city|tour|destination)\b",
            "work": r"\b(work|job|career|office|boss|colleague|meeting|project|deadline|salary|hire)\b",
            "school": r"\b(school|college|university|class|study|exam|homework|degree|professor|student)\b",
            "health": r"\b(health|doctor|hospital|medicine|exercise|fitness|diet|sick|pain|treatment)\b",
            "relationships": r"\b(relationship|dating|love|friend|family|married|single|breakup|divorce)\b",
            "money": r"\b(money|cash|dollar|price|cost|expensive|cheap|buy|sell|invest|budget)\b",
            "weather": r"\b(weather|rain|snow|sunny|cold|hot|temperature|climate|forecast)\b",
            "pets": r"\b(pet|dog|cat|animal|puppy|kitten|vet|leash|toy|treat)\b",
            "books": r"\b(book|novel|read|reading|author|story|chapter|library|literature)\b",
            "politics": r"\b(politics|government|election|president|policy|vote|democrat|republican|congress)\b",
            "religion": r"\b(god|church|religion|pray|faith|bible|jesus|christian|muslim|islam)\b",
        }

        detected_topics: Set[str] = set()

        # Check each pattern
        for topic, pattern in topic_patterns.items():
            if re.search(pattern, content, re.IGNORECASE):
                detected_topics.add(topic)

        # Use ThinkingService if available for more sophisticated detection
        if self.thinking_service and len(detected_topics) < 3:
            try:
                prompt = f"""Extract 1-3 main topics from this message. Respond with comma-separated topics only.

Message: "{message}"

Examples:
- "I love playing Elden Ring" -> gaming
- "The new Marvel movie was amazing" -> movies
- "Just adopted a puppy" -> pets

Topics:"""

                response = await self.thinking_service.quick_generate(
                    prompt, max_tokens=30
                )
                llm_topics = [
                    t.strip().lower() for t in response.split(",") if t.strip()
                ]

                # Only add topics that match our predefined categories
                for topic in llm_topics:
                    if topic in topic_patterns:
                        detected_topics.add(topic)

            except Exception as e:
                logger.debug(f"ThinkingService topic analysis failed: {e}")

        return list(detected_topics)

    async def _should_engage_by_topics(self, topics: List[str]) -> Dict[str, Any]:
        """
        Determine if persona should engage based on topic interests and avoidances.

        Args:
            topics: List of detected topics

        Returns:
            Dict with engagement recommendation and reasoning
        """
        if not topics or not self.current_persona:
            return {"should_engage": None, "reason": "no_topics_or_persona"}

        character = self.current_persona.character
        topic_interests = getattr(character, "topic_interests", [])
        topic_avoidances = getattr(character, "topic_avoidances", [])

        # If no preferences configured, no topic-based filtering
        if not topic_interests and not topic_avoidances:
            return {"should_engage": None, "reason": "no_preferences"}

        # Check for avoided topics (highest priority)
        for topic in topics:
            for avoided in topic_avoidances:
                if avoided.lower() in topic or topic in avoided.lower():
                    logger.debug(
                        f"Topic avoidance triggered: {topic} matches {avoided}"
                    )
                    return {
                        "should_engage": False,
                        "reason": f"avoided_topic:{avoided}",
                        "modifier": -1.0,  # Strong negative modifier
                    }

        # Check for interested topics
        engagement_modifier = 0.0
        matched_interests = []

        for topic in topics:
            for interest in topic_interests:
                if interest.lower() in topic or topic in interest.lower():
                    matched_interests.append(interest)
                    engagement_modifier += 0.3  # +30% chance per matched interest

        if matched_interests:
            logger.debug(
                f"Topic interests triggered: {matched_interests} (modifier: {engagement_modifier})"
            )
            return {
                "should_engage": True,
                "reason": f"interested_topics:{','.join(matched_interests)}",
                "modifier": min(engagement_modifier, 0.9),  # Cap at 90% increase
            }

        # No strong preferences matched
        return {"should_engage": None, "reason": "no_topic_match"}

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

        # T11: Record message to Channel Activity Profiler
        if self.channel_profiler:
            try:
                channel_name = getattr(message.channel, "name", str(message.channel.id))
                await self.channel_profiler.record_message(
                    message.channel.id, channel_name
                )
            except Exception as e:
                logger.debug(f"Failed to record message to profiler: {e}")

        # 1. Update Mood (T1: Dynamic Mood System)
        await self._update_mood(message, state)

        # 2. T9: Analyze Message Topics
        topics = await self._analyze_message_topics(message.content)

        # T15: Check for conflict triggers in persona interactions
        if message.webhook_id and self.current_persona:
            # Message from another persona - check for conflicts
            persona_relationships = getattr(self.bot, "persona_relationships", None)
            if persona_relationships:
                current_name = self.current_persona.character.display_name
                speaker_name = message.author.display_name

                # Check if message contains conflict trigger
                conflict_trigger = persona_relationships.detect_conflict_trigger(
                    current_name, speaker_name, message.content, topics
                )

                if conflict_trigger:
                    # Escalate conflict
                    persona_relationships.escalate_conflict(
                        current_name, speaker_name, conflict_trigger
                    )
                    logger.info(
                        f"Conflict triggered between {current_name} and {speaker_name}: {conflict_trigger}"
                    )

        # T13: Track interaction for character evolution
        if self.evolution_tracker and self.current_persona:
            try:
                evolution_event = await self.evolution_tracker.track_message(
                    persona_id=self.current_persona.persona_id,
                    user_id=str(message.author.id),
                    topics=topics,
                    conversation_turn=state.message_count,
                )

                # If milestone achieved, log it (could send notification in future)
                if evolution_event:
                    logger.info(
                        f"🎉 Evolution milestone: {self.current_persona.character.display_name} "
                        f"reached {evolution_event['milestone']} messages!"
                    )
            except Exception as e:
                logger.error(f"Failed to track evolution: {e}")

        # 3. Analyze Conversation Context (T3: Context-Aware Response Length)
        from cogs.chat.helpers import ChatHelpers

        context_type = ChatHelpers.analyze_conversation_context(
            message.content,
            history=[],  # TODO: Could pass recent history for deeper analysis
        )

        # 4. Decision: React?
        reaction_emoji = await self._decide_reaction(message, state)

        # 5. Decision: Proactive Reply? (Jump in)
        # Only if not mentioned (handled by ChatCog) and not a reply to bot
        engagement = None
        is_reply_to_bot = False
        if message.reference and message.reference.resolved:
            # Check if it's a reply to the bot
            from discord import DeletedReferencedMessage

            if not isinstance(message.reference.resolved, DeletedReferencedMessage):
                is_reply_to_bot = message.reference.resolved.author == self.bot.user

        if self.bot.user not in message.mentions and not is_reply_to_bot:
            engagement = await self._decide_proactive_engagement(message, state, topics)

        if reaction_emoji or engagement:
            return {
                "should_respond": bool(engagement),
                "reaction": reaction_emoji,
                "reply": engagement,
                "reason": "proactive" if engagement else "reaction",
                "suggested_style": None,
                "mood": state.mood_state,  # T1: Include mood in response
                "mood_intensity": state.mood_intensity,
                "context_type": context_type,  # T3: Pass context for verbosity control
                "topics": topics,  # T9: Include detected topics
            }

        return None

    async def _update_mood(self, message: discord.Message, state: BehaviorState):
        """
        Update mood state based on message sentiment and context.

        Mood transitions are gradual (max 0.1 shift per message) and influenced by:
        - Message sentiment (positive/negative)
        - User tone (excited, frustrated, etc.)
        - Time decay (moods fade to neutral over 30 min)
        """
        now = datetime.now()

        # Time decay: Moods fade to neutral over time (30 min = 1800 seconds)
        time_since_update = (now - state.last_mood_update).total_seconds()
        if time_since_update > 1800:  # 30 minutes
            # Decay toward neutral
            if state.mood_state != "neutral":
                state.mood_intensity = max(0.0, state.mood_intensity - 0.2)
                if state.mood_intensity < 0.3:
                    state.mood_state = "neutral"
                    state.mood_intensity = 0.5
                    logger.debug(
                        f"Mood decayed to neutral in channel {message.channel.id}"
                    )

        # Simple sentiment analysis based on keywords and patterns
        content = message.content.lower()
        sentiment_score = 0.0  # -1.0 (very negative) to 1.0 (very positive)

        # Positive indicators
        positive_words = [
            "lol",
            "lmao",
            "haha",
            "cool",
            "awesome",
            "great",
            "love",
            "!!",
            "nice",
            "yeah",
            "yay",
            "amazing",
        ]
        negative_words = [
            "ugh",
            "hate",
            "annoying",
            "stupid",
            "terrible",
            "bad",
            "sad",
            "angry",
            "frustrated",
            "boring",
        ]
        question_words = ["?", "how", "what", "why", "when", "where", "curious"]

        # Count sentiment indicators
        positive_count = sum(1 for w in positive_words if w in content)
        negative_count = sum(1 for w in negative_words if w in content)
        question_count = sum(1 for w in question_words if w in content)

        # Calculate sentiment (-1.0 to 1.0)
        if positive_count + negative_count > 0:
            sentiment_score = (positive_count - negative_count) / (
                positive_count + negative_count + 1
            )

        # Determine target mood based on sentiment
        target_mood = state.mood_state
        target_intensity = state.mood_intensity

        if sentiment_score > 0.5:
            target_mood = "excited"
            target_intensity = min(1.0, 0.7 + sentiment_score * 0.3)
        elif sentiment_score > 0.2:
            target_mood = "curious" if question_count > 0 else "neutral"
            target_intensity = 0.6
        elif sentiment_score < -0.5:
            target_mood = "frustrated"
            target_intensity = min(1.0, 0.7 + abs(sentiment_score) * 0.3)
        elif sentiment_score < -0.2:
            target_mood = "sad"
            target_intensity = 0.6
        elif question_count > 1:
            target_mood = "curious"
            target_intensity = 0.6
        elif "bored" in content or time_since_update > 600:  # 10 min since last message
            target_mood = "bored"
            target_intensity = 0.5

        # Gradual transition (max 0.1 shift per message)
        if target_mood != state.mood_state:
            # Transition to new mood gradually
            state.mood_intensity = max(0.0, state.mood_intensity - 0.1)
            if state.mood_intensity < 0.3:
                # Switch mood
                old_mood = state.mood_state
                state.mood_state = target_mood
                state.mood_intensity = target_intensity
                state.mood_history.append(
                    {
                        "from": old_mood,
                        "to": target_mood,
                        "timestamp": now,
                        "trigger": "sentiment",
                    }
                )
                logger.debug(
                    f"Mood changed from {old_mood} to {target_mood} (intensity: {target_intensity:.2f}) in channel {message.channel.id}"
                )
        else:
            # Same mood, adjust intensity gradually
            intensity_diff = target_intensity - state.mood_intensity
            state.mood_intensity += max(-0.1, min(0.1, intensity_diff))
            state.mood_intensity = max(0.0, min(1.0, state.mood_intensity))

        state.last_mood_update = now

        # T21-T22: Track user sentiment for emotional contagion
        # Only track sentiment from actual users (not bots/webhooks)
        if not message.author.bot and not message.webhook_id:
            state.sentiment_history.append(sentiment_score)

            # Update emotional contagion if we have enough history
            if len(state.sentiment_history) >= 5:
                self._update_emotional_contagion(state)

    def _update_emotional_contagion(self, state: BehaviorState):
        """Calculate and update emotional contagion based on user sentiment trends.

        T21-T22: Emotional Contagion System
        This makes the bot more emotionally intelligent by detecting prolonged
        user emotional states and adapting its tone accordingly.

        - Consistently sad user → Bot becomes more empathetic and supportive
        - Consistently happy user → Bot becomes more energetic and enthusiastic
        - Neutral/mixed → Bot maintains balanced tone

        Performance: <0.1ms (simple average calculation)
        """
        # Calculate average sentiment over recent messages
        avg_sentiment = sum(state.sentiment_history) / len(state.sentiment_history)

        # Determine contagion state based on average sentiment
        old_modifier = state.contagion_modifier

        if avg_sentiment < -0.3:  # Consistently negative (sad, frustrated)
            state.contagion_active = True
            state.contagion_modifier = "empathetic"
            state.contagion_intensity = min(1.0, abs(avg_sentiment))

        elif avg_sentiment > 0.3:  # Consistently positive (happy, excited)
            state.contagion_active = True
            state.contagion_modifier = "enthusiastic"
            state.contagion_intensity = min(1.0, avg_sentiment)

        else:  # Neutral or mixed sentiments
            state.contagion_active = False
            state.contagion_modifier = "balanced"
            state.contagion_intensity = 0.0

        # Log contagion changes
        if old_modifier != state.contagion_modifier and state.contagion_active:
            logger.debug(
                f"Emotional contagion activated: {state.contagion_modifier} "
                f"(intensity: {state.contagion_intensity:.2f}, avg_sentiment: {avg_sentiment:.2f})"
            )
        elif not state.contagion_active and old_modifier != "balanced":
            logger.debug("Emotional contagion deactivated (sentiment neutral)")

    async def _tick_loop(self):
        """Periodic loop to check for ambient opportunities."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute
                for channel_id, state in list(self.states.items()):
                    await self._check_ambient_triggers(channel_id, state)
            except Exception as e:
                logger.error(f"Error in BehaviorEngine tick: {e}")

    async def _check_ambient_triggers(self, channel_id: int, state: BehaviorState):
        """Check if we should say something during a lull."""
        # Skip if proactive engagement is disabled
        if not self.proactive_enabled:
            return

        # Skip if ambient mode is explicitly disabled
        if not Config.AMBIENT_MODE_ENABLED:
            return

        # Skip if channel is not in allowed ambient channels (if specified)
        if Config.AMBIENT_CHANNELS and channel_id not in Config.AMBIENT_CHANNELS:
            return

        now = datetime.now()
        silence_duration = (now - state.last_message_time).total_seconds()

        # T11: Get adaptive thresholds from Channel Activity Profiler
        adaptive_thresholds = {
            "silence_threshold": 3600.0,  # Default 1 hour
            "cooldown_multiplier": 1.0,
            "chance_modifier": 0.0,
        }

        if self.channel_profiler:
            try:
                adaptive_thresholds = (
                    await self.channel_profiler.get_adaptive_thresholds(channel_id)
                )
            except Exception as e:
                logger.debug(f"Failed to get adaptive thresholds: {e}")

        # Use adaptive silence threshold
        silence_threshold = adaptive_thresholds["silence_threshold"]

        # Lull Detection: Use adaptive threshold (default 1-8 hours range)
        if (
            silence_duration > silence_threshold and silence_duration < 28800
        ):  # < 8 hours
            time_since_last_ambient = (now - state.last_ambient_trigger).total_seconds()

            # T11: Apply adaptive cooldown multiplier
            adaptive_cooldown = (
                self.ambient_interval_min * adaptive_thresholds["cooldown_multiplier"]
            )

            # Only allow ambient message after adaptive cooldown
            if time_since_last_ambient > max(
                adaptive_cooldown, 21600
            ):  # At least 6 hours
                # T11: Apply adaptive chance modifier
                base_chance = 1 / 6  # ~16.7% base chance
                adaptive_chance = max(
                    0.05, min(0.8, base_chance + adaptive_thresholds["chance_modifier"])
                )

                if random.random() < adaptive_chance:
                    channel = self.bot.get_channel(channel_id)
                    if channel and isinstance(channel, discord.TextChannel):
                        # AI-FIRST SPAM CHECK: Let thinking model decide if speaking would be annoying
                        try:
                            recent_msgs = [
                                msg async for msg in channel.history(limit=6)
                            ]
                            if recent_msgs:
                                # Build context for LLM to evaluate
                                history_summary = []
                                for msg in reversed(recent_msgs):
                                    author_type = (
                                        "BOT"
                                        if (msg.author.bot or msg.webhook_id)
                                        else "HUMAN"
                                    )
                                    history_summary.append(
                                        f"[{author_type}] {msg.author.display_name}: {msg.content[:100]}"
                                    )

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
                                    should_speak = await self.thinking_service.decide(
                                        decision_prompt, default=False
                                    )
                                else:
                                    decision = await self.ollama.generate(
                                        decision_prompt
                                    )
                                    should_speak = "YES" in decision.strip().upper()

                                if not should_speak:
                                    logger.info(
                                        f"AI decided NOT to send ambient message in {channel.name} (spam prevention)"
                                    )
                                    return

                        except Exception as e:
                            logger.warning(f"AI spam check failed, using fallback: {e}")
                            # Fallback: simple check for any human in last 5
                            try:
                                recent_msgs_fallback = [
                                    msg async for msg in channel.history(limit=5)
                                ]
                                human_found = any(
                                    not m.author.bot and not m.webhook_id
                                    for m in recent_msgs_fallback[:5]
                                )
                                if not human_found:
                                    return
                            except Exception:
                                return

                        msg = await self._generate_ambient_thought(channel, state)
                        if msg:
                            # Send via webhook to appear as persona
                            await self._send_as_persona(channel, msg)
                            state.last_ambient_trigger = now
                            logger.info(
                                f"Sent ambient lull message in {channel.name} (adaptive: silence={silence_duration:.0f}s, chance={adaptive_chance:.2f})"
                            )

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
                content=message, username=display_name, avatar_url=avatar_url
            )
        except Exception as e:
            logger.error(f"Failed to send ambient message via webhook: {e}")
            # Fallback to regular send
            await channel.send(message)

    async def handle_voice_update(self, member, before, after):
        """Handle voice state changes (Environmental Awareness)."""
        if member.bot:
            return

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
            if random.random() < 0.3:  # 30% chance
                # Find a text channel to comment in (usually the system channel or general)
                # For now, simplistic selection
                if member.guild.system_channel:
                    msg = await self._generate_environmental_comment(member, event_type)
                    if msg:
                        await member.guild.system_channel.send(msg)

    # --- Generative Methods ---

    async def _decide_reaction(
        self, message: discord.Message, state: BehaviorState
    ) -> Optional[str]:
        """
        Decide if and what emoji to react with.

        Mood affects reaction selection:
        - excited: More fire/party reactions
        - sad: More sympathetic reactions
        - frustrated: More thinking/confused reactions
        - bored: Less likely to react
        - curious: More question reactions
        """
        # Mood affects reaction probability
        reaction_probability = self.reaction_chance

        if state.mood_state == "excited":
            reaction_probability += 0.1 * state.mood_intensity
        elif state.mood_state == "bored":
            reaction_probability -= 0.05 * state.mood_intensity
        elif state.mood_state == "curious":
            reaction_probability += 0.05 * state.mood_intensity

        if random.random() > reaction_probability:
            return None

        # Lightweight check: Basic sentiment/keyword map
        # Mood influences emoji selection
        content = message.content.lower()

        # Mood-based emoji selection
        if state.mood_state == "excited":
            if any(w in content for w in ["lol", "lmao", "haha"]):
                return "😂"
            if any(w in content for w in ["cool", "wow", "nice", "awesome"]):
                return "🔥"
            if "?" in content:
                return "👀"
            return "🎉" if state.mood_intensity > 0.7 else "✨"

        elif state.mood_state == "sad":
            if any(w in content for w in ["sorry", "sad", "unfortunately"]):
                return "😔"
            if any(w in content for w in ["bad", "terrible", "awful"]):
                return "💔"
            return "😢" if state.mood_intensity > 0.6 else None

        elif state.mood_state == "frustrated":
            if "?" in content:
                return "🤔"
            if any(w in content for w in ["why", "how"]):
                return "😤"
            return "😑" if state.mood_intensity > 0.6 else None

        elif state.mood_state == "curious":
            if "?" in content:
                return "🤔"
            if any(w in content for w in ["tell", "explain", "what"]):
                return "👀"
            return "🧐" if state.mood_intensity > 0.6 else None

        # Default neutral reactions
        if any(w in content for w in ["lol", "lmao", "haha"]):
            return "😂"
        if any(w in content for w in ["cool", "wow", "nice"]):
            return "🔥"
        if "?" in content:
            return "🤔"

        return None

        # Lightweight check: Basic sentiment/keyword map
        # Or lightweight LLM call if needed
        # For efficiency, let's use a simplified keyword map derived from the old Naturalness

        content = message.content.lower()
        if any(w in content for w in ["lol", "lmao", "haha"]):
            return "😂"
        if any(w in content for w in ["cool", "wow", "nice"]):
            return "🔥"
        if "?" in content:
            return "🤔"

        return None

    async def _decide_proactive_engagement(
        self,
        message: discord.Message,
        state: BehaviorState,
        topics: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Decide whether to jump into a conversation or ask a follow-up question.

        Mood affects engagement probability:
        - excited: +20% chance to engage
        - bored: +10% chance to engage (looking for stimulation)
        - sad: -20% chance to engage
        - curious: +15% chance to engage

        T7: Curiosity-Driven Follow-Up Questions
        - Checks for interesting topics to ask follow-up questions
        - Respects curiosity level and cooldowns
        """
        # 0. Check channel restrictions
        if Config.AMBIENT_CHANNELS and message.channel.id not in Config.AMBIENT_CHANNELS:
            return None

        # 1. Check cooldown for proactive engagement
        if (
            datetime.now() - state.last_proactive_trigger
        ).total_seconds() < self.proactive_cooldown:
            return None

        # T9: Check topic-based engagement first (highest priority)
        if topics:
            topic_decision = await self._should_engage_by_topics(topics)
            if topic_decision["should_engage"] is False:
                # Strong topic avoidance - skip engagement entirely
                logger.debug(f"Topic avoidance: {topic_decision['reason']}")
                return None
            elif topic_decision["should_engage"] is True:
                # Topic interest - add modifier and continue
                engagement_modifier = topic_decision.get("modifier", 0.0)
                logger.debug(
                    f"Topic interest: {topic_decision['reason']} (modifier: {engagement_modifier})"
                )
            else:
                engagement_modifier = 0.0
        else:
            engagement_modifier = 0.0

        # T7: Check for follow-up question opportunities first (higher priority)
        followup = await self._check_followup_opportunity(message, state)
        if followup:
            state.last_proactive_trigger = datetime.now()
            return followup

        # 2. Mood-based engagement probability adjustment (on top of topic modifier)
        mood_modifier = 0.0
        if state.mood_state == "excited":
            mood_modifier = 0.2 * state.mood_intensity
        elif state.mood_state == "bored":
            mood_modifier = 0.1 * state.mood_intensity
        elif state.mood_state == "sad":
            mood_modifier = -0.2 * state.mood_intensity
        elif state.mood_state == "curious":
            mood_modifier = 0.15 * state.mood_intensity

        # Combine topic and mood modifiers
        total_modifier = engagement_modifier + mood_modifier

        # Random check with combined adjustment
        base_chance = 0.3  # 30% base chance
        if random.random() > (base_chance + total_modifier):
            return None

        # 3. Check Interest (LLM Fast Path)
        # We ask the LLM: "Is [Character] interested in this?"
        if not self.current_persona:
            return None

        # Include mood in the decision prompt
        mood_context = (
            f"Current mood: {state.mood_state} (intensity: {state.mood_intensity:.1f})"
        )

        prompt = f"""Message: "{message.content}"
{mood_context}

As {self.current_persona.character.display_name}, is this a topic you would excitedly jump into?
Reply YES or NO."""

        try:
            res = await self.ollama.generate(prompt)
            if "YES" in res.upper():
                # Generate actual reply with mood context
                mood_instruction = self._get_mood_instruction(state)
                reply_prompt = f"""User said: "{message.content}"

{mood_context}
{mood_instruction}

Reply naturally as {self.current_persona.character.display_name}. Keep it short and casual."""
                reply = await self.ollama.generate(reply_prompt)
                state.last_proactive_trigger = datetime.now()
                return reply
        except Exception:
            pass

        return None

    async def _check_followup_opportunity(
        self, message: discord.Message, state: BehaviorState
    ) -> Optional[str]:
        """
        Check if we should ask a follow-up question (T7: Curiosity-Driven Follow-Up Questions).

        Returns:
            Follow-up question string or None
        """
        # Get curiosity level from persona config or use state default
        curiosity_level = "medium"
        if self.current_persona and hasattr(self.current_persona, "config"):
            curiosity_level = (
                self.current_persona.config.get("autonomous_behavior", {})
                .get("curiosity", {})
                .get("curiosity_level", "medium")
            )
        else:
            curiosity_level = state.curiosity_level

        # Curiosity probability mapping
        curiosity_probabilities = {
            "low": 0.10,  # 10% chance
            "medium": 0.30,  # 30% chance
            "high": 0.60,  # 60% chance
            "maximum": 0.80,  # 80% chance
        }

        curiosity_chance = curiosity_probabilities.get(curiosity_level, 0.30)

        # 1. Check follow-up cooldown (max 1 question per configured interval)
        from config import Config

        now = datetime.now()
        if (
            now - state.last_followup_time
        ).total_seconds() < Config.PERSONA_FOLLOWUP_COOLDOWN:
            return None

        # 2. Check 15-minute window limit (max 3 questions per 15 minutes)
        recent_followups = [
            mem
            for mem in state.short_term_memories
            if mem.get("type") == "followup"
            and (now - mem["timestamp"]).total_seconds() < 900  # 15 minutes
        ]
        if len(recent_followups) >= 3:
            return None

        # 3. Random curiosity check
        if random.random() > curiosity_chance:
            return None

        # 4. Detect interesting topics
        topics = await self._detect_interesting_topics(message.content)
        if not topics:
            return None

        # 5. Check if we've already asked about these topics recently
        new_topics = [
            topic
            for topic in topics
            if topic.lower() not in [t.lower() for t in state.asked_topics]
        ]
        if not new_topics:
            return None

        # 6. Generate follow-up question for the first new topic
        topic = new_topics[0]
        question = await self._generate_followup_question(topic, message.content)

        if question:
            # Update tracking
            state.last_followup_time = now
            state.asked_topics.append(topic)
            state.short_term_memories.append(
                {
                    "type": "followup",
                    "topic": topic,
                    "timestamp": now,
                    "question": question,
                }
            )

            logger.debug(
                f"Asked follow-up question about '{topic}' in channel {message.channel.id}"
            )
            return question

        return None

    def _get_mood_instruction(self, state: BehaviorState) -> str:
        """
        Generate mood-specific instruction for LLM prompts.

        Returns a string describing how the mood should affect the response.
        """
        mood_instructions = {
            "excited": "You're feeling excited and energetic. Be enthusiastic and engaged!",
            "sad": "You're feeling a bit down. Be more subdued and thoughtful in your response.",
            "frustrated": "You're feeling frustrated. Your responses may be more curt or sarcastic.",
            "bored": "You're feeling bored. You might be looking for something interesting to engage with.",
            "curious": "You're feeling curious. Show genuine interest and ask follow-up questions.",
            "neutral": "You're in a neutral, balanced mood.",
        }

        instruction = mood_instructions.get(
            state.mood_state, mood_instructions["neutral"]
        )

        # Intensity modifier
        if state.mood_intensity > 0.7:
            instruction = instruction.replace("feeling", "feeling very")
        elif state.mood_intensity < 0.4:
            instruction = instruction.replace("feeling", "feeling slightly")

        return instruction

    async def _detect_interesting_topics(self, message: str) -> List[str]:
        """
        Detect interesting topics in a message that might warrant follow-up questions.

        Uses ThinkingService to identify topics worth following up on.
        Looks for: incomplete explanations, new concepts, user interests.

        Args:
            message: The message content to analyze

        Returns:
            List of interesting topics detected
        """
        if not self.thinking_service:
            # Fallback to simple keyword detection
            topics = []
            content = message.lower()

            # Look for indicators of interesting topics
            interest_indicators = [
                "just got",
                "just bought",
                "just finished",
                "just started",
                "thinking about",
                "planning to",
                "going to",
                "might",
                "working on",
                "playing",
                "watching",
                "reading",
            ]

            # Extract potential topics
            for indicator in interest_indicators:
                if indicator in content:
                    # Simple extraction - get the phrase after the indicator
                    idx = content.find(indicator)
                    if idx != -1:
                        phrase = content[idx + len(indicator) :].strip()
                        # Take first 3-4 words as topic
                        words = phrase.split()[:4]
                        topic = " ".join(words)
                        if len(topic) > 3:  # Minimum length
                            topics.append(topic)

            return topics[:3]  # Max 3 topics

        # Use ThinkingService for more sophisticated detection
        try:
            prompt = f"""Analyze this message for interesting topics that would make good follow-up questions:

Message: "{message}"

Look for:
- Incomplete explanations ("I was thinking about...")
- New experiences or activities ("Just started playing...")
- Plans or intentions ("Planning to...")
- Hobbies or interests mentioned
- Emotional states that could be explored

Respond with a comma-separated list of 1-3 interesting topics (max 3 words each). If nothing interesting, respond with "NONE"."""

            response = await self.thinking_service.quick_generate(prompt, max_tokens=50)
            response = response.strip()

            if response.upper() == "NONE":
                return []

            # Parse topics
            topics = [topic.strip() for topic in response.split(",") if topic.strip()]
            return topics[:3]  # Max 3 topics

        except Exception as e:
            logger.warning(f"Topic detection failed: {e}")
            return []

    async def _generate_followup_question(
        self, topic: str, context: str
    ) -> Optional[str]:
        """
        Generate a natural follow-up question about a topic.

        Args:
            topic: The topic to ask about
            context: The original message context

        Returns:
            A natural follow-up question
        """
        if not self.current_persona:
            return None

        try:
            prompt = f"""As {self.current_persona.character.display_name}, generate a natural, brief follow-up question about this topic.

Topic: {topic}
Context: "{context}"

Requirements:
- Keep it under 15 words
- Sound genuinely curious
- Match your personality
- Don't be generic
- Ask for more details

Examples:
- "A convention? What kind was it?"
- "Playing what game now?"
- "Planning something exciting?"

Generate just the question, nothing else:"""

            if self.thinking_service:
                question = await self.thinking_service.quick_generate(
                    prompt, max_tokens=30
                )
            else:
                question = await self.ollama.generate(prompt)
            return question.strip()

        except Exception as e:
            logger.warning(f"Follow-up question generation failed: {e}")
            return None

    async def _generate_ambient_thought(
        self, channel, state: BehaviorState
    ) -> Optional[str]:
        """
        Generate a random thought or callback.

        Mood affects the type of ambient message:
        - excited: More energetic, might share something interesting
        - sad: More melancholic or contemplative
        - bored: Explicitly looking for engagement
        - curious: Ask questions or bring up interesting topics
        """
        if not self.current_persona:
            return None

        # Include mood context in ambient thoughts
        mood_context = (
            f"Current mood: {state.mood_state} (intensity: {state.mood_intensity:.1f})"
        )
        mood_instruction = self._get_mood_instruction(state)

        # Decide between random thought or callback
        prompt = f"""You are hanging out in #{channel.name}. It's been quiet for a while.

{mood_context}
{mood_instruction}

Say something to break the silence. It could be:
1. A random thought based on your personality and current mood.
2. A callback to a recent topic (if you remember one).

Keep it conversational and short."""

        return await self.ollama.generate(prompt)

    async def _generate_environmental_comment(
        self, member, event_type
    ) -> Optional[str]:
        """
        Comment on voice activity.

        Mood affects environmental reactions:
        - excited: More enthusiastic greetings
        - sad: More subdued acknowledgments
        - bored: Might be more interested in activity
        """
        if not self.current_persona:
            return None

        # Get mood from guild's default channel state (or create default)
        # Use first text channel as proxy for guild mood state
        default_channel = (
            member.guild.system_channel or member.guild.text_channels[0]
            if member.guild.text_channels
            else None
        )

        if default_channel and default_channel.id in self.states:
            state = self.states[default_channel.id]
            mood_context = f"Current mood: {state.mood_state} (intensity: {state.mood_intensity:.1f})"
            mood_instruction = self._get_mood_instruction(state)
        else:
            mood_context = "Current mood: neutral"
            mood_instruction = ""

        prompt = f"""{member.display_name} just {event_type}ed the voice channel.

{mood_context}
{mood_instruction}

Make a brief, friendly comment about it as {self.current_persona.character.display_name}."""

        return await self.ollama.generate(prompt)
