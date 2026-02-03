"""BM25 Keyword Search and Reciprocal Rank Fusion implementation.

This module provides hybrid search capabilities combining keyword-based BM25
with vector similarity search using Reciprocal Rank Fusion (RRF).
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional
import math

logger = logging.getLogger(__name__)


@dataclass
class BM25Document:
    """Document representation for BM25 indexing."""

    id: str
    content: str
    content_lower: str
    metadata: Dict


@dataclass
class BM25Result:
    """BM25 search result with score and document info."""

    doc_id: str
    score: float
    content: str
    metadata: Dict


class BM25Index:
    """BM25 (Okapi Best Matching 25) inverted index for keyword search.

    Implements the BM25 ranking function for efficient keyword-based
    document retrieval. Supports phrase queries and fuzzy matching.
    """

    def __init__(
        self,
        k1: float = 1.2,
        b: float = 0.75,
        epsilon: float = 0.25,
    ):
        """Initialize BM25 index.

        Args:
            k1: Term frequency saturation parameter (default: 1.2)
            b: Length normalization parameter (default: 0.75)
            epsilon: IDF smoothing parameter (default: 0.25)
        """
        self.k1 = k1
        self.b = b
        self.epsilon = epsilon

        self.documents: Dict[str, BM25Document] = {}
        self.inverted_index: Dict[str, Dict[str, List[int]]] = {}
        self.doc_lengths: Dict[str, int] = {}
        self.avg_doc_length: float = 0.0
        self.num_docs: int = 0
        self.doc_freqs: Dict[str, int] = {}

    def add_document(self, doc: BM25Document):
        """Add a document to the BM25 index.

        Args:
            doc: Document to add
        """
        self.documents[doc.id] = doc
        self.doc_lengths[doc.id] = len(doc.content_lower.split())

        words = self._tokenize(doc.content_lower)
        word_positions = defaultdict(list)

        for pos, word in enumerate(words):
            word_positions[word].append(pos)

        for word, positions in word_positions.items():
            if word not in self.inverted_index:
                self.inverted_index[word] = {}
            self.inverted_index[word][doc.id] = positions

            if doc.id not in self.doc_freqs:
                self.doc_freqs[word] = 0
            self.doc_freqs[word] += 1

        self.num_docs += 1
        self._update_avg_doc_length()

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words.

        Args:
            text: Text to tokenize

        Returns:
            List of tokens
        """
        text = text.lower()
        tokens = re.findall(r"\b[a-z]+\b", text)
        return tokens

    def _update_avg_doc_length(self):
        """Update average document length."""
        if self.num_docs > 0:
            total_length = sum(self.doc_lengths.values())
            self.avg_doc_length = total_length / self.num_docs

    def _compute_idf(self, word: str) -> float:
        """Compute IDF for a term.

        Args:
            word: Term to compute IDF for

        Returns:
            IDF score
        """
        n = self.num_docs
        df = self.doc_freqs.get(word, 0)

        if df == 0:
            return self.epsilon

        return math.log((n - df + 0.5) / (df + 0.5) + 1)

    def _compute_tf(self, doc_id: str, word: str) -> float:
        """Compute term frequency for a term in a document.

        Args:
            doc_id: Document ID
            word: Term to compute TF for

        Returns:
            Term frequency
        """
        positions = self.inverted_index.get(word, {}).get(doc_id, [])
        return len(positions)

    def search(
        self,
        query: str,
        top_k: int = 10,
        include_phrases: bool = True,
    ) -> List[BM25Result]:
        """Search the BM25 index.

        Args:
            query: Search query
            top_k: Number of top results to return
            include_phrases: Whether to include phrase matching

        Returns:
            List of BM25Result sorted by score (descending)
        """
        if not self.documents:
            return []

        query_lower = query.lower()
        query_words = self._tokenize(query_lower)
        query_words = [w for w in query_words if len(w) >= 2]

        if not query_words:
            return []

        scores: Dict[str, float] = defaultdict(float)

        for word in set(query_words):
            idf = self._compute_idf(word)

            for doc_id in self.documents:
                tf = self._compute_tf(doc_id, word)
                if tf > 0:
                    doc_length = self.doc_lengths[doc_id]
                    tf_saturation = (tf * (self.k1 + 1)) / (
                        tf
                        + self.k1
                        * (1 - self.b + self.b * doc_length / self.avg_doc_length)
                    )
                    scores[doc_id] += idf * tf_saturation

        if include_phrases and len(query_words) > 1:
            phrase_query = query_lower
            phrase_matches = self._phrase_search(phrase_query)

            boost_factor = 2.0
            for doc_id, match_score in phrase_matches.items():
                scores[doc_id] += match_score * boost_factor

        results = []
        for doc_id, score in scores.items():
            doc = self.documents.get(doc_id)
            if doc:
                results.append(
                    BM25Result(
                        doc_id=doc_id,
                        score=score,
                        content=doc.content,
                        metadata=doc.metadata,
                    )
                )

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def _phrase_search(self, phrase: str) -> Dict[str, float]:
        """Search for exact phrase matches.

        Args:
            phrase: Phrase to search for

        Returns:
            Dictionary mapping document IDs to match scores
        """
        phrase_words = self._tokenize(phrase)
        if len(phrase_words) < 2:
            return {}

        phrase_length = len(phrase_words)
        matches: Dict[str, float] = {}

        for word in phrase_words:
            if word not in self.inverted_index:
                return {}

        for doc_id in self.documents:
            doc = self.documents[doc_id]
            words = self._tokenize(doc.content_lower)

            for i in range(len(words) - phrase_length + 1):
                if words[i : i + phrase_length] == phrase_words:
                    if doc_id not in matches:
                        matches[doc_id] = 0.0
                    matches[doc_id] += 1.0

        return matches

    def get_stats(self) -> Dict:
        """Get index statistics.

        Returns:
            Dictionary with index statistics
        """
        return {
            "num_documents": self.num_docs,
            "vocabulary_size": len(self.inverted_index),
            "avg_doc_length": self.avg_doc_length,
            "k1": self.k1,
            "b": self.b,
        }


