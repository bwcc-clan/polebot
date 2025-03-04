"""The Discord bot entry point."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import commands
from lagom import Container

if TYPE_CHECKING:
    from polebot.orchestrator import Orchestrator

from .discord_bot import DiscordBot

logger = logging.getLogger(__name__)


@commands.guild_only()
class Polebot(DiscordBot):
    """The main bot class."""

    def __init__(self, orchestrator: Orchestrator, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        """Initialises the bot."""
        self.orchestrator = orchestrator
        super().__init__(*args, **kwargs)
        self.remove_command("help")

    async def setup_hook(self) -> None:
        """Initialize the bot, database, prefixes & cogs."""
        # Initialize the DiscordBot setup hook
        await super().setup_hook()

        await self.load_all_cogs()
        # Sync application commands
        self.loop.create_task(self.startup())

    async def startup(self) -> None:
        await self.wait_until_ready()

        # Sync application commands
        try:
            synced = await self.tree.sync()
            logger.info("Application commands synced (%d)", len(synced))
        except TimeoutError:
            logger.warning(
                "Timeout during app command sync. This was likely last done recently, resulting in rate limits.",
            )

        if self.user:
            logger.info("Launched bot %s with ID %d", self.user.name, self.user.id)
        else:
            logger.warning("Launched bot with no user")

def make_bot(orchestrator: Orchestrator, container: Container, discord_owner_id: int) -> Polebot:
    """Creates a bot instance."""
    intents = discord.Intents.default()

    bot = Polebot(
        orchestrator=orchestrator,
        intents=intents,
        command_prefix=commands.when_mentioned_or("/", "!"),
        case_insensitive=True,
        container=container,
        owner_id=discord_owner_id,
    )

    return bot
