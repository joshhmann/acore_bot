import time
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from .types import RLAction


class SafetyLayer:
    """Safety layer for RL actions to prevent spam/abuse."""

    def __init__(self):
        self.user_history: Dict[Tuple[int, int], List[Tuple[float, RLAction]]] = (
            defaultdict(list)
        )
        self.channel_history: Dict[int, List[float]] = defaultdict(list)

    def check(
        self,
        channel_id: int,
        user_id: int,
        action: RLAction,
        timestamp: Optional[float] = None,
    ) -> bool:
        if timestamp is None:
            timestamp = time.time()

        if action == RLAction.WAIT:
            return True

        user_key = (channel_id, user_id)

        self.user_history[user_key] = [
            (t, a) for t, a in self.user_history[user_key] if timestamp - t < 300
        ]

        same_action_count = sum(
            1 for _, a in self.user_history[user_key] if a == action
        )
        if same_action_count >= 3:
            return False

        self.channel_history[channel_id] = [
            t for t in self.channel_history[channel_id] if timestamp - t < 3600
        ]

        if len(self.channel_history[channel_id]) >= 20:
            return False

        self.user_history[user_key].append((timestamp, action))
        self.channel_history[channel_id].append(timestamp)

        return True
