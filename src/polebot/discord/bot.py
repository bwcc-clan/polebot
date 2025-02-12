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

def make_bot(orchestrator: Orchestrator, container: Container) -> Polebot:
    """Creates a bot instance."""
    intents = discord.Intents(
        emojis=True,
        guild_scheduled_events=False,
        guilds=True,
        invites=True,
        members=False,
        message_content=False,
        messages=True,
        presences=False,
        reactions=True,
        voice_states=False,
    )

    bot = Polebot(
        orchestrator=orchestrator,
        intents=intents,
        command_prefix=commands.when_mentioned_or("/", "!"),
        case_insensitive=True,
        container=container,
    )

    # @bot.command(aliases=["load"])
    # @commands.is_owner()
    # async def enable(ctx: commands.Context, cog: str) -> None:
    #     """Enable a cog."""
    #     cog = cog.lower()
    #     if _cog_exists(cog):
    #         await _load_cog(bot, cog)
    #         await ctx.send(f"Enabled {cog}")
    #     else:
    #         await ctx.send(f"{cog} doesn't exist")

    # @bot.command(aliases=["unload"])
    # @commands.is_owner()
    # async def disable(ctx: commands.Context, cog: str) -> None:
    #     """Disable a cog."""
    #     cog = cog.lower()
    #     if _cog_exists(cog):
    #         await _unload_cog(bot, cog)
    #         await ctx.send(f"Disabled {cog}")
    #     else:
    #         await ctx.send(f"{cog} doesn't exist")

    # @bot.command()
    # @commands.is_owner()
    # async def reload(ctx: commands.Context, cog: str | None = None) -> None:
    #     """Reload cogs."""

    #     async def reload_cog(ctx: commands.Context, cog_name: str) -> None:
    #         """Reloads a cog."""
    #         try:
    #             await _reload_cog(bot, cog_name)
    #             await ctx.send(f"Reloaded {cog_name}")
    #         except Exception as e:  # noqa: BLE001
    #             await ctx.send(f"Couldn't reload {cog_name}, " + str(e))

    #     if not cog:
    #         for cog_name in _all_cog_names():
    #             await reload_cog(ctx, cog_name)
    #     else:
    #         if Path(f"./cogs/{cog}.py").exists():
    #             await reload_cog(ctx, cog)
    #         else:
    #             await ctx.send(f"{cog} doesn't exist")

    return bot
