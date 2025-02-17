import logging

import discord
from aiohttp import ClientConnectorDNSError, ContentTypeError
from attrs import define
from discord import Interaction, app_commands
from discord.ext import commands
from discord.utils import escape_markdown

from crcon import ApiClientError, ServerConnectionDetails
from polebot.composition_root import create_api_client
from polebot.discord.bot import Polebot
from polebot.exceptions import DatastoreError
from polebot.orchestrator import OrchestrationError
from polebot.services import cattrs_helpers
from utils import is_absolute

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
class ServerProps:
    label: str
    api_url: str
    api_key: str


@define
class ModalResult:
    success: bool
    error: str | None = None
    server_props: ServerProps | None = None


class AddServerModal(BaseInputModal, title="Add CRCON Server"):
    label: discord.ui.TextInput = discord.ui.TextInput(
        label="Label",
        placeholder="srv1",
        min_length=1,
        max_length=10,
        required=True,
        row=0,
    )
    url: discord.ui.TextInput = discord.ui.TextInput(
        label="Server URL",
        placeholder="https://my.crcon.server",
        min_length=1,
        max_length=254,
        row=1,
    )
    api_key: discord.ui.TextInput = discord.ui.TextInput(
        label="API Key",
        placeholder="<Your CRCON API Key>",
        min_length=5,
        max_length=50,
        row=2,
    )

    def __init__(
        self,
        logger: logging.Logger,
        *,
        title: str = discord.utils.MISSING,
        timeout: float | None = None,
        custom_id: str = discord.utils.MISSING,
    ) -> None:
        super().__init__(validate_server_props, logger, title=title, timeout=timeout, custom_id=custom_id)


async def validate_server_props(modal: BaseInputModal) -> ValidationFailure | ServerProps:
    if not isinstance(modal, AddServerModal):
        return ValidationFailure(error_message="Invalid modal type")
    if not is_absolute(modal.url.value):
        return ValidationFailure("Invalid value for Server URL - must be a valid URL")
    return ServerProps(label=modal.label.value, api_url=modal.url.value, api_key=modal.api_key.value)


