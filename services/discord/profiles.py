"""User Profile service for learning about Discord users over time."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import asyncio
import aiofiles
import pickle
import time

logger = logging.getLogger(__name__)


class UserProfileService:
    """Service for managing user profiles and memories.

    Learns about users through conversations and can:
    - Store facts about users (interests, preferences, personality traits)
    - Remember past interactions and events
    - Provide user context to the AI for personalized responses
    - Allow bot to reference users by their characteristics
    """

    INDEX_VERSION = 1
    INDEX_CACHE_FILE = "_index_cache.pkl"

    def __init__(
        self, profiles_dir: Path, ollama_service=None, persona_id: Optional[str] = None
    ):
        """Initialize user profile service.

        Args:
            profiles_dir: Base directory to store user profile JSON files
            ollama_service: Optional OllamaService for AI-powered profile extraction
            persona_id: Optional persona ID for memory isolation (default: "default")
        """
        # Store base directory and persona ID
        self.profiles_base_dir = Path(profiles_dir)
        self.persona_id = persona_id or "default"

        # Persona-scoped directory: data/profiles/{persona_id}/
        self.profiles_dir = self.profiles_base_dir / self.persona_id
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache of loaded profiles
        self.profiles: Dict[int, Dict] = {}

        # Indices for fast lookups
        self.trait_index: Dict[str, set] = {}
        self.interest_index: Dict[str, set] = {}
        self._indices_built = False

        # AI service for automatic profile learning
        self.ollama = ollama_service

        # Dirty profiles tracking for periodic saving
        self.dirty_profiles = set()
        self._save_task = None
        self._index_task = None

        logger.info(
            f"User profile service initialized (persona: {self.persona_id}, dir: {self.profiles_dir})"
        )

    def set_persona(self, persona_id: str):
        """Switch to a different persona context.

        This updates the profiles directory and clears caches.
        Pending dirty profiles will be flushed before switching.

        Args:
            persona_id: The persona ID to switch to
        """
        if persona_id == self.persona_id:
            return  # Already using this persona

        logger.info(
            f"Switching persona context from '{self.persona_id}' to '{persona_id}'"
        )

        # Flush any pending saves for current persona
        # Note: This is sync, caller should await _flush_all_dirty() if needed

        # Update persona context
        self.persona_id = persona_id
        self.profiles_dir = self.profiles_base_dir / self.persona_id
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

        # Clear caches
        self.profiles.clear()
        self.trait_index.clear()
        self.interest_index.clear()
        self._indices_built = False
        self.dirty_profiles.clear()

        logger.info(f"Switched to persona '{persona_id}' (dir: {self.profiles_dir})")

    async def start_background_saver(self):
        """Start the background task to save dirty profiles periodically."""
        if self._save_task is None:
            self._save_task = asyncio.create_task(self._periodic_save_loop())
            logger.info("Started background profile saver")

        # Also start building/loading indices in background
        if self._index_task is None and not self._indices_built:
            self._index_task = asyncio.create_task(self._load_or_build_indices())

    async def stop_background_saver(self):
        """Stop the background saver and flush pending changes."""
        if self._save_task:
            self._save_task.cancel()
            try:
                await self._save_task
            except asyncio.CancelledError:
                pass
            self._save_task = None

        # Flush all dirty profiles
        await self._flush_all_dirty()

    async def _periodic_save_loop(self):
        """Loop to save dirty profiles at configured interval."""
        from config import Config

        try:
            while True:
                await asyncio.sleep(Config.PROFILE_SAVE_INTERVAL_SECONDS)
                await self._flush_all_dirty()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in periodic save loop: {e}")

    async def _flush_all_dirty(self):
        """Save all profiles marked as dirty."""
        if not self.dirty_profiles:
            return

        dirty_ids = list(self.dirty_profiles)
        self.dirty_profiles.clear()

        logger.debug(f"Flushing {len(dirty_ids)} dirty profiles...")

        # Parallel save with concurrency limit
        semaphore = asyncio.Semaphore(10)

        async def save_with_limit(user_id):
            async with semaphore:
                await self._flush_profile(user_id)

        # Use asyncio.gather for parallel saving
        await asyncio.gather(
            *[save_with_limit(uid) for uid in dirty_ids], return_exceptions=True
        )

    async def _flush_profile(self, user_id: int) -> bool:
        """Internal method to write profile to disk immediately."""
        if user_id not in self.profiles:
            return False

        profile = self.profiles[user_id]
        try:
            profile_file = self._get_profile_file(user_id)
            async with aiofiles.open(profile_file, "w", encoding="utf-8") as f:
                await f.write(json.dumps(profile, indent=2))
            logger.debug(f"Flushed profile for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to flush profile for user {user_id}: {e}")
            # Add back to dirty set to retry later
            self.dirty_profiles.add(user_id)
            return False

    async def _load_or_build_indices(self):
        """Load indices from cache or build from scratch."""
        cache_path = self.profiles_dir / self.INDEX_CACHE_FILE

        # Try to load cached indices
        if cache_path.exists():
            try:
                logger.info(f"Loading profile indices from cache: {cache_path}")

                # Use to_thread for pickle loading as it can be CPU intensive
                def load_pickle():
                    with open(cache_path, "rb") as f:
                        return pickle.load(f)

                cache_data = await asyncio.to_thread(load_pickle)

                if cache_data.get("version") == self.INDEX_VERSION:
                    self.trait_index = cache_data["trait_index"]
                    self.interest_index = cache_data["interest_index"]
                    self._indices_built = True
                    logger.info("Successfully loaded profile indices from cache")
                    return
                else:
                    logger.info(
                        f"Index cache version mismatch (got {cache_data.get('version')}, expected {self.INDEX_VERSION})"
                    )
            except Exception as e:
                logger.warning(f"Failed to load index cache: {e}")

        # Build indices from scratch
        await self._build_indices()

        # Save to cache
        await self._save_index_cache()

    async def _save_index_cache(self):
        """Save indices to pickle cache."""
        try:
            cache_path = self.profiles_dir / self.INDEX_CACHE_FILE
            cache_data = {
                "version": self.INDEX_VERSION,
                "trait_index": self.trait_index,
                "interest_index": self.interest_index,
                "timestamp": time.time(),
            }

            def save_pickle():
                with open(cache_path, "wb") as f:
                    pickle.dump(cache_data, f)

            await asyncio.to_thread(save_pickle)
            logger.debug("Saved profile index cache")
        except Exception as e:
            logger.error(f"Failed to save index cache: {e}")

    async def _build_indices(self):
        """Build in-memory indices from all profile files."""
        logger.info("Building user profile indices from disk...")
        count = 0
        try:
            # Iterate over all profile files
            for profile_file in self.profiles_dir.glob("user_*.json"):
                try:
                    async with aiofiles.open(profile_file, "r", encoding="utf-8") as f:
                        content = await f.read()
                        profile = json.loads(content)
                        user_id = profile["user_id"]

                        # Cache profile
                        self.profiles[user_id] = profile

                        # Update indices
                        self._update_indices(user_id, profile)
                        count += 1
                except Exception as e:
                    logger.error(f"Error indexing profile {profile_file}: {e}")

            self._indices_built = True
            logger.info(f"Indexed {count} user profiles")

        except Exception as e:
            logger.error(f"Failed to build profile indices: {e}")

    def _update_indices(self, user_id: int, profile: Dict):
        """Update indices for a single user.

        Args:
            user_id: Discord user ID
            profile: User profile dict
        """
        # Update trait index
        for trait in profile.get("traits", []):
            trait_lower = trait.lower()
            if trait_lower not in self.trait_index:
                self.trait_index[trait_lower] = set()
            self.trait_index[trait_lower].add(user_id)

        # Update interest index
        for interest in profile.get("interests", []):
            interest_lower = interest.lower()
            if interest_lower not in self.interest_index:
                self.interest_index[interest_lower] = set()
            self.interest_index[interest_lower].add(user_id)

    def _get_profile_file(self, user_id: int) -> Path:
        """Get the profile file path for a user.

        Args:
            user_id: Discord user ID

        Returns:
            Path to user's profile file
        """
        return self.profiles_dir / f"user_{user_id}.json"

    async def load_profile(self, user_id: int) -> Dict:
        """Load a user's profile from disk.

        Args:
            user_id: Discord user ID

        Returns:
            User profile dict
        """
        # Check cache first
        if user_id in self.profiles:
            return self.profiles[user_id]

        profile_file = self._get_profile_file(user_id)

        # Initialize default profile if doesn't exist
        if not profile_file.exists():
            profile = self._create_default_profile(user_id)
            self.profiles[user_id] = profile
            self._update_indices(user_id, profile)
            return profile

        # Load from disk
        try:
            async with aiofiles.open(profile_file, "r", encoding="utf-8") as f:
                content = await f.read()
                profile = json.loads(content)
                self.profiles[user_id] = profile
                self._update_indices(user_id, profile)
                logger.debug(f"Loaded profile for user {user_id}")
                return profile
        except Exception as e:
            logger.error(f"Failed to load profile for user {user_id}: {e}")
            profile = self._create_default_profile(user_id)
            self.profiles[user_id] = profile
            self._update_indices(user_id, profile)
            return profile

    def _create_default_profile(self, user_id: int) -> Dict:
        """Create a default user profile.

        Args:
            user_id: Discord user ID

        Returns:
            Default profile dict
        """
        return {
            "user_id": user_id,
            "username": None,  # Will be populated on first interaction
            "created_at": datetime.utcnow().isoformat(),
            "last_updated": datetime.utcnow().isoformat(),
            "traits": [],  # List of personality traits: ["funny", "sarcastic", "tech-savvy"]
            "interests": [],  # List of interests: ["gaming", "anime", "coding"]
            "preferences": {},  # Key-value preferences: {"favorite_game": "Halo"}
            "facts": [],  # List of facts about the user with timestamps
            "interaction_count": 0,
            "memorable_quotes": [],  # Funny or notable things they've said
            "relationships": {},  # Relationships with other users: {user_id: "friend", ...}
            "affection": {
                "level": 0,  # 0-100 scale: how much the bot "likes" this user
                "relationship_stage": "stranger",  # stranger -> acquaintance -> friend -> close_friend -> best_friend
                "last_interaction": None,
                "positive_interactions": 0,  # Times user made bot "happy"
                "negative_interactions": 0,  # Times user was mean/rude
                "conversation_quality": 0,  # Rolling average of conversation quality
            },
            "first_met": datetime.utcnow().isoformat(),
            "total_messages": 0,
            "avg_message_length": 0,
        }

    async def save_profile(self, user_id: int) -> bool:
        """Mark a user's profile as dirty to be saved later.

        Args:
            user_id: Discord user ID

        Returns:
            True (always returns True as save is deferred)
        """
        if user_id not in self.profiles:
            logger.warning(f"Attempted to save non-existent profile for user {user_id}")
            return False

        profile = self.profiles[user_id]
        profile["last_updated"] = datetime.utcnow().isoformat()

        # Mark as dirty
        self.dirty_profiles.add(user_id)
        return True

    async def add_fact(
        self, user_id: int, fact: str, source: str = "conversation"
    ) -> bool:
        """Add a fact about a user.

        Args:
            user_id: Discord user ID
            fact: Fact to remember about the user
            source: Source of the fact (conversation, command, etc.)

        Returns:
            True if successful
        """
        profile = await self.load_profile(user_id)

        fact_entry = {
            "fact": fact,
            "timestamp": datetime.utcnow().isoformat(),
            "source": source,
        }

        profile["facts"].append(fact_entry)
        profile["interaction_count"] += 1

        return await self.save_profile(user_id)

    async def add_interest(self, user_id: int, interest: str) -> bool:
        """Add an interest for a user.

        Args:
            user_id: Discord user ID
            interest: Interest to add

        Returns:
            True if successful
        """
        profile = await self.load_profile(user_id)

        if interest.lower() not in [i.lower() for i in profile["interests"]]:
            profile["interests"].append(interest)
            self._update_indices(user_id, profile)
            return await self.save_profile(user_id)

        return False  # Already exists

    async def add_trait(self, user_id: int, trait: str) -> bool:
        """Add a personality trait for a user.

        Args:
            user_id: Discord user ID
            trait: Trait to add

        Returns:
            True if successful
        """
        profile = await self.load_profile(user_id)

        if trait.lower() not in [t.lower() for t in profile["traits"]]:
            profile["traits"].append(trait)
            self._update_indices(user_id, profile)
            return await self.save_profile(user_id)

        return False

    async def set_preference(self, user_id: int, key: str, value: str) -> bool:
        """Set a preference for a user.

        Args:
            user_id: Discord user ID
            key: Preference key
            value: Preference value

        Returns:
            True if successful
        """
        profile = await self.load_profile(user_id)
        profile["preferences"][key] = value
        return await self.save_profile(user_id)

    async def add_quote(self, user_id: int, quote: str, context: str = "") -> bool:
        """Add a memorable quote from the user.

        Args:
            user_id: Discord user ID
            quote: The quote
            context: Optional context for the quote

        Returns:
            True if successful
        """
        profile = await self.load_profile(user_id)

        quote_entry = {
            "quote": quote,
            "context": context,
            "timestamp": datetime.utcnow().isoformat(),
        }

        profile["memorable_quotes"].append(quote_entry)

        # Keep only last 20 quotes
        if len(profile["memorable_quotes"]) > 20:
            profile["memorable_quotes"] = profile["memorable_quotes"][-20:]

        return await self.save_profile(user_id)

    async def set_relationship(
        self, user_id: int, other_user_id: int, relationship: str
    ) -> bool:
        """Set relationship between users.

        Args:
            user_id: Discord user ID
            other_user_id: Other user's ID
            relationship: Type of relationship (friend, rival, etc.)

        Returns:
            True if successful
        """
        profile = await self.load_profile(user_id)
        profile["relationships"][str(other_user_id)] = relationship
        return await self.save_profile(user_id)

    async def get_user_context(self, user_id: int, max_length: int = 500) -> str:
        """Get formatted context about a user for AI.

        Args:
            user_id: Discord user ID
            max_length: Maximum character length

        Returns:
            Formatted string describing the user
        """
        profile = await self.load_profile(user_id)

        if profile["interaction_count"] == 0:
            return "New user - no profile information yet."

        context_parts = []

        # Username
        if profile.get("username"):
            context_parts.append(f"User: {profile['username']}")

        # Traits
        if profile["traits"]:
            traits_str = ", ".join(profile["traits"][:5])
            context_parts.append(f"Personality: {traits_str}")

        # Interests
        if profile["interests"]:
            interests_str = ", ".join(profile["interests"][:5])
            context_parts.append(f"Interests: {interests_str}")

        # Recent facts (last 5)
        if profile["facts"]:
            recent_facts = profile["facts"][-5:]
            # Handle both string facts and dict facts (in case of malformed data)
            fact_strings = []
            for f in recent_facts:
                fact = f.get("fact", f) if isinstance(f, dict) else f
                # Convert to string if it's still a dict (malformed data)
                if isinstance(fact, dict):
                    fact = str(fact.get("value", str(fact)))
                if isinstance(fact, str) and fact.strip():
                    fact_strings.append(fact)
            if fact_strings:
                facts_str = "; ".join(fact_strings)
                context_parts.append(f"Known facts: {facts_str}")

        # Preferences
        if profile["preferences"]:
            prefs = []
            for k, v in list(profile["preferences"].items())[:3]:
                prefs.append(f"{k}: {v}")
            context_parts.append(f"Preferences: {', '.join(prefs)}")

        context = "\n".join(context_parts)

        # Truncate if too long
        if len(context) > max_length:
            context = context[: max_length - 3] + "..."

        return context

    async def search_users_by_trait(self, trait: str) -> List[int]:
        """Find users with a specific trait.

        Args:
            trait: Trait to search for

        Returns:
            List of user IDs matching the trait
        """
        matching_users = []
        trait_lower = trait.lower()

        # Use index if available
        if trait_lower in self.trait_index:
            return list(self.trait_index[trait_lower])

        # Fallback to scanning if indices not built yet (should be rare)
        if not self._indices_built:
            # Load all profiles
            for profile_file in self.profiles_dir.glob("user_*.json"):
                try:
                    async with aiofiles.open(profile_file, "r", encoding="utf-8") as f:
                        content = await f.read()
                        profile = json.loads(content)

                        # Update cache while we're at it
                        self.profiles[profile["user_id"]] = profile
                        self._update_indices(profile["user_id"], profile)

                        # Check traits
                        user_traits = [t.lower() for t in profile.get("traits", [])]
                        if trait_lower in user_traits:
                            matching_users.append(profile["user_id"])

                except Exception as e:
                    logger.error(f"Error searching profile {profile_file}: {e}")

        return matching_users

    async def search_users_by_interest(self, interest: str) -> List[int]:
        """Find users with a specific interest.

        Args:
            interest: Interest to search for

        Returns:
            List of user IDs matching the interest
        """
        matching_users = []
        interest_lower = interest.lower()

        # Use index if available
        if interest_lower in self.interest_index:
            return list(self.interest_index[interest_lower])

        # Fallback to scanning if indices not built yet
        if not self._indices_built:
            for profile_file in self.profiles_dir.glob("user_*.json"):
                try:
                    async with aiofiles.open(profile_file, "r", encoding="utf-8") as f:
                        content = await f.read()
                        profile = json.loads(content)

                        # Update cache
                        self.profiles[profile["user_id"]] = profile
                        self._update_indices(profile["user_id"], profile)

                        user_interests = [
                            i.lower() for i in profile.get("interests", [])
                        ]
                        if interest_lower in user_interests:
                            matching_users.append(profile["user_id"])

                except Exception as e:
                    logger.error(f"Error searching profile {profile_file}: {e}")

        return matching_users

    async def get_all_users_context(self, max_users: int = 10) -> str:
        """Get context about all known users for AI awareness.

        Args:
            max_users: Maximum number of users to include

        Returns:
            Formatted string describing known users
        """
        all_profiles = []

        if self._indices_built:
            # Use cached profiles
            all_profiles = list(self.profiles.values())
        else:
            # Fallback to reading files
            for profile_file in self.profiles_dir.glob("user_*.json"):
                try:
                    async with aiofiles.open(profile_file, "r", encoding="utf-8") as f:
                        content = await f.read()
                        profile = json.loads(content)
                        if profile["interaction_count"] > 0:
                            all_profiles.append(profile)
                except Exception as e:
                    logger.error(f"Error loading profile {profile_file}: {e}")

        if not all_profiles:
            return "No user profiles available yet."

        # Sort by interaction count (most active first)
        all_profiles.sort(key=lambda p: p["interaction_count"], reverse=True)
        all_profiles = all_profiles[:max_users]

        context_parts = ["Known server members:"]

        for profile in all_profiles:
            username = profile.get("username", f"User {profile['user_id']}")
            traits = (
                ", ".join(profile["traits"][:3]) if profile["traits"] else "unknown"
            )
            interests = (
                ", ".join(profile["interests"][:3]) if profile["interests"] else "none"
            )

            user_desc = f"- {username}: {traits}"
            if interests != "none":
                user_desc += f" | interests: {interests}"

            context_parts.append(user_desc)

        return "\n".join(context_parts)

    async def update_username(self, user_id: int, username: str) -> bool:
        """Update a user's username.

        Args:
            user_id: Discord user ID
            username: New username

        Returns:
            True if successful
        """
        profile = await self.load_profile(user_id)
        profile["username"] = username
        return await self.save_profile(user_id)

    async def increment_interaction(self, user_id: int) -> bool:
        """Increment interaction counter for a user.

        Args:
            user_id: Discord user ID

        Returns:
            True if successful
        """
        profile = await self.load_profile(user_id)
        profile["interaction_count"] += 1
        return await self.save_profile(user_id)

    async def learn_from_conversation(
        self, user_id: int, username: str, user_message: str, bot_response: str
    ) -> bool:
        """Automatically learn about a user from a conversation using AI.

        Args:
            user_id: Discord user ID
            username: User's display name
            user_message: What the user said
            bot_response: How the bot responded

        Returns:
            True if profile was updated
        """
        if not self.ollama:
            logger.warning(
                "Cannot learn from conversation - no Ollama service provided"
            )
            return False

        try:
            response = ""  # Initialize for exception handler
            # Create extraction prompt
            extraction_prompt = f"""Analyze this Discord conversation and extract information about the user.

