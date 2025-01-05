import logging
from collections.abc import Callable

import discord
from aiohttp import ClientConnectorDNSError, ContentTypeError
from attrs import define
from discord import Interaction, app_commands
from discord.ext import commands

from ...api_client import CRCONApiClient
from ...composition_root import create_api_client
from ...discord.discord_bot import DiscordBot
from ...exceptions import CRCONApiClientError
from ...guild_repo import GuildRepository
from ...server_params import ServerCRCONDetails


@define
class ServerProps:
    server_name: str
    api_url: str
    api_key: str


@define
class ModalResult:
    success: bool
    error: str | None = None
    server_props: ServerProps | None = None


class AddServerModal(discord.ui.Modal, title="Add CRCON Server"):
    url: discord.ui.TextInput = discord.ui.TextInput(label="Server URL", placeholder="https://my.crcon.server/api")
    api_key: discord.ui.TextInput = discord.ui.TextInput(label="API Key", placeholder="<Your CRCON API Key>")

    def __init__(
        self,
        logger: logging.Logger,
        api_client_factory: Callable[[ServerCRCONDetails], CRCONApiClient],
        *,
        title: str = discord.utils.MISSING,
        timeout: float | None = None,
        custom_id: str = discord.utils.MISSING,
    ) -> None:
        self.logger = logger
        self.api_client_factory = api_client_factory
        self.result: ModalResult | None = None
        super().__init__(title=title, timeout=timeout, custom_id=custom_id)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        crcon_details = ServerCRCONDetails(self.url.value, self.api_key.value)
        api_client = self.api_client_factory(crcon_details)
        async with api_client:
            try:
                status = await api_client.get_status()
                server_props = ServerProps(server_name=status.name, api_url=self.url.value, api_key=self.api_key.value)
                self.result = ModalResult(success=True, server_props=server_props)
            except CRCONApiClientError as ex:
                if ex.error == "You must be logged in to use this":
                    error = "Invalid API Key"
                else:
                    error = f"Server returned an error: {ex.error}"
                self.result = ModalResult(success=False, error=error)
            except ClientConnectorDNSError:
                self.result = ModalResult(success=False, error=f"Server '{self.url.value}' not found")
            except ContentTypeError:
                self.result = ModalResult(success=False, error=f"'{self.url.value}' is not a CRCON API endpoint")
            except Exception as ex:
                self.logger.error("Unhandled error contacting new server", exc_info=ex)
                raise

        if self.result and self.result.success and self.result.server_props:
            await interaction.response.send_message(
                f"Added server {self.result.server_props.server_name}",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                self.result.error if self.result and self.result.error else "Oops! Something went wrong ",
                suppress_embeds=True,
                ephemeral=True,
            )
        self.stop()

    async def on_error(self, interaction: Interaction, error: Exception) -> None:  # type: ignore
        self.logger.error("Modal error", exc_info=error)
        await interaction.response.send_message("Oops! Something went wrong.", ephemeral=True)
        self.stop()


@app_commands.guild_only()
class Servers(commands.GroupCog, name="servers", description="Manage your CRCON servers"):
    def __init__(self, bot: DiscordBot, guild_repo: GuildRepository) -> None:
        self.bot = bot
        self.guild_repo = guild_repo

    @app_commands.command(name="list", description="List your servers")
    @app_commands.guild_only()
    async def list_servers(self, interaction: Interaction, description: str) -> None:
        await interaction.response.send_message(f"{description}: Pong!")

    @app_commands.command(name="add", description="Add a server")
    @app_commands.guild_only()
    async def add_server(self, interaction: Interaction) -> None:
        def _create_api_client(crcon_details: ServerCRCONDetails) -> CRCONApiClient:
            return create_api_client(self.bot.container, crcon_details)

        modal = AddServerModal(self.bot.logger, _create_api_client)
        await interaction.response.send_modal(modal)
        timed_out = await modal.wait()
        if not timed_out and modal.result:
            self.bot.logger.info("Modal complete")
        #     if modal.result.success and modal.result.server_props:
        #         await interaction.response.send_message(
        #             f"Added server {modal.result.server_props.server_name}", ephemeral=True,
        #         )
        #     else:
        #         await interaction.response.send_message(
        #             modal.result.error or "Oops! Something went wrong ", ephemeral=True,
        #         )

    @app_commands.command(name="remove", description="Remove a server")
    @app_commands.guild_only()
    async def remove_server(self, interaction: Interaction, description: str) -> None:
        await interaction.response.send_message(f"{description}: Pong!")


async def setup(bot: commands.Bot) -> None:
    """Adds the cog to the bot."""
    if not isinstance(bot, DiscordBot):
        raise TypeError("This cog is designed to be used with DiscordBot.")
    container = bot.container
    await bot.add_cog(Servers(bot, guild_repo=container[GuildRepository]))
