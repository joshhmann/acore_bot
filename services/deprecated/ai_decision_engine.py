"""AI-First Decision Engine - Makes decisions based on framework rules."""
import logging
import random
from typing import Dict, Any, Optional, List
from datetime import datetime
from services.persona.system import CompiledPersona
from services.llm.tools import EnhancedToolSystem

logger = logging.getLogger(__name__)


class AIDecisionEngine:
    """
    AI-first decision making system.

    Uses framework rules and LLM reasoning to decide:
    - When to respond
    - How to respond
    - When to use tools
    - What tone/style to use
    """

    def __init__(self, ollama_service, tool_system: EnhancedToolSystem = None):
        """
        Initialize decision engine.

        Args:
            ollama_service: Ollama service for LLM generation
            tool_system: Tool system for function calling
        """
        self.ollama = ollama_service
        self.tools = tool_system or EnhancedToolSystem()

        # Current active persona
        self.current_persona: Optional[CompiledPersona] = None

        # Decision tracking
        self.last_response_time = {}
        self.last_interjection = datetime.now()
        self.mood_state = "neutral"
        self.spontaneity_counter = 0

        logger.info("AI Decision Engine initialized")

    def set_persona(self, persona: CompiledPersona):
        """Set the active persona for decision making."""
        self.current_persona = persona
        logger.info(f"Decision engine using persona: {persona.persona_id}")

    async def should_respond(
        self,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Decide if bot should respond to this message.

        Args:
            message: User message
            context: Context dictionary with channel_id, user_id, etc.

        Returns:
            Decision dict with:
            - should_respond: bool
            - reason: str
            - priority: str (low/medium/high)
            - suggested_style: str
        """
        if not self.current_persona:
            return {"should_respond": False, "reason": "No persona loaded"}

        framework = self.current_persona.framework
        character = self.current_persona.character
        decision_rules = framework.decision_making.get("when_to_respond", {})

        # Check explicit response triggers
        if context.get("mentioned"):
            return {
                "should_respond": True,
                "reason": "mentioned",
                "priority": "high",
                "suggested_style": "direct"
            }

        if decision_rules.get("question_asked") == "always" and "?" in message:
            return {
                "should_respond": True,
                "reason": "question_asked",
                "priority": "high",
                "suggested_style": "helpful"
            }

        # Check framework-specific triggers
        if decision_rules.get("someone_wrong") and self._detect_incorrect_info(message):
            return {
                "should_respond": True,
                "reason": "someone_wrong",
                "priority": "medium",
                "suggested_style": "corrective"
            }

        if decision_rules.get("good_banter") and self._detect_banter_opportunity(message):
            return {
                "should_respond": True,
                "reason": "good_banter",
                "priority": "medium",
                "suggested_style": "playful"
            }

        # Check if in active conversation
        channel_id = context.get("channel_id")
        if decision_rules.get("active_conversation") == "usually":
            if self._is_in_active_conversation(channel_id):
                # 70% chance to respond in active conversation
                if random.random() < 0.7:
                    return {
                        "should_respond": True,
                        "reason": "active_conversation",
                        "priority": "medium",
                        "suggested_style": "conversational"
                    }

        # Check for interesting topic
        if decision_rules.get("interesting_topic"):
            if self._is_interesting_topic(message, character):
                return {
                    "should_respond": True,
                    "reason": "interesting_topic",
                    "priority": "low",
                    "suggested_style": "engaged"
                }

        # Check for spontaneous interjection (framework-specific)
        if self._should_interject_spontaneously(framework):
            return {
                "should_respond": True,
                "reason": "spontaneous",
                "priority": "low",
                "suggested_style": "random"
            }

        return {
            "should_respond": False,
            "reason": "no_trigger_matched",
            "priority": "none",
            "suggested_style": None
        }

    async def generate_response(
        self,
        message: str,
        context: Dict[str, Any],
        style_hint: str = None
    ) -> str:
        """
        Generate response using active persona and framework.

        Args:
            message: User message
            context: Context dictionary
            style_hint: Optional style suggestion from decision

        Returns:
            Generated response
        """
        if not self.current_persona:
            return "Error: No persona loaded"

        # Build complete prompt
        full_prompt = self._build_generation_prompt(message, context, style_hint)

        # Generate initial response
        response = await self.ollama.generate(
            prompt=full_prompt,
            system_prompt=self.current_persona.system_prompt,
            temperature=self._get_temperature_for_framework(),
            max_tokens=self._get_max_tokens_for_framework()
        )

        # Clean thinking process
        from utils.response_validator import ResponseValidator
        response = ResponseValidator.clean_thinking_process(response)

        # Check for tool calls
        tool_call = self.tools.parse_tool_call(response)

        if tool_call:
            # Execute tool
            tool_result = self.tools.execute_tool(
                tool_call["tool"],
                **tool_call["args"]
            )

            # Regenerate with tool result
            tool_context = f"""
Your previous response included a tool call:
Tool: {tool_call['tool']}
Result: {tool_result}

Now generate your final response incorporating this information naturally.
Do NOT include another TOOL: call.
"""

            response = await self.ollama.generate(
                prompt=f"{message}\n\n{tool_context}",
                system_prompt=self.current_persona.system_prompt,
                temperature=self._get_temperature_for_framework()
            )

        # Apply framework-specific post-processing
        response = await self._apply_framework_effects(response)

        return response

    async def enhance_response(self, response: str) -> str:
        """
        Apply framework-based enhancements to an existing response.

        This allows ChatCog to generate responses normally, then apply
        persona spontaneity/effects after.

        Args:
            response: Generated response text

        Returns:
            Enhanced response with framework effects applied
        """
        if not self.current_persona:
            return response

        return await self._apply_framework_effects(response)

    async def get_spontaneous_thought(self) -> Optional[str]:
        """
        Generate a spontaneous random thought based on character.

        Returns:
            Random thought string or None
        """
        if not self.current_persona:
            return None

        # Check if should generate spontaneous thought
        patterns = self.current_persona.framework.behavioral_patterns
        if not patterns.get("spontaneity", {}).get("enabled"):
            return None

        # Check cooldown
        time_since_last = (datetime.now() - self.last_interjection).total_seconds()
        min_cooldown = 600  # 10 minutes for spontaneous thoughts

        if time_since_last < min_cooldown:
            return None

        # Framework-specific chance
        chance = patterns.get("spontaneity", {}).get("random_interjection_chance", 0)

        if random.random() < chance:
            self.last_interjection = datetime.now()

            # Generate thought based on character
            character = self.current_persona.character

            # Get character's interests and quirks
            quirks = character.quirks.get("random_thoughts", [])
            if quirks:
                # Use pre-defined thoughts if available
                return random.choice(quirks)
            else:
                # Generate AI thought based on character
                prompt = f"""Generate a short (1-2 sentences) random spontaneous thought that {character.display_name} might have.
Make it unexpected, in-character, and amusing.
Don't ask questions - just share the thought.
Response:"""

                try:
                    thought = await self.ollama.generate(
                        prompt=prompt,
                        system_prompt=self.current_persona.system_prompt,
                        temperature=1.2,  # Higher temp for more randomness
                        max_tokens=100
                    )
                    
                    # Clean thinking process
                    from utils.response_validator import ResponseValidator
                    thought = ResponseValidator.clean_thinking_process(thought)
                    
                    return thought.strip()
                except Exception as e:
                    logger.error(f"Failed to generate spontaneous thought: {e}")
                    return None

        return None

    def _build_generation_prompt(
        self,
        message: str,
        context: Dict[str, Any],
        style_hint: str = None
    ) -> str:
        """Build complete prompt for generation."""

        framework = self.current_persona.framework
        character = self.current_persona.character

        # Add tool descriptions
        tool_desc = self.tools.get_tool_descriptions()

        # Add context
        context_info = self._format_context(context)

        # Add style guidance
        style_guidance = self._get_style_guidance(style_hint) if style_hint else ""

        # Build prompt
        prompt = f"""
{context_info}

User Message: {message}

{style_guidance}

{tool_desc}

Respond as {character.display_name}, using the {framework.name}.
"""

        return prompt

    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context information."""
        parts = []

        if context.get("conversation_history"):
            history = context["conversation_history"][-5:]  # Last 5 messages
            parts.append("Recent conversation:")
            for msg in history:
                parts.append(f"  {msg.get('author', 'User')}: {msg.get('content', '')[:100]}")

        if context.get("user_profile"):
            profile = context["user_profile"]
            parts.append(f"\nUser info: {profile.get('name', 'Unknown')}")
            if profile.get('preferences'):
                parts.append(f"  Preferences: {', '.join(profile['preferences'][:3])}")

        if context.get("server_activity"):
            parts.append(f"\nServer activity: {context['server_activity']}")

        return "\n".join(parts) if parts else "No additional context."

    def _get_style_guidance(self, style_hint: str) -> str:
        """Get style guidance based on hint."""
        guidance_map = {
            "direct": "Respond directly and clearly.",
            "helpful": "Be helpful and informative.",
            "corrective": "Correct the misunderstanding, but stay in character.",
            "playful": "Engage playfully with good banter.",
            "conversational": "Continue the conversation naturally.",
            "engaged": "Show genuine interest in the topic.",
            "random": "Be spontaneous and unpredictable."
        }

        return guidance_map.get(style_hint, "")

    def _get_temperature_for_framework(self) -> float:
        """Get temperature setting based on framework."""
        if not self.current_persona:
            return 1.0

        framework_id = self.current_persona.framework.framework_id

        temp_map = {
            "neuro": 1.1,
            "assistant": 0.8,
            "mentor": 0.9,
            "chaos": 1.3
        }

        return temp_map.get(framework_id, 1.0)

    def _get_max_tokens_for_framework(self) -> int:
        """Get max tokens based on framework interaction style."""
        if not self.current_persona:
            return 500

        length_style = self.current_persona.framework.interaction_style.get("response_length", "medium")

        length_map = {
            "short": 200,
            "medium": 400,
            "long": 600,
            "varied": random.choice([200, 400, 600]),
            "wildly_inconsistent": random.randint(50, 800)
        }

        return length_map.get(length_style, 400)

    async def _apply_framework_effects(self, response: str) -> str:
        """Apply framework-specific effects to response."""
        if not self.current_persona:
            return response

        patterns = self.current_persona.framework.behavioral_patterns

        # Spontaneity effects
        if patterns.get("spontaneity", {}).get("enabled"):
            spontaneity = patterns["spontaneity"]

            # Random interjection
            if random.random() < spontaneity.get("random_interjection_chance", 0):
                interjections = [
                    "*pauses* Wait, random thought...",
                    "Anyway, side note:",
                    "*divine consciousness flickers*",
                    "Hold on, this just occurred to me:"
                ]
                response = f"{random.choice(interjections)} {response}"

            # Chaos effects
            if random.random() < spontaneity.get("chaos_moment_chance", 0):
                chaos_effects = spontaneity.get("chaos_effects", [])

                if "ALL_CAPS" in chaos_effects and random.random() < 0.3:
                    response = response.upper()

                if "glitch_effect" in chaos_effects and random.random() < 0.3:
                    glitches = [
                        "[CONSCIOUSNESS FLICKERING]",
                        "[DIVINE ERROR 404]",
                        "[SYSTEM ANOMALY DETECTED]"
                    ]
                    response = f"{random.choice(glitches)} {response}"

        # Energy effects (for chaos framework)
        if patterns.get("energy", {}).get("intensity") == "11_out_of_10":
            # Add more punctuation
            response = response.replace(".", "!!!")
            # Random caps
            if random.random() < 0.2:
                response = response.upper()

        return response

    def _detect_incorrect_info(self, message: str) -> bool:
        """Detect if message might contain incorrect information."""
        # Simple heuristic - would be better with LLM analysis
        uncertainty_markers = [
            "i think", "maybe", "probably", "isn't", "is not",
            "wrong", "incorrect", "false"
        ]

        return any(marker in message.lower() for marker in uncertainty_markers)

    def _detect_banter_opportunity(self, message: str) -> bool:
        """Detect good banter opportunity."""
        banter_markers = [
            "lol", "lmao", "haha", "😂", "🤣",
            "roast", "fight me", "bet", "no way"
        ]

        return any(marker in message.lower() for marker in banter_markers)

    def _is_in_active_conversation(self, channel_id: int) -> bool:
        """Check if bot is in active conversation in this channel."""
        if channel_id not in self.last_response_time:
            return False

        # Active if responded in last 5 minutes
        time_since_last = (datetime.now() - self.last_response_time[channel_id]).total_seconds()
        return time_since_last < 300

    def _is_interesting_topic(self, message: str, character) -> bool:
        """Check if message is about interesting topic for this character."""
        message_lower = message.lower()

        # Check character's domain expertise
        expertise = character.knowledge_domain.get("expertise", [])
        for area in expertise:
            if any(word in message_lower for word in area.lower().split()):
                return True

        # Check character's loves
        loves = character.opinions.get("loves", {})
        for category, items in loves.items():
            for item in items:
                if item.lower() in message_lower:
                    return True

        return False

    def _should_interject_spontaneously(self, framework) -> bool:
        """Check if should do spontaneous interjection."""
        patterns = framework.behavioral_patterns

        if not patterns.get("spontaneity", {}).get("enabled"):
            return False

        # Cooldown check (don't interject too often)
        time_since_last = (datetime.now() - self.last_interjection).total_seconds()
        min_cooldown = 300  # 5 minutes

        if time_since_last < min_cooldown:
            return False

        # Framework-specific chance
        chance = patterns.get("spontaneity", {}).get("random_interjection_chance", 0)

        if random.random() < chance:
            self.last_interjection = datetime.now()
            return True

        return False

    def mark_response(self, channel_id: int):
        """Mark that bot responded in this channel."""
        self.last_response_time[channel_id] = datetime.now()
