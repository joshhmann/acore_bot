"""Runtime-host-backed Discord startup surface."""

from __future__ import annotations

import logging
from typing import Any

import discord
from discord.ext import commands

from config import Config


logger = logging.getLogger(__name__)


class GestaltDiscordBot(commands.Bot):
    """Transitional Discord bot that owns runtime-host startup only."""

    def __init__(self, runtime_host: Any, command_prefix: str = "!") -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True

        super().__init__(
            command_prefix=command_prefix,
            intents=intents,
            help_command=None,
        )
        self.runtime_host = runtime_host
        self.runtime = runtime_host.runtime

    async def setup_hook(self) -> None:
        from adapters.discord.commands.runtime_chat import RuntimeChatCog
        from adapters.discord.commands.social import SocialCommandsCog
        from adapters.discord.commands.help import HelpCog
        from adapters.discord.commands.system import SystemCog
        from adapters.discord.commands.character import CharacterCommandsCog

        await self.add_cog(RuntimeChatCog(self, runtime=self.runtime))
        await self.add_cog(HelpCog(self, runtime=self.runtime))
        await self.add_cog(SystemCog(self, runtime=self.runtime))
        await self.add_cog(SocialCommandsCog(self, runtime=self.runtime))

        if getattr(Config, "DISCORD_LEGACY_PERSONA_ADMIN_ENABLED", False):
            await self.add_cog(CharacterCommandsCog(self))
            logger.info("Loaded CharacterCommandsCog (legacy persona admin enabled)")
        else:
            logger.info("Skipped CharacterCommandsCog (legacy persona admin enabled)")

        try:
            await self.tree.sync()
        except Exception as exc:
            logger.warning("Discord command sync failed: %s", exc)

    async def on_ready(self) -> None:
        if self.user is None:
            logger.info("Discord bot ready")
            return
        logger.info("Discord bot ready as %s (%s)", self.user, self.user.id)
