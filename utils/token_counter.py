"""Token counting utilities for context budget management."""

import logging
from typing import Dict, List, Optional
from config import Config

logger = logging.getLogger(__name__)


def count_tokens(text: str) -> int:
    """Estimate token count using character-based approximation.

    Args:
        text: Text to count tokens for

    Returns:
        Estimated token count
    """
    if not text:
        return 0

    # Approximate: ~1 token per 4 characters for English
    # This is a rough estimate. For accurate counts, use tiktoken or similar
    return len(text) // 4


def check_token_budget(
    current_tokens: int, context_limit: Optional[int] = None
) -> Dict[str, any]:
    """Check token budget and return status with warnings.

    Args:
        current_tokens: Current token count in context
        context_limit: Maximum allowed tokens (uses Config.MAX_CONTEXT_TOKENS if not specified)

    Returns:
        Dictionary with status and warning info:
        {
            "under_limit": bool,
            "warning": Optional[str],
            "warning_level": Optional[str],  # "info", "warning", "critical"
            "tokens_used": int,
            "tokens_remaining": int,
            "percentage_used": float
        }
    """
    if context_limit is None:
        context_limit = Config.MAX_CONTEXT_TOKENS

    tokens_remaining = context_limit - current_tokens
    percentage_used = (current_tokens / context_limit) * 100

    result = {
        "tokens_used": current_tokens,
        "tokens_remaining": tokens_remaining,
        "percentage_used": percentage_used,
        "under_limit": current_tokens < context_limit,
    }

    # Add warnings based on usage
    if percentage_used >= 90:
        result["warning_level"] = "critical"
        result["warning"] = (
            f"⚠️ CRITICAL: {percentage_used:.1f}% context used ({current_tokens}/{context_limit} tokens)"
        )
    elif percentage_used >= 75:
        result["warning_level"] = "warning"
        result["warning"] = (
            f"⚠️ WARNING: {percentage_used:.1f}% context used ({current_tokens}/{context_limit} tokens)"
        )
    elif percentage_used >= 50:
        result["warning_level"] = "info"
        result["warning"] = (
            f"ℹ️ INFO: {percentage_used:.1f}% context used ({current_tokens}/{context_limit} tokens)"
        )
    else:
        result["warning_level"] = None
        result["warning"] = None

    return result


def format_token_warning(budget_info: Dict[str, any]) -> Optional[str]:
    """Format token budget warning for display in logs or UI.

    Args:
        budget_info: Result from check_token_budget()

    Returns:
        Formatted warning string or None
    """
    if not budget_info.get("warning"):
        return None

    return budget_info["warning"]
