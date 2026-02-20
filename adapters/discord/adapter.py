from typing import Any
import discord
from core.interfaces import InputAdapter, OutputAdapter


class DiscordInputAdapter(InputAdapter):
    """
    Skeleton InputAdapter for Discord. Converts Discord events into AcoreEvent.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()

    async def start(self) -> None:
        # Placeholder: initialize Discord event subscriptions
        pass

    async def stop(self) -> None:
        # Placeholder: cleanup resources
        pass

    async def on_event(self, event: Any) -> None:
        # Placeholder: convert Discord event to AcoreEvent
        pass


class DiscordOutputAdapter(OutputAdapter):
    """
    Skeleton OutputAdapter for Discord. Sends messages via Discord bot/webhook.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()

    async def send(self, payload: Any) -> None:
        # Placeholder: implement sending plain payload to Discord
        pass

    async def send_embed(self, embed: discord.Embed) -> None:
        # Placeholder: implement sending a Discord Embed
        pass
