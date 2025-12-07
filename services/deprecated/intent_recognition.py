"""Intent recognition service - detects what users want from natural language."""
import logging
import re
from typing import Optional, Dict, List, Tuple
from datetime import datetime

from services.reminders import TimeParser

logger = logging.getLogger(__name__)


class Intent:
    """Represents a detected user intent."""

    def __init__(self, intent_type: str, confidence: float, data: Dict = None):
        """Initialize an intent.

        Args:
            intent_type: Type of intent (reminder, question, trivia, etc.)
            confidence: Confidence score 0-1
            data: Additional data for the intent
        """
        self.intent_type = intent_type
        self.confidence = confidence
        self.data = data or {}

    def __repr__(self):
        return f"Intent({self.intent_type}, confidence={self.confidence:.2f})"


class IntentRecognitionService:
    """Service for recognizing user intents from natural language."""

    # Reminder patterns
    REMINDER_PATTERNS = [
        # Direct reminder requests
        r'remind\s+me\s+(?:to\s+)?(.+)',
        r'set\s+(?:a\s+)?reminder\s+(?:to\s+)?(.+)',
        r'(?:can\s+you\s+)?remind\s+(?:me\s+)?(.+)',
        # Time-first patterns
        r'in\s+\d+\s+(?:min|minute|hour|day)s?\s+remind\s+(?:me\s+)?(?:to\s+)?(.+)',
        r'(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s+remind\s+(?:me\s+)?(?:to\s+)?(.+)',
    ]

    # Math/Calculation patterns
    MATH_PATTERNS = [
        r'(?:what\'?s?|calculate|compute|solve)\s+(\d+\.?\d*)\s*([+\-*/×÷])\s*(\d+\.?\d*)',
        r'(\d+\.?\d*)\s*([+\-*/×÷])\s*(\d+\.?\d*)\s*[=?]?',
        r'(?:what\'?s?|how\s+much\s+is)\s+(\d+\.?\d*)\s+(?:plus|minus|times|divided\s+by)\s+(\d+\.?\d*)',
        r'square\s+root\s+of\s+(\d+\.?\d*)',
        r'(\d+\.?\d*)\s+(?:squared|cubed)',
    ]

    # Trivia patterns
    TRIVIA_PATTERNS = [
        r'(?:start|play|begin)\s+(?:a\s+)?trivia',
        r'trivia\s+(?:game|question|time)',
        r'(?:give\s+me\s+a\s+)?trivia\s+question',
        r'(?:let\'?s|wanna)\s+play\s+trivia',
    ]

    # Music patterns
    MUSIC_PATTERNS = [
        r'play\s+(?:the\s+)?(?:song|music|track)\s+(.+)',
        r'play\s+(.+)\s+by\s+(.+)',
        r'(?:can\s+you\s+)?play\s+(.+)',
        r'music\s+from\s+(.+)',
        r'(?:pause|stop|skip|resume)\s+(?:the\s+)?(?:music|song|track)',
    ]

    # Time/Date patterns
    TIME_PATTERNS = [
        r'what\s+(?:time|date)\s+is\s+it',
        r'what\'?s?\s+the\s+(?:time|date)',
        r'(?:current|today\'?s?)\s+(?:time|date)',
        r'tell\s+me\s+the\s+(?:time|date)',
    ]

    # Search patterns
    SEARCH_PATTERNS = [
        r'(?:search|look\s+up|find|google)\s+(?:for\s+)?(.+)',
        r'(?:what|who)\s+is\s+(.+)',
        r'(?:information|info)\s+(?:on|about)\s+(.+)',
    ]

    # Translation patterns
    TRANSLATION_PATTERNS = [
        r'translate\s+(.+)\s+to\s+(\w+)',
        r'(?:how\s+do\s+you\s+say)\s+(.+)\s+in\s+(\w+)',
        r'what\'?s?\s+(.+)\s+in\s+(\w+)',
    ]

    # Weather patterns
    WEATHER_PATTERNS = [
        r'(?:what\'?s?|how\'?s?)\s+the\s+weather',
        r'weather\s+(?:in|for|at)\s+(.+)',
        r'(?:is\s+it\s+)?(?:raining|snowing|sunny|cloudy)',
        r'temperature\s+(?:in|at)\s+(.+)',
    ]

    # Question patterns
    QUESTION_PATTERNS = [
        r'\?$',  # Ends with question mark
        r'^(?:what|when|where|who|why|how|which|can|could|would|should|is|are|do|does|did)',
        r'(?:tell|explain|show|describe)\s+(?:me\s+)?(?:about\s+)?',
    ]

    # Small talk patterns
    SMALLTALK_PATTERNS = [
        r'^(?:hi|hello|hey|yo|sup|wassup|greetings|howdy)',
        r'^(?:bye|goodbye|see\s+ya|later|cya|farewell)',
        r'how\s+(?:are\s+)?(?:you|ya)\s*(?:doing)?',
        r'what\'?s?\s+up',
        r'thanks?(?:\s+you)?',
        r'you\'?re?\s+(?:the\s+)?(?:best|awesome|great|cool)',
    ]

    # Help patterns
    HELP_PATTERNS = [
        r'help\s+(?:me\s+)?(?:with\s+)?',
        r'how\s+do\s+i\s+',
        r'what\s+can\s+you\s+do',
        r'what\s+(?:are\s+)?(?:your\s+)?commands',
    ]

    def __init__(self, enable_learning: bool = True, enable_custom_intents: bool = True):
        """Initialize the intent recognition service.

        Args:
            enable_learning: Enable pattern learning
            enable_custom_intents: Enable custom intents
        """
        self.stats = {
            'total_intents_detected': 0,
            'by_type': {}
        }

        # Pattern learner
        self.learner = None
        if enable_learning:
            try:
                from services.pattern_learner import PatternLearner
                self.learner = PatternLearner()
                logger.info("Pattern learning enabled")
            except Exception as e:
                logger.warning(f"Could not enable pattern learning: {e}")

        # Custom intents
        self.custom_intents = None
        if enable_custom_intents:
            try:
                from services.custom_intents import CustomIntentManager
                self.custom_intents = CustomIntentManager()
                logger.info("Custom intents enabled")
            except Exception as e:
                logger.warning(f"Could not enable custom intents: {e}")

        logger.info("Intent recognition service initialized")

    def detect_intent(self, message: str, bot_mentioned: bool = False, server_id: Optional[int] = None) -> Optional[Intent]:
        """Detect the primary intent from a message.

        Args:
            message: User message text
            bot_mentioned: Whether the bot was mentioned in the message
            server_id: Server ID for custom intents

        Returns:
            Detected Intent or None
        """
        message_lower = message.lower().strip()

        # Priority 0: Check custom intents first (server-specific overrides)
        if self.custom_intents:
            custom_match = self.custom_intents.check_custom_intent(server_id, message)
            if custom_match:
                intent = Intent(
                    intent_type='custom',
                    confidence=0.95,
                    data=custom_match
                )
                self._record_intent(intent)
                return intent

        # Priority 0.5: Check learned patterns
        if self.learner:
            learned_match = self.learner.check_learned_pattern(message)
            if learned_match:
                intent_type, confidence = learned_match
                intent = Intent(
                    intent_type=intent_type,
                    confidence=confidence,
                    data={'source': 'learned_pattern', 'message': message}
                )
                self._record_intent(intent)
                # Learn from this success
                self.learner.learn_from_success(message, intent_type, confidence)
                return intent

        # Priority order for intent detection
        # 1. Math (quick calculations)
        math_intent = self._detect_math(message_lower)
        if math_intent:
            self._record_intent(math_intent)
            return math_intent

        # 2. Time/Date (quick responses)
        time_intent = self._detect_time(message_lower)
        if time_intent:
            self._record_intent(time_intent)
            return time_intent

        # 3. Reminders (high priority)
        reminder_intent = self._detect_reminder(message_lower)
        if reminder_intent:
            self._record_intent(reminder_intent)
            return reminder_intent

        # 4. Trivia
        trivia_intent = self._detect_trivia(message_lower)
        if trivia_intent:
            self._record_intent(trivia_intent)
            return trivia_intent

        # 5. Music
        music_intent = self._detect_music(message_lower)
        if music_intent:
            self._record_intent(music_intent)
            return music_intent

        # 6. Weather
        weather_intent = self._detect_weather(message_lower)
        if weather_intent:
            self._record_intent(weather_intent)
            return weather_intent

        # 7. Translation
        translation_intent = self._detect_translation(message_lower)
        if translation_intent:
            self._record_intent(translation_intent)
            return translation_intent

        # 8. Search
        search_intent = self._detect_search(message_lower)
        if search_intent:
            self._record_intent(search_intent)
            return search_intent

        # 9. Help requests
        help_intent = self._detect_help(message_lower)
        if help_intent:
            self._record_intent(help_intent)
            return help_intent

        # 10. Questions - only if bot is mentioned or message is directed at bot
        if bot_mentioned or self._is_directed_at_bot(message_lower):
            question_intent = self._detect_question(message_lower)
            if question_intent:
                self._record_intent(question_intent)
                return question_intent

        # 11. Small talk
        smalltalk_intent = self._detect_smalltalk(message_lower)
        if smalltalk_intent and bot_mentioned:
            self._record_intent(smalltalk_intent)
            return smalltalk_intent

        return None

    def _detect_reminder(self, message: str) -> Optional[Intent]:
        """Detect reminder intent.

        Args:
            message: Message text (lowercase)

        Returns:
            Intent or None
        """
        # Check for reminder patterns
        for pattern in self.REMINDER_PATTERNS:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                # Try to parse time
                trigger_time = TimeParser.parse(message)
                if trigger_time:
                    # Extract reminder message
                    reminder_message = TimeParser.extract_message(message)

                    return Intent(
                        intent_type='reminder',
                        confidence=0.9,
                        data={
                            'message': reminder_message,
                            'trigger_time': trigger_time,
                            'original_text': message
                        }
                    )
                else:
                    # Found reminder pattern but couldn't parse time
                    return Intent(
                        intent_type='reminder_no_time',
                        confidence=0.7,
                        data={'original_text': message}
                    )

        return None

    def _detect_question(self, message: str) -> Optional[Intent]:
        """Detect question intent.

        Args:
            message: Message text (lowercase)

        Returns:
            Intent or None
        """
        for pattern in self.QUESTION_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                return Intent(
                    intent_type='question',
                    confidence=0.8,
                    data={'question': message}
                )

        return None

    def _detect_smalltalk(self, message: str) -> Optional[Intent]:
        """Detect small talk intent.

        Args:
            message: Message text (lowercase)

        Returns:
            Intent or None
        """
        for pattern in self.SMALLTALK_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                return Intent(
                    intent_type='smalltalk',
                    confidence=0.9,
                    data={'message': message}
                )

        return None

    def _detect_help(self, message: str) -> Optional[Intent]:
        """Detect help request intent.

        Args:
            message: Message text (lowercase)

        Returns:
            Intent or None
        """
        for pattern in self.HELP_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                return Intent(
                    intent_type='help',
                    confidence=0.85,
                    data={'message': message}
                )

        return None

    def _detect_math(self, message: str) -> Optional[Intent]:
        """Detect math calculation intent.

        Args:
            message: Message text (lowercase)

        Returns:
            Intent or None
        """
        for pattern in self.MATH_PATTERNS:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return Intent(
                    intent_type='math',
                    confidence=0.95,
                    data={
                        'expression': message,
                        'groups': match.groups()
                    }
                )
        return None

    def _detect_trivia(self, message: str) -> Optional[Intent]:
        """Detect trivia game intent.

        Args:
            message: Message text (lowercase)

        Returns:
            Intent or None
        """
        for pattern in self.TRIVIA_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                return Intent(
                    intent_type='trivia',
                    confidence=0.9,
                    data={'message': message}
                )
        return None

    def _detect_music(self, message: str) -> Optional[Intent]:
        """Detect music request intent.

        Args:
            message: Message text (lowercase)

        Returns:
            Intent or None
        """
        for pattern in self.MUSIC_PATTERNS:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return Intent(
                    intent_type='music',
                    confidence=0.85,
                    data={
                        'action': 'play' if 'play' in message else 'control',
                        'query': match.group(1) if match.groups() else message,
                        'original': message
                    }
                )
        return None

    def _detect_time(self, message: str) -> Optional[Intent]:
        """Detect time/date query intent.

        Args:
            message: Message text (lowercase)

        Returns:
            Intent or None
        """
        for pattern in self.TIME_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                query_type = 'date' if 'date' in message else 'time'
                return Intent(
                    intent_type='time',
                    confidence=0.95,
                    data={'query_type': query_type}
                )
        return None

    def _detect_search(self, message: str) -> Optional[Intent]:
        """Detect search intent.

        Args:
            message: Message text (lowercase)

        Returns:
            Intent or None
        """
        for pattern in self.SEARCH_PATTERNS:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                query = match.group(1) if match.groups() else message
                return Intent(
                    intent_type='search',
                    confidence=0.8,
                    data={'query': query}
                )
        return None

    def _detect_translation(self, message: str) -> Optional[Intent]:
        """Detect translation intent.

        Args:
            message: Message text (lowercase)

        Returns:
            Intent or None
        """
        for pattern in self.TRANSLATION_PATTERNS:
            match = re.search(pattern, message, re.IGNORECASE)
            if match and len(match.groups()) >= 2:
                return Intent(
                    intent_type='translation',
                    confidence=0.9,
                    data={
                        'text': match.group(1),
                        'target_language': match.group(2)
                    }
                )
        return None

    def _detect_weather(self, message: str) -> Optional[Intent]:
        """Detect weather query intent.

        Args:
            message: Message text (lowercase)

        Returns:
            Intent or None
        """
        for pattern in self.WEATHER_PATTERNS:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                location = match.group(1) if match.groups() else None
                return Intent(
                    intent_type='weather',
                    confidence=0.85,
                    data={'location': location}
                )
        return None

    def _is_directed_at_bot(self, message: str) -> bool:
        """Check if message seems directed at the bot.

        Args:
            message: Message text (lowercase)

        Returns:
            True if likely directed at bot
        """
        directed_patterns = [
            r'^(?:hey\s+)?(?:bot|assistant)',
            r'^(?:can\s+you|could\s+you|would\s+you|please)',
        ]

        for pattern in directed_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return True

        return False

    def _record_intent(self, intent: Intent):
        """Record intent in stats.

        Args:
            intent: Detected intent
        """
        self.stats['total_intents_detected'] += 1
        if intent.intent_type not in self.stats['by_type']:
            self.stats['by_type'][intent.intent_type] = 0
        self.stats['by_type'][intent.intent_type] += 1

        logger.debug(f"Detected intent: {intent}")

    def report_success(self, message: str, intent_type: str):
        """Report successful intent handling.

        Args:
            message: User message
            intent_type: Intent type that succeeded
        """
        if self.learner:
            self.learner.learn_from_success(message, intent_type)

    def report_failure(self, message: str, intent_type: str):
        """Report failed intent handling.

        Args:
            message: User message
            intent_type: Intent type that failed
        """
        if self.learner:
            self.learner.learn_from_failure(message, intent_type)

    def report_correction(self, message: str, correct_intent: str):
        """Report user correction.

        Args:
            message: User message
            correct_intent: Correct intent type
        """
        if self.learner:
            self.learner.learn_from_correction(message, correct_intent)

    def get_stats(self) -> Dict:
        """Get intent recognition statistics.

        Returns:
            Statistics dict
        """
        stats = self.stats.copy()

        if self.learner:
            stats['pattern_learning'] = self.learner.get_stats()

        if self.custom_intents:
            stats['custom_intents'] = self.custom_intents.get_stats()

        return stats


