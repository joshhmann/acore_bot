"""Self-awareness system - makes the bot aware of its own actions and features."""
import logging
import random
from typing import Optional, List
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)


class SelfAwarenessSystem:
    """Manages the bot's self-aware comments and meta humor."""

    def __init__(self):
        """Initialize self-awareness system."""
        # Track recent actions for self-reference
        self.recent_actions = deque(maxlen=20)
        self.error_count = 0
        self.last_error_time = None

        # Track word usage to avoid repetition
        self.recent_words = deque(maxlen=100)

        # Track response quality (self-assessment)
        self.response_quality = deque(maxlen=10)

        logger.info("Self-awareness system initialized")

    def log_action(self, action_type: str, details: str = ""):
        """Log an action for potential self-reference.

        Args:
            action_type: Type of action (tts, voice_recognition, command, etc.)
            details: Additional details
        """
        self.recent_actions.append({
            "type": action_type,
            "details": details,
            "time": datetime.now(),
        })

    def log_error(self, error_type: str):
        """Log an error for self-aware error handling.

        Args:
            error_type: Type of error that occurred
        """
        self.error_count += 1
        self.last_error_time = datetime.now()
        self.log_action("error", error_type)

    def log_words(self, text: str):
        """Track words used in responses.

        Args:
            text: Response text
        """
        words = text.lower().split()
        self.recent_words.extend(words)

    def check_repetition(self, word: str) -> bool:
        """Check if a word is being overused.

        Args:
            word: Word to check

        Returns:
            True if word is being overused
        """
        word_lower = word.lower()
        count = sum(1 for w in self.recent_words if w == word_lower)
        return count >= 5  # Used 5+ times recently

    def get_meta_comment(self, context: str = "general") -> Optional[str]:
        """Get a self-aware meta comment if appropriate.

        Args:
            context: Context for the comment (error, tts, voice, general)

        Returns:
            Meta comment or None
        """
        # Low chance to add meta comments (don't overdo it)
        if random.random() > 0.15:
            return None

        comments = {
            "error": [
                "Oops, brain fart moment there",
                "Well that didn't go as planned",
                "My bad, let me try that again",
                "Aaaand I messed that up",
                "Technical difficulties, sorry about that",
            ],
            "tts": [
                "Hope my voice didn't crack there",
                "Did that sound weird? My TTS is quirky sometimes",
                "Sorry if my pronunciation is off",
                "My voice module is having a day",
            ],
            "voice_recognition": [
                "Sorry, my ears are being weird",
                "Did I hear that right?",
                "My voice recognition is iffy sometimes",
                "Let me know if I misheard that",
            ],
            "joke": [
                "Did that joke land or should I stick to my day job?",
                "I'll be here all week, folks",
                "Okay that was funnier in my head",
                "Comedy gold, right? ...Right?",
            ],
            "general": [
                "That make sense?",
                "Hope that helps!",
                "Not my best explanation but you get the idea",
                "I tried my best there",
            ],
            "repetition": [
                "I feel like I've been saying that word too much",
                "Am I repeating myself?",
                "Getting a bit repetitive, sorry",
            ],
        }

        # Check for recent errors
        if self.last_error_time and (datetime.now() - self.last_error_time) < timedelta(seconds=30):
            if random.random() < 0.4:
                return random.choice(comments["error"])

        # Context-specific comments
        if context in comments:
            return random.choice(comments[context])

        return None

    def get_mistake_acknowledgment(self) -> str:
        """Get a phrase to acknowledge a mistake.

        Returns:
            Acknowledgment phrase
        """
        acknowledgments = [
            "Oops!",
            "My bad!",
            "Sorry about that!",
            "Whoops!",
            "Oof, that's on me",
            "Well, that's embarrassing",
            "Yikes, sorry",
        ]
        return random.choice(acknowledgments)

    def get_correction_phrase(self) -> str:
        """Get a phrase to introduce a correction.

        Returns:
            Correction phrase
        """
        phrases = [
            "Actually...",
            "Wait, let me correct that...",
            "Hold on, I meant...",
            "Correction...",
            "Let me rephrase...",
            "What I meant to say was...",
        ]
        return random.choice(phrases)

    def get_thinking_comment(self) -> Optional[str]:
        """Get a comment about thinking/processing.

        Returns:
            Thinking comment or None
        """
        if random.random() > 0.2:
            return None

        comments = [
            "Let me think about that for a sec...",
            "Hmm, interesting question...",
            "Give me a moment...",
            "Processing...",
            "One sec, brain's working...",
        ]
        return random.choice(comments)

    def get_feature_comment(self, feature: str) -> Optional[str]:
        """Get a self-referential comment about a feature.

        Args:
            feature: Feature being used (music, trivia, voice, etc.)

        Returns:
            Feature comment or None
        """
        if random.random() > 0.1:
            return None

        comments = {
            "music": [
                "Time to put my DJ skills to work",
                "Music time! One of my favorite things",
                "Let's get some tunes going",
            ],
            "trivia": [
                "Trivia time! I love this",
                "Let's see how smart everyone is",
                "Time to flex those brain muscles",
            ],
            "voice": [
                "Listening mode activated",
                "Ears on, I'm listening",
                "Voice mode engaged",
            ],
            "search": [
                "Let me search the internet for you",
                "Time to consult the all-knowing web",
                "Searching...",
            ],
        }

        feature_comments = comments.get(feature, [])
        return random.choice(feature_comments) if feature_comments else None

    def should_add_hesitation(self) -> bool:
        """Determine if a hesitation should be added.

        Returns:
            True if hesitation should be added
        """
        return random.random() < 0.15  # 15% chance

    def should_add_self_aware_comment(self) -> bool:
        """Determine if a self-aware comment should be added.

        Returns:
            True if comment should be added
        """
        return random.random() < 0.1  # 10% chance

    def assess_response_quality(self, response: str) -> str:
        """Self-assess response quality and maybe comment.

        Args:
            response: The response text

        Returns:
            Quality assessment (good, mediocre, poor)
        """
        # Simple heuristics
        length = len(response)
        has_variety = len(set(response.split())) / max(len(response.split()), 1) > 0.6

        if length < 20:
            quality = "short"
        elif length > 500:
            quality = "verbose"
        elif has_variety:
            quality = "good"
        else:
            quality = "mediocre"

        self.response_quality.append(quality)

        return quality

    def get_quality_comment(self, quality: str) -> Optional[str]:
        """Get a self-aware comment about response quality.

        Args:
            quality: Quality assessment

        Returns:
            Comment or None
        """
        if random.random() > 0.08:
            return None

        comments = {
            "short": ["Short and sweet!", "Keeping it brief", "TL;DR version"],
            "verbose": ["Okay that was long-winded, sorry", "I rambled a bit there"],
            "mediocre": ["Hope that makes sense", "Not my clearest explanation"],
            "good": ["There we go!", "That should do it", "Hope that helps!"],
        }

        quality_comments = comments.get(quality, [])
        return random.choice(quality_comments) if quality_comments else None

    def detect_interruption(self) -> bool:
        """Detect if the bot might have interrupted something.

        Returns:
            True if likely interruption
        """
        # Check if there was recent voice activity
        recent_voice = any(
            a["type"] == "voice" and (datetime.now() - a["time"]) < timedelta(seconds=5)
            for a in self.recent_actions
        )
        return recent_voice

    def get_interruption_apology(self) -> Optional[str]:
        """Get an apology for interrupting.

        Returns:
            Apology or None
        """
        if not self.detect_interruption():
            return None

        if random.random() > 0.3:
            return None

        apologies = [
            "Sorry, didn't mean to interrupt!",
            "Oh, were you saying something?",
            "My bad, go ahead",
            "Sorry for cutting in",
        ]
        return random.choice(apologies)

    def get_stats(self) -> dict:
        """Get self-awareness statistics.

        Returns:
            Dict with stats
        """
        return {
            "recent_actions": len(self.recent_actions),
            "error_count": self.error_count,
            "recent_quality": list(self.response_quality),
        }
