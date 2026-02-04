"""RAG (Retrieval-Augmented Generation) configuration."""

from pathlib import Path
from .base import BaseConfig


class RAGConfig(BaseConfig):
    """RAG system configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("RAG_ENABLED", False)
    MODE: str = BaseConfig._get_env("RAG_MODE", "simple")
    VECTOR_STORE: Path = BaseConfig._get_env_path(
        "RAG_VECTOR_STORE", "./data/vector_store"
    )
    DOCUMENTS_PATH: Path = BaseConfig._get_env_path(
        "RAG_DOCUMENTS_PATH", "./data/documents"
    )
    TOP_K: int = BaseConfig._get_env_int("RAG_TOP_K", 3)
    IN_CHAT: bool = BaseConfig._get_env_bool("RAG_IN_CHAT", True)
    RELEVANCE_THRESHOLD: float = BaseConfig._get_env_float(
        "RAG_RELEVANCE_THRESHOLD", 0.5
    )


class HybridSearchConfig(BaseConfig):
    """Hybrid search configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("RAG_HYBRID_SEARCH_ENABLED", True)
    KEYWORD_WEIGHT: float = BaseConfig._get_env_float("RAG_KEYWORD_WEIGHT", 0.3)
    SEMANTIC_WEIGHT: float = BaseConfig._get_env_float("RAG_SEMANTIC_WEIGHT", 0.7)
    KEYWORD_MATCH_THRESHOLD: float = BaseConfig._get_env_float(
        "RAG_KEYWORD_MATCH_THRESHOLD", 0.5
    )

    # BM25 parameters
    BM25_ENABLED: bool = BaseConfig._get_env_bool("RAG_BM25_ENABLED", True)
    BM25_K1: float = BaseConfig._get_env_float("RAG_BM25_K1", 1.2)
    BM25_B: float = BaseConfig._get_env_float("RAG_BM25_B", 0.75)

    # RRF (Reciprocal Rank Fusion)
    RRF_K: int = BaseConfig._get_env_int("RAG_RRF_K", 60)

    # Vector/keyword weights for RRF
    VECTOR_WEIGHT: float = BaseConfig._get_env_float("RAG_VECTOR_WEIGHT", 0.5)
    KEYWORD_WEIGHT_RRF: float = BaseConfig._get_env_float("RAG_KEYWORD_WEIGHT", 0.5)


class RerankerConfig(BaseConfig):
    """Cross-encoder reranker configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("RAG_RERANKER_ENABLED", True)
    MODEL: str = BaseConfig._get_env(
        "RAG_RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
    )
    TOP_K_MULTIPLIER: int = BaseConfig._get_env_int("RAG_RERANKER_TOP_K_MULTIPLIER", 3)
    BATCH_SIZE: int = BaseConfig._get_env_int("RAG_RERANKER_BATCH_SIZE", 32)
    INITIAL_K: int = BaseConfig._get_env_int("RAG_RERANK_INITIAL_K", 20)
    CACHE_SIZE: int = BaseConfig._get_env_int("RAG_RERANKER_CACHE_SIZE", 1000)


class RealtimeIndexingConfig(BaseConfig):
    """Real-time indexing configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("RAG_REALTIME_INDEXING_ENABLED", True)
    DEBOUNCE_SECONDS: float = BaseConfig._get_env_float(
        "RAG_INDEXING_DEBOUNCE_SECONDS", 5.0
    )
    BATCH_SIZE: int = BaseConfig._get_env_int("RAG_INDEXING_BATCH_SIZE", 100)
    QUEUE_SIZE: int = BaseConfig._get_env_int("RAG_INDEXING_QUEUE_SIZE", 1000)
    SUPPORTED_EXTENSIONS: tuple = (
        ".txt",
        ".md",
        ".rst",
        ".py",
        ".js",
        ".html",
        ".css",
        ".json",
        ".yaml",
        ".yml",
    )


class QueryProcessingConfig(BaseConfig):
    """Query processing configuration."""

    EXPANSION_ENABLED: bool = BaseConfig._get_env_bool(
        "RAG_QUERY_EXPANSION_ENABLED", True
    )
    EXPANSION: bool = BaseConfig._get_env_bool("RAG_QUERY_EXPANSION", True)
    EXPANSION_TECHNIQUES: list = BaseConfig._get_env_list(
        "RAG_QUERY_EXPANSION_TECHNIQUES", ["synonyms", "hyponyms"]
    )
    MAX_EXPANSIONS: int = BaseConfig._get_env_int("RAG_MAX_QUERY_EXPANSIONS", 3)
    SUB_QUERY_COUNT: int = BaseConfig._get_env_int("RAG_SUB_QUERY_COUNT", 3)


class UserProfilesConfig(BaseConfig):
    """User profiles configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("USER_PROFILES_ENABLED", True)
    PATH: Path = BaseConfig._get_env_path("USER_PROFILES_PATH", "./data/user_profiles")
    AUTO_LEARN: bool = BaseConfig._get_env_bool("USER_PROFILES_AUTO_LEARN", True)
    AFFECTION_ENABLED: bool = BaseConfig._get_env_bool("USER_AFFECTION_ENABLED", True)
    CONTEXT_IN_CHAT: bool = BaseConfig._get_env_bool("USER_CONTEXT_IN_CHAT", True)
    SAVE_INTERVAL_SECONDS: int = BaseConfig._get_env_int(
        "PROFILE_SAVE_INTERVAL_SECONDS", 60
    )
