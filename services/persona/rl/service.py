"""RL Service Manager."""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional
from collections import OrderedDict

from .types import RLAction, RLState
from .agent import RLAgent
from .constants import (
    RL_EPSILON_START,
    RL_MAX_AGENTS_PER_CHANNEL,
    RL_PERSIST_INTERVAL,
)
from .persistence import RLStorage
from .safety import SafetyLayer

logger = logging.getLogger(__name__)


class RLService:
    """Service for managing RL agents per (channel_id, user_id)."""

    def __init__(self, bot=None, config=None):
        self.bot = bot
        self.config = config
        self.enabled = getattr(config, "RL_ENABLED", False) if config else False
        self.data_dir = Path(
            getattr(config, "RL_DATA_DIR", "./data/rl") if config else "./data/rl"
        )

        if self.enabled:
            self.data_dir.mkdir(parents=True, exist_ok=True)

        self.agents: OrderedDict[Tuple[int, int], RLAgent] = OrderedDict()
        self.agent_locks: Dict[Tuple[int, int], asyncio.Lock] = {}

        self.max_agents = RL_MAX_AGENTS_PER_CHANNEL * 10
        self.save_interval = RL_PERSIST_INTERVAL

        self.storage = RLStorage(self.data_dir)
        self.safety = SafetyLayer()

        self._bg_task = None

    async def start(self):
        if not self.enabled:
            return

        try:
            loaded_agents = await asyncio.to_thread(self.storage.load)
            self.agents.update(loaded_agents)
            logger.info(f"RL Service loaded {len(self.agents)} agents")
        except Exception as e:
            logger.error(f"Failed to load agents: {e}")

        if self._bg_task is None:
            self._bg_task = asyncio.create_task(self._persistence_loop())
            logger.info("RL Service started")

    async def stop(self):
        if self._bg_task:
            self._bg_task.cancel()
            try:
                await self._bg_task
            except asyncio.CancelledError:
                pass

        await self._save_all_dirty()
        logger.info("RL Service stopped")

    async def get_agent(self, channel_id: int, user_id: int) -> RLAgent:
        key = (channel_id, user_id)

        if key in self.agents:
            self.agents.move_to_end(key)
            return self.agents[key]

        agent = RLAgent(epsilon=RL_EPSILON_START)

        if len(self.agents) >= self.max_agents:
            old_key, old_agent = self.agents.popitem(last=False)
            if old_agent.dirty:
                await self._save_agent(old_key[0], old_key[1], old_agent)

        self.agents[key] = agent
        return agent

    async def get_action(
        self, channel_id: int, user_id: int, state: RLState
    ) -> Tuple[RLAction, Optional[str]]:
        """Get the next action for a user context."""
        if not self.enabled:
            return RLAction.WAIT, None

        key = (channel_id, user_id)
        if key not in self.agent_locks:
            self.agent_locks[key] = asyncio.Lock()

        async with self.agent_locks[key]:
            agent = await self.get_agent(channel_id, user_id)

            action = agent.get_action(state)

            if not self.safety.check(channel_id, user_id, action):
                return RLAction.WAIT, None

            return action, None

    async def update_agent(
        self,
        channel_id: int,
        user_id: int,
        state: RLState,
        action: RLAction,
        reward: float,
        next_state: RLState,
    ):
        """Update agent policy based on reward."""
        if not self.enabled:
            return

        key = (channel_id, user_id)
        if key not in self.agent_locks:
            self.agent_locks[key] = asyncio.Lock()

        async with self.agent_locks[key]:
            agent = await self.get_agent(channel_id, user_id)
            agent.update(state, action, reward, next_state)

    async def _save_agent(self, channel_id: int, user_id: int, agent: RLAgent):
        """Save a single agent."""
        await self._save_all_dirty()

    async def _save_all_dirty(self):
        """Save all agents marked as dirty."""
        any_dirty = any(a.dirty for a in self.agents.values())
        if not any_dirty:
            return

        try:
            await asyncio.to_thread(self.storage.save, self.agents)

            for agent in self.agents.values():
                agent.dirty = False

        except Exception as e:
            logger.error(f"Failed to save RL agents: {e}")

    async def _persistence_loop(self):
        """Background loop to periodically save data."""
        while True:
            try:
                await asyncio.sleep(self.save_interval)
                await self._save_all_dirty()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in RL persistence loop: {e}")
