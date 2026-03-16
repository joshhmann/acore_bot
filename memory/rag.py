from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Document:
    """A document in the RAG store."""

    id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] = field(default_factory=list, repr=False)


@dataclass(slots=True)
class SearchResult:
    """Result of a RAG search."""

    document: Document
    score: float


@dataclass(slots=True)
class RAGResult:
    """Legacy RAG result for backward compatibility."""

    content: str
    source: str = ""
    score: float = 0.0


class RAGStore:
    """Simple in-memory RAG store with hash-based embeddings."""

    def __init__(self, embedding_dim: int = 128) -> None:
        """Initialize the RAG store.

        Args:
            embedding_dim: Dimension of hash-based embeddings (default 128)
        """
        self.embedding_dim = embedding_dim
        self._documents: dict[str, Document] = {}

    def _compute_embedding(self, text: str) -> list[float]:
        """Compute a simple hash-based embedding for text.

        Uses multiple hash functions to create a fixed-size embedding vector.
        Normalizes the result to unit length for cosine similarity.

        Args:
            text: The text to embed

        Returns:
            Normalized embedding vector
        """
        # Initialize embedding vector
        embedding = [0.0] * self.embedding_dim

        # Use multiple hash functions with different seeds
        for i in range(self.embedding_dim):
            # Create a unique hash for each dimension
            hash_input = f"{i}:{text}"
            hash_bytes = hashlib.md5(hash_input.encode()).digest()

            # Convert first 4 bytes to a float in range [-1, 1]
            int_val = int.from_bytes(hash_bytes[:4], byteorder="little")
            normalized = (int_val / (2**31 - 1)) - 1.0
            embedding[i] = normalized

        # Normalize to unit length for cosine similarity
        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]

        return embedding

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score in range [-1, 1]
        """
        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have same dimension")

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        # Vectors are pre-normalized, so cosine similarity = dot product
        return dot_product

    def add_document(
        self, doc_id: str, content: str, metadata: dict[str, Any] | None = None
    ) -> Document:
        """Add a document to the store.

        Args:
            doc_id: Unique identifier for the document
            content: Document content
            metadata: Optional metadata dictionary

        Returns:
            The created Document
        """
        embedding = self._compute_embedding(content)
        doc = Document(
            id=doc_id,
            content=content,
            metadata=metadata or {},
            embedding=embedding,
        )
        self._documents[doc_id] = doc
        return doc

    async def search(
        self,
        query: str,
        top_k: int = 5,
        persona_id: str | None = None,
        room_id: str | None = None,
    ) -> list[SearchResult]:
        """Search for documents similar to the query.

        Args:
            query: Search query text
            top_k: Number of top results to return
            persona_id: Optional persona identifier for filtering (currently unused)
            room_id: Optional room identifier for filtering (currently unused)

        Returns:
            List of SearchResult sorted by relevance (highest first)
        """
        if persona_id or room_id:
            pass  # Accepted for API compatibility but not yet implemented
        if not self._documents:
            return []

        query_embedding = self._compute_embedding(query)

        # Compute similarity for all documents
        results: list[SearchResult] = []
        for doc in self._documents.values():
            score = self._cosine_similarity(query_embedding, doc.embedding)
            results.append(SearchResult(document=doc, score=score))

        # Sort by score descending and return top_k
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def get_document(self, doc_id: str) -> Document | None:
        """Retrieve a document by ID.

        Args:
            doc_id: Document identifier

        Returns:
            Document if found, None otherwise
        """
        return self._documents.get(doc_id)

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document by ID.

        Args:
            doc_id: Document identifier

        Returns:
            True if document was deleted, False if not found
        """
        if doc_id in self._documents:
            del self._documents[doc_id]
            return True
        return False

    def list_documents(self) -> list[str]:
        """List all document IDs in the store.

        Returns:
            List of document IDs
        """
        return list(self._documents.keys())

    def clear(self) -> None:
        """Clear all documents from the store."""
        self._documents.clear()

    async def search_by_persona(
        self, persona_id: str, room_id: str, query: str
    ) -> list[RAGResult]:
        """Search for documents filtered by persona and room (legacy async interface).

        Args:
            persona_id: Persona identifier
            room_id: Room/channel identifier
            query: Search query

        Returns:
            List of RAGResult for backward compatibility
        """
        del persona_id, room_id  # Currently not filtering by these

        results = self.search(query, top_k=5)
        return [
            RAGResult(
                content=res.document.content,
                source=res.document.metadata.get("source", ""),
                score=res.score,
            )
            for res in results
        ]
