"""Query optimization service using patterns and RAG-based learning."""
import json
import re
import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import aiofiles

logger = logging.getLogger(__name__)


class QueryPatternMatcher:
    """Matches queries against known patterns and transforms them."""

    def __init__(self, patterns_file: Path = Path("data/query_patterns.json")):
        """Initialize pattern matcher.

        Args:
            patterns_file: Path to query patterns JSON file
        """
        self.patterns_file = patterns_file
        self.patterns = {}
        self.stopwords = []
        self.temporal_boosters = {}
        self.load_patterns()

    def load_patterns(self):
        """Load patterns from JSON file."""
        try:
            if not self.patterns_file.exists():
                logger.warning(f"Patterns file not found: {self.patterns_file}")
                return

            with open(self.patterns_file, 'r') as f:
                data = json.load(f)

            self.patterns = data.get("transformation_patterns", {})
            self.stopwords = data.get("conversational_stopwords", [])
            self.temporal_boosters = data.get("temporal_boosters", {})

            total_patterns = sum(len(cat["patterns"]) for cat in self.patterns.values())
            logger.info(f"Loaded {total_patterns} query transformation patterns")

        except Exception as e:
            logger.error(f"Failed to load patterns: {e}")

    def match_pattern(self, query: str) -> Optional[Tuple[str, Dict]]:
        """Match query against patterns and return transformation.

        Args:
            query: User query

        Returns:
            Tuple of (transformed_query, metadata) or None if no match
        """
        query_lower = query.lower().strip()

        # Try to match against all pattern categories
        for category_name, category_data in self.patterns.items():
            for pattern_obj in category_data.get("patterns", []):
                pattern = pattern_obj.get("pattern", "")
                transform_template = pattern_obj.get("transform", "")

                if not pattern or not transform_template:
                    continue

                try:
                    match = re.match(pattern, query_lower, re.IGNORECASE)
                    if match:
                        # Extract captured groups
                        groups = match.groups()

                        # Build transformation using captured groups
                        transformed = transform_template

                        # Replace {topic}, {topic1}, {topic2}, etc.
                        # Strip punctuation from captured groups
                        if len(groups) >= 1:
                            topic = groups[0].strip().rstrip('?!.,;:')
                            transformed = transformed.replace("{topic}", topic)
                        if len(groups) >= 2:
                            topic1 = groups[0].strip().rstrip('?!.,;:')
                            topic2 = groups[1].strip().rstrip('?!.,;:')
                            transformed = transformed.replace("{topic1}", topic1)
                            transformed = transformed.replace("{topic2}", topic2)

                        metadata = {
                            "category": category_name,
                            "pattern": pattern,
                            "original_query": query,
                            "matched": True
                        }

                        logger.info(f"Pattern matched: '{query}' -> '{transformed}' (category: {category_name})")
                        return transformed, metadata

                except re.error as e:
                    logger.error(f"Regex error in pattern '{pattern}': {e}")
                    continue

        return None

    def remove_stopwords(self, query: str) -> str:
        """Remove conversational stopwords from query.

        Args:
            query: User query

        Returns:
            Query with stopwords removed
        """
        cleaned = query.lower().strip()

        # Sort by length (longest first) to avoid partial matches
        for stopword in sorted(self.stopwords, key=len, reverse=True):
            cleaned = cleaned.replace(stopword, "")

        # Clean up extra spaces
        cleaned = " ".join(cleaned.split())

        return cleaned.strip()


