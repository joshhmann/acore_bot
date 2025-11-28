"""RAG (Retrieval-Augmented Generation) service for context-aware responses."""
import logging
from pathlib import Path
from typing import List, Optional
import json
import aiofiles

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

    async def initialize(self):
        """Initialize the service asynchronously."""
        await self._load_documents()

    async def _load_documents(self):
        """Load documents from the documents directory."""
        try:
            self.documents = []
            files = []
            
            # Collect all files first
            files.extend(self.documents_path.glob("**/*.txt"))
            files.extend(self.documents_path.glob("**/*.md"))
            
            total_files = len(files)
            logger.info(f"Found {total_files} documents to load...")
            
            count = 0
            for file_path in files:
                try:
                    # Extract category from parent folder name
                    # e.g. data/documents/dagoth/lore.txt -> category="dagoth"
                    # e.g. data/documents/file.txt -> category="documents" (or whatever root is)
                    category = file_path.parent.name.lower()
                    if category == self.documents_path.name.lower():
                        category = "general"

                    async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        content = await f.read()
                        self.documents.append({
                            "path": str(file_path),
                            "content": content,
                            "content_lower": content.lower(),
                            "filename": file_path.name,
                            "category": category
                        })
                        count += 1
                        if count % 1000 == 0:
                            logger.info(f"Loaded {count}/{total_files} documents...")
                except Exception as e:
                    logger.error(f"Error reading {file_path}: {e}")

            logger.info(f"Successfully loaded {len(self.documents)} documents for RAG")

        except Exception as e:
            logger.error(f"Failed to load RAG documents: {e}")

    def search(self, query: str, top_k: Optional[int] = None, category: Optional[str] = None, boost_category: Optional[str] = None) -> List[dict]:
        """Search for relevant documents based on query.

        This is a simple keyword-based search. For production, use proper vector embeddings.

        Args:
            query: Search query
            top_k: Number of results to return (uses self.top_k if not specified)
            category: Filter by category (exact match)
            boost_category: Boost score for documents in this category

        Returns:
            List of relevant document chunks
        """
        if not self.documents:
            return []

        k = top_k or self.top_k
        query_lower = query.lower()
        query_words = query_lower.split()
        
        if not query_words:
            return []

        # Simple keyword matching (replace with vector similarity in production)
        results = []
        
        # Advanced search with fuzzy matching and keyword extraction
        results = []
        
        # Extract meaningful keywords (ignore common stop words)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'shall', 'should', 'can', 'could', 'may', 'might', 'must', 'about', 'what', 'when', 'where', 'who', 'why', 'how', 'which', 'this', 'that', 'these', 'those', 'it', 'its', 'they', 'them', 'their', 'he', 'him', 'his', 'she', 'her', 'hers', 'you', 'your', 'yours', 'we', 'us', 'our', 'ours', 'i', 'me', 'my', 'mine'}
        
        keywords = [w for w in query_words if w not in stop_words and len(w) >= 2]
        
        # If no meaningful keywords, fall back to all words
        if not keywords:
            keywords = query_words

        for doc in self.documents:
            # Filter by category if specified
            if category and doc["category"] != category.lower():
                continue

            content_lower = doc["content_lower"]
            
            # Calculate score based on keyword presence
            matches = 0
            matched_keywords = []
            
            for word in keywords:
                if word in content_lower:
                    matches += 1
                    matched_keywords.append(word)
                else:
                    # Simple fuzzy check (singular/plural)
                    if word.endswith('s') and word[:-1] in content_lower:
                        matches += 0.8
                        matched_keywords.append(word)
                    elif word + 's' in content_lower:
                        matches += 0.8
                        matched_keywords.append(word)
            
            if matches > 0:
                # Base score is percentage of keywords matched
                score = matches / len(keywords)
                
                # Boost for exact phrase match (if query is multi-word)
                if len(query_words) > 1 and query_lower in content_lower:
                    score *= 2.0
                
                # Apply category boost
                if boost_category and doc["category"] == boost_category.lower():
                    score *= 5.0  # 500% boost for matching category
                
                results.append({
                    "filename": doc["filename"],
                    "path": doc["path"],
                    "content": doc["content"],
                    "category": doc["category"],
                    "relevance_score": score,
                    "matched_keywords": matched_keywords
                })

        # Sort by relevance and return top k
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        top_results = results[:k]
        
        if top_results:
            logger.info(f"RAG Search '{query}' (cat={category}, boost={boost_category}) found {len(top_results)} results:")
            for i, res in enumerate(top_results):
                logger.info(f"  {i+1}. {res['filename']} (Score: {res['relevance_score']:.2f}) - Matched: {res.get('matched_keywords')}")
        else:
            logger.info(f"RAG Search '{query}' found NO results")
            
        return top_results

    def get_context(self, query: str, max_length: int = 1000, category: Optional[str] = None, boost_category: Optional[str] = None) -> str:
        """Get relevant context for a query.

        Args:
            query: User query
            max_length: Maximum character length of context

        Returns:
            Combined context string from relevant documents
        """
        import traceback
        caller = traceback.extract_stack()[-2]
        logger.debug(f"get_context called from {caller.filename}:{caller.lineno} in {caller.name}")
        
        results = self.search(query, category=category, boost_category=boost_category)

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

    async def add_document(self, filename: str, content: str) -> bool:
        """Add a new document to the RAG system.

        Args:
            filename: Name for the document
            content: Document content

        Returns:
            True if successful
        """
        try:
            file_path = self.documents_path / filename
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(content)

            # Reload documents
            await self._load_documents()
            logger.info(f"Added document: {filename}")
            return True

        except Exception as e:
            logger.error(f"Failed to add document: {e}")
            return False

    async def reload(self):
        """Reload all documents from disk."""
        self.documents = []
        await self._load_documents()

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
