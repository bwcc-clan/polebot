import datetime as dt
import traceback
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

import discord
from discord import ButtonStyle, Emoji, Interaction, PartialEmoji, SelectOption, app_commands, ui
from discord.ext import commands
from discord.utils import MISSING
from discord.utils import escape_markdown as esc_md
from typing_extensions import TypeVar

from ..cache_utils import ttl_cache

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


class ExpiredButtonError(Exception):
    """Raised when pressing a button that has already expired."""


class CustomException(Exception):
    """Raised to log a custom exception."""

    def __init__(self, error: Any, *args: Any) -> None:  # noqa: ANN401
        self.error = error
        super().__init__(*args)


async def handle_error(interaction: Interaction | commands.Context, error: Exception) -> None:
    if isinstance(error, app_commands.CommandInvokeError | commands.CommandInvokeError):
        error = error.original

    if isinstance(error, app_commands.CommandNotFound | commands.CommandNotFound):
        embed = get_error_embed(title="Unknown command!")

    elif type(error).__name__ == CustomException.__name__:
        embed = get_error_embed(title=str(error), description=str(error))

    elif isinstance(error, ExpiredButtonError):
        embed = get_error_embed(title="This action no longer is available.")
    elif isinstance(error, app_commands.CommandOnCooldown | commands.CommandOnCooldown):
        sec = dt.timedelta(seconds=int(error.retry_after))
        d = dt.datetime(1, 1, 1, tzinfo=dt.UTC) + sec
        output = f"{d.hour}h{d.minute}m{d.second}s"
        if output.startswith("0h"):
            output = output.replace("0h", "")
        if output.startswith("0m"):
            output = output.replace("0m", "")
        embed = get_error_embed(
            title="That command is still on cooldown!",
            description="Cooldown expires in " + output + ".",
        )
    elif isinstance(error, app_commands.MissingPermissions | commands.MissingPermissions):
        embed = get_error_embed(title="Missing required permissions to use that command!", description=str(error))
    elif isinstance(error, app_commands.BotMissingPermissions | commands.BotMissingPermissions):
        embed = get_error_embed(title="I am missing required permissions to use that command!", description=str(error))
    elif isinstance(error, app_commands.CheckFailure | commands.CheckFailure):
        embed = get_error_embed(title="Couldn't run that command!", description=None)
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = get_error_embed(title="Missing required argument(s)!")
        embed.description = str(error)
    elif isinstance(error, commands.MaxConcurrencyReached):
        embed = get_error_embed(title="You can't do that right now!")
        embed.description = str(error)
    elif isinstance(error, commands.BadArgument):
        embed = get_error_embed(title="Invalid argument!", description=esc_md(str(error)))
    else:
        embed = get_error_embed(title="An unexpected error occured!", description=esc_md(str(error)))
        try:
            raise error
        except:
            traceback.print_exc()

    if isinstance(interaction, Interaction):
        if interaction.response.is_done() or interaction.is_expired():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.send(embed=embed)


class View(ui.View):
    async def on_error(self, interaction: Interaction, error: Exception, item: ui.Item[Any], /) -> None:
        await handle_error(interaction, error)


class Modal(ui.Modal):
    async def on_error(self, interaction: Interaction, error: Exception, /) -> None:  # type: ignore[override]
        await handle_error(interaction, error)


def only_once(func: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Coroutine[Any, Any, Any]]:
    func.__has_been_ran_once = False  # type: ignore

    async def decorated(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        if func.__has_been_ran_once:  # type: ignore
            raise ExpiredButtonError
        res = await func(*args, **kwargs)
        func.__has_been_ran_once = True  # type: ignore
        return res

    return decorated


@ttl_cache(size=100, seconds=60 * 60 * 24)
async def get_command_mention(tree: discord.app_commands.CommandTree, name: str, subcommands: str | None = None) -> str:
    commands = await tree.fetch_commands()
    command = next(cmd for cmd in commands if cmd.name == name)
    if subcommands:
        return f"</{command.name} {subcommands}:{command.id}>"
    else:
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
                f"Cannot decorate a class that is not a subclass of Command, get: {type(command)} must be Command"
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
