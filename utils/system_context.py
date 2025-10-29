"""System context provider for real-time information."""
from datetime import datetime, timezone
import platform
import psutil
from typing import Dict, Any, Optional


class SystemContextProvider:
    """Provides real-time system context to the AI."""

    @staticmethod
    def get_time_of_day_context() -> str:
        """Get contextual information based on time of day.

        Returns:
            Time-appropriate context
        """
        now = datetime.now()
        hour = now.hour

        if 5 <= hour < 12:
            period = "morning"
            mood = "fresh and energetic"
        elif 12 <= hour < 17:
            period = "afternoon"
            mood = "productive and engaged"
        elif 17 <= hour < 21:
            period = "evening"
            mood = "relaxed and conversational"
        else:
            period = "late night"
            mood = "calm and introspective"

        return f"{period} ({mood})"

    @staticmethod
    def get_datetime_context() -> str:
        """Get current date and time information.

        Returns:
            Formatted datetime context string
        """
        now = datetime.now()
        utc_now = datetime.now(timezone.utc)

        context = f"""Current Date & Time:
- Local Time: {now.strftime('%I:%M:%S %p')}
- Date: {now.strftime('%A, %B %d, %Y')}
- Day of Week: {now.strftime('%A')}
- Month: {now.strftime('%B')}
- Year: {now.year}
- UTC Time: {utc_now.strftime('%I:%M:%S %p UTC')}
- Unix Timestamp: {int(now.timestamp())}"""

        return context

    @staticmethod
    def get_system_context() -> str:
        """Get system information context.

        Returns:
            Formatted system context string
        """
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            context = f"""System Status:
- CPU Usage: {cpu_percent}%
- RAM Usage: {memory.percent}% ({memory.used / (1024**3):.1f}GB / {memory.total / (1024**3):.1f}GB)
- Disk Usage: {disk.percent}% ({disk.used / (1024**3):.1f}GB / {disk.total / (1024**3):.1f}GB)
- Platform: {platform.system()} {platform.release()}"""

        except Exception:
            context = f"System Status: Running on {platform.system()}"

        return context

    @staticmethod
    def get_full_context(include_system: bool = False) -> str:
        """Get complete system context for AI.

        Args:
            include_system: Whether to include system resource info

        Returns:
            Complete context string
        """
        contexts = [
            "=== SYSTEM CONTEXT ===",
            SystemContextProvider.get_datetime_context(),
        ]

        if include_system:
            contexts.append("")
            contexts.append(SystemContextProvider.get_system_context())

        contexts.append("===================")

        return "\n".join(contexts)

    @staticmethod
    def get_compact_context() -> str:
        """Get compact context for prepending to prompts.

        Returns:
            One-line context string
        """
        now = datetime.now()
        time_context = SystemContextProvider.get_time_of_day_context()
        return f"[Current time: {now.strftime('%I:%M %p')}, {now.strftime('%A, %B %d, %Y')} - {time_context}]"

    @staticmethod
    def get_activity_context(
        interaction_count: int, last_interaction: Optional[str] = None
    ) -> str:
        """Get context based on user activity patterns.

        Args:
            interaction_count: Total interactions with user
            last_interaction: Timestamp of last interaction

        Returns:
            Activity-based context string
        """
        if interaction_count == 0:
            return "first time meeting"
        elif interaction_count < 5:
            return "getting to know each other"
        elif interaction_count < 20:
            return "familiar with each other"
        elif interaction_count < 50:
            return "good friends"
        else:
            return "close companions"

    @staticmethod
    def get_server_context(
        guild_name: Optional[str] = None, channel_name: Optional[str] = None
    ) -> str:
        """Get Discord server/channel context.

        Args:
            guild_name: Name of the Discord server
            channel_name: Name of the channel

        Returns:
            Server context string
        """
        parts = []
        if guild_name:
            parts.append(f"Server: {guild_name}")
        if channel_name:
            parts.append(f"Channel: #{channel_name}")

        return " | ".join(parts) if parts else ""
