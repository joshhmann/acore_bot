"""Voice command parser for detecting music and other commands from speech."""
import logging
import re
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CommandType(Enum):
    """Types of voice commands."""
    PLAY = "play"
    SKIP = "skip"
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"
    VOLUME = "volume"
    QUEUE = "queue"
    SHUFFLE = "shuffle"
    LOOP = "loop"
    NOWPLAYING = "nowplaying"
    CLEAR = "clear"
    DISCONNECT = "disconnect"
    CHAT = "chat"  # Not a command, regular chat


@dataclass
class VoiceCommand:
    """Parsed voice command."""
    type: CommandType
    argument: Optional[str] = None
    confidence: float = 1.0


class VoiceCommandParser:
    """Parses voice transcriptions to detect commands."""

    def __init__(self, wake_words: list = None):
        """Initialize the parser.

        Args:
            wake_words: List of wake words/phrases to trigger commands
        """
        self.wake_words = wake_words or [
            "hey bot",
            "okay bot",
            "hey music",
            "bot",
        ]

        # Filler words to remove from search queries
        self.filler_words = [
            "some", "a", "an", "the", "any", "just"
        ]

        # Command patterns (regex)
        self.patterns = {
            CommandType.PLAY: [
                r"play\s+(.+)",
                r"put on\s+(.+)",
                r"queue\s+(.+)",
                r"add\s+(.+)\s+to\s+(?:the\s+)?queue",
            ],
            CommandType.SKIP: [
                r"skip(?:\s+(?:this|the)\s+song)?",
                r"next(?:\s+song)?",
                r"skip\s+this",
            ],
            CommandType.STOP: [
                r"stop(?:\s+(?:the\s+)?music)?",
                r"stop\s+playing",
                r"shut\s+up",
            ],
            CommandType.PAUSE: [
                r"pause(?:\s+(?:the\s+)?(?:music|song))?",
                r"hold\s+on",
            ],
            CommandType.RESUME: [
                r"resume(?:\s+(?:the\s+)?(?:music|song))?",
                r"continue(?:\s+(?:the\s+)?(?:music|song))?",
                r"unpause",
                r"play(?!\s+\w)",  # "play" with no argument = resume
            ],
            CommandType.VOLUME: [
                r"(?:set\s+)?volume\s+(?:to\s+)?(\d+)",
                r"turn\s+(?:it\s+)?(?:up|down)",
                r"louder",
                r"quieter",
            ],
            CommandType.QUEUE: [
                r"(?:show\s+)?(?:the\s+)?queue",
                r"what'?s\s+(?:in\s+)?(?:the\s+)?queue",
                r"list\s+(?:the\s+)?songs",
            ],
            CommandType.SHUFFLE: [
                r"shuffle(?:\s+(?:the\s+)?queue)?",
                r"randomize(?:\s+(?:the\s+)?queue)?",
                r"mix\s+(?:it\s+)?up",
            ],
            CommandType.LOOP: [
                r"loop(?:\s+(?:this|the)\s+(?:song|track))?",
                r"repeat(?:\s+(?:this|the)\s+(?:song|track))?",
                r"(?:turn\s+)?loop\s+(on|off)",
            ],
            CommandType.NOWPLAYING: [
                r"what'?s\s+playing",
                r"what\s+(?:song\s+)?is\s+this",
                r"current\s+song",
                r"now\s+playing",
            ],
            CommandType.CLEAR: [
                r"clear\s+(?:the\s+)?queue",
                r"empty\s+(?:the\s+)?queue",
            ],
            CommandType.DISCONNECT: [
                r"disconnect",
                r"leave(?:\s+(?:the\s+)?(?:voice|channel))?",
                r"go\s+away",
                r"bye",
            ],
        }

    def _clean_search_query(self, query: str) -> str:
        """Remove filler words from search query.

        Args:
            query: Raw search query

        Returns:
            Cleaned search query
        """
        words = query.split()

        # Remove filler words from the beginning
        cleaned_words = []
        for i, word in enumerate(words):
            # Skip filler words at the start
            if i == 0 and word.lower() in self.filler_words:
                continue
            cleaned_words.append(word)

        cleaned = " ".join(cleaned_words).strip()

        # If we removed everything, return original
        if not cleaned:
            return query

        logger.debug(f"Cleaned search query: '{query}' -> '{cleaned}'")
        return cleaned

    def parse(self, text: str) -> VoiceCommand:
        """Parse text to detect voice commands.

        Args:
            text: Transcribed text from speech

        Returns:
            VoiceCommand with detected type and arguments
        """
        original_text = text
        text = text.lower().strip()

        # Check for @mention patterns first (strip them out like wake words)
        mention_patterns = [
            (r'^@\s*arby[,\s]+', '@Arby'),
            (r'^at\s+arby[,\s]+', 'at Arby'),
            (r'^add\s+arby[,\s]+', 'add Arby'),
            (r'^at\s+r\.?b\.?[,\s]+', 'at R.B.'),
        ]

        has_wake_word = False
        for pattern, name in mention_patterns:
            if re.match(pattern, text):
                text = re.sub(pattern, '', text).strip()
                logger.debug(f"Stripped {name} mention from command")
                has_wake_word = True
                break

        # Check for wake word if no @mention found
        if not has_wake_word:
            for wake_word in self.wake_words:
                if text.startswith(wake_word):
                    text = text[len(wake_word):].strip()
                    # Remove common fillers after wake word
                    text = re.sub(r'^[,\s]*(can you|could you|please|would you)\s*', '', text)
                    has_wake_word = True
                    break

        # If no wake word found, this might still be a command
        # Check for direct command patterns

        # Try to match command patterns
        for cmd_type, patterns in self.patterns.items():
            for pattern in patterns:
                match = re.match(pattern, text)
                if match:
                    # Extract argument if captured
                    argument = None
                    if match.groups():
                        argument = match.group(1).strip()

                        # Clean up play command arguments (remove filler words)
                        if cmd_type == CommandType.PLAY and argument:
                            argument = self._clean_search_query(argument)

                    # Handle special cases
                    if cmd_type == CommandType.VOLUME:
                        # Check for relative volume commands
                        if "louder" in text or "turn it up" in text or "turn up" in text:
                            argument = "+20"
                        elif "quieter" in text or "turn it down" in text or "turn down" in text:
                            argument = "-20"

                    logger.info(f"Detected command: {cmd_type.value} (arg: {argument})")

                    return VoiceCommand(
                        type=cmd_type,
                        argument=argument,
                        confidence=0.9 if has_wake_word else 0.7
                    )

        # No command detected, treat as chat
        return VoiceCommand(
            type=CommandType.CHAT,
            argument=original_text,
            confidence=1.0
        )

    def is_music_command(self, command: VoiceCommand) -> bool:
        """Check if command is music-related.

        Args:
            command: Parsed voice command

        Returns:
            True if music command
        """
        music_commands = {
            CommandType.PLAY,
            CommandType.SKIP,
            CommandType.STOP,
            CommandType.PAUSE,
            CommandType.RESUME,
            CommandType.VOLUME,
            CommandType.QUEUE,
            CommandType.SHUFFLE,
            CommandType.LOOP,
            CommandType.NOWPLAYING,
            CommandType.CLEAR,
            CommandType.DISCONNECT,
        }
        return command.type in music_commands


# Global instance for easy access
_parser = None


def get_parser(wake_words: list = None) -> VoiceCommandParser:
    """Get or create the global voice command parser.

    Args:
        wake_words: Optional wake words to use

    Returns:
        VoiceCommandParser instance
    """
    global _parser
    if _parser is None:
        _parser = VoiceCommandParser(wake_words)
    return _parser
