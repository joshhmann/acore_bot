# User Management System Workflow

This document describes the complete user management system in acore_bot, including user profiles, learning systems, relationship tracking, and personalized experience workflows.

## Overview

The user management system enables **personalized AI interactions** through **user profiling**, **relationship building**, **preference learning**, and **adaptive behavior** based on individual user patterns and history.

## Architecture

### Component Structure
```
services/discord/
└── profiles.py              # UserProfileService - core user management

services/memory/
├── conversation.py         # User conversation history
├── context_router.py       # Context-aware retrieval
└── rag.py                  # User-specific knowledge

cogs/
├── profile_commands.py     # User profile management commands
├── chat/main.py           # Integration with chat system
└── memory_commands.py     # Memory and history commands

data/
└── user_profiles/          # User profile storage
```

### Service Dependencies
```
User Management Dependencies:
├── Discord API             # User identity and permissions
├── Conversation History    # Interaction tracking
├── LLM Interface          # Learning and analysis
├── Persona System         # Relationship dynamics
├── Analytics              # User behavior metrics
├── Memory Systems         # Long-term data storage
└── Configuration          # User preferences
```

## User Profile System

### 1. UserProfileService Core
**File**: `services/discord/profiles.py:45-234`

#### 1.1 Profile Initialization
```python
class UserProfileService:
    """Manages user profiles, learning, and relationships."""

    def __init__(self, profiles_path: Path):
        self.profiles_path = profiles_path
        self.profiles = {}  # user_id -> UserProfile
        self.learning_enabled = Config.USER_PROFILES_AUTO_LEARN
        self.affection_enabled = Config.USER_AFFECTION_ENABLED

        # Learning configuration
        self.save_interval = Config.PROFILE_SAVE_INTERVAL_SECONDS
        self.last_save = {}

        # In-memory cache for active users
        self.active_profiles = set()
        self.last_access = {}

        # Load existing profiles
        self.load_profiles()

        # Start background save task
        if self.learning_enabled:
            asyncio.create_task(self._periodic_save())

async def get_user_profile(self, user_id: int) -> UserProfile:
    """Get or create user profile."""

    # 1. Check cache first
    if user_id in self.profiles:
        profile = self.profiles[user_id]
        self.last_access[user_id] = datetime.now()
        return profile

    # 2. Load from disk if not in cache
    profile_file = self.profiles_path / f"{user_id}.json"
    if profile_file.exists():
        profile = await self._load_profile_from_file(profile_file, user_id)
    else:
        # 3. Create new profile
        profile = UserProfile(
            user_id=user_id,
            username="",
            display_name="",
            preferences=UserPreferences(),
            personality_profile={},
            interaction_stats=InteractionStats(),
            relationship_metrics=RelationshipMetrics(),
            learning_data=LearningData()
        )

    # 4. Cache and return
    self.profiles[user_id] = profile
    self.active_profiles.add(user_id)
    self.last_access[user_id] = datetime.now()

    return profile

async def _load_profile_from_file(self, profile_file: Path, user_id: int) -> UserProfile:
    """Load user profile from JSON file."""
    try:
        with open(profile_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Reconstruct profile object
        profile = UserProfile(
            user_id=user_id,
            username=data.get('username', ''),
            display_name=data.get('display_name', ''),
            preferences=UserPreferences(**data.get('preferences', {})),
            personality_profile=data.get('personality_profile', {}),
            interaction_stats=InteractionStats(**data.get('interaction_stats', {})),
            relationship_metrics=RelationshipMetrics(**data.get('relationship_metrics', {})),
            learning_data=LearningData(**data.get('learning_data', {}))
        )

        return profile

    except Exception as e:
        logger.error(f"Error loading profile {profile_file}: {e}")
        # Return default profile on error
        return UserProfile(user_id=user_id)
```

