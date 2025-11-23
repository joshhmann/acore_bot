"""Environmental awareness - bot notices changes in its environment."""
import logging
import random
from typing import Optional, Dict, Set
from datetime import datetime, timedelta
from collections import deque

import discord

logger = logging.getLogger(__name__)


class EnvironmentalAwareness:
    """Tracks and responds to environmental changes (voice channels, server events)."""

    def __init__(self, bot):
        """Initialize environmental awareness.

        Args:
            bot: Discord bot instance
        """
        self.bot = bot

        # Track who's in voice channels
        self.voice_users: Dict[int, Set[int]] = {}  # guild_id -> set of user_ids

        # Track recent comments to avoid spam
        self.recent_comments: deque = deque(maxlen=50)
        self.last_comment_time: Dict[str, datetime] = {}

        # Comment cooldown (seconds)
        self.comment_cooldown = 120  # 2 minutes between similar comments

        logger.info("Environmental awareness initialized")

    def get_voice_users(self, guild_id: int) -> Set[int]:
        """Get users currently in voice for a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            Set of user IDs in voice
        """
        if guild_id not in self.voice_users:
            self.voice_users[guild_id] = set()
        return self.voice_users[guild_id]

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ) -> Optional[str]:
        """Handle voice state changes.

        Args:
            member: Member whose voice state changed
            before: Previous voice state
            after: New voice state

        Returns:
            Comment string or None
        """
        guild_id = member.guild.id
        user_id = member.id

        # Don't comment on bot's own voice state
        if member.bot:
            return None

        # Track current voice users
        voice_users = self.get_voice_users(guild_id)

        # User joined voice
        if before.channel is None and after.channel is not None:
            voice_users.add(user_id)
            return await self._on_user_joined_voice(member, after.channel)

        # User left voice
        elif before.channel is not None and after.channel is None:
            voice_users.discard(user_id)
            return await self._on_user_left_voice(member, before.channel)

        # User switched channels
        elif before.channel != after.channel:
            return await self._on_user_switched_channel(member, before.channel, after.channel)

        # User muted/unmuted, deafened/undeafened
        elif before.self_mute != after.self_mute or before.self_deaf != after.self_deaf:
            return await self._on_user_audio_change(member, before, after)

        return None

    async def _on_user_joined_voice(
        self,
        member: discord.Member,
        channel: discord.VoiceChannel
    ) -> Optional[str]:
        """Generate comment when user joins voice.

        Args:
            member: Member who joined
            channel: Voice channel they joined

        Returns:
            Comment or None
        """
        # Check cooldown
        cooldown_key = f"join_{member.id}"
        if not self._check_cooldown(cooldown_key):
            return None

        # Chance to comment (30%)
        if random.random() > 0.3:
            return None

        comments = [
            f"Oh hey {member.display_name}, you just hopped in! 👋",
            f"{member.display_name} joined! What's up?",
            f"Hey {member.display_name}! 🎧",
            f"Oh nice, {member.display_name} is here!",
            f"Welcome {member.display_name}!",
        ]

        # Check if others are already in voice
        guild_users = self.get_voice_users(member.guild.id)
        if len(guild_users) > 1:
            comments.extend([
                f"Oh hey {member.display_name}! The gang's all here now",
                f"{member.display_name} joined the party!",
                f"Looks like the whole squad is here now!",
            ])

        comment = random.choice(comments)
        self._mark_commented(cooldown_key)
        return comment

    async def _on_user_left_voice(
        self,
        member: discord.Member,
        channel: discord.VoiceChannel
    ) -> Optional[str]:
        """Generate comment when user leaves voice.

        Args:
            member: Member who left
            channel: Voice channel they left

        Returns:
            Comment or None
        """
        # Check cooldown
        cooldown_key = f"leave_{member.id}"
        if not self._check_cooldown(cooldown_key):
            return None

        # Lower chance to comment on leaving (15%)
        if random.random() > 0.15:
            return None

        comments = [
            f"Later {member.display_name}!",
            f"Bye {member.display_name}! 👋",
            f"See ya {member.display_name}!",
            f"Catch you later {member.display_name}!",
        ]

        comment = random.choice(comments)
        self._mark_commented(cooldown_key)
        return comment

    async def _on_user_switched_channel(
        self,
        member: discord.Member,
        before_channel: discord.VoiceChannel,
        after_channel: discord.VoiceChannel
    ) -> Optional[str]:
        """Generate comment when user switches voice channels.

        Args:
            member: Member who switched
            before_channel: Previous channel
            after_channel: New channel

        Returns:
            Comment or None
        """
        # Very low chance (5%)
        if random.random() > 0.05:
            return None

        # Check cooldown
        cooldown_key = f"switch_{member.id}"
        if not self._check_cooldown(cooldown_key):
            return None

        comments = [
            f"{member.display_name} moved to {after_channel.name}",
            f"Oh, {member.display_name} switched channels",
        ]

        comment = random.choice(comments)
        self._mark_commented(cooldown_key)
        return comment

    async def _on_user_audio_change(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ) -> Optional[str]:
        """Generate comment when user mutes/unmutes.

        Args:
            member: Member whose audio changed
            before: Previous state
            after: New state

        Returns:
            Comment or None
        """
        # Very low chance (3%)
        if random.random() > 0.03:
            return None

        # Check cooldown
        cooldown_key = f"audio_{member.id}"
        if not self._check_cooldown(cooldown_key, cooldown_seconds=300):  # 5 min cooldown
            return None

        # User unmuted
        if before.self_mute and not after.self_mute:
            comments = [
                f"Oh, {member.display_name} is back!",
                f"Unmuted! What's up {member.display_name}?",
            ]
            comment = random.choice(comments)
            self._mark_commented(cooldown_key)
            return comment

        return None

    def detect_voice_channel_state(self, guild: discord.Guild) -> Dict:
        """Detect the current state of voice channels.

        Args:
            guild: Discord guild

        Returns:
            Dict with voice channel state info
        """
        voice_channels = guild.voice_channels
        total_users = 0
        active_channels = []

        for channel in voice_channels:
            user_count = len(channel.members)
            if user_count > 0:
                total_users += user_count
                active_channels.append({
                    "name": channel.name,
                    "users": user_count,
                    "members": [m.display_name for m in channel.members if not m.bot]
                })

        return {
            "total_users": total_users,
            "active_channels": len(active_channels),
            "channels": active_channels,
        }

    def get_voice_context(self, guild: discord.Guild) -> str:
        """Get voice channel context for AI.

        Args:
            guild: Discord guild

        Returns:
            Context string describing voice state
        """
        state = self.detect_voice_channel_state(guild)

        if state["total_users"] == 0:
            return "[Voice channels are empty right now]"

        if state["total_users"] == 1:
            channel = state["channels"][0]
            user = channel["members"][0] if channel["members"] else "someone"
            return f"[{user} is hanging out in voice ({channel['name']})]"

        # Multiple users
        parts = []
        for channel in state["channels"]:
            members = ", ".join(channel["members"])
            parts.append(f"{members} in {channel['name']}")

        return f"[Voice activity: {'; '.join(parts)}]"

    def detect_prolonged_silence(self, guild_id: int) -> Optional[str]:
        """Detect if someone's been in voice alone for a while.

        Args:
            guild_id: Guild ID to check

        Returns:
            Comment or None
        """
        # This would need to track time in voice per user
        # For now, return None - could be enhanced later
        return None

    def detect_channel_gathering(self, channel: discord.VoiceChannel) -> Optional[str]:
        """Detect when multiple people gather in a channel.

        Args:
            channel: Voice channel to check

        Returns:
            Comment or None
        """
        user_count = len([m for m in channel.members if not m.bot])

        # 3+ people is a gathering
        if user_count >= 3:
            # Check cooldown
            cooldown_key = f"gathering_{channel.id}"
            if not self._check_cooldown(cooldown_key, cooldown_seconds=600):  # 10 min
                return None

            if random.random() < 0.2:  # 20% chance
                comments = [
                    "Ooh, looks like the whole squad is in voice!",
                    "Party in voice channel! 🎉",
                    "Everyone's gathering in voice!",
                    "Sounds like the whole gang is here!",
                ]
                self._mark_commented(cooldown_key)
                return random.choice(comments)

        return None

    def _check_cooldown(self, key: str, cooldown_seconds: int = None) -> bool:
        """Check if enough time has passed since last comment.

        Args:
            key: Cooldown key
            cooldown_seconds: Cooldown duration (default: self.comment_cooldown)

        Returns:
            True if can comment
        """
        if cooldown_seconds is None:
            cooldown_seconds = self.comment_cooldown

        if key in self.last_comment_time:
            elapsed = (datetime.now() - self.last_comment_time[key]).total_seconds()
            return elapsed >= cooldown_seconds
        return True

    def _mark_commented(self, key: str):
        """Mark that a comment was made.

        Args:
            key: Cooldown key
        """
        self.last_comment_time[key] = datetime.now()
        self.recent_comments.append({
            "key": key,
            "time": datetime.now(),
        })

    def get_stats(self) -> Dict:
        """Get environmental awareness statistics.

        Returns:
            Dict with stats
        """
        return {
            "tracked_guilds": len(self.voice_users),
            "total_voice_users": sum(len(users) for users in self.voice_users.values()),
            "recent_comments": len(self.recent_comments),
        }
