"""Search agent for web search and information retrieval."""

import logging
import re
from typing import Dict, List, Any, Optional
from services.agents.base import BaseAgent, AgentResult, AgentType, AgentConfidence
from services.agents.tools import WebSearchTool, FactCheckTool, ToolRegistry

logger = logging.getLogger(__name__)


class SearchAgent(BaseAgent):
    """Agent specialized in web search and information retrieval.

    Capabilities:
    - Query understanding and reformulation
    - Web search execution
    - Result summarization and citation
    - Fact-checking against sources
    - Current events and news retrieval
    """

    name = "SearchAgent"
    description = "Searches the web for current information, facts, and news"
    agent_type = AgentType.SEARCH
    capabilities = [
        "web_search",
        "query_reformulation",
        "result_summarization",
        "fact_checking",
        "news_retrieval",
        "source_citation",
    ]

    def __init__(
        self,
        web_search_tool: WebSearchTool = None,
        fact_check_tool: FactCheckTool = None,
        timeout: float = 20.0,
    ):
        """Initialize search agent.

        Args:
            web_search_tool: Web search tool instance.
            fact_check_tool: Fact check tool instance.
            timeout: Maximum execution time.
        """
        super().__init__(timeout=timeout)
        self._web_search = web_search_tool
        self._fact_check = fact_check_tool
        self._search_indicators = [
            "search",
            "look up",
            "find",
            "what is",
            "who is",
            "when is",
            "where is",
            "latest",
            "recent",
            "current",
            "news",
            "announcement",
            "update",
            "tell me about",
            "explain",
            "information on",
            "details about",
        ]

    async def can_handle(self, request: str) -> float:
        """Determine if search agent should handle this request.

        Args:
            request: User request.

        Returns:
            Confidence score 0-1.
        """
        request_lower = request.lower()

        # Check for search indicators
        has_search_indicator = any(
            indicator in request_lower for indicator in self._search_indicators
        )

        # Check for question patterns that need current info
        is_question = "?" in request or any(
            word in request_lower.split()[:5]
            for word in ["who", "what", "when", "where", "why", "how"]
        )

        # Check for temporal markers requiring current info
        has_temporal = any(
            word in request_lower
            for word in [
                "latest",
                "recent",
                "current",
                "today",
                "this week",
                "this month",
                "2024",
                "2025",
            ]
        )

        # Check for explicit search commands
        has_search_command = any(
            cmd in request_lower for cmd in ["search for", "look up", "google", "bing"]
        )

        if has_search_command:
            return AgentConfidence.CERTAIN.value
        elif has_temporal and is_question:
            return AgentConfidence.VERY_HIGH.value
        elif has_search_indicator and is_question:
            return AgentConfidence.HIGH.value
        elif has_search_indicator:
            return AgentConfidence.MEDIUM.value
        elif is_question and len(request.split()) > 5:
            return AgentConfidence.LOW.value

        return AgentConfidence.VERY_LOW.value

    async def process(self, request: str, context: Dict[str, Any]) -> AgentResult:
        """Process search request.

        Args:
            request: User request.
            context: Additional context.

        Returns:
            AgentResult with search results.
        """
        if not self._web_search:
            return AgentResult(
                success=False,
                content="",
                agent_type=self.agent_type,
                error="Web search tool not available",
            )

        try:
            # Step 1: Reformulate query for better results
            reformulated = self._reformulate_query(request)
            logger.info(f"Reformulated query: '{request}' -> '{reformulated}'")

            # Step 2: Execute search
            search_results = await self._web_search.execute(reformulated, max_results=5)

            if not search_results:
                return AgentResult(
                    success=False,
                    content="I couldn't find any results for your query.",
                    agent_type=self.agent_type,
                    confidence=0.3,
                    sources=[],
                )

            # Step 3: Summarize results
            summary = self._summarize_results(search_results, reformulated)

            # Step 4: Format for response
            content = self._format_response(search_results, summary)

            # Step 5: Extract sources
            sources = [r.url for r in search_results if r.url]

            # Step 6: Check if fact-checking is needed
            fact_check_result = None
            if context.get("needs_fact_check", False) and self._fact_check:
                fact_check_result = await self._fact_check.execute(request)

            return AgentResult(
                success=True,
                content=content,
                agent_type=self.agent_type,
                confidence=0.85,
                sources=sources,
                metadata={
                    "reformulated_query": reformulated,
                    "results_count": len(search_results),
                    "fact_check": fact_check_result,
                },
            )

        except Exception as e:
            logger.error(f"Search agent error: {e}")
            return AgentResult(
                success=False,
                content=f"Search failed: {str(e)}",
                agent_type=self.agent_type,
                error=str(e),
            )

    def _reformulate_query(self, request: str) -> str:
        """Reformulate query for better search results.

        Args:
            original_request: Original user request.

        Returns:
            Reformulated search query.
        """
        # Remove conversational elements
        cleaned = request.lower().strip()

        conversational_phrases = [
            "tell me about",
            "please tell me",
            "can you tell me",
            "i want to know",
            "look up",
            "find out about",
            "search for",
            "what is",
            "what are",
            "who is",
            "where is",
        ]

        for phrase in sorted(conversational_phrases, key=len, reverse=True):
            cleaned = cleaned.replace(phrase, "")

        # Clean up
        cleaned = " ".join(cleaned.split())
        cleaned = cleaned.strip("?.,! ")

        # If query is too short or empty, use original
        if len(cleaned) < 3:
            return request

        return cleaned

    def _summarize_results(self, results: List[Any], query: str) -> str:
        """Summarize search results.

        Args:
            results: Search results.
            query: Original query.

        Returns:
            Summary string.
        """
        if not results:
            return "No results found."

        relevant = [r for r in results if r.relevance_score > 0.3]

        if not relevant:
            return f"Found {len(results)} results, but relevance is low."

        key_themes = set()
        for r in relevant[:3]:
            words = r.title.lower().split()[:5]
            key_themes.update(words)

        return f"Found {len(results)} results related to '{query[:50]}...'"

    def _format_response(self, results: List[Any], summary: str) -> str:
        """Format search results for response.

        Args:
            results: Search results.
            summary: Result summary.

        Returns:
            Formatted response string.
        """
        parts = [summary, "\n\n"]

        for i, result in enumerate(results[:5], 1):
            parts.append(f"{i}. **{result.title}**")
            if result.snippet:
                snippet = result.snippet[:200]
                if len(result.snippet) > 200:
                    snippet += "..."
                parts.append(f"   {snippet}")
            if result.url:
                parts.append(f"   [Source]({result.url})")
            parts.append("")

        return "\n".join(parts).strip()

    def set_web_search_service(self, service):
        """Set web search service (for dependency injection).

        Args:
            service: WebSearchService instance.
        """
        from services.agents.tools import WebSearchTool

        self._web_search = WebSearchTool(service)
        self._fact_check = FactCheckTool(self._web_search)
        logger.info("Search agent web search service configured")


class SearchAgentFactory:
    """Factory for creating SearchAgent instances."""

    @staticmethod
    def create(web_search_service=None) -> SearchAgent:
        """Create search agent.

        Args:
            web_search_service: Optional WebSearchService.

        Returns:
            Configured SearchAgent.
        """
        web_tool = None
        fact_check_tool = None

        if web_search_service:
            web_tool = WebSearchTool(web_search_service)
            fact_check_tool = FactCheckTool(web_tool)

        return SearchAgent(
            web_search_tool=web_tool,
            fact_check_tool=fact_check_tool,
        )
