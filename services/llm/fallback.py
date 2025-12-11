"""LLM Model Fallback System - like LiteLLM routing."""
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for a single model in the fallback chain."""
    name: str
    provider: str  # "openrouter", "ollama"
    max_temp: Optional[float] = None  # Max temperature for this model
    cost_tier: str = "free"  # "free", "paid", "premium"
    priority: int = 0  # Lower = higher priority


class LLMFallbackManager:
    """Manages model fallback chain for resilient LLM requests."""

    def __init__(self, models: List[ModelConfig]):
        """Initialize fallback manager.

        Args:
            models: List of models in priority order (first = primary)
        """
        self.models = sorted(models, key=lambda m: m.priority)
        self.stats = {
            "total_requests": 0,
            "fallbacks_triggered": 0,
            "model_usage": {model.name: 0 for model in self.models},
            "model_failures": {model.name: 0 for model in self.models},
        }

        logger.info(f"LLM Fallback chain initialized with {len(self.models)} models:")
        for i, model in enumerate(self.models):
            logger.info(f"  [{i+1}] {model.name} ({model.provider}, {model.cost_tier})")

    async def chat_with_fallback(
        self,
        llm_service,  # OllamaService or OpenRouterService
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> tuple[str, str]:
        """Send chat request with automatic fallback.

        Args:
            llm_service: LLM service instance
            messages: Chat messages
            system_prompt: Optional system prompt
            temperature: Temperature override
            max_tokens: Max tokens override

        Returns:
            Tuple of (response, model_used)

        Raises:
            Exception: If all models in chain fail
        """
        self.stats["total_requests"] += 1

        errors = []
        original_model = llm_service.model

        for i, model_config in enumerate(self.models):
            try:
                # Update service to use this model
                llm_service.model = model_config.name

                # Adjust temperature if needed for this model
                actual_temp = temperature
                if model_config.max_temp is not None and actual_temp:
                    if actual_temp > model_config.max_temp:
                        logger.debug(f"Clamping temperature from {actual_temp} to {model_config.max_temp} for {model_config.name}")
                        actual_temp = model_config.max_temp

                # Attempt request
                logger.debug(f"Attempting LLM request with model: {model_config.name} (attempt {i+1}/{len(self.models)})")
                start_time = time.time()

                response = await llm_service.chat(
                    messages=messages,
                    system_prompt=system_prompt,
                    temperature=actual_temp,
                    max_tokens=max_tokens
                )

                elapsed = time.time() - start_time

                # Success!
                self.stats["model_usage"][model_config.name] += 1

                if i > 0:
                    # We had to fallback
                    self.stats["fallbacks_triggered"] += 1
                    logger.warning(
                        f"LLM fallback succeeded with {model_config.name} "
                        f"(attempt {i+1}/{len(self.models)}) after {len(errors)} failures"
                    )

                logger.info(
                    f"LLM request successful: {model_config.name} "
                    f"({elapsed:.2f}s, {model_config.cost_tier})"
                )

                # Restore original model
                llm_service.model = original_model

                return response, model_config.name

            except Exception as e:
                error_msg = str(e)
                errors.append(f"{model_config.name}: {error_msg}")
                self.stats["model_failures"][model_config.name] += 1

                logger.warning(
                    f"Model {model_config.name} failed (attempt {i+1}/{len(self.models)}): {error_msg[:200]}"
                )

                # If this isn't the last model, continue to next
                if i < len(self.models) - 1:
                    logger.info(f"Falling back to next model: {self.models[i+1].name}")
                    continue
                else:
                    # Last model failed - we're out of options
                    break

        # All models failed
        llm_service.model = original_model

        error_summary = "\n".join(f"  - {err}" for err in errors)
        raise Exception(
            f"All {len(self.models)} models in fallback chain failed:\n{error_summary}"
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get fallback statistics.

        Returns:
            Dictionary with usage stats
        """
        stats = self.stats.copy()

        # Calculate fallback rate
        if stats["total_requests"] > 0:
            stats["fallback_rate_percent"] = round(
                (stats["fallbacks_triggered"] / stats["total_requests"]) * 100, 1
            )
        else:
            stats["fallback_rate_percent"] = 0.0

        # Primary model success rate
        if self.models:
            primary_model = self.models[0].name
            primary_attempts = stats["model_usage"][primary_model] + stats["model_failures"][primary_model]
            if primary_attempts > 0:
                stats["primary_success_rate_percent"] = round(
                    (stats["model_usage"][primary_model] / primary_attempts) * 100, 1
                )
            else:
                stats["primary_success_rate_percent"] = 0.0

        return stats

    def __repr__(self) -> str:
        """String representation."""
        stats = self.get_stats()
        return (
            f"LLMFallbackManager({len(self.models)} models, "
            f"{stats['total_requests']} requests, "
            f"{stats['fallback_rate_percent']}% fallback rate)"
        )
