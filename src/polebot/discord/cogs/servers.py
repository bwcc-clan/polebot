import datetime as dt
import logging

import bson
import bson.errors
import discord
from aiohttp import ClientConnectorDNSError, ContentTypeError
from attrs import define
from bson import ObjectId
from discord import Interaction, app_commands
from discord.ext import commands

from ...composition_root import create_api_client
from ...exceptions import CRCONApiClientError, DatastoreError
from ...models import GuildServer, ServerCRCONDetails
from ...polebot_database import PolebotDatabase
from ...utils import is_absolute
from ..discord_bot import DiscordBot
from ..discord_utils import get_command_mention, get_error_embed, get_success_embed, to_discord_markdown


@define
class ServerProps:
    api_url: str
    api_key: str


@define
class ModalResult:
    success: bool
    error: str | None = None
    server_props: ServerProps | None = None


class AddServerModal(discord.ui.Modal, title="Add CRCON Server"):
    url: discord.ui.TextInput = discord.ui.TextInput(label="Server URL", placeholder="https://my.crcon.server")
    api_key: discord.ui.TextInput = discord.ui.TextInput(label="API Key", placeholder="<Your CRCON API Key>")

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
        if is_absolute(self.url.value):
            server_props = ServerProps(api_url=self.url.value, api_key=self.api_key.value)
            self.result = ModalResult(success=True, server_props=server_props)
        else:
            self.result = ModalResult(False, error="Invalid value for Server URL - must be a valid URL")
        self.stop()

    async def on_error(self, interaction: Interaction, error: Exception) -> None:  # type: ignore
        self.logger.error("Modal error", exc_info=error)
        await interaction.response.send_message("Oops! Something went wrong.", ephemeral=True)
        self.stop()


@app_commands.guild_only()
class Servers(commands.GroupCog, name="servers", description="Manage your CRCON servers"):
    def __init__(self, bot: DiscordBot, db: PolebotDatabase) -> None:
        self.bot = bot
        self.db = db

    @app_commands.command(name="list", description="List your servers")
    @app_commands.guild_only()
    async def list_servers(self, interaction: Interaction) -> None:
        if interaction.guild_id is None:
            self.bot.logger.error("add_server interaction has no guild_id")
            await interaction.response.defer()
            return

        try:
            guild_servers = await self.db.list_guild_servers(interaction.guild_id)
            if len(guild_servers):
                content = ""
                for idx, server in enumerate(guild_servers):
                    content += f"{idx}. {discord.utils.escape_markdown(server.server_name)}\n"
                embed = get_success_embed(title="CRCON Servers", description=content)
            else:
                content = to_discord_markdown(
                    f"""
                    No CRCON servers have been added yet. Use
                    {await get_command_mention(self.bot.tree, 'servers', 'add')} to add one.
                    """,
                )
                embed = get_error_embed(title="No servers", description=content)
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except DatastoreError as ex:
            self.bot.logger.error("Error accessing database", exc_info=ex)
            await interaction.response.send_message("Oops, something went wrong!", ephemeral=True)

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

        crcon_details = ServerCRCONDetails(modal.result.server_props.api_url, modal.result.server_props.api_key)
        result = await self._attempt_connect_to_server(crcon_details)

        if not result[0]:
            content = f"Unable to connect to the server with the details provided: {result[1]}"
            embed = get_error_embed(title="Error", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        server_name = result[1]
        guild_server = GuildServer(
            guild_id=interaction.guild_id,
            server_name=server_name,
            crcon_details=crcon_details,
            created_date_utc=dt.datetime.now(dt.UTC),
        )
        try:
            await self.db.insert_guild_server(guild_server)
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
        if interaction.guild_id is None:
            return []

        await interaction.response.defer()
        guild_servers = await self.db.list_guild_servers(interaction.guild_id)
        choices = [
            app_commands.Choice(name=server.server_name, value=str(server.id))
            for server in guild_servers
            if current.lower() in server.server_name.lower() and server.id
        ]
        return choices

    @app_commands.command(name="remove", description="Remove a server")
    @app_commands.guild_only()
    @app_commands.autocomplete(server=_autocomplete_servers)
    async def remove_server(self, interaction: Interaction, server: str) -> None:
        if interaction.guild_id is None:
            self.bot.logger.error("add_server interaction has no guild_id")
            return

        # If server contains a valid ObjectId then the user selected from the choices. If not, error
        await interaction.response.defer()
        try:
            server_id = ObjectId(server)
        except bson.errors.InvalidId:
            embed = get_error_embed(
                title="Invalid selection",
                description="You did not select a server from the list.",
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            guild_server = await self.db.get_guild_server(server_id)
            if guild_server:
                await self.db.delete_guild_server(server_id)
                self.bot.logger.info("Server %s deleted", server)
                content = f"Server {guild_server.server_name} was removed."
                embed = get_success_embed(title="Server removed", description=to_discord_markdown(content))
                await interaction.followup.send(embed=embed)
            else:
                embed = get_error_embed(
                    title="Server not found",
                    description="That server doesn't exist.",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

    async def _attempt_connect_to_server(self, crcon_details: ServerCRCONDetails) -> tuple[bool, str]:
        api_client = create_api_client(self.bot.container, crcon_details)
        result: tuple[bool, str] = (False, "Oops, an error occurred!")
        async with api_client:
            try:
                status = await api_client.get_status()
            except CRCONApiClientError as ex:
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