#### 1.2 User Data Structures
```python
@dataclass
class UserProfile:
    """Comprehensive user profile data."""
    user_id: int
    username: str
    display_name: str
    preferences: 'UserPreferences'
    personality_profile: Dict[str, Any]
    interaction_stats: 'InteractionStats'
    relationship_metrics: 'RelationshipMetrics'
    learning_data: 'LearningData'
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class UserPreferences:
    """User preferences and settings."""
    preferred_personas: List[str] = field(default_factory=list)
    avoided_personas: List[str] = field(default_factory=list)
    preferred_response_length: str = "medium"  # short, medium, long
    preferred_response_style: str = "balanced"  # formal, casual, balanced
    voice_responses_enabled: bool = True
    auto_translation_enabled: bool = False
    content_filter_level: str = "standard"  # minimal, standard, strict
    timezone: str = "UTC"
    language: str = "en"
    notification_level: str = "important"  # all, important, none

@dataclass
class InteractionStats:
    """User interaction statistics."""
    total_messages: int = 0
    total_responses: int = 0
    average_response_length: float = 0.0
    most_active_hours: List[int] = field(default_factory=list)
    preferred_topics: List[str] = field(default_factory=list)
    command_usage: Dict[str, int] = field(default_factory=dict)
    session_duration_avg: float = 0.0
    last_interaction: Optional[datetime] = None

@dataclass
class RelationshipMetrics:
    """User-bot relationship measurements."""
    affection_level: float = 0.0  # -10 (dislike) to +10 (love)
    trust_level: float = 0.0     # 0 (neutral) to 10 (complete trust)
    familiarity_score: float = 0.0  # 0 (stranger) to 10 (close friend)
    rapport_score: float = 0.0       # 0 (no rapport) to 10 (strong rapport)
    shared_interests: List[str] = field(default_factory=list)
    conflict_history: List[Dict] = field(default_factory=list)
    positive_interaction_ratio: float = 0.0

@dataclass
class LearningData:
    """Machine learning data about user."""
    personality_traits: Dict[str, float] = field(default_factory=dict)
    communication_style: Dict[str, Any] = field(default_factory=dict)
    topic_interests: Dict[str, float] = field(default_factory=dict)
    emotional_patterns: Dict[str, Any] = field(default_factory=dict)
    response_preferences: Dict[str, Any] = field(default_factory=dict)
    behavior_patterns: Dict[str, Any] = field(default_factory=dict)
    adaptation_history: List[Dict] = field(default_factory=list)
```

### 2. Learning and Adaptation
**File**: `services/discord/profiles.py:235-389`

