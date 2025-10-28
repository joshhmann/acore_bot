"""RAG (Retrieval-Augmented Generation) service for context-aware responses."""
import logging
from pathlib import Path
from typing import List, Optional
import json

logger = logging.getLogger(__name__)


class RAGService:
    """Service for RAG functionality.

    This is a simple implementation using file-based document storage.
    For production, consider using vector databases like ChromaDB, Pinecone, or Weaviate.
    """

    def __init__(self, documents_path: str, vector_store_path: str, top_k: int = 3):
        """Initialize RAG service.

        Args:
            documents_path: Path to documents directory
            vector_store_path: Path to vector store (currently unused in simple implementation)
            top_k: Number of top results to retrieve
        """
        self.documents_path = Path(documents_path)
        self.vector_store_path = Path(vector_store_path)
        self.top_k = top_k
        self.documents = []

        # Create directories
        self.documents_path.mkdir(parents=True, exist_ok=True)
        self.vector_store_path.mkdir(parents=True, exist_ok=True)

        # Load documents
        self._load_documents()

    def _load_documents(self):
        """Load documents from the documents directory."""
        try:
            # Load text files
            for file_path in self.documents_path.glob("**/*.txt"):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.documents.append({
                        "path": str(file_path),
                        "content": content,
                        "filename": file_path.name
                    })

            # Load markdown files
            for file_path in self.documents_path.glob("**/*.md"):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.documents.append({
                        "path": str(file_path),
                        "content": content,
                        "filename": file_path.name
                    })

            logger.info(f"Loaded {len(self.documents)} documents for RAG")

        except Exception as e:
            logger.error(f"Failed to load RAG documents: {e}")

    def search(self, query: str, top_k: Optional[int] = None) -> List[dict]:
        """Search for relevant documents based on query.

        This is a simple keyword-based search. For production, use proper vector embeddings.

        Args:
            query: Search query
            top_k: Number of results to return (uses self.top_k if not specified)

        Returns:
            List of relevant document chunks
        """
        if not self.documents:
            return []

        k = top_k or self.top_k
        query_lower = query.lower()

        # Simple keyword matching (replace with vector similarity in production)
        results = []
        for doc in self.documents:
            content_lower = doc["content"].lower()

            # Count keyword matches
            query_words = query_lower.split()
            matches = sum(1 for word in query_words if word in content_lower)

            if matches > 0:
                results.append({
                    "filename": doc["filename"],
                    "path": doc["path"],
                    "content": doc["content"],
                    "relevance_score": matches / len(query_words)
                })

        # Sort by relevance and return top k
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:k]

    def get_context(self, query: str, max_length: int = 1000) -> str:
        """Get relevant context for a query.

        Args:
            query: User query
            max_length: Maximum character length of context

        Returns:
            Combined context string from relevant documents
        """
        results = self.search(query)

        if not results:
            return ""

        # Combine relevant documents into context
        context_parts = []
        total_length = 0

        for result in results:
            content = result["content"]
            filename = result["filename"]

            # Add document with attribution
            doc_text = f"[From {filename}]\n{content}\n"

            if total_length + len(doc_text) <= max_length:
                context_parts.append(doc_text)
                total_length += len(doc_text)
            else:
                # Add truncated version
                remaining = max_length - total_length
                if remaining > 100:  # Only add if meaningful space left
                    truncated = content[:remaining - 50] + "..."
                    context_parts.append(f"[From {filename}]\n{truncated}\n")
                break

        return "\n---\n".join(context_parts)

    def add_document(self, filename: str, content: str) -> bool:
        """Add a new document to the RAG system.

        Args:
            filename: Name for the document
            content: Document content

        Returns:
            True if successful
        """
        try:
            file_path = self.documents_path / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            # Reload documents
            self._load_documents()
            logger.info(f"Added document: {filename}")
            return True

        except Exception as e:
            logger.error(f"Failed to add document: {e}")
            return False

    def reload(self):
        """Reload all documents from disk."""
        self.documents = []
        self._load_documents()

    def list_documents(self) -> List[str]:
        """List all loaded documents.

        Returns:
            List of document filenames
        """
        return [doc["filename"] for doc in self.documents]

    def is_enabled(self) -> bool:
        """Check if RAG has documents loaded.

        Returns:
            True if documents are available
        """
        return len(self.documents) > 0


# TODO: For production RAG implementation:
# 1. Install: uv add chromadb sentence-transformers
# 2. Replace keyword search with vector embeddings
# 3. Use proper vector store (ChromaDB, Pinecone, etc.)
# 4. Implement document chunking for large documents
# 5. Add metadata filtering
# 6. Cache embeddings for performance
