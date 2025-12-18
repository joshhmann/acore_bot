"""Channel Activity Profiler - Learns channel patterns for adaptive ambient timing.

Tracks message timestamps per channel, calculates peak hours, average frequency,
silence patterns, and stores learned profiles in JSON with 7-day rolling window.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
from collections import defaultdict, deque

import aiofiles

logger = logging.getLogger(__name__)


@dataclass
class ChannelProfile:
    """Profile for a single channel's activity patterns."""

    # Basic stats
    channel_id: int
    channel_name: str = ""
    total_messages: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

    # Activity patterns (7-day rolling window)
    hourly_activity: Dict[int, int] = field(
        default_factory=lambda: defaultdict(int)
    )  # hour -> count
    daily_activity: Dict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )  # date -> count

    # Timing patterns
    avg_message_frequency: float = 0.0  # messages per hour
    avg_silence_duration: float = 0.0  # seconds between messages
    peak_hours: List[int] = field(default_factory=list)  # hours with highest activity
    quiet_hours: List[int] = field(default_factory=list)  # hours with lowest activity

    # Recent activity tracking (last 100 messages for pattern detection)
    recent_messages: deque = field(default_factory=lambda: deque(maxlen=100))
    recent_silences: deque = field(default_factory=lambda: deque(maxlen=50))

    # Adaptive thresholds
    ambient_silence_threshold: float = 3600.0  # seconds of silence before ambient
    ambient_cooldown_multiplier: float = 1.0  # multiplier for base cooldown
    ambient_chance_modifier: float = 0.0  # modifier to base chance (-0.5 to 0.5)


