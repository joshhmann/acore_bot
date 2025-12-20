"""Lorebook service for managing and injecting world info.

T25-T26: Enhanced with semantic similarity matching using sentence-transformers.
Falls back to keyword matching for backward compatibility.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import OrderedDict
import time
import numpy as np

logger = logging.getLogger(__name__)

# Lazy load sentence-transformers to avoid startup overhead
_semantic_model = None
_semantic_enabled = True  # Can be disabled via config


@dataclass
class LoreEntry:
    """A single lorebook entry."""

    uid: str
    keys: List[str]  # Keywords that trigger this entry
    content: str  # The actual lore text
    order: int = 100  # Insertion order (lower = higher priority/earlier in prompt)
    enabled: bool = True
    case_sensitive: bool = False

    # Non-standard extensions
    constant: bool = False  # Always include this entry
    position: str = "before_char"  # where to insert: before_char, after_char

    # T25-T26: Semantic matching support
    embedding: Optional[np.ndarray] = None  # Cached embedding for semantic search
    semantic_enabled: bool = True  # Whether this entry supports semantic matching


@dataclass
class Lorebook:
    """A collection of lore entries."""

    name: str
    entries: Dict[str, LoreEntry] = field(default_factory=dict)

    def get_entries_list(self) -> List[LoreEntry]:
        """Get all entries as a list sorted by order."""
        return sorted(self.entries.values(), key=lambda x: x.order)


class LorebookService:
    """Service for managing lorebooks and scanning text for triggers.

    T25-T26: Enhanced with semantic similarity matching.
    - Uses sentence-transformers for conceptual matching
    - Falls back to keyword matching for compatibility
    - Caches embeddings for performance
    """

    def __init__(
        self,
        lorebooks_dir: Path = Path("./data/lorebooks"),
        semantic_threshold: float = 0.65,  # Cosine similarity threshold
        enable_semantic: bool = True,
        max_cache_size: int = 1000,
    ):
        """
        Initialize lorebook service.

        Args:
            lorebooks_dir: Directory where lorebooks are stored
            semantic_threshold: Minimum similarity for matches (0.0-1.0)
                - 0.5: Very loose matching
                - 0.65: Recommended (default)
                - 0.8: Very strict matching
            enable_semantic: Enable ML-based semantic matching (falls back to keywords)
            max_cache_size: Maximum number of embeddings to cache (LRU eviction)

        Raises:
            ValueError: If semantic_threshold is outside valid range (0.0-1.0)
        """
        # Validate inputs
        if not 0.0 <= semantic_threshold <= 1.0:
            raise ValueError(
                f"semantic_threshold must be between 0.0 and 1.0, got {semantic_threshold}"
            )

        self.lorebooks_dir = lorebooks_dir
        self.lorebooks_dir.mkdir(parents=True, exist_ok=True)
        self.loaded_lorebooks: Dict[str, Lorebook] = {}

        # T25-T26: Semantic matching configuration
        self.semantic_threshold = semantic_threshold
        self.enable_semantic = enable_semantic
        self._model = None  # Lazy loaded
        self._max_cache_size = max_cache_size
        # Use OrderedDict for LRU cache (O(1) access and eviction)
        self._embedding_cache: OrderedDict[str, np.ndarray] = OrderedDict()

        # Load all available lorebooks on startup
        self._load_all_lorebooks()

    def _load_all_lorebooks(self):
        """Load all JSON lorebooks from directory."""
        for file in self.lorebooks_dir.glob("*.json"):
            try:
                self.load_lorebook(file.stem)
            except Exception as e:
                logger.error(f"Failed to load lorebook {file}: {e}")

    def load_lorebook(self, name: str) -> Optional[Lorebook]:
        """
        Load a lorebook by name.

        Args:
            name: Lorebook name (filename without extension)

        Returns:
            Lorebook object or None if not found
        """
        file_path = self.lorebooks_dir / f"{name}.json"

        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            entries = {}
            # Handle standard V2/SillyTavern format
            raw_entries = data.get("entries", {})

            # If entries is a list (common export format)
            if isinstance(raw_entries, list):
                # Convert list to dict keyed by uid
                for i, raw_entry in enumerate(raw_entries):
                    uid = str(raw_entry.get("uid", i))
                    entries[uid] = self._parse_entry(raw_entry, uid)
            else:
                # If it's a dict (internal format)
                for uid, raw_entry in raw_entries.items():
                    entries[uid] = self._parse_entry(raw_entry, uid)

            lorebook = Lorebook(name=data.get("name", name), entries=entries)

            self.loaded_lorebooks[name] = lorebook
            logger.info(f"Loaded lorebook: {name} with {len(entries)} entries")
            return lorebook

        except Exception as e:
            logger.error(f"Error loading lorebook {name}: {e}")
            return None

    def _parse_entry(self, raw: Dict, uid: str) -> LoreEntry:
        """Parse a raw dictionary into a LoreEntry."""
        entry = LoreEntry(
            uid=str(uid),
            keys=raw.get("key", []),
            content=raw.get("content", ""),
            order=int(raw.get("order", 100)),
            enabled=raw.get("enabled", True),
            case_sensitive=raw.get("case_sensitive", False),
            constant=raw.get("constant", False),
            position=raw.get("position", "before_char"),
            semantic_enabled=raw.get("semantic_enabled", True),
        )

        # T25-T26: Pre-compute embedding for semantic matching
        if self.enable_semantic and entry.semantic_enabled and entry.keys:
            try:
                # Create a composite text from all keywords for embedding
                composite_text = " ".join(entry.keys).strip()

                # Skip if composite text is empty (edge case protection)
                if not composite_text:
                    logger.debug(
                        f"Entry {uid} has empty keys after joining, skipping embedding"
                    )
                    return entry

                entry.embedding = self.get_embedding(composite_text)
                logger.debug(f"Generated embedding for lore entry {uid}")
            except Exception as e:
                logger.debug(f"Failed to generate embedding for entry {uid}: {e}")

        return entry

    def scan_for_triggers(
        self, text: str, lorebook_names: List[str]
    ) -> List[LoreEntry]:
        """
        Scan text for keywords from specified lorebooks.

        T25-T26: Enhanced with semantic similarity matching.
        - First tries semantic matching (if enabled)
        - Falls back to keyword matching for compatibility
        - Combines results and deduplicates

        Args:
            text: Text to scan (usually user input + recent history)
            lorebook_names: List of lorebooks to check

        Returns:
            List of matching LoreEntry objects, sorted by order
        """
        triggered_entries = []
        seen_uids = set()

        text_lower = text.lower()

        for lb_name in lorebook_names:
            lorebook = self.loaded_lorebooks.get(lb_name)
            if not lorebook:
                continue

            for entry in lorebook.entries.values():
                if not entry.enabled:
                    continue

                if entry.uid in seen_uids:
                    continue

                # Check constant entries
                if entry.constant:
                    triggered_entries.append(entry)
                    seen_uids.add(entry.uid)
                    continue

                # T25-T26: Try semantic matching first (if enabled)
                semantic_match = False
                if (
                    self.enable_semantic
                    and entry.semantic_enabled
                    and entry.embedding is not None
                ):
                    try:
                        similarity = self.compute_similarity(text, entry.embedding)
                        if similarity >= self.semantic_threshold:
                            triggered_entries.append(entry)
                            seen_uids.add(entry.uid)
                            semantic_match = True
                            logger.debug(
                                f"Semantic match for entry {entry.uid}: "
                                f"similarity={similarity:.3f} (threshold={self.semantic_threshold})"
                            )
                            continue  # Skip keyword check
                    except Exception as e:
                        logger.debug(
                            f"Semantic matching failed for entry {entry.uid}: {e}"
                        )

                # Fallback to keyword matching (original behavior)
                if not semantic_match:
                    for key in entry.keys:
                        if not key:
                            continue

                        is_match = False
                        if entry.case_sensitive:
                            if key in text:
                                is_match = True
                        else:
                            if key.lower() in text_lower:
                                is_match = True

                        if is_match:
                            triggered_entries.append(entry)
                            seen_uids.add(entry.uid)
                            logger.debug(
                                f"Keyword match for entry {entry.uid}: key='{key}'"
                            )
                            break  # Stop checking keys for this entry once triggered

        # Sort by insertion order
        triggered_entries.sort(key=lambda x: x.order)
        return triggered_entries

    def create_lorebook_from_text(self, name: str, text: str):
        """Simple helper to create a basic lorebook from text file (one entry per paragraph)."""
        entries = {}
        paragraphs = text.split("\n\n")

        for i, p in enumerate(paragraphs):
            p = p.strip()
            if not p:
                continue

            # Naive keyword extraction: first 2 words
            words = p.split()[:2]
            key = " ".join(words)

            entries[str(i)] = LoreEntry(
                uid=str(i), keys=[key], content=p, order=100 + i
            )

        lorebook = Lorebook(name=name, entries=entries)
        self.loaded_lorebooks[name] = lorebook

        # Save to disk
        self._save_lorebook(lorebook)

    def _save_lorebook(self, lorebook: Lorebook):
        """Save lorebook to disk."""
        path = self.lorebooks_dir / f"{lorebook.name}.json"

        data = {
            "name": lorebook.name,
            "entries": [
                {
                    "uid": e.uid,
                    "key": e.keys,
                    "content": e.content,
                    "order": e.order,
                    "enabled": e.enabled,
                    "constant": e.constant,
                }
                for e in lorebook.entries.values()
            ],
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_available_lorebooks(self) -> List[str]:
        """List names of available lorebooks."""
        return list(self.loaded_lorebooks.keys())

    # T25-T26: Semantic Matching Methods

    def _load_semantic_model(self):
        """Lazy load the sentence-transformers model.

        Uses all-MiniLM-L6-v2 which is fast and lightweight (~80MB).
        Performance: ~50ms for encoding on CPU.
        """
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info("Loading semantic matching model (all-MiniLM-L6-v2)...")
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("Semantic matching model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load semantic model: {e}")
                self.enable_semantic = False
                raise
        return self._model

    def get_embedding(self, text: str) -> np.ndarray:
        """Get embedding vector for text, with LRU caching.

        Args:
            text: Text to embed

        Returns:
            Embedding vector (384 dimensions for all-MiniLM-L6-v2)
        """
        start_time = time.time()

        # Check cache first (LRU: move to end = most recently used)
        if text in self._embedding_cache:
            self._embedding_cache.move_to_end(text)
            logger.debug(
                f"Embedding cache HIT (size: {len(self._embedding_cache)}/{self._max_cache_size})"
            )
            return self._embedding_cache[text]

        # Load model if needed
        model = self._load_semantic_model()

        # Generate embedding
        embedding = model.encode(text, convert_to_numpy=True)

        # Performance logging
        elapsed_ms = (time.time() - start_time) * 1000
        logger.debug(f"Generated embedding in {elapsed_ms:.1f}ms")

        # Add to cache with LRU eviction
        if len(self._embedding_cache) >= self._max_cache_size:
            # Remove least recently used (first item)
            evicted_key = next(iter(self._embedding_cache))
            self._embedding_cache.pop(evicted_key)
            logger.debug(f"Evicted LRU embedding from cache: '{evicted_key[:50]}...'")

        self._embedding_cache[text] = embedding
        logger.debug(
            f"Embedding cache MISS - added to cache "
            f"(size: {len(self._embedding_cache)}/{self._max_cache_size})"
        )

        return embedding

    # Alias for backward compatibility if needed, but we're updating internal calls
    _get_embedding = get_embedding

    def compute_similarity(self, text: str, target_embedding: np.ndarray) -> float:
        """Compute cosine similarity between text and a target embedding.

        Args:
            text: Input text to compare
            target_embedding: Pre-computed embedding to compare against

        Returns:
            Cosine similarity score (0.0 to 1.0, higher is more similar)
        """
        text_embedding = self.get_embedding(text)

        # Cosine similarity: dot product of normalized vectors
        # Both embeddings are already normalized by sentence-transformers
        similarity = np.dot(text_embedding, target_embedding)

        return float(similarity)

    # Alias for backward compatibility
    _compute_similarity = compute_similarity

    def precompute_all_embeddings(self, batch_size: int = 32):
        """Pre-compute embeddings for all lore entries using batch processing.

        Call this during bot startup to avoid first-query latency.
        Uses batch encoding for 5-10x faster performance compared to sequential.

        Args:
            batch_size: Number of texts to encode in parallel (default: 32)
        """
        if not self.enable_semantic:
            logger.debug(
                "Semantic matching disabled, skipping embedding precomputation"
            )
            return

        start_time = time.time()
        logger.info("Pre-computing lore entry embeddings (batch mode)...")

        # Collect all texts that need embeddings
        texts_to_embed = []
        entries_to_update = []

        for lorebook in self.loaded_lorebooks.values():
            for entry in lorebook.entries.values():
                if entry.semantic_enabled and entry.keys and entry.embedding is None:
                    composite_text = " ".join(entry.keys)
                    # Skip empty texts
                    if not composite_text.strip():
                        logger.debug(f"Entry {entry.uid} has empty keys, skipping")
                        continue
                    texts_to_embed.append(composite_text)
                    entries_to_update.append(entry)

        if not texts_to_embed:
            logger.info("No embeddings to precompute")
            return

        try:
            # Batch encode (much faster than sequential)
            model = self._load_semantic_model()
            logger.info(f"Batch encoding {len(texts_to_embed)} lore entries...")
            embeddings = model.encode(
                texts_to_embed,
                convert_to_numpy=True,
                batch_size=batch_size,
                show_progress_bar=False,
            )

            # Assign embeddings to entries and cache them
            for entry, embedding, text in zip(
                entries_to_update, embeddings, texts_to_embed
            ):
                entry.embedding = embedding

                # Also add to cache (with LRU eviction if needed)
                if len(self._embedding_cache) >= self._max_cache_size:
                    evicted_key = next(iter(self._embedding_cache))
                    self._embedding_cache.pop(evicted_key)

                self._embedding_cache[text] = embedding

            elapsed = time.time() - start_time
            logger.info(
                f"Pre-computed {len(embeddings)} lore entry embeddings in {elapsed:.2f}s "
                f"({len(embeddings) / elapsed:.1f} embeddings/sec)"
            )

        except Exception as e:
            logger.error(f"Failed to batch precompute embeddings: {e}")
            logger.info("Falling back to sequential embedding generation...")

            # Fallback to sequential if batch fails
            count = 0
            for entry in entries_to_update:
                try:
                    composite_text = " ".join(entry.keys)
                    entry.embedding = self.get_embedding(composite_text)
                    count += 1
                except Exception as e:
                    logger.debug(f"Failed to embed entry {entry.uid}: {e}")

            elapsed = time.time() - start_time
            logger.info(
                f"Pre-computed {count} embeddings (sequential fallback) in {elapsed:.2f}s"
            )