#### 2.1 Conversation Learning
```python
async def learn_from_conversation(
    self,
    user_id: int,
    username: str,
    user_message: str,
    bot_response: str
):
    """Learn from a conversation interaction."""

    if not self.learning_enabled:
        return

    try:
        # 1. Get user profile
        profile = await self.get_user_profile(user_id)

        # 2. Update basic info
        profile.username = username
        profile.last_updated = datetime.now()

        # 3. Analyze user message for personality traits
        await self._analyze_personality_traits(profile, user_message)

        # 4. Update communication style
        await self._update_communication_style(profile, user_message, bot_response)

        # 5. Extract topic interests
        await self._extract_topic_interests(profile, user_message)

        # 6. Update interaction statistics
        await self._update_interaction_stats(profile, user_message, bot_response)

        # 7. Adapt response preferences
        await self._adapt_response_preferences(profile, user_message, bot_response)

        # 8. Store learning event
        learning_event = {
            'timestamp': datetime.now().isoformat(),
            'user_message': user_message,
            'bot_response': bot_response,
            'type': 'conversation'
        }
        profile.learning_data.adaptation_history.append(learning_event)

        # 9. Keep history bounded
        if len(profile.learning_data.adaptation_history) > 100:
            profile.learning_data.adaptation_history = profile.learning_data.adaptation_history[-80:]

    except Exception as e:
        logger.error(f"Error learning from conversation for user {user_id}: {e}")

async def _analyze_personality_traits(self, profile: UserProfile, message: str):
    """Analyze message for personality trait indicators."""

    try:
        # Use LLM to analyze personality traits
        analysis_prompt = f"""
        Analyze this message for personality traits:
        Message: "{message}"

        Rate these traits on a scale of 0.0 to 1.0:
        - openness: willingness to try new things and be creative
        - conscientiousness: organization and responsibility
        - extraversion: social energy and assertiveness
        - agreeableness: cooperation and kindness
        - neuroticism: emotional stability and anxiety
        - formality: preference for formal vs casual language
        - humor_tendency: likelihood to use humor
        - curiosity: interest in learning and exploration

        Return JSON format only.
        """

        # This would use the LLM service
        traits_result = await self._analyze_with_llm(analysis_prompt)

        if traits_result:
            # Update personality traits with moving average
            current_traits = profile.learning_data.personality_traits
            for trait, value in traits_result.items():
                if isinstance(value, (int, float)) and 0.0 <= value <= 1.0:
                    if trait in current_traits:
                        # Weighted average (70% old, 30% new)
                        current_traits[trait] = current_traits[trait] * 0.7 + value * 0.3
                    else:
                        current_traits[trait] = value

    except Exception as e:
        logger.error(f"Error analyzing personality traits: {e}")

async def _extract_topic_interests(self, profile: UserProfile, message: str):
    """Extract and update topic interests from user message."""

    try:
        # Use keyword extraction and LLM analysis
        extraction_prompt = f"""
        Extract main topics and interests from this message:
        "{message}"

        List up to 5 topics with relevance scores (0.0 to 1.0):
        Format: {{"topic_name": score, ...}}
        """

        topics_result = await self._analyze_with_llm(extraction_prompt)

        if topics_result:
            current_interests = profile.learning_data.topic_interests

            for topic, relevance in topics_result.items():
                if isinstance(relevance, (int, float)) and 0.0 <= relevance <= 1.0:
                    if topic in current_interests:
                        # Increase interest with decay
                        current_interests[topic] = min(1.0,
                            current_interests[topic] * 0.9 + relevance * 0.3
                        )
                    else:
                        current_interests[topic] = relevance

            # Decay all interests slightly to prioritize recent ones
            for topic in list(current_interests.keys()):
                current_interests[topic] *= 0.995

                # Remove very low interests
                if current_interests[topic] < 0.05:
                    del current_interests[topic]

    except Exception as e:
        logger.error(f"Error extracting topic interests: {e}")
```