class ChannelActivityProfiler:
    """
    Learns channel activity patterns and provides adaptive timing thresholds.

    Features:
    - 7-day rolling window for learning
    - Peak hour detection
    - Message frequency analysis
    - Silence pattern recognition
    - Adaptive ambient timing thresholds
    - Async file I/O for persistence
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("./data")
        self.profiles_file = self.data_dir / "channel_activity_profiles.json"
        self.profiles: Dict[int, ChannelProfile] = {}

        # Learning parameters
        self.learning_window_days = 7
        self.peak_hours_count = 4  # Top N hours considered peak
        self.quiet_hours_count = 4  # Top N hours considered quiet

        # Performance tracking
        self._last_save_time = datetime.now()
        self._save_interval_minutes = 15

    async def start(self):
        """Load existing profiles from disk."""
        await self._load_profiles()
        logger.info(
            f"ChannelActivityProfiler started with {len(self.profiles)} profiles"
        )

    async def stop(self):
        """Save profiles to disk."""
        await self._save_profiles()
        logger.info("ChannelActivityProfiler stopped")

    async def record_message(self, channel_id: int, channel_name: str = ""):
        """
        Record a new message in the channel and update patterns.

        Args:
            channel_id: Discord channel ID
            channel_name: Channel name for reference
        """
        now = datetime.now()

        # Get or create profile
        if channel_id not in self.profiles:
            self.profiles[channel_id] = ChannelProfile(
                channel_id=channel_id, channel_name=channel_name
            )

        profile = self.profiles[channel_id]

        # Update basic stats
        profile.total_messages += 1
        profile.last_updated = now
        if channel_name:
            profile.channel_name = channel_name

        # Record timestamp
        timestamp = now.timestamp()
        profile.recent_messages.append(timestamp)

        # Calculate silence duration from previous message
        if len(profile.recent_messages) >= 2:
            silence = profile.recent_messages[-1] - profile.recent_messages[-2]
            profile.recent_silences.append(silence)

        # Update hourly activity
        hour = now.hour
        profile.hourly_activity[hour] += 1

        # Update daily activity
        date_key = now.strftime("%Y-%m-%d")
        profile.daily_activity[date_key] += 1

        # Periodic pattern analysis (every 10 messages)
        if profile.total_messages % 10 == 0:
            await self._analyze_patterns(profile)

        # Periodic save
        if (
            now - self._last_save_time
        ).total_seconds() > self._save_interval_minutes * 60:
            await self._save_profiles()

    async def get_adaptive_thresholds(self, channel_id: int) -> Dict[str, float]:
        """
        Get adaptive timing thresholds for a channel.

        Returns:
            Dict with adaptive thresholds:
            - silence_threshold: seconds of silence before ambient trigger
            - cooldown_multiplier: multiplier for base cooldown
            - chance_modifier: modifier for ambient chance (-0.5 to 0.5)
        """
        if channel_id not in self.profiles:
            # Default thresholds for new channels
            return {
                "silence_threshold": 3600.0,  # 1 hour
                "cooldown_multiplier": 1.0,
                "chance_modifier": 0.0,
            }

        profile = self.profiles[channel_id]
        current_hour = datetime.now().hour

        # Adaptive logic based on learned patterns
        silence_threshold = profile.ambient_silence_threshold
        cooldown_multiplier = profile.ambient_cooldown_multiplier
        chance_modifier = profile.ambient_chance_modifier

        # Peak hour adjustments
        if current_hour in profile.peak_hours:
            # During peak hours: reduce ambient chance, increase cooldown
            chance_modifier -= 0.2  # Reduce chance by 20%
            cooldown_multiplier *= 1.5  # Increase cooldown by 50%
            silence_threshold *= 1.2  # Require longer silence

        # Quiet hour adjustments
        elif current_hour in profile.quiet_hours:
            # During quiet hours: increase ambient chance, reduce cooldown
            chance_modifier += 0.3  # Increase chance by 30%
            cooldown_multiplier *= 0.7  # Reduce cooldown by 30%
            silence_threshold *= 0.8  # Require shorter silence

        # High-frequency channel adjustments
        if profile.avg_message_frequency > 10.0:  # More than 10 messages/hour
            chance_modifier -= 0.1  # Reduce chance for active channels
            cooldown_multiplier *= 1.2  # Increase cooldown

        # Low-frequency channel adjustments
        elif profile.avg_message_frequency < 1.0:  # Less than 1 message/hour
            chance_modifier += 0.2  # Increase chance for quiet channels
            cooldown_multiplier *= 0.8  # Reduce cooldown

        # Clamp values to reasonable ranges
        chance_modifier = max(-0.5, min(0.5, chance_modifier))
        cooldown_multiplier = max(0.5, min(3.0, cooldown_multiplier))
        silence_threshold = max(600.0, min(28800.0, silence_threshold))  # 10min to 8hr

        return {
            "silence_threshold": silence_threshold,
            "cooldown_multiplier": cooldown_multiplier,
            "chance_modifier": chance_modifier,
        }

    async def _analyze_patterns(self, profile: ChannelProfile):
        """
        Analyze activity patterns and update adaptive thresholds.

        This is called periodically to update the profile's learned patterns.
        """
        # Calculate average message frequency
        if len(profile.recent_messages) >= 2:
            time_span = profile.recent_messages[-1] - profile.recent_messages[0]
            if time_span > 0:
                profile.avg_message_frequency = (len(profile.recent_messages) - 1) / (
                    time_span / 3600
                )

        # Calculate average silence duration
        if profile.recent_silences:
            profile.avg_silence_duration = sum(profile.recent_silences) / len(
                profile.recent_silences
            )

        # Identify peak and quiet hours
        if profile.hourly_activity:
            # Sort hours by activity
            sorted_hours = sorted(
                profile.hourly_activity.items(), key=lambda x: x[1], reverse=True
            )

            # Peak hours: top N hours
            profile.peak_hours = [
                hour for hour, _ in sorted_hours[: self.peak_hours_count]
            ]

            # Quiet hours: bottom N hours (but exclude hours with zero activity)
            non_zero_hours = [
                (hour, count) for hour, count in sorted_hours if count > 0
            ]
            if len(non_zero_hours) > self.quiet_hours_count:
                profile.quiet_hours = [
                    hour for hour, _ in non_zero_hours[-self.quiet_hours_count :]
                ]

        # Update adaptive thresholds based on patterns
        # Base silence threshold on average silence duration
        if profile.avg_silence_duration > 0:
            # Set threshold to 2x average silence, but within reasonable bounds
            base_threshold = profile.avg_silence_duration * 2
            profile.ambient_silence_threshold = max(
                1800.0, min(7200.0, base_threshold)
            )  # 30min to 2hr
        else:
            profile.ambient_silence_threshold = 3600.0  # Default 1 hour

        # Adjust cooldown based on message frequency
        if profile.avg_message_frequency > 5.0:  # High frequency
            profile.ambient_cooldown_multiplier = 1.5
        elif profile.avg_message_frequency < 1.0:  # Low frequency
            profile.ambient_cooldown_multiplier = 0.7
        else:
            profile.ambient_cooldown_multiplier = 1.0

        logger.debug(
            f"Updated patterns for channel {profile.channel_id}: "
            f"freq={profile.avg_message_frequency:.1f}/hr, "
            f"silence={profile.avg_silence_duration:.0f}s, "
            f"threshold={profile.ambient_silence_threshold:.0f}s"
        )

    async def _load_profiles(self):
        """Load profiles from JSON file."""
        try:
            if self.profiles_file.exists():
                async with aiofiles.open(self.profiles_file, "r") as f:
                    content = await f.read()
                    data = json.loads(content)

                for channel_id_str, profile_data in data.items():
                    channel_id = int(channel_id_str)

                    # Convert datetime strings back to datetime objects
                    if "created_at" in profile_data:
                        profile_data["created_at"] = datetime.fromisoformat(
                            profile_data["created_at"]
                        )
                    if "last_updated" in profile_data:
                        profile_data["last_updated"] = datetime.fromisoformat(
                            profile_data["last_updated"]
                        )

                    # Convert deques back to deques
                    if "recent_messages" in profile_data:
                        profile_data["recent_messages"] = deque(
                            profile_data["recent_messages"], maxlen=100
                        )
                    if "recent_silences" in profile_data:
                        profile_data["recent_silences"] = deque(
                            profile_data["recent_silences"], maxlen=50
                        )

                    # Convert defaultdicts back to defaultdicts
                    if "hourly_activity" in profile_data:
                        profile_data["hourly_activity"] = defaultdict(
                            int, profile_data["hourly_activity"]
                        )
                    if "daily_activity" in profile_data:
                        profile_data["daily_activity"] = defaultdict(
                            int, profile_data["daily_activity"]
                        )

                    self.profiles[channel_id] = ChannelProfile(**profile_data)

                logger.info(f"Loaded {len(self.profiles)} channel profiles")
            else:
                logger.info("No existing profiles file found, starting fresh")

        except Exception as e:
            logger.error(f"Failed to load channel profiles: {e}")

    async def _save_profiles(self):
        """Save profiles to JSON file."""
        try:
            # Ensure data directory exists
            self.data_dir.mkdir(parents=True, exist_ok=True)

            # Convert profiles to serializable format
            serializable_data = {}
            for channel_id, profile in self.profiles.items():
                profile_dict = asdict(profile)

                # Convert datetime objects to strings
                profile_dict["created_at"] = profile.created_at.isoformat()
                profile_dict["last_updated"] = profile.last_updated.isoformat()

                # Convert deques to lists
                profile_dict["recent_messages"] = list(profile.recent_messages)
                profile_dict["recent_silences"] = list(profile.recent_silences)

                serializable_data[str(channel_id)] = profile_dict

            # Write to file
            async with aiofiles.open(self.profiles_file, "w") as f:
                await f.write(json.dumps(serializable_data, indent=2))

            self._last_save_time = datetime.now()
            logger.debug(f"Saved {len(self.profiles)} channel profiles")

        except Exception as e:
            logger.error(f"Failed to save channel profiles: {e}")

    async def cleanup_old_data(self):
        """Clean up data older than the learning window."""
        cutoff_date = datetime.now() - timedelta(days=self.learning_window_days)

        for profile in self.profiles.values():
            # Clean up old daily activity
            old_dates = [
                date
                for date in profile.daily_activity
                if datetime.strptime(date, "%Y-%m-%d") < cutoff_date
            ]
            for date in old_dates:
                del profile.daily_activity[date]

        logger.info("Cleaned up old activity data")

    def get_channel_stats(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """Get statistics for a channel."""
        if channel_id not in self.profiles:
            return None

        profile = self.profiles[channel_id]
        return {
            "channel_id": profile.channel_id,
            "channel_name": profile.channel_name,
            "total_messages": profile.total_messages,
            "avg_message_frequency": profile.avg_message_frequency,
            "avg_silence_duration": profile.avg_silence_duration,
            "peak_hours": profile.peak_hours,
            "quiet_hours": profile.quiet_hours,
            "ambient_silence_threshold": profile.ambient_silence_threshold,
            "ambient_cooldown_multiplier": profile.ambient_cooldown_multiplier,
            "ambient_chance_modifier": profile.ambient_chance_modifier,
            "last_updated": profile.last_updated.isoformat(),
        }
