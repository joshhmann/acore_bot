"""Sound effects system for playing reaction sounds in voice channels."""
import logging
import re
import json
import asyncio
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timedelta
import discord

logger = logging.getLogger(__name__)


class SoundEffect:
    """Represents a single sound effect with triggers and settings."""

    def __init__(self, name: str, file_path: str, triggers: List[str], cooldown: int = 10, volume: float = 0.5):
        """Initialize sound effect.

        Args:
            name: Display name for the sound
            file_path: Path to audio file
            triggers: List of trigger words/phrases (supports regex)
            cooldown: Cooldown in seconds between plays
            volume: Volume level (0.0-1.0)
        """
        self.name = name
        self.file_path = Path(file_path)
        self.triggers = triggers
        self.cooldown = cooldown
        self.volume = volume
        self.last_played: Optional[datetime] = None

        # Compile regex patterns for triggers (case-insensitive)
        self.patterns = [re.compile(r'\b' + re.escape(t) + r'\b', re.IGNORECASE) for t in triggers]

    def matches(self, text: str) -> bool:
        """Check if text matches any trigger.

        Args:
            text: Text to check

        Returns:
            True if any trigger matches
        """
        return any(pattern.search(text) for pattern in self.patterns)

    def can_play(self) -> bool:
        """Check if sound effect is off cooldown.

        Returns:
            True if can play
        """
        if self.last_played is None:
            return True

        elapsed = (datetime.now() - self.last_played).total_seconds()
        return elapsed >= self.cooldown

    def mark_played(self):
        """Mark sound as played (starts cooldown)."""
        self.last_played = datetime.now()


