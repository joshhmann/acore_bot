"""RAG (Retrieval-Augmented Generation) service with hybrid search and re-ranking.

Enhanced Features:
- Hybrid search (vector similarity + BM25 keyword)
- Cross-encoder re-ranking for improved accuracy
- Real-time Discord message indexing
- Query expansion and processing
- Reciprocal Rank Fusion (RRF) for result fusion
"""

import asyncio
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import aiofiles
import time

logger = logging.getLogger(__name__)

from config import Config


@dataclass
class SearchResult:
    """Unified search result from hybrid search."""

    id: str
    content: str
    relevance_score: float
    vector_score: float = 0.0
    keyword_score: float = 0.0
    rerank_score: float = 0.0
    metadata: Dict = field(default_factory=dict)
    search_methods: List[str] = field(default_factory=list)
    rank: int = 0


@dataclass
class IndexingTask:
    """Represents a document to be indexed."""

    message_id: str
    content: str
    metadata: Dict


class QueryProcessor:
    """Process and expand queries for better retrieval."""

    STOP_WORDS = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "shall",
        "should",
        "can",
        "could",
        "may",
        "might",
        "must",
        "about",
        "what",
        "when",
        "where",
        "who",
        "why",
        "how",
        "which",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "they",
        "them",
        "their",
        "he",
        "him",
        "his",
        "she",
        "her",
        "hers",
        "you",
        "your",
        "yours",
        "we",
        "us",
        "our",
        "ours",
        "i",
        "me",
        "my",
        "mine",
    }

    def __init__(self, enable_expansion: bool = True, sub_query_count: int = 3):
        self.enable_expansion = enable_expansion
        self.sub_query_count = sub_query_count

    def extract_keywords(self, query: str) -> List[str]:
        """Extract meaningful keywords from query.

        Args:
            query: Search query

        Returns:
            List of extracted keywords
        """
        query_lower = query.lower()
        words = re.findall(r"\b[a-z]+\b", query_lower)
        keywords = [w for w in words if w not in self.STOP_WORDS and len(w) >= 2]
        return keywords

    def extract_entities(self, query: str) -> List[str]:
        """Extract potential named entities (simple pattern-based).

        Args:
            query: Search query

        Returns:
            List of potential entity names
        """
        words = query.split()
        entities = []
        current_entity = []

        for word in words:
            if word[0].isupper() if word else False:
                current_entity.append(word)
            elif current_entity:
                entities.append(" ".join(current_entity))
                current_entity = []

        if current_entity:
            entities.append(" ".join(current_entity))

        return entities

    def expand_query(self, query: str) -> List[str]:
        """Generate sub-queries for better coverage.

        Args:
            query: Original query

        Returns:
            List of sub-queries including original
        """
        if not self.enable_expansion:
            return [query]

        keywords = self.extract_keywords(query)
        sub_queries = [query]

        if len(keywords) >= 2:
            sub_queries.append(" ".join(keywords[:2]))
            sub_queries.append(" ".join(keywords[-2:]))

        if len(keywords) >= 3:
            sub_queries.append(" ".join(keywords[:3]))
            sub_queries.append(keywords[0] + " " + keywords[-1])

        return list(set(sub_queries))[: self.sub_query_count + 1]

    def understand_intent(self, query: str) -> Dict[str, Any]:
        """Analyze query intent and characteristics.

        Args:
            query: Search query

        Returns:
            Dictionary with intent analysis
        """
        keywords = self.extract_keywords(query)
        entities = self.extract_entities(query)

        intent_type = "general"
        if any(w in query.lower() for w in ["how", "why", "what is", "explain"]):
            intent_type = "explanatory"
        elif any(w in query.lower() for w in ["who", "when", "where"]):
            intent_type = "factual"
        elif any(w in query.lower() for w in ["list", "show me", "find"]):
            intent_type = "search"
        elif any(w in query.lower() for w in ["compare", "difference"]):
            intent_type = "comparison"

        return {
            "intent_type": intent_type,
            "keywords": keywords,
            "entities": entities,
            "query_length": len(query.split()),
            "is_complex": len(keywords) >= 3,
        }


