"""RL types and enums."""

from enum import IntEnum
from typing import Tuple


class RLAction(IntEnum):
    """Actions available to the RL agent."""

    WAIT = 0  # Return (WAIT, None) -> Do nothing
    REACT = 1  # Return (REACT, emoji) -> Call _decide_reaction
    ENGAGE = (
        2  # Return (ENGAGE, text) -> Call _decide_proactive_engagement(force=False)
    )
    INITIATE = (
        3  # Return (INITIATE, text) -> Call _decide_proactive_engagement(force=True)
    )


# State is a tuple of (sentiment_bin, time_since_last_bin, message_count_bin)
RLState = Tuple[int, int, int]
