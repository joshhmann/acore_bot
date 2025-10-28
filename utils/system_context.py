"""System context provider for real-time information."""
from datetime import datetime, timezone
import platform
import psutil
from typing import Dict, Any


class SystemContextProvider:
    """Provides real-time system context to the AI."""

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
        return f"[Current time: {now.strftime('%I:%M %p')}, {now.strftime('%A, %B %d, %Y')}]"
