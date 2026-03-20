"""Runtime-host-backed Discord startup surface."""

from __future__ import annotations

import logging
from typing import Any

import discord
from discord.ext import commands

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
        from adapters.discord.commands.profile import ProfileCommandsCog
        from adapters.discord.commands.search import SearchCommandsCog
        from adapters.discord.commands.system import SystemCog

        await self.add_cog(RuntimeChatCog(self, runtime=self.runtime))
        await self.add_cog(HelpCog(self, runtime=self.runtime))
        await self.add_cog(SystemCog(self, runtime=self.runtime))
        await self.add_cog(SocialCommandsCog(self, runtime=self.runtime))
        await self.add_cog(
            ProfileCommandsCog(
                self,
                user_profiles=None,
                gestalt_runtime=self.runtime,
            )
        )
        await self.add_cog(
            SearchCommandsCog(
                self,
                web_search=None,
                system_prompt="",
                gestalt_runtime=self.runtime,
            )
        )
        logger.info(
            "Legacy Discord character/persona admin remains quarantined behind legacy entrypoints"
        )

        try:
            await self.tree.sync()
        except Exception as exc:
            logger.warning("Discord command sync failed: %s", exc)

    async def on_ready(self) -> None:
        if self.user is None:
            logger.info("Discord bot ready")
            return
        logger.info("Discord bot ready as %s (%s)", self.user, self.user.id)