class QueryOptimizationRAG:
    """RAG-based query optimization that learns from successful searches."""

    def __init__(self, storage_dir: Path = Path("data/query_optimization")):
        """Initialize query optimization RAG.

        Args:
            storage_dir: Directory to store query optimization data
        """
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.history_file = self.storage_dir / "query_history.jsonl"
        self.pattern_matcher = QueryPatternMatcher()

        logger.info("Query optimization RAG initialized")

    async def optimize_query(self, query: str) -> Tuple[str, Dict]:
        """Optimize a search query using patterns and learned transformations.

        Args:
            query: Original user query

        Returns:
            Tuple of (optimized_query, metadata)
        """
        metadata = {
            "original": query,
            "optimizations_applied": [],
            "source": "pattern_match"
        }

        # Step 1: Try pattern matching
        pattern_result = self.pattern_matcher.match_pattern(query)
        if pattern_result:
            optimized, pattern_meta = pattern_result
            metadata.update(pattern_meta)
            metadata["optimizations_applied"].append("pattern_match")
            return optimized, metadata

        # Step 2: If no pattern match, try learned transformations
        learned_result = await self.find_similar_query(query)
        if learned_result:
            optimized, similarity = learned_result
            metadata["optimizations_applied"].append("learned_transformation")
            metadata["similarity_score"] = similarity
            metadata["source"] = "learned"
            return optimized, metadata

        # Step 3: Fallback - basic stopword removal
        cleaned = self.pattern_matcher.remove_stopwords(query)
        if cleaned and cleaned != query.lower():
            metadata["optimizations_applied"].append("stopword_removal")
            metadata["source"] = "fallback"
            return cleaned, metadata

        # No optimization applied
        metadata["source"] = "original"
        return query, metadata

    async def find_similar_query(self, query: str, threshold: float = 0.7) -> Optional[Tuple[str, float]]:
        """Find similar past queries and return their successful transformations.

        Args:
            query: Current query
            threshold: Minimum similarity score (0-1)

        Returns:
            Tuple of (transformed_query, similarity_score) or None
        """
        if not self.history_file.exists():
            return None

        try:
            # Load query history
            async with aiofiles.open(self.history_file, 'r') as f:
                lines = await f.readlines()

            query_lower = query.lower()
            best_match = None
            best_score = 0.0

            for line in lines[-100:]:  # Check last 100 queries
                try:
                    entry = json.loads(line)
                    past_query = entry.get("original_query", "").lower()
                    transformed = entry.get("transformed_query", "")
                    success = entry.get("success", False)

                    if not success or not transformed:
                        continue

                    # Simple similarity: Jaccard similarity of words
                    similarity = self._calculate_similarity(query_lower, past_query)

                    if similarity > best_score and similarity >= threshold:
                        best_score = similarity
                        best_match = transformed

                except json.JSONDecodeError:
                    continue

            if best_match:
                logger.info(f"Found similar query with score {best_score:.2f}: '{query}' -> '{best_match}'")
                return best_match, best_score

            return None

        except Exception as e:
            logger.error(f"Error finding similar query: {e}")
            return None

    def _calculate_similarity(self, query1: str, query2: str) -> float:
        """Calculate Jaccard similarity between two queries.

        Args:
            query1: First query
            query2: Second query

        Returns:
            Similarity score (0-1)
        """
        words1 = set(query1.split())
        words2 = set(query2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union)

    async def record_search(
        self,
        original_query: str,
        transformed_query: str,
        results_count: int,
        success: bool,
        metadata: Optional[Dict] = None
    ):
        """Record a search for learning.

        Args:
            original_query: Original user query
            transformed_query: Transformed/optimized query
            results_count: Number of results returned
            success: Whether the search was successful
            metadata: Additional metadata
        """
        try:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "original_query": original_query,
                "transformed_query": transformed_query,
                "results_count": results_count,
                "success": success,
                "metadata": metadata or {}
            }

            # Append to history file (JSONL format)
            async with aiofiles.open(self.history_file, 'a') as f:
                await f.write(json.dumps(entry) + "\n")

            logger.debug(f"Recorded search: '{original_query}' -> '{transformed_query}' (success: {success})")

        except Exception as e:
            logger.error(f"Failed to record search: {e}")

    async def get_stats(self) -> Dict:
        """Get statistics about query optimizations.

        Returns:
            Dictionary of statistics
        """
        stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "pattern_matches": 0,
            "learned_matches": 0,
            "fallback_used": 0,
            "success_rate": 0.0
        }

        if not self.history_file.exists():
            return stats

        try:
            async with aiofiles.open(self.history_file, 'r') as f:
                lines = await f.readlines()

            for line in lines:
                try:
                    entry = json.loads(line)
                    stats["total_queries"] += 1

                    if entry.get("success"):
                        stats["successful_queries"] += 1

                    source = entry.get("metadata", {}).get("source", "")
                    if source == "pattern_match":
                        stats["pattern_matches"] += 1
                    elif source == "learned":
                        stats["learned_matches"] += 1
                    elif source == "fallback":
                        stats["fallback_used"] += 1

                except json.JSONDecodeError:
                    continue

            if stats["total_queries"] > 0:
                stats["success_rate"] = stats["successful_queries"] / stats["total_queries"]

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")

        return stats


# Singleton instance
_query_optimizer = None


def get_query_optimizer() -> QueryOptimizationRAG:
    """Get or create the global query optimizer instance.

    Returns:
        QueryOptimizationRAG instance
    """
    global _query_optimizer
    if _query_optimizer is None:
        _query_optimizer = QueryOptimizationRAG()
    return _query_optimizer
