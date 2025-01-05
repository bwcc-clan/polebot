import datetime as dt
import importlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import discord
from discord import __version__ as discord_version
from discord import app_commands
from discord.ext import commands
from discord.ext.commands._types import BotT
from lagom import Container

# from polebot.discord.discord_utils import CogOperation, cogs_manager

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from discord.ext.commands.bot import PrefixType
else:
    # Dummy definitions to stop things from breaking at runtime
    T = TypeVar("T")
    P = TypeVar("P")
    PrefixType = Any | Callable[[...], T]


class DiscordBot(commands.Bot):
    def __init__(
        self,
        command_prefix: PrefixType[BotT],
        *,
        container: Container,
        help_command: commands.HelpCommand | None = commands.bot._default,
        tree_cls: type[app_commands.CommandTree[Any]] = app_commands.CommandTree,
        description: str | None = None,
        allowed_contexts: app_commands.AppCommandContext = discord.utils.MISSING,
        allowed_installs: app_commands.AppInstallationType = discord.utils.MISSING,
        intents: discord.Intents,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        self.bot_module = importlib.import_module(self.__module__)
        if not (self.bot_module.__file__ and self.bot_module.__package__):
            raise TypeError("Bot module must have a file and package")
        self.cogs_dir = "cogs"
        self.container: Container = container
        self.logger: logging.Logger = kwargs.pop("logger", None) or _logger
        self.uptime = dt.datetime.now(tz=dt.UTC)
        super().__init__(
            command_prefix,
            help_command=help_command,
            tree_cls=tree_cls,
            description=description,
            allowed_contexts=allowed_contexts,
            allowed_installs=allowed_installs,
            intents=intents,
            **kwargs,
        )

    async def on_ready(self) -> None:
        self.logger.info(
            "Logged as: %s | discord.py%s Guilds: %d Users: %d",
            self.user,
            discord_version,
            len(self.guilds),
            len(self.users),
        )

    async def setup_hook(self) -> None:
        # Retrieve the bot's application info
        self.appinfo = await self.application_info()

    async def load_cog(self, cog: str) -> None:
        fullname = f".{self.cogs_dir}.{cog}"
        try:
            await self.load_extension(fullname, package=self.bot_module.__package__)
            self.logger.info("Loaded cog %s", cog)
        except Exception as e:
            self.logger.error("Cog %s cannot be loaded:", cog, exc_info=e)
            raise

    async def unload_cog(self, cog: str) -> None:
        fullname = f".{self.cogs_dir}.{cog}"
        try:
            await self.unload_extension(fullname, package=self.bot_module.__package__)
            self.logger.info("Unloaded cog %s", cog)
        except Exception as e:
            self.logger.error("Cog %s cannot be unloaded:", cog, exc_info=e)
            raise

    async def reload_cog(self, cog: str) -> None:
        fullname = f".{self.cogs_dir}.{cog}"
        try:
            await self.reload_extension(fullname)
            self.logger.info("Reloaded cog %s", cog)
        except Exception as e:
            self.logger.error("Cog %s cannot be reloaded:", cog, exc_info=e)
            raise

    async def load_all_cogs(self) -> None:
        assert self.bot_module.__file__  # noqa: S101
        cogs_path = Path(self.bot_module.__file__).parent.joinpath(self.cogs_dir)
        for file_path in cogs_path.glob("*.py"):
            await self.load_cog(file_path.stem)
