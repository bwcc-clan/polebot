import logging

import discord
from attrs import define
from discord import Interaction, app_commands
from discord.ext import commands

from polebot.discord.bot import Polebot
from polebot.orchestrator import OrchestrationError
from polebot.services.player_matcher import PlayerMatcher

from ..discord_utils import (
    BaseInputModal,
    ValidationFailure,
    do_input_modal,
    get_autocomplete_servers,
    get_command_mention,
    get_error_embed,
    get_success_embed,
    to_discord_markdown,
)


@define
class PlayerGroupProps:
    label: str
    selector: str


class AddPlayerGroupModal(BaseInputModal, title="Add Player Group"):
    label: discord.ui.TextInput = discord.ui.TextInput(
        label="Label",
        placeholder="Enter the group's label",
        min_length=1,
        max_length=50,
        required=True,
        row=0,
    )
    selector: discord.ui.TextInput = discord.ui.TextInput(
        label="Filter",
        placeholder="Enter the filter that identifies group members",
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
        super().__init__(
            validator=validate_player_group_props,
            logger=logger,
            title=title,
            timeout=timeout,
            custom_id=custom_id,
        )


async def validate_player_group_props(modal: BaseInputModal) -> ValidationFailure | PlayerGroupProps:
    if not isinstance(modal, AddPlayerGroupModal):
        return ValidationFailure(error_message="Invalid modal type")
    selector = modal.selector.value
    ok, err = PlayerMatcher.validate_selector(selector)
    if not ok:
        assert isinstance(err, str)  # noqa: S101
        return ValidationFailure(error_message=err)
    return PlayerGroupProps(label=modal.label.value, selector=modal.selector.value)


@define
class SendMessageResult:
    message: str


class SendMessageModal(BaseInputModal, title="Send Message"):
    message_text: discord.ui.TextInput = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.paragraph,
        placeholder="Enter message text",
        min_length=1,
        max_length=250,
        required=True,
        row=0,
    )

    def __init__(
        self,
        logger: logging.Logger,
        *,
        title: str = discord.utils.MISSING,
        timeout: float | None = None,
        custom_id: str = discord.utils.MISSING,
    ) -> None:
        super().__init__(validate_send_message, logger, title=title, timeout=timeout, custom_id=custom_id)


async def validate_send_message(modal: BaseInputModal) -> ValidationFailure | SendMessageResult:
    if not isinstance(modal, SendMessageModal):
        return ValidationFailure(error_message="Invalid modal type")
    return SendMessageResult(message=modal.message_text.value)


