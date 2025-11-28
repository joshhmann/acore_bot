"""Ambient conversation mode - bot chimes in naturally without being prompted."""
import logging
import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from collections import deque

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class ChannelState:
    """Tracks state for ambient mode in a channel."""
    last_message_time: datetime = field(default_factory=datetime.now)
    last_ambient_time: datetime = field(default_factory=lambda: datetime.now() - timedelta(hours=1))
    message_count: int = 0
    recent_topics: deque = field(default_factory=lambda: deque(maxlen=10))
    recent_users: deque = field(default_factory=lambda: deque(maxlen=5))
    greeted_today: bool = False
    last_greeting_date: Optional[str] = None


class AmbientMode:
    """Manages ambient/proactive bot responses."""

    def __init__(self, bot, ollama_service, persona_system=None, compiled_persona=None, callbacks_system=None):
        """Initialize ambient mode.

        Args:
            bot: Discord bot instance
            ollama_service: Ollama service for generating responses
            persona_system: AI-First PersonaSystem (optional)
            compiled_persona: Current compiled persona (optional)
            callbacks_system: ProactiveCallbacksSystem for topic memory (optional)
        """
        self.bot = bot
        self.ollama = ollama_service
        self.persona_system = persona_system
        self.compiled_persona = compiled_persona
        self.callbacks_system = callbacks_system
        self.channel_states: Dict[int, ChannelState] = {}
        self.running = False
        self._task = None

        # Proactive engagement
        try:
            from services.proactive_engagement import ProactiveEngagement
            self.proactive = ProactiveEngagement(ollama_service)
            logger.info("Proactive engagement initialized")
        except Exception as e:
            logger.warning(f"Could not load proactive engagement: {e}")
            self.proactive = None

        # Ambient triggers configuration
        self.lull_timeout = Config.AMBIENT_LULL_TIMEOUT  # seconds before considering it a lull
        self.min_ambient_interval = Config.AMBIENT_MIN_INTERVAL * 2  # Double the interval (less frequent)
        self.ambient_chance = Config.AMBIENT_CHANCE * 0.5  # Halve the chance (less spammy)

        # Keyword triggers - topics that might prompt a comment
        self.interest_keywords = [
            "game", "gaming", "playing", "stream", "streaming",
            "music", "song", "album", "artist",
            "movie", "film", "show", "series", "anime",
            "food", "eating", "dinner", "lunch", "breakfast",
            "code", "coding", "programming", "bug", "error",
            "tired", "sleepy", "exhausted", "energetic",
            "weekend", "friday", "party",
        ]

        # Time-based greetings
        self.greeting_hours = {
            "morning": (6, 11),
            "afternoon": (12, 17),
            "evening": (18, 21),
            "night": (22, 5),
        }
        
        # User callout tracking
        self.last_callout_time = datetime.now() - timedelta(hours=1)

        logger.info("Ambient mode initialized")

    def get_state(self, channel_id: int) -> ChannelState:
        """Get or create channel state.

        Args:
            channel_id: Discord channel ID

        Returns:
            ChannelState for the channel
        """
        if channel_id not in self.channel_states:
            self.channel_states[channel_id] = ChannelState()
        return self.channel_states[channel_id]

    async def start(self):
        """Start the ambient mode background task."""
        if self.running:
            return

        self.running = True
        self._task = asyncio.create_task(self._ambient_loop())
        logger.info("Ambient mode started")

    async def stop(self):
        """Stop the ambient mode background task."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Ambient mode stopped")

    async def on_message(self, message, mood=None):
        """Track message activity for ambient triggers.

        Args:
            message: Discord message
            mood: Current bot mood (optional)
        """
        if message.author.bot:
            return None

        # Ignore specific users
        if message.author.id in Config.AMBIENT_IGNORE_USERS:
            return None

        # Only track messages in configured ambient channels
        if Config.AMBIENT_CHANNELS and message.channel.id not in Config.AMBIENT_CHANNELS:
            return None

        # Ignore activity when music is playing
        if message.guild and message.guild.voice_client:
            voice_client = message.guild.voice_client
            if voice_client.is_playing() or voice_client.is_paused():
                return None

        state = self.get_state(message.channel.id)
        state.last_message_time = datetime.now()
        state.message_count += 1

        # Track recent users
        if message.author.name not in state.recent_users:
            state.recent_users.append(message.author.name)

        # Extract potential topics from message
        content_lower = message.content.lower()
        for keyword in self.interest_keywords:
            if keyword in content_lower:
                state.recent_topics.append(keyword)

        # Check for proactive engagement (NEW!)
        if self.proactive and Config.PROACTIVE_ENGAGEMENT_ENABLED:
            # Build recent conversation context
            recent_context = [
                f"{user}: {topic}"
                for user, topic in zip(list(state.recent_users)[-3:], list(state.recent_topics)[-3:])
            ]

            # Check if bot should jump in
            should_engage, engagement_data = await self.proactive.should_engage(
                message=message.content,
                channel_id=message.channel.id,
                conversation_context=recent_context,
                current_mood=mood
            )

            if should_engage:
                # Generate engagement
                engagement = await self.proactive.generate_engagement(
                    message=message.content,
                    engagement_data=engagement_data,
                    conversation_context=recent_context
                )

                if engagement:
                    logger.info(f"Proactive engagement triggered in {message.channel.name}: {engagement[:50]}...")
                    return engagement  # Return the message to send

        # Check for greeting opportunity
        await self._check_greeting_trigger(message.channel, state)
        return None

    async def _ambient_loop(self):
        """Main loop for checking ambient triggers."""
        while self.running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                for channel_id, state in list(self.channel_states.items()):
                    await self._check_ambient_triggers(channel_id, state)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in ambient loop: {e}")
                await asyncio.sleep(60)

    async def _check_ambient_triggers(self, channel_id: int, state: ChannelState):
        """Check if we should send an ambient message.

        Args:
            channel_id: Discord channel ID
            state: Channel state
        """
        now = datetime.now()

        # Don't trigger too frequently
        if (now - state.last_ambient_time).total_seconds() < self.min_ambient_interval:
            return

        # Check if music is playing (don't interrupt music)
        channel = self.bot.get_channel(channel_id)
        if channel and hasattr(channel, 'guild') and channel.guild:
            voice_client = channel.guild.voice_client
            if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
                return

        # Check for conversation lull
        time_since_message = (now - state.last_message_time).total_seconds()

        if time_since_message > self.lull_timeout and time_since_message < self.lull_timeout * 3:
            # There's been a lull but not too long ago

            # 15% chance for proactive callback (bring up past topic)
            if random.random() < 0.15 and self.callbacks_system:
                if channel:
                    # Get a topic memory to bring up
                    topic_memory = self.callbacks_system.get_callback_candidate(channel.id)
                    if topic_memory:
                        callback_msg = await self._generate_callback_message(channel.id, topic_memory)
                        if callback_msg:
                            await channel.send(callback_msg)
                            state.last_ambient_time = now
                            logger.info(f"Sent proactive callback: {callback_msg[:50]}...")
                            return

            # 10% chance for random thought (character-aware)
            if random.random() < 0.1:
                if channel:
                    thought = await self._generate_random_thought()
                    if thought:
                        await channel.send(thought)
                        state.last_ambient_time = now
                        logger.info(f"Sent character-aware random thought: {thought[:50]}...")
                    return

            # 5% chance for user callout (character-aware)
            if random.random() < 0.05 and (now - self.last_callout_time).total_seconds() > 600:
                if channel and state.recent_users:
                    user_name = random.choice(list(state.recent_users))
                    callout = await self._generate_user_callout(user_name)
                    if callout:
                        await channel.send(callout)
                        state.last_ambient_time = now
                        self.last_callout_time = now
                        logger.info(f"Sent character-aware callout: {callout}")
                    return

            # Regular lull message
            if random.random() < self.ambient_chance:
                if channel:
                    await self._send_ambient_message(channel, state, "lull")
                    state.last_ambient_time = now

    async def _generate_random_thought(self) -> Optional[str]:
        """Generate a character-aware random thought.

        Returns:
            Random thought string or None
        """
        try:
            # Use persona system if available
            if self.compiled_persona:
                system_prompt = self.compiled_persona.system_prompt
                character_name = self.compiled_persona.character.display_name
            else:
                # Fallback to generic
                system_prompt = "You are a friendly Discord bot."
                character_name = "Bot"

            prompt = f"""{system_prompt}

