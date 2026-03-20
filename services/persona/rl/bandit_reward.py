"""Reward calculation for mode switching bandit."""

import logging
from typing import Optional

from .bandit_types import BanditConfig

logger = logging.getLogger(__name__)


def compute_mode_switch_reward(
    replied_within_5min: bool,
    engagement_quality: Optional[float] = None,
    config: Optional[BanditConfig] = None,
) -> float:
    """Compute reward for mode switching decision.

    Args:
        replied_within_5min: Whether user replied within 5 minutes
        engagement_quality: Optional quality score (0.0 to 1.0)
        config: Bandit configuration

    Returns:
        Reward value (typically -0.5 to +1.0)
    """
    cfg = config or BanditConfig()

    # Base reward based on reply timing
    if replied_within_5min:
        base_reward = cfg.reply_bonus  # +1.0
    else:
        base_reward = cfg.no_reply_penalty  # -0.5

    # Adjust by engagement quality if provided
    if engagement_quality is not None:
        # Blend base reward with quality (30% weight to quality)
        quality_adjusted = engagement_quality * cfg.reply_bonus
        reward = 0.7 * base_reward + 0.3 * quality_adjusted
    else:
        reward = base_reward

    # Clip to reasonable bounds
    reward = max(-1.0, min(1.0, reward))

    logger.debug(
        f"Computed reward: {reward:.3f} (replied={replied_within_5min}, quality={engagement_quality})"
    )
    return reward


def compute_engagement_quality(
    reply_content: str, sentiment: Optional[float] = None
) -> float:
    """Compute engagement quality from reply content.

    Args:
        reply_content: User's reply message
        sentiment: Optional sentiment score (-1.0 to 1.0)

    Returns:
        Quality score (0.0 to 1.0)
    """
    quality = 0.5  # Neutral default

    # Length heuristic: longer replies indicate more engagement
    content_len = len(reply_content.strip())
    if content_len > 100:
        quality += 0.2
    elif content_len > 50:
        quality += 0.1
    elif content_len < 10:
        quality -= 0.1

    # Sentiment adjustment
    if sentiment is not None:
        # Positive sentiment = better engagement
        quality += sentiment * 0.2

    # Clip to [0, 1]
    return max(0.0, min(1.0, quality))