class SoundEffectsService:
    """Service for playing sound effects in voice channels."""

    def __init__(self, effects_dir: str = "sound_effects", config_file: str = "sound_effects/config.json"):
        """Initialize sound effects service.

        Args:
            effects_dir: Directory containing sound files
            config_file: Path to config file
        """
        self.effects_dir = Path(effects_dir)
        self.config_file = Path(config_file)
        self.effects: List[SoundEffect] = []
        self.enabled = True
        self.global_volume = 0.5

        logger.info(f"Sound effects service initialized (dir: {self.effects_dir})")

    async def load_effects(self):
        """Load sound effects from config file."""
        if not self.config_file.exists():
            logger.warning(f"Config file not found: {self.config_file} - creating default")
            await self._create_default_config()

        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)

            self.enabled = config.get('enabled', True)
            self.global_volume = config.get('global_volume', 0.5)

            # Load each effect
            self.effects = []
            for effect_data in config.get('effects', []):
                name = effect_data['name']
                file_name = effect_data['file']
                file_path = self.effects_dir / file_name

                # Check if file exists
                if not file_path.exists():
                    logger.warning(f"Sound file not found: {file_path} - skipping effect '{name}'")
                    continue

                effect = SoundEffect(
                    name=name,
                    file_path=str(file_path),
                    triggers=effect_data.get('triggers', []),
                    cooldown=effect_data.get('cooldown', 10),
                    volume=effect_data.get('volume', 0.5)
                )

                self.effects.append(effect)
                logger.info(f"Loaded sound effect: {name} ({len(effect.triggers)} triggers)")

            logger.info(f"Loaded {len(self.effects)} sound effects")

        except Exception as e:
            logger.error(f"Error loading sound effects config: {e}")
            self.effects = []

    async def _create_default_config(self):
        """Create default config file with examples."""
        # Create directory if it doesn't exist
        self.effects_dir.mkdir(parents=True, exist_ok=True)

        default_config = {
            "enabled": True,
            "global_volume": 0.5,
            "effects": [
                {
                    "name": "Bruh",
                    "file": "bruh.mp3",
                    "triggers": ["bruh", "bro moment", "bruh moment"],
                    "cooldown": 10,
                    "volume": 0.6
                },
                {
                    "name": "Vine Boom",
                    "file": "vine_boom.mp3",
                    "triggers": ["boom", "vine boom"],
                    "cooldown": 5,
                    "volume": 0.5
                },
                {
                    "name": "Pipes Falling",
                    "file": "pipes_falling.mp3",
                    "triggers": ["whiff", "whiffed", "missed", "fail", "failed"],
                    "cooldown": 15,
                    "volume": 0.7
                },
                {
                    "name": "Perfect",
                    "file": "perfect.mp3",
                    "triggers": ["perfect", "nailed it", "ace"],
                    "cooldown": 12,
                    "volume": 0.5
                },
                {
                    "name": "Gottem",
                    "file": "gottem.mp3",
                    "triggers": ["got em", "gottem", "deez nuts"],
                    "cooldown": 20,
                    "volume": 0.6
                },
                {
                    "name": "Oh No",
                    "file": "oh_no.mp3",
                    "triggers": ["oh no", "uh oh"],
                    "cooldown": 8,
                    "volume": 0.5
                },
                {
                    "name": "Sad Trombone",
                    "file": "sad_trombone.mp3",
                    "triggers": ["rip", "sad", "oof"],
                    "cooldown": 10,
                    "volume": 0.5
                },
                {
                    "name": "Airhorn",
                    "file": "airhorn.mp3",
                    "triggers": ["airhorn", "hype", "lets go"],
                    "cooldown": 15,
                    "volume": 0.4
                }
            ]
        }

        with open(self.config_file, 'w') as f:
            json.dump(default_config, f, indent=2)

        logger.info(f"Created default config: {self.config_file}")

    def find_matching_effect(self, text: str) -> Optional[SoundEffect]:
        """Find first matching sound effect for text.

        Args:
            text: Text to check against triggers

        Returns:
            Matching SoundEffect or None
        """
        if not self.enabled:
            return None

        for effect in self.effects:
            if effect.matches(text) and effect.can_play():
                return effect

        return None

    async def play_effect(self, effect: SoundEffect, voice_client: discord.VoiceClient):
        """Play a sound effect in voice channel.

        Args:
            effect: Sound effect to play
            voice_client: Discord voice client
        """
        if not voice_client or not voice_client.is_connected():
            logger.warning("Cannot play sound effect - not connected to voice")
            return

        # Check if already playing something (don't interrupt TTS)
        if voice_client.is_playing():
            # Check if it's TTS - don't interrupt that
            source = voice_client.source if hasattr(voice_client, 'source') else None
            is_tts = getattr(source, '_is_tts', False) if source else False

            if is_tts:
                logger.debug(f"Skipping sound effect '{effect.name}' - TTS is playing")
                return

            # If music is playing, mix in the sound at lower volume
            # For now, we'll just skip to avoid complexity
            logger.debug(f"Skipping sound effect '{effect.name}' - audio already playing")
            return

        try:
            # Calculate final volume
            final_volume = effect.volume * self.global_volume

            # Create audio source
            audio_source = discord.FFmpegPCMAudio(str(effect.file_path))
            audio_source = discord.PCMVolumeTransformer(audio_source, volume=final_volume)

            # Mark as sound effect (not TTS, not music)
            audio_source._is_sound_effect = True

            # Play the sound
            voice_client.play(audio_source)
            effect.mark_played()

            logger.info(f"Playing sound effect: {effect.name}")

        except Exception as e:
            logger.error(f"Error playing sound effect '{effect.name}': {e}")

    async def reload_config(self):
        """Reload sound effects from config file."""
        logger.info("Reloading sound effects config")
        await self.load_effects()

    def get_available_effects(self) -> List[Dict]:
        """Get list of available effects.

        Returns:
            List of effect info dicts
        """
        return [
            {
                'name': effect.name,
                'triggers': effect.triggers,
                'cooldown': effect.cooldown,
                'ready': effect.can_play()
            }
            for effect in self.effects
        ]


# Global instance
_sound_effects_service: Optional[SoundEffectsService] = None


async def get_sound_effects_service() -> SoundEffectsService:
    """Get or create the global sound effects service.

    Returns:
        SoundEffectsService instance
    """
    global _sound_effects_service
    if _sound_effects_service is None:
        _sound_effects_service = SoundEffectsService()
        await _sound_effects_service.load_effects()
    return _sound_effects_service
