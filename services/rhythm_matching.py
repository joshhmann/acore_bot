"""Conversational rhythm matching - adapts response style to chat pace and energy."""
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)


class ConversationalRhythmMatcher:
    """Matches response style to conversation rhythm and energy."""

    def __init__(self):
        """Initialize rhythm matcher."""
        # Track message timing per channel
        self.channel_activity: Dict[int, deque] = {}  # channel_id -> deque of timestamps

        # Track message lengths per channel
        self.channel_lengths: Dict[int, deque] = {}  # channel_id -> deque of message lengths

        # Window for analysis (last N messages)
        self.analysis_window = 10

        logger.info("Conversational rhythm matcher initialized")

    def track_message(self, channel_id: int, message_length: int):
        """Track a message for rhythm analysis.

        Args:
            channel_id: Discord channel ID
            message_length: Length of message in characters
        """
        # Initialize tracking for channel if needed
        if channel_id not in self.channel_activity:
            self.channel_activity[channel_id] = deque(maxlen=self.analysis_window)
            self.channel_lengths[channel_id] = deque(maxlen=self.analysis_window)

        # Add timestamp and length
        self.channel_activity[channel_id].append(datetime.now())
        self.channel_lengths[channel_id].append(message_length)

    def analyze_rhythm(self, channel_id: int) -> Dict:
        """Analyze the conversational rhythm for a channel.

        Args:
            channel_id: Discord channel ID

        Returns:
            Dict with rhythm analysis
        """
        if channel_id not in self.channel_activity:
            return self._default_rhythm()

        timestamps = list(self.channel_activity[channel_id])
        lengths = list(self.channel_lengths[channel_id])

        if len(timestamps) < 2:
            return self._default_rhythm()

        # Calculate message rate (messages per minute)
        time_span = (timestamps[-1] - timestamps[0]).total_seconds()
        if time_span > 0:
            messages_per_minute = (len(timestamps) - 1) / (time_span / 60)
        else:
            messages_per_minute = 0

        # Calculate average message length
        avg_length = sum(lengths) / len(lengths) if lengths else 50

        # Determine pace
        if messages_per_minute > 6:
            pace = "very_fast"
        elif messages_per_minute > 3:
            pace = "fast"
        elif messages_per_minute > 1:
            pace = "moderate"
        elif messages_per_minute > 0.5:
            pace = "slow"
        else:
            pace = "very_slow"

        # Determine verbosity
        if avg_length > 300:
            verbosity = "very_high"
        elif avg_length > 150:
            verbosity = "high"
        elif avg_length > 50:
            verbosity = "moderate"
        elif avg_length > 20:
            verbosity = "low"
        else:
            verbosity = "very_low"

        # Calculate recent activity (last 30 seconds)
        now = datetime.now()
        recent_messages = sum(
            1 for ts in timestamps
            if (now - ts).total_seconds() <= 30
        )

        # Determine energy level
        if recent_messages >= 5:
            energy = "high"
        elif recent_messages >= 3:
            energy = "moderate"
        elif recent_messages >= 1:
            energy = "low"
        else:
            energy = "idle"

        return {
            "pace": pace,
            "verbosity": verbosity,
            "energy": energy,
            "messages_per_minute": messages_per_minute,
            "avg_message_length": avg_length,
            "recent_activity": recent_messages,
        }

    def get_recommended_style(self, channel_id: int) -> Dict:
        """Get recommended response style based on rhythm.

        Args:
            channel_id: Discord channel ID

        Returns:
            Dict with style recommendations
        """
        rhythm = self.analyze_rhythm(channel_id)

        # Base recommendations
        style = {
            "max_length": 300,
            "min_length": 30,
            "sentences": 2,
            "use_emojis": True,
            "use_abbreviations": False,
            "response_speed": "normal",
        }

        # Adjust based on pace
        pace = rhythm["pace"]
        if pace == "very_fast":
            style["max_length"] = 100
            style["sentences"] = 1
            style["use_abbreviations"] = True
            style["response_speed"] = "fast"
        elif pace == "fast":
            style["max_length"] = 150
            style["sentences"] = 1
            style["response_speed"] = "fast"
        elif pace == "slow":
            style["max_length"] = 400
            style["sentences"] = 3
        elif pace == "very_slow":
            style["max_length"] = 500
            style["sentences"] = 4
            style["response_speed"] = "slow"

        # Adjust based on verbosity
        verbosity = rhythm["verbosity"]
        if verbosity in ("very_low", "low"):
            style["max_length"] = min(style["max_length"], 150)
            style["sentences"] = 1
            style["use_emojis"] = False
        elif verbosity == "very_high":
            style["max_length"] = max(style["max_length"], 400)
            style["sentences"] = max(style["sentences"], 3)

        # Adjust based on energy
        energy = rhythm["energy"]
        if energy == "high":
            style["use_emojis"] = True
            style["response_speed"] = "fast"
        elif energy == "idle":
            style["response_speed"] = "slow"

        return style

    def get_style_prompt(self, channel_id: int) -> str:
        """Get a style prompt to inject into AI context.

        Args:
            channel_id: Discord channel ID

        Returns:
            Prompt string with style guidance
        """
        rhythm = self.analyze_rhythm(channel_id)
        style = self.get_recommended_style(channel_id)

        pace = rhythm["pace"]
        energy = rhythm["energy"]

        prompts = {
            "very_fast": f"[CHAT PACE: VERY FAST - Keep responses SHORT (max {style['max_length']} chars). Chat is moving quickly - be brief and punchy. 1 sentence max.]",
            "fast": f"[CHAT PACE: FAST - Keep responses concise (max {style['max_length']} chars). Quick, snappy replies. 1-2 sentences.]",
            "moderate": f"[CHAT PACE: MODERATE - Normal responses (max {style['max_length']} chars). 2-3 sentences is good.]",
            "slow": f"[CHAT PACE: SLOW - You can be more detailed (max {style['max_length']} chars). Take your time, 3-4 sentences is fine.]",
            "very_slow": f"[CHAT PACE: VERY SLOW - Thoughtful, detailed responses welcome (max {style['max_length']} chars). Feel free to elaborate.]",
        }

        base_prompt = prompts.get(pace, prompts["moderate"])

        # Add energy context
        if energy == "high":
            base_prompt += " [Energy is HIGH - match the excitement!]"
        elif energy == "idle":
            base_prompt += " [Chat has been quiet - gentle, relaxed tone.]"

        return base_prompt

    def _default_rhythm(self) -> Dict:
        """Get default rhythm when no data available.

        Returns:
            Default rhythm dict
        """
        return {
            "pace": "moderate",
            "verbosity": "moderate",
            "energy": "moderate",
            "messages_per_minute": 1.0,
            "avg_message_length": 50,
            "recent_activity": 0,
        }

    def is_conversation_fast_paced(self, channel_id: int) -> bool:
        """Check if conversation is fast-paced.

        Args:
            channel_id: Channel ID

        Returns:
            True if fast-paced
        """
        rhythm = self.analyze_rhythm(channel_id)
        return rhythm["pace"] in ("fast", "very_fast")

    def is_conversation_energetic(self, channel_id: int) -> bool:
        """Check if conversation is energetic.

        Args:
            channel_id: Channel ID

        Returns:
            True if energetic
        """
        rhythm = self.analyze_rhythm(channel_id)
        return rhythm["energy"] == "high"

    def get_stats(self) -> Dict:
        """Get rhythm matching statistics.

        Returns:
            Dict with stats
        """
        return {
            "tracked_channels": len(self.channel_activity),
            "total_messages_tracked": sum(len(msgs) for msgs in self.channel_activity.values()),
        }