#### 2.2 Relationship Building
```python
async def update_affection(
    self,
    user_id: int,
    message: discord.Message,
    bot_response: str
):
    """Update affection and relationship metrics."""

    if not self.affection_enabled:
        return

    try:
        profile = await self.get_user_profile(user_id)
        metrics = profile.relationship_metrics

        # 1. Analyze message sentiment
        sentiment_score = await self._analyze_sentiment(message.content)

        # 2. Analyze interaction quality
        interaction_quality = await self._analyze_interaction_quality(
            message.content, bot_response
        )

        # 3. Calculate affection change
        affection_change = 0.0

        # Positive sentiment increases affection
        if sentiment_score > 0.2:
            affection_change += sentiment_score * 0.5

        # Negative sentiment decreases affection (less than positive increases)
        if sentiment_score < -0.2:
            affection_change += sentiment_score * 0.3

        # High-quality interactions increase affection
        if interaction_quality > 0.7:
            affection_change += (interaction_quality - 0.7) * 2.0

        # Special interactions
        if "thank" in message.content.lower() or "appreciate" in message.content.lower():
            affection_change += 1.0
        elif "love" in message.content.lower() or "favorite" in message.content.lower():
            affection_change += 2.0
        elif "hate" in message.content.lower() or "dislike" in message.content.lower():
            affection_change -= 1.5

        # 4. Apply affection change with bounds
        metrics.affection_level = max(-10.0, min(10.0,
            metrics.affection_level + affection_change))

        # 5. Update trust based on consistency
        await self._update_trust(profile, message, bot_response)

        # 6. Update familiarity score
        await self._update_familiarity(profile)

        # 7. Update rapport score
        await self._update_rapport(profile, interaction_quality)

        # 8. Calculate positive interaction ratio
        await self._update_interaction_ratio(profile)

    except Exception as e:
        logger.error(f"Error updating affection for user {user_id}: {e}")

async def _update_trust(self, profile: UserProfile, user_message: discord.Message, bot_response: str):
    """Update trust level based on interaction consistency and quality."""

    metrics = profile.relationship_metrics

    # Trust increases with:
    # - Consistent positive interactions
    # - User sharing personal information
    # - User asking for advice or help
    # - Long, thoughtful messages

    trust_change = 0.0

    # Check for trust indicators
    message_lower = user_message.content.lower()

    # Sharing personal info
    trust_indicators = [
        "my name is", "i am from", "i work at", "i study",
        "i think", "i feel", "i believe", "my opinion",
        "can you help", "i need advice", "what do you think"
    ]

    for indicator in trust_indicators:
        if indicator in message_lower:
            trust_change += 0.2
            break  # Only count once per message

    # Message length (longer messages often indicate more trust)
    if len(user_message.content) > 100:
        trust_change += 0.1
    elif len(user_message.content) > 300:
        trust_change += 0.3

    # Apply trust change with decay
    metrics.trust_level = max(0.0, min(10.0,
        metrics.trust_level * 0.995 + trust_change))
```

### 3. Personalized Context Generation
**File**: `services/discord/profiles.py:390-456`