class ConversationalResponder:
    """Generates natural, conversational responses for intents."""

    # Response templates for various situations
    ACKNOWLEDGMENTS = [
        "Got it!",
        "Sure thing!",
        "On it!",
        "You got it!",
        "Alright!",
        "Okay!",
        "Will do!",
        "No problem!",
    ]

    CONFIRMATION_PHRASES = [
        "I'll remind you",
        "I'll send you a reminder",
        "Reminder set",
        "I'll let you know",
        "I'll ping you",
    ]

    FRIENDLY_ENDINGS = [
        "👍",
        "✅",
        "",  # No ending sometimes
        "!",
    ]

    @classmethod
    def generate_reminder_confirmation(cls, message: str, time_str: str, time_until: str) -> str:
        """Generate a natural reminder confirmation.

        Args:
            message: Reminder message
            time_str: Formatted time string
            time_until: Time until reminder (e.g., "30 minutes")

        Returns:
            Conversational confirmation message
        """
        import random

        templates = [
            f"{random.choice(cls.ACKNOWLEDGMENTS)} {random.choice(cls.CONFIRMATION_PHRASES)} about \"{message}\" in {time_until}",
            f"{random.choice(cls.CONFIRMATION_PHRASES)} to \"{message}\" at {time_str} (in {time_until})",
            f"Reminder set! I'll remind you to \"{message}\" in {time_until}",
            f"Done! I'll ping you in {time_until} to \"{message}\"",
        ]

        response = random.choice(templates)
        ending = random.choice(cls.FRIENDLY_ENDINGS)

        return f"{response} {ending}".strip()

    @classmethod
    def generate_reminder_no_time_response(cls) -> str:
        """Generate response when reminder lacks time info.

        Returns:
            Helpful error message
        """
        import random

        responses = [
            "I'd love to help! But when should I remind you? Try something like \"in 30 minutes\" or \"at 5pm\"",
            "Sure! When do you want the reminder? You can say \"in 2 hours\" or \"tomorrow at 9am\"",
            "Got it! Just need to know when - try \"in 1 hour\" or \"at 3pm tomorrow\"",
        ]

        return random.choice(responses)

    @classmethod
    def generate_smalltalk_response(cls, message: str) -> Optional[str]:
        """Generate a small talk response.

        Args:
            message: Original message

        Returns:
            Response or None to let AI handle it
        """
        import random

        message_lower = message.lower()

        # Greetings
        if any(word in message_lower for word in ['hi', 'hello', 'hey', 'yo', 'sup']):
            responses = [
                "Hey! What's up?",
                "Hi there! How can I help?",
                "Hey hey! Need anything?",
                "Yo! What can I do for you?",
            ]
            return random.choice(responses)

        # Farewells
        if any(word in message_lower for word in ['bye', 'goodbye', 'later', 'cya']):
            responses = [
                "Later!",
                "See ya!",
                "Bye! Talk soon!",
                "Take care!",
                "Catch you later!",
            ]
            return random.choice(responses)

        # Thanks
        if 'thank' in message_lower:
            responses = [
                "No problem!",
                "Happy to help!",
                "Anytime!",
                "You're welcome!",
                "Glad I could help!",
            ]
            return random.choice(responses)

        # Compliments
        if any(word in message_lower for word in ['awesome', 'great', 'cool', 'best']):
            responses = [
                "Aw thanks! 😊",
                "You're too kind!",
                "Thanks! You're pretty awesome too!",
                "Appreciate it! 💙",
            ]
            return random.choice(responses)

        # Let AI handle other small talk
        return None
