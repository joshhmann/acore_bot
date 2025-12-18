"""Post-processing for speech transcription to fix common errors."""
import logging
import re

logger = logging.getLogger(__name__)


class TranscriptionFixer:
    """Fixes common transcription errors and normalizes text."""

    def __init__(self):
        """Initialize transcription fixer with common replacements."""
        # Common bot name variations that Whisper gets wrong
        self.bot_name_variants = [
            r'\bA\.R\.B\.?\b',
            r'\bARB\b',
            r'\bR\.B\.?\b',
            r'\bAR B\b',
            r'\bA R B\b',
        ]

        # Common word replacements (transcription errors)
        self.word_replacements = {
            # Bot trigger words
            r'\b(?:hey\s+)?(?:A\.R\.B\.?|ARB|R\.B\.?|AR\s+B|A\s+R\s+B)\b': 'Arby',
            r'\bOK\s+B\b': 'Arby',

            # Common command words that get mangled
            r'\bplace\s+(?:a|the)\s+man\b': 'play He-Man',
            r'\bplace\s+(?:some|a)\b': 'play some',
            r'\bA\.E\.\s+Man\b': 'He-Man',
            r'\bHe\s+Man\b': 'He-Man',

            # YouTube gets transcribed weirdly
            r'\bon\s+you\s+tube\b': 'on YouTube',
            r'\byou\s+tube\b': 'YouTube',

            # Common music command fixes
            # Don't replace "stop playing" - the command parser handles it fine
            r'\bpause\s+it\b': 'pause',
            r'\bskip\s+(?:this|it|song)\b': 'skip',
            r'\bnext\s+song\b': 'skip',
        }

        logger.info("Transcription fixer initialized with common replacements")

    def fix(self, transcription: str) -> str:
        """Fix common transcription errors.

        Args:
            transcription: Raw transcription text

        Returns:
            Fixed transcription
        """
        if not transcription:
            return transcription

        fixed = transcription

        # Apply word replacements (case-insensitive)
        for pattern, replacement in self.word_replacements.items():
            fixed = re.sub(pattern, replacement, fixed, flags=re.IGNORECASE)

        # Log if we made changes
        if fixed != transcription:
            logger.info(f"Fixed transcription: '{transcription}' → '{fixed}'")

        return fixed

    def normalize_command(self, text: str) -> str:
        """Normalize a command for better matching.

        Args:
            text: Command text

        Returns:
            Normalized command
        """
        # Remove common filler words at start
        normalized = text.strip()

        # Remove leading fillers
        fillers = ['hey', 'ok', 'okay', 'please', 'can you', 'could you']
        for filler in fillers:
            pattern = f'^{filler}\\s+'
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)

        # Remove trailing punctuation
        normalized = normalized.rstrip('.,!?')

        return normalized.strip()

    def extract_command_and_arg(self, text: str) -> tuple[str, str]:
        """Extract command and argument from transcribed text.

        Args:
            text: Transcribed text (already fixed)

        Returns:
            Tuple of (command, argument)
        """
        # Common command patterns
        patterns = {
            'play': r'\b(?:play|plays)\s+(.+)',
            'stop': r'\b(?:stop|stops|halt)(?:\s+.*)?$',
            'pause': r'\b(?:pause|pauses)(?:\s+.*)?$',
            'resume': r'\b(?:resume|continue|unpause)(?:\s+.*)?$',
            'skip': r'\b(?:skip|next)(?:\s+.*)?$',
            'volume': r'\b(?:volume|set volume)\s+(?:to\s+)?(\d+)',
        }

        text_lower = text.lower()

        for cmd, pattern in patterns.items():
            match = re.search(pattern, text_lower)
            if match:
                # Get argument if it exists
                arg = match.group(1) if match.lastindex else None
                if arg:
                    arg = arg.strip()
                return cmd, arg

        return None, None


# Global instance
_transcription_fixer = None


def get_transcription_fixer() -> TranscriptionFixer:
    """Get or create the global transcription fixer instance.

    Returns:
        TranscriptionFixer instance
    """
    global _transcription_fixer
    if _transcription_fixer is None:
        _transcription_fixer = TranscriptionFixer()
    return _transcription_fixer