class HybridSearchManager:
    """Manages hybrid search combining vector and keyword search."""

    def __init__(
        self,
        use_bm25: bool = True,
        rrf_k: int = 60,
        vector_weight: float = 0.5,
        keyword_weight: float = 0.5,
        bm25_k1: float = 1.2,
        bm25_b: float = 0.75,
    ):
        self.use_bm25 = use_bm25
        self.rrf_k = rrf_k
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.bm25_k1 = bm25_k1
        self.bm25_b = bm25_b

        self.bm25_index = None
        self.documents_map: Dict[str, Dict] = {}

    def initialize_bm25(self, documents: List[Dict]):
        """Build BM25 index from documents.

        Args:
            documents: List of document dictionaries with 'id', 'content', 'metadata'
        """
        if not self.use_bm25:
            return

        try:
            from services.memory.hybrid_search import BM25Index, BM25Document

            self.bm25_index = BM25Index(k1=self.bm25_k1, b=self.bm25_b)

            for doc in documents:
                self.documents_map[doc["id"]] = doc
                self.bm25_index.add_document(
                    BM25Document(
                        id=doc["id"],
                        content=doc.get("content", ""),
                        content_lower=doc.get("content", "").lower(),
                        metadata=doc.get("metadata", {}),
                    )
                )

            logger.info(
                f"BM25 index initialized with {len(documents)} documents, "
                f"vocabulary size: {self.bm25_index.inverted_index.__len__()}"
            )

        except Exception as e:
            logger.warning(f"Failed to initialize BM25 index: {e}")
            self.use_bm25 = False

    def keyword_search(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[Dict] = None,
    ) -> List[Dict]:
        """Perform BM25 keyword search.

        Args:
            query: Search query
            top_k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of search results with scores
        """
        if not self.use_bm25 or not self.bm25_index:
            return []

        try:
            results = self.bm25_index.search(query, top_k=top_k)

            filtered_results = []
            for result in results:
                if filters:
                    matches = all(
                        result.metadata.get(k) == v for k, v in filters.items()
                    )
                    if not matches:
                        continue

                filtered_results.append(
                    {
                        "id": result.doc_id,
                        "content": result.content,
                        "relevance_score": result.score,
                        "metadata": result.metadata,
                        "search_method": "keyword",
                        "category": result.metadata.get("category", "unknown"),
                    }
                )

            return filtered_results

        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []

    def combine_results(
        self,
        vector_results: List[Dict],
        keyword_results: List[Dict],
    ) -> List[Dict]:
        """Combine vector and keyword results using RRF.

        Args:
            vector_results: Results from vector search
            keyword_results: Results from keyword search

        Returns:
            Combined results sorted by RRF score
        """
        try:
            from services.memory.hybrid_search import reciprocal_rank_fusion

            combined = reciprocal_rank_fusion(
                vector_results=vector_results,
                keyword_results=keyword_results,
                k=self.rrf_k,
                vector_weight=self.vector_weight,
                keyword_weight=self.keyword_weight,
            )

            return combined

        except ImportError:
            logger.warning(
                "Hybrid search module not available, falling back to vector results"
            )
            return vector_results

    def get_stats(self) -> Dict:
        """Get hybrid search statistics."""
        stats = {
            "bm25_enabled": self.use_bm25,
            "bm25_documents": len(self.documents_map),
        }

        if self.bm25_index:
            stats.update(self.bm25_index.get_stats())

        return stats