def reciprocal_rank_fusion(
    vector_results: List[dict],
    keyword_results: List[dict],
    k: int = 60,
    vector_weight: float = 0.5,
    keyword_weight: float = 0.5,
) -> List[dict]:
    """Combine vector and keyword results using Reciprocal Rank Fusion.

    RRF combines multiple ranked lists by computing:
        score(d) = w_V * 1/(rank_V(d) + k) + w_K * 1/(rank_K(d) + k)

    Args:
        vector_results: Results from vector search (already sorted)
        keyword_results: Results from keyword search (already sorted)
        k: RRF constant (default: 60)
        vector_weight: Weight for vector scores (default: 0.5)
        keyword_weight: Weight for keyword scores (default: 0.5)

    Returns:
        Combined results sorted by RRF score (descending)
    """
    combined_scores: Dict[str, dict] = {}

    for rank, result in enumerate(vector_results):
        doc_id = result.get("id") or result.get("doc_id") or result.get("filename")
        if doc_id:
            rrf_score = vector_weight / (rank + k)
            combined_scores[doc_id] = {
                "doc_id": doc_id,
                "vector_score": result.get(
                    "relevance_score", result.get("similarity", 0)
                ),
                "vector_rank": rank + 1,
                "rrf_score": rrf_score,
                "content": result.get("content", ""),
                "metadata": result.get("metadata", {}),
                "category": result.get(
                    "category", result.get("metadata", {}).get("category", "unknown")
                ),
                "search_methods": ["vector"],
            }

    for rank, result in enumerate(keyword_results):
        doc_id = result.get("id") or result.get("doc_id") or result.get("filename")
        if doc_id:
            rrf_score = keyword_weight / (rank + k)

            if doc_id in combined_scores:
                combined_scores[doc_id]["rrf_score"] += rrf_score
                combined_scores[doc_id]["keyword_score"] = result.get(
                    "relevance_score", 0
                )
                combined_scores[doc_id]["keyword_rank"] = rank + 1
                combined_scores[doc_id]["search_methods"].append("keyword")
            else:
                combined_scores[doc_id] = {
                    "doc_id": doc_id,
                    "vector_score": 0,
                    "vector_rank": None,
                    "keyword_score": result.get("relevance_score", 0),
                    "keyword_rank": rank + 1,
                    "rrf_score": rrf_score,
                    "content": result.get("content", ""),
                    "metadata": result.get("metadata", {}),
                    "category": result.get(
                        "category",
                        result.get("metadata", {}).get("category", "unknown"),
                    ),
                    "search_methods": ["keyword"],
                }

    results = list(combined_scores.values())
    results.sort(key=lambda x: x["rrf_score"], reverse=True)

    return results


def normalize_scores(
    results: List[dict], score_key: str = "relevance_score"
) -> List[dict]:
    """Normalize scores to 0-1 range using min-max normalization.

    Args:
        results: List of result dictionaries
        score_key: Key for the score to normalize

    Returns:
        Results with normalized scores
    """
    if not results:
        return results

    scores = [r.get(score_key, 0) for r in results]
    min_score = min(scores)
    max_score = max(scores)

    if max_score == min_score:
        return results

    for result in results:
        original_score = result.get(score_key, 0)
        normalized = (original_score - min_score) / (max_score - min_score)
        result[score_key] = normalized

    return results
