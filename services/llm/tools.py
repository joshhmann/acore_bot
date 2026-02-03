"""Enhanced tool system with anti-hallucination measures and OpenAI function calling support."""

import logging
import random
import json
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union, Set
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


class ToolParameter:
    """Definition of a tool parameter."""

    def __init__(
        self,
        name: str,
        param_type: type,
        description: str,
        required: bool = False,
        default: Any = None,
        enum_values: Optional[List[str]] = None,
    ):
        """
        Initialize a tool parameter.

        Args:
            name: Parameter name
            param_type: Python type (str, int, float, bool)
            description: Human-readable description
            required: Whether parameter is required
            default: Default value if optional
            enum_values: List of allowed values for enum-like parameters
        """
        self.name = name
        self.param_type = param_type
        self.description = description
        self.required = required
        self.default = default
        self.enum_values = enum_values

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling schema format."""
        schema = {
            "type": "object",
            "properties": {
                self.name: {
                    "type": self._get_openai_type(),
                    "description": self.description,
                }
            },
            "required": [self.name] if self.required else [],
        }

        if self.enum_values:
            schema["properties"][self.name]["enum"] = self.enum_values

        return schema

    def _get_openai_type(self) -> str:
        """Map Python type to OpenAI schema type."""
        type_map: Dict[type, str] = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
        }
        return type_map.get(self.param_type, "string")

    def coerce_value(self, value: Any) -> Any:
        """Coerce a value to the parameter's type."""
        if value is None:
            if self.default is not None:
                return self.default
            if self.required:
                raise ValueError(f"Required parameter '{self.name}' is missing")
            return None

        if self.param_type == str:
            return str(value)
        elif self.param_type == int:
            return int(value)
        elif self.param_type == float:
            return float(value)
        elif self.param_type == bool:
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return bool(value)
        return value


class ToolDefinition:
    """Complete definition of a tool for OpenAI function calling."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: List[ToolParameter],
        category: str = "general",
    ):
        """
        Initialize a tool definition.

        Args:
            name: Tool name (must be valid Python identifier)
            description: Human-readable description of what the tool does
            parameters: List of ToolParameter objects
            category: Category for grouping tools
        """
        self.name = name
        self.description = description
        self.parameters = parameters
        self.category = category

    def to_openai_function(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format."""
        properties = {}
        required_fields = []

        for param in self.parameters:
            param_schema = {
                "type": param._get_openai_type(),
                "description": param.description,
            }
            if param.enum_values:
                param_schema["enum"] = param.enum_values
            properties[param.name] = param_schema
            if param.required:
                required_fields.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required_fields,
                },
            },
        }


