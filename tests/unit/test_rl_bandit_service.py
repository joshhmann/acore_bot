from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.persona.rl.bandit import LinUCBBandit
from services.persona.rl.service import RLService


pytestmark = pytest.mark.unit


def _config(tmp_path):
    return SimpleNamespace(
        RL_ENABLED=True,
        RL_DATA_DIR=str(tmp_path / "rl"),
        RL_EXPLORATION_MODE=False,
        RL_EXPLORATION_ACTIVITY_THRESHOLD=5,
        RL_EXPLORATION_BONUS_MAX=3.0,
        RL_EPSILON_BOOST_FACTOR=2.0,
        RL_EPSILON_BOOST_DECAY=0.999,
    )


def test_rl_service_initializes_bandit_state(tmp_path) -> None:
    service = RLService(config=_config(tmp_path))

    assert service.bandits == {}
    assert service.bandit_storage.file_path.name == "bandit_states.json"
    assert service.bandit_config.feature_dim == 7


@pytest.mark.asyncio
async def test_rl_service_saves_bandits_even_without_dirty_agents(tmp_path) -> None:
    service = RLService(config=_config(tmp_path))
    service.bandits[(1, 2)] = LinUCBBandit(service.bandit_config)

    await service._save_all_dirty()

    assert service.bandit_storage.file_path.exists()
