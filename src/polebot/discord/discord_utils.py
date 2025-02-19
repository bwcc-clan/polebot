import datetime as dt
import inspect
import json
import logging
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import TYPE_CHECKING, Any, NoReturn, Self, TypeVar, cast, overload

import discord
from attrs import frozen
from discord import ButtonStyle, Emoji, Interaction, PartialEmoji, SelectOption, app_commands, ui
from discord.ext import commands
from discord.utils import MISSING

from polebot.orchestrator import Orchestrator
from utils import JSON, parse_content_type
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


async def parse_attachment_as_json(file: discord.Attachment) -> JSON:
    if not file.content_type:
        raise ValueError("No content type provided for file")
    content_type = parse_content_type(file.content_type)
    if content_type[0] != "application/json":
        raise ValueError("File must be a JSON file")
    encoding: str = content_type[1].get("charset", "utf-8")
    file_data = await file.read()
    try:
        decoded_data = file_data.decode(encoding)
        parsed_json: JSON = json.loads(decoded_data)
        return parsed_json
    except (json.JSONDecodeError, UnicodeDecodeError) as ex:
        raise ValueError(f"Error parsing JSON file: {ex}") from ex


async def get_attachment_as_text(file: discord.Attachment) -> str:
    if not file.content_type:
        encoding: str = "utf-8"
    else:
        content_type = parse_content_type(file.content_type)
        encoding = content_type[1].get("charset", "utf-8")
    file_data = await file.read()
    return file_data.decode(encoding)


async def get_autocomplete_servers(
    orchestrator: Orchestrator,
    interaction: Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    if interaction.guild_id is None:
        return []

    await interaction.response.defer()
    guild_servers = await orchestrator.get_guild_servers(interaction.guild_id)
    choices = [
        app_commands.Choice(name=server.name, value=server.label)
        for server in guild_servers
        if current.lower() in server.name.lower() and server.id
    ]
    return choices


class ModalResult[T]:
    @overload
    def __init__(self, *, error_msg: str) -> None: ...

    @overload
    def __init__(self, *, result: T) -> None: ...

    def __init__(self, *, result: T | None = None, error_msg: str | None = None) -> None:
        if result and error_msg:
            raise ValueError("You must only provide either result or error_msg, not both")
        if result:
            self.success = True
            self._value = result
        elif error_msg:
            self.success = False
            self._error_msg = error_msg
        else:
            raise ValueError("Either result or error must be provided")

    @property
    def value(self) -> T:
        if not self.success:
            raise RuntimeError("Result indicates failure; error message not available")
        return self._value

    @property
    def error_msg(self) -> str:
        if self.success:
            raise RuntimeError("Result indicates success; error message not available")
        return self._error_msg

    @classmethod
    def from_error(cls, error_msg: str) -> Self:
        return cls(error_msg=error_msg)

    @classmethod
    def from_value(cls, value: T) -> Self:
        return cls(result=value)


@frozen
class ValidationFailure:
    error_message: str


class BaseInputModal(discord.ui.Modal):
    def __init__(
        self,
        validator: Callable[["BaseInputModal"], Awaitable[ValidationFailure | Any]],
        logger: logging.Logger,
        *,
        title: str = discord.utils.MISSING,
        timeout: float | None = None,
        custom_id: str = discord.utils.MISSING,
    ) -> None:
        self.logger = logger
        self._validator = validator
        self.result: ModalResult[Any] | None = None
        super().__init__(title=title, timeout=timeout, custom_id=custom_id)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        validate_result = await self.validate()
        if isinstance(validate_result, ValidationFailure):
            self.result = ModalResult.from_error(error_msg=validate_result.error_message)
        else:
            self.result = ModalResult.from_value(value=validate_result)
        self.stop()

    async def on_error(self, interaction: Interaction, error: Exception) -> None:  # type: ignore
        self.logger.error("Modal error", exc_info=error)
        await interaction.response.send_message(embed=get_unknown_error_embed(), ephemeral=True)
        self.stop()

    async def validate(self) -> ValidationFailure | Any:  # noqa: ANN401
        return await self._validator(self)


async def do_input_modal[T](result_type: type[T], interaction: Interaction, modal: BaseInputModal) -> T | None:
    modal_class_name = type(modal).__name__
    modal.logger.debug("Launching modal %s", modal_class_name)
    await interaction.response.send_modal(modal)
    timed_out = await modal.wait()
    modal.logger.debug("Modal complete")
    if timed_out or not modal.result:
        return None
    if not (modal.result.success):
        error_desc = modal.result.error_msg or "-unknown-"
        modal.logger.info("Modal %s returned error: %s", modal_class_name, error_desc)
        content = f"Oops! Something went wrong: {error_desc}"
        embed = get_error_embed(title="Error", description=to_discord_markdown(content))
        await interaction.followup.send(embed=embed, ephemeral=True)
        return None

    if not isinstance(modal.result.value, result_type):
        raise TypeError(f"Unexpected result type from modal: {type(modal.result.value)}")
    result = cast(T, modal.result.value)
    return result


class DiscordDateFormat(StrEnum):
    full_date_time = "F"
    long_date_time = "f"
    long_date = "D"
    short_date = "d"
    long_time = "T"
    short_time = "t"
    relative = "R"


def discord_date(date: dt.datetime, date_format: DiscordDateFormat) -> str:
    return f"<t:{int(date.timestamp())}:{date_format.value}>"
