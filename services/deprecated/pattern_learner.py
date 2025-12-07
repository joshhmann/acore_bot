"""Pattern learning system - learns from user interactions to improve intent recognition."""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict
import re

logger = logging.getLogger(__name__)


class PatternLearner:
    """Learns patterns from user interactions to improve intent recognition."""

    def __init__(self, data_dir: Path = None):
        """Initialize the pattern learner.

        Args:
            data_dir: Directory to store learned patterns
        """
        from config import Config
        self.data_dir = data_dir or (Config.DATA_DIR / "learned_patterns")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Learned patterns: intent_type -> list of (pattern, confidence, usage_count)
        self.learned_patterns: Dict[str, List[Tuple[str, float, int]]] = defaultdict(list)

        # User corrections: phrase -> correct_intent_type
        self.user_corrections: Dict[str, str] = {}

        # Pattern success rates
        self.pattern_stats: Dict[str, Dict] = defaultdict(lambda: {
            'total_attempts': 0,
            'successful': 0,
            'failed': 0,
            'success_rate': 0.0
        })

        # Common phrase transformations learned
        self.phrase_transformations: Dict[str, str] = {}

        # User preference learning (NEW for Phase 4)
        self.user_preferences: Dict[int, Dict] = {}  # user_id -> preferences
        self.user_interaction_history: Dict[int, List[Dict]] = defaultdict(list)  # user_id -> interactions

        # Load existing learned data
        self._load_learned_data()

        logger.info("Pattern learner initialized with user adaptation")

    def _load_learned_data(self):
        """Load previously learned patterns from disk."""
        patterns_file = self.data_dir / "learned_patterns.json"
        if patterns_file.exists():
            try:
                with open(patterns_file, 'r') as f:
                    data = json.load(f)

                    # Load patterns
                    if 'patterns' in data:
                        for intent_type, patterns in data['patterns'].items():
                            self.learned_patterns[intent_type] = [
                                tuple(p) for p in patterns
                            ]

                    # Load corrections
                    if 'corrections' in data:
                        self.user_corrections = data['corrections']

                    # Load stats
                    if 'stats' in data:
                        self.pattern_stats = defaultdict(lambda: {
                            'total_attempts': 0,
                            'successful': 0,
                            'failed': 0,
                            'success_rate': 0.0
                        }, data['stats'])

                    # Load transformations
                    if 'transformations' in data:
                        self.phrase_transformations = data['transformations']

                    # Load user preferences (Phase 4)
                    if 'user_preferences' in data:
                        self.user_preferences = {
                            int(k): v for k, v in data['user_preferences'].items()
                        }

                    # Load user interaction history (Phase 4)
                    if 'user_interactions' in data:
                        self.user_interaction_history = defaultdict(list, {
                            int(k): v for k, v in data['user_interactions'].items()
                        })

                logger.info(f"Loaded {len(self.learned_patterns)} learned pattern types and {len(self.user_preferences)} user profiles")

            except Exception as e:
                logger.error(f"Failed to load learned patterns: {e}")

    def _save_learned_data(self):
        """Save learned patterns to disk."""
        patterns_file = self.data_dir / "learned_patterns.json"
        try:
            data = {
                'patterns': {
                    intent_type: list(patterns)
                    for intent_type, patterns in self.learned_patterns.items()
                },
                'corrections': self.user_corrections,
                'stats': dict(self.pattern_stats),
                'transformations': self.phrase_transformations,
                'user_preferences': {
                    str(k): v for k, v in self.user_preferences.items()
                },
                'user_interactions': {
                    str(k): v[-100:] for k, v in self.user_interaction_history.items()  # Keep last 100 per user
                },
                'last_updated': datetime.now().isoformat()
            }

            with open(patterns_file, 'w') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save learned patterns: {e}")

    def learn_from_success(self, message: str, intent_type: str, confidence: float = 0.8):
        """Learn from a successfully recognized intent.

        Args:
            message: User message
            intent_type: Detected intent type
            confidence: Confidence of detection
        """
        # Extract pattern from message
        pattern = self._extract_pattern(message)

        if not pattern:
            return

        # Check if we already have this pattern
        existing = next(
            (p for p in self.learned_patterns[intent_type] if p[0] == pattern),
            None
        )

        if existing:
            # Increment usage count
            idx = self.learned_patterns[intent_type].index(existing)
            old_pattern, old_conf, count = existing
            # Update confidence based on usage
            new_conf = min(0.95, old_conf + 0.01)
            self.learned_patterns[intent_type][idx] = (pattern, new_conf, count + 1)
        else:
            # Add new pattern
            self.learned_patterns[intent_type].append((pattern, confidence, 1))

        # Update stats
        self.pattern_stats[intent_type]['total_attempts'] += 1
        self.pattern_stats[intent_type]['successful'] += 1
        self._update_success_rate(intent_type)

        self._save_learned_data()
        logger.debug(f"Learned pattern for {intent_type}: {pattern}")

    def learn_from_failure(self, message: str, attempted_intent: str):
        """Learn from a failed intent recognition.

        Args:
            message: User message
            attempted_intent: Intent that was attempted but failed
        """
        # Update stats
        self.pattern_stats[attempted_intent]['total_attempts'] += 1
        self.pattern_stats[attempted_intent]['failed'] += 1
        self._update_success_rate(attempted_intent)

        self._save_learned_data()

    def learn_from_correction(self, message: str, correct_intent: str):
        """Learn from a user correction.

        Args:
            message: Original message
            correct_intent: What the intent should have been
        """
        # Store the correction
        message_normalized = message.lower().strip()
        self.user_corrections[message_normalized] = correct_intent

        # Learn the pattern for the correct intent
        self.learn_from_success(message, correct_intent, confidence=0.9)

        logger.info(f"Learned correction: '{message}' -> {correct_intent}")

    def _extract_pattern(self, message: str) -> Optional[str]:
        """Extract a pattern from a message.

        Args:
            message: User message

        Returns:
            Regex pattern or None
        """
        message = message.lower().strip()

        # Replace specific values with placeholders
        # Numbers
        pattern = re.sub(r'\d+\.?\d*', r'\\d+\\.?\\d*', message)

        # Time expressions
        pattern = re.sub(r'\b\d{1,2}:\d{2}\s*(?:am|pm)?\b', r'\\d{1,2}:\\d{2}\\s*(?:am|pm)?', pattern)

        # Don't create patterns that are too generic
        if len(pattern) < 10:
            return None

        # Escape special regex characters except our placeholders
        pattern = pattern.replace('(', '\\(').replace(')', '\\)')
        pattern = pattern.replace('[', '\\[').replace(']', '\\]')
        pattern = pattern.replace('{', '\\{').replace('}', '\\}')

        return pattern

    def check_learned_pattern(self, message: str) -> Optional[Tuple[str, float]]:
        """Check if message matches any learned patterns.

        Args:
            message: User message

        Returns:
            (intent_type, confidence) or None
        """
        message_normalized = message.lower().strip()

        # Check exact corrections first
        if message_normalized in self.user_corrections:
            return (self.user_corrections[message_normalized], 0.95)

        # Check learned patterns
        best_match = None
        best_confidence = 0.0

        for intent_type, patterns in self.learned_patterns.items():
            for pattern, confidence, usage_count in patterns:
                try:
                    if re.search(pattern, message_normalized, re.IGNORECASE):
                        # Boost confidence based on usage
                        adjusted_confidence = min(0.98, confidence + (usage_count * 0.01))

                        if adjusted_confidence > best_confidence:
                            best_match = intent_type
                            best_confidence = adjusted_confidence
                except re.error:
                    # Invalid regex, skip
                    continue

        if best_match and best_confidence > 0.7:
            return (best_match, best_confidence)

        return None

    def _update_success_rate(self, intent_type: str):
        """Update success rate for an intent type.

        Args:
            intent_type: Intent type
        """
        stats = self.pattern_stats[intent_type]
        total = stats['total_attempts']
        if total > 0:
            stats['success_rate'] = stats['successful'] / total

    def get_top_patterns(self, intent_type: str, limit: int = 10) -> List[Tuple[str, float, int]]:
        """Get top patterns for an intent type.

        Args:
            intent_type: Intent type
            limit: Maximum number of patterns to return

        Returns:
            List of (pattern, confidence, usage_count)
        """
        patterns = self.learned_patterns.get(intent_type, [])
        # Sort by usage count, then confidence
        sorted_patterns = sorted(patterns, key=lambda x: (x[2], x[1]), reverse=True)
        return sorted_patterns[:limit]

    def get_stats(self) -> Dict:
        """Get pattern learner statistics.

        Returns:
            Statistics dict
        """
        total_patterns = sum(len(patterns) for patterns in self.learned_patterns.values())

        return {
            'total_patterns': total_patterns,
            'intent_types_learned': len(self.learned_patterns),
            'user_corrections': len(self.user_corrections),
            'pattern_stats': dict(self.pattern_stats),
            'top_performing': self._get_top_performing_intents()
        }

    def _get_top_performing_intents(self, limit: int = 5) -> List[Tuple[str, float]]:
        """Get top performing intent types.

        Args:
            limit: Number to return

        Returns:
            List of (intent_type, success_rate)
        """
        sorted_intents = sorted(
            self.pattern_stats.items(),
            key=lambda x: (x[1]['success_rate'], x[1]['total_attempts']),
            reverse=True
        )
        return [(intent, stats['success_rate']) for intent, stats in sorted_intents[:limit]]

    def learn_user_interaction(
        self,
        user_id: int,
        user_message: str,
        bot_response: str,
        user_reaction: Optional[str] = None
    ):
        """Learn from a user interaction.

        Args:
            user_id: Discord user ID
            user_message: User's message
            bot_response: Bot's response
            user_reaction: User's reaction (positive/negative/neutral)
        """
        interaction = {
            'timestamp': datetime.now().isoformat(),
            'user_message_length': len(user_message),
            'bot_response_length': len(bot_response),
            'user_message_has_question': '?' in user_message,
            'bot_response_has_question': '?' in bot_response,
            'reaction': user_reaction,
        }

        self.user_interaction_history[user_id].append(interaction)

        # Keep only recent interactions
        if len(self.user_interaction_history[user_id]) > 100:
            self.user_interaction_history[user_id] = self.user_interaction_history[user_id][-100:]

        # Update user preferences every 10 interactions
        if len(self.user_interaction_history[user_id]) % 10 == 0:
            self._update_user_preferences(user_id)
            self._save_learned_data()

    def _update_user_preferences(self, user_id: int):
        """Analyze interaction history and update user preferences.

        Args:
            user_id: Discord user ID
        """
        interactions = self.user_interaction_history.get(user_id, [])

        if len(interactions) < 5:
            return  # Need at least 5 interactions to learn preferences

        # Analyze response length preferences
        bot_response_lengths = [i['bot_response_length'] for i in interactions]
        avg_bot_length = sum(bot_response_lengths) / len(bot_response_lengths)

        # Classify preferred response length
        if avg_bot_length < 100:
            preferred_length = "short"
        elif avg_bot_length < 300:
            preferred_length = "medium"
        else:
            preferred_length = "long"

        # Analyze question frequency
        question_ratio = sum(1 for i in interactions if i['user_message_has_question']) / len(interactions)
        curious_user = question_ratio > 0.4

        # Analyze formality (simple heuristic based on message length and punctuation)
        user_message_lengths = [i['user_message_length'] for i in interactions]
        avg_user_length = sum(user_message_lengths) / len(user_message_lengths)
        formal_user = avg_user_length > 50  # Longer messages tend to be more formal

        # Store preferences
        self.user_preferences[user_id] = {
            'preferred_response_length': preferred_length,
            'curious_user': curious_user,
            'formal_user': formal_user,
            'total_interactions': len(interactions),
            'last_updated': datetime.now().isoformat(),
        }

        logger.debug(f"Updated preferences for user {user_id}: {preferred_length} responses, curious={curious_user}, formal={formal_user}")

    def get_user_preferences(self, user_id: int) -> Dict:
        """Get learned preferences for a user.

        Args:
            user_id: Discord user ID

        Returns:
            User preferences dictionary
        """
        return self.user_preferences.get(user_id, {
            'preferred_response_length': 'medium',
            'curious_user': False,
            'formal_user': False,
            'total_interactions': 0,
        })

    def get_adaptation_guidance(self, user_id: int) -> str:
        """Get guidance for adapting responses to a user.

        Args:
            user_id: Discord user ID

        Returns:
            Guidance string for LLM
        """
        prefs = self.get_user_preferences(user_id)

        if prefs['total_interactions'] < 5:
            return ""  # Not enough data yet

        guidance_parts = []

        # Response length guidance
        length_map = {
            'short': "Keep responses concise (1-2 sentences).",
            'medium': "Use moderate response length (2-4 sentences).",
            'long': "Provide detailed, thorough responses."
        }
        guidance_parts.append(length_map.get(prefs['preferred_response_length'], ''))

        # Curiosity guidance
        if prefs['curious_user']:
            guidance_parts.append("This user asks many questions - be prepared to elaborate and provide details.")

        # Formality guidance
        if prefs['formal_user']:
            guidance_parts.append("This user communicates formally - match their tone.")
        else:
            guidance_parts.append("This user is casual - keep the conversation relaxed.")

        return " ".join(guidance_parts)

    def suggest_improvements(self) -> List[str]:
        """Suggest improvements based on learned patterns.

        Returns:
            List of suggestions
        """
        suggestions = []

        # Find underperforming intents
        for intent_type, stats in self.pattern_stats.items():
            if stats['total_attempts'] > 10 and stats['success_rate'] < 0.5:
                suggestions.append(
                    f"Intent '{intent_type}' has low success rate ({stats['success_rate']:.1%}). "
                    f"Consider reviewing patterns or adding more examples."
                )

        # Find popular corrections
        if len(self.user_corrections) > 20:
            suggestions.append(
                f"You have {len(self.user_corrections)} user corrections. "
                f"Consider updating default patterns based on these."
            )

        # User adaptation suggestions
        if len(self.user_preferences) > 5:
            suggestions.append(
                f"Learned preferences for {len(self.user_preferences)} users. "
                f"Using adaptive responses based on interaction patterns."
            )

        return suggestions
