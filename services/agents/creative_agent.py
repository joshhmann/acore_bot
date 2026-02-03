"""Creative agent for image generation, storytelling, and creative writing."""

import logging
import re
from typing import Dict, List, Any, Optional
from services.agents.base import BaseAgent, AgentResult, AgentType, AgentConfidence
from services.agents.tools import ImageGenerationTool, ToolRegistry

logger = logging.getLogger(__name__)


class CreativeAgent(BaseAgent):
    """Agent specialized in creative tasks.

    Capabilities:
    - Image generation from prompts
    - Story and poem writing
    - Creative content with persona voice
    - Meme creation assistance
    - Music/lyric generation concepts
    """

    name = "CreativeAgent"
    description = "Generates creative content including images, stories, and poems"
    agent_type = AgentType.CREATIVE
    capabilities = [
        "image_generation",
        "storytelling",
        "poetry",
        "creative_writing",
        "meme_creation",
        "character_voice",
    ]

    def __init__(
        self,
        image_tool: ImageGenerationTool = None,
        llm_service=None,
        timeout: float = 30.0,
    ):
        """Initialize creative agent.

        Args:
            image_tool: Image generation tool.
            llm_service: LLM service for text generation.
            timeout: Maximum execution time.
        """
        super().__init__(timeout=timeout)
        self._image_tool = image_tool
        self._llm = llm_service
        self._creative_patterns = {
            "image": r"(generate|create|make|draw|paint|render)\s+(an?|the)?\s*(.*?)\s*(image|picture|art|illustration|photo)",
            "story": r"(tell|write|create|make|compose)\s+(a|an|the)?\s*(.*?)\s*(story|tale|narrative|fiction)",
            "poem": r"(write|create|compose|make)\s+(a|an|the)?\s*(.*?)\s*(poem|poetry|verse|sonnet|haiku)",
            "creative": r"(creative|imaginative|artistic)\s+(content|task|request)",
            "meme": r"(make|create|generate)\s+(a|an)?\s*(meme|reaction)",
        }

    async def can_handle(self, request: str) -> float:
        """Determine if creative agent should handle this request.

        Args:
            request: User request.

        Returns:
            Confidence score 0-1.
        """
        request_lower = request.lower()

        # Check for explicit creative indicators
        explicit_patterns = [
            "generate an image",
            "create an image",
            "draw something",
            "write a story",
            "tell me a story",
            "write a poem",
            "create some art",
            "make a picture",
            "render an image",
        ]

        for pattern in explicit_patterns:
            if pattern in request_lower:
                return AgentConfidence.CERTAIN.value

        # Check for regex patterns
        for category, pattern in self._creative_patterns.items():
            if re.search(pattern, request_lower):
                return AgentConfidence.HIGH.value

        # Check for creative keywords
        creative_keywords = [
            "image",
            "picture",
            "art",
            "illustration",
            "creative writing",
            "story",
            "tale",
            "poem",
            "poetry",
            "meme",
            "draw",
            "paint",
        ]

        keyword_count = sum(1 for kw in creative_keywords if kw in request_lower)

        if keyword_count >= 2:
            return AgentConfidence.MEDIUM.value
        elif keyword_count == 1:
            return AgentConfidence.LOW.value

        return AgentConfidence.VERY_LOW.value

    async def process(self, request: str, context: Dict[str, Any]) -> AgentResult:
        """Process creative request.

        Args:
            request: User request.
            context: Additional context.

        Returns:
            AgentResult with creative content.
        """
        request_lower = request.lower()

        # Detect creative type
        creative_type = self._detect_creative_type(request_lower)

        try:
            if creative_type == "image":
                return await self._handle_image_generation(request, context)
            elif creative_type == "story":
                return await self._handle_story(request, context)
            elif creative_type == "poem":
                return await self._handle_poem(request, context)
            else:
                return await self._handle_general_creative(request, context)

        except Exception as e:
            logger.error(f"Creative agent error: {e}")
            return AgentResult(
                success=False,
                content=f"Creative task failed: {str(e)}",
                agent_type=self.agent_type,
                error=str(e),
            )

    def _detect_creative_type(self, request: str) -> str:
        """Detect the type of creative request.

        Args:
            request: Lowercased request.

        Returns:
            Creative type string.
        """
        for category, pattern in self._creative_patterns.items():
            if re.search(pattern, request):
                return category

        # Fallback keyword detection
        if "image" in request or "picture" in request or "art" in request:
            return "image"
        elif "story" in request or "tale" in request or "narrative" in request:
            return "story"
        elif "poem" in request or "poetry" in request or "verse" in request:
            return "poem"

        return "general"

    async def _handle_image_generation(
        self, request: str, context: Dict[str, Any]
    ) -> AgentResult:
        """Handle image generation request.

        Args:
            request: User request.
            context: Additional context.

        Returns:
            AgentResult with image.
        """
        if not self._image_tool or not self._image_tool.is_available:
            return AgentResult(
                success=False,
                content="Image generation is not configured. Please set up an image generation API key.",
                agent_type=self.agent_type,
                error="Image generation not available",
            )

        # Extract prompt from request
        prompt = self._extract_image_prompt(request)

        # Detect style
        style = self._detect_style(request)

        # Generate image
        result = await self._image_tool.execute(
            prompt=prompt,
            style=style,
        )

        if result.success:
            return AgentResult(
                success=True,
                content=f"Here's your generated image:\n{result.image_url}",
                agent_type=self.agent_type,
                confidence=0.9,
                metadata={
                    "prompt_used": prompt,
                    "style": style,
                    "generation_time_ms": result.generation_time_ms,
                },
            )
        else:
            return AgentResult(
                success=False,
                content=f"Image generation failed: {result.error}",
                agent_type=self.agent_type,
                error=result.error,
            )

    async def _handle_story(self, request: str, context: Dict[str, Any]) -> AgentResult:
        """Handle story writing request.

        Args:
            request: User request.
            context: Additional context.

        Returns:
            AgentResult with story.
        """
        if not self._llm:
            return AgentResult(
                success=False,
                content="Story writing requires LLM service.",
                agent_type=self.agent_type,
                error="LLM not available",
            )

        # Extract story parameters
        topic = self._extract_story_topic(request)
        length = self._detect_length(request)

        # Build prompt
        system_prompt = """You are a creative storyteller. Write engaging, 
        vivid stories with well-developed characters and plots. Use 
        descriptive language and maintain narrative flow."""

        user_prompt = f"Write a {length} story about: {topic}"

        if context.get("persona"):
            user_prompt += f"\n\nWrite in the voice of: {context['persona']}"

        try:
            response = await self._llm.chat(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                temperature=0.8,
                max_tokens=self._get_token_limit(length),
            )

            return AgentResult(
                success=True,
                content=response,
                agent_type=self.agent_type,
                confidence=0.85,
                metadata={"topic": topic, "length": length},
            )

        except Exception as e:
            return AgentResult(
                success=False,
                content=f"Story generation failed: {str(e)}",
                agent_type=self.agent_type,
                error=str(e),
            )

    async def _handle_poem(self, request: str, context: Dict[str, Any]) -> AgentResult:
        """Handle poem writing request.

        Args:
            request: User request.
            context: Additional context.

        Returns:
            AgentResult with poem.
        """
        if not self._llm:
            return AgentResult(
                success=False,
                content="Poem writing requires LLM service.",
                agent_type=self.agent_type,
                error="LLM not available",
            )

        # Detect poem type
        poem_type = self._detect_poem_type(request)
        topic = self._extract_poem_topic(request)

        system_prompt = """You are a poet. Write beautiful, evocative poetry.
        Use vivid imagery, metaphor, and appropriate meter for the form."""

        user_prompt = f"Write a {poem_type} about: {topic}"

        if context.get("persona"):
            user_prompt += f"\n\nWrite in the voice of: {context['persona']}"

        try:
            response = await self._llm.chat(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                temperature=0.9,
                max_tokens=500,
            )

            return AgentResult(
                success=True,
                content=response,
                agent_type=self.agent_type,
                confidence=0.85,
                metadata={"topic": topic, "poem_type": poem_type},
            )

        except Exception as e:
            return AgentResult(
                success=False,
                content=f"Poem generation failed: {str(e)}",
                agent_type=self.agent_type,
                error=str(e),
            )

    async def _handle_general_creative(
        self, request: str, context: Dict[str, Any]
    ) -> AgentResult:
        """Handle general creative request.

        Args:
            request: User request.
            context: Additional context.

        Returns:
            AgentResult with creative content.
        """
        if not self._llm:
            return AgentResult(
                success=False,
                content="Creative tasks require LLM service.",
                agent_type=self.agent_type,
                error="LLM not available",
            )

        system_prompt = """You are a creative assistant. Help users with
        creative tasks including brainstorming, creative writing, and
        artistic concepts. Be imaginative and inspiring."""

        try:
            response = await self._llm.chat(
                messages=[{"role": "user", "content": request}],
                system_prompt=system_prompt,
                temperature=0.8,
                max_tokens=1000,
            )

            return AgentResult(
                success=True,
                content=response,
                agent_type=self.agent_type,
                confidence=0.7,
            )

        except Exception as e:
            return AgentResult(
                success=False,
                content=f"Creative task failed: {str(e)}",
                agent_type=self.agent_type,
                error=str(e),
            )

    def _extract_image_prompt(self, request: str) -> str:
        """Extract image generation prompt from request.

        Args:
            request: User request.

        Returns:
            Cleaned prompt string.
        """
        prompt = request

        # Remove common prefixes
        prefixes = [
            "generate an image of",
            "create an image of",
            "draw",
            "make a picture of",
            "render",
            "create art of",
        ]

        for prefix in prefixes:
            if request.lower().startswith(prefix):
                prompt = request[len(prefix) :].strip()
                break

        # Clean up
        prompt = prompt.strip(".,!?;:")

        if not prompt:
            prompt = request

        return prompt

    def _detect_style(self, request: str) -> str:
        """Detect desired image style.

        Args:
            request: User request.

        Returns:
            Style string.
        """
        request_lower = request.lower()

        styles = {
            "realistic": ["realistic", "photorealistic", "photo", "real life"],
            "anime": ["anime", "manga", "japanese style"],
            "abstract": ["abstract", "surreal", "dreamlike"],
            "cartoon": ["cartoon", "animated", "comic style"],
            "oil painting": ["oil painting", "painting style", "canvas"],
            "watercolor": ["watercolor", "watercolour"],
            "sketch": ["sketch", "drawing", "pencil", "charcoal"],
        }

        for style, keywords in styles.items():
            if any(kw in request_lower for kw in keywords):
                return style

        return "realistic"

    def _extract_story_topic(self, request: str) -> str:
        """Extract story topic from request.

        Args:
            request: User request.

        Returns:
            Topic string.
        """
        # Remove common prefixes
        prefixes = [
            "write a story about",
            "tell me a story about",
            "create a story",
            "write a",
            "tell me a story",
        ]

        topic = request
        for prefix in prefixes:
            if prefix in request.lower():
                topic = request.lower().split(prefix)[1].strip()
                break

        return topic.strip(".,!?;:")

    def _detect_length(self, request: str) -> str:
        """Detect desired story length.

        Args:
            request: User request.

        Returns:
            Length string.
        """
        request_lower = request.lower()

        if any(w in request_lower for w in ["short", "brief", "quick", "small"]):
            return "short"
        elif any(w in request_lower for w in ["long", "epic", "detailed", "full"]):
            return "long"
        else:
            return "medium"

    def _extract_poem_topic(self, request: str) -> str:
        """Extract poem topic from request.

        Args:
            request: User request.

        Returns:
            Topic string.
        """
        prefixes = [
            "write a poem about",
            "write a haiku about",
            "write a sonnet about",
            "compose a poem",
            "create a poem",
        ]

        topic = request
        for prefix in prefixes:
            if prefix in request.lower():
                topic = request.lower().split(prefix)[1].strip()
                break

        return topic.strip(".,!?;:")

    def _detect_poem_type(self, request: str) -> str:
        """Detect poem type.

        Args:
            request: User request.

        Returns:
            Poem type string.
        """
        request_lower = request.lower()

        if "haiku" in request_lower:
            return "haiku"
        elif "sonnet" in request_lower:
            return "sonnet"
        elif "limerick" in request_lower:
            return "limerick"
        elif "free verse" in request_lower:
            return "free verse"
        else:
            return "poem"

    def _get_token_limit(self, length: str) -> int:
        """Get token limit based on length.

        Args:
            length: Length string.

        Returns:
            Token limit.
        """
        limits = {
            "short": 300,
            "medium": 700,
            "long": 1500,
        }
        return limits.get(length, 500)


class CreativeAgentFactory:
    """Factory for creating CreativeAgent instances."""

    @staticmethod
    def create(
        image_api_key: str = None,
        llm_service=None,
    ) -> CreativeAgent:
        """Create creative agent.

        Args:
            image_api_key: API key for image generation.
            llm_service: LLM service instance.

        Returns:
            Configured CreativeAgent.
        """
        image_tool = None
        if image_api_key:
            image_tool = ImageGenerationTool(api_key=image_api_key)

        return CreativeAgent(
            image_tool=image_tool,
            llm_service=llm_service,
        )