@app_commands.guild_only()
class Servers(commands.GroupCog, name="servers", description="Manage your CRCON servers"):
    def __init__(
        self,
        bot: Polebot,
    ) -> None:
        self.bot = bot
        self._orchestrator = self.bot.orchestrator

        self._converter = cattrs_helpers.make_params_converter()

    @app_commands.command(name="list", description="List your servers")
    @app_commands.guild_only()
    async def list_servers(self, interaction: Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        if interaction.guild_id is None:
            self.bot.logger.error("add_server interaction has no guild_id")
            return

        try:
            guild_servers = await self._orchestrator.get_guild_servers(interaction.guild_id)
            if len(guild_servers):
                content = ""
                for server in sorted(guild_servers, key=lambda s: s.label):
                    content += f"{server.label}. {discord.utils.escape_markdown(server.name)}\n"
                embed = get_success_embed(title="CRCON Servers", description=content)
            else:
                content = to_discord_markdown(
                    f"""
                    No CRCON servers have been added yet. Use
                    {await get_command_mention(self.bot.tree, "servers", "add")} to add one.
                    """,
                )
                embed = get_error_embed(title="No servers", description=content)
            await interaction.followup.send(embed=embed, ephemeral=True)

        except DatastoreError as ex:
            self.bot.logger.error("Error accessing database", exc_info=ex)
            await interaction.followup.send("Oops, something went wrong!", ephemeral=True)

    @app_commands.command(name="add", description="Add a server")
    @app_commands.guild_only()
    async def add_server(self, interaction: Interaction) -> None:
        if interaction.guild_id is None:
            self.bot.logger.error("add_server interaction has no guild_id")
            return

        modal = AddServerModal(self.bot.logger)
        server_props = await do_input_modal(ServerProps, interaction, modal)
        if not server_props:
            return

        crcon_details = ServerConnectionDetails(server_props.api_url, server_props.api_key)
        try:
            server_name = await self._orchestrator.add_guild_server(
                interaction.guild_id,
                server_props.label,
                crcon_details,
            )
        except OrchestrationError as ex:
            self.bot.logger.warning("Unable to add server", exc_info=ex)
            content = f"Unable to add server at {server_props.api_url}."
            embed = get_error_embed(title="Error", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            content = f"Server `{server_name}` was added."
            embed = get_success_embed(title="Server added", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed)

    async def _autocomplete_servers(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await get_autocomplete_servers(self._orchestrator, interaction, current)

    @app_commands.command(name="remove", description="Remove a server")
    @app_commands.guild_only()
    @app_commands.autocomplete(server=_autocomplete_servers)
    async def remove_server(self, interaction: Interaction, server: str) -> None:
        if interaction.guild_id is None:
            self.bot.logger.error("add_server interaction has no guild_id")
            return

        await interaction.response.defer()
        try:
            await self._orchestrator.remove_guild_server(interaction.guild_id, server)
        except OrchestrationError as ex:
            self.bot.logger.error("Error removing server", exc_info=ex)
            content = f"Unable to remove server {server}."
            embed = get_error_embed(title="Error", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            content = f"Server {server} was removed."
            embed = get_success_embed(title="Server removed", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="show", description="Show server details")
    @app_commands.guild_only()
    @app_commands.autocomplete(server=_autocomplete_servers)
    async def show_server(self, interaction: Interaction, server: str) -> None:
        if interaction.guild_id is None:
            self.bot.logger.error("add_server interaction has no guild_id")
            return

        await interaction.response.defer()
        guild_server = await self._orchestrator.get_guild_server(interaction.guild_id, server)

        if guild_server is None:
            content = f"Server {server} not found."
            embed = get_error_embed(title="Error", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        content = f"""Details for server `{server}`:"""
        embed = get_success_embed(title="Server details", description=to_discord_markdown(content))
        embed.add_field(name="Name", value=escape_markdown(guild_server.name))
        embed.add_field(name="Label", value=guild_server.label)
        embed.add_field(name="URL", value=guild_server.crcon_details.api_url)
        embed.add_field(name="Votemap enabled?", value="Yes" if guild_server.enable_votemap else "No")
        if guild_server.enable_votemap and guild_server.weighting_parameters:
            mention = await get_command_mention(self.bot.tree, "votemaps", "downloadsettings")
            embed.add_field(name="Weighting Parameters", value=f"Use {mention} to view")
        embed.add_field(name="Created", value=f"<t:{int(guild_server.created_date_utc.timestamp())}:R>")
        embed.add_field(name="Modified", value=f"<t:{int(guild_server.modified_date_utc.timestamp())}:R>")
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _attempt_connect_to_server(self, crcon_details: ServerConnectionDetails) -> tuple[bool, str]:
        api_client = create_api_client(self.bot.container, crcon_details)
        result: tuple[bool, str] = (False, "Oops, an error occurred!")
        async with api_client:
            try:
                status = await api_client.get_status()
            except ApiClientError as ex:
                if ex.error == "You must be logged in to use this":
                    error = "Invalid API Key"
                else:
                    error = f"Server returned an error: {ex.error}"
                result = (False, error)
            except ClientConnectorDNSError:
                result = (False, f"Server `{crcon_details.api_url}` not found")
            except ContentTypeError:
                result = (False, f"`{crcon_details.api_url}` does not have a CRCON API endpoint")
            except Exception as ex:
                self.bot.logger.error("Unhandled error contacting new server", exc_info=ex)
                raise
            else:
                result = (True, status.name)
        return result


async def setup(bot: commands.Bot) -> None:
    """Adds the cog to the bot."""
    if not isinstance(bot, Polebot):
        raise TypeError("This cog is designed to be used with DiscordBot.")
    await bot.add_cog(Servers(bot))
