"""Web Search service for retrieving real-time information from the internet."""
import logging
from typing import List, Dict, Optional
import aiohttp
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


class WebSearchService:
    """Service for searching the web and retrieving context.

    Supports DuckDuckGo (no API key needed) and Google (requires API key).
    """

    def __init__(self, engine: str = "duckduckgo", max_results: int = 3, google_api_key: str = None, google_cx_id: str = None):
        """Initialize web search service.

        Args:
            engine: Search engine to use ("duckduckgo" or "google")
            max_results: Maximum number of results to return
            google_api_key: Google API key (required for Google search)
            google_cx_id: Google Custom Search Engine ID (required for Google search)
        """
        self.engine = engine.lower()
        self.max_results = max_results
        self.google_api_key = google_api_key
        self.google_cx_id = google_cx_id
        self.session: Optional[aiohttp.ClientSession] = None

        logger.info(f"Web search service initialized (engine: {self.engine})")

    async def initialize(self):
        """Initialize the HTTP session."""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None

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

        results_limit = max_results or self.max_results

        if self.engine == "google":
            return await self._search_google(query, results_limit)
        else:
            return await self._search_duckduckgo(query, results_limit)

    async def _search_duckduckgo(self, query: str, max_results: int) -> List[Dict]:
        """Search using DuckDuckGo Instant Answer API.

        Args:
            query: Search query
            max_results: Maximum results

        Returns:
            List of search results
        """
        try:
            # DuckDuckGo Instant Answer API (free, no key needed)
            url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1"

            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.error(f"DuckDuckGo search failed with status {resp.status}")
                    return []

                data = await resp.json()

                results = []

                # Try to get instant answer
                if data.get("Abstract"):
                    results.append({
                        "title": data.get("Heading", "Summary"),
                        "snippet": data.get("Abstract", ""),
                        "url": data.get("AbstractURL", ""),
                        "source": "DuckDuckGo"
                    })

                # Get related topics
                related = data.get("RelatedTopics", [])
                for item in related[:max_results - len(results)]:
                    if isinstance(item, dict) and item.get("Text"):
                        results.append({
                            "title": item.get("Text", "")[:100],
                            "snippet": item.get("Text", ""),
                            "url": item.get("FirstURL", ""),
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

    async def get_context(self, query: str, max_length: int = 1000) -> str:
        """Get formatted context from search results for AI.

        Args:
            query: Search query
            max_length: Maximum character length

        Returns:
            Formatted search context string
        """
        results = await self.search(query)

        if not results:
            return ""

        context_parts = [f"Web search results for '{query}':"]

        for i, result in enumerate(results, 1):
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
            "current",
            "today",
            "this year",
            "2024",
            "2025",
            "news",
            "update",
            "when is",
            "when did",
            "search",
            "look up",
            "find out",
            "google",
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
