
## Task 5: Management Commands
- **Decision**: Created a dedicated Cog `cogs/rl_commands.py` instead of adding to `cogs/chat/commands.py` to keep RL management logic isolated and clean.
- **Decision**: Implemented `!rl_reset` with mandatory "confirm" argument and automatic backup creation (`.bak` file) before wiping data, ensuring safety.
- **Decision**: Used `rl_service.storage.save({})` to reset the storage file atomically, leveraging the existing persistence layer.
- **Decision**: Added `!rl_stats` to show active agent count and average epsilon, providing visibility into the learning process without exposing sensitive internal state.
