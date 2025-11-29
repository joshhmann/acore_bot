"""Reminders service - allows users to set time-based reminders."""
import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict
import uuid

import discord

from config import Config

logger = logging.getLogger(__name__)


class TimeParser:
    """Parse natural language time expressions."""

    # Patterns for relative times
    RELATIVE_PATTERNS = [
        # "in X minutes/hours/days"
        (r'in\s+(\d+)\s*(?:min(?:ute)?s?)', 'minutes'),
        (r'in\s+(\d+)\s*(?:hr|hour)s?', 'hours'),
        (r'in\s+(\d+)\s*(?:day)s?', 'days'),
        (r'in\s+(\d+)\s*(?:week)s?', 'weeks'),
        (r'in\s+(\d+)\s*mo(?:nths?)?', 'months'),
        (r'in\s+(\d+)\s*y(?:ears?)?', 'years'),
        (r'in\s+(\d+)\s*(?:sec(?:ond)?s?)', 'seconds'),
        (r'in\s+(\d+)\s*(?:ms|millisecond)s?', 'milliseconds'),
        (r'in\s+(\d+)\s*(?:us|microsecond)s?', 'microseconds'),
        # Text-based relative times
        (r'in\s+half\s+an?\s+hour', 'half_hour'),
        (r'in\s+an?\s+hour', 'one_hour'),
        (r'in\s+a\s+min(?:ute)?', 'one_minute'),
        (r'in\s+a\s+sec(?:ond)?', 'one_second'),
        # "X minutes/hours from now"
        (r'(\d+)\s*(?:min(?:ute)?s?)\s*(?:from now)?', 'minutes'),
        (r'(\d+)\s*(?:hr|hour)s?\s*(?:from now)?', 'hours'),
        (r'(\d+)\s*(?:sec(?:ond)?s?)\s*(?:from now)?', 'seconds'),
        # Short forms
        (r'in\s+(\d+)m\b', 'minutes'),
        (r'in\s+(\d+)h\b', 'hours'),
        (r'in\s+(\d+)d\b', 'days'),
        (r'in\s+(\d+)w\b', 'weeks'),
        (r'in\s+(\d+)mo\b', 'months'),
        (r'in\s+(\d+)y\b', 'years'),
        (r'in\s+(\d+)s\b', 'seconds'),
    ]

    # Patterns for absolute times
    ABSOLUTE_PATTERNS = [
        # "at 5pm", "at 5:30pm", "at 17:00"
        (r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', 'time'),
        # "tomorrow at 5pm"
        (r'tomorrow\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', 'tomorrow_time'),
    ]

    # Patterns for combined relative date + absolute time
    COMBINED_PATTERNS = [
        # "in 3 days at 5pm", "3 days from now at 5pm"
        (r'(?:in\s+)?(\d+)\s*days?\s*(?:from now)?\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', 'days_at_time'),
    ]

    @classmethod
    def parse(cls, text: str) -> Optional[datetime]:
        """Parse a time expression and return the target datetime.

        Args:
            text: Natural language time expression

        Returns:
            Target datetime or None if parsing failed
        """
        text = text.lower().strip()
        now = datetime.now()

        # Try combined patterns first (most specific)
        for pattern, ptype in cls.COMBINED_PATTERNS:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                days = int(groups[0])
                hour = int(groups[1])
                minute = int(groups[2]) if groups[2] else 0
                ampm = groups[3] if len(groups) > 3 else None

                # Convert to 24-hour format
                if ampm == 'pm' and hour != 12:
                    hour += 12
                elif ampm == 'am' and hour == 12:
                    hour = 0
                
                # Calculate target date
                target_date = now + timedelta(days=days)
                
                # Combine with target time
                return target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # Try relative patterns
        for pattern, unit in cls.RELATIVE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                amount = int(match.group(1))
                if unit == 'minutes':
                    return now + timedelta(minutes=amount)
                elif unit == 'hours':
                    return now + timedelta(hours=amount)
                elif unit == 'days':
                    return now + timedelta(days=amount)
                elif unit == 'weeks':
                    return now + timedelta(weeks=amount)
                elif unit == 'months':
                    return now + timedelta(days=amount * 30)
                elif unit == 'years':
                    return now + timedelta(days=amount * 365)
                elif unit == 'seconds':
                    return now + timedelta(seconds=amount)
                elif unit == 'milliseconds':
                    return now + timedelta(milliseconds=amount)
                elif unit == 'microseconds':
                    return now + timedelta(microseconds=amount)
            
            # Handle text-based units (no amount capture)
            if unit == 'half_hour':
                return now + timedelta(minutes=30)
            elif unit == 'one_hour':
                return now + timedelta(hours=1)
            elif unit == 'one_minute':
                return now + timedelta(minutes=1)
            elif unit == 'one_second':
                return now + timedelta(seconds=1)

        # Try absolute patterns
        for pattern, ptype in cls.ABSOLUTE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                hour = int(groups[0])
                minute = int(groups[1]) if groups[1] else 0
                ampm = groups[2] if len(groups) > 2 else None

                # Convert to 24-hour format
                if ampm == 'pm' and hour != 12:
                    hour += 12
                elif ampm == 'am' and hour == 12:
                    hour = 0

                if ptype == 'tomorrow_time':
                    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    target += timedelta(days=1)
                else:
                    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    # If the time has passed today, assume tomorrow
                    if target <= now:
                        target += timedelta(days=1)

                return target

        return None

    @classmethod
    def extract_message(cls, text: str) -> str:
        """Extract the reminder message from the full text.

        Args:
            text: Full reminder text

        Returns:
            The message part without time expressions
        """
        # Remove common time expressions
        cleaned = text

        # Remove combined patterns
        for pattern, _ in cls.COMBINED_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        # Remove relative time patterns
        for pattern, _ in cls.RELATIVE_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        # Remove absolute time patterns
        for pattern, _ in cls.ABSOLUTE_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        # Remove common prefixes
        cleaned = re.sub(r'^(remind\s+me\s+)?(to\s+)?', '', cleaned, flags=re.IGNORECASE)

        # Clean up
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned if cleaned else "Reminder!"


class RemindersService:
    """Service for managing user reminders."""

    def __init__(self, bot, data_dir: Path = None):
        """Initialize the reminders service.

        Args:
            bot: Discord bot instance
            data_dir: Directory to store reminder data
        """
        self.bot = bot
        self.data_dir = data_dir or Config.DATA_DIR / "reminders"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.reminders: Dict[str, Dict] = {}  # reminder_id -> reminder data
        self.running = False
        self._task = None

        # Load existing reminders
        self._load_reminders()

        logger.info(f"Reminders service initialized with {len(self.reminders)} active reminders")

    def _load_reminders(self):
        """Load reminders from disk."""
        reminders_file = self.data_dir / "reminders.json"
        if reminders_file.exists():
            try:
                with open(reminders_file, 'r') as f:
                    data = json.load(f)
                    # Convert string dates back to datetime
                    for rid, reminder in data.items():
                        try:
                            reminder['trigger_time'] = datetime.fromisoformat(reminder['trigger_time'])
                            reminder['created_at'] = datetime.fromisoformat(reminder['created_at'])
                            self.reminders[rid] = reminder
                        except (ValueError, KeyError) as e:
                            logger.error(f"Skipping invalid reminder {rid}: {e}")
                            
                logger.info(f"Loaded {len(self.reminders)} reminders from disk")
            except Exception as e:
                logger.error(f"Failed to load reminders: {e}")
                # Don't wipe existing reminders on file read error
                if not self.reminders:
                    self.reminders = {}

    def _save_reminders(self):
        """Save reminders to disk."""
        reminders_file = self.data_dir / "reminders.json"
        try:
            # Convert datetime to string for JSON
            data = {}
            for rid, reminder in self.reminders.items():
                data[rid] = {
                    **reminder,
                    'trigger_time': reminder['trigger_time'].isoformat(),
                    'created_at': reminder['created_at'].isoformat(),
                }
            with open(reminders_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save reminders: {e}")

    async def start(self):
        """Start the reminder checking task."""
        if self.running:
            return

        self.running = True
        self._task = asyncio.create_task(self._check_reminders_loop())
        logger.info("Reminders background task started")

    async def stop(self):
        """Stop the reminder checking task."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Reminders background task stopped")

    async def _check_reminders_loop(self):
        """Background loop to check for due reminders."""
        while self.running:
            try:
                await self._check_due_reminders()
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in reminders loop: {e}")
                await asyncio.sleep(60)

    async def _check_due_reminders(self):
        """Check for and trigger any due reminders."""
        now = datetime.now()
        due_reminders = []

        for rid, reminder in list(self.reminders.items()):
            if reminder['trigger_time'] <= now:
                due_reminders.append((rid, reminder))

        for rid, reminder in due_reminders:
            await self._trigger_reminder(rid, reminder)

    async def _trigger_reminder(self, reminder_id: str, reminder: Dict):
        """Send a reminder notification.

        Args:
            reminder_id: Reminder ID
            reminder: Reminder data
        """
        try:
            channel = self.bot.get_channel(reminder['channel_id'])
            if not channel:
                logger.warning(f"Channel {reminder['channel_id']} not found for reminder {reminder_id}")
                del self.reminders[reminder_id]
                self._save_reminders()
                return

            # Build reminder message
            user_mention = f"<@{reminder['user_id']}>"

            embed = discord.Embed(
                title="⏰ Reminder!",
                description=reminder['message'],
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"Set {self._format_relative_time(reminder['created_at'])} ago")

            await channel.send(f"{user_mention}", embed=embed)
            logger.info(f"Triggered reminder {reminder_id} for user {reminder['user_id']}")

            # Remove the reminder
            del self.reminders[reminder_id]
            self._save_reminders()

        except Exception as e:
            logger.error(f"Failed to trigger reminder {reminder_id}: {e}")
            # Remove failed reminder to prevent spam
            if reminder_id in self.reminders:
                del self.reminders[reminder_id]
                self._save_reminders()

    def _format_relative_time(self, dt: datetime) -> str:
        """Format a datetime as relative time (e.g., '2 hours').

        Args:
            dt: Datetime to format

        Returns:
            Relative time string
        """
        delta = datetime.now() - dt
        seconds = int(delta.total_seconds())

        if seconds < 60:
            return f"{seconds} seconds"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            days = seconds // 86400
            return f"{days} day{'s' if days != 1 else ''}"

    async def add_reminder(
        self,
        user_id: int,
        channel_id: int,
        message: str,
        trigger_time: datetime
    ) -> Optional[str]:
        """Add a new reminder.

        Args:
            user_id: User who set the reminder
            channel_id: Channel to send reminder in
            message: Reminder message
            trigger_time: When to trigger the reminder

        Returns:
            Reminder ID or None if failed
        """
        # Check user's reminder count
        user_reminders = self.get_user_reminders(user_id)
        max_reminders = getattr(Config, 'MAX_REMINDERS_PER_USER', 10)

        if len(user_reminders) >= max_reminders:
            return None

        reminder_id = str(uuid.uuid4())[:8]

        self.reminders[reminder_id] = {
            'user_id': user_id,
            'channel_id': channel_id,
            'message': message,
            'trigger_time': trigger_time,
            'created_at': datetime.now(),
        }

        self._save_reminders()
        logger.info(f"Added reminder {reminder_id} for user {user_id}: {message[:50]}...")

        return reminder_id

    def get_user_reminders(self, user_id: int) -> List[Dict]:
        """Get all reminders for a user.

        Args:
            user_id: User ID

        Returns:
            List of reminder dicts
        """
        return [
            {'id': rid, **reminder}
            for rid, reminder in self.reminders.items()
            if reminder['user_id'] == user_id
        ]

    def cancel_reminder(self, reminder_id: str, user_id: int) -> bool:
        """Cancel a reminder.

        Args:
            reminder_id: Reminder ID to cancel
            user_id: User requesting cancellation (must own the reminder)

        Returns:
            True if cancelled, False if not found or not owned
        """
        if reminder_id not in self.reminders:
            return False

        if self.reminders[reminder_id]['user_id'] != user_id:
            return False

        del self.reminders[reminder_id]
        self._save_reminders()
        logger.info(f"Cancelled reminder {reminder_id}")

        return True

    def format_time_until(self, trigger_time: datetime) -> str:
        """Format time until a reminder triggers.

        Args:
            trigger_time: When the reminder triggers

        Returns:
            Formatted time string
        """
        delta = trigger_time - datetime.now()
        seconds = int(delta.total_seconds())

        if seconds < 0:
            return "any moment"
        elif seconds < 60:
            return f"{seconds} seconds"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif seconds < 86400:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if minutes > 0:
                return f"{hours}h {minutes}m"
            return f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            if hours > 0:
                return f"{days}d {hours}h"
            return f"{days} day{'s' if days != 1 else ''}"
