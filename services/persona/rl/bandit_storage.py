"""Persistence layer for bandit state."""

import json
import logging
from pathlib import Path
from typing import Dict, Tuple

from .bandit import LinUCBBandit
from .bandit_types import BanditConfig

logger = logging.getLogger(__name__)


class BanditStorage:
    """Storage for contextual bandit states using atomic JSON writes."""

    def __init__(self, data_dir: Path):
        """Initialize bandit storage.

        Args:
            data_dir: Directory for persistence files
        """
        self.file_path = data_dir / "bandit_states.json"

    def load(self) -> Dict[Tuple[int, int], LinUCBBandit]:
        """Load all bandit states from disk.

        Returns:
            Dictionary mapping (channel_id, user_id) to bandit instances
        """
        bandits = {}

        if not self.file_path.exists():
            logger.info("No bandit state file found, starting fresh")
            return bandits

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_bandits = data.get("bandits", {})
            for key_str, bandit_data in raw_bandits.items():
                try:
                    cid_str, uid_str = key_str.split(":")
                    key = (int(cid_str), int(uid_str))

                    # Create bandit and restore state
                    from .bandit import BanditState

                    bandit = LinUCBBandit(BanditConfig(**bandit_data.get("config", {})))
                    bandit.set_state(
                        BanditState.from_dict(bandit_data.get("state", {}))
                    )
                    bandits[key] = bandit

                except (ValueError, IndexError, KeyError) as e:
                    logger.warning(f"Skipping invalid bandit key {key_str}: {e}")
                    continue

            logger.info(f"Loaded {len(bandits)} bandit states")
            return bandits

        except json.JSONDecodeError:
            logger.error(f"Corrupt bandit data file: {self.file_path}. Starting fresh.")
            return bandits
        except Exception as e:
            logger.error(f"Failed to load bandit data: {e}")
            return bandits

    def save(self, bandits: Dict[Tuple[int, int], LinUCBBandit]) -> None:
        """Save all bandit states to disk atomically.

        Args:
            bandits: Dictionary of bandit instances
        """
        try:
            data = {
                "version": 1,
                "bandits": {
                    f"{k[0]}:{k[1]}": {
                        "config": {
                            "feature_dim": v.config.feature_dim,
                            "alpha": v.config.alpha,
                        },
                        "state": v.get_state().to_dict(),
                    }
                    for k, v in bandits.items()
                },
            }

            # Atomic write
            temp_file = self.file_path.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            temp_file.replace(self.file_path)
            logger.info(f"Saved {len(bandits)} bandit states")

        except Exception as e:
            logger.error(f"Failed to save bandit data: {e}")