class EnhancedToolSystem:
    """
    Comprehensive tool system to prevent LLM hallucinations.

    Philosophy: Give the LLM tools for facts it shouldn't guess.
    - Time/dates → tools, not hallucinated
    - Math → tools, not approximated
    - Conversions → tools, not estimated
    - User facts → database, not invented

    Supports both legacy regex-based parsing and modern OpenAI function calling.
    """

    TOOL_SCHEMA: List[Dict[str, Any]] = []

    def __init__(self, use_function_calling: bool = False):
        """
        Initialize enhanced tool system.

        Args:
            use_function_calling: Whether to use OpenAI function calling format
        """
        self.tools: Dict[str, callable] = {}
        self.tool_definitions: Dict[str, ToolDefinition] = {}
        self._use_function_calling = use_function_calling
        self._enabled_tools: set = set()
        self._register_all_tools()
        self._build_tool_schema()
        logger.info(
            f"Enhanced tool system initialized with {len(self.tools)} tools, "
            f"function_calling_mode={use_function_calling}"
        )

    def _build_tool_schema(self) -> None:
        """Build OpenAI function calling schema from registered tools."""
        self.TOOL_SCHEMA = []
        for name, definition in self.tool_definitions.items():
            self.TOOL_SCHEMA.append(definition.to_openai_function())
            self._enabled_tools.add(name)

    def _register_all_tools(self) -> None:
        """Register all available tools with their definitions."""
        self._register_time_tools()
        self._register_math_tools()
        self._register_conversion_tools()
        self._register_randomness_tools()
        self._register_text_tools()
        self._register_validation_tools()
        self._register_image_tools()
        self._register_code_tools()

    def _register_tool(
        self, name: str, function: callable, definition: ToolDefinition
    ) -> None:
        """Register a tool with its implementation and definition."""
        self.tools[name] = function
        self.tool_definitions[name] = definition

    def _register_time_tools(self) -> None:
        """Register time and date tools."""
        self._register_tool(
            "get_current_time",
            self._get_current_time,
            ToolDefinition(
                name="get_current_time",
                description="Get the current time in 12-hour format (e.g., '3:47 PM'). Use this whenever the user asks for the current time.",
                parameters=[],
                category="time",
            ),
        )

        self._register_tool(
            "get_current_date",
            self._get_current_date,
            ToolDefinition(
                name="get_current_date",
                description="Get the current date in YYYY-MM-DD format with day of week. Use this when the user asks for today's date.",
                parameters=[],
                category="time",
            ),
        )

        self._register_tool(
            "get_time_in_timezone",
            self._get_time_in_timezone,
            ToolDefinition(
                name="get_time_in_timezone",
                description="Get the current time in a specific timezone. Use IANA timezone format like 'America/New_York' or 'Europe/London'.",
                parameters=[
                    ToolParameter(
                        name="timezone",
                        param_type=str,
                        description="IANA timezone name (e.g., 'America/New_York', 'Europe/London', 'Asia/Tokyo')",
                        required=True,
                    )
                ],
                category="time",
            ),
        )

        self._register_tool(
            "calculate_time_offset",
            self._calculate_time_offset,
            ToolDefinition(
                name="calculate_time_offset",
                description="Calculate the time X hours/minutes in the past or future. Useful for 'what time was it 3 hours ago?' or 'what time will it be in 2 hours?'",
                parameters=[
                    ToolParameter(
                        name="hours",
                        param_type=int,
                        description="Number of hours to offset (0-23)",
                        required=False,
                        default=0,
                    ),
                    ToolParameter(
                        name="minutes",
                        param_type=int,
                        description="Number of minutes to offset (0-59)",
                        required=False,
                        default=0,
                    ),
                    ToolParameter(
                        name="direction",
                        param_type=str,
                        description="Whether to calculate time in the 'past' or 'future'",
                        required=True,
                        enum_values=["past", "future"],
                    ),
                ],
                category="time",
            ),
        )

        self._register_tool(
            "time_until",
            self._time_until,
            ToolDefinition(
                name="time_until",
                description="Calculate the time remaining until a specific time today. Format: 'HH:MM' or 'HH:MM AM/PM'.",
                parameters=[
                    ToolParameter(
                        name="target_time",
                        param_type=str,
                        description="Target time in format 'HH:MM' or 'HH:MM AM/PM' (e.g., '14:30' or '2:30 PM')",
                        required=True,
                    )
                ],
                category="time",
            ),
        )

        self._register_tool(
            "time_since",
            self._time_since,
            ToolDefinition(
                name="time_since",
                description="Calculate what time it was X hours/minutes ago.",
                parameters=[
                    ToolParameter(
                        name="hours",
                        param_type=int,
                        description="Number of hours ago (0-23)",
                        required=False,
                        default=0,
                    ),
                    ToolParameter(
                        name="minutes",
                        param_type=int,
                        description="Number of minutes ago (0-59)",
                        required=False,
                        default=0,
                    ),
                ],
                category="time",
            ),
        )

        self._register_tool(
            "day_of_week",
            self._day_of_week,
            ToolDefinition(
                name="day_of_week",
                description="Get the day of week for a specific date. Format: YYYY-MM-DD. If no date provided, returns today's day of week.",
                parameters=[
                    ToolParameter(
                        name="date",
                        param_type=str,
                        description="Date in YYYY-MM-DD format (e.g., '2024-12-25'). Leave empty for today.",
                        required=False,
                        default=None,
                    )
                ],
                category="time",
            ),
        )

    def _register_math_tools(self) -> None:
        """Register math and calculation tools."""
        self._register_tool(
            "calculate",
            self._calculate,
            ToolDefinition(
                name="calculate",
                description="Safely evaluate a mathematical expression. Supports: +, -, *, /, %, parentheses. Use for any calculation the user asks for.",
                parameters=[
                    ToolParameter(
                        name="expression",
                        param_type=str,
                        description="Mathematical expression to evaluate (e.g., '2 + 2 * 5', '(10 + 5) / 2', '15 * 0.2')",
                        required=True,
                    )
                ],
                category="math",
            ),
        )

        self._register_tool(
            "calculate_percentage",
            self._calculate_percentage,
            ToolDefinition(
                name="calculate_percentage",
                description="Calculate what percentage one value is of another. Use for 'what percentage of X is Y?' or 'X is what percent of Y?'",
                parameters=[
                    ToolParameter(
                        name="value",
                        param_type=float,
                        description="The value to calculate percentage for",
                        required=True,
                    ),
                    ToolParameter(
                        name="total",
                        param_type=float,
                        description="The total value (the whole)",
                        required=True,
                    ),
                ],
                category="math",
            ),
        )

        self._register_tool(
            "round_number",
            self._round_number,
            ToolDefinition(
                name="round_number",
                description="Round a number to a specified number of decimal places.",
                parameters=[
                    ToolParameter(
                        name="number",
                        param_type=float,
                        description="The number to round",
                        required=True,
                    ),
                    ToolParameter(
                        name="decimals",
                        param_type=int,
                        description="Number of decimal places (default: 2)",
                        required=False,
                        default=2,
                    ),
                ],
                category="math",
            ),
        )

    def _register_conversion_tools(self) -> None:
        """Register unit conversion tools."""
        self._register_tool(
            "convert_temperature",
            self._convert_temperature,
            ToolDefinition(
                name="convert_temperature",
                description="Convert temperature between Fahrenheit, Celsius, and Kelvin.",
                parameters=[
                    ToolParameter(
                        name="value",
                        param_type=float,
                        description="Temperature value to convert",
                        required=True,
                    ),
                    ToolParameter(
                        name="from_unit",
                        param_type=str,
                        description="Source unit: 'F' for Fahrenheit, 'C' for Celsius, 'K' for Kelvin",
                        required=True,
                        enum_values=["F", "C", "K"],
                    ),
                    ToolParameter(
                        name="to_unit",
                        param_type=str,
                        description="Target unit: 'F' for Fahrenheit, 'C' for Celsius, 'K' for Kelvin",
                        required=True,
                        enum_values=["F", "C", "K"],
                    ),
                ],
                category="conversion",
            ),
        )

        self._register_tool(
            "convert_distance",
            self._convert_distance,
            ToolDefinition(
                name="convert_distance",
                description="Convert distance between common units: miles, kilometers, meters, feet, inches.",
                parameters=[
                    ToolParameter(
                        name="value",
                        param_type=float,
                        description="Distance value to convert",
                        required=True,
                    ),
                    ToolParameter(
                        name="from_unit",
                        param_type=str,
                        description="Source unit: 'mi', 'km', 'm', 'ft', 'in'",
                        required=True,
                        enum_values=["mi", "km", "m", "ft", "in"],
                    ),
                    ToolParameter(
                        name="to_unit",
                        param_type=str,
                        description="Target unit: 'mi', 'km', 'm', 'ft', 'in'",
                        required=True,
                        enum_values=["mi", "km", "m", "ft", "in"],
                    ),
                ],
                category="conversion",
            ),
        )

        self._register_tool(
            "convert_weight",
            self._convert_weight,
            ToolDefinition(
                name="convert_weight",
                description="Convert weight between common units: pounds, kilograms, ounces, grams.",
                parameters=[
                    ToolParameter(
                        name="value",
                        param_type=float,
                        description="Weight value to convert",
                        required=True,
                    ),
                    ToolParameter(
                        name="from_unit",
                        param_type=str,
                        description="Source unit: 'lbs', 'kg', 'oz', 'g'",
                        required=True,
                        enum_values=["lbs", "kg", "oz", "g"],
                    ),
                    ToolParameter(
                        name="to_unit",
                        param_type=str,
                        description="Target unit: 'lbs', 'kg', 'oz', 'g'",
                        required=True,
                        enum_values=["lbs", "kg", "oz", "g"],
                    ),
                ],
                category="conversion",
            ),
        )

        self._register_tool(
            "convert_currency",
            self._convert_currency,
            ToolDefinition(
                name="convert_currency",
                description="Currency conversion. Note: Requires a live API for accurate rates. This tool provides guidance on how to get conversion rates.",
                parameters=[
                    ToolParameter(
                        name="amount",
                        param_type=float,
                        description="Amount to convert",
                        required=True,
                    ),
                    ToolParameter(
                        name="from_curr",
                        param_type=str,
                        description="Source currency code (e.g., 'USD', 'EUR', 'GBP')",
                        required=True,
                    ),
                    ToolParameter(
                        name="to_curr",
                        param_type=str,
                        description="Target currency code (e.g., 'USD', 'EUR', 'GBP')",
                        required=True,
                    ),
                ],
                category="conversion",
            ),
        )

    def _register_randomness_tools(self) -> None:
        """Register randomness tools."""
        self._register_tool(
            "roll_dice",
            self._roll_dice,
            ToolDefinition(
                name="roll_dice",
                description="Roll dice in standard RPG notation. Examples: '1d6', '2d20', '3d6+5', '4d10-2'. Returns individual rolls and total.",
                parameters=[
                    ToolParameter(
                        name="dice",
                        param_type=str,
                        description="Dice notation (e.g., '1d6', '2d20+5', '3d6-2'). Format: [num]d[sides][+/-modifier]",
                        required=True,
                    )
                ],
                category="random",
            ),
        )

        self._register_tool(
            "random_number",
            self._random_number,
            ToolDefinition(
                name="random_number",
                description="Generate a random number within a specified range.",
                parameters=[
                    ToolParameter(
                        name="min",
                        param_type=int,
                        description="Minimum value (inclusive)",
                        required=False,
                        default=1,
                    ),
                    ToolParameter(
                        name="max",
                        param_type=int,
                        description="Maximum value (inclusive)",
                        required=False,
                        default=100,
                    ),
                ],
                category="random",
            ),
        )

        self._register_tool(
            "random_choice",
            self._random_choice,
            ToolDefinition(
                name="random_choice",
                description="Randomly select one option from a list of choices.",
                parameters=[
                    ToolParameter(
                        name="options",
                        param_type=str,
                        description="Comma-separated options (e.g., 'pizza, pasta, salad' or 'red, blue, green')",
                        required=True,
                    )
                ],
                category="random",
            ),
        )

    def _register_text_tools(self) -> None:
        """Register text processing tools."""
        self._register_tool(
            "count_words",
            self._count_words,
            ToolDefinition(
                name="count_words",
                description="Count the number of words in a text string.",
                parameters=[
                    ToolParameter(
                        name="text",
                        param_type=str,
                        description="The text to count words in",
                        required=True,
                    )
                ],
                category="text",
            ),
        )

        self._register_tool(
            "count_characters",
            self._count_characters,
            ToolDefinition(
                name="count_characters",
                description="Count the number of characters in a text string, optionally excluding spaces.",
                parameters=[
                    ToolParameter(
                        name="text",
                        param_type=str,
                        description="The text to count characters in",
                        required=True,
                    ),
                    ToolParameter(
                        name="include_spaces",
                        param_type=bool,
                        description="Whether to include spaces in the count (default: True)",
                        required=False,
                        default=True,
                    ),
                ],
                category="text",
            ),
        )

    def _register_validation_tools(self) -> None:
        """Register validation tools."""
        self._register_tool(
            "validate_url",
            self._validate_url,
            ToolDefinition(
                name="validate_url",
                description="Check if a URL is syntactically valid. Does not verify the URL actually exists.",
                parameters=[
                    ToolParameter(
                        name="url",
                        param_type=str,
                        description="The URL to validate",
                        required=True,
                    )
                ],
                category="validation",
            ),
        )

        self._register_tool(
            "validate_email",
            self._validate_email,
            ToolDefinition(
                name="validate_email",
                description="Check if an email address is syntactically valid. Does not verify the email actually exists.",
                parameters=[
                    ToolParameter(
                        name="email",
                        param_type=str,
                        description="The email address to validate",
                        required=True,
                    )
                ],
                category="validation",
            ),
        )

    def _register_image_tools(self) -> None:
        """Register image generation tools."""
        self._register_tool(
            "generate_image",
            self._generate_image,
            ToolDefinition(
                name="generate_image",
                description="Generate images from text prompts using DALL-E 3 or Stable Diffusion. Requires IMAGE_GENERATION_ENABLED=true and API keys configured.",
                parameters=[
                    ToolParameter(
                        name="prompt",
                        param_type=str,
                        description="Text description of the image to generate",
                        required=True,
                    ),
                    ToolParameter(
                        name="size",
                        param_type=str,
                        description="Image size: 1024x1024, 1024x1792, or 1792x1024",
                        required=False,
                        default="1024x1024",
                        enum_values=[
                            "1024x1024",
                            "1024x1792",
                            "1792x1024",
                            "512x512",
                            "256x256",
                        ],
                    ),
                    ToolParameter(
                        name="quality",
                        param_type=str,
                        description="Image quality: standard or hd (DALL-E 3 only)",
                        required=False,
                        default="standard",
                        enum_values=["standard", "hd"],
                    ),
                    ToolParameter(
                        name="style",
                        param_type=str,
                        description="Image style: vivid (natural) or natural (DALL-E 3 only)",
                        required=False,
                        default="vivid",
                        enum_values=["vivid", "natural"],
                    ),
                ],
                category="image",
            ),
        )

        self._register_tool(
            "edit_image",
            self._edit_image,
            ToolDefinition(
                name="edit_image",
                description="Edit an image using DALL-E 2 by providing a mask. The transparent area of the mask will be regenerated.",
                parameters=[
                    ToolParameter(
                        name="image_path",
                        param_type=str,
                        description="Path to the image file to edit",
                        required=True,
                    ),
                    ToolParameter(
                        name="mask_path",
                        param_type=str,
                        description="Path to the mask image (transparent areas will be edited)",
                        required=False,
                        default=None,
                    ),
                    ToolParameter(
                        name="prompt",
                        param_type=str,
                        description="Text description of how to edit the image",
                        required=True,
                    ),
                ],
                category="image",
            ),
        )

        self._register_tool(
            "create_image_variation",
            self._create_image_variation,
            ToolDefinition(
                name="create_image_variation",
                description="Create variations of an existing image using DALL-E 2.",
                parameters=[
                    ToolParameter(
                        name="image_path",
                        param_type=str,
                        description="Path to the image file to create variations of",
                        required=True,
                    ),
                    ToolParameter(
                        name="n",
                        param_type=int,
                        description="Number of variations to create (1-10)",
                        required=False,
                        default=1,
                    ),
                ],
                category="image",
            ),
        )

    def _register_code_tools(self) -> None:
        """Register code execution and analysis tools."""
        self._register_tool(
            "run_python",
            self._run_python,
            ToolDefinition(
                name="run_python",
                description="Execute Python code in a sandboxed environment. Use for calculations, data processing, and running Python scripts.",
                parameters=[
                    ToolParameter(
                        name="code",
                        param_type=str,
                        description="Python code to execute",
                        required=True,
                    ),
                    ToolParameter(
                        name="timeout",
                        param_type=int,
                        description="Maximum execution time in seconds",
                        required=False,
                        default=30,
                    ),
                    ToolParameter(
                        name="capture_output",
                        param_type=bool,
                        description="Whether to capture stdout/stderr",
                        required=False,
                        default=True,
                    ),
                ],
                category="code",
            ),
        )

        self._register_tool(
            "run_bash",
            self._run_bash,
            ToolDefinition(
                name="run_bash",
                description="Execute bash commands safely. Dangerous commands are blocked. Use for system operations, git, file management, etc.",
                parameters=[
                    ToolParameter(
                        name="command",
                        param_type=str,
                        description="Bash command to execute",
                        required=True,
                    ),
                    ToolParameter(
                        name="timeout",
                        param_type=int,
                        description="Maximum execution time in seconds",
                        required=False,
                        default=60,
                    ),
                    ToolParameter(
                        name="working_dir",
                        param_type=str,
                        description="Working directory for command execution",
                        required=False,
                        default=None,
                    ),
                ],
                category="code",
            ),
        )

        self._register_tool(
            "explain_code",
            self._explain_code,
            ToolDefinition(
                name="explain_code",
                description="Get an AI-powered explanation of code in any language. Returns summary, complexity, key points, and suggestions.",
                parameters=[
                    ToolParameter(
                        name="code",
                        param_type=str,
                        description="Code to explain",
                        required=True,
                    ),
                    ToolParameter(
                        name="language",
                        param_type=str,
                        description="Programming language of the code",
                        required=True,
                    ),
                    ToolParameter(
                        name="detail_level",
                        param_type=str,
                        description="Level of detail: low, medium, or high",
                        required=False,
                        default="medium",
                        enum_values=["low", "medium", "high"],
                    ),
                ],
                category="code",
            ),
        )

        self._register_tool(
            "analyze_code",
            self._analyze_code,
            ToolDefinition(
                name="analyze_code",
                description="Perform static analysis on code to find bugs, security issues, and style problems.",
                parameters=[
                    ToolParameter(
                        name="code",
                        param_type=str,
                        description="Code to analyze",
                        required=True,
                    ),
                    ToolParameter(
                        name="language",
                        param_type=str,
                        description="Programming language of the code",
                        required=True,
                    ),
                ],
                category="code",
            ),
        )

    def get_tool_descriptions(self) -> str:
        """
        Get formatted descriptions of all tools for the LLM (legacy format).

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

    def get_function_calling_context(self) -> List[Dict[str, Any]]:
        """
        Get the OpenAI function calling schema for available tools.

        Returns:
            List of function definitions for OpenAI API
        """
        return self.TOOL_SCHEMA

    def get_enabled_tools(self) -> List[str]:
        """Get list of enabled tool names."""
        return list(self._enabled_tools)

    def enable_tool(self, tool_name: str) -> bool:
        """Enable a specific tool."""
        if tool_name in self.tools:
            self._enabled_tools.add(tool_name)
            logger.info(f"Tool enabled: {tool_name}")
            return True
        return False

    def disable_tool(self, tool_name: str) -> bool:
        """Disable a specific tool."""
        if tool_name in self._enabled_tools:
            self._enabled_tools.remove(tool_name)
            logger.info(f"Tool disabled: {tool_name}")
            return True
        return False

    def set_function_calling_mode(self, enabled: bool) -> None:
        """Enable or disable function calling mode."""
        self._use_function_calling = enabled
        logger.info(f"Function calling mode: {enabled}")

    def is_using_function_calling(self) -> bool:
        """Check if function calling mode is enabled."""
        return self._use_function_calling

    # ==================== TIME & DATE TOOLS ====================

    def _get_current_time(self) -> str:
        """Get current time in 12-hour format."""
        now = datetime.now()
        return now.strftime("%I:%M %p").lstrip("0")

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
        self, hours: int = 0, minutes: int = 0, direction: str = "future"
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

        return target.strftime("%I:%M %p on %A, %B %d").lstrip("0")

    def _time_until(self, target_time: str) -> str:
        """
        Calculate time until a specific time today.

        Args:
            target_time: Time in format "HH:MM" or "HH:MM AM/PM"
        """
        try:
            now = datetime.now()

            if "AM" in target_time.upper() or "PM" in target_time.upper():
                target = datetime.strptime(target_time, "%I:%M %p")
            else:
                target = datetime.strptime(target_time, "%H:%M")

            target = target.replace(year=now.year, month=now.month, day=now.day)

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

    def _day_of_week(self, date: Optional[str] = None) -> str:
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
            allowed = set("0123456789+-*/().% ")
            if not all(c in allowed for c in expression.replace(" ", "")):
                return "Error: Expression contains invalid characters"

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
            if from_unit.upper() == "F":
                celsius = (value - 32) * 5 / 9
            elif from_unit.upper() == "C":
                celsius = value
            elif from_unit.upper() == "K":
                celsius = value - 273.15
            else:
                return f"Error: Invalid unit '{from_unit}'"

            if to_unit.upper() == "F":
                result = (celsius * 9 / 5) + 32
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
                return "Error: Invalid unit. Use: mi, km, m, ft, in"

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
                return "Error: Invalid unit. Use: kg, lbs, oz, g"

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
                return "Error: Invalid dice notation. Use format: '2d6' or '1d20+5'"

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
            r"^https?://"
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
            r"localhost|"
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
            r"(?::\d+)?"
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )

        is_valid = bool(url_pattern.match(url))
        return f"URL '{url}' is {'valid' if is_valid else 'invalid'}"

    def _validate_email(self, email: str) -> str:
        """Validate if string is a valid email."""
        email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

        is_valid = bool(email_pattern.match(email))
        return f"Email '{email}' is {'valid' if is_valid else 'invalid'}"

    # ==================== TOOL EXECUTION ====================

    def parse_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Parse tool call from LLM response (legacy regex-based format).

        Args:
            text: LLM response text

        Returns:
            Dict with tool name and arguments, or None
        """
        pattern = r"TOOL:\s*(\w+)\((.*?)\)"
        match = re.search(pattern, text, re.IGNORECASE)

        if not match:
            return None

        tool_name = match.group(1)
        args_str = match.group(2)

        args = {}
        if args_str.strip():
            arg_pattern = r'(\w+)\s*=\s*(["\'])(.*?)\2|(\w+)\s*=\s*([^,\)]+)'

            for arg_match in re.finditer(arg_pattern, args_str):
                if arg_match.group(1):
                    key = arg_match.group(1)
                    value = arg_match.group(3)
                else:
                    key = arg_match.group(4)
                    value = arg_match.group(5).strip()

                try:
                    value = int(value)
                except ValueError:
                    try:
                        value = float(value)
                    except ValueError:
                        if value.lower() == "true":
                            value = True
                        elif value.lower() == "false":
                            value = False

                args[key] = value

        return {"tool": tool_name, "args": args, "full_match": match.group(0)}

    def parse_function_call(self, response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse function call from OpenAI response format.

        Handles both modern tool_calls format and legacy function_call format.
        Supports both streaming and non-streaming responses.

        Args:
            response: OpenAI API response dict

        Returns:
            Dict with tool name and arguments, or None if no function call
        """
        if not response or not isinstance(response, dict):
            return None

        tool_calls = (
            response.get("choices", [{}])[0].get("message", {}).get("tool_calls")
        )
        if tool_calls:
            if len(tool_calls) > 1:
                logger.warning(f"Multiple tool calls detected: {len(tool_calls)}")
            call = tool_calls[0]
            return {
                "tool": call["function"]["name"],
                "args": json.loads(call["function"]["arguments"]),
                "tool_call_id": call.get("id"),
            }

        legacy_function_call = (
            response.get("choices", [{}])[0].get("message", {}).get("function_call")
        )
        if legacy_function_call:
            return {
                "tool": legacy_function_call["name"],
                "args": json.loads(legacy_function_call["arguments"]),
            }

        return None

    def parse_streaming_tool_call(
        self, chunk: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Parse function call from streaming OpenAI response.

        Streaming responses accumulate tool calls across chunks.

        Args:
            chunk: Individual chunk from streaming response

        Returns:
            Dict with tool name and arguments if complete, or None
        """
        if not chunk or not isinstance(chunk, dict):
            return None

        delta = chunk.get("choices", [{}])[0].get("delta", {})

        tool_calls = delta.get("tool_calls")
        if tool_calls:
            call = tool_calls[0]
            function = call.get("function", {})
            name = function.get("name")
            arguments = function.get("arguments", "")

            if name and arguments:
                try:
                    args = json.loads(arguments)
                    return {
                        "tool": name,
                        "args": args,
                        "tool_call_id": call.get("id"),
                    }
                except json.JSONDecodeError:
                    logger.debug(f"Partial function arguments: {arguments}")
                    return None

        return None

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

        if tool_name not in self._enabled_tools:
            return f"Error: Tool '{tool_name}' is disabled"

        try:
            result = self.tools[tool_name](**kwargs)
            logger.debug(f"Tool executed: {tool_name}({kwargs}) = {result}")
            return result
        except TypeError as e:
            logger.error(f"Invalid arguments for {tool_name}: {e}")
            return f"Error: Invalid arguments for {tool_name}: {e}"
        except Exception as e:
            logger.error(f"Tool {tool_name} execution error: {e}")
            return f"Error executing {tool_name}: {e}"

    def execute_function_call(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a function call with properly coerced arguments.

        Args:
            tool_name: Name of the tool to execute
            arguments: Raw arguments from OpenAI function call

        Returns:
            Tool result as string
        """
        if tool_name not in self.tool_definitions:
            return f"Error: Unknown tool '{tool_name}'"

        definition = self.tool_definitions[tool_name]
        coerced_args = {}

        for param in definition.parameters:
            param_name = param.name
            if param_name in arguments:
                value = arguments[param_name]
                try:
                    coerced_args[param_name] = param.coerce_value(value)
                except (ValueError, TypeError) as e:
                    return f"Error: Invalid value for '{param_name}': {e}"
            elif param.required:
                return f"Error: Missing required parameter '{param_name}'"

        return self.execute_tool(tool_name, **coerced_args)

    async def process_message_with_tools(
        self, message: str, llm_generate_func, system_prompt: Optional[str] = None
    ) -> str:
        """
        Process a message, execute any tool calls, and regenerate response.

        Args:
            message: User message
            llm_generate_func: Async function to generate LLM response
            system_prompt: Optional system prompt

        Returns:
            Final response with tool results incorporated
        """
        if self._use_function_calling:
            return await self._process_with_function_calling(
                message, llm_generate_func, system_prompt
            )
        else:
            return await self._process_with_regex(
                message, llm_generate_func, system_prompt
            )

    async def _process_with_regex(
        self, message: str, llm_generate_func, system_prompt: Optional[str] = None
    ) -> str:
        """
        Process message using legacy regex-based tool parsing.
        """
        prompt = message
        if system_prompt:
            prompt = f"{system_prompt}\n\n{prompt}"

        response = await llm_generate_func(prompt)
        tool_call = self.parse_tool_call(response)

        if tool_call:
            tool_result = self.execute_tool(tool_call["tool"], **tool_call["args"])

            tool_context = f"""
Your previous response included a tool call that has been executed:

Tool: {tool_call["tool"]}
Result: {tool_result}

Now generate your final response to the user incorporating this result.
Do NOT include another TOOL: call. Use the result naturally in your response.
"""

            final_response = await llm_generate_func(
                message, additional_context=tool_context
            )

            return final_response

        return response

    async def _process_with_function_calling(
        self, message: str, llm_generate_func, system_prompt: Optional[str] = None
    ) -> str:
        """
        Process message using OpenAI function calling format.
        """
        tools = self.get_function_calling_context()

        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}]
        else:
            messages = []

        messages.append({"role": "user", "content": message})

        response = await llm_generate_func(
            messages=messages, tools=tools, tool_choice="auto"
        )

        tool_calls = self.parse_function_call(response)

        if tool_calls:
            tool_name = tool_calls["tool"]
            args = tool_calls.get("args", {})
            tool_result = self.execute_function_call(tool_name, args)

            messages.append(response["choices"][0]["message"])
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_calls.get("tool_call_id"),
                    "name": tool_name,
                    "content": tool_result,
                }
            )

            final_response = await llm_generate_func(messages=messages)

            if isinstance(final_response, dict):
                return (
                    final_response.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
            return final_response

        if isinstance(response, dict):
            return (
                response.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
        return response

    async def _generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
        style: str = "vivid",
    ) -> str:
        """Generate image using configured provider."""
        from services.llm.image_tools import image_tool_system

        return await image_tool_system.generate_image(prompt, size, quality, style)

    async def _edit_image(
        self, image_path: str, mask_path: Optional[str] = None, prompt: str = ""
    ) -> str:
        """Edit image with DALL-E edit endpoint."""
        from services.llm.image_tools import image_tool_system

        return await image_tool_system.edit_image(image_path, mask_path, prompt)

    async def _create_image_variation(self, image_path: str, n: int = 1) -> str:
        """Create variations of an image."""
        from services.llm.image_tools import image_tool_system

        return await image_tool_system.create_variation(image_path, n)

    async def _run_python(
        self, code: str, timeout: int = 30, capture_output: bool = True
    ) -> str:
        """Execute Python code in sandboxed environment."""
        from services.llm.code_tools import code_tool_system

        return await code_tool_system.run_python(code, timeout, capture_output)

    async def _run_bash(
        self, command: str, timeout: int = 60, working_dir: Optional[str] = None
    ) -> str:
        """Execute bash command safely."""
        from services.llm.code_tools import code_tool_system

        return await code_tool_system.run_bash(command, timeout, working_dir)

    async def _explain_code(
        self, code: str, language: str, detail_level: str = "medium"
    ) -> str:
        """Get LLM-powered code explanation."""
        from services.llm.code_tools import code_tool_system

        return await code_tool_system.explain_code(code, language, detail_level)

    async def _analyze_code(self, code: str, language: str) -> str:
        """Static analysis for bugs, security issues, style."""
        from services.llm.code_tools import code_tool_system

        return await code_tool_system.analyze_code(code, language)


def format_tool_result_message(
    tool_name: str, result: str, tool_call_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format a tool result as a message for the LLM.

    Args:
        tool_name: Name of the tool that was executed
        result: Result from the tool execution
        tool_call_id: Optional tool call ID from OpenAI

    Returns:
        Message dict formatted for LLM API
    """
    message = {
        "role": "tool",
        "name": tool_name,
        "content": result,
    }

    if tool_call_id:
        message["tool_call_id"] = tool_call_id

    return message


def create_tool_call_message(
    tool_name: str, arguments: Dict[str, Any], tool_call_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a tool call message for the LLM.

    Args:
        tool_name: Name of the tool to call
        arguments: Arguments to pass to the tool
        tool_call_id: Optional tool call ID

    Returns:
        Message dict formatted for LLM API
    """
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": tool_call_id or f"call_{tool_name}_{id(arguments)}",
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(arguments),
                },
            }
        ],
    }

    return message


def is_function_calling_response(response: Dict[str, Any]) -> bool:
    """
    Check if an OpenAI response contains function/tool calls.

    Args:
        response: OpenAI API response dict

    Returns:
        True if response contains function calls
    """
    if not response or not isinstance(response, dict):
        return False

    message = response.get("choices", [{}])[0].get("message", {})

    return bool(message.get("tool_calls")) or bool(message.get("function_call"))
