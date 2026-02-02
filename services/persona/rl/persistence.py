import json
import logging
import os
from pathlib import Path
from typing import Dict, Tuple
from collections import OrderedDict

from .agent import RLAgent

logger = logging.getLogger(__name__)


class RLStorage:
    """Persistence layer for RL agents using atomic JSON file storage."""

    def __init__(self, data_dir: Path):
        self.file_path = data_dir / "rl_policies.json"

    def load(self) -> OrderedDict[Tuple[int, int], RLAgent]:
        agents = OrderedDict()
        if not self.file_path.exists():
            return agents

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_agents = data.get("agents", {})
            for key_str, agent_data in raw_agents.items():
                try:
                    cid_str, uid_str = key_str.split(":")
                    key = (int(cid_str), int(uid_str))
                    agents[key] = RLAgent.from_dict(agent_data)
                except (ValueError, IndexError) as e:
                    logger.warning(f"Skipping invalid agent key {key_str}: {e}")
                    continue

            return agents
        except json.JSONDecodeError:
            logger.error(f"Corrupt RL data file: {self.file_path}. Starting fresh.")
            return agents
        except Exception as e:
            logger.error(f"Failed to load RL data: {e}")
            return agents

    def save(self, agents: Dict[Tuple[int, int], RLAgent]) -> None:
        data = {
            "version": 1,
            "agents": {f"{k[0]}:{k[1]}": v.to_dict() for k, v in agents.items()},
        }

        tmp_path = self.file_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            os.replace(tmp_path, self.file_path)
        except Exception as e:
            logger.error(f"Failed to save RL data: {e}")
            if tmp_path.exists():
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