#### 3.1 User Context for LLM
```python
async def get_user_context(self, user_id: int) -> str:
    """Generate personalized context for LLM about this user."""

    try:
        profile = await self.get_user_profile(user_id)

        context_parts = []

        # 1. Basic user info
        if profile.display_name:
            context_parts.append(f"User: {profile.display_name}")

        # 2. Relationship status
        if self.affection_enabled:
            metrics = profile.relationship_metrics
            if metrics.affection_level > 5.0:
                context_parts.append("Relationship: Close friend")
            elif metrics.affection_level > 2.0:
                context_parts.append("Relationship: Friendly acquaintance")
            elif metrics.affection_level < -2.0:
                context_parts.append("Relationship: Strained")
            else:
                context_parts.append("Relationship: Neutral")

        # 3. Communication preferences
        prefs = profile.preferences
        style_notes = []

        if prefs.preferred_response_length == "short":
            style_notes.append("prefers brief responses")
        elif prefs.preferred_response_length == "long":
            style_notes.append("appreciates detailed responses")

        if prefs.preferred_response_style == "formal":
            style_notes.append("prefers formal communication")
        elif prefs.preferred_response_style == "casual":
            style_notes.append("enjoys casual conversation")

        if style_notes:
            context_parts.append(f"Communication style: {', '.join(style_notes)}")

        # 4. Personality insights
        if profile.learning_data.personality_traits:
            traits = profile.learning_data.personality_traits

            trait_descriptions = []
            if traits.get('extraversion', 0) > 0.7:
                trait_descriptions.append("outgoing")
            elif traits.get('extraversion', 0) < 0.3:
                trait_descriptions.append("reserved")

            if traits.get('openness', 0) > 0.7:
                trait_descriptions.append("open to new ideas")
            elif traits.get('openness', 0) < 0.3:
                trait_descriptions.append("prefers familiar topics")

            if traits.get('humor_tendency', 0) > 0.6:
                trait_descriptions.append("enjoys humor")

            if trait_descriptions:
                context_parts.append(f"Personality: {', '.join(trait_descriptions)}")

        # 5. Recent interests
        if profile.learning_data.topic_interests:
            interests = sorted(
                profile.learning_data.topic_interests.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]  # Top 5 interests

            if interests:
                interest_list = [topic for topic, score in interests if score > 0.3]
                if interest_list:
                    context_parts.append(f"Interests: {', '.join(interest_list)}")

        # 6. Preferred personas
        if prefs.preferred_personas:
            context_parts.append(f"Preferred characters: {', '.join(prefs.preferred_personas)}")

        # 7. Last interaction context
        if profile.interaction_stats.last_interaction:
            time_since = datetime.now() - profile.interaction_stats.last_interaction
            if time_since.days > 0:
                context_parts.append(f"Last interaction: {time_since.days} days ago")
            else:
                hours_ago = time_since.seconds // 3600
                if hours_ago > 0:
                    context_parts.append(f"Last interaction: {hours_ago} hours ago")

        return "\n".join(context_parts) if context_parts else ""

    except Exception as e:
        logger.error(f"Error generating user context for {user_id}: {e}")
        return ""

async def get_affection_context(self, user_id: int) -> str:
    """Generate affection-based context for persona interactions."""

    if not self.affection_enabled:
        return ""

    try:
        profile = await self.get_user_profile(user_id)
        metrics = profile.relationship_metrics

        if metrics.affection_level > 7.0:
            return ("This user is a very close friend. You can be warm, affectionate, "
                   "and use informal language. Share personal feelings and show genuine care.")
        elif metrics.affection_level > 4.0:
            return ("This user is a good friend. Be friendly and warm, but maintain "
                   "appropriate boundaries. You can use informal language and show interest "
                   "in their life.")
        elif metrics.affection_level > 1.0:
            return ("This user is friendly with you. Maintain a pleasant, balanced tone. "
                   "Be helpful and engaging but not overly familiar.")
        elif metrics.affection_level < -2.0:
            return ("This user has negative feelings toward you. Be polite and professional, "
                   "but don't try to force friendliness. Focus on being helpful and respectful.")
        else:
            return ("This user is a neutral acquaintance. Maintain a friendly but reserved "
                   "tone. Be helpful and appropriate.")

    except Exception as e:
        logger.error(f"Error generating affection context for {user_id}: {e}")
        return ""
```

### 4. Profile Management Commands
**File**: `cogs/profile_commands.py:34-189`