User: {username}
Message: "{user_message}"
Bot Response: "{bot_response}"

Extract ONLY information that is clearly stated or strongly implied. Return a JSON object with:
{{
  "traits": [],        // Personality traits: ["funny", "sarcastic", "friendly", "analytical", etc.]
  "interests": [],     // Topics they're interested in: ["gaming", "Halo", "anime", "coding", etc.]
  "facts": [],         // Specific facts: ["Plays Halo 3", "Favorite color is blue", etc.]
  "preferences": {{}},  // Key-value pairs: {{"favorite_game": "Halo 3", "timezone": "PST"}}
  "memorable_quote": null,  // If user said something genuinely funny/clever/interesting, include it. Otherwise null.
  "behavioral_instruction": null  // IMPORTANT: If the user is telling the bot HOW to behave or respond (e.g., "when you see X, say Y", "always greet them with Z", "call them by nickname"), extract the EXACT instruction here.
}}

RULES:
- Only include information that is clearly present in this conversation
- Be conservative - if unsure, don't include it
- Traits should be adjectives describing personality
- Interests should be nouns/topics
- Facts should be complete statements
- memorable_quote: Only for genuinely funny, witty, or uniquely interesting statements
- **behavioral_instruction**: Look for phrases like "when you see", "always say", "greet with", "call them", "respond with", "remember to". If found, extract the FULL instruction EXACTLY as stated.
- If nothing can be extracted, return empty arrays/objects/null
- Return ONLY valid JSON, no other text

