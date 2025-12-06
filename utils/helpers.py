"""Utility functions and helpers."""

import json
import logging
import re
import base64
from pathlib import Path
from typing import Dict, List, Optional
from collections import OrderedDict
import aiofiles
import aiohttp

logger = logging.getLogger(__name__)


class ChatHistoryManager:
    """Manages chat history per Discord channel with in-memory caching."""

    def __init__(
        self,
        history_dir: Path,
        max_messages: int = 20,
        cache_size: int = 100,
        metrics=None,
    ):
        """Initialize chat history manager.

        Args:
            history_dir: Directory to store chat history files
            max_messages: Maximum messages to keep per channel
            cache_size: Maximum number of channel histories to keep in memory
            metrics: Optional metrics service for tracking cache performance
        """
        self.history_dir = Path(history_dir)
        self.max_messages = max_messages
        self.cache_size = cache_size
        self.metrics = metrics
        self.history_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache using OrderedDict for O(1) LRU operations
        # {channel_id: messages_list}
        self._cache: OrderedDict[int, List[Dict[str, str]]] = OrderedDict()

    def _get_history_file(self, channel_id: int) -> Path:
        """Get the history file path for a channel.

        Args:
            channel_id: Discord channel ID

        Returns:
            Path to history file
        """
        return self.history_dir / f"{channel_id}.json"

    def _update_cache_access(self, channel_id: int):
        """Update cache access order for LRU eviction using OrderedDict.

        Args:
            channel_id: Channel ID that was accessed
        """
        # Move to end (most recently used) - O(1) operation in OrderedDict
        if channel_id in self._cache:
            self._cache.move_to_end(channel_id)

        # Evict oldest if cache is full
        if len(self._cache) > self.cache_size:
            # Remove least recently used (first item) - O(1) operation
            oldest_channel, _ = self._cache.popitem(last=False)
            logger.debug(f"Evicted channel {oldest_channel} from history cache")

    async def load_history(self, channel_id: int) -> List[Dict[str, str]]:
        """Load chat history for a channel (from cache or disk).

        Args:
            channel_id: Discord channel ID

        Returns:
            List of message dicts with 'role' and 'content'
        """
        # Check cache first
        if channel_id in self._cache:
            self._update_cache_access(channel_id)
            logger.debug(f"Cache hit for channel {channel_id}")
            # Record cache hit
            if self.metrics:
                self.metrics.record_cache_hit("history")
            return self._cache[
                channel_id
            ].copy()  # Return copy to prevent external modification

        # Cache miss - load from disk
        logger.debug(f"Cache miss for channel {channel_id}")
        # Record cache miss
        if self.metrics:
            self.metrics.record_cache_miss("history")

        history_file = self._get_history_file(channel_id)

        if not history_file.exists():
            # Initialize empty history in cache
            self._cache[channel_id] = []
            self._update_cache_access(channel_id)
            return []

        try:
            async with aiofiles.open(history_file, "r") as f:
                content = await f.read()
                history = json.loads(content)

                # Validate history format
                if not isinstance(history, list):
                    logger.warning(
                        f"Invalid history format for channel {channel_id}, expected list"
                    )
                    history = []

                # Store in cache
                self._cache[channel_id] = history
                self._update_cache_access(channel_id)

                logger.debug(f"Loaded history for channel {channel_id} from disk")
                return history.copy()  # Return copy
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted history file for channel {channel_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to load history for channel {channel_id}: {e}")
            return []

    async def save_history(
        self, channel_id: int, messages: List[Dict[str, str]]
    ) -> None:
        """Save chat history for a channel (to cache and disk).

        Args:
            channel_id: Discord channel ID
            messages: List of message dicts to save
        """
        try:
            # Trim to max messages
            if len(messages) > self.max_messages:
                messages = messages[-self.max_messages :]

            # Update cache
            self._cache[channel_id] = messages.copy()
            self._update_cache_access(channel_id)

            # Save to disk asynchronously
            history_file = self._get_history_file(channel_id)
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
        # Build message dict
        message = {"role": role, "content": content}

        # Add user attribution for multi-user conversations
        if username:
            message["username"] = username
        if user_id:
            message["user_id"] = user_id

        # Get history from cache or load if needed
        if channel_id not in self._cache:
            # Load from disk to populate cache
            await self.load_history(channel_id)

        # Append to cached history
        self._cache[channel_id].append(message)

        # Trim if needed
        if len(self._cache[channel_id]) > self.max_messages:
            self._cache[channel_id] = self._cache[channel_id][-self.max_messages :]

        # Update access order
        self._update_cache_access(channel_id)

        # Save to disk asynchronously
        await self.save_history(channel_id, self._cache[channel_id])

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
        """Clear chat history for a channel (from cache and disk).

        Args:
            channel_id: Discord channel ID
        """
        try:
            # Clear from cache (OrderedDict handles removal automatically)
            if channel_id in self._cache:
                del self._cache[channel_id]

            # Clear from disk
            history_file = self._get_history_file(channel_id)
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
    text = re.sub(r"\*[^*]+\*", "", text)

    # Remove content in underscores (markdown italic)
    text = re.sub(r"_[^_]+_", "", text)

    # Remove markdown bold
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)

    # Remove code blocks
    text = re.sub(r"```[^`]*```", "", text)
    text = re.sub(r"`[^`]+`", "", text)

    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)

    # Remove common emoji patterns
    # Remove emoji shortcodes like :smile:, :joy:
    text = re.sub(r":[a-z_]+:", "", text)

    # Remove Unicode emojis (basic range)
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # emoticons
        "\U0001f300-\U0001f5ff"  # symbols & pictographs
        "\U0001f680-\U0001f6ff"  # transport & map symbols
        "\U0001f1e0-\U0001f1ff"  # flags
        "\U00002702-\U000027b0"  # dingbats
        "\U000024c2-\U0001f251"
        "]+",
        flags=re.UNICODE,
    )
    text = emoji_pattern.sub("", text)

    # Remove stage directions in parentheses or brackets
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"\[[^\]]*\]", "", text)

    # Clean up excessive punctuation (but keep some for emphasis)
    # Replace multiple exclamation marks with max 3
    text = re.sub(r"!{4,}", "!!!", text)
    # Replace multiple question marks with max 2
    text = re.sub(r"\?{3,}", "??", text)
    # Replace multiple periods with ellipsis
    text = re.sub(r"\.{4,}", "...", text)

    # Remove multiple spaces
    text = re.sub(r"\s+", " ", text)

    # Trim whitespace
    text = text.strip()

    return text


async def download_attachment(url: str) -> bytes:
    """Download a Discord attachment.

    Args:
        url: URL of the attachment

    Returns:
        Attachment content as bytes

    Raises:
        Exception: If download fails
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise Exception(
                        f"Failed to download attachment: HTTP {resp.status}"
                    )
                return await resp.read()
    except Exception as e:
        logger.error(f"Failed to download attachment from {url}: {e}")
        raise


def image_to_base64(image_data: bytes) -> str:
    """Convert image bytes to base64 string.

    Args:
        image_data: Image data as bytes

    Returns:
        Base64-encoded string
    """
    return base64.b64encode(image_data).decode("utf-8")


def is_image_attachment(filename: str) -> bool:
    """Check if a file is an image based on extension.

    Args:
        filename: Name of the file

    Returns:
        True if file is an image
    """
    image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
    return Path(filename).suffix.lower() in image_extensions