#### 4.1 Profile Viewing
```python
@app_commands.command(name="profile", description="View your user profile")
async def view_profile(self, interaction: discord.Interaction):
    """Display user's profile information."""
    await interaction.response.defer(thinking=True)

    try:
        user_id = interaction.user.id
        profile_service = self.bot.profile_service
        profile = await profile_service.get_user_profile(user_id)

        # Create profile embed
        embed = discord.Embed(
            title=f"👤 {interaction.user.display_name}'s Profile",
            color=discord.Color.blue()
        )

        # Basic info
        embed.add_field(
            name="📊 Account Info",
            value=f"**User ID:** {user_id}\n"
                  f"**Joined:** {profile.created_at.strftime('%Y-%m-%d')}\n"
                  f"**Total Messages:** {profile.interaction_stats.total_messages}",
            inline=False
        )

        # Relationship metrics
        if Config.USER_AFFECTION_ENABLED:
            metrics = profile.relationship_metrics
            affection_emoji = "❤️" if metrics.affection_level > 0 else "💔"
            embed.add_field(
                name=f"{affection_emoji} Relationship",
                value=f"**Affection:** {metrics.affection_level:.1f}/10\n"
                      f"**Trust:** {metrics.trust_level:.1f}/10\n"
                      f"**Familiarity:** {metrics.familiarity_score:.1f}/10",
                inline=True
            )

        # Communication preferences
        prefs = profile.preferences
        embed.add_field(
            name="💬 Preferences",
            value=f"**Style:** {prefs.preferred_response_style}\n"
                  f"**Length:** {prefs.preferred_response_length}\n"
                  f"**Voice:** {'Enabled' if prefs.voice_responses_enabled else 'Disabled'}",
            inline=True
        )

        # Top interests
        if profile.learning_data.topic_interests:
            top_interests = sorted(
                profile.learning_data.topic_interests.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]

            interest_list = [
                f"**{topic}**: {score:.2f}"
                for topic, score in top_interests
                if score > 0.3
            ]

            if interest_list:
                embed.add_field(
                    name="🎯 Top Interests",
                    value="\n".join(interest_list),
                    inline=False
                )

        # Personality traits
        if profile.learning_data.personality_traits:
            traits = profile.learning_data.personality_traits
            trait_list = []

            trait_names = {
                'openness': 'Openness',
                'conscientiousness': 'Conscientiousness',
                'extraversion': 'Extraversion',
                'agreeableness': 'Agreeableness',
                'formality': 'Formality',
                'humor_tendency': 'Humor'
            }

            for trait_key, trait_name in trait_names.items():
                if trait_key in traits:
                    value = traits[trait_key]
                    bar_length = int(value * 10)
                    bar = "█" * bar_length + "░" * (10 - bar_length)
                    trait_list.append(f"**{trait_name}:** {bar} {value:.2f}")

            if trait_list:
                embed.add_field(
                    name="🧠 Personality",
                    value="\n".join(trait_list),
                    inline=False
                )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(
            f"❌ Error loading profile: {e}",
            ephemeral=True
        )

@app_commands.command(name="preferences", description="Manage your preferences")
@app_commands.describe(
    response_length="Preferred response length",
    response_style="Preferred communication style",
    voice_responses="Enable voice responses"
)
async def manage_preferences(
    self,
    interaction: discord.Interaction,
    response_length: Optional[str] = None,
    response_style: Optional[str] = None,
    voice_responses: Optional[bool] = None
):
    """Update user preferences."""
    await interaction.response.defer(thinking=True)

    try:
        profile_service = self.bot.profile_service
        profile = await profile_service.get_user_profile(interaction.user.id)
        prefs = profile.preferences

        changes = []

        # Update preferences
        if response_length:
            if response_length in ["short", "medium", "long"]:
                prefs.preferred_response_length = response_length
                changes.append(f"Response length: {response_length}")
            else:
                await interaction.followup.send(
                    "❌ Response length must be: short, medium, or long",
                    ephemeral=True
                )
                return

        if response_style:
            if response_style in ["formal", "casual", "balanced"]:
                prefs.preferred_response_style = response_style
                changes.append(f"Response style: {response_style}")
            else:
                await interaction.followup.send(
                    "❌ Response style must be: formal, casual, or balanced",
                    ephemeral=True
                )
                return

        if voice_responses is not None:
            prefs.voice_responses_enabled = voice_responses
            changes.append(f"Voice responses: {'Enabled' if voice_responses else 'Disabled'}")

        if changes:
            profile.last_updated = datetime.now()

            embed = discord.Embed(
                title="✅ Preferences Updated",
                description="\n".join(f"• {change}" for change in changes),
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(
                "No changes specified. Use the command options to update preferences.",
                ephemeral=True
            )

    except Exception as e:
        await interaction.followup.send(
            f"❌ Error updating preferences: {e}",
            ephemeral=True
        )
```

## Configuration