JSON:"""

            # Get AI extraction
            response = await self.ollama.chat(
                messages=[{"role": "user", "content": extraction_prompt}],
                system_prompt="You are a precise information extraction system. Return only valid JSON.",
                temperature=0.3,  # Lower temperature for more consistent extraction
            )

            # Parse the JSON response
            # Strip any markdown code blocks if present
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            extracted = json.loads(response)

            # Load current profile
            profile = await self.load_profile(user_id)

            # Update username
            if not profile.get("username"):
                profile["username"] = username

            # Merge extracted data
            updated = False

            # Add new traits (avoid duplicates)
            for trait in extracted.get("traits", []):
                if trait and trait.lower() not in [
                    t.lower() for t in profile["traits"]
                ]:
                    profile["traits"].append(trait)
                    updated = True

            # Add new interests (avoid duplicates)
            for interest in extracted.get("interests", []):
                if interest and interest.lower() not in [
                    i.lower() for i in profile["interests"]
                ]:
                    profile["interests"].append(interest)
                    updated = True

            # Add new facts with timestamp
            for fact in extracted.get("facts", []):
                if fact:
                    fact_entry = {
                        "fact": fact,
                        "timestamp": datetime.utcnow().isoformat(),
                        "source": "conversation",
                    }
                    profile["facts"].append(fact_entry)
                    updated = True

            # Update preferences
            for key, value in extracted.get("preferences", {}).items():
                if key and value:
                    profile["preferences"][key] = value
                    updated = True

            # Extract memorable quotes if conversation was funny/interesting
            if extracted.get("memorable_quote"):
                quote_entry = {
                    "quote": extracted["memorable_quote"],
                    "context": f"{user_message[:100]}...",
                    "timestamp": datetime.utcnow().isoformat(),
                }
                profile["memorable_quotes"].append(quote_entry)
                # Keep only last 20 quotes
                if len(profile["memorable_quotes"]) > 20:
                    profile["memorable_quotes"] = profile["memorable_quotes"][-20:]
                updated = True

            # Extract behavioral instructions (e.g., "when you see X, say Y")
            if extracted.get("behavioral_instruction"):
                instruction = extracted["behavioral_instruction"]

                # Check if this instruction is about another user (contains "when you see", "for @user", etc.)
                # We'll store it in the MENTIONED user's profile, not the speaker's
                import re

                # Try to extract mentioned user IDs from the original message
                mention_pattern = r"<@!?(\d+)>"
                mentioned_ids = re.findall(mention_pattern, user_message)

                if mentioned_ids:
                    # Store instruction in the MENTIONED user's profile
                    for mentioned_id_str in mentioned_ids:
                        mentioned_id = int(mentioned_id_str)
                        mentioned_profile = await self.load_profile(mentioned_id)

                        fact_entry = {
                            "fact": f"When you see this user: {instruction}",
                            "timestamp": datetime.utcnow().isoformat(),
                            "source": "behavioral_instruction",
                        }
                        mentioned_profile["facts"].append(fact_entry)
                        await self.save_profile(mentioned_id)
                        logger.info(
                            f"Learned behavioral instruction for mentioned user {mentioned_id}: {instruction}"
                        )
                        updated = True
                else:
                    # No mention found, store in speaker's profile as before
                    fact_entry = {
                        "fact": f"When you see {username}: {instruction}",
                        "timestamp": datetime.utcnow().isoformat(),
                        "source": "behavioral_instruction",
                    }
                    profile["facts"].append(fact_entry)
                    updated = True
                    logger.info(
                        f"Learned behavioral instruction for user {user_id}: {instruction}"
                    )

            # Save if anything was learned
            if updated:
                await self.save_profile(user_id)
                logger.info(
                    f"Learned new information about user {user_id} from conversation"
                )

            return updated

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI extraction response: {e}")
            # Only log response if it was successfully retrieved
            if "response" in locals():
                logger.debug(f"Response was: {response}")
            return False
        except Exception as e:
            logger.error(f"Failed to learn from conversation for user {user_id}: {e}")
            return False

    async def update_affection(
        self, user_id: int, message: str, bot_response: str
    ) -> dict:
        """Update affection score based on conversation quality.

        Args:
            user_id: Discord user ID
            message: User's message
            bot_response: Bot's response

        Returns:
            Updated affection data
        """
        if not self.ollama:
            return {}

        profile = await self.load_profile(user_id)

        # Initialize affection if it doesn't exist (for old profiles)
        if "affection" not in profile:
            profile["affection"] = {
                "level": 0,
                "relationship_stage": "stranger",
                "last_interaction": None,
                "positive_interactions": 0,
                "negative_interactions": 0,
                "conversation_quality": 0,
            }

        try:
            # Ask AI to rate the conversation sentiment
            sentiment_prompt = f"""Analyze this Discord conversation and rate how the user treated the bot.

User message: "{message}"
Bot response: "{bot_response}"

Return ONLY a JSON object:
{{
  "sentiment": "positive" | "neutral" | "negative",
  "is_funny": true/false,
  "is_interesting": true/false,
  "affection_change": <integer from -5 to 5>
}}

RULES:
- positive: User is friendly, engaging, appreciative
- negative: User is rude, dismissive, mean
- neutral: Normal conversation
- is_funny: User made a genuinely funny joke/comment
- is_interesting: Conversation was engaging/thought-provoking
- affection_change: Integer from -5 to 5 (no + prefix, just the number)

JSON:"""

            response = await self.ollama.chat(
                messages=[{"role": "user", "content": sentiment_prompt}],
                system_prompt="You are a sentiment analyzer. Return only valid JSON.",
                temperature=0.3,
            )

            # Parse response - clean up markdown and extra text
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            # Try to extract JSON if there's extra text
            if not response.startswith("{"):
                # Find first { and last }
                start = response.find("{")
                end = response.rfind("}")
                if start >= 0 and end > start:
                    response = response[start : end + 1]

            # Remove any comments, trailing commas, and fix common JSON issues
            import re

            response = re.sub(
                r"//.*$", "", response, flags=re.MULTILINE
            )  # Remove comments
            response = re.sub(r",\s*}", "}", response)  # Remove trailing commas
            response = re.sub(
                r",\s*]", "]", response
            )  # Remove trailing commas in arrays
            response = re.sub(
                r":\s*\+(\d)", r": \1", response
            )  # Remove + prefix from positive numbers

            try:
                sentiment_data = json.loads(response)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse affection JSON: {e}")
                logger.error(f"Raw response: {response[:200]}")
                # Return neutral sentiment as fallback
                sentiment_data = {
                    "sentiment": "neutral",
                    "is_funny": False,
                    "is_interesting": False,
                    "affection_change": 0,
                }

            # Update affection
            affection_change = sentiment_data.get("affection_change", 0)
            profile["affection"]["level"] = max(
                0, min(100, profile["affection"]["level"] + affection_change)
            )

            # Track positive/negative interactions
            if sentiment_data.get("sentiment") == "positive":
                profile["affection"]["positive_interactions"] += 1
            elif sentiment_data.get("sentiment") == "negative":
                profile["affection"]["negative_interactions"] += 1

            # Update relationship stage based on affection level
            level = profile["affection"]["level"]
            if level >= 80:
                profile["affection"]["relationship_stage"] = "best_friend"
            elif level >= 60:
                profile["affection"]["relationship_stage"] = "close_friend"
            elif level >= 40:
                profile["affection"]["relationship_stage"] = "friend"
            elif level >= 20:
                profile["affection"]["relationship_stage"] = "acquaintance"
            else:
                profile["affection"]["relationship_stage"] = "stranger"

            # Update last interaction
            profile["affection"]["last_interaction"] = datetime.utcnow().isoformat()

            await self.save_profile(user_id)

            return profile["affection"]

        except Exception as e:
            logger.error(f"Failed to update affection for user {user_id}: {e}")
            return profile.get("affection", {})

    def get_affection_context(self, user_id: int) -> str:
        """Get affection context for AI prompt.

        Args:
            user_id: Discord user ID

        Returns:
            Formatted affection context string
        """
        if user_id not in self.profiles:
            return ""

        profile = self.profiles[user_id]
        affection = profile.get("affection", {})

        if not affection:
            return ""

        level = affection.get("level", 0)
        stage = affection.get("relationship_stage", "stranger")
        username = profile.get("username", "this user")

        # Generate context based on relationship stage
        context_map = {
            "stranger": f"You just met {username}. Be polite but not overly familiar.",
            "acquaintance": f"You know {username} a bit. Be friendly and conversational.",
            "friend": f"{username} is your friend! Be warm, playful, and engaged.",
            "close_friend": f"{username} is a close friend! You care about them, joke around freely, and show genuine interest.",
            "best_friend": f"{username} is your BEST FRIEND! You're super close, totally comfortable together, inside jokes are common.",
        }

        base_context = context_map.get(stage, "")

        # Add emotional tone based on level
        if level >= 70:
            tone = "You genuinely enjoy talking to them."
        elif level >= 40:
            tone = "You appreciate their company."
        elif level >= 20:
            tone = "You're warming up to them."
        elif level <= 10:
            tone = "You're a bit cautious around them."
        else:
            tone = ""

        return f"{base_context} {tone}".strip()
