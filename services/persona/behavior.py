"""Behavior Engine - Central brain for bot autonomy and responsiveness.

Consolidates naturalness, ambient mode, proactive engagement, mood,
environmental awareness, callbacks, and curiosity into a single system.
"""

import logging
import re
import random
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from collections import deque, defaultdict

from config import Config
from core.types import AcoreContext, AcoreMessage, AcoreChannel, AcoreUser
from services.llm.ollama import OllamaService
from services.core.context import ContextManager
from services.persona.lorebook import LorebookService

# RL components are optional for unit tests. Guard imports to avoid heavy deps
try:
    from services.persona.rl.service import RLService  # type: ignore
    from services.persona.rl.types import RLAction, RLState  # type: ignore
except Exception:
    RLService = None  # type: ignore

    class RLAction:
        WAIT = 0
        REACT = 1
        ENGAGE = 2
        INITIATE = 3

    class RLState:
        pass


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
        rl_service: Optional[RLService] = None,
    ):
        self.bot = bot
        self.ollama = ollama
        self.context_manager = context_manager
        self.lorebook_service = lorebook_service
        self.thinking_service = thinking_service  # Cheap/fast LLM for decisions
        self.rl_service = rl_service
        self.rl_enabled = rl_service.enabled if rl_service else False

        # State tracking
        self.states: Dict[int, BehaviorState] = defaultdict(BehaviorState)
        self.voice_states: Dict[int, Dict] = {}  # guild_id -> voice state info

        # RL Context: (channel_id, user_id) -> (prev_action, prev_state, prev_sentiment, prev_affinity, timestamp)
        self.reward_context: Dict[
            Tuple[int, int], Tuple[RLAction, RLState, float, float, datetime]
        ] = {}

        # T11: Adaptive Ambient Timing - Channel Activity Profiler
        self.channel_profiler = None  # Will be initialized in start() method

        # Configuration (from Config)

        # Load reaction probability from config (exposed for tuning)
        self.reaction_chance = getattr(Config, "BEHAVIOR_REACTION_PROBABILITY", 0.5)
        self.proactive_interval_min = 600
        # Base proactive chance loaded from config (tunable)
        self.proactive_base_chance = getattr(
            Config, "BEHAVIOR_PROACTIVE_PROBABILITY", 0.6
        )
        self.proactive_enabled = Config.PROACTIVE_ENGAGEMENT_ENABLED
        self.proactive_cooldown = int(
            getattr(Config, "BEHAVIOR_COOLDOWN_SECONDS", 150)
        )  # Seconds between proactive engagements

        # T27: Local NLP Topic Detection
        self.topic_embeddings = {}
        self.topic_patterns = {
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

        # Background task
        self._running = False
        self._task = None

        # Persona reference (set by ChatCog). Provide a lightweight
        # default persona so unit tests can exercise behavior without
        # requiring a fully initialized character pipeline.
        class _DummyCharacter:
            def __init__(self):
                self.display_name = "Dummy"

        class _DummyPersona:
            def __init__(self):
                self.character = _DummyCharacter()
                self.persona_id = "dummy"

        self.current_persona = _DummyPersona()

        # Track available personas for rotation in ambient messages
        self._available_personas: List[Any] = []
        self._last_ambient_persona_index: int = 0

    def set_available_personas(self, personas: List[Any]):
        """Set the list of available personas for rotation."""
        self._available_personas = personas

    def _select_random_persona(self) -> Any:
        """Select a random persona from available personas."""
        if not self._available_personas:
            return self.current_persona
        return random.choice(self._available_personas)

    def _select_next_persona_rotating(self) -> Any:
        """Select next persona in rotation for ambient messages."""
        if not self._available_personas:
            return self.current_persona
        self._last_ambient_persona_index = (self._last_ambient_persona_index + 1) % len(
            self._available_personas
        )
        return self._available_personas[self._last_ambient_persona_index]

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

        # T27: Pre-compute topic embeddings for semantic matching
        if self.lorebook_service:
            self._precompute_topic_embeddings()
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


    def _bin_sentiment(self, score: float) -> int:
        """Bin sentiment score (-1.0 to 1.0) into discrete levels 0-3.

        Bins (as per RL specification):
        0: Very Negative (-∞ to -0.5)
        1: Negative (-0.5 to 0.0)
        2: Neutral (0.0 to 0.5)
        3: Positive (0.5 to +∞)
        """
        if score < -0.5:
            return 0
        if score < 0.0:
            return 1
        if score < 0.5:
            return 2
        return 3

    def _precompute_topic_embeddings(self):
        """Pre-compute embeddings for defined topics using LorebookService."""
        try:
            logger.info("Pre-computing topic embeddings for BehaviorEngine...")
            for topic, pattern in self.topic_patterns.items():
                # Extract keywords from regex pattern to create a rich semantic description
                # Remove regex syntax to get raw words
                clean_pattern = pattern.replace(r"\b", "").replace("(", " ").replace(")", " ").replace("|", " ")
                # Remove common regex chars
                clean_pattern = clean_pattern.replace("?", "").replace("*", "").replace("+", "")

                # Combine topic name with keywords
                # "technology tech software hardware..."
                description = f"{topic} {clean_pattern}"

                # Clean up whitespace
                description = " ".join(description.split())

                self.topic_embeddings[topic] = self.lorebook_service.get_embedding(description)
                logger.debug(f"Computed embedding for '{topic}' using description: '{description}'")
            logger.info(f"Pre-computed {len(self.topic_embeddings)} topic embeddings")
        except Exception as e:
            logger.error(f"Failed to pre-compute topic embeddings: {e}")

    async def _analyze_message_topics(self, message: str) -> List[str]:
        """
        Analyze message content to extract topics using hybrid regex + semantic NLP matching.

        Args:
            message: The message content to analyze

        Returns:
            List of detected topics (lowercase, deduplicated)
        """
        from typing import Set

        # Convert to lowercase for matching
        content = message.lower()

        detected_topics: Set[str] = set()

        # 1. Fast Path: Regex Matching
        for topic, pattern in self.topic_patterns.items():
            if re.search(pattern, content, re.IGNORECASE):
                detected_topics.add(topic)

        # 2. Smart Path: Semantic Matching (Local NLP)
        # Use sentence-transformers via LorebookService if available
        if self.lorebook_service and self.topic_embeddings:
            try:
                # Similarity threshold (tunable)
                # Lowered to 0.35 to catch more subtle semantic matches like "neural network" -> "technology"
                semantic_threshold = 0.35

                for topic, embedding in self.topic_embeddings.items():
                    if topic in detected_topics:
                        continue  # Skip if already found via regex

                    similarity = self.lorebook_service.compute_similarity(message, embedding)
                    if similarity > semantic_threshold:
                        detected_topics.add(topic)
                        logger.debug(f"Semantic topic detected: {topic} (score: {similarity:.2f})")
            except Exception as e:
                logger.debug(f"Semantic topic analysis failed: {e}")

        # 3. Fallback: ThinkingService (if available and few topics found)
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
                    if topic in self.topic_patterns:
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
        # Use active_persona if available (set by handle_message), otherwise fall back
        persona = getattr(self, "_active_persona", None) or self.current_persona
        if not topics or not persona:
            return {"should_engage": None, "reason": "no_topics_or_persona"}

        character = persona.character
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

    async def process_message(
        self, context: AcoreContext, persona: Optional[Any] = None
    ) -> Optional[Dict]:
        """
        Process a new message and decide on immediate reactions or replies.

        Args:
            context: The Acore context containing message, channel, user, and reply callback
            persona: Optional specific persona to evaluate. If None, uses current_persona.

        Returns:
            Dict containing action directives (e.g. {'reaction': '🔥', 'reply': '...'}) or None
        """
        message = context.message
        channel = context.channel
        user = context.user

        if user.metadata.get("is_bot", False):
            return None

        # Use provided persona or fall back to current
        active_persona = persona or self.current_persona
        if not active_persona:
            logger.warning("No persona available for process_message")
            return None

        # Convert string IDs to int for state tracking (will be updated later)
        channel_id = int(channel.id)
        user_id = int(user.id)

        state = self.states[channel_id]
        state.last_message_time = datetime.now()
        state.message_count += 1
        state.recent_users.add(user.display_name)

        # T11: Record message to Channel Activity Profiler
        if self.channel_profiler:
            try:
                await self.channel_profiler.record_message(channel_id, channel.name)
            except Exception as e:
                logger.debug(f"Failed to record message to profiler: {e}")

        # 1. Update Mood (T1: Dynamic Mood System)
        await self._update_mood(context, state)

        # 2. T9: Analyze Message Topics
        topics = await self._analyze_message_topics(message.text)

        # 3. Analyze Conversation Context (T3: Context-Aware Response Length)
        # Import is deferred to avoid importing Discord-specific modules during unit tests
        try:
            from adapters.discord.commands.chat.helpers import ChatHelpers

            context_type = ChatHelpers.analyze_conversation_context(
                message.text,
                history=[],  # TODO: Could pass recent history for deeper analysis
            )
        except Exception:
            context_type = None

        if self.rl_enabled and self.rl_service:
            ctx_key = (channel_id, user_id)
            last_ctx = self.reward_context.get(ctx_key)
            now = datetime.now()

            if last_ctx:
                last_time = last_ctx[-1]
                if (now - last_time).total_seconds() < 5.0:
                    return None

            current_sentiment = (
                state.sentiment_history[-1] if state.sentiment_history else 0.0
            )
            sentiment_bin = self._bin_sentiment(current_sentiment)

            time_bin = 4
            if last_ctx:
                time_diff = (now - last_ctx[-1]).total_seconds()
                if time_diff < 10:
                    time_bin = 0
                elif time_diff < 30:
                    time_bin = 1
                elif time_diff < 60:
                    time_bin = 2
                elif time_diff < 300:
                    time_bin = 3

            count_bin = 0
            if state.message_count > 50:
                count_bin = 3
            elif state.message_count > 20:
                count_bin = 2
            elif state.message_count > 5:
                count_bin = 1

            rl_state = (sentiment_bin, time_bin, count_bin)

            # Fetch current affinity
            current_affinity = 0.0
            chat_cog = self.bot.get_cog("ChatCog")
            if chat_cog and hasattr(chat_cog, "user_profiles"):
                try:
                    profile = await chat_cog.user_profiles.load_profile(user_id)
                    current_affinity = profile.get("affection", {}).get("level", 0.0)
                except Exception as e:
                    logger.warning(f"Failed to load profile for affinity: {e}")

            if last_ctx:
                # Handle migration/backward compatibility for reward context
                if len(last_ctx) == 4:
                    prev_action, prev_state, prev_sentiment, last_time = last_ctx
                    prev_affinity = current_affinity  # Assume no change if no history
                else:
                    (
                        prev_action,
                        prev_state,
                        prev_sentiment,
                        prev_affinity,
                        last_time,
                    ) = last_ctx

                # Calculate latency
                latency = (now - last_time).total_seconds()

                # Calculate affinity delta
                affinity_delta = current_affinity - prev_affinity

                reward = await self.rl_service.calculate_reward(
                    channel_id,
                    user_id,
                    message,
                    state,
                    prev_action,
                    prev_sentiment,
                    latency=latency,
                    affinity_delta=affinity_delta,
                )

                await self.rl_service.update_agent(
                    channel_id,
                    user_id,
                    prev_state,
                    prev_action,
                    reward,
                    rl_state,
                )

            action, _ = await self.rl_service.get_action(channel_id, user_id, rl_state)

            result = None
            if action == RLAction.WAIT:
                result = None
            elif action == RLAction.REACT:
                reaction = await self._decide_reaction(context, state)
                if reaction:
                    result = {
                        "should_respond": False,
                        "reaction": reaction,
                        "reply": None,
                        "reason": "rl_react",
                        "mood": state.mood_state,
                        "mood_intensity": state.mood_intensity,
                        "context_type": context_type,
                        "topics": topics,
                    }
            elif action == RLAction.ENGAGE:
                reply = await self._decide_proactive_engagement(
                    context, state, topics, force=False
                )
                if reply:
                    result = {
                        "should_respond": True,
                        "reaction": None,
                        "reply": reply,
                        "reason": "rl_engage",
                        "mood": state.mood_state,
                        "mood_intensity": state.mood_intensity,
                        "context_type": context_type,
                        "topics": topics,
                    }
            elif action == RLAction.INITIATE:
                reply = await self._decide_proactive_engagement(
                    context, state, topics, force=True
                )
                if reply:
                    result = {
                        "should_respond": True,
                        "reaction": None,
                        "reply": reply,
                        "reason": "rl_initiate",
                        "mood": state.mood_state,
                        "mood_intensity": state.mood_intensity,
                        "context_type": context_type,
                        "topics": topics,
                    }

            self.reward_context[ctx_key] = (
                action,
                rl_state,
                current_sentiment,
                current_affinity,
                now,
            )

            if random.random() < 0.05:
                cutoff = now.timestamp() - 3600
                keys_to_remove = [
                    k
                    for k, v in self.reward_context.items()
                    if v[-1].timestamp() < cutoff
                ]
                for k in keys_to_remove:
                    del self.reward_context[k]

            return result

        # 4. Decision: React?
        reaction_emoji = await self._decide_reaction(context, state)

        # 5. Decision: Proactive Reply? (Jump in)
        # Only if not mentioned (handled by ChatCog) and not a reply to bot
        engagement = None
        is_reply_to_bot = False
        if user.metadata.get("is_reply_to_bot", False):
            is_reply_to_bot = True

        if not user.metadata.get("mentions_bot", False) and not is_reply_to_bot:
            engagement = await self._decide_proactive_engagement(context, state, topics)

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

    async def handle_message(
        self, message: Any, persona: Optional[Any] = None
    ) -> Optional[Dict]:
        """
        Compatibility wrapper for processing Discord messages.
        Converts Discord message to AcoreContext and calls process_message.

        Args:
            message: Discord Message object
            persona: Optional specific persona to use

        Returns:
            Dict containing action directives or None
        """
        try:
            import discord

            if not isinstance(message, discord.Message):
                logger.warning(
                    f"handle_message received non-Discord message: {type(message)}"
                )
                return None

            # Convert Discord message to AcoreContext
            from core.types import AcoreMessage, AcoreUser, AcoreChannel, AcoreContext

            # Create AcoreMessage
            acore_message = AcoreMessage(
                text=message.content or "",
                author_id=str(message.author.id),
                channel_id=str(message.channel.id),
                timestamp=message.created_at,
            )

            # Create AcoreUser
            acore_user = AcoreUser(
                id=str(message.author.id),
                display_name=message.author.display_name,
                metadata={
                    "username": message.author.name,
                    "is_bot": message.author.bot,
                },
            )

            # Create AcoreChannel
            channel_type = "text"
            if isinstance(message.channel, discord.DMChannel):
                channel_type = "dm"
            elif isinstance(message.channel, discord.Thread):
                channel_type = "thread"

            acore_channel = AcoreChannel(
                id=str(message.channel.id),
                name=getattr(message.channel, "name", "dm"),
                type=channel_type,
            )

            # Create AcoreContext with a reply callback
            async def reply_callback(text: str) -> None:
                await message.channel.send(text)

            context = AcoreContext(
                message=acore_message,
                channel=acore_channel,
                user=acore_user,
                reply_callback=reply_callback,
            )

            # Call the main process_message method
            return await self.process_message(context, persona)

        except ImportError:
            logger.error("Discord not available for handle_message")
            return None
        except Exception as e:
            logger.error(f"Error in handle_message: {e}")
            return None

    async def _update_mood(self, context: AcoreContext, state: BehaviorState):
        """
        Update mood state based on message sentiment and context.

        Mood transitions are gradual (max 0.1 shift per message) and influenced by:
        - Message sentiment (positive/negative)
        - User tone (excited, frustrated, etc.)
        - Time decay (moods fade to neutral over 30 min)
        """
        now = datetime.now()
        message = context.message
        user = context.user
        channel = context.channel

        # Time decay: Moods fade to neutral over time (30 min = 1800 seconds)
        time_since_update = (now - state.last_mood_update).total_seconds()
        if time_since_update > 1800:  # 30 minutes
            # Decay toward neutral
            if state.mood_state != "neutral":
                state.mood_intensity = max(0.0, state.mood_intensity - 0.2)
                if state.mood_intensity < 0.3:
                    state.mood_state = "neutral"
                    state.mood_intensity = 0.5
                    logger.debug(f"Mood decayed to neutral in channel {channel.id}")

        # Simple sentiment analysis based on keywords and patterns
        content = message.text.lower()
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
                    f"Mood changed from {old_mood} to {target_mood} (intensity: {target_intensity:.2f}) in channel {channel.id}"
                )
        else:
            # Same mood, adjust intensity gradually
            intensity_diff = target_intensity - state.mood_intensity
            state.mood_intensity += max(-0.1, min(0.1, intensity_diff))
            state.mood_intensity = max(0.0, min(1.0, state.mood_intensity))

        state.last_mood_update = now

        # T21-T22: Track user sentiment for emotional contagion
        # Only track sentiment from actual users (not bots/webhooks)
        if not user.metadata.get("is_bot", False) and not user.metadata.get(
            "is_webhook", False
        ):
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
                self.proactive_interval_min * adaptive_thresholds["cooldown_multiplier"]
            )

            # Only allow ambient message after adaptive cooldown
            if time_since_last_ambient > max(
                adaptive_cooldown, 21600
            ):  # At least 6 hours
                # T11: Apply adaptive chance modifier
                base_chance = getattr(
                    Config, "BEHAVIOR_PROACTIVE_PROBABILITY", 0.6
                )  # base proactive chance
                adaptive_chance = max(
                    0.05, min(0.8, base_chance + adaptive_thresholds["chance_modifier"])
                )

                if random.random() < adaptive_chance:
                    channel = self.bot.get_channel(channel_id)
                    if channel and hasattr(channel, "history"):
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
                                        if (
                                            getattr(msg.author, "bot", False)
                                            or getattr(msg, "webhook_id", None)
                                        )
                                        else "HUMAN"
                                    )
                                    author_name = getattr(
                                        msg.author, "display_name", str(msg.author)
                                    )
                                    content = getattr(msg, "content", str(msg))[:100]
                                    history_summary.append(
                                        f"[{author_type}] {author_name}: {content}"
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
                                    channel_name = getattr(
                                        channel, "name", str(channel_id)
                                    )
                                    logger.info(
                                        f"AI decided NOT to send ambient message in {channel_name} (spam prevention)"
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
                                    not getattr(m.author, "bot", False)
                                    and not getattr(m, "webhook_id", None)
                                    for m in recent_msgs_fallback[:5]
                                )
                                if not human_found:
                                    return
                            except Exception:
                                return

                        # Select a rotating persona for variety
                        selected_persona = self._select_next_persona_rotating()
                        acore_channel = AcoreChannel(
                            id=str(channel_id),
                            name=getattr(channel, "name", str(channel_id)),
                            type="text",
                        )
                        msg = await self._generate_ambient_thought(
                            acore_channel, state, selected_persona
                        )
                        if msg:
                            # Send via bot channel
                            await channel.send(msg)
                            state.last_ambient_trigger = now
                            channel_name = getattr(channel, "name", str(channel_id))
                            logger.info(
                                f"Sent ambient lull message in {channel_name} as {selected_persona.character.display_name} (adaptive: silence={silence_duration:.0f}s, chance={adaptive_chance:.2f})"
                            )

    async def _send_as_persona(self, reply_callback, message: str, persona=None):
        """Send a message via the provided reply callback as the specified persona.

        Args:
            reply_callback: A callable that sends the message (e.g., context.reply)
            message: The message content to send
            persona: Optional persona to use for the message
        """
        try:
            # Use provided persona, or fall back to internal state, then ChatCog
            if persona is None:
                persona = self.current_persona

            if not persona:
                chat_cog = self.bot.get_cog("ChatCog")
                if chat_cog:
                    persona = chat_cog.current_persona

            if not persona:
                await reply_callback(message)
                return

            await reply_callback(message)
        except Exception as e:
            logger.error(f"Failed to send message via callback: {e}")

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
        self, context: AcoreContext, state: BehaviorState
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
        content = context.message.text.lower()

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

        content = context.message.text.lower()
        if any(w in content for w in ["lol", "lmao", "haha"]):
            return "😂"
        if any(w in content for w in ["cool", "wow", "nice"]):
            return "🔥"
        if "?" in content:
            return "🤔"

        return None

    async def _decide_proactive_engagement(
        self,
        context: AcoreContext,
        state: BehaviorState,
        topics: Optional[List[str]] = None,
        force: bool = False,
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
            not force
            and (datetime.now() - state.last_proactive_trigger).total_seconds()
            < self.proactive_cooldown
        ):
            return None

        # T9: Check topic-based engagement first (highest priority)
        if topics:
            topic_decision = await self._should_engage_by_topics(topics)
            if topic_decision["should_engage"] is False and not force:
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
        followup = await self._check_followup_opportunity(context, state)
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
        if not force and random.random() > (base_chance + total_modifier):
            return None

        # 3. Check Interest (LLM Fast Path)
        # We ask the LLM: "Is [Character] interested in this?"
        if not self.current_persona:
            return None

        # Include mood in the decision prompt
        mood_context = (
            f"Current mood: {state.mood_state} (intensity: {state.mood_intensity:.1f})"
        )

        prompt = f"""Message: "{context.message.text}"
{mood_context}

As {self.current_persona.character.display_name}, is this a topic you would excitedly jump into?
Reply YES or NO."""

        try:
            res = await self.ollama.generate(prompt)
            if "YES" in res.upper():
                # Generate actual reply with mood context
                mood_instruction = self._get_mood_instruction(state)
                reply_prompt = f"""User said: "{context.message.text}"

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
        self, context: AcoreContext, state: BehaviorState
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
        topics = await self._detect_interesting_topics(context.message.text)
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
        question = await self._generate_followup_question(topic, context.message.text)

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
                f"Asked follow-up question about '{topic}' in channel {context.channel.id}"
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
        self, channel, state: BehaviorState, persona=None
    ) -> Optional[str]:
        """
        Generate a random thought or callback.

        Mood affects the type of ambient message:
        - excited: More energetic, might share something interesting
        - sad: More melancholic or contemplative
        - bored: Explicitly looking for engagement
        - curious: Ask questions or bring up interesting topics
        """
        # Use provided persona or fall back to current
        active_persona = persona or self.current_persona
        if not active_persona:
            return None

        # Include mood context in ambient thoughts
        mood_context = (
            f"Current mood: {state.mood_state} (intensity: {state.mood_intensity:.1f})"
        )
        mood_instruction = self._get_mood_instruction(state)

        # Expanded topic categories for variety
        topic_categories = [
            "a hot take on something controversial",
            "a random observation about life",
            "something you're currently interested in",
            "a question to spark conversation",
            "a funny anecdote or story",
            "your opinion on a current topic",
            "something nostalgic from your past",
            "a philosophical musing",
            "a comment on the server or channel",
            "something completely random and unexpected",
        ]

        # Randomly select a topic category
        selected_topic = random.choice(topic_categories)

        # Decide between random thought or callback
        prompt = f"""You are {active_persona.character.display_name} hanging out in #{channel.name}. It's been quiet for a while.

{mood_context}
{mood_instruction}

Say something to break the silence about {selected_topic}. It could be:
1. A random thought based on your personality and current mood.
2. A callback to a recent topic (if you remember one).
3. {selected_topic}.

Keep it conversational, in character, and short (1-2 sentences max)."""

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
