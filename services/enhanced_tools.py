"""Enhanced tool system with anti-hallucination measures."""
import logging
import math
import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import re
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


class EnhancedToolSystem:
    """
    Comprehensive tool system to prevent LLM hallucinations.

    Philosophy: Give the LLM tools for facts it shouldn't guess.
    - Time/dates → tools, not hallucinated
    - Math → tools, not approximated
    - Conversions → tools, not estimated
    - User facts → database, not invented
    """

    def __init__(self):
        """Initialize enhanced tool system."""
        self.tools = {}
        self._register_all_tools()
        logger.info(f"Enhanced tool system initialized with {len(self.tools)} tools")

    def _register_all_tools(self):
        """Register all available tools."""
        # Time & Date tools
        self.register_tool("get_current_time", self._get_current_time)
        self.register_tool("get_current_date", self._get_current_date)
        self.register_tool("get_time_in_timezone", self._get_time_in_timezone)
        self.register_tool("calculate_time_offset", self._calculate_time_offset)
        self.register_tool("time_until", self._time_until)
        self.register_tool("time_since", self._time_since)
        self.register_tool("day_of_week", self._day_of_week)

        # Math & Calculations
        self.register_tool("calculate", self._calculate)
        self.register_tool("calculate_percentage", self._calculate_percentage)
        self.register_tool("round_number", self._round_number)

        # Unit Conversions
        self.register_tool("convert_temperature", self._convert_temperature)
        self.register_tool("convert_distance", self._convert_distance)
        self.register_tool("convert_weight", self._convert_weight)
        self.register_tool("convert_currency", self._convert_currency)

        # Randomness (for dice, choices, etc.)
        self.register_tool("roll_dice", self._roll_dice)
        self.register_tool("random_number", self._random_number)
        self.register_tool("random_choice", self._random_choice)

        # Text processing
        self.register_tool("count_words", self._count_words)
        self.register_tool("count_characters", self._count_characters)

        # Validation
        self.register_tool("validate_url", self._validate_url)
        self.register_tool("validate_email", self._validate_email)

    def register_tool(self, name: str, function: callable):
        """Register a tool with its implementation."""
        self.tools[name] = function

    def get_tool_descriptions(self) -> str:
        """
        Get formatted descriptions of all tools for the LLM.

        Returns:
            Formatted tool descriptions for system prompt
        """
        descriptions = """
=== AVAILABLE TOOLS ===

You have access to these tools to prevent hallucination. Use them for facts you shouldn't guess.

SYNTAX: Use tools by responding with the exact format:
TOOL: tool_name(param1=value1, param2=value2)

TIME & DATE TOOLS:
• get_current_time() → Returns current time in 12-hour format
• get_current_date() → Returns current date (YYYY-MM-DD)
• get_time_in_timezone(timezone="America/New_York") → Time in specific timezone
• calculate_time_offset(hours=2, minutes=30, direction="past"|"future") → Calculate time offset
• time_until(target_time="14:30") → Time until specific time today
• time_since(hours=3, minutes=15) → Time since X ago
• day_of_week(date="2024-12-25") → Get day of week for date

MATH TOOLS:
• calculate(expression="2 + 2 * 5") → Evaluate math expression safely
• calculate_percentage(value=50, total=200) → Calculate percentage
• round_number(number=3.14159, decimals=2) → Round to N decimals

CONVERSION TOOLS:
• convert_temperature(value=32, from_unit="F", to_unit="C") → Temperature conversion
• convert_distance(value=5, from_unit="mi", to_unit="km") → Distance conversion
• convert_weight(value=150, from_unit="lbs", to_unit="kg") → Weight conversion
• convert_currency(amount=100, from_curr="USD", to_curr="EUR") → Currency (requires API)

RANDOMNESS TOOLS:
• roll_dice(dice="2d6") → Roll dice (supports "1d6", "3d20", etc.)
• random_number(min=1, max=100) → Random number in range
• random_choice(options=["option1", "option2", "option3"]) → Pick random option

TEXT TOOLS:
• count_words(text="some text here") → Count words
• count_characters(text="some text", include_spaces=true) → Count characters

VALIDATION TOOLS:
• validate_url(url="https://example.com") → Check if URL is valid
• validate_email(email="user@example.com") → Check if email is valid

ANTI-HALLUCINATION RULES:
1. For time/date questions → ALWAYS use time tools, NEVER guess
2. For math/calculations → ALWAYS use calculate, NEVER approximate
3. For conversions → ALWAYS use convert tools, NEVER estimate
4. For user facts → Use get_user_profile (if available), NEVER invent
5. If uncertain about a fact → Say so or search, NEVER make it up

EXAMPLES:

User: "What time is it?"
❌ Bad: "It's around 3 PM" (hallucinating)
✅ Good: TOOL: get_current_time()
        [Result: 3:47 PM]
        "It's 3:47 PM, mortal."

User: "What's 15% of 230?"
❌ Bad: "About 34 or 35" (approximating)
✅ Good: TOOL: calculate_percentage(value=15, total=230)
        [Result: 34.5]
        "34.5. Even a mortal could calculate that."

User: "Roll 2d6 for me"
✅ Good: TOOL: roll_dice(dice="2d6")
        [Result: 2d6: [3, 5] = 8]
        "You rolled an 8. Mediocre, as expected."

User: "What's the weather like?"
❌ Bad: "It's sunny" (complete hallucination)
✅ Good: "I'm an immortal god, not a weather station. Check your mortal weather app."
"""
        return descriptions

    # ==================== TIME & DATE TOOLS ====================

    def _get_current_time(self) -> str:
        """Get current time in 12-hour format."""
        now = datetime.now()
        return now.strftime("%I:%M %p").lstrip('0')

    def _get_current_date(self) -> str:
        """Get current date."""
        return datetime.now().strftime("%Y-%m-%d (%A)")

    def _get_time_in_timezone(self, timezone: str = "UTC") -> str:
        """
        Get current time in a specific timezone.

        Args:
            timezone: Timezone name (e.g., "America/New_York", "Europe/London")
        """
        try:
            tz = ZoneInfo(timezone)
            now = datetime.now(tz)
            return f"{now.strftime('%I:%M %p').lstrip('0')} {timezone}"
        except Exception as e:
            return f"Error: Invalid timezone '{timezone}'. Use format like 'America/New_York'"

    def _calculate_time_offset(
        self,
        hours: int = 0,
        minutes: int = 0,
        direction: str = "future"
    ) -> str:
        """
        Calculate time X hours/minutes in past or future.

        Args:
            hours: Number of hours
            minutes: Number of minutes
            direction: "past" or "future"
        """
        now = datetime.now()
        delta = timedelta(hours=hours, minutes=minutes)

        if direction.lower() == "past":
            target = now - delta
        else:
            target = now + delta

        return target.strftime("%I:%M %p on %A, %B %d").lstrip('0')

    def _time_until(self, target_time: str) -> str:
        """
        Calculate time until a specific time today.

        Args:
            target_time: Time in format "HH:MM" or "HH:MM AM/PM"
        """
        try:
            now = datetime.now()

            # Parse target time
            if "AM" in target_time.upper() or "PM" in target_time.upper():
                target = datetime.strptime(target_time, "%I:%M %p")
            else:
                target = datetime.strptime(target_time, "%H:%M")

            # Set to today's date
            target = target.replace(year=now.year, month=now.month, day=now.day)

            # If time already passed, assume tomorrow
            if target < now:
                target += timedelta(days=1)

            diff = target - now
            hours = int(diff.total_seconds() // 3600)
            minutes = int((diff.total_seconds() % 3600) // 60)

            if hours > 0:
                return f"{hours}h {minutes}m until {target_time}"
            else:
                return f"{minutes}m until {target_time}"
        except Exception as e:
            return f"Error parsing time: {e}"

    def _time_since(self, hours: int = 0, minutes: int = 0) -> str:
        """Calculate what time it was X hours/minutes ago."""
        return self._calculate_time_offset(hours, minutes, "past")

    def _day_of_week(self, date: str = None) -> str:
        """
        Get day of week for a date.

        Args:
            date: Date in format "YYYY-MM-DD" or None for today
        """
        try:
            if date:
                dt = datetime.strptime(date, "%Y-%m-%d")
            else:
                dt = datetime.now()
            return dt.strftime("%A, %B %d, %Y")
        except Exception as e:
            return f"Error parsing date: {e}"

    # ==================== MATH TOOLS ====================

    def _calculate(self, expression: str) -> str:
        """
        Safely evaluate a math expression.

        Args:
            expression: Math expression (e.g., "2 + 2 * 5")
        """
        try:
            # Sanitize input - only allow numbers, operators, and common functions
            allowed = set("0123456789+-*/().% ")
            if not all(c in allowed for c in expression.replace(" ", "")):
                return "Error: Expression contains invalid characters"

            # Evaluate safely
            result = eval(expression, {"__builtins__": {}}, {})
            return str(result)
        except Exception as e:
            return f"Error calculating: {e}"

    def _calculate_percentage(self, value: float, total: float) -> str:
        """
        Calculate what percentage value is of total.

        Args:
            value: The value
            total: The total
        """
        try:
            percentage = (value / total) * 100
            return f"{percentage:.2f}%"
        except ZeroDivisionError:
            return "Error: Cannot divide by zero"
        except Exception as e:
            return f"Error: {e}"

    def _round_number(self, number: float, decimals: int = 2) -> str:
        """Round a number to N decimal places."""
        try:
            return str(round(float(number), decimals))
        except Exception as e:
            return f"Error: {e}"

    # ==================== CONVERSION TOOLS ====================

    def _convert_temperature(self, value: float, from_unit: str, to_unit: str) -> str:
        """
        Convert temperature between F, C, K.

        Args:
            value: Temperature value
            from_unit: "F", "C", or "K"
            to_unit: "F", "C", or "K"
        """
        try:
            # Convert to Celsius first
            if from_unit.upper() == "F":
                celsius = (value - 32) * 5/9
            elif from_unit.upper() == "C":
                celsius = value
            elif from_unit.upper() == "K":
                celsius = value - 273.15
            else:
                return f"Error: Invalid unit '{from_unit}'"

            # Convert from Celsius to target
            if to_unit.upper() == "F":
                result = (celsius * 9/5) + 32
            elif to_unit.upper() == "C":
                result = celsius
            elif to_unit.upper() == "K":
                result = celsius + 273.15
            else:
                return f"Error: Invalid unit '{to_unit}'"

            return f"{value}°{from_unit.upper()} = {result:.2f}°{to_unit.upper()}"
        except Exception as e:
            return f"Error: {e}"

    def _convert_distance(self, value: float, from_unit: str, to_unit: str) -> str:
        """
        Convert distance (mi, km, m, ft, etc.).

        Args:
            value: Distance value
            from_unit: "mi", "km", "m", "ft", "in"
            to_unit: Same options
        """
        try:
            # Conversion factors to meters
            to_meters = {
                "m": 1,
                "km": 1000,
                "mi": 1609.34,
                "ft": 0.3048,
                "in": 0.0254,
            }

            from_u = from_unit.lower()
            to_u = to_unit.lower()

            if from_u not in to_meters or to_u not in to_meters:
                return f"Error: Invalid unit. Use: mi, km, m, ft, in"

            # Convert to meters, then to target unit
            meters = value * to_meters[from_u]
            result = meters / to_meters[to_u]

            return f"{value} {from_unit} = {result:.2f} {to_unit}"
        except Exception as e:
            return f"Error: {e}"

    def _convert_weight(self, value: float, from_unit: str, to_unit: str) -> str:
        """Convert weight (lbs, kg, oz, g)."""
        try:
            to_kg = {
                "kg": 1,
                "lbs": 0.453592,
                "oz": 0.0283495,
                "g": 0.001,
            }

            from_u = from_unit.lower()
            to_u = to_unit.lower()

            if from_u not in to_kg or to_u not in to_kg:
                return f"Error: Invalid unit. Use: kg, lbs, oz, g"

            kg = value * to_kg[from_u]
            result = kg / to_kg[to_u]

            return f"{value} {from_unit} = {result:.2f} {to_unit}"
        except Exception as e:
            return f"Error: {e}"

    def _convert_currency(self, amount: float, from_curr: str, to_curr: str) -> str:
        """Currency conversion (would need API in production)."""
        return (
            f"Currency conversion requires a live API. "
            f"Try: 'search for {amount} {from_curr} to {to_curr} conversion'"
        )

    # ==================== RANDOMNESS TOOLS ====================

    def _roll_dice(self, dice: str = "1d6") -> str:
        """
        Roll dice in standard notation (e.g., "2d6", "1d20").

        Args:
            dice: Dice notation (e.g., "2d6" = 2 six-sided dice)
        """
        try:
            match = re.match(r"(\d+)d(\d+)([+-]\d+)?", dice.lower())
            if not match:
                return f"Error: Invalid dice notation. Use format: '2d6' or '1d20+5'"

            num_dice = int(match.group(1))
            num_sides = int(match.group(2))
            modifier = int(match.group(3)) if match.group(3) else 0

            if num_dice > 100:
                return "Error: Maximum 100 dice at once"
            if num_sides > 1000:
                return "Error: Maximum 1000 sides per die"

            rolls = [random.randint(1, num_sides) for _ in range(num_dice)]
            total = sum(rolls) + modifier

            rolls_str = ", ".join(map(str, rolls))
            mod_str = f" {modifier:+d}" if modifier else ""

            return f"{dice}: [{rolls_str}]{mod_str} = {total}"
        except Exception as e:
            return f"Error: {e}"

    def _random_number(self, min: int = 1, max: int = 100) -> str:
        """Generate random number in range."""
        try:
            result = random.randint(int(min), int(max))
            return f"Random number ({min}-{max}): {result}"
        except Exception as e:
            return f"Error: {e}"

    def _random_choice(self, options: str) -> str:
        """
        Pick random option from list.

        Args:
            options: Comma-separated options or list
        """
        try:
            if isinstance(options, str):
                choices = [opt.strip() for opt in options.split(",")]
            else:
                choices = options

            if not choices:
                return "Error: No options provided"

            choice = random.choice(choices)
            return f"Random choice: {choice}"
        except Exception as e:
            return f"Error: {e}"

    # ==================== TEXT TOOLS ====================

    def _count_words(self, text: str) -> str:
        """Count words in text."""
        words = len(text.split())
        return f"Word count: {words}"

    def _count_characters(self, text: str, include_spaces: bool = True) -> str:
        """Count characters in text."""
        if include_spaces:
            count = len(text)
        else:
            count = len(text.replace(" ", ""))

        spaces_note = "with" if include_spaces else "without"
        return f"Character count ({spaces_note} spaces): {count}"

    # ==================== VALIDATION TOOLS ====================

    def _validate_url(self, url: str) -> str:
        """Validate if string is a valid URL."""
        url_pattern = re.compile(
            r'^https?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$', re.IGNORECASE
        )

        is_valid = bool(url_pattern.match(url))
        return f"URL '{url}' is {'valid' if is_valid else 'invalid'}"

    def _validate_email(self, email: str) -> str:
        """Validate if string is a valid email."""
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

        is_valid = bool(email_pattern.match(email))
        return f"Email '{email}' is {'valid' if is_valid else 'invalid'}"

    # ==================== TOOL EXECUTION ====================

    def parse_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Parse tool call from LLM response.

        Args:
            text: LLM response text

        Returns:
            Dict with tool name and arguments, or None
        """
        pattern = r'TOOL:\s*(\w+)\((.*?)\)'
        match = re.search(pattern, text, re.IGNORECASE)

        if not match:
            return None

        tool_name = match.group(1)
        args_str = match.group(2)

        # Parse arguments
        args = {}
        if args_str.strip():
            # Parse key=value pairs
            arg_pattern = r'(\w+)\s*=\s*(["\'])(.*?)\2|(\w+)\s*=\s*([^,\)]+)'

            for arg_match in re.finditer(arg_pattern, args_str):
                if arg_match.group(1):  # Quoted value
                    key = arg_match.group(1)
                    value = arg_match.group(3)
                else:  # Unquoted value
                    key = arg_match.group(4)
                    value = arg_match.group(5).strip()

                # Try to convert to appropriate type
                try:
                    # Try int
                    value = int(value)
                except ValueError:
                    try:
                        # Try float
                        value = float(value)
                    except ValueError:
                        # Try bool
                        if value.lower() == "true":
                            value = True
                        elif value.lower() == "false":
                            value = False
                        # Otherwise keep as string

                args[key] = value

        return {
            "tool": tool_name,
            "args": args,
            "full_match": match.group(0)
        }

    def execute_tool(self, tool_name: str, **kwargs) -> str:
        """
        Execute a tool by name.

        Args:
            tool_name: Name of tool to execute
            **kwargs: Tool arguments

        Returns:
            Tool result as string
        """
        if tool_name not in self.tools:
            return f"Error: Unknown tool '{tool_name}'"

        try:
            result = self.tools[tool_name](**kwargs)
            return result
        except TypeError as e:
            return f"Error: Invalid arguments for {tool_name}: {e}"
        except Exception as e:
            logger.error(f"Tool {tool_name} execution error: {e}")
            return f"Error executing {tool_name}: {e}"

    async def process_message_with_tools(self, message: str, llm_generate_func) -> str:
        """
        Process a message, execute any tool calls, and regenerate response.

        Args:
            message: User message
            llm_generate_func: Async function to generate LLM response

        Returns:
            Final response with tool results incorporated
        """
        # First pass: Generate response
        response = await llm_generate_func(message)

        # Check for tool calls
        tool_call = self.parse_tool_call(response)

        if tool_call:
            # Execute tool
            tool_result = self.execute_tool(
                tool_call["tool"],
                **tool_call["args"]
            )

            # Second pass: Generate response with tool result
            tool_context = f"""
Your previous response included a tool call that has been executed:

Tool: {tool_call['tool']}
Result: {tool_result}

Now generate your final response to the user incorporating this result.
Do NOT include another TOOL: call. Use the result naturally in your response.
"""

            final_response = await llm_generate_func(
                message,
                additional_context=tool_context
            )

            return final_response

        return response
