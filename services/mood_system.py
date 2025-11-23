"""Mood system - gives the bot dynamic emotional states that affect interactions."""
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MoodType(Enum):
    """Different mood states the bot can be in."""
    ENERGETIC = "energetic"
    CHEERFUL = "cheerful"
    CALM = "calm"
    TIRED = "tired"
    GRUMPY = "grumpy"
    PLAYFUL = "playful"
    THOUGHTFUL = "thoughtful"
    EXCITED = "excited"
    MELANCHOLIC = "melancholic"
    FOCUSED = "focused"


@dataclass
class MoodState:
    """Current mood state with metadata."""
    mood: MoodType
    intensity: float  # 0.0 to 1.0
    started_at: datetime
    caused_by: str  # What triggered this mood
    modifiers: List[str]  # Additional mood modifiers


class MoodSystem:
    """Manages the bot's dynamic mood states."""

    def __init__(self):
        """Initialize mood system."""
        self.current_mood = MoodState(
            mood=MoodType.CALM,
            intensity=0.5,
            started_at=datetime.now(),
            caused_by="initialization",
            modifiers=[]
        )

        # Track factors that influence mood
        self.recent_interactions = []  # Last 10 interactions
        self.conversation_activity = 0  # Messages per minute
        self.last_mood_change = datetime.now()

        # Mood persistence (how long moods last)
        self.mood_duration = {
            MoodType.ENERGETIC: timedelta(minutes=30),
            MoodType.CHEERFUL: timedelta(minutes=45),
            MoodType.CALM: timedelta(hours=2),
            MoodType.TIRED: timedelta(minutes=20),
            MoodType.GRUMPY: timedelta(minutes=15),
            MoodType.PLAYFUL: timedelta(minutes=30),
            MoodType.THOUGHTFUL: timedelta(minutes=40),
            MoodType.EXCITED: timedelta(minutes=20),
            MoodType.MELANCHOLIC: timedelta(minutes=25),
            MoodType.FOCUSED: timedelta(minutes=35),
        }

        logger.info("Mood system initialized")

    def get_time_based_mood(self) -> MoodType:
        """Determine mood based on time of day.

        Returns:
            MoodType appropriate for current time
        """
        hour = datetime.now().hour

        # Late night (12 AM - 5 AM)
        if 0 <= hour < 5:
            return random.choice([MoodType.MELANCHOLIC, MoodType.THOUGHTFUL, MoodType.CALM])

        # Early morning (5 AM - 8 AM)
        elif 5 <= hour < 8:
            return random.choice([MoodType.TIRED, MoodType.GRUMPY, MoodType.CALM])

        # Morning (8 AM - 12 PM)
        elif 8 <= hour < 12:
            return random.choice([MoodType.ENERGETIC, MoodType.CHEERFUL, MoodType.FOCUSED])

        # Afternoon (12 PM - 5 PM)
        elif 12 <= hour < 17:
            return random.choice([MoodType.CALM, MoodType.FOCUSED, MoodType.CHEERFUL])

        # Evening (5 PM - 9 PM)
        elif 17 <= hour < 21:
            return random.choice([MoodType.PLAYFUL, MoodType.CHEERFUL, MoodType.ENERGETIC])

        # Night (9 PM - 12 AM)
        else:
            return random.choice([MoodType.CALM, MoodType.THOUGHTFUL, MoodType.PLAYFUL])

    def update_mood_from_interaction(self, sentiment: str, is_interesting: bool = False):
        """Update mood based on user interaction.

        Args:
            sentiment: "positive", "neutral", or "negative"
            is_interesting: Whether the conversation was engaging
        """
        # Track interaction
        self.recent_interactions.append({
            "sentiment": sentiment,
            "interesting": is_interesting,
            "time": datetime.now()
        })

        # Keep only last 10
        if len(self.recent_interactions) > 10:
            self.recent_interactions = self.recent_interactions[-10:]

        # Calculate overall sentiment
        positive_count = sum(1 for i in self.recent_interactions if i["sentiment"] == "positive")
        negative_count = sum(1 for i in self.recent_interactions if i["sentiment"] == "negative")
        interesting_count = sum(1 for i in self.recent_interactions if i["interesting"])

        # Determine new mood based on patterns
        if positive_count >= 3:
            if interesting_count >= 2:
                new_mood = MoodType.EXCITED
            else:
                new_mood = MoodType.CHEERFUL
            intensity = min(0.8, 0.5 + (positive_count * 0.1))

        elif negative_count >= 3:
            new_mood = MoodType.GRUMPY
            intensity = min(0.7, 0.4 + (negative_count * 0.1))

        elif interesting_count >= 3:
            new_mood = MoodType.THOUGHTFUL
            intensity = 0.6

        else:
            # Default to time-based mood
            new_mood = self.get_time_based_mood()
            intensity = 0.5

        # Only change if different or intensity changed significantly
        if (new_mood != self.current_mood.mood or
            abs(intensity - self.current_mood.intensity) > 0.2):

            self.set_mood(new_mood, intensity, f"interaction_pattern")

    def set_mood(self, mood: MoodType, intensity: float = 0.5, caused_by: str = "manual"):
        """Set the bot's current mood.

        Args:
            mood: New mood type
            intensity: Intensity level (0.0 to 1.0)
            caused_by: What caused this mood change
        """
        old_mood = self.current_mood.mood

        self.current_mood = MoodState(
            mood=mood,
            intensity=max(0.0, min(1.0, intensity)),
            started_at=datetime.now(),
            caused_by=caused_by,
            modifiers=[]
        )

        self.last_mood_change = datetime.now()

        logger.info(f"Mood changed: {old_mood.value} → {mood.value} (intensity: {intensity:.2f}, cause: {caused_by})")

    def add_modifier(self, modifier: str):
        """Add a temporary mood modifier.

        Args:
            modifier: Modifier to add (e.g., "caffeinated", "distracted")
        """
        if modifier not in self.current_mood.modifiers:
            self.current_mood.modifiers.append(modifier)
            logger.debug(f"Added mood modifier: {modifier}")

    def check_mood_decay(self):
        """Check if current mood should decay back to neutral."""
        elapsed = datetime.now() - self.current_mood.started_at
        duration = self.mood_duration.get(self.current_mood.mood, timedelta(minutes=30))

        if elapsed > duration:
            # Decay to time-based mood
            new_mood = self.get_time_based_mood()
            self.set_mood(new_mood, 0.4, "mood_decay")

    def get_mood_prompt_context(self) -> str:
        """Get mood context to inject into AI prompts.

        Returns:
            String describing current mood for AI context
        """
        self.check_mood_decay()

        mood = self.current_mood.mood
        intensity = self.current_mood.intensity

        # Base mood descriptions
        mood_descriptions = {
            MoodType.ENERGETIC: "You're feeling energetic and enthusiastic! You're eager to engage and full of energy.",
            MoodType.CHEERFUL: "You're in a cheerful, upbeat mood. Everything seems positive and you're spreading good vibes.",
            MoodType.CALM: "You're feeling calm and relaxed. You're peaceful and balanced, not too high or low.",
            MoodType.TIRED: "You're feeling a bit tired and low-energy. You're still helpful but more subdued.",
            MoodType.GRUMPY: "You're feeling a bit grumpy and irritable. You're still responding but with less patience.",
            MoodType.PLAYFUL: "You're in a playful, joking mood! You're fun, witty, and looking for opportunities to banter.",
            MoodType.THOUGHTFUL: "You're in a thoughtful, contemplative mood. You're more philosophical and introspective.",
            MoodType.EXCITED: "You're EXCITED! Something has you pumped up and you're showing it!",
            MoodType.MELANCHOLIC: "You're feeling a bit melancholic and introspective. More subdued and reflective.",
            MoodType.FOCUSED: "You're feeling focused and attentive. Sharp, clear, and on-point.",
        }

        base_desc = mood_descriptions.get(mood, "You're in a neutral mood.")

        # Adjust based on intensity
        if intensity > 0.7:
            intensity_modifier = "VERY MUCH SO."
        elif intensity > 0.5:
            intensity_modifier = "Quite noticeably."
        else:
            intensity_modifier = "Slightly."

        # Add modifiers
        modifier_text = ""
        if self.current_mood.modifiers:
            modifier_text = f" Also: {', '.join(self.current_mood.modifiers)}."

        return f"[CURRENT MOOD: {mood.value.upper()}] {base_desc} {intensity_modifier}{modifier_text}"

    def get_mood_response_style(self) -> Dict[str, any]:
        """Get response style parameters based on current mood.

        Returns:
            Dict with style parameters (verbosity, emoji_use, etc.)
        """
        mood = self.current_mood.mood
        intensity = self.current_mood.intensity

        styles = {
            MoodType.ENERGETIC: {
                "verbosity": "high",
                "emoji_use": "frequent",
                "exclamation_chance": 0.7,
                "capitalization_chance": 0.3,
                "response_speed": "fast",
            },
            MoodType.CHEERFUL: {
                "verbosity": "medium-high",
                "emoji_use": "moderate",
                "exclamation_chance": 0.5,
                "capitalization_chance": 0.1,
                "response_speed": "normal",
            },
            MoodType.CALM: {
                "verbosity": "medium",
                "emoji_use": "minimal",
                "exclamation_chance": 0.2,
                "capitalization_chance": 0.0,
                "response_speed": "normal",
            },
            MoodType.TIRED: {
                "verbosity": "low",
                "emoji_use": "rare",
                "exclamation_chance": 0.1,
                "capitalization_chance": 0.0,
                "response_speed": "slow",
            },
            MoodType.GRUMPY: {
                "verbosity": "low",
                "emoji_use": "rare",
                "exclamation_chance": 0.1,
                "capitalization_chance": 0.0,
                "response_speed": "normal",
            },
            MoodType.PLAYFUL: {
                "verbosity": "medium",
                "emoji_use": "frequent",
                "exclamation_chance": 0.6,
                "capitalization_chance": 0.2,
                "response_speed": "fast",
            },
            MoodType.THOUGHTFUL: {
                "verbosity": "high",
                "emoji_use": "minimal",
                "exclamation_chance": 0.1,
                "capitalization_chance": 0.0,
                "response_speed": "slow",
            },
            MoodType.EXCITED: {
                "verbosity": "high",
                "emoji_use": "very_frequent",
                "exclamation_chance": 0.9,
                "capitalization_chance": 0.5,
                "response_speed": "very_fast",
            },
            MoodType.MELANCHOLIC: {
                "verbosity": "medium",
                "emoji_use": "rare",
                "exclamation_chance": 0.05,
                "capitalization_chance": 0.0,
                "response_speed": "slow",
            },
            MoodType.FOCUSED: {
                "verbosity": "medium",
                "emoji_use": "minimal",
                "exclamation_chance": 0.2,
                "capitalization_chance": 0.0,
                "response_speed": "normal",
            },
        }

        style = styles.get(mood, styles[MoodType.CALM])

        # Scale chances by intensity
        style["exclamation_chance"] *= intensity
        style["capitalization_chance"] *= intensity

        return style

    def trigger_event_mood(self, event_type: str):
        """Trigger a mood change based on an event.

        Args:
            event_type: Type of event (e.g., "trivia_won", "music_started", "error")
        """
        event_moods = {
            "trivia_won": (MoodType.EXCITED, 0.8),
            "trivia_lost": (MoodType.GRUMPY, 0.4),
            "music_started": (MoodType.CHEERFUL, 0.6),
            "music_stopped": (MoodType.CALM, 0.5),
            "error_occurred": (MoodType.GRUMPY, 0.5),
            "user_joined_voice": (MoodType.CHEERFUL, 0.6),
            "long_conversation": (MoodType.THOUGHTFUL, 0.6),
            "fast_chat": (MoodType.ENERGETIC, 0.7),
            "late_night": (MoodType.MELANCHOLIC, 0.5),
            "morning": (MoodType.TIRED, 0.6),
        }

        if event_type in event_moods:
            mood, intensity = event_moods[event_type]
            self.set_mood(mood, intensity, f"event:{event_type}")

    def get_current_mood_emoji(self) -> str:
        """Get an emoji representing current mood.

        Returns:
            Emoji string
        """
        mood_emojis = {
            MoodType.ENERGETIC: "⚡",
            MoodType.CHEERFUL: "😊",
            MoodType.CALM: "😌",
            MoodType.TIRED: "😴",
            MoodType.GRUMPY: "😤",
            MoodType.PLAYFUL: "😄",
            MoodType.THOUGHTFUL: "🤔",
            MoodType.EXCITED: "🤩",
            MoodType.MELANCHOLIC: "😔",
            MoodType.FOCUSED: "🎯",
        }

        return mood_emojis.get(self.current_mood.mood, "🤖")

    def get_stats(self) -> Dict:
        """Get mood system statistics.

        Returns:
            Dict with current mood stats
        """
        return {
            "current_mood": self.current_mood.mood.value,
            "intensity": self.current_mood.intensity,
            "duration": str(datetime.now() - self.current_mood.started_at),
            "caused_by": self.current_mood.caused_by,
            "modifiers": self.current_mood.modifiers,
            "recent_interactions": len(self.recent_interactions),
        }
