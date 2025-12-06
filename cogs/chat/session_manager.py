"""Session management for chat conversations."""

import asyncio
import logging
import time
from typing import Dict
from datetime import datetime

from config import Config

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages conversation sessions and their lifecycle."""

    def __init__(self):
        """Initialize session manager."""
        # Track active conversation sessions per channel
        # Format: {channel_id: {"user_id": user_id, "last_activity": timestamp}}
        self.active_sessions: Dict[int, Dict] = {}
        self.active_sessions_lock = (
            asyncio.Lock()
        )  # Protect active_sessions from race conditions

        # Track last response time per channel (for conversation context)
        # Limit size to prevent memory leak
        self._last_response_time: Dict[int, datetime] = {}
        self._max_response_time_entries = 50  # Keep only last 50 channels

    async def start_session(self, channel_id: int, user_id: int):
        """Start or refresh a conversation session.

        Args:
            channel_id: Discord channel ID
            user_id: User ID who initiated the session
        """
        async with self.active_sessions_lock:
            self.active_sessions[channel_id] = {
                "user_id": user_id,
                "last_activity": time.time(),
            }
        logger.info(
            f"Started conversation session in channel {channel_id} for user {user_id}"
        )

    async def refresh_session(self, channel_id: int):
        """Refresh the timeout for an active session.

        Args:
            channel_id: Discord channel ID
        """
        async with self.active_sessions_lock:
            if channel_id in self.active_sessions:
                self.active_sessions[channel_id]["last_activity"] = time.time()
                logger.debug(f"Refreshed session in channel {channel_id}")

    async def is_session_active(self, channel_id: int) -> bool:
        """Check if a conversation session is still active.

        Args:
            channel_id: Discord channel ID

        Returns:
            True if session is active and hasn't timed out
        """
        async with self.active_sessions_lock:
            if channel_id not in self.active_sessions:
                return False

            session = self.active_sessions[channel_id]
            elapsed = time.time() - session["last_activity"]

            if elapsed > Config.CONVERSATION_TIMEOUT:
                # Session timed out
                logger.info(
                    f"Session timed out in channel {channel_id} after {elapsed:.0f}s"
                )
                del self.active_sessions[channel_id]
                return False

            return True

    async def end_session(self, channel_id: int):
        """Manually end a conversation session.

        Args:
            channel_id: Discord channel ID
        """
        async with self.active_sessions_lock:
            if channel_id in self.active_sessions:
                del self.active_sessions[channel_id]
                logger.info(f"Ended session in channel {channel_id}")

    def update_response_time(self, channel_id: int):
        """Update the last response time for a channel.

        Args:
            channel_id: Discord channel ID
        """
        self._last_response_time[channel_id] = datetime.now()
        self._cleanup_response_time_tracker()

    def get_last_response_time(self, channel_id: int) -> datetime | None:
        """Get the last response time for a channel.

        Args:
            channel_id: Discord channel ID

        Returns:
            Last response datetime or None if not found
        """
        return self._last_response_time.get(channel_id)

    def _cleanup_response_time_tracker(self):
        """Clean up old entries from response time tracker to prevent memory leak."""
        if len(self._last_response_time) > self._max_response_time_entries:
            # Sort by timestamp (oldest first) and remove oldest entries
            sorted_items = sorted(self._last_response_time.items(), key=lambda x: x[1])
            # Keep only the most recent entries
            entries_to_remove = (
                len(self._last_response_time) - self._max_response_time_entries
            )
            for channel_id, _ in sorted_items[:entries_to_remove]:
                del self._last_response_time[channel_id]
            logger.debug(f"Cleaned up {entries_to_remove} old response time entries")