Generate a brief, spontaneous random thought or observation that you might share during a quiet moment in chat.
This should be:
- In character
- 1-2 sentences maximum
- About anything on your mind (your interests, observations, existential thoughts, etc.)
- Natural and conversational
- NOT a question or conversation starter

Just the thought itself, nothing else:"""

            response = await self.ollama.generate(prompt)

            if response and len(response.strip()) > 0:
                from utils.response_validator import ResponseValidator
                message = ResponseValidator.clean_thinking_process(response.strip())
                # Clean up quotes
                if message.startswith('"') and message.endswith('"'):
                    message = message[1:-1]

                # Validate length
                if 10 < len(message) < 300:
                    return message

        except Exception as e:
            logger.error(f"Failed to generate random thought: {e}")

        return None

    async def _generate_user_callout(self, user_name: str) -> Optional[str]:
        """Generate a character-aware callout for a user.

        Args:
            user_name: Username to call out

        Returns:
            Callout message or None
        """
        try:
            # Use persona system if available
            if self.compiled_persona:
                system_prompt = self.compiled_persona.system_prompt
            else:
                system_prompt = "You are a friendly Discord bot."

            prompt = f"""{system_prompt}

Generate a brief, playful callout directed at the user "{user_name}".
This should be:
- In character
- 1 sentence maximum
- Teasing, playful, or acknowledging their presence
- Natural and conversational
- NOT mean-spirited (keep it friendly)

