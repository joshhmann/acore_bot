"""Web Search service for retrieving real-time information from the internet."""
import logging
from typing import List, Dict, Optional, Tuple
import aiohttp
from urllib.parse import quote_plus
import asyncio
from ddgs import DDGS
from services.query_optimizer import get_query_optimizer
import re

logger = logging.getLogger(__name__)


class WebSearchService:
    """Service for searching the web and retrieving context.

    Supports DuckDuckGo (no API key needed) and Google (requires API key).
    """

    def __init__(self, engine: str = "duckduckgo", max_results: int = 3, google_api_key: str = None, google_cx_id: str = None, use_optimizer: bool = True):
        """Initialize web search service.

        Args:
            engine: Search engine to use ("duckduckgo" or "google")
            max_results: Maximum number of results to return
            google_api_key: Google API key (required for Google search)
            google_cx_id: Google Custom Search Engine ID (required for Google search)
            use_optimizer: Enable query optimization with RAG learning (default: True)
        """
        self.engine = engine.lower()
        self.max_results = max_results
        self.google_api_key = google_api_key
        self.google_cx_id = google_cx_id
        self.session: Optional[aiohttp.ClientSession] = None
        self.use_optimizer = use_optimizer

        # Initialize query optimizer
        self.optimizer = get_query_optimizer() if use_optimizer else None

        logger.info(f"Web search service initialized (engine: {self.engine}, optimizer: {use_optimizer})")

    async def initialize(self):
        """Initialize the HTTP session."""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None

    def _clean_query(self, query: str) -> str:
        """Clean conversational language from search query.

        Args:
            query: Raw user query

        Returns:
            Cleaned search query with conversational words removed
        """
        cleaned = query.lower().strip()

        # Common conversational phrases to remove
        conversational_phrases = [
            "tell me about",
            "tell me",
            "what is",
            "what are",
            "what's",
            "whats",
            "can you tell me",
            "i want to know",
            "please tell me",
            "do you know",
            "search for",
            "look up",
            "find out about",
            "find out",
            "find",
            "about the",
            "about",
        ]

        # Remove conversational phrases (order matters - do longer phrases first)
        for phrase in sorted(conversational_phrases, key=len, reverse=True):
            cleaned = cleaned.replace(phrase, "")

        # Remove common question words at the start
        start_words = ["is there", "are there", "have there been", "has there been"]
        for word in start_words:
            if cleaned.startswith(word):
                cleaned = cleaned[len(word):].strip()

        # If query starts with "any recent/latest/new news/updates about/on X",
        # extract just the topic X + news/updates
        # This prevents "news" from dominating the search
        import re

        # Pattern: "any [recent/latest/new] [news/updates/info] [on/about] TOPIC"
        pattern = r'^(?:any\s+)?(?:recent|latest|new|current)?\s*(?:news|updates?|info|information)\s+(?:on|about|for|regarding)?\s*(.+)$'
        match = re.search(pattern, cleaned)
        if match and match.group(1).strip():
            # Extract topic and add a temporal keyword
            topic = match.group(1).strip()
            cleaned = f"{topic} news 2024 2025"
            logger.debug(f"Extracted topic from news query: '{topic}'")

        # Clean up extra spaces and punctuation
        cleaned = " ".join(cleaned.split())
        cleaned = cleaned.strip("?,. ")

        return cleaned.strip()

    async def search(self, query: str, max_results: Optional[int] = None) -> List[Dict]:
        """Search the web for a query.

        Args:
            query: Search query
            max_results: Override default max results

        Returns:
            List of search result dicts with title, snippet, url
        """
        if not self.session:
            await self.initialize()

        original_query = query
        optimization_metadata = {}

        # Use query optimizer if enabled
        if self.optimizer:
            optimized_query, optimization_metadata = await self.optimizer.optimize_query(query)
            logger.info(f"Query optimization: '{query}' -> '{optimized_query}' (source: {optimization_metadata.get('source')})")
            query = optimized_query
        else:
            # Fallback to basic cleaning
            query = self._clean_query(query)
            if not query or len(query) < 3:
                query = original_query
            logger.info(f"Basic cleaning: '{original_query}' -> '{query}'")

        results_limit = max_results or self.max_results

        # Perform the actual search
        if self.engine == "google":
            results = await self._search_google(query, results_limit)
        else:
            results = await self._search_duckduckgo(query, results_limit)

        # Record search for learning (if optimizer is enabled)
        if self.optimizer:
            success = len(results) > 0
            await self.optimizer.record_search(
                original_query=original_query,
                transformed_query=query,
                results_count=len(results),
                success=success,
                metadata=optimization_metadata
            )

        return results

    async def _search_duckduckgo(self, query: str, max_results: int) -> List[Dict]:
        """Search using DuckDuckGo text search (via ddgs library).

        Args:
            query: Search query
            max_results: Maximum results

        Returns:
            List of search results
        """
        try:
            # Run DuckDuckGo search in thread pool (it's synchronous)
            loop = asyncio.get_event_loop()

            def _do_search():
                # Use DDGS with proper configuration
                ddgs = DDGS()
                # Use text search which returns actual web results
                # The new API expects query as first positional argument
                results_raw = list(ddgs.text(
                    query,
                    region='wt-wt',
                    safesearch='off',
                    max_results=max_results
                ))
                return results_raw

            results_raw = await loop.run_in_executor(None, _do_search)

            # Format results
            results = []
            for item in results_raw:
                results.append({
                    "title": item.get("title", "No title"),
                    "snippet": item.get("body", ""),
                    "url": item.get("href", ""),
                    "source": "DuckDuckGo"
                })

            logger.info(f"DuckDuckGo search returned {len(results)} results for: {query}")
            return results[:max_results]

        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
            return []

    async def _search_google(self, query: str, max_results: int) -> List[Dict]:
        """Search using Google Custom Search API.

        Args:
            query: Search query
            max_results: Maximum results

        Returns:
            List of search results
        """
        if not self.google_api_key or not self.google_cx_id:
            logger.error("Google search requires API key and CX ID")
            return []

        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.google_api_key,
                "cx": self.google_cx_id,
                "q": query,
                "num": min(max_results, 10)  # Google max is 10
            }

            async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.error(f"Google search failed with status {resp.status}")
                    return []

                data = await resp.json()

                results = []
                for item in data.get("items", []):
                    results.append({
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "url": item.get("link", ""),
                        "source": "Google"
                    })

                logger.info(f"Google search returned {len(results)} results for: {query}")
                return results

        except Exception as e:
            logger.error(f"Google search error: {e}")
            return []

    async def get_context(self, query: str, max_length: int = 1000, conversation_context: str = None) -> str:
        """Get formatted context from search results for AI.

        Args:
            query: Search query
            max_length: Maximum character length
            conversation_context: Recent conversation context to help with vague queries

        Returns:
            Formatted search context string (empty if low quality results)
        """
        # Enhance query with conversation context if provided
        enhanced_query = query
        if conversation_context and len(query.split()) < 5:
            # Query is short/vague, try to add context
            logger.info(f"Enhancing short query '{query}' with conversation context")
            enhanced_query = f"{conversation_context} {query}"

        results = await self.search(enhanced_query)

        if not results:
            return ""

        # Filter results by quality/relevance
        filtered_results, is_quality = self._filter_results_by_quality(results, query, min_relevance=0.3)

        # If quality is poor, return empty (let AI say it doesn't have info)
        if not is_quality or not filtered_results:
            logger.warning(f"Search results for '{query}' are low quality - not providing to AI")
            return ""

        context_parts = [f"Web search results for '{query}':"]

        for i, result in enumerate(filtered_results, 1):
            title = result.get("title", "No title")
            snippet = result.get("snippet", "")
            url = result.get("url", "")

            # Format result
            result_text = f"\n{i}. {title}"
            if snippet:
                result_text += f"\n   {snippet}"
            if url:
                result_text += f"\n   Source: {url}"

            # Check length
            if len("\n".join(context_parts)) + len(result_text) > max_length:
                break

            context_parts.append(result_text)

        return "\n".join(context_parts)

    async def should_search(self, query: str) -> bool:
        """Determine if a query needs web search based on keywords.

        Args:
            query: User query

        Returns:
            True if web search would be helpful
        """
        # Keywords that suggest current/real-time information needed
        search_indicators = [
            "who won",
            "what happened",
            "latest",
            "recent",
            "any recent",
            "current",
            "today",
            "this year",
            "this week",
            "2024",
            "2025",
            "news",
            "update",
            "announcement",
            "when is",
            "when did",
            "search",
            "look up",
            "find out",
            "google",
            "what's new",
            "whats new",
        ]

        query_lower = query.lower()
        return any(indicator in query_lower for indicator in search_indicators)

    def is_enabled(self) -> bool:
        """Check if web search is available.

        Returns:
            True if search engine is configured
        """
        if self.engine == "google":
            return bool(self.google_api_key and self.google_cx_id)
        else:
            return True  # DuckDuckGo doesn't need config

    def _extract_topic_keywords(self, query: str) -> List[str]:
        """Extract key topic words from a query.

        Args:
            query: Search query

        Returns:
            List of important keywords
        """
        # Remove common stopwords
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'are', 'was', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'should', 'could', 'may', 'might', 'can', 'what', 'when',
            'where', 'who', 'how', 'why', 'any', 'some', 'all', 'about', 'latest',
            'recent', 'new', 'news', 'update', 'updates', '2024', '2025'
        }

        # Extract words, filter stopwords, keep meaningful terms
        words = re.findall(r'\b\w+\b', query.lower())
        keywords = [w for w in words if w not in stopwords and len(w) > 2]

        return keywords[:5]  # Return top 5 keywords

    def _calculate_relevance_score(self, result: Dict, topic_keywords: List[str]) -> float:
        """Calculate relevance score for a search result.

        Args:
            result: Search result dict
            topic_keywords: Keywords from original query

        Returns:
            Relevance score (0-1)
        """
        if not topic_keywords:
            return 0.5  # Neutral if no keywords

        title = result.get("title", "").lower()
        snippet = result.get("snippet", "").lower()
        url = result.get("url", "").lower()

        combined_text = f"{title} {snippet} {url}"

        # Count keyword matches
        matches = sum(1 for kw in topic_keywords if kw in combined_text)
        score = matches / len(topic_keywords)

        return score

    def _filter_results_by_quality(
        self,
        results: List[Dict],
        query: str,
        min_relevance: float = 0.4
    ) -> Tuple[List[Dict], bool]:
        """Filter search results by quality and relevance.

        Args:
            results: List of search results
            query: Original query
            min_relevance: Minimum relevance score (0-1)

        Returns:
            Tuple of (filtered_results, is_quality_good)
        """
        if not results:
            return [], False

        # Extract topic keywords from query
        topic_keywords = self._extract_topic_keywords(query)

        if not topic_keywords:
            # No meaningful keywords - can't assess quality
            return [], False

        # Score each result
        scored_results = []
        for result in results:
            score = self._calculate_relevance_score(result, topic_keywords)
            scored_results.append((result, score))

        # Filter by minimum relevance
        filtered = [r for r, s in scored_results if s >= min_relevance]

        # Check if we have quality results
        # Need at least 2 keyword matches on average for quality
        avg_score = sum(s for _, s in scored_results) / len(scored_results) if scored_results else 0
        is_quality = avg_score >= min_relevance and len(filtered) >= 1

        if is_quality:
            logger.info(f"Quality check PASSED: {len(filtered)}/{len(results)} results (avg score: {avg_score:.2f})")
        else:
            logger.warning(f"Quality check FAILED: {len(filtered)}/{len(results)} results (avg score: {avg_score:.2f})")

        return filtered, is_quality


# Example usage for testing
async def test_search():
    """Test web search functionality."""
    search = WebSearchService(engine="duckduckgo", max_results=3)
    await search.initialize()

    # Test query
    results = await search.search("Halo World Championship 2024 winner")
    print(f"Found {len(results)} results:")
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result['title']}")
        print(f"   {result['snippet'][:100]}...")
        print(f"   {result['url']}")

    # Get formatted context
    context = await search.get_context("Master Chief Halo")
    print("\nFormatted context:")
    print(context)

    await search.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_search())
