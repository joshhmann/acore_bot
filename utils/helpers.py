"""Utility functions and helpers."""
import json
import logging
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

    async def add_message(self, channel_id: int, role: str, content: str) -> None:
        """Add a message to channel history.

        Args:
            channel_id: Discord channel ID
            role: Message role ('user' or 'assistant')
            content: Message content
        """
        history = await self.load_history(channel_id)
        history.append({"role": role, "content": content})
        await self.save_history(channel_id, history)

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
