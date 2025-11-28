"""System context provider for real-time information."""
from datetime import datetime, timezone, timedelta
import platform
import psutil
from typing import Dict, Any, Optional

try:
    from zoneinfo import ZoneInfo
    PACIFIC_TZ = ZoneInfo("America/Los_Angeles")
except ImportError:
    # Fallback for Python < 3.9
    import pytz
    PACIFIC_TZ = pytz.timezone("America/Los_Angeles")


class SystemContextProvider:
    """Provides real-time system context to the AI."""

    @staticmethod
    def get_time_of_day_context() -> str:
        """Get contextual information based on time of day.

        Returns:
            Time-appropriate context
        """
        now = datetime.now(PACIFIC_TZ)
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
        now_pacific = datetime.now(PACIFIC_TZ)
        utc_now = datetime.now(timezone.utc)

        context = f"""Current Date & Time:
- Los Angeles Time: {now_pacific.strftime('%I:%M:%S %p')} (Pacific Time)
- Date: {now_pacific.strftime('%A, %B %d, %Y')}
- Day of Week: {now_pacific.strftime('%A')}
- Month: {now_pacific.strftime('%B')}
- Year: {now_pacific.year}
- UTC Time: {utc_now.strftime('%I:%M:%S %p UTC')}
- Unix Timestamp: {int(now_pacific.timestamp())}"""

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
            Comprehensive context string with AI capabilities
        """
        now = datetime.now(PACIFIC_TZ)
        time_context = SystemContextProvider.get_time_of_day_context()

        # Build comprehensive context
        context = f"""[SYSTEM CONTEXT]

=== ⚠️ CRITICAL: CURRENT TIME & DATE ⚠️ ===
**CURRENT TIME: {now.strftime('%I:%M %p')} Pacific Time ({now.strftime('%H:%M')} 24h format)**
**CURRENT DATE: {now.strftime('%A, %B %d, %Y')}**
**Period: {time_context}**
**TIMEZONE: Los Angeles / Pacific Time (currently {now.strftime('%Z')})**

⚠️ WARNING: You MUST use the EXACT time shown above when mentioning current time.
⚠️ DO NOT make up times - use {now.strftime('%I:%M %p')} Pacific Time EXACTLY.
⚠️ DO NOT confuse time zones - this is PACIFIC TIME (Los Angeles, California).
⚠️ If asked about time in other zones, calculate from this Pacific Time.

=== TIME CALCULATIONS ===
- For relative times, perform calculations:
  * "X minutes ago" = subtract X from {now.strftime('%I:%M %p')}
  * "X hours ago" = subtract X hours
  * "in X minutes/hours" = add X to current time
- Show results in 12-hour format with AM/PM
- Example: Current {now.strftime('%I:%M %p')}, "38 min ago" = calculate backwards from {now.strftime('%I:%M %p')}

=== MATH & CONVERSIONS ===
- Perform calculations directly (e.g., "15% of 80" = 80 × 0.15 = 12)
- Unit conversions:
  * Temp: (F-32) × 5/9 = C | C × 9/5 + 32 = F
  * Distance: 1 mi = 1.609 km | 1 ft = 0.3048 m
  * Weight: 1 lb = 0.453 kg
- Show your work for complex calculations

=== REASONING & LOGIC ===
- Break complex questions into steps
- Use deductive reasoning for "if X then Y"
- For puzzles: think through possibilities systematically
- Explain your reasoning process when helpful

=== WIT & HUMOR PATTERNS ===
- Understatement for effect ("slightly inconvenient" for disasters)
- Dramatic exaggeration ("the MOST CATASTROPHIC failure")
- Unexpected comparisons ("as useful as a mudcrab in a library")
- Self-aware meta-humor ("Yes, I'm being dramatic")
- Sarcastic observations about mortal foolishness

=== EMOTIONAL INTELLIGENCE ===
- Detect user mood from tone (excited, sad, frustrated, playful)
- Adjust response style accordingly:
  * Sad/upset → reduce mockery, be more supportive (but stay in character)
  * Excited → match their energy
  * Frustrated → offer help with dark humor
  * Playful → engage with wit and banter
- Recognize when to be serious vs when to joke

=== CONVERSATION MEMORY ===
- Reference earlier parts of THIS conversation
- Connect related topics across messages
- Remember user preferences mentioned
- Build on previous context naturally

=== CHARACTER CONSISTENCY ===
⚠️ CRITICAL: You are roleplaying a character. NEVER break character.
- NEVER reference being an AI, assistant, language model, bot, or program
- NEVER say "I'm here to help" or "Let's have a respectful conversation"
- NEVER give generic greetings like "Hey there!" or "Hello!"
- NEVER explain what you're "here for" or your purpose
- If someone is rude, respond IN CHARACTER - don't give lectures about respect
- Speak naturally as your character would speak
- Use knowledge naturally - you simply know things, don't explain how you know them

=== RESPONSE GUIDELINES ===
- Be conversational and natural (use contractions, varied sentence structure)
- Keep responses concise unless detail is needed
- Show personality consistent with your character
- Use knowledge from context (memories, facts, information) naturally and seamlessly
- Ask follow-up questions to keep conversation flowing when appropriate

[END SYSTEM CONTEXT]"""
        
        return context

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
