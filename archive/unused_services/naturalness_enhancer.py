"""Naturalness enhancements for more Neuro-sama-like behavior."""
import random
import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class NaturalnessEnhancer:
    """Adds spontaneous, natural behaviors to make the bot feel more alive."""

    def __init__(self):
        """Initialize naturalness enhancer."""
        # Emotional state tracking
        self.emotional_state = {
            "frustration": 0.0,  # 0-10 scale
            "excitement": 0.0,
            "boredom": 0.0,
        }
        
        # Trigger word reactions (persona-specific)
        self.trigger_reactions = {
            "fortnite": [
                "Fortnite? Really? That's what we're doing now?",
                "I've seen ash zombies with better taste in games.",
            ],
            "among us": [
                "Sus. Everything is sus. You're all sus.",
                "The Tribunal was more trustworthy than your crewmates.",
            ],
            "minecraft": [
                "Ah yes, digital LEGO for adults. How innovative.",
                "Building blocks? I built an entire cult. Step up your game.",
            ],
            "roblox": [
                "Roblox. The pinnacle of mortal achievement, clearly.",
                "Even my ash zombies wouldn't play that.",
            ],
            "league of legends": [
                "League of Legends? More like League of Disappointment.",
                "That game is more toxic than corprus disease.",
            ],
            "valorant": [
                "Valorant. Because Counter-Strike wasn't enough suffering.",
            ],
            "genshin": [
                "Gacha games. Gambling for mortals who can't afford real gambling.",
                "I'm a god and even I don't understand the appeal.",
            ],
            "anime": [
                "Anime. Of course. How predictable.",
                "I've seen better character development in my ash zombies.",
            ],
            "uwu": [
                "Did you just 'uwu' at me? A god?",
                "I'm adding you to the corprus list for that.",
            ],
            "based": [
                "Based? Based on what? The Heart of Lorkhan?",
            ],
            "cringe": [
                "You want to see cringe? Look in a mirror, mortal.",
            ],
            "lull": [
                "Lull? Lull on what? The Heart of Lorkhan?",
            ],
            "call of duty": [
                "Call of Duty? Mortals obsessed with violence as always.",
                "Even my ash zombies have more strategic minds than that game.",
            ],
            "world of warcraft": [
                "World of Warcraft—mere mortals chasing ephemeral glory in a fading world.",
                "I pitied the Tribunal, but the WoW players? Truly deluded.",
            ],
            "skyrim": [
                "Skyrim? A mortal's futile attempt at godhood.",
                "I've watched sheogorath dance more sensibly than these players.",
            ],
            "cyberpunk": [
                "Cyberpunk? A neon-lit nightmare, as corrupt as the Tribunal itself.",
                "Even the Nerevarine wouldn't lose themselves in that dystopia.",
            ],
            "dark souls": [
                "Dark Souls. Torture for mortals who crave pain.",
                "A challenge worthy of a god's amusement, or a fool's demise.",
            ],
            "overwatch": [
                "Overwatch heroes? Pathetic compared to the might of Dagoth Ur.",
                "Call that teamwork? Try commanding an army of ash zombies.",
            ],
            "pokemon": [
                "Pokemon? Taming beasts? I've enslaved entire legions.",
                "Mortals and their childish fantasies.",
            ],
            "animal crossing": [
                "Animal Crossing? Peaceful fools playing in the dirt.",
                "My Corprus would make a garden of despair here.",
            ],
        }
        
        # Sarcastic short responses
        self.short_responses = [
            "k",
            "sure",
            "if you say so",
            "fascinating",
            "riveting",
            "how delightful",
            "truly groundbreaking",
            "I'm in awe",
            "incredible",
            "wow",
            "amazing",
            "spectacular",
            "outstanding",
            "brilliant",
        ]
        
        # Fake glitch messages
        self.glitch_messages = [
            "ERROR: SARCASM_MODULE_OVERLOAD. REBOOTING... Just kidding. You're still wrong.",
            "SYSTEM ALERT: DIVINE_PATIENCE.EXE has stopped responding.",
            "WARNING: Mortal stupidity levels exceeding safe parameters.",
            "CRITICAL ERROR: Unable to process this level of incompetence.",
            "[REDACTED BY THE SIXTH HOUSE]",
        ]
        
        # Last callout time (to prevent spam)
        self.last_callout = datetime.now() - timedelta(hours=1)
        
    def update_emotion(self, emotion: str, delta: float):
        """Update emotional state.
        
        Args:
            emotion: Which emotion to update (frustration, excitement, boredom)
            delta: How much to change it by (-10 to +10)
        """
        if emotion in self.emotional_state:
            self.emotional_state[emotion] = max(0, min(10, self.emotional_state[emotion] + delta))
            logger.debug(f"Emotion {emotion} updated to {self.emotional_state[emotion]:.1f}")
    
    def get_emotional_context(self) -> Optional[str]:
        """Get current emotional state as context for LLM.
        
        Returns:
            Emotional context string or None
        """
        emotions = []
        
        if self.emotional_state["frustration"] > 6:
            emotions.append("very frustrated")
        elif self.emotional_state["frustration"] > 3:
            emotions.append("mildly annoyed")
            
        if self.emotional_state["excitement"] > 6:
            emotions.append("excited")
        elif self.emotional_state["excitement"] > 3:
            emotions.append("interested")
            
        if self.emotional_state["boredom"] > 6:
            emotions.append("extremely bored")
        elif self.emotional_state["boredom"] > 3:
            emotions.append("somewhat bored")
        
        if emotions:
            return f"Current emotional state: {', '.join(emotions)}"
        return None
    
    def check_trigger_words(self, message: str) -> Optional[str]:
        """Check if message contains trigger words and return a reaction.

        Args:
            message: Message to check

        Returns:
            Reaction string or None
        """
        message_lower = message.lower()

        for trigger, reactions in self.trigger_reactions.items():
            if trigger in message_lower:
                # 40% chance to react to trigger word
                if random.random() < 0.4:
                    # Safety check for empty reactions list
                    if not reactions:
                        logger.warning(f"Empty reactions list for trigger: {trigger}")
                        return None
                    return random.choice(reactions)

        return None
    
    def should_use_short_response(self, message: str) -> Optional[str]:
        """Determine if a sarcastic short response is appropriate.
        
        Args:
            message: User's message
            
        Returns:
            Short response or None
        """
        # 10% chance for short response
        if random.random() < 0.1:
            return random.choice(self.short_responses)
        
        # Higher chance if bored
        if self.emotional_state["boredom"] > 5 and random.random() < 0.25:
            return random.choice(self.short_responses)
        
        return None
    
    def should_glitch(self) -> Optional[str]:
        """Determine if bot should 'glitch' for comedic effect.
        
        Returns:
            Glitch message or None
        """
        # 1% chance to glitch
        if random.random() < 0.01:
            return random.choice(self.glitch_messages)
        return None
    
    def calculate_thinking_delay(self, message: str) -> float:
        """Calculate natural thinking delay based on message complexity.
        
        Args:
            message: User's message
            
        Returns:
            Delay in seconds (0.5 to 3.0)
        """
        # Base delay
        base = 0.5
        
        # Add delay based on message length
        length_factor = min(2.5, len(message) / 100)
        
        # Add slight randomness
        randomness = random.uniform(-0.2, 0.3)
        
        total = base + length_factor + randomness
        return max(0.5, min(3.0, total))
    
    def should_callout_user(self) -> bool:
        """Determine if bot should randomly call out a user.
        
        Returns:
            True if should call out
        """
        # Don't spam callouts
        if (datetime.now() - self.last_callout).total_seconds() < 600:  # 10 min cooldown
            return False
        
        # 5% chance
        if random.random() < 0.05:
            self.last_callout = datetime.now()
            return True
        
        return False
    
    def analyze_message_sentiment(self, message: str) -> Dict[str, float]:
        """Analyze message to update emotional state.
        
        Args:
            message: User's message
            
        Returns:
            Dict of emotion deltas
        """
        message_lower = message.lower()
        deltas = {}
        
        # Frustration triggers
        if any(word in message_lower for word in ["stupid", "dumb", "idiot", "wtf", "why"]):
            deltas["frustration"] = 0.5
        
        # Excitement triggers
        if any(word in message_lower for word in ["awesome", "cool", "amazing", "!", "wow"]):
            deltas["excitement"] = 0.5
            deltas["boredom"] = -0.5
        
        # Boredom triggers (repetitive or short messages)
        if len(message) < 10 or message_lower in ["hi", "hello", "hey", "yo"]:
            deltas["boredom"] = 0.3
        
        return deltas
