"""Storage interfaces and implementations for learned state persistence.

This module provides interfaces and implementations for persisting learned
social intelligence data, including user profiles, relationship graphs,
learned thresholds, and bandit state.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from core.social_intelligence.types import (
    UserPattern,
    RelationshipProfile,
)

logger = logging.getLogger(__name__)


class LearnedStateStore(Protocol):
    """Protocol for learned state persistence.

    Implementations of this protocol provide storage for learned social
    intelligence data, including user patterns, relationships, and
    adaptation state.
    """

    async def get_user_profile(
        self,
        user_id: str,
        persona_id: str,
        channel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve a user's learned profile.

        Args:
            user_id: The user identifier.
            persona_id: The persona identifier.
            channel_id: Optional channel context.

        Returns:
            User profile data dictionary.
        """
        ...

    async def update_user_profile(
        self,
        user_id: str,
        persona_id: str,
        updates: Dict[str, Any],
        channel_id: Optional[str] = None,
    ) -> None:
        """Update a user's learned profile.

        Args:
            user_id: The user identifier.
            persona_id: The persona identifier.
            updates: Profile fields to update.
            channel_id: Optional channel context.
        """
        ...

    async def get_relationship(
        self,
        user_id: str,
        persona_id: str,
    ) -> Optional[RelationshipProfile]:
        """Retrieve relationship profile between user and persona.

        Args:
            user_id: The user identifier.
            persona_id: The persona identifier.

        Returns:
            Relationship profile or None if not found.
        """
        ...

    async def update_relationship(
        self,
        profile: RelationshipProfile,
    ) -> None:
        """Update or create a relationship profile.

        Args:
            profile: The relationship profile to store.
        """
        ...

    async def get_learned_threshold(
        self,
        threshold_name: str,
        user_id: Optional[str] = None,
        persona_id: Optional[str] = None,
        default: float = 0.5,
    ) -> float:
        """Retrieve a learned threshold value.

        Args:
            threshold_name: Name of the threshold.
            user_id: Optional user-specific threshold.
            persona_id: Optional persona-specific threshold.
            default: Default value if not found.

        Returns:
            The threshold value.
        """
        ...

    async def update_learned_threshold(
        self,
        threshold_name: str,
        value: float,
        user_id: Optional[str] = None,
        persona_id: Optional[str] = None,
    ) -> None:
        """Update a learned threshold value.

        Args:
            threshold_name: Name of the threshold.
            value: New threshold value.
            user_id: Optional user-specific threshold.
            persona_id: Optional persona-specific threshold.
        """
        ...

    async def get_user_patterns(
        self,
        user_id: str,
        pattern_type: Optional[str] = None,
    ) -> List[UserPattern]:
        """Retrieve learned patterns for a user.

        Args:
            user_id: The user identifier.
            pattern_type: Optional pattern type filter.

        Returns:
            List of user patterns.
        """
        ...

    async def add_user_pattern(
        self,
        user_id: str,
        pattern: UserPattern,
    ) -> None:
        """Add a learned pattern for a user.

        Args:
            user_id: The user identifier.
            pattern: The pattern to store.
        """
        ...

    async def get_bandit_state(
        self,
        bandit_id: str,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve contextual bandit algorithm state.

        Args:
            bandit_id: Identifier for the bandit instance.
            user_id: Optional user-specific bandit.

        Returns:
            Bandit state dictionary.
        """
        ...

    async def update_bandit_state(
        self,
        bandit_id: str,
        state: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> None:
        """Update contextual bandit algorithm state.

        Args:
            bandit_id: Identifier for the bandit instance.
            state: Bandit state dictionary.
            user_id: Optional user-specific bandit.
        """
        ...


class SocialMemoryStore:
    """File-based implementation of learned state storage.

    Stores learned social intelligence data in JSON files under
    the data/social_intelligence/ directory. Uses namespaced storage
    for user_id × persona_id × channel_id isolation.

    Attributes:
        base_path: Root directory for storage.
        _cache: In-memory cache of frequently accessed data.
    """

    def __init__(self, base_path: Optional[str] = None):
        """Initialize the social memory store.

        Args:
            base_path: Root directory for storage. Defaults to
                data/social_intelligence/.
        """
        if base_path:
            self.base_path = Path(base_path)
        else:
            self.base_path = Path("data/social_intelligence")

        self._cache: Dict[str, Any] = {}
        self._ensure_directories()

        logger.debug(f"SocialMemoryStore initialized at {self.base_path}")

    def _ensure_directories(self) -> None:
        """Ensure storage directories exist."""
        (self.base_path / "profiles").mkdir(parents=True, exist_ok=True)
        (self.base_path / "relationships").mkdir(parents=True, exist_ok=True)
        (self.base_path / "thresholds").mkdir(parents=True, exist_ok=True)
        (self.base_path / "patterns").mkdir(parents=True, exist_ok=True)
        (self.base_path / "bandits").mkdir(parents=True, exist_ok=True)

    def _get_namespace_key(
        self,
        user_id: str,
        persona_id: str,
        channel_id: Optional[str] = None,
    ) -> str:
        """Generate a namespaced key for storage.

        Args:
            user_id: The user identifier.
            persona_id: The persona identifier.
            channel_id: Optional channel identifier.

        Returns:
            Namespaced key string.
        """
        if channel_id:
            return f"{user_id}:{persona_id}:{channel_id}"
        return f"{user_id}:{persona_id}"

    def _safe_filename(self, key: str) -> str:
        """Convert a key to a safe filename.

        Args:
            key: The key to convert.

        Returns:
            Safe filename string.
        """
        # Replace characters that might be problematic in filenames
        return key.replace(":", "_").replace("/", "_")

    async def get_user_profile(
        self,
        user_id: str,
        persona_id: str,
        channel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve a user's learned profile."""
        key = self._get_namespace_key(user_id, persona_id, channel_id)
        cache_key = f"profile:{key}"

        # Check cache first
        if cache_key in self._cache:
            return self._cache[cache_key].copy()

        # Load from file
        filename = self._safe_filename(key) + ".json"
        filepath = self.base_path / "profiles" / filename

        if not filepath.exists():
            # Return default profile
            return {
                "user_id": user_id,
                "persona_id": persona_id,
                "channel_id": channel_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "preferences": {},
                "interaction_count": 0,
            }

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                profile = json.load(f)
            self._cache[cache_key] = profile
            return profile.copy()
        except Exception as e:
            logger.warning(f"Failed to load profile for {key}: {e}")
            return {}

    async def update_user_profile(
        self,
        user_id: str,
        persona_id: str,
        updates: Dict[str, Any],
        channel_id: Optional[str] = None,
    ) -> None:
        """Update a user's learned profile."""
        key = self._get_namespace_key(user_id, persona_id, channel_id)
        cache_key = f"profile:{key}"

        # Get existing profile
        profile = await self.get_user_profile(user_id, persona_id, channel_id)

        # Apply updates
        profile.update(updates)
        profile["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Update cache
        self._cache[cache_key] = profile

        # Write to file (async-friendly using threads)
        filename = self._safe_filename(key) + ".json"
        filepath = self.base_path / "profiles" / filename

        def _write():
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(profile, f, indent=2, default=str)

        # Run in thread pool to avoid blocking
        import asyncio

        await asyncio.get_event_loop().run_in_executor(None, _write)

        logger.debug(f"Updated profile for {key}")

    async def get_relationship(
        self,
        user_id: str,
        persona_id: str,
    ) -> Optional[RelationshipProfile]:
        """Retrieve relationship profile between user and persona."""
        key = f"{user_id}:{persona_id}"
        filename = self._safe_filename(key) + ".json"
        filepath = self.base_path / "relationships" / filename

        if not filepath.exists():
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return RelationshipProfile.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to load relationship for {key}: {e}")
            return None

    async def update_relationship(
        self,
        profile: RelationshipProfile,
    ) -> None:
        """Update or create a relationship profile."""
        key = f"{profile.user_id}:{profile.persona_id}"
        filename = self._safe_filename(key) + ".json"
        filepath = self.base_path / "relationships" / filename

        def _write():
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(profile.to_dict(), f, indent=2, default=str)

        import asyncio

        await asyncio.get_event_loop().run_in_executor(None, _write)

        logger.debug(f"Updated relationship for {key}")

    async def get_learned_threshold(
        self,
        threshold_name: str,
        user_id: Optional[str] = None,
        persona_id: Optional[str] = None,
        default: float = 0.5,
    ) -> float:
        """Retrieve a learned threshold value."""
        # Build namespace key
        parts = [threshold_name]
        if user_id:
            parts.append(user_id)
        if persona_id:
            parts.append(persona_id)
        key = "_".join(parts)

        filename = self._safe_filename(key) + ".json"
        filepath = self.base_path / "thresholds" / filename

        if not filepath.exists():
            return default

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("value", default)
        except Exception as e:
            logger.warning(f"Failed to load threshold {key}: {e}")
            return default

    async def update_learned_threshold(
        self,
        threshold_name: str,
        value: float,
        user_id: Optional[str] = None,
        persona_id: Optional[str] = None,
    ) -> None:
        """Update a learned threshold value."""
        # Build namespace key
        parts = [threshold_name]
        if user_id:
            parts.append(user_id)
        if persona_id:
            parts.append(persona_id)
        key = "_".join(parts)

        filename = self._safe_filename(key) + ".json"
        filepath = self.base_path / "thresholds" / filename

        data = {
            "threshold_name": threshold_name,
            "user_id": user_id,
            "persona_id": persona_id,
            "value": value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        def _write():
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)

        import asyncio

        await asyncio.get_event_loop().run_in_executor(None, _write)

        logger.debug(f"Updated threshold {key} = {value}")

    async def get_user_patterns(
        self,
        user_id: str,
        pattern_type: Optional[str] = None,
    ) -> List[UserPattern]:
        """Retrieve learned patterns for a user."""
        patterns: List[UserPattern] = []
        patterns_dir = self.base_path / "patterns"

        if not patterns_dir.exists():
            return patterns

        prefix = self._safe_filename(user_id)

        for filepath in patterns_dir.glob("*.json"):
            if not filepath.stem.startswith(prefix):
                continue

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if pattern_type and data.get("pattern_type") != pattern_type:
                    continue

                patterns.append(UserPattern.from_dict(data))
            except Exception as e:
                logger.warning(f"Failed to load pattern from {filepath}: {e}")

        return patterns

    async def add_user_pattern(
        self,
        user_id: str,
        pattern: UserPattern,
    ) -> None:
        """Add a learned pattern for a user."""
        key = f"{user_id}_{pattern.pattern_id}"
        filename = self._safe_filename(key) + ".json"
        filepath = self.base_path / "patterns" / filename

        def _write():
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(pattern.to_dict(), f, indent=2, default=str)

        import asyncio

        await asyncio.get_event_loop().run_in_executor(None, _write)

        logger.debug(f"Added pattern {pattern.pattern_id} for {user_id}")

    async def get_bandit_state(
        self,
        bandit_id: str,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve contextual bandit algorithm state."""
        key = f"{bandit_id}_{user_id}" if user_id else bandit_id
        filename = self._safe_filename(key) + ".json"
        filepath = self.base_path / "bandits" / filename

        if not filepath.exists():
            return {"bandit_id": bandit_id, "user_id": user_id}

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load bandit state for {key}: {e}")
            return {"bandit_id": bandit_id, "user_id": user_id}

    async def update_bandit_state(
        self,
        bandit_id: str,
        state: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> None:
        """Update contextual bandit algorithm state."""
        key = f"{bandit_id}_{user_id}" if user_id else bandit_id
        filename = self._safe_filename(key) + ".json"
        filepath = self.base_path / "bandits" / filename

        # Add metadata to state
        state["bandit_id"] = bandit_id
        state["user_id"] = user_id
        state["updated_at"] = datetime.now(timezone.utc).isoformat()

        def _write():
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, default=str)

        import asyncio

        await asyncio.get_event_loop().run_in_executor(None, _write)

        logger.debug(f"Updated bandit state for {key}")

    def clear_cache(self) -> None:
        """Clear the in-memory cache."""
        self._cache.clear()
        logger.debug("Cache cleared")


# Type alias for backward compatibility
LearnedStateStoreImpl = SocialMemoryStore
