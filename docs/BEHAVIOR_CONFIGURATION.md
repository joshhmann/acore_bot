# Behavior Configuration (Naturalness and Behavior Settings)

This document describes the behavior-related configuration settings used by the bot. These settings live under the NaturalnessConfig class in config/features.py and are exported for backward compatibility as BEHAVIOR_* aliases in config/__init__.py.

## Summary of new settings
- REACTION_PROBABILITY (float, default 0.50)
- PROACTIVE_PROBABILITY (float, default 0.60)
- COOLDOWN_SECONDS (int, default 150)
- MOOD_SHIFT_MAX (float, default 0.20)

All of these can be overridden via environment variables following the project conventions. They are grouped under NATURALNESS in the codebase but are surfaced for backward compatibility under the BEHAVIOR_ namespace.

## Details

- REACTION_PROBABILITY
  - Description: Global probability that the bot reacts to mentions or triggers.
  - Type: float
  - Default: 0.50
  - Env var: REACTION_PROBABILITY
  - Usage: Influences how readily the bot responds when prompted or mentioned.

- PROACTIVE_PROBABILITY
  - Description: Base probability for proactive engagement by the bot (initiating messages).
  - Type: float
  - Default: 0.60
  - Env var: PROACTIVE_PROBABILITY
  - Usage: Affects how often the bot proactively initiates conversations or checks in with users.

- COOLDOWN_SECONDS
  - Description: Cooldown period between bot actions to avoid excessive activity.
  - Type: int
  - Default: 150
  - Env var: COOLDOWN_SECONDS
  - Usage: Shortens or extends cooldown between bot actions across interactions.

- MOOD_SHIFT_MAX
  - Description: Maximum mood intensity change per interaction.
  - Type: float
  - Default: 0.2
  - Env var: MOOD_SHIFT_MAX
  - Usage: Caps how much mood can shift in a single interaction to keep behavior stable.

## Backward-compatibility aliases
- BEHAVIOR_REACTION_PROBABILITY = naturalness.REACTION_PROBABILITY
- BEHAVIOR_PROACTIVE_PROBABILITY = naturalness.PROACTIVE_PROBABILITY
- BEHAVIOR_COOLDOWN_SECONDS = naturalness.COOLDOWN_SECONDS
- BEHAVIOR_MOOD_SHIFT_MAX = naturalness.MOOD_SHIFT_MAX

## Validation and quick check
- Example: print the value via Python:
  from config import BEHAVIOR_REACTION_PROBABILITY
  print(BEHAVIOR_REACTION_PROBABILITY)  # should print 0.5 by default

## Examples
- In a .env or environment, you can set:
  REACTION_PROBABILITY=0.75
  PROACTIVE_PROBABILITY=0.65
  COOLDOWN_SECONDS=120
  MOOD_SHIFT_MAX=0.25

This is sufficient to customize the bot's propensity to react, its proactive behavior, and how mood evolves over time.
