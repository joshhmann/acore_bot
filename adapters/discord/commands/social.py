"""Runtime-backed social status commands for Discord."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands


logger = logging.getLogger(__name__)


class SocialCommandsCog(commands.Cog):
    """Thin Discord surface over runtime social state."""

    def __init__(self, bot: commands.Bot, runtime) -> None:
        self.bot = bot
        self.runtime = runtime

    def _context(self, interaction: discord.Interaction) -> dict[str, str | dict]:
        room_id = str(getattr(interaction.channel, "id", "discord_room"))
        user_id = str(getattr(interaction.user, "id", "discord_user"))
        session_id = f"discord:{room_id}:{user_id}"
        return {
            "session_id": session_id,
            "persona_id": str(getattr(self.runtime.router, "default_persona_id", "default")),
            "room_id": room_id,
            "platform": "discord",
            "mode": "",
            "flags": {},
        }

    @app_commands.command(name="social_status", description="Show runtime social state")
    async def social_status(self, interaction: discord.Interaction) -> None:
        snapshot = self.runtime.get_social_state_snapshot(**self._context(interaction))
        await interaction.response.send_message(
            f"override={snapshot.get('override', 'auto')} mode={snapshot.get('effective_mode', 'default')}",
            ephemeral=True,
        )

    @app_commands.command(name="social_mode", description="Set runtime social mode")
    async def social_mode(self, interaction: discord.Interaction, mode: str) -> None:
        snapshot = self.runtime.set_social_mode(
            **self._context(interaction),
            social_mode=str(mode or "").strip() or "default",
        )
        await interaction.response.send_message(
            f"social mode set to {snapshot.get('effective_mode', 'default')}",
            ephemeral=True,
        )
