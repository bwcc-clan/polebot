import inspect
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, NoReturn

import discord
from discord import ButtonStyle, Emoji, Interaction, PartialEmoji, SelectOption, app_commands, ui
from discord.ext import commands
from discord.utils import MISSING
from typing_extensions import TypeVar

from utils.cachetools import ttl_cache

if TYPE_CHECKING:
    from discord.client import Client

    ClientT = TypeVar("ClientT", bound=Client, covariant=True, default=Client)
else:
    ClientT = TypeVar("ClientT", bound="Client", covariant=True)


class CallableButton(ui.Button):
    def __init__(
        self,
        callback: Callable,
        *args: Any,  # noqa: ANN401
        style: ButtonStyle = ButtonStyle.secondary,
        label: str | None = None,
        disabled: bool = False,
        custom_id: str | None = None,
        url: str | None = None,
        emoji: str | Emoji | PartialEmoji | None = None,
        row: int | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        super().__init__(
            style=style,
            label=label,
            disabled=disabled,
            custom_id=custom_id,
            url=url,
            emoji=emoji,
            row=row,
        )
        self._callback = callback
        self._args = args
        self._kwargs = kwargs

    async def callback(self, interaction: Interaction) -> None:
        await self._callback(interaction, *self._args, **self._kwargs)


class CallableSelect(ui.Select):
    def __init__(
        self,
        callback: Callable,
        *args: Any,  # noqa: ANN401
        custom_id: str = MISSING,
        placeholder: str | None = None,
        min_values: int = 1,
        max_values: int = 1,
        options: list[SelectOption] = MISSING,
        disabled: bool = False,
        row: int | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        super().__init__(
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            options=options,
            disabled=disabled,
            row=row,
        )
        self._callback = callback
        self._args = args
        self._kwargs = kwargs

    async def callback(self, interaction: Interaction) -> None:
        await self._callback(interaction, self.values, *self._args, **self._kwargs)


async def dummy_awaitable_callable(*args: Any, **kwargs: Any) -> NoReturn:  # noqa: ANN401
    raise NotImplementedError("This function is a dummy function and is not meant to be called.")


def to_discord_markdown(markdown: str) -> str:
    lines = inspect.cleandoc(markdown).splitlines()
    discord_markdown = ""
    for idx, line in enumerate(lines):
        if len(line):
            discord_markdown += line
            if idx != len(lines) - 1:
                discord_markdown += " "
        else:
            discord_markdown += "\n"
    return discord_markdown


def get_error_embed(title: str, description: str | None = None) -> discord.Embed:
    embed = discord.Embed(color=discord.Color.from_rgb(221, 46, 68))
    embed.set_author(name=title, icon_url="https://cdn.discordapp.com/emojis/808045512393621585.png")
    if description:
        embed.description = description
    return embed


def get_success_embed(title: str, description: str | None = None) -> discord.Embed:
    embed = discord.Embed(color=discord.Color(7844437))
    embed.set_author(name=title, icon_url="https://cdn.discordapp.com/emojis/809149148356018256.png")
    if description:
        embed.description = description
    return embed


def get_question_embed(title: str, description: str | None = None) -> discord.Embed:
    embed = discord.Embed(color=discord.Color(3315710))
    embed.set_author(
        name=title,
        icon_url="https://cdn.discordapp.com/attachments/729998051288285256/924971834343059496/unknown.png",
    )
    if description:
        embed.description = description
    return embed


def get_unknown_error_embed() -> discord.Embed:
    return get_error_embed(title="Oops! Something went wrong", description="Sorry, something bad happened :,(")


# @ttl_cache(size=100, seconds=60 * 60 * 24)
@ttl_cache(size=100, seconds=60)
async def get_command_mention(tree: discord.app_commands.CommandTree, name: str, subcommand: str | None = None) -> str:
    commands = await tree.fetch_commands()
    command = next((cmd for cmd in commands if cmd.name == name), None)
    if not command:
        return "magic"
    if subcommand:
        return f"</{command.name} {subcommand}:{command.id}>"
    return f"</{command.name}:{command.id}>"


MyCommand = app_commands.Command | commands.HybridCommand | commands.Command


def bot_has_permissions(**perms: bool) -> Callable[..., MyCommand]:
    """A decorator for command permissions.

    This decorator adds specified permissions to Command.extras and adds bot_has_permissions check to Command with
    specified permissions.

    Warning: - This decorator must be on the top of the decorator stack - This decorator is not compatible with
    commands.check()
    """

    def wrapped(
        command: MyCommand,
    ) -> MyCommand:
        if not isinstance(command, MyCommand):
            raise TypeError(
                f"Cannot decorate a class that is not a subclass of Command, get: {type(command)} must be Command",
            )

        valid_required_permissions = [
            perm for perm, value in perms.items() if getattr(discord.Permissions.none(), perm) != value
        ]
        command.extras.update({"bot_permissions": valid_required_permissions})

        if isinstance(command, commands.HybridCommand) and command.app_command:
            command.app_command.extras.update({"bot_permissions": valid_required_permissions})

        if isinstance(command, app_commands.Command | commands.HybridCommand):
            app_commands.checks.bot_has_permissions(**perms)(command)
        if isinstance(command, commands.Command | commands.HybridCommand):
            commands.bot_has_permissions(**perms)(command)

        return command

    return wrapped
