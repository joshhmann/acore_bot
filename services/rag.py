"""RAG (Retrieval-Augmented Generation) service for context-aware responses."""
import logging
from pathlib import Path
from typing import List, Optional, Dict
import json
import aiofiles
import asyncio
from functools import lru_cache

logger = logging.getLogger(__name__)


class RAGService:
    """Enhanced RAG service with vector embeddings support.

    Features:
    - Vector similarity search using ChromaDB and sentence-transformers
    - Document chunking for better retrieval
    - Fallback to keyword search if vector store unavailable
    - Metadata filtering and category boosting
    - Cached embeddings for performance
    """

    def __init__(self, documents_path: str, vector_store_path: str, top_k: int = 3, use_vector_search: bool = True):
        """Initialize RAG service.

        Args:
            documents_path: Path to documents directory
            vector_store_path: Path to vector store
            top_k: Number of top results to retrieve
            use_vector_search: Use vector embeddings (True) or keyword search (False)
        """
        self.documents_path = Path(documents_path)
        self.vector_store_path = Path(vector_store_path)
        self.top_k = top_k
        self.documents = []
        self.use_vector_search = use_vector_search

        # Vector search components
        self.chroma_client = None
        self.collection = None
        self.embedding_model = None

        # Cache for embeddings to avoid recomputing for identical queries
        self.embedding_cache = {}
        self.cache_max_size = 500

        # Create directories
        self.documents_path.mkdir(parents=True, exist_ok=True)
        self.vector_store_path.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        """Initialize the service asynchronously."""
        # Load documents first
        await self._load_documents()

        # Initialize vector store if enabled
        if self.use_vector_search:
            await self._initialize_vector_store()

    async def _initialize_vector_store(self):
        """Initialize ChromaDB and embedding model."""
        try:
            # Force disable telemetry before import
            import os
            os.environ["ANONYMIZED_TELEMETRY"] = "False"
            
            import chromadb
            from sentence_transformers import SentenceTransformer

            logger.info("Initializing vector store...")

            # Initialize ChromaDB client
            self.chroma_client = chromadb.PersistentClient(path=str(self.vector_store_path))

            # Get or create collection
            try:
                self.collection = self.chroma_client.get_collection(name="documents")
                logger.info(f"Loaded existing collection with {self.collection.count()} embeddings")
            except Exception:
                self.collection = self.chroma_client.create_collection(
                    name="documents",
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info("Created new collection")

            # Initialize embedding model (all-MiniLM-L6-v2 is fast and good)
            logger.info("Loading embedding model (this may take a moment)...")
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Embedding model loaded successfully")

            # Index documents if collection is empty
            if self.collection.count() == 0 and len(self.documents) > 0:
                await self._index_documents()

            logger.info("Vector store initialized successfully")

        except Exception as e:
            logger.warning(f"Failed to initialize vector store: {e}")
            logger.warning("Falling back to keyword-based search")
            self.use_vector_search = False
            self.chroma_client = None
            self.collection = None
            self.embedding_model = None

    async def _load_documents(self):
        """Load documents from the documents directory."""
        try:
            self.documents = []
            files = []

            # Collect all files first
            files.extend(self.documents_path.glob("**/*.txt"))
            files.extend(self.documents_path.glob("**/*.md"))

            total_files = len(files)
            if total_files == 0:
                logger.info("No documents found in RAG directory")
                return

            logger.info(f"Found {total_files} documents to load...")

            count = 0
            for file_path in files:
                try:
                    # Extract category from parent folder name
                    category = file_path.parent.name.lower()
                    if category == self.documents_path.name.lower():
                        category = "general"

                    async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        content = await f.read()

                        # Chunk large documents
                        chunks = self._chunk_document(content, file_path.name)

                        for i, chunk in enumerate(chunks):
                            self.documents.append({
                                "id": f"{file_path.name}_{i}",
                                "path": str(file_path),
                                "content": chunk,
                                "content_lower": chunk.lower(),
                                "filename": file_path.name,
                                "category": category,
                                "chunk_index": i,
                                "total_chunks": len(chunks)
                            })

                        count += 1
                        if count % 100 == 0:
                            logger.info(f"Loaded {count}/{total_files} documents...")

                except Exception as e:
                    logger.error(f"Error reading {file_path}: {e}")

            logger.info(f"Successfully loaded {len(self.documents)} document chunks from {count} files")

        except Exception as e:
            logger.error(f"Failed to load RAG documents: {e}")

    def _chunk_document(self, content: str, filename: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split document into overlapping chunks.

        Args:
            content: Document content
            filename: Document filename
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks

        Returns:
            List of text chunks
        """
        # For small documents, return as-is
        if len(content) <= chunk_size:
            return [content]

        chunks = []
        start = 0

        while start < len(content):
            end = start + chunk_size

            # Try to end at a sentence boundary
            if end < len(content):
                # Look for sentence endings near the chunk boundary
                for punct in ['. ', '.\n', '! ', '!\n', '? ', '?\n']:
                    last_punct = content[start:end].rfind(punct)
                    if last_punct > chunk_size * 0.7:  # At least 70% through chunk
                        end = start + last_punct + len(punct)
                        break

            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start position with overlap
            start = end - overlap

        return chunks

    async def _index_documents(self):
        """Index all documents into ChromaDB."""
        if not self.collection or not self.embedding_model:
            return

        logger.info(f"Indexing {len(self.documents)} document chunks...")

        # Batch processing for efficiency
        batch_size = 100
        for i in range(0, len(self.documents), batch_size):
            batch = self.documents[i:i + batch_size]

            # Prepare data
            ids = [doc["id"] for doc in batch]
            documents = [doc["content"] for doc in batch]
            metadatas = [
                {
                    "filename": doc["filename"],
                    "category": doc["category"],
                    "chunk_index": doc["chunk_index"],
                    "path": doc["path"]
                }
                for doc in batch
            ]

            # Generate embeddings
            embeddings = self.embedding_model.encode(documents, show_progress_bar=False).tolist()

            # Add to collection
            self.collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )

            if (i + batch_size) % 500 == 0:
                logger.info(f"Indexed {min(i + batch_size, len(self.documents))}/{len(self.documents)} chunks...")

        logger.info(f"Indexing complete! {self.collection.count()} embeddings in vector store")

    def search(self, query: str, top_k: Optional[int] = None, category: Optional[str] = None, boost_category: Optional[str] = None) -> List[dict]:
        """Search for relevant documents.

        Uses vector similarity if available, falls back to keyword search.

        Args:
            query: Search query
            top_k: Number of results to return
            category: Filter by category
            boost_category: Boost score for documents in this category

        Returns:
            List of relevant document chunks
        """
        k = top_k or self.top_k

        # Try vector search first
        if self.use_vector_search and self.collection and self.embedding_model:
            return self._vector_search(query, k, category, boost_category)
        else:
            # Fallback to keyword search
            return self._keyword_search(query, k, category, boost_category)

    def _vector_search(self, query: str, top_k: int, category: Optional[str], boost_category: Optional[str]) -> List[dict]:
        """Perform vector similarity search."""
        try:
            # Generate query embedding
            # Note: We need to use asyncio.run or similar if calling async from sync method,
            # but usually this method is called from search which is sync.
            # However, for performance we should make search async or use asyncio.run here.
            # But making search async requires changing interface.
            # For now, we'll keep it sync but blocking if not refactored fully.
            # Actually, `search` is synchronous in interface but we can assume we are in async context?
            # Wait, `get_context` calls `search` synchronously.
            # The plan suggested making `_get_embedding` async.
            # But since `search` is synchronous, we cannot await `_get_embedding`.

            # Let's check if we can check cache synchronously here.

            if query in self.embedding_cache:
                query_embedding = self.embedding_cache[query]
            else:
                query_embedding = self.embedding_model.encode([query])[0].tolist()
                self.embedding_cache[query] = query_embedding
                if len(self.embedding_cache) > self.cache_max_size:
                    oldest_key = next(iter(self.embedding_cache))
                    del self.embedding_cache[oldest_key]

            # Build where filter
            where_filter = None
            if category:
                where_filter = {"category": category}

            # Search with more results than needed for boosting
            search_k = top_k * 3 if boost_category else top_k

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(search_k, self.collection.count()),
                where=where_filter,
                include=["documents", "metadatas", "distances"]
            )

            if not results or not results['documents'][0]:
                return []

            # Format results
            formatted_results = []
            for i, (doc, metadata, distance) in enumerate(zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            )):
                # Convert distance to similarity score (cosine distance to similarity)
                similarity = 1 - distance

                # Apply category boost
                score = similarity
                if boost_category and metadata['category'] == boost_category.lower():
                    score *= 5.0

                formatted_results.append({
                    "filename": metadata['filename'],
                    "path": metadata['path'],
                    "content": doc,
                    "category": metadata['category'],
                    "relevance_score": score,
                    "similarity": similarity,
                    "search_method": "vector"
                })

            # Re-sort after boosting
            formatted_results.sort(key=lambda x: x["relevance_score"], reverse=True)
            top_results = formatted_results[:top_k]

            if top_results:
                logger.info(f"Vector Search '{query}' found {len(top_results)} results:")
                for i, res in enumerate(top_results[:3]):
                    logger.info(f"  {i+1}. {res['filename']} (Score: {res['relevance_score']:.2f}, Similarity: {res['similarity']:.2f})")

            return top_results

        except Exception as e:
            logger.error(f"Vector search failed: {e}, falling back to keyword search")
            return self._keyword_search(query, top_k, category, boost_category)

    def _keyword_search(self, query: str, top_k: int, category: Optional[str], boost_category: Optional[str]) -> List[dict]:
        """Perform keyword-based search (fallback)."""
        if not self.documents:
            return []

        query_lower = query.lower()
        query_words = query_lower.split()

        if not query_words:
            return []

        # Extract meaningful keywords
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'shall', 'should', 'can', 'could', 'may', 'might', 'must', 'about', 'what', 'when', 'where', 'who', 'why', 'how', 'which', 'this', 'that', 'these', 'those', 'it', 'its', 'they', 'them', 'their', 'he', 'him', 'his', 'she', 'her', 'hers', 'you', 'your', 'yours', 'we', 'us', 'our', 'ours', 'i', 'me', 'my', 'mine'}

        keywords = [w for w in query_words if w not in stop_words and len(w) >= 2]

        if not keywords:
            keywords = query_words

        results = []
        for doc in self.documents:
            # Filter by category
            if category and doc["category"] != category.lower():
                continue

            content_lower = doc["content_lower"]

            # Calculate score
            matches = 0
            matched_keywords = []

            for word in keywords:
                if word in content_lower:
                    matches += 1
                    matched_keywords.append(word)
                else:
                    # Fuzzy check
                    if word.endswith('s') and word[:-1] in content_lower:
                        matches += 0.8
                        matched_keywords.append(word)
                    elif word + 's' in content_lower:
                        matches += 0.8
                        matched_keywords.append(word)

            if matches > 0:
                score = matches / len(keywords)

                # Boost for exact phrase
                if len(query_words) > 1 and query_lower in content_lower:
                    score *= 2.0

                # Apply category boost
                if boost_category and doc["category"] == boost_category.lower():
                    score *= 5.0

                results.append({
                    "filename": doc["filename"],
                    "path": doc["path"],
                    "content": doc["content"],
                    "category": doc["category"],
                    "relevance_score": score,
                    "matched_keywords": matched_keywords,
                    "search_method": "keyword"
                })

        # Sort and return top k
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        top_results = results[:top_k]

        if top_results:
            logger.info(f"Keyword Search '{query}' found {len(top_results)} results:")
            for i, res in enumerate(top_results[:3]):
                logger.info(f"  {i+1}. {res['filename']} (Score: {res['relevance_score']:.2f})")

        return top_results

    def get_context(self, query: str, max_length: int = 1000, category: Optional[str] = None, boost_category: Optional[str] = None) -> str:
        """Get relevant context for a query.

        Args:
            query: User query
            max_length: Maximum character length of context
            category: Filter by category
            boost_category: Boost documents in this category

        Returns:
            Combined context string from relevant documents
        """
        import traceback
        caller = traceback.extract_stack()[-2]
        logger.debug(f"get_context called from {caller.filename}:{caller.lineno} in {caller.name}")

        results = self.search(query, category=category, boost_category=boost_category)

        if not results:
            return ""

        # Combine relevant documents
        context_parts = []
        total_length = 0

        for result in results:
            content = result["content"]
            filename = result["filename"]

            doc_text = f"[From {filename}]\n{content}\n"

            if total_length + len(doc_text) <= max_length:
                context_parts.append(doc_text)
                total_length += len(doc_text)
            else:
                remaining = max_length - total_length
                if remaining > 100:
                    truncated = content[:remaining - 50] + "..."
                    context_parts.append(f"[From {filename}]\n{truncated}\n")
                break

        return "\n---\n".join(context_parts)

    async def add_document(self, filename: str, content: str, category: str = "general") -> bool:
        """Add a new document to the RAG system.

        Args:
            filename: Name for the document
            content: Document content
            category: Document category

        Returns:
            True if successful
        """
        try:
            # Create category directory if needed
            category_dir = self.documents_path / category
            category_dir.mkdir(exist_ok=True)

            file_path = category_dir / filename
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(content)

            # Reload documents and re-index
            await self._load_documents()

            if self.use_vector_search and self.collection:
                await self._index_documents()

            logger.info(f"Added document: {filename} to category {category}")
            return True

        except Exception as e:
            logger.error(f"Failed to add document: {e}")
            return False

    async def reload(self):
        """Reload all documents from disk."""
        self.documents = []
        await self._load_documents()

        # Re-index if using vector store
        if self.use_vector_search and self.collection:
            # Clear existing collection
            try:
                self.chroma_client.delete_collection("documents")
                self.collection = self.chroma_client.create_collection(
                    name="documents",
                    metadata={"hnsw:space": "cosine"}
                )
                await self._index_documents()
            except Exception as e:
                logger.error(f"Failed to reload vector store: {e}")

    def list_documents(self) -> List[str]:
        """List all loaded documents.

        Returns:
            List of document filenames
        """
        # Get unique filenames
        filenames = set(doc["filename"] for doc in self.documents)
        return sorted(list(filenames))

    def is_enabled(self) -> bool:
        """Check if RAG has documents loaded.

        Returns:
            True if documents are available
        """
        return len(self.documents) > 0

    def get_stats(self) -> Dict:
        """Get RAG service statistics.

        Returns:
            Statistics dictionary
        """
        stats = {
            "total_documents": len(set(doc["filename"] for doc in self.documents)),
            "total_chunks": len(self.documents),
            "search_method": "vector" if self.use_vector_search else "keyword",
            "categories": {}
        }

        # Count by category
        for doc in self.documents:
            cat = doc["category"]
            stats["categories"][cat] = stats["categories"].get(cat, 0) + 1

        # Vector store stats
        if self.collection:
            stats["vector_store_embeddings"] = self.collection.count()
            stats["embedding_model"] = "all-MiniLM-L6-v2"

        return stats