### User Management Settings
```bash
# Profile System
USER_PROFILES_ENABLED=true                      # Enable user profiles
USER_PROFILES_PATH=./data/user_profiles         # Profile storage location
USER_PROFILES_AUTO_LEARN=true                   # AI-powered learning
USER_CONTEXT_IN_CHAT=true                       # Include user context in responses

# Relationship System
USER_AFFECTION_ENABLED=true                     # Enable affection tracking
USER_AFFECTION_DECAY_RATE=0.01                 # Daily affection decay

# Learning Configuration
PROFILE_SAVE_INTERVAL_SECONDS=60               # Auto-save interval
LEARNING_BATCH_SIZE=10                          # Process learning in batches
MAX_LEARNING_HISTORY=100                        # Maximum learning events stored

# Privacy and Security
PROFILE_RETENTION_DAYS=365                      # How long to keep inactive profiles
ANONYMIZED_TELEMETRY=false                      # Collect anonymous usage data
DATA_ENCRYPTION_ENABLED=false                   # Encrypt sensitive profile data
```

## Integration Points

### With Chat System
- **Personalized Context**: User profiles inform response generation
- **Relationship Dynamics**: Affection levels affect persona behavior
- **Preference Integration**: User preferences applied to responses

### With Persona System
- **Character Preferences**: Users can prefer certain personas
- **Relationship Building**: Different relationships with different personas
- **Personalized Interactions**: Personas adapt to individual users

### With Memory System
- **Conversation History**: User-specific conversation tracking
- **Learning Data**: Integration with long-term memory
- **Context Retrieval**: Personalized context for conversations

## Performance Considerations

### 1. Profile Caching
- **Active User Cache**: Frequently accessed profiles kept in memory
- **LRU Eviction**: Inactive profiles automatically unloaded
- **Batch Operations**: Multiple profile operations processed together

### 2. Learning Optimization
- **Async Processing**: Learning tasks run in background
- **Batch Analysis**: Multiple messages analyzed together
- **Selective Learning**: Only learn from quality interactions

### 3. Storage Efficiency
- **Incremental Updates**: Only save changed profile data
- **Compression**: Profile data compressed for storage
- **Cleanup Tasks**: Automatic removal of old/unused data

## Security Considerations

### 1. Data Privacy
- **User Consent**: Profile creation requires implicit consent
- **Data Minimization**: Only collect necessary user data
- **Right to Deletion**: Users can request profile deletion

### 2. Access Control
- **User Isolation**: Users can only access their own profiles
- **Admin Oversight**: Admin access for troubleshooting
- **Audit Logging**: All profile accesses logged

### 3. Data Protection
- **Encryption**: Sensitive data encrypted at rest
- **Secure Storage**: Profile files with proper permissions
- **Backup Security**: Encrypted backups of profile data

## Common Issues and Troubleshooting

### 1. Profile Not Loading
```python
# Check profile file existence
profile_file = Path("./data/user_profiles") / f"{user_id}.json"
print(profile_file.exists())

# Verify profile directory permissions
import os
print(os.access("./data/user_profiles", os.R_OK | os.W_OK))

# Check profile cache
profile_service = bot.profile_service
print(user_id in profile_service.profiles)
```

### 2. Learning Not Working
```bash
# Verify learning is enabled
echo $USER_PROFILES_AUTO_LEARN

# Check LLM service status
python -c "from services.llm.ollama import OllamaService; print(OllamaService().is_available())"

# Review learning logs
grep "learning" logs/bot.log | tail -10
```

### 3. Relationship Scores Not Updating
```python
# Check affection system
print(Config.USER_AFFECTION_ENABLED)

# Verify interaction analysis
profile = await profile_service.get_user_profile(user_id)
print(profile.relationship_metrics.affection_level)

# Check sentiment analysis
await profile_service._analyze_sentiment("I love this bot!")
```

## Files Reference

| File | Purpose | Key Functions |
|-------|---------|------------------|
| `services/discord/profiles.py` | UserProfileService - core user management |
| `cogs/profile_commands.py` | User profile management commands |
| `cogs/memory_commands.py` | Memory and history commands |
| `services/memory/context_router.py` | Context-aware information retrieval |
| `services/memory/conversation.py` | User conversation history |

---

**Last Updated**: 2025-12-16
**Version**: 1.0