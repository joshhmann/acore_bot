"""User Profile service for learning about Discord users over time."""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import aiofiles

logger = logging.getLogger(__name__)


class UserProfileService:
    """Service for managing user profiles and memories.

    Learns about users through conversations and can:
    - Store facts about users (interests, preferences, personality traits)
    - Remember past interactions and events
    - Provide user context to the AI for personalized responses
    - Allow bot to reference users by their characteristics
    """

    def __init__(self, profiles_dir: Path, ollama_service=None):
        """Initialize user profile service.

        Args:
            profiles_dir: Directory to store user profile JSON files
            ollama_service: Optional OllamaService for AI-powered profile extraction
        """
        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache of loaded profiles
        self.profiles: Dict[int, Dict] = {}

        # AI service for automatic profile learning
        self.ollama = ollama_service

        logger.info(f"User profile service initialized (dir: {self.profiles_dir})")

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
            return profile

        # Load from disk
        try:
            async with aiofiles.open(profile_file, "r", encoding="utf-8") as f:
                content = await f.read()
                profile = json.loads(content)
                self.profiles[user_id] = profile
                logger.debug(f"Loaded profile for user {user_id}")
                return profile
        except Exception as e:
            logger.error(f"Failed to load profile for user {user_id}: {e}")
            profile = self._create_default_profile(user_id)
            self.profiles[user_id] = profile
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
        """Save a user's profile to disk.

        Args:
            user_id: Discord user ID

        Returns:
            True if successful
        """
        if user_id not in self.profiles:
            logger.warning(f"Attempted to save non-existent profile for user {user_id}")
            return False

        profile = self.profiles[user_id]
        profile["last_updated"] = datetime.utcnow().isoformat()

        try:
            profile_file = self._get_profile_file(user_id)
            async with aiofiles.open(profile_file, "w", encoding="utf-8") as f:
                await f.write(json.dumps(profile, indent=2))
            logger.debug(f"Saved profile for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save profile for user {user_id}: {e}")
            return False

    async def add_fact(self, user_id: int, fact: str, source: str = "conversation") -> bool:
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

    async def set_relationship(self, user_id: int, other_user_id: int, relationship: str) -> bool:
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
            facts_str = "; ".join([f["fact"] for f in recent_facts])
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
            context = context[:max_length - 3] + "..."

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

        # Load all profiles
        for profile_file in self.profiles_dir.glob("user_*.json"):
            try:
                async with aiofiles.open(profile_file, "r", encoding="utf-8") as f:
                    content = await f.read()
                    profile = json.loads(content)

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

        for profile_file in self.profiles_dir.glob("user_*.json"):
            try:
                async with aiofiles.open(profile_file, "r", encoding="utf-8") as f:
                    content = await f.read()
                    profile = json.loads(content)

                    user_interests = [i.lower() for i in profile.get("interests", [])]
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
            traits = ", ".join(profile["traits"][:3]) if profile["traits"] else "unknown"
            interests = ", ".join(profile["interests"][:3]) if profile["interests"] else "none"

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

    async def learn_from_conversation(self, user_id: int, username: str, user_message: str, bot_response: str) -> bool:
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
            logger.warning("Cannot learn from conversation - no Ollama service provided")
            return False

        try:
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
  "memorable_quote": null  // If user said something genuinely funny/clever/interesting, include it. Otherwise null.
}}

RULES:
- Only include information that is clearly present in this conversation
- Be conservative - if unsure, don't include it
- Traits should be adjectives describing personality
- Interests should be nouns/topics
- Facts should be complete statements
- memorable_quote: Only for genuinely funny, witty, or uniquely interesting statements
- If nothing can be extracted, return empty arrays/objects
- Return ONLY valid JSON, no other text

JSON:"""

            # Get AI extraction
            response = await self.ollama.chat(
                messages=[{"role": "user", "content": extraction_prompt}],
                system_prompt="You are a precise information extraction system. Return only valid JSON.",
                temperature=0.3  # Lower temperature for more consistent extraction
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
                if trait and trait.lower() not in [t.lower() for t in profile["traits"]]:
                    profile["traits"].append(trait)
                    updated = True

            # Add new interests (avoid duplicates)
            for interest in extracted.get("interests", []):
                if interest and interest.lower() not in [i.lower() for i in profile["interests"]]:
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

            # Save if anything was learned
            if updated:
                await self.save_profile(user_id)
                logger.info(f"Learned new information about user {user_id} from conversation")

            return updated

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI extraction response: {e}")
            logger.debug(f"Response was: {response}")
            return False
        except Exception as e:
            logger.error(f"Failed to learn from conversation for user {user_id}: {e}")
            return False

    async def update_affection(self, user_id: int, message: str, bot_response: str) -> dict:
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
  "affection_change": -5 to +5  // How much this should change affection
}}

RULES:
- positive: User is friendly, engaging, appreciative
- negative: User is rude, dismissive, mean
- neutral: Normal conversation
- is_funny: User made a genuinely funny joke/comment
- is_interesting: Conversation was engaging/thought-provoking
- affection_change: Suggest change (-5 to +5)

JSON:"""

            response = await self.ollama.chat(
                messages=[{"role": "user", "content": sentiment_prompt}],
                system_prompt="You are a sentiment analyzer. Return only valid JSON.",
                temperature=0.3
            )

            # Parse response
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            sentiment_data = json.loads(response)

            # Update affection
            affection_change = sentiment_data.get("affection_change", 0)
            profile["affection"]["level"] = max(0, min(100, profile["affection"]["level"] + affection_change))

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
