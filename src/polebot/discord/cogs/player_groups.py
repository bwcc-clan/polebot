import logging
import re
from typing import Self, overload

import discord
from attrs import define
from discord import Interaction, app_commands
from discord.ext import commands

from polebot.exceptions import DatastoreError, DuplicateKeyError
from polebot.models import GuildPlayerGroup
from polebot.services.polebot_database import PolebotDatabase

from ..discord_bot import DiscordBot
from ..discord_utils import (
    get_command_mention,
    get_error_embed,
    get_success_embed,
    get_unknown_error_embed,
    to_discord_markdown,
)


@define
class PlayerGroupProps:
    label: str
    selector: str


class ModalResult[T]:
    @overload
    def __init__(self, *, error_msg: str) -> None:
        ...

    @overload
    def __init__(self, *, result: T) -> None:
        ...

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


class AddPlayerGroupModal(discord.ui.Modal, title="Add Player Group"):
    label: discord.ui.TextInput = discord.ui.TextInput(
        label="Label",
        placeholder="clan-members",
        min_length=1,
        max_length=50,
        required=True,
        row=0,
    )
    selector: discord.ui.TextInput = discord.ui.TextInput(
        label="Selector",
        placeholder="[clan]",
        min_length=1,
        max_length=256,
        required=True,
        row=1,
    )

    def __init__(
        self,
        logger: logging.Logger,
        *,
        title: str = discord.utils.MISSING,
        timeout: float | None = None,
        custom_id: str = discord.utils.MISSING,
    ) -> None:
        self.logger = logger
        self.result: ModalResult[PlayerGroupProps] | None = None
        super().__init__(title=title, timeout=timeout, custom_id=custom_id)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        validate_result = self.validate()
        if isinstance(validate_result, PlayerGroupProps):
            self.result = ModalResult.from_value(value=validate_result)
        else:
            self.result = ModalResult.from_error(error_msg=validate_result)
        self.stop()

    async def on_error(self, interaction: Interaction, error: Exception) -> None:  # type: ignore
        self.logger.error("Modal error", exc_info=error)
        await interaction.response.send_message(embed=get_unknown_error_embed(), ephemeral=True)
        self.stop()

    def validate(self) -> str | PlayerGroupProps:
        selector = self.selector.value
        if selector.startswith("/") and selector.endswith("/"):
            try:
                re.compile(selector)
            except re.error:
                return "Selector is not a valid regular expression"
        return PlayerGroupProps(label=self.label.value, selector=self.selector.value)


@app_commands.guild_only()
class PlayerGroups(commands.GroupCog, name="playergroups", description="Manage groups of server players"):
    def __init__(self, bot: DiscordBot, db: PolebotDatabase) -> None:
        self.bot = bot
        self.db = db

    @app_commands.command(name="list", description="List player groups")
    @app_commands.guild_only()
    async def list_all(self, interaction: Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        if interaction.guild_id is None:
            self.bot.logger.error("list_all interaction has no guild_id")
            return

        try:
            player_groups = await self.db.fetch_all(GuildPlayerGroup, interaction.guild_id, sort="label")
            if len(player_groups):
                content = ""
                for player_group in sorted(player_groups, key=lambda s: s.label):
                    content += f"{player_group.label}: `{player_group.selector}`\n"
                embed = get_success_embed(title="Player Groups", description=content)
            else:
                content = to_discord_markdown(
                    f"""
                    No player groups have been added yet. Use
                    {await get_command_mention(self.bot.tree, 'playergroups', 'add')} to add one.
                    """,
                )
                embed = get_error_embed(title="No player groups", description=content)
            await interaction.followup.send(embed=embed, ephemeral=True)

        except DatastoreError as ex:
            self.bot.logger.error("Error accessing database", exc_info=ex)
            await interaction.followup.send("Oops, something went wrong!", ephemeral=True)

    @app_commands.command(name="add", description="Add a player group")
    @app_commands.guild_only()
    async def add(self, interaction: Interaction) -> None:
        if interaction.guild_id is None:
            self.bot.logger.error("add interaction has no guild_id")
            return

        modal = AddPlayerGroupModal(self.bot.logger)
        await interaction.response.send_modal(modal)
        timed_out = await modal.wait()
        self.bot.logger.debug("Modal complete")
        if timed_out or not modal.result:
            return
        if not (modal.result.success):
            error_desc = modal.result.error_msg or "-unknown-"
            self.bot.logger.info("Add Player Group modal returned error: %s", error_desc)
            content = f"Oops! Something went wrong: {error_desc}"
            embed = get_error_embed(title="Error", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        player_group = GuildPlayerGroup(
            guild_id=interaction.guild_id,
            label=modal.result.value.label,
            selector=modal.result.value.selector,
        )
        try:
            await self.db.insert(player_group)
        except DatastoreError as ex:
            self.bot.logger.warning("Failed to add player group", exc_info=ex)
            if isinstance(ex, DuplicateKeyError):
                content = f"Player group {modal.result.value.label} already exists."
            else:
                content = f"Unable to add player group {modal.result.value.label}."
            embed = get_error_embed(title="Error", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            content = f"Player group `{modal.result.value.label}` was added."
            embed = get_success_embed(title="Player group added", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed)

    async def _autocomplete_groups(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        if interaction.guild_id is None:
            return []

        await interaction.response.defer()
        player_groups = await self.db.fetch_all(GuildPlayerGroup, interaction.guild_id, sort="label")
        choices = [
            app_commands.Choice(name=f"{group.label}: {group.selector}", value=group.label)
            for group in player_groups
            if current.lower() in group.selector.lower() and group.id
        ]
        return choices

    @app_commands.command(name="remove", description="Remove a player group")
    @app_commands.guild_only()
    @app_commands.autocomplete(group=_autocomplete_groups)
    async def remove(self, interaction: Interaction, group: str) -> None:
        if interaction.guild_id is None:
            self.bot.logger.error("remove interaction has no guild_id")
            return

        # If server contains a valid label then the user selected from the choices. If not, error
        await interaction.response.defer()
        guild_server = await self.db.find_one(
            GuildPlayerGroup,
            guild_id=interaction.guild_id,
            attr_name="label",
            attr_value=group,
        )
        if guild_server:
            await self.db.delete(GuildPlayerGroup, guild_server.id)
            self.bot.logger.info("Group %s deleted", group)
            content = f"Group {guild_server.label} was removed."
            embed = get_success_embed(title="Group removed", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed)
        else:
            embed = get_error_embed(
                title="Group not found",
                description=f"No group labelled '{group}' exists.",
            )
            await interaction.delete_original_response()
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    if not isinstance(bot, DiscordBot):
        raise TypeError("This cog is designed to be used with a DiscordBot.")
    container = bot.container
    await bot.add_cog(PlayerGroups(bot, db=container[PolebotDatabase]))