class RAGService:
    """Enhanced RAG service with hybrid search and re-ranking.

    Features:
    - Hybrid search (vector + BM25 keyword)
    - Cross-encoder re-ranking
    - Real-time message indexing
    - Query processing and expansion
    - Metadata filtering
    """

    def __init__(
        self,
        documents_path: str,
        vector_store_path: str,
        top_k: int = 3,
        use_vector_search: bool = True,
    ):
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

        self.chroma_client = None
        self.collection = None
        self.embedding_model = None

        self.embedding_cache = {}
        self.cache_max_size = 500

        self.hybrid_manager = HybridSearchManager(
            use_bm25=Config.RAG_BM25_ENABLED,
            rrf_k=Config.RAG_RRF_K,
            vector_weight=Config.RAG_VECTOR_WEIGHT,
            keyword_weight=Config.RAG_KEYWORD_WEIGHT,
            bm25_k1=Config.RAG_BM25_K1,
            bm25_b=Config.RAG_BM25_B,
        )

        self.reranker = None
        self.query_processor = QueryProcessor(
            enable_expansion=Config.RAG_QUERY_EXPANSION,
            sub_query_count=Config.RAG_SUB_QUERY_COUNT,
        )

        self.indexing_queue: asyncio.Queue = asyncio.Queue(
            maxsize=Config.RAG_INDEXING_QUEUE_SIZE
        )
        self._indexing_task = None

        self._stats = {
            "search_calls": 0,
            "hybrid_searches": 0,
            "rerank_calls": 0,
            "avg_search_time_ms": 0,
            "cache_hits": 0,
        }

        self.documents_path.mkdir(parents=True, exist_ok=True)
        self.vector_store_path.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        """Initialize the service asynchronously."""
        await self._load_documents()

        if self.use_vector_search:
            await self._initialize_vector_store()

        self.hybrid_manager.initialize_bm25(self.documents)

        if Config.RAG_RERANKER_ENABLED:
            await self._initialize_reranker()

        if Config.RAG_REALTIME_INDEXING:
            self._indexing_task = asyncio.create_task(self._indexing_worker())

    async def _initialize_reranker(self):
        """Initialize the cross-encoder re-ranker."""
        try:
            from services.memory.reranker import CrossEncoderReranker

            self.reranker = CrossEncoderReranker(
                model_name=Config.RAG_RERANKER_MODEL,
                max_batch_size=Config.RAG_RERANK_BATCH_SIZE,
                cache_size=Config.RAG_RERANKER_CACHE_SIZE,
            )
            await self.reranker.initialize()
            logger.info("Cross-encoder re-ranker initialized successfully")

        except Exception as e:
            logger.warning(f"Failed to initialize re-ranker: {e}")
            self.reranker = None

    async def _indexing_worker(self):
        """Background worker for processing indexing tasks."""
        logger.info("Starting background indexing worker")

        batch = []
        while True:
            try:
                task = await asyncio.wait_for(self.indexing_queue.get(), timeout=1.0)
                batch.append(task)

                if len(batch) >= Config.RAG_INDEXING_BATCH_SIZE:
                    await self._process_indexing_batch(batch)
                    batch.clear()

            except asyncio.TimeoutError:
                if batch:
                    await self._process_indexing_batch(batch)
                    batch.clear()

    async def _process_indexing_batch(self, tasks: List[IndexingTask]):
        """Process a batch of indexing tasks.

        Args:
            tasks: List of indexing tasks to process
        """
        try:
            for task in tasks:
                doc_id = f"discord_{task.message_id}"
                existing = next(
                    (d for d in self.documents if d.get("id") == doc_id), None
                )

                if existing:
                    existing["content"] = task.content
                    existing["content_lower"] = task.content.lower()
                    existing["metadata"].update(task.metadata)
                else:
                    self.documents.append(
                        {
                            "id": doc_id,
                            "content": task.content,
                            "content_lower": task.content.lower(),
                            "metadata": task.metadata,
                            "filename": f"discord_{task.message_id}",
                            "category": task.metadata.get("category", "discord"),
                            "chunk_index": 0,
                            "total_chunks": 1,
                        }
                    )

            self.hybrid_manager.initialize_bm25(self.documents)

            if self.use_vector_search and self.collection:
                await self._index_discord_messages(tasks)

            logger.debug(f"Indexed {len(tasks)} Discord messages")

        except Exception as e:
            logger.error(f"Failed to process indexing batch: {e}")

    async def index_discord_message(
        self,
        message_id: str,
        content: str,
        metadata: Dict,
    ) -> bool:
        """Add a Discord message to the indexing queue.

        Args:
            message_id: Discord message ID
            content: Message content
            metadata: Message metadata (author, channel, timestamp, etc.)

        Returns:
            True if queued successfully
        """
        try:
            task = IndexingTask(
                message_id=message_id,
                content=content,
                metadata={
                    **metadata,
                    "source": "discord",
                    "indexed_at": time.time(),
                },
            )

            await asyncio.wait_for(self.indexing_queue.put(task), timeout=1.0)
            return True

        except asyncio.TimeoutError:
            logger.warning("Indexing queue full, dropping message")
            return False
        except Exception as e:
            logger.error(f"Failed to queue message for indexing: {e}")
            return False

    async def _initialize_vector_store(self):
        """Initialize ChromaDB and embedding model."""
        try:
            import os

            os.environ["ANONYMIZED_TELEMETRY"] = "False"

            import chromadb
            from sentence_transformers import SentenceTransformer

            logger.info("Initializing vector store...")

            self.chroma_client = chromadb.PersistentClient(
                path=str(self.vector_store_path)
            )

            try:
                self.collection = self.chroma_client.get_collection(name="documents")
                logger.info(
                    f"Loaded existing collection with {self.collection.count()} embeddings"
                )
            except Exception:
                self.collection = self.chroma_client.create_collection(
                    name="documents", metadata={"hnsw:space": "cosine"}
                )
                logger.info("Created new collection")

            logger.info("Loading embedding model...")
            self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Embedding model loaded successfully")

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
                    category = file_path.parent.name.lower()
                    if category == self.documents_path.name.lower():
                        category = "general"

                    async with aiofiles.open(
                        file_path, "r", encoding="utf-8", errors="replace"
                    ) as f:
                        content = await f.read()

                    chunks = self._chunk_document(content, file_path.name)

                    for i, chunk in enumerate(chunks):
                        self.documents.append(
                            {
                                "id": f"{file_path.name}_{i}",
                                "path": str(file_path),
                                "content": chunk,
                                "content_lower": chunk.lower(),
                                "filename": file_path.name,
                                "category": category,
                                "chunk_index": i,
                                "total_chunks": len(chunks),
                            }
                        )

                    count += 1
                    if count % 100 == 0:
                        logger.info(f"Loaded {count}/{total_files} documents...")

                except Exception as e:
                    logger.error(f"Error reading {file_path}: {e}")

            logger.info(
                f"Successfully loaded {len(self.documents)} document chunks from {count} files"
            )

        except Exception as e:
            logger.error(f"Failed to load RAG documents: {e}")

    def _chunk_document(
        self,
        content: str,
        filename: str,
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> List[str]:
        """Split document into overlapping chunks."""
        if len(content) <= chunk_size:
            return [content]

        chunks = []
        start = 0

        while start < len(content):
            end = start + chunk_size

            if end < len(content):
                for punct in [". ", ".\n", "! ", "!\n", "? ", "?\n"]:
                    last_punct = content[start:end].rfind(punct)
                    if last_punct > chunk_size * 0.7:
                        end = start + last_punct + len(punct)
                        break

            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap

        return chunks

    async def _index_documents(self):
        """Index all documents into ChromaDB."""
        if not self.collection or not self.embedding_model:
            return

        logger.info(f"Indexing {len(self.documents)} document chunks...")

        batch_size = 100
        for i in range(0, len(self.documents), batch_size):
            batch = self.documents[i : i + batch_size]

            ids = [doc["id"] for doc in batch]
            documents = [doc["content"] for doc in batch]
            metadatas = [
                {
                    "filename": doc["filename"],
                    "category": doc["category"],
                    "chunk_index": doc["chunk_index"],
                    "path": doc["path"],
                }
                for doc in batch
            ]

            embeddings = self.embedding_model.encode(
                documents, show_progress_bar=False
            ).tolist()

            self.collection.add(
                ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas
            )

            if (i + batch_size) % 500 == 0:
                logger.info(
                    f"Indexed {min(i + batch_size, len(self.documents))}/{len(self.documents)} chunks..."
                )

        logger.info(
            f"Indexing complete! {self.collection.count()} embeddings in vector store"
        )

    async def _index_discord_messages(self, tasks: List[IndexingTask]):
        """Index Discord messages into vector store.

        Args:
            tasks: List of indexing tasks
        """
        if not self.collection or not self.embedding_model:
            return

        ids = []
        documents = []
        metadatas = []
        embeddings = []

        for task in tasks:
            doc_id = f"discord_{task.message_id}"
            embedding = self.embedding_model.encode(
                [task.content], show_progress_bar=False
            ).tolist()[0]

            ids.append(doc_id)
            documents.append(task.content)
            metadatas.append(
                {
                    "filename": doc_id,
                    "category": task.metadata.get("category", "discord"),
                    "chunk_index": 0,
                    "path": f"discord:{task.message_id}",
                    **task.metadata,
                }
            )
            embeddings.append(embedding)

        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        category: Optional[str] = None,
        categories: Optional[List[str]] = None,
        boost_category: Optional[str] = None,
        search_mode: str = "hybrid",
        use_reranker: bool = True,
        filters: Optional[Dict] = None,
    ) -> List[dict]:
        """Search for relevant documents.

        Supports hybrid search with optional re-ranking.

        Args:
            query: Search query
            top_k: Number of results to return
            category: Filter by single category (deprecated, use categories)
            categories: Filter by list of categories
            boost_category: Boost relevance score for documents in this category
            search_mode: "vector", "keyword", or "hybrid"
            use_reranker: Whether to apply cross-encoder re-ranking
            filters: Additional metadata filters

        Returns:
            List of relevant document chunks with metadata
        """
        start_time = time.time()
        self._stats["search_calls"] += 1

        k = top_k or self.top_k
        effective_k = k

        if use_reranker and self.reranker:
            effective_k = Config.RAG_RERANK_INITIAL_K

        sub_queries = self.query_processor.expand_query(query)
        all_results = []

        for sq in sub_queries[:3]:
            results = self._search_internal(
                query=sq,
                top_k=effective_k,
                category=category,
                categories=categories,
                boost_category=boost_category,
                search_mode=search_mode,
                filters=filters,
            )
            all_results.extend(results)

        merged = self._merge_sub_query_results(all_results, k)

        if use_reranker and self.reranker and merged:
            merged = self._apply_reranking(query, merged, k)
            self._stats["rerank_calls"] += 1

        elapsed_ms = (time.time() - start_time) * 1000
        self._stats["avg_search_time_ms"] = (
            self._stats["avg_search_time_ms"] * (self._stats["search_calls"] - 1)
            + elapsed_ms
        ) / self._stats["search_calls"]

        return merged[:k]

    def _search_internal(
        self,
        query: str,
        top_k: int,
        category: Optional[str],
        categories: Optional[List[str]],
        boost_category: Optional[str],
        search_mode: str,
        filters: Optional[Dict],
    ) -> List[dict]:
        """Internal search implementation."""
        if search_mode == "hybrid" and Config.RAG_HYBRID_SEARCH_ENABLED:
            self._stats["hybrid_searches"] += 1
            return self._hybrid_search(
                query, top_k, category, categories, boost_category, filters
            )
        elif search_mode == "vector" and self.use_vector_search:
            return self._vector_search(
                query, top_k, category, categories, boost_category
            )
        else:
            return self._keyword_search(
                query, top_k, category, boost_category, categories
            )

    def _hybrid_search(
        self,
        query: str,
        top_k: int,
        category: Optional[str],
        categories: Optional[List[str]],
        boost_category: Optional[str],
        filters: Optional[Dict],
    ) -> List[dict]:
        """Perform hybrid search combining vector and keyword."""
        vector_results = self._vector_search(
            query, top_k, category, categories, boost_category
        )

        keyword_results = self.hybrid_manager.keyword_search(
            query, top_k=top_k, filters=filters
        )

        combined = self.hybrid_manager.combine_results(
            vector_results=vector_results,
            keyword_results=keyword_results,
        )

        for i, result in enumerate(combined):
            result["search_methods"] = result.get("search_methods", [])
            if "vector" in result["search_methods"]:
                result["vector_score"] = (
                    vector_results[
                        next(
                            (
                                j
                                for j, v in enumerate(vector_results)
                                if v.get("filename") == result.get("id")
                            ),
                            -1,
                        )
                    ].get("relevance_score", 0)
                    if any(
                        v.get("filename") == result.get("id") for v in vector_results
                    )
                    else 0
                )
            if "keyword" in result["search_methods"]:
                result["keyword_score"] = (
                    keyword_results[
                        next(
                            (
                                j
                                for j, k in enumerate(keyword_results)
                                if k.get("filename") == result.get("id")
                            ),
                            -1,
                        )
                    ].get("relevance_score", 0)
                    if any(
                        k.get("filename") == result.get("id") for k in keyword_results
                    )
                    else 0
                )

        return combined

    def _vector_search(
        self,
        query: str,
        top_k: int,
        category: Optional[str],
        categories: Optional[List[str]],
        boost_category: Optional[str],
    ) -> List[dict]:
        """Perform vector similarity search."""
        try:
            if query in self.embedding_cache:
                query_embedding = self.embedding_cache[query]
                self._stats["cache_hits"] += 1
            else:
                query_embedding = self.embedding_model.encode([query])[0].tolist()
                self.embedding_cache[query] = query_embedding
                if len(self.embedding_cache) > self.cache_max_size:
                    oldest_key = next(iter(self.embedding_cache))
                    del self.embedding_cache[oldest_key]

            where_filter = None
            if category:
                where_filter = {"category": category}
            elif categories:
                if len(categories) == 1:
                    where_filter = {"category": categories[0]}
                else:
                    where_filter = {"category": {"$in": categories}}

            search_k = top_k * 3 if boost_category else top_k

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(search_k, self.collection.count()),
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )

            if not results or not results["documents"][0]:
                return []

            formatted_results = []
            for i, (doc, metadata, distance) in enumerate(
                zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                )
            ):
                similarity = 1 - distance
                score = similarity
                if boost_category and metadata["category"] == boost_category.lower():
                    score *= 5.0

                formatted_results.append(
                    {
                        "filename": metadata["filename"],
                        "path": metadata["path"],
                        "content": doc,
                        "category": metadata["category"],
                        "relevance_score": score,
                        "similarity": similarity,
                        "search_method": "vector",
                        "metadata": metadata,
                    }
                )

            formatted_results.sort(key=lambda x: x["relevance_score"], reverse=True)
            return formatted_results[:top_k]

        except Exception as e:
            logger.error(f"Vector search failed: {e}, falling back to keyword search")
            return self._keyword_search(
                query, top_k, category, boost_category, categories
            )

    def _keyword_search(
        self,
        query: str,
        top_k: int,
        category: Optional[str],
        boost_category: Optional[str],
        categories: Optional[List[str]] = None,
    ) -> List[dict]:
        """Perform keyword-based search."""
        if not self.documents:
            return []

        query_lower = query.lower()
        query_words = query_lower.split()

        if not query_words:
            return []

        keywords = [
            w for w in query_words if w not in QueryProcessor.STOP_WORDS and len(w) >= 2
        ]

        if not keywords:
            keywords = query_words

        results = []
        for doc in self.documents:
            if category and doc["category"] != category.lower():
                continue

            if categories:
                categories_lower = [c.lower() for c in categories]
                if doc["category"] not in categories_lower:
                    continue

            content_lower = doc["content_lower"]
            matches = 0
            matched_keywords = []

            for word in keywords:
                if word in content_lower:
                    matches += 1
                    matched_keywords.append(word)
                else:
                    if word.endswith("s") and word[:-1] in content_lower:
                        matches += 0.8
                        matched_keywords.append(word)
                    elif word + "s" in content_lower:
                        matches += 0.8
                        matched_keywords.append(word)

            if matches > 0:
                score = matches / len(keywords)

                if len(query_words) > 1 and query_lower in content_lower:
                    score *= 2.0

                if boost_category and doc["category"] == boost_category.lower():
                    score *= 5.0

                results.append(
                    {
                        "filename": doc["filename"],
                        "path": doc["path"],
                        "content": doc["content"],
                        "category": doc["category"],
                        "relevance_score": score,
                        "matched_keywords": matched_keywords,
                        "search_method": "keyword",
                        "metadata": {
                            "filename": doc["filename"],
                            "category": doc["category"],
                            "chunk_index": doc["chunk_index"],
                            "path": doc["path"],
                        },
                    }
                )

        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:top_k]

    def _merge_sub_query_results(
        self,
        all_results: List[dict],
        top_k: int,
    ) -> List[dict]:
        """Merge results from multiple sub-queries."""
        merged = {}
        for result in all_results:
            doc_id = result.get("filename") or result.get("id") or result.get("doc_id")
            if not doc_id:
                continue

            if doc_id in merged:
                existing_score = merged[doc_id].get("relevance_score", 0)
                new_score = result.get("relevance_score", 0)
                merged[doc_id]["relevance_score"] = max(existing_score, new_score)
            else:
                if "relevance_score" not in result:
                    result["relevance_score"] = result.get(
                        "rrf_score",
                        result.get("vector_score", result.get("keyword_score", 0)),
                    )
                merged[doc_id] = result

        sorted_results = sorted(
            merged.values(), key=lambda x: x.get("relevance_score", 0), reverse=True
        )

        return sorted_results[: top_k * 2]

    def _apply_reranking(
        self,
        query: str,
        results: List[dict],
        final_k: int,
    ) -> List[dict]:
        """Apply cross-encoder re-ranking to results."""
        if not self.reranker or not results:
            return results

        try:
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                reranked = loop.run_until_complete(
                    self.reranker.rerank_with_metadata(query, results, final_k)
                )
                return reranked
            finally:
                loop.close()

        except Exception as e:
            logger.error(f"Re-ranking failed: {e}")
            return results[:final_k]

    def get_context(
        self,
        query: str,
        max_length: int = 1000,
        category: Optional[str] = None,
        categories: Optional[List[str]] = None,
        boost_category: Optional[str] = None,
    ) -> str:
        """Get relevant context for a query."""
        import traceback

        caller = traceback.extract_stack()[-2]
        logger.debug(
            f"get_context called from {caller.filename}:{caller.lineno} in {caller.name}"
        )

        results = self.search(
            query,
            category=category,
            categories=categories,
            boost_category=boost_category,
        )

        if not results:
            return ""

        threshold = Config.RAG_RELEVANCE_THRESHOLD
        relevant_results = [
            r for r in results if r.get("relevance_score", 0) > threshold
        ]

        if not relevant_results:
            logger.debug(
                f"Matches found but below relevance threshold ({threshold}). "
                f"Best: {results[0].get('relevance_score', 0):.2f}"
            )
            return ""

        context_parts = []
        total_length = 0

        for result in relevant_results:
            content = result["content"]
            filename = result["filename"]

            doc_text = f"[From {filename}]\n{content}\n"

            if total_length + len(doc_text) <= max_length:
                context_parts.append(doc_text)
                total_length += len(doc_text)
            else:
                remaining = max_length - total_length
                if remaining > 100:
                    truncated = content[: remaining - 50] + "..."
                    context_parts.append(f"[From {filename}]\n{truncated}\n")
                break

        return "\n---\n".join(context_parts)

    async def add_document(
        self, filename: str, content: str, category: str = "general"
    ) -> bool:
        """Add a new document to the RAG system."""
        try:
            category_dir = self.documents_path / category
            category_dir.mkdir(exist_ok=True)

            file_path = category_dir / filename
            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                await f.write(content)

            await self._load_documents()
            self.hybrid_manager.initialize_bm25(self.documents)

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
        self.hybrid_manager.initialize_bm25(self.documents)

        if self.use_vector_search and self.collection:
            try:
                self.chroma_client.delete_collection("documents")
                self.collection = self.chroma_client.create_collection(
                    name="documents", metadata={"hnsw:space": "cosine"}
                )
                await self._index_documents()
            except Exception as e:
                logger.error(f"Failed to reload vector store: {e}")

    def list_documents(self) -> List[str]:
        """List all loaded documents."""
        filenames = set(doc["filename"] for doc in self.documents)
        return sorted(list(filenames))

    def is_enabled(self) -> bool:
        """Check if RAG has documents loaded."""
        return len(self.documents) > 0

    def get_stats(self) -> Dict:
        """Get RAG service statistics."""
        stats = {
            "total_documents": len(set(doc["filename"] for doc in self.documents)),
            "total_chunks": len(self.documents),
            "search_method": "hybrid"
            if Config.RAG_HYBRID_SEARCH_ENABLED
            else ("vector" if self.use_vector_search else "keyword"),
            "categories": {},
            "performance": self._stats.copy(),
            "hybrid": self.hybrid_manager.get_stats(),
        }

        if self.reranker:
            stats["reranker"] = self.reranker.get_stats()

        for doc in self.documents:
            cat = doc["category"]
            stats["categories"][cat] = stats["categories"].get(cat, 0) + 1

        if self.collection:
            stats["vector_store_embeddings"] = self.collection.count()
            stats["embedding_model"] = "all-MiniLM-L6-v2"

        return stats

    async def shutdown(self):
        """Clean up resources."""
        if self._indexing_task:
            self._indexing_task.cancel()
            try:
                await self._indexing_task
            except asyncio.CancelledError:
                pass

        if self.reranker:
            self.reranker.shutdown()
            self.reranker = None

        logger.info("RAG service shutdown complete")