Just the callout message, nothing else:"""

            response = await self.ollama.generate(prompt)

            if response and len(response.strip()) > 0:
                from utils.response_validator import ResponseValidator
                message = ResponseValidator.clean_thinking_process(response.strip())
                # Clean up quotes
                if message.startswith('"') and message.endswith('"'):
                    message = message[1:-1]

                # Validate length
                if 10 < len(message) < 200:
                    return message

        except Exception as e:
            logger.error(f"Failed to generate user callout: {e}")

        return None

    async def _generate_callback_message(self, channel_id: int, topic_memory) -> Optional[str]:
        """Generate a callback message bringing up a past topic.

        Args:
            channel_id: Discord channel ID
            topic_memory: TopicMemory to bring up

        Returns:
            Callback message or None
        """
        if not topic_memory:
            return None

        try:
            # Use persona system if available
            if self.compiled_persona:
                system_prompt = self.compiled_persona.system_prompt
            else:
                system_prompt = "You are a friendly Discord bot."

            # Format time ago
            from datetime import datetime
            time_ago = datetime.now() - topic_memory.timestamp
            if time_ago.days > 0:
                time_str = f"{time_ago.days} day{'s' if time_ago.days != 1 else ''} ago"
            else:
                hours = time_ago.seconds // 3600
                if hours > 0:
                    time_str = f"{hours} hour{'s' if hours != 1 else ''} ago"
                else:
                    time_str = "earlier"

            prompt = f"""{system_prompt}

You're bringing up a past topic from a conversation that happened {time_str}.

Topic: {topic_memory.topic}
Context: {topic_memory.context}
Users involved: {', '.join(topic_memory.users)}
Sentiment: {topic_memory.sentiment}

Generate a natural, casual message that brings this topic back up. This could be:
- Asking for an update ("Hey, whatever happened with...")
- Sharing a related thought ("I was thinking about when you mentioned...")
- Making a callback reference ("Remember when we were talking about...")
- Expressing curiosity ("Still curious about...")

Keep it:
- Short (1-2 sentences)
- In character
- Natural and conversational
- Not forced

Just the callback message, nothing else:"""

            response = await self.ollama.generate(prompt)

            if response and len(response.strip()) > 0:
                from utils.response_validator import ResponseValidator
                message = ResponseValidator.clean_thinking_process(response.strip())
                # Clean up quotes
                if message.startswith('"') and message.endswith('"'):
                    message = message[1:-1]

                # Validate length
                if 10 < len(message) < 300:
                    # Mark as used
                    if self.callbacks_system:
                        self.callbacks_system.mark_callback_used(topic_memory)
                    return message

        except Exception as e:
            logger.error(f"Failed to generate callback message: {e}")

        return None

    async def _check_greeting_trigger(self, channel, state: ChannelState):
        """Check if we should send a time-based greeting.
        
        Args:
            channel: Discord channel
            state: Channel state
        """
        # DISABLED: Greetings break persona character
        # Ambient greetings generate generic friendly messages that don't match
        # the bot's persona (e.g., Dagoth Ur shouldn't say "Hey all! Nighty night!")
        return

        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        # Only greet once per day per channel
        if state.last_greeting_date == today:
            return

        # Check if enough time since last ambient
        if (now - state.last_ambient_time).total_seconds() < self.min_ambient_interval:
            return

        # Don't greet if music is playing
        if hasattr(channel, 'guild') and channel.guild:
            voice_client = channel.guild.voice_client
            if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
                return

        hour = now.hour

        # Determine time of day
        time_of_day = None
        for period, (start, end) in self.greeting_hours.items():
            if start <= end:
                if start <= hour <= end:
                    time_of_day = period
                    break
            else:  # Wraps around midnight
                if hour >= start or hour <= end:
                    time_of_day = period
                    break

        if time_of_day and random.random() < 0.3:  # 30% chance to greet
            # Set date immediately to prevent race conditions
            state.last_greeting_date = today
            state.last_ambient_time = now
            
            await self._send_ambient_message(channel, state, "greeting", time_of_day=time_of_day)

    async def _send_ambient_message(
        self,
        channel,
        state: ChannelState,
        trigger_type: str,
        **kwargs
    ):
        """Generate and send an ambient message.

        Args:
            channel: Discord channel to send to
            state: Channel state
            trigger_type: What triggered this message
            **kwargs: Additional context
        """
        try:
            # Use persona system if available
            if self.compiled_persona:
                system_prompt = self.compiled_persona.system_prompt
            else:
                system_prompt = "You are a friendly Discord bot."

            # Build context for the LLM
            context_parts = []

            if state.recent_topics:
                topics = list(state.recent_topics)[-5:]
                context_parts.append(f"Recent topics discussed: {', '.join(topics)}")

            if state.recent_users:
                users = list(state.recent_users)
                context_parts.append(f"Active users: {', '.join(users)}")

            context = "\n".join(context_parts) if context_parts else "General chat channel"

            # Build the prompt based on trigger type
            if trigger_type == "greeting":
                time_of_day = kwargs.get("time_of_day", "day")
                prompt = f"""{system_prompt}

