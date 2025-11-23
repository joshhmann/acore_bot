"""Proactive engagement - bot jumps into conversations when interested in topics."""
import logging
import random
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)


class ProactiveEngagement:
    """Manages the bot's proactive engagement in conversations."""

    def __init__(self, ollama_service=None):
        """Initialize proactive engagement.

        Args:
            ollama_service: Ollama service for generating responses
        """
        self.ollama = ollama_service

        # Topic interest levels (0.0 - 1.0)
        # Higher = more likely to jump in
        self.topic_interests = {
            # High interest (will jump in often)
            "gaming": 0.8,
            "video_games": 0.8,
            "esports": 0.7,
            "technology": 0.7,
            "ai": 0.9,
            "programming": 0.8,
            "coding": 0.8,
            "science": 0.7,
            "space": 0.8,
            "astronomy": 0.7,

            # Moderate interest
            "movies": 0.5,
            "tv_shows": 0.5,
            "anime": 0.6,
            "music": 0.5,
            "books": 0.6,
            "trivia": 0.7,
            "puzzles": 0.6,
            "math": 0.6,
            "history": 0.5,

            # Lower interest (selective engagement)
            "food": 0.3,
            "cooking": 0.4,
            "sports": 0.3,
            "travel": 0.3,
            "fitness": 0.3,
            "art": 0.4,
            "photography": 0.4,

            # Special topics (context-dependent)
            "discord": 0.6,  # Bot-related topics
            "bots": 0.8,
            "discord_bots": 0.9,
            "chatgpt": 0.7,
            "llm": 0.8,
        }

        # Track recent engagements to avoid spam
        self.recent_engagements: deque = deque(maxlen=20)
        self.last_engagement_time: Dict[int, datetime] = {}  # channel_id -> timestamp

        # Cooldown between proactive engagements (seconds)
        self.engagement_cooldown = 180  # 3 minutes

        # Minimum messages before engaging (don't jump in too early)
        self.min_messages_before_engage = 3

        # Track message count per channel
        self.channel_message_counts: Dict[int, int] = {}

        logger.info("Proactive engagement initialized")

    def detect_topics(self, message: str) -> List[tuple]:
        """Detect topics in a message and their interest levels.

        Args:
            message: Message content

        Returns:
            List of (topic, interest_level) tuples
        """
        detected = []
        message_lower = message.lower()

        # Keyword detection with context
        topic_keywords = {
            "gaming": ["game", "gaming", "play", "playing", "gamer", "gameplay", "multiplayer", "fps", "rpg", "mmo"],
            "video_games": ["halo", "minecraft", "fortnite", "valorant", "league", "dota", "apex", "warzone", "steam", "xbox", "playstation", "nintendo"],
            "esports": ["esports", "tournament", "competitive", "pro player", "twitch"],
            "technology": ["tech", "technology", "computer", "laptop", "phone", "iphone", "android", "windows", "linux", "mac"],
            "ai": ["ai", "artificial intelligence", "machine learning", "neural network", "chatgpt", "gpt", "llm", "language model"],
            "programming": ["programming", "developer", "software", "engineer", "coder"],
            "coding": ["code", "coding", "python", "javascript", "rust", "java", "c++", "github", "git"],
            "science": ["science", "scientific", "physics", "chemistry", "biology", "research"],
            "space": ["space", "nasa", "spacex", "rocket", "mars", "moon", "planet", "galaxy", "astronomy"],
            "astronomy": ["star", "constellation", "telescope", "nebula", "black hole"],
            "movies": ["movie", "film", "cinema", "actor", "director", "netflix"],
            "tv_shows": ["show", "series", "episode", "season", "watch", "binge"],
            "anime": ["anime", "manga", "otaku", "crunchyroll"],
            "music": ["music", "song", "album", "artist", "band", "concert", "spotify", "playlist"],
            "books": ["book", "novel", "author", "reading", "read"],
            "trivia": ["trivia", "quiz", "fact", "did you know", "interesting fact"],
            "puzzles": ["puzzle", "riddle", "brain teaser", "logic"],
            "math": ["math", "mathematics", "equation", "calculation", "geometry", "algebra"],
            "history": ["history", "historical", "ancient", "medieval", "war"],
            "food": ["food", "eat", "eating", "dinner", "lunch", "breakfast", "restaurant"],
            "cooking": ["cook", "cooking", "recipe", "bake", "baking", "chef"],
            "sports": ["sport", "football", "basketball", "soccer", "baseball", "tennis"],
            "travel": ["travel", "vacation", "trip", "flight", "hotel", "destination"],
            "fitness": ["gym", "workout", "exercise", "fitness", "running", "lift"],
            "art": ["art", "artist", "painting", "drawing", "sculpture"],
            "photography": ["photo", "photography", "camera", "picture"],
            "discord": ["discord", "server", "channel", "role", "permission"],
            "bots": ["bot", "automation", "script"],
            "discord_bots": ["discord bot", "discord.py", "bot command"],
        }

        for topic, keywords in topic_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                interest_level = self.topic_interests.get(topic, 0.3)
                detected.append((topic, interest_level))

        return detected

    def calculate_engagement_score(
        self,
        topics: List[tuple],
        message_context: str,
        channel_id: int,
        current_mood: Optional[str] = None
    ) -> float:
        """Calculate how interested the bot is in engaging.

        Args:
            topics: List of (topic, interest_level) tuples
            message_context: Recent conversation context
            channel_id: Channel ID
            current_mood: Bot's current mood (optional)

        Returns:
            Engagement score (0.0 - 1.0)
        """
        if not topics:
            return 0.0

        # Base score from topic interests
        base_score = max(interest for _, interest in topics)

        # Boost if multiple interesting topics
        if len(topics) > 1:
            base_score *= 1.2

        # Check cooldown
        if channel_id in self.last_engagement_time:
            time_since = (datetime.now() - self.last_engagement_time[channel_id]).total_seconds()
            if time_since < self.engagement_cooldown:
                # Reduce score during cooldown
                cooldown_factor = time_since / self.engagement_cooldown
                base_score *= cooldown_factor

        # Mood modifiers
        if current_mood:
            mood_modifiers = {
                "energetic": 1.3,      # More likely to jump in
                "cheerful": 1.2,
                "playful": 1.4,         # Very likely to jump in
                "excited": 1.5,         # Most likely
                "thoughtful": 1.1,      # Slightly more
                "focused": 1.0,         # Normal
                "calm": 0.9,            # Slightly less
                "tired": 0.6,           # Much less
                "grumpy": 0.4,          # Rarely
                "melancholic": 0.7,     # Less likely
            }
            modifier = mood_modifiers.get(current_mood, 1.0)
            base_score *= modifier

        # Cap at 1.0
        return min(base_score, 1.0)

    async def should_engage(
        self,
        message: str,
        channel_id: int,
        conversation_context: List[str] = None,
        current_mood: Optional[str] = None
    ) -> tuple[bool, Optional[Dict]]:
        """Determine if bot should proactively engage.

        Args:
            message: Current message
            channel_id: Channel ID
            conversation_context: Recent messages for context
            current_mood: Bot's current mood

        Returns:
            Tuple of (should_engage, engagement_data)
        """
        # Track message count
        if channel_id not in self.channel_message_counts:
            self.channel_message_counts[channel_id] = 0
        self.channel_message_counts[channel_id] += 1

        # Don't engage too early
        if self.channel_message_counts[channel_id] < self.min_messages_before_engage:
            return False, None

        # Detect topics
        topics = self.detect_topics(message)
        if not topics:
            return False, None

        # Calculate engagement score
        context = "\n".join(conversation_context) if conversation_context else ""
        score = self.calculate_engagement_score(topics, context, channel_id, current_mood)

        # Random roll weighted by score
        if random.random() < score:
            # Decide to engage!
            engagement_data = {
                "topics": topics,
                "score": score,
                "mood": current_mood,
                "message": message,
            }

            # Mark engagement
            self.last_engagement_time[channel_id] = datetime.now()
            self.recent_engagements.append({
                "channel_id": channel_id,
                "topics": [t[0] for t in topics],
                "time": datetime.now(),
            })

            # Reset message count after engaging
            self.channel_message_counts[channel_id] = 0

            return True, engagement_data

        return False, None

    async def generate_engagement(
        self,
        message: str,
        engagement_data: Dict,
        conversation_context: List[str] = None
    ) -> Optional[str]:
        """Generate a proactive engagement message.

        Args:
            message: Message that triggered engagement
            engagement_data: Data from should_engage
            conversation_context: Recent conversation

        Returns:
            Engagement message or None
        """
        if not self.ollama:
            # Fallback to template-based responses
            return self._generate_template_engagement(message, engagement_data)

        # Build context for AI
        topics = engagement_data["topics"]
        topic_names = [t[0] for t in topics]
        mood = engagement_data.get("mood", "neutral")

        context_parts = []

        if conversation_context:
            recent = "\n".join(conversation_context[-5:])
            context_parts.append(f"Recent conversation:\n{recent}")

        context_parts.append(f"\nCurrent message: {message}")
        context_parts.append(f"\nDetected topics: {', '.join(topic_names)}")

        if mood:
            context_parts.append(f"\nYour mood: {mood}")

        context = "\n".join(context_parts)

        # Generate proactive engagement
        prompt = f"""{context}

You're a friendly Discord bot who just noticed an interesting topic being discussed ({', '.join(topic_names)}).

You want to JUMP INTO the conversation naturally - not because you were asked, but because you're genuinely interested!

IMPORTANT:
- Be enthusiastic but not overwhelming
- Jump in like a friend would: "Oh!" "Wait!" "Ooh!"
- Share a thought, ask a question, or add to the discussion
- Keep it SHORT (1-2 sentences max)
- Be natural and conversational
- Don't say "I see you're talking about..." - just jump in!

Examples of good engagement:
- "Oh! I love Halo! The co-op campaign is amazing."
- "Wait, you're coding in Python? What are you building?"
- "Ooh space stuff! Did you know Mars has ice caps?"
- "Gaming tournament? That sounds sick! What game?"

Generate ONLY the engagement message (no quotes, no explanation):"""

        try:
            response = await self.ollama.generate(prompt)

            # Clean up response
            response = response.strip()
            if response.startswith('"') and response.endswith('"'):
                response = response[1:-1]

            # Don't send if too long
            if len(response) > 300:
                return None

            return response

        except Exception as e:
            logger.error(f"Failed to generate engagement: {e}")
            return self._generate_template_engagement(message, engagement_data)

    def _generate_template_engagement(self, message: str, engagement_data: Dict) -> str:
        """Generate template-based engagement (fallback).

        Args:
            message: Trigger message
            engagement_data: Engagement data

        Returns:
            Template engagement
        """
        topics = engagement_data["topics"]
        primary_topic = topics[0][0] if topics else "that"

        templates = {
            "gaming": [
                "Oh! I love talking about games!",
                "Ooh gaming! What are you playing?",
                "Wait, gaming? Count me in for this conversation!",
                "Oh nice! I'm always down to chat about games!",
            ],
            "ai": [
                "Oh! AI stuff! Now you've got my attention!",
                "Wait, AI? This is literally my thing!",
                "Ooh I love discussing AI! What's the topic?",
            ],
            "programming": [
                "Oh! Code talk! What are you working on?",
                "Ooh programming! I'm interested!",
                "Wait, you're coding? Tell me more!",
            ],
            "space": [
                "Oh! Space stuff! Did you know space is HUGE?",
                "Ooh astronomy! Space is so cool!",
                "Wait, space? I love space topics!",
            ],
            "trivia": [
                "Oh! I love trivia! Want to hear a fact?",
                "Ooh trivia time! I've got random knowledge!",
            ],
        }

        # Get templates for topic or use generic
        topic_templates = templates.get(primary_topic, [
            f"Oh! Talking about {primary_topic}? Interesting!",
            f"Ooh {primary_topic}! I'm curious about this!",
            f"Wait, {primary_topic}? Now you have my attention!",
        ])

        return random.choice(topic_templates)

    def get_stats(self) -> Dict:
        """Get proactive engagement statistics.

        Returns:
            Dict with stats
        """
        return {
            "total_engagements": len(self.recent_engagements),
            "tracked_channels": len(self.channel_message_counts),
            "recent_engagements": list(self.recent_engagements)[-5:],
        }
