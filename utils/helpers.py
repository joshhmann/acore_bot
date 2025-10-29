"""Utility functions and helpers."""
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional
import aiofiles

logger = logging.getLogger(__name__)


class ChatHistoryManager:
    """Manages chat history per Discord channel."""

    def __init__(self, history_dir: Path, max_messages: int = 20):
        """Initialize chat history manager.

        Args:
            history_dir: Directory to store chat history files
            max_messages: Maximum messages to keep per channel
        """
        self.history_dir = Path(history_dir)
        self.max_messages = max_messages
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def _get_history_file(self, channel_id: int) -> Path:
        """Get the history file path for a channel.

        Args:
            channel_id: Discord channel ID

        Returns:
            Path to history file
        """
        return self.history_dir / f"{channel_id}.json"

    async def load_history(self, channel_id: int) -> List[Dict[str, str]]:
        """Load chat history for a channel.

        Args:
            channel_id: Discord channel ID

        Returns:
            List of message dicts with 'role' and 'content'
        """
        history_file = self._get_history_file(channel_id)

        if not history_file.exists():
            return []

        try:
            async with aiofiles.open(history_file, "r") as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to load history for channel {channel_id}: {e}")
            return []

    async def save_history(self, channel_id: int, messages: List[Dict[str, str]]) -> None:
        """Save chat history for a channel.

        Args:
            channel_id: Discord channel ID
            messages: List of message dicts to save
        """
        history_file = self._get_history_file(channel_id)

        try:
            # Trim to max messages
            if len(messages) > self.max_messages:
                messages = messages[-self.max_messages:]

            async with aiofiles.open(history_file, "w") as f:
                await f.write(json.dumps(messages, indent=2))

        except Exception as e:
            logger.error(f"Failed to save history for channel {channel_id}: {e}")

    async def add_message(
        self,
        channel_id: int,
        role: str,
        content: str,
        username: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> None:
        """Add a message to channel history with user attribution.

        Args:
            channel_id: Discord channel ID
            role: Message role ('user' or 'assistant')
            content: Message content
            username: Username of the speaker (for multi-user tracking)
            user_id: User ID (for multi-user tracking)
        """
        history = await self.load_history(channel_id)

        message = {"role": role, "content": content}

        # Add user attribution for multi-user conversations
        if username:
            message["username"] = username
        if user_id:
            message["user_id"] = user_id

        history.append(message)
        await self.save_history(channel_id, history)

    def format_history_for_display(
        self, messages: List[Dict[str, str]], include_usernames: bool = True
    ) -> str:
        """Format chat history for display with user attribution.

        Args:
            messages: List of message dicts
            include_usernames: Whether to include usernames

        Returns:
            Formatted history string
        """
        formatted = []

        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            username = msg.get("username", "User")

            if role == "user" and include_usernames:
                formatted.append(f"{username}: {content}")
            elif role == "assistant":
                formatted.append(f"Assistant: {content}")
            else:
                formatted.append(content)

        return "\n".join(formatted)

    def get_conversation_participants(
        self, messages: List[Dict[str, str]]
    ) -> List[Dict[str, any]]:
        """Get list of unique participants in a conversation.

        Args:
            messages: List of message dicts

        Returns:
            List of participant info dicts
        """
        participants = {}

        for msg in messages:
            if msg.get("role") == "user":
                user_id = msg.get("user_id")
                username = msg.get("username", "Unknown User")

                if user_id and user_id not in participants:
                    participants[user_id] = {
                        "user_id": user_id,
                        "username": username,
                        "message_count": 0,
                    }

                if user_id:
                    participants[user_id]["message_count"] += 1

        return list(participants.values())

    def build_multi_user_context(self, messages: List[Dict[str, str]]) -> str:
        """Build context string for multi-user conversations.

        Args:
            messages: List of message dicts

        Returns:
            Context string describing participants
        """
        participants = self.get_conversation_participants(messages)

        if len(participants) == 0:
            return ""
        elif len(participants) == 1:
            return f"Talking with {participants[0]['username']}"
        else:
            names = [p["username"] for p in participants]
            return f"Group conversation with: {', '.join(names)}"

    async def clear_history(self, channel_id: int) -> None:
        """Clear chat history for a channel.

        Args:
            channel_id: Discord channel ID
        """
        history_file = self._get_history_file(channel_id)

        try:
            if history_file.exists():
                history_file.unlink()
                logger.info(f"Cleared history for channel {channel_id}")
        except Exception as e:
            logger.error(f"Failed to clear history for channel {channel_id}: {e}")


async def chunk_message(text: str, max_length: int = 2000) -> List[str]:
    """Split a message into chunks that fit Discord's message limit.

    Args:
        text: Text to split
        max_length: Maximum length per chunk (Discord limit is 2000)

    Returns:
        List of text chunks
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    current_chunk = ""

    for line in text.split("\n"):
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = line
        else:
            if current_chunk:
                current_chunk += "\n" + line
            else:
                current_chunk = line

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def format_error(error: Exception) -> str:
    """Format an exception for user-friendly display.

    Args:
        error: Exception to format

    Returns:
        Formatted error message
    """
    return f"❌ **Error:** {str(error)}"


def format_success(message: str) -> str:
    """Format a success message.

    Args:
        message: Success message

    Returns:
        Formatted success message
    """
    return f"✅ {message}"


def format_info(message: str) -> str:
    """Format an info message.

    Args:
        message: Info message

    Returns:
        Formatted info message
    """
    return f"ℹ️ {message}"


def clean_text_for_tts(text: str) -> str:
    """Clean text for TTS by removing markdown, emojis, and roleplay actions.

    This removes:
    - Asterisks for actions (*sighs*, *laughs*)
    - Emojis and emoji-like text
    - Markdown formatting (bold, italic, code blocks)
    - URLs
    - Excessive punctuation

    Args:
        text: Raw text from LLM response

    Returns:
        Cleaned text suitable for TTS
    """
    # Remove content in asterisks (roleplay actions like *sighs*, *laughs*)
    text = re.sub(r'\*[^*]+\*', '', text)

    # Remove content in underscores (markdown italic)
    text = re.sub(r'_[^_]+_', '', text)

    # Remove markdown bold
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)

    # Remove code blocks
    text = re.sub(r'```[^`]*```', '', text)
    text = re.sub(r'`[^`]+`', '', text)

    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)

    # Remove common emoji patterns
    # Remove emoji shortcodes like :smile:, :joy:
    text = re.sub(r':[a-z_]+:', '', text)

    # Remove Unicode emojis (basic range)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE
    )
    text = emoji_pattern.sub('', text)

    # Remove stage directions in parentheses or brackets
    text = re.sub(r'\([^)]*\)', '', text)
    text = re.sub(r'\[[^\]]*\]', '', text)

    # Clean up excessive punctuation (but keep some for emphasis)
    # Replace multiple exclamation marks with max 3
    text = re.sub(r'!{4,}', '!!!', text)
    # Replace multiple question marks with max 2
    text = re.sub(r'\?{3,}', '??', text)
    # Replace multiple periods with ellipsis
    text = re.sub(r'\.{4,}', '...', text)

    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)

    # Trim whitespace
    text = text.strip()

    return text