@app_commands.guild_only()
class PlayerGroups(commands.GroupCog, name="playergroups", description="Manage groups of server players"):
    def __init__(self, bot: Polebot) -> None:
        self.bot = bot
        self._orchestrator = bot.orchestrator

    @app_commands.command(name="list", description="List player groups")
    @app_commands.guild_only()
    async def list_all(self, interaction: Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        if interaction.guild_id is None:
            self.bot.logger.error("list_all interaction has no guild_id")
            return

        try:
            player_groups = await self._orchestrator.get_player_groups(interaction.guild_id)
            if len(player_groups):
                content = ""
                for player_group in sorted(player_groups, key=lambda s: s.label):
                    content += f"{player_group.label}: `{player_group.selector}`\n"
                embed = get_success_embed(title="Player Groups", description=content)
            else:
                content = to_discord_markdown(
                    f"""
                    No player groups have been added yet. Use
                    {await get_command_mention(self.bot.tree, "playergroups", "add")} to add one.
                    """,
                )
                embed = get_error_embed(title="No player groups", description=content)
            await interaction.followup.send(embed=embed, ephemeral=True)

        except OrchestrationError as ex:
            self.bot.logger.error("Error accessing database", exc_info=ex)
            await interaction.followup.send("Oops, something went wrong!", ephemeral=True)

    @app_commands.command(name="add", description="Add a player group")
    @app_commands.guild_only()
    async def add(self, interaction: Interaction) -> None:
        if interaction.guild_id is None:
            self.bot.logger.error("add interaction has no guild_id")
            return

        modal = AddPlayerGroupModal(self.bot.logger)
        props = await do_input_modal(PlayerGroupProps, interaction, modal)
        if not props:
            return

        try:
            player_group = await self._orchestrator.add_player_group(
                guild_id=interaction.guild_id,
                label=props.label,
                selector=props.selector,
            )
        except OrchestrationError as ex:
            self.bot.logger.warning("Failed to add player group", exc_info=ex)
            content = ex.message
            embed = get_error_embed(title="Error", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            content = f"Player group `{player_group.label}` was added."
            embed = get_success_embed(title="Player group added", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed)

    async def _autocomplete_groups(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        if interaction.guild_id is None:
            return []

        await interaction.response.defer()
        player_groups = await self._orchestrator.get_player_groups(interaction.guild_id)
        choices = [
            app_commands.Choice(name=f"{group.label}: {group.selector}", value=group.label)
            for group in player_groups
            if current.lower() in group.selector.lower() and group.id
        ]
        return choices

    async def _autocomplete_servers(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await get_autocomplete_servers(self._orchestrator, interaction, current)

    @app_commands.command(name="remove", description="Remove a player group")
    @app_commands.guild_only()
    @app_commands.autocomplete(group=_autocomplete_groups)
    async def remove(self, interaction: Interaction, group: str) -> None:
        if interaction.guild_id is None:
            self.bot.logger.error("remove interaction has no guild_id")
            return

        await interaction.response.defer()

        try:
            await self._orchestrator.remove_player_group(interaction.guild_id, group)
        except OrchestrationError as ex:
            content = ex.message
            embed = get_error_embed(title="Group not removed", description=to_discord_markdown(content))
            await interaction.delete_original_response()
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        else:
            content = f"Group {group} was removed."
            embed = get_success_embed(title="Group removed", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="message", description="Send a message to a player group")
    @app_commands.guild_only()
    @app_commands.autocomplete(group=_autocomplete_groups, server=_autocomplete_servers)
    async def send_message(self, interaction: Interaction, server: str, group: str) -> None:
        if interaction.guild_id is None:
            self.bot.logger.error("remove interaction has no guild_id")
            return

        # Display modal to get message
        modal = SendMessageModal(self.bot.logger)
        message = await do_input_modal(SendMessageResult, interaction, modal)
        if not message:
            return

        try:
            self.bot.logger.debug("Sending message to group %s on server %s", group, server)
            players = list(
                await self._orchestrator.send_message_to_player_group(
                    interaction.guild_id,
                    server,
                    group,
                    message.message,
                ),
            )
            if players:
                player_list = ", ".join([p.name for p in players])
                content = f"""
                Message sent to {len(players)} player(s) in group `{group}` on server `{server}`:

                {player_list}."""
            else:
                content = f"No players in group `{group}` are currently playing on server `{server}`."
            embed = get_success_embed(title="Message sent", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed, ephemeral=True)
        except OrchestrationError as ex:
            self.bot.logger.warning("Failed to send message to player group", exc_info=ex)
            content = ex.message
            embed = get_error_embed(title="Error", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="show", description="Show the members of a player group on a server")
    @app_commands.guild_only()
    @app_commands.autocomplete(group=_autocomplete_groups, server=_autocomplete_servers)
    async def show_players(self, interaction: Interaction, server: str, group: str) -> None:
        if interaction.guild_id is None:
            self.bot.logger.error("show_players interaction has no guild_id")
            return

        await interaction.response.defer(ephemeral=True)

        try:
            players = await self._orchestrator.get_players_in_group(interaction.guild_id, server, group)
            if players:
                player_list = ", ".join([p.name for p in players])
                content = f"Players in group `{group}` on server `{server}`:\n\n\n{player_list}"
            else:
                content = f"No players in group `{group}` are currently playing on server `{server}`."
            embed = get_success_embed(title="Players in group", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed, ephemeral=True)
        except OrchestrationError as ex:
            self.bot.logger.warning("Failed to get players in group", exc_info=ex)
            content = ex.message
            embed = get_error_embed(title="Error", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="help", description="Display help on player groups")
    @app_commands.guild_only()
    async def get_help(self, interaction: Interaction) -> None:
        content = r"""
        # About Player Groups

        Player groups are lists of players who are currently playing on your servers. By using player groups, you can
        perform bulk actions on all players in the group, such as sending messages.

        ## Filters

        A group's members are defined by a filter, which is applied to each online player to see if they are in the
        group. If the player matches the filter, they are a member of the group.


        Filters work by looking at the player name. A filter can be:

        - for simple scenarios, a prefix filter that matches the first characters of a player name; or

        - for more complex scenarios, a [regular expression](https://en.wikipedia.org/wiki/Regular_expression) filter
        that matches the whole of a player's name.


        If your filter starts and ends with a `/` (forward slash) character, Polebot treats the text in between these
        delimiters as a regular expression. Otherwise, Polebot assumes it is a prefix filter.

        ### Prefix filter

        Example: `[57th]`


        This is a prefix filter that matches any player whose name starts with the exact text `[57th]`. Prefix matches
        are case sensitive. The table below shows some examples of names and whether they are group members or not:


        :white_check_mark: `[57th] Geronimo`

        :white_check_mark: `[57th]Geronimo`

        :x: `[57TH] Geronimo`

        :x: `57th Geronimo`

        :x: `Geronimo [57th]`

        ### Regular expression filter

        Example: `/\[57[tT][hH]\]/`


        This is a regular expression filter that matches any player with `[57th]` anywhere in their name (case
        insensitive).


        :white_check_mark: `[57th] Geronimo`

        :white_check_mark: `[57th]Geronimo`

        :white_check_mark: `[57TH] Geronimo`

        :x: `57th Geronimo`

        :white_check_mark: `Geronimo [57th]`


        Regular expressions are complicated but powerful. There are many online resources that can help you learn them:
        a good starting point is [regex101](https://regex101.com/).

        ## Commands
        """

        embed = discord.Embed(title="Player group help", description=to_discord_markdown(content))
        embed.set_thumbnail(url="https://github.com/bwcc-clan/polebot/blob/main/assets/polebot.png?raw=true")
        embed.add_field(
            name=await get_command_mention(self.bot.tree, "playergroups", "list"),
            value="List all the player groups.",
            inline=False,
        )
        embed.add_field(
            name=await get_command_mention(self.bot.tree, "playergroups", "add"),
            value="Add a player group.",
            inline=False,
        )
        embed.add_field(
            name=await get_command_mention(self.bot.tree, "playergroups", "remove"),
            value="Remove a player group.",
            inline=False,
        )
        embed.add_field(
            name=await get_command_mention(self.bot.tree, "playergroups", "message"),
            value="Send an in-game message to all players that match the group's filter.",
            inline=False,
        )
        embed.add_field(
            name=await get_command_mention(self.bot.tree, "playergroups", "show"),
            value="Show the members of a player group on a server.",
            inline=False,
        )
        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    if not isinstance(bot, Polebot):
        raise TypeError("This cog is designed to be used with a Polebot.")

    await bot.add_cog(PlayerGroups(bot))
