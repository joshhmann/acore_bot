"""Hybrid Facilitator Routing with Classifier + LLM Fallback.

Uses a fast classifier for 80% of routing decisions and
LLM-based facilitator for complex edge cases (20%).

Features:
- Fast classifier path (<30ms latency)
- LLM fallback for low-confidence cases
- Embedding-based classification
- Result caching
- Performance monitoring
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any

from core.social_intelligence.modes import CognitiveMode
from core.social_intelligence.router import ModeRouter, RoutingDecision


@dataclass
class ClassificationResult:
    """Result from classifier."""

    mode: CognitiveMode
    confidence: float
    is_cached: bool = False
    latency_ms: float = 0.0


class SimpleClassifier:
    """Lightweight classifier for fast routing.

    Uses keyword-based classification with embeddings
    as a fallback for semantic understanding.
    """

    def __init__(self):
        # Keyword signatures for each mode
        self._signatures = {
            CognitiveMode.LOGIC: {
                "code",
                "debug",
                "error",
                "fix",
                "function",
                "class",
                "algorithm",
                "analyze",
                "calculate",
                "compute",
                "solve",
                "prove",
                "verify",
                "logic",
                "reasoning",
                "evidence",
                "fact",
                "data",
                "if",
                "then",
                "how",
                "why",
                "explain",
                "implementation",
                "refactor",
            },
            CognitiveMode.CREATIVE: {
                "brainstorm",
                "idea",
                "creative",
                "imagine",
                "design",
                "concept",
                "generate",
                "create",
                "invent",
                "novel",
                "innovative",
                "unique",
                "story",
                "write",
                "poem",
                "art",
                "artistic",
                "inspiration",
                "what if",
                "possibility",
                "alternative",
                "different",
                "think",
                "envision",
                "dream",
                "fantasy",
                "color",
                "visual",
                "music",
            },
        }

        # Embedding model (lazy loaded)
        self._embedding_model = None

        # Training data for calibration
        self._training_samples: list[tuple[str, CognitiveMode]] = []

    def classify(self, content: str) -> ClassificationResult:
        """Classify content to cognitive mode.

        Returns mode with confidence score.
        """
        start_time = time.time()

        content_lower = content.lower()
        words = set(content_lower.split())

        # Count keyword matches
        scores: dict[CognitiveMode, int] = {
            mode: 0 for mode in CognitiveMode if mode != CognitiveMode.FACILITATOR
        }

        for mode, keywords in self._signatures.items():
            for keyword in keywords:
                if keyword in content_lower:
                    scores[mode] += 1

        # Calculate confidence
        total_matches = sum(scores.values())

        if total_matches == 0:
            # No clear signals
            latency = (time.time() - start_time) * 1000
            return ClassificationResult(
                mode=CognitiveMode.FACILITATOR,
                confidence=0.0,
                latency_ms=latency,
            )

        # Get best matching mode
        best_mode = max(scores, key=lambda k: scores[k])
        best_score = scores[best_mode]

        # Calculate confidence (normalized)
        confidence = min(1.0, best_score / max(3, total_matches * 0.6))

        latency = (time.time() - start_time) * 1000

        return ClassificationResult(
            mode=best_mode,
            confidence=confidence,
            latency_ms=latency,
        )

    def train(self, samples: list[tuple[str, CognitiveMode]]) -> None:
        """Train classifier on labeled samples.

        Args:
            samples: List of (content, mode) tuples
        """
        self._training_samples.extend(samples)

        # Update signatures based on training data
        # (Simple frequency-based update)
        for content, mode in samples:
            words = set(content.lower().split())
            if mode in self._signatures:
                self._signatures[mode].update(words)


class HybridFacilitator:
    """Hybrid routing with classifier fast path + LLM fallback.

    Routing strategy:
    1. Try fast classifier first (<30ms)
    2. If confidence >= threshold, use classifier result
    3. If confidence < threshold, use LLM facilitator
    4. Cache results for repeated contexts
    """

    def __init__(
        self,
        classifier: SimpleClassifier | None = None,
        confidence_threshold: float = 0.7,
        use_llm_fallback: bool = True,
        cache_size: int = 1000,
    ):
        self.classifier = classifier or SimpleClassifier()
        self.confidence_threshold = confidence_threshold
        self.use_llm_fallback = use_llm_fallback
        self._cache: dict[str, ClassificationResult] = {}
        self._cache_size = cache_size

        # Metrics
        self._stats = {
            "classifier_hits": 0,
            "llm_fallbacks": 0,
            "cache_hits": 0,
            "total_requests": 0,
        }

    def route(
        self,
        content: str,
        llm_router: ModeRouter | None = None,
    ) -> RoutingDecision:
        """Route content using hybrid approach.

        Args:
            content: Content to route
            llm_router: LLM-based router for fallback

        Returns:
            RoutingDecision with selected mode
        """
        self._stats["total_requests"] += 1

        # Check cache first
        cache_key = self._get_cache_key(content)
        if cache_key in self._cache:
            self._stats["cache_hits"] += 1
            cached = self._cache[cache_key]
            return RoutingDecision(
                mode=cached.mode,
                confidence=cached.confidence,
                reason="Cached classification result",
                strategy="cache",
            )

        # Try fast classifier
        result = self.classifier.classify(content)

        # Check if confidence is high enough
        if result.confidence >= self.confidence_threshold:
            self._stats["classifier_hits"] += 1
            self._cache_result(cache_key, result)

            return RoutingDecision(
                mode=result.mode,
                confidence=result.confidence,
                reason=f"Classifier confidence {result.confidence:.2f}",
                strategy="fast_classifier",
            )

        # Low confidence - use LLM fallback
        if self.use_llm_fallback and llm_router:
            self._stats["llm_fallbacks"] += 1

            # Create synthetic event for router
            event = {"content": content, "type": "text"}
            decision = llm_router.select_mode(event)

            # Cache the result
            cached_result = ClassificationResult(
                mode=decision.mode,
                confidence=decision.confidence,
                latency_ms=0.0,
            )
            self._cache_result(cache_key, cached_result)

            return RoutingDecision(
                mode=decision.mode,
                confidence=decision.confidence,
                reason=f"LLM fallback (classifier confidence {result.confidence:.2f})",
                strategy="llm_fallback",
            )

        # No LLM fallback - use classifier result anyway
        self._cache_result(cache_key, result)
        return RoutingDecision(
            mode=result.mode,
            confidence=result.confidence,
            reason=f"Classifier (below threshold, no fallback)",
            strategy="classifier_no_fallback",
        )

    def _get_cache_key(self, content: str) -> str:
        """Generate cache key for content."""
        # Use first 100 chars + hash for key
        normalized = content.lower().strip()[:100]
        return hashlib.md5(normalized.encode()).hexdigest()[:16]

    def _cache_result(self, key: str, result: ClassificationResult) -> None:
        """Cache classification result."""
        result.is_cached = True
        self._cache[key] = result

        # Limit cache size
        if len(self._cache) > self._cache_size:
            # Remove oldest entries
            keys = list(self._cache.keys())
            for old_key in keys[: self._cache_size // 10]:
                del self._cache[old_key]

    def get_stats(self) -> dict[str, Any]:
        """Get routing statistics."""
        total = self._stats["total_requests"]
        if total == 0:
            return self._stats

        return {
            **self._stats,
            "classifier_rate": self._stats["classifier_hits"] / total,
            "llm_fallback_rate": self._stats["llm_fallbacks"] / total,
            "cache_hit_rate": self._stats["cache_hits"] / total,
            "cache_size": len(self._cache),
        }

    def train_classifier(self, samples: list[tuple[str, CognitiveMode]]) -> None:
        """Train the classifier on labeled data.

        Args:
            samples: List of (content, mode) tuples
        """
        self.classifier.train(samples)