Generate a casual, natural {time_of_day} greeting for the chat.
Keep it short (1-2 sentences), in character, and conversational.
Maybe reference the time of day or acknowledge the chat.

Context: {context}

Generate just the greeting message, nothing else:"""

            elif trigger_type == "lull":
                prompt = f"""{system_prompt}

The conversation has gone quiet for a bit.
Generate a casual comment to naturally re-engage the chat. This could be:
- A thought about something recently discussed
- A random interesting observation
- A gentle conversation starter
- A playful comment

Keep it short (1-2 sentences), natural, in character, and not forced.

Recent context: {context}

Generate just the message, nothing else:"""

            elif trigger_type == "topic":
                topic = kwargs.get("topic", "")
                prompt = f"""{system_prompt}

Someone just mentioned "{topic}" which you find interesting.
Generate a brief, natural reaction or comment about this topic.
Keep it casual, in character, and conversational (1-2 sentences).

Generate just the message, nothing else:"""

            else:
                prompt = f"""{system_prompt}

Generate a casual, natural comment for the chat.
Keep it short, in character, and conversational.

Context: {context}

Generate just the message, nothing else:"""

            # Generate the response
            response = await self.ollama.generate(prompt)

            if response and len(response.strip()) > 0:
                # Clean up the response
                from utils.response_validator import ResponseValidator
                message = ResponseValidator.clean_thinking_process(response.strip())

                # Remove quotes if the model wrapped it
                if message.startswith('"') and message.endswith('"'):
                    message = message[1:-1]

                # Don't send if too long or too short
                if 5 < len(message) < 500:
                    await channel.send(message)
                    logger.info(f"Sent ambient message ({trigger_type}): {message[:50]}...")

                    # Update dashboard
                    if hasattr(self.bot, 'web_dashboard'):
                        self.bot.web_dashboard.set_status("Ambient", f"Sent: {message[:30]}...")

        except Exception as e:
            logger.error(f"Failed to send ambient message: {e}")

    async def trigger_topic_reaction(self, channel, topic: str):
        """Manually trigger a reaction to a specific topic.

        Args:
            channel: Discord channel
            topic: Topic to react to
        """
        state = self.get_state(channel.id)

        # Check interval
        now = datetime.now()
        if (now - state.last_ambient_time).total_seconds() < self.min_ambient_interval / 2:
            return

        # Don't react if music is playing
        if hasattr(channel, 'guild') and channel.guild:
            voice_client = channel.guild.voice_client
            if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
                return

        if random.random() < 0.4:  # 40% chance to react to interesting topics
            await self._send_ambient_message(channel, state, "topic", topic=topic)
            state.last_ambient_time = now

    def set_channel_active(self, channel_id: int):
        """Mark a channel as having recent activity.

        Args:
            channel_id: Discord channel ID
        """
        state = self.get_state(channel_id)
        state.last_message_time = datetime.now()

    def get_stats(self) -> Dict[str, Any]:
        """Get ambient mode statistics.

        Returns:
            Dict with stats
        """
        return {
            "active_channels": len(self.channel_states),
            "running": self.running,
            "lull_timeout": self.lull_timeout,
            "min_interval": self.min_ambient_interval,
            "chance": self.ambient_chance,
        }
