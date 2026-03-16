"""Model-Agnostic Provider Selection.

Selects appropriate providers based on:
- Cognitive mode requirements
- Provider availability and health
- Cost considerations
- Latency tracking
- Fallback chains
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from core.social_intelligence.modes import CognitiveMode, ModeConfig


@dataclass
class ProviderMetrics:
    """Metrics for a provider."""

    provider: str
    avg_latency_ms: float = 0.0
    success_rate: float = 1.0
    cost_per_1k_tokens: float = 0.0
    last_used: float = field(default_factory=time.time)
    total_requests: int = 0
    failed_requests: int = 0

    def record_request(self, latency_ms: float, success: bool, tokens: int = 0) -> None:
        """Record a request metrics."""
        self.total_requests += 1
        self.last_used = time.time()

        if not success:
            self.failed_requests += 1

        # Update rolling averages
        alpha = 0.3  # Smoothing factor
        self.avg_latency_ms = self.avg_latency_ms * (1 - alpha) + latency_ms * alpha
        self.success_rate = (
            self.success_rate * (1 - alpha) + (1.0 if success else 0.0) * alpha
        )


@dataclass
class ProviderSelection:
    """Result of provider selection."""

    primary: str
    fallbacks: list[str]
    reason: str


class ProviderSelector:
    """Selects providers based on mode and metrics.

    Features:
    - Mode-to-provider mapping
    - Fallback chains
    - Cost-aware selection
    - Latency tracking
    - Health monitoring
    """

    # Default cost estimates (per 1K tokens)
    DEFAULT_COSTS = {
        "openai/gpt-4": 0.03,
        "openai/gpt-4-turbo": 0.01,
        "openai/gpt-3.5-turbo": 0.0015,
        "anthropic/claude-3-opus": 0.015,
        "anthropic/claude-3-sonnet": 0.003,
        "anthropic/claude-3-haiku": 0.00025,
        "local/ollama": 0.0,
    }

    def __init__(
        self,
        enable_cost_optimization: bool = True,
        max_latency_ms: float = 5000.0,
        min_success_rate: float = 0.8,
    ):
        self.enable_cost_optimization = enable_cost_optimization
        self.max_latency_ms = max_latency_ms
        self.min_success_rate = min_success_rate

        # Provider metrics
        self._metrics: dict[str, ProviderMetrics] = {}

        # Mode to provider mappings (can be customized)
        self._mode_mappings: dict[CognitiveMode, list[str]] = {
            CognitiveMode.CREATIVE: [
                "openai/gpt-4",
                "anthropic/claude-3-opus",
                "openai/gpt-4-turbo",
            ],
            CognitiveMode.LOGIC: [
                "anthropic/claude-3-opus",
                "openai/gpt-4",
                "anthropic/claude-3-sonnet",
            ],
            CognitiveMode.FACILITATOR: [
                "openai/gpt-4",
                "anthropic/claude-3-sonnet",
                "openai/gpt-4-turbo",
            ],
        }

        # Fallback chain (global)
        self._fallback_chain = [
            "openai/gpt-4-turbo",
            "anthropic/claude-3-sonnet",
            "openai/gpt-3.5-turbo",
            "anthropic/claude-3-haiku",
            "local/ollama",
        ]

    def select_provider(
        self,
        mode: CognitiveMode,
        config: ModeConfig | None = None,
        prefer_cheap: bool = False,
        require_fast: bool = False,
    ) -> ProviderSelection:
        """Select appropriate provider for a cognitive mode.

        Args:
            mode: The cognitive mode
            config: Mode configuration (optional)
            prefer_cheap: Prefer cheaper providers
            require_fast: Require low latency

        Returns:
            ProviderSelection with primary and fallback providers
        """
        # Get preferred providers for mode
        preferred = config.provider_preference if config else self._mode_mappings[mode]

        # Score each provider
        scored_providers = []
        for provider in preferred:
            score = self._score_provider(provider, prefer_cheap, require_fast)
            scored_providers.append((provider, score))

        # Sort by score (descending)
        scored_providers.sort(key=lambda x: x[1], reverse=True)

        if not scored_providers:
            # Use global fallback
            return ProviderSelection(
                primary=self._fallback_chain[0],
                fallbacks=self._fallback_chain[1:],
                reason="No preferred providers available, using fallback chain",
            )

        # Select primary and fallbacks
        primary = scored_providers[0][0]
        fallbacks = [p for p, _ in scored_providers[1:]]

        # Add global fallbacks if needed
        for fallback in self._fallback_chain:
            if fallback not in [primary] + fallbacks:
                fallbacks.append(fallback)

        reason = f"Selected based on mode '{mode.name}'"
        if prefer_cheap:
            reason += " with cost optimization"
        if require_fast:
            reason += " with latency requirement"

        return ProviderSelection(
            primary=primary,
            fallbacks=fallbacks,
            reason=reason,
        )

    def _score_provider(
        self,
        provider: str,
        prefer_cheap: bool,
        require_fast: bool,
    ) -> float:
        """Calculate a score for a provider.

        Higher is better. Combines:
        - Success rate
        - Latency
        - Cost
        """
        metrics = self._metrics.get(provider)

        # Default scores
        success_score = 1.0
        latency_score = 1.0
        cost_score = 0.5

        if metrics:
            # Success rate (0-1)
            success_score = metrics.success_rate

            # Latency score (inverse, 0-1)
            if metrics.avg_latency_ms > 0:
                latency_score = max(
                    0, 1 - (metrics.avg_latency_ms / self.max_latency_ms)
                )

            # Check requirements
            if require_fast and metrics.avg_latency_ms > self.max_latency_ms:
                return 0.0  # Too slow

            if metrics.success_rate < self.min_success_rate:
                return 0.0  # Unreliable

        # Cost score (inverse, 0-1)
        cost = self.DEFAULT_COSTS.get(provider, 0.01)
        cost_score = max(0, 1 - (cost / 0.03))  # Normalize against max cost

        # Combine scores with weights
        if prefer_cheap:
            # Prioritize cost
            final_score = success_score * 0.3 + latency_score * 0.2 + cost_score * 0.5
        else:
            # Prioritize quality
            final_score = success_score * 0.4 + latency_score * 0.35 + cost_score * 0.25

        return final_score

    def record_metrics(
        self,
        provider: str,
        latency_ms: float,
        success: bool,
        tokens: int = 0,
    ) -> None:
        """Record metrics for a provider request.

        Args:
            provider: Provider identifier
            latency_ms: Request latency in milliseconds
            success: Whether request succeeded
            tokens: Number of tokens used
        """
        if provider not in self._metrics:
            self._metrics[provider] = ProviderMetrics(
                provider=provider,
                cost_per_1k_tokens=self.DEFAULT_COSTS.get(provider, 0.01),
            )

        self._metrics[provider].record_request(latency_ms, success, tokens)

    def set_mode_mapping(
        self,
        mode: CognitiveMode,
        providers: list[str],
    ) -> None:
        """Set preferred providers for a mode.

        Args:
            mode: Cognitive mode
            providers: Ordered list of preferred providers
        """
        self._mode_mappings[mode] = providers

    def get_provider_health(self) -> dict[str, dict[str, Any]]:
        """Get health status of all providers."""
        health = {}
        for provider, metrics in self._metrics.items():
            health[provider] = {
                "status": "healthy" if metrics.success_rate > 0.8 else "degraded",
                "success_rate": f"{metrics.success_rate:.1%}",
                "avg_latency_ms": f"{metrics.avg_latency_ms:.0f}ms",
                "total_requests": metrics.total_requests,
            }
        return health

    def get_cost_estimate(
        self,
        mode: CognitiveMode,
        estimated_tokens: int = 1000,
    ) -> dict[str, float]:
        """Estimate cost for different providers.

        Args:
            mode: Cognitive mode
            estimated_tokens: Expected token count

        Returns:
            Dict mapping provider to estimated cost
        """
        providers = self._mode_mappings[mode]
        estimates = {}

        for provider in providers:
            cost_per_1k = self.DEFAULT_COSTS.get(provider, 0.01)
            estimates[provider] = cost_per_1k * (estimated_tokens / 1000)

        return estimates
