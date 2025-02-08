import io
import json

import discord
from discord import File, Interaction, app_commands
from discord.ext import commands

from polebot.exceptions import DatastoreError
from polebot.models import GuildServer, WeightingParameters
from polebot.services import cattrs_helpers
from polebot.services.polebot_database import PolebotDatabase

from ..discord_bot import DiscordBot
from ..discord_utils import (
    get_autocomplete_servers,
    get_error_embed,
    get_success_embed,
    parse_attachment_as_json,
    to_discord_markdown,
)


@app_commands.guild_only()
class Votemaps(commands.GroupCog, name="votemaps", description="Manage the votemap settings for your CRCON servers"):
    def __init__(self, bot: DiscordBot, db: PolebotDatabase) -> None:
        self.bot = bot
        self.db = db
        self._converter = cattrs_helpers.make_params_converter()

    async def _autocomplete_servers(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await get_autocomplete_servers(self.db, interaction, current)

    # @app_commands.command(name="list", description="List your servers")
    # @app_commands.guild_only()
    # async def list_servers(self, interaction: Interaction) -> None:
    #     await interaction.response.defer(ephemeral=True)

    #     if interaction.guild_id is None:
    #         self.bot.logger.error("add_server interaction has no guild_id")
    #         return

    #     try:
    #         guild_servers = await self.db.fetch_all(GuildServer, interaction.guild_id, sort="label")
    #         if len(guild_servers):
    #             content = ""
    #             for server in sorted(guild_servers, key=lambda s: s.label):
    #                 content += f"{server.label}. {discord.utils.escape_markdown(server.name)}\n"
    #             embed = get_success_embed(title="CRCON Servers", description=content)
    #         else:
    #             content = to_discord_markdown(
    #                 f"""
    #                 No CRCON servers have been added yet. Use
    #                 {await get_command_mention(self.bot.tree, "servers", "add")} to add one.
    #                 """,
    #             )
    #             embed = get_error_embed(title="No servers", description=content)
    #         await interaction.followup.send(embed=embed, ephemeral=True)

    #     except DatastoreError as ex:
    #         self.bot.logger.error("Error accessing database", exc_info=ex)
    #         await interaction.followup.send("Oops, something went wrong!", ephemeral=True)

    # @app_commands.command(name="remove", description="Remove a server")
    # @app_commands.guild_only()
    # @app_commands.autocomplete(server=_autocomplete_servers)
    # async def remove_server(self, interaction: Interaction, server: str) -> None:
    #     if interaction.guild_id is None:
    #         self.bot.logger.error("add_server interaction has no guild_id")
    #         return

    #     # If server contains a valid label then the user selected from the choices. If not, error
    #     await interaction.response.defer()
    #     guild_server = await self.db.find_one(
    #         GuildServer,
    #         guild_id=interaction.guild_id,
    #         attr_name="label",
    #         attr_value=server,
    #     )
    #     if guild_server:
    #         await self.db.delete(GuildServer, guild_server.id)
    #         self.bot.logger.info("Server %s deleted", server)
    #         content = f"Server {guild_server.name} was removed."
    #         embed = get_success_embed(title="Server removed", description=to_discord_markdown(content))
    #         await interaction.followup.send(embed=embed)
    #     else:
    #         embed = get_error_embed(
    #             title="Server not found",
    #             description=f"No server labelled '{server}' exists.",
    #         )
    #         await interaction.delete_original_response()
    #         await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="downloadsettings", description="Download the votemap settings file for a server")
    @app_commands.guild_only()
    @app_commands.autocomplete(server=_autocomplete_servers)
    async def download_votemap_settings(self, interaction: Interaction, server: str) -> None:
        if interaction.guild_id is None:
            self.bot.logger.error("upload_votemap_settings interaction has no guild_id")
            return

        await interaction.response.defer()

        result = await self._get_votemap_settings_file(interaction.guild_id, server)
        if isinstance(result, File):
            content = f"Votemap settings for server **{server}** are attached."
            embed = get_success_embed(title="Votemap settings downloaded", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed, file=result, ephemeral=True)
        else:
            embed = get_error_embed(
                title="Error downloading settings",
                description=result,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="uploadsettings", description="Upload the votemap settings file for a server")
    @app_commands.guild_only()
    @app_commands.autocomplete(server=_autocomplete_servers)
    async def upload_votemap_settings(self, interaction: Interaction, server: str, file: discord.Attachment) -> None:
        if interaction.guild_id is None:
            self.bot.logger.error("upload_votemap_settings interaction has no guild_id")
            return

        await interaction.response.defer()

        error = await self._save_votemap_settings(interaction.guild_id, server, file)
        if error:
            embed = get_error_embed(
                title="Error uploading settings",
                description=str(error),
            )
            await interaction.delete_original_response()
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            self.bot.logger.info("Votemap settings uploaded for server %s", server)
            content = f"Votemap settings were uploaded for server **{server}**."
            embed = get_success_embed(title="Votemap settings uploaded", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed)

    async def _save_votemap_settings(self, guild_id: int, server_label: str, file: discord.Attachment) -> str | None:
        try:
            json_contents = await parse_attachment_as_json(file)
            weighting_params = self._converter.structure(json_contents, WeightingParameters)
        except ValueError as ex:
            return f"Error parsing JSON file: {ex}"

        guild_server = await self.db.find_one(
            GuildServer,
            guild_id=guild_id,
            attr_name="label",
            attr_value=server_label,
        )
        if not guild_server:
            return f"No server with label {server_label} found"
        guild_server.weighting_parameters = weighting_params
        try:
            guild_server = await self.db.update(guild_server)
        except DatastoreError as ex:
            return f"Error updating document: {ex}"
        else:
            return None

    async def _get_votemap_settings_file(self, guild_id: int, server_label: str) -> File | str:
        guild_server = await self.db.find_one(
            GuildServer,
            guild_id=guild_id,
            attr_name="label",
            attr_value=server_label,
        )
        if not guild_server:
            return f"Server {server_label} not found"
        if not guild_server.weighting_parameters:
            return f"Server {server_label} does not have any votemap settings"
        try:
            content = self._converter.unstructure(guild_server.weighting_parameters)
            json_contents = json.dumps(content, indent=4)
            bytes_contents = json_contents.encode("utf-8")
            fp = io.BytesIO(bytes_contents)
            return File(fp=fp, filename=f"votemap_settings_{server_label}.json")
        except UnicodeEncodeError:
            return f"Server {server_label} settings could not be downloaded"

async def setup(bot: commands.Bot) -> None:
    """Adds the cog to the bot."""
    if not isinstance(bot, DiscordBot):
        raise TypeError("This cog is designed to be used with DiscordBot.")
    container = bot.container
    await bot.add_cog(Votemaps(bot, db=container[PolebotDatabase]))
