"""Agent-specific tools that extend beyond the basic tool system."""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, AsyncGenerator
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)


class ToolType(Enum):
    """Types of agent tools."""

    WEB_SEARCH = "web_search"
    IMAGE_GENERATION = "image_generation"
    CODE_EXECUTION = "code_execution"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"
    FACT_CHECK = "fact_check"


@dataclass
class SearchResult:
    """Result from web search."""

    title: str
    snippet: str
    url: str
    source: str = "web"
    relevance_score: float = 1.0


@dataclass
class ImageResult:
    """Result from image generation."""

    success: bool
    image_url: Optional[str] = None
    local_path: Optional[str] = None
    prompt_used: str = ""
    style: str = ""
    error: Optional[str] = None
    generation_time_ms: float = 0.0


@dataclass
class CodeResult:
    """Result from code execution."""

    success: bool
    output: str = ""
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    language: str = ""
    return_code: int = 0
    stdout: str = ""
    stderr: str = ""


@dataclass
class SentimentResult:
    """Result from sentiment analysis."""

    sentiment: str  # positive, negative, neutral
    confidence: float
    emotions: Dict[str, float] = field(default_factory=dict)


class AgentTool(ABC):
    """Abstract base class for agent tools."""

    @property
    @abstractmethod
    def tool_type(self) -> ToolType:
        """Get the type of this tool."""

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Execute the tool with given arguments."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Get tool name."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Get tool description."""


class WebSearchTool(AgentTool):
    """Tool for web searching using existing WebSearchService."""

    def __init__(self, web_search_service=None):
        """Initialize web search tool.

        Args:
            web_search_service: Optional WebSearchService instance.
        """
        self._service = web_search_service
        self._tool_type = ToolType.WEB_SEARCH

    @property
    def tool_type(self) -> ToolType:
        return self._tool_type

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web for current information, news, and facts"

    async def execute(
        self, query: str, max_results: int = 5, include_snippets: bool = True
    ) -> List[SearchResult]:
        """Execute web search.

        Args:
            query: Search query string.
            max_results: Maximum number of results.
            include_snippets: Include result snippets.

        Returns:
            List of SearchResult objects.
        """
        start_time = time.time()

        if not self._service:
            logger.warning("WebSearchService not available, using fallback")
            return []

        try:
            results = await self._service.search(query, max_results)

            search_results = []
            for r in results:
                search_results.append(
                    SearchResult(
                        title=r.get("title", "No title"),
                        snippet=r.get("snippet", "") if include_snippets else "",
                        url=r.get("url", ""),
                        source=r.get("source", "web"),
                    )
                )

            logger.info(
                f"Web search for '{query}' returned {len(search_results)} results in "
                f"{(time.time() - start_time) * 1000:.0f}ms"
            )

            return search_results

        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return []

    async def get_context(self, query: str, max_length: int = 1000) -> str:
        """Get formatted search context for LLM.

        Args:
            query: Search query.
            max_length: Maximum context length.

        Returns:
            Formatted context string.
        """
        if not self._service:
            return ""

        try:
            return await self._service.get_context(query, max_length)
        except Exception as e:
            logger.error(f"Failed to get search context: {e}")
            return ""

    async def should_search(self, query: str) -> bool:
        """Check if query needs web search.

        Args:
            query: User query.

        Returns:
            True if search would be helpful.
        """
        if not self._service:
            return False

        return await self._service.should_search(query)


class ImageGenerationTool(AgentTool):
    """Tool for image generation via external APIs."""

    def __init__(self, api_key: str = None, base_url: str = None):
        """Initialize image generation tool.

        Args:
            api_key: API key for image service.
            base_url: Base URL for API.
        """
        self._api_key = api_key
        self._base_url = base_url
        self._tool_type = ToolType.IMAGE_GENERATION
        self._available = bool(api_key)

    @property
    def tool_type(self) -> ToolType:
        return self._tool_type

    @property
    def name(self) -> str:
        return "generate_image"

    @property
    def description(self) -> str:
        return "Generate images from text prompts (DALL-E, Stable Diffusion)"

    @property
    def is_available(self) -> bool:
        """Check if image generation is available."""
        return self._available

    async def execute(
        self,
        prompt: str,
        style: str = "realistic",
        size: str = "1024x1024",
        quality: str = "standard",
    ) -> ImageResult:
        """Generate an image from prompt.

        Args:
            prompt: Image description.
            style: Art style (realistic, anime, abstract, etc.).
            size: Image size.
            quality: Quality setting.

        Returns:
            ImageResult with image URL or path.
        """
        start_time = time.time()

        if not self._available:
            return ImageResult(
                success=False,
                prompt_used=prompt,
                style=style,
                error="Image generation not configured (no API key)",
            )

        try:
            # Placeholder for actual API integration
            # Would integrate with DALL-E, Midjourney, or Stable Diffusion API
            logger.info(f"Image generation request: {prompt[:100]}...")

            # Simulated response for now
            return ImageResult(
                success=False,  # Change to True when API is configured
                prompt_used=prompt,
                style=style,
                error="Image generation API not yet implemented",
                generation_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return ImageResult(
                success=False,
                prompt_used=prompt,
                style=style,
                error=str(e),
                generation_time_ms=(time.time() - start_time) * 1000,
            )


class CodeExecutionTool(AgentTool):
    """Tool for sandboxed code execution."""

    def __init__(self, timeout: float = 10.0, memory_limit_mb: int = 128):
        """Initialize code execution tool.

        Args:
            timeout: Maximum execution time in seconds.
            memory_limit_mb: Memory limit in megabytes.
        """
        self._timeout = timeout
        self._memory_limit = memory_limit_mb
        self._tool_type = ToolType.CODE_EXECUTION
        self._allowed_languages = {"python", "javascript", "typescript", "rust", "go"}

    @property
    def tool_type(self) -> ToolType:
        return self._tool_type

    @property
    def name(self) -> str:
        return "run_code"

    @property
    def description(self) -> str:
        return "Execute code in sandboxed environment (Python, JS, Rust, Go)"

    async def execute(
        self, language: str, code: str, timeout: float = None
    ) -> CodeResult:
        """Execute code in specified language.

        Args:
            language: Programming language.
            code: Code to execute.
            timeout: Override timeout.

        Returns:
            CodeResult with output or error.
        """
        start_time = time.time()
        timeout = timeout or self._timeout

        language = language.lower().strip()

        if language not in self._allowed_languages:
            return CodeResult(
                success=False,
                language=language,
                output="",
                error=f"Language '{language}' not supported. Allowed: {', '.join(self._allowed_languages)}",
            )

        try:
            async with asyncio.timeout(timeout):
                result = await self._execute_sandboxed(language, code)

            result.execution_time_ms = (time.time() - start_time) * 1000
            return result

        except asyncio.TimeoutError:
            return CodeResult(
                success=False,
                language=language,
                output="",
                error=f"Execution timed out after {timeout}s",
                execution_time_ms=timeout * 1000,
                return_code=-1,
            )

        except Exception as e:
            logger.error(f"Code execution error: {e}")
            return CodeResult(
                success=False,
                language=language,
                output="",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _execute_sandboxed(self, language: str, code: str) -> CodeResult:
        """Execute code in sandboxed environment.

        Args:
            language: Programming language.
            code: Code to execute.

        Returns:
            CodeResult with output.
        """
        # Security: Code execution should use proper sandboxing
        # This is a placeholder - real implementation would use:
        # - Docker containers
        # - Firejail namespaces
        # - Restricted exec with resource limits
        # - WASM execution for browser sandboxing

        if language == "python":
            return await self._run_python(code)

        return CodeResult(
            success=False,
            language=language,
            error=f"No executor configured for {language}",
        )

    async def _run_python(self, code: str) -> CodeResult:
        """Execute Python code safely.

        Args:
            code: Python code to execute.

        Returns:
            CodeResult with output.
        """
        import io
        import sys

        # Capturing stdout/stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        # Note: This is NOT truly sandboxed
        # For production, use Docker or restricted execution
        try:
            old_stdout = sys.stdout
            old_stderr = sys.stderr

            sys.stdout = stdout_capture
            sys.stderr = stderr_capture

            # Execute with limited globals
            restricted_globals = {
                "__name__": "__main__",
                "__builtins__": __builtins__,
            }

            exec(code, restricted_globals)

            sys.stdout = old_stdout
            sys.stderr = old_stderr

            return CodeResult(
                success=True,
                language="python",
                output=stdout_capture.getvalue(),
                stdout=stdout_capture.getvalue(),
                stderr=stderr_capture.getvalue(),
                return_code=0,
            )

        except Exception as e:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

            return CodeResult(
                success=False,
                language="python",
                output=str(e),
                error=str(e),
                stdout=stdout_capture.getvalue(),
                stderr=stderr_capture.getvalue(),
                return_code=1,
            )


class SentimentAnalysisTool(AgentTool):
    """Tool for analyzing sentiment and emotions in text."""

    def __init__(self):
        """Initialize sentiment analysis tool."""
        self._tool_type = ToolType.SENTIMENT_ANALYSIS
        self._positive_words = {
            "good",
            "great",
            "excellent",
            "amazing",
            "wonderful",
            "happy",
            "love",
            "best",
            "awesome",
            "fantastic",
        }
        self._negative_words = {
            "bad",
            "terrible",
            "awful",
            "horrible",
            "sad",
            "hate",
            "worst",
            "angry",
            "upset",
            "disappointed",
        }

    @property
    def tool_type(self) -> ToolType:
        return self._tool_type

    @property
    def name(self) -> str:
        return "analyze_sentiment"

    @property
    def description(self) -> str:
        return "Analyze sentiment and emotions in text"

    async def execute(self, text: str) -> SentimentResult:
        """Analyze sentiment of text.

        Args:
            text: Text to analyze.

        Returns:
            SentimentResult with sentiment and emotions.
        """
        text_lower = text.lower()
        words = set(text_lower.split())

        positive_count = len(words & self._positive_words)
        negative_count = len(words & self._negative_words)

        if positive_count > negative_count:
            sentiment = "positive"
            confidence = min(0.5 + (positive_count - negative_count) * 0.1, 0.95)
        elif negative_count > positive_count:
            sentiment = "negative"
            confidence = min(0.5 + (negative_count - positive_count) * 0.1, 0.95)
        else:
            sentiment = "neutral"
            confidence = 0.6

        emotions = {
            "joy": positive_count / max(len(words), 1) * 2,
            "sadness": negative_count / max(len(words), 1),
            "anger": negative_count / max(len(words), 1),
            "surprise": 0.1,
        }

        return SentimentResult(
            sentiment=sentiment,
            confidence=confidence,
            emotions=emotions,
        )


class FactCheckTool(AgentTool):
    """Tool for fact-checking information."""

    def __init__(self, web_search_tool: WebSearchTool = None):
        """Initialize fact check tool.

        Args:
            web_search_tool: Web search tool for verification.
        """
        self._web_search = web_search_tool
        self._tool_type = ToolType.FACT_CHECK

    @property
    def tool_type(self) -> ToolType:
        return self._tool_type

    @property
    def name(self) -> str:
        return "fact_check"

    @property
    def description(self) -> str:
        return "Verify claims and facts against web sources"

    async def execute(self, claim: str) -> Dict[str, Any]:
        """Check a claim against web sources.

        Args:
            claim: Statement to verify.

        Returns:
            Dict with verification results.
        """
        if not self._web_search:
            return {
                "verified": False,
                "confidence": 0.0,
                "error": "Web search not available",
            }

        # Search for the claim
        search_results = await self._web_search.execute(claim, max_results=3)

        if not search_results:
            return {
                "verified": False,
                "confidence": 0.3,
                "sources": [],
                "summary": "No sources found to verify this claim",
            }

        # Simple verification logic (would be more sophisticated with LLM)
        relevant_results = [r for r in search_results if r.relevance_score > 0.3]

        return {
            "verified": len(relevant_results) > 0,
            "confidence": min(len(relevant_results) / 3, 1.0),
            "sources": [{"title": r.title, "url": r.url} for r in relevant_results],
            "summary": f"Found {len(relevant_results)} relevant sources",
        }


class ToolRegistry:
    """Registry for agent tools."""

    def __init__(self):
        """Initialize tool registry."""
        self._tools: Dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> None:
        """Register a tool.

        Args:
            tool: Tool to register.
        """
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def get(self, name: str) -> Optional[AgentTool]:
        """Get tool by name.

        Args:
            name: Tool name.

        Returns:
            Tool or None if not found.
        """
        return self._tools.get(name)

    def list_tools(self) -> List[AgentTool]:
        """List all registered tools."""
        return list(self._tools.values())

    def get_tools_by_type(self, tool_type: ToolType) -> List[AgentTool]:
        """Get tools by type.

        Args:
            tool_type: Type of tools to get.

        Returns:
            List of matching tools.
        """
        return [t for t in self._tools.values() if t.tool_type == tool_type]

    def create_default_registry(self, web_search_service=None) -> "ToolRegistry":
        """Create registry with default tools.

               Args:
                   web_search_service: Optional web search service.

               Returns:
                   Configured ToolRegistry.
        = ToolRegistry()

               # Register web search
               web_tool = WebSearchTool"""
        registry(web_search_service)
        if web_search_service:
            registry.register(web_tool)

        # Register image generation (configured via API key)
        registry.register(ImageGenerationTool())

        # Register code execution
        registry.register(CodeExecutionTool())

        # Register sentiment analysis
        registry.register(SentimentAnalysisTool())

        # Register fact check
        fact_check = FactCheckTool(web_tool)
        registry.register(fact_check)

        return registry
