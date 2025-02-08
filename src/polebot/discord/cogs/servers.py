import logging

import discord
from aiohttp import ClientConnectorDNSError, ContentTypeError
from attrs import define
from discord import Interaction, app_commands
from discord.ext import commands

from crcon import ApiClientError, ServerConnectionDetails
from polebot.composition_root import create_api_client
from polebot.exceptions import DatastoreError
from polebot.models import GuildServer
from polebot.services import converters
from polebot.services.polebot_database import PolebotDatabase
from utils import is_absolute

from ..discord_bot import DiscordBot
from ..discord_utils import (
    get_autocomplete_servers,
    get_command_mention,
    get_error_embed,
    get_success_embed,
    get_unknown_error_embed,
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


class AddServerModal(discord.ui.Modal, title="Add CRCON Server"):
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
        self.logger = logger
        self.result: ModalResult | None = None
        super().__init__(title=title, timeout=timeout, custom_id=custom_id)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        validate_result = self.validate()
        if isinstance(validate_result, ServerProps):
            self.result = ModalResult(success=True, server_props=validate_result)
        else:
            self.result = ModalResult(False, error=validate_result)
        self.stop()

    async def on_error(self, interaction: Interaction, error: Exception) -> None:  # type: ignore
        self.logger.error("Modal error", exc_info=error)
        await interaction.response.send_message(embed=get_unknown_error_embed(), ephemeral=True)
        self.stop()

    def validate(self) -> str | ServerProps:
        if not is_absolute(self.url.value):
            return "Invalid value for Server URL - must be a valid URL"
        return ServerProps(label=self.label.value, api_url=self.url.value, api_key=self.api_key.value)


@app_commands.guild_only()
class Servers(commands.GroupCog, name="servers", description="Manage your CRCON servers"):
    def __init__(self, bot: DiscordBot, db: PolebotDatabase) -> None:
        self.bot = bot
        self.db = db
        self._converter = converters.make_params_converter()

    @app_commands.command(name="list", description="List your servers")
    @app_commands.guild_only()
    async def list_servers(self, interaction: Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        if interaction.guild_id is None:
            self.bot.logger.error("add_server interaction has no guild_id")
            return

        try:
            guild_servers = await self.db.fetch_all(GuildServer, interaction.guild_id, sort="label")
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
        await interaction.response.send_modal(modal)
        timed_out = await modal.wait()
        self.bot.logger.debug("Modal complete")
        if timed_out or not modal.result:
            return
        if not (modal.result.success and modal.result.server_props):
            error_desc = modal.result.error or "-unknown-"
            self.bot.logger.info("Add Server modal returned error: %s", error_desc)
            content = f"Oops! Something went wrong: {error_desc}"
            embed = get_error_embed(title="Error", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        crcon_details = ServerConnectionDetails(modal.result.server_props.api_url, modal.result.server_props.api_key)
        result = await self._attempt_connect_to_server(crcon_details)

        if not result[0]:
            content = f"Unable to connect to the server with the details provided: {result[1]}"
            embed = get_error_embed(title="Error", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        server_name = result[1]
        guild_server = GuildServer(
            guild_id=interaction.guild_id,
            label=modal.result.server_props.label,
            name=server_name,
            crcon_details=crcon_details,
        )
        try:
            await self.db.insert(guild_server)
        except DatastoreError as ex:
            self.bot.logger.warning("Unable to add server", exc_info=ex)
            content = f"Unable to add server {server_name}."
            embed = get_error_embed(title="Error", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            content = f"Server `{server_name}` was added."
            embed = get_success_embed(title="Server added", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed)

    async def _autocomplete_servers(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await get_autocomplete_servers(self.db, interaction, current)

    @app_commands.command(name="remove", description="Remove a server")
    @app_commands.guild_only()
    @app_commands.autocomplete(server=_autocomplete_servers)
    async def remove_server(self, interaction: Interaction, server: str) -> None:
        if interaction.guild_id is None:
            self.bot.logger.error("add_server interaction has no guild_id")
            return

        # If server contains a valid label then the user selected from the choices. If not, error
        await interaction.response.defer()
        guild_server = await self.db.find_one(
            GuildServer,
            guild_id=interaction.guild_id,
            attr_name="label",
            attr_value=server,
        )
        if guild_server:
            await self.db.delete(GuildServer, guild_server.id)
            self.bot.logger.info("Server %s deleted", server)
            content = f"Server {guild_server.name} was removed."
            embed = get_success_embed(title="Server removed", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed)
        else:
            embed = get_error_embed(
                title="Server not found",
                description=f"No server labelled '{server}' exists.",
            )
            await interaction.delete_original_response()
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
    if not isinstance(bot, DiscordBot):
        raise TypeError("This cog is designed to be used with DiscordBot.")
    container = bot.container
    await bot.add_cog(Servers(bot, db=container[PolebotDatabase]))
