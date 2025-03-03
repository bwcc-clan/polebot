import io

import discord
from discord import File, Interaction, app_commands
from discord.ext import commands
from discord.utils import escape_markdown

from polebot.discord.bot import Polebot
from polebot.orchestrator import OrchestrationError
from polebot.services.settings_loader._settings_loader import SettingsLoader

from ..discord_utils import (
    get_attachment_as_text,
    get_autocomplete_servers,
    get_command_mention,
    get_error_embed,
    get_success_embed,
    to_discord_markdown,
)


@app_commands.guild_only()
class Votemaps(commands.GroupCog, name="votemaps", description="Manage the votemap settings for your CRCON servers"):
    def __init__(self, bot: Polebot) -> None:
        self.bot = bot

        self._orchestrator = self.bot.orchestrator
        self._settings_loader = SettingsLoader()

    async def _autocomplete_servers(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await get_autocomplete_servers(self._orchestrator, interaction, current)

    @app_commands.command(name="downloadsettings", description="Download the votemap settings file for a server")
    @app_commands.guild_only()
    @app_commands.autocomplete(server=_autocomplete_servers)
    async def download_votemap_settings(self, interaction: Interaction, server: str) -> None:
        if interaction.guild_id is None:
            self.bot.logger.error("upload_votemap_settings interaction has no guild_id")
            return

        await interaction.response.defer()

        try:
            result = await self._orchestrator.get_server_votemap_settings(interaction.guild_id, server)
            bytes_contents = result.encode("utf-8")
            fp = io.BytesIO(bytes_contents)
            attachment = File(fp=fp, filename=f"votemap_settings_{server}.json")
            content = f"Votemap settings for server **{server}** are attached."
            embed = get_success_embed(title="Votemap settings downloaded", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed, file=attachment, ephemeral=True)

        except OrchestrationError as ex:
            embed = get_error_embed(
                title="Error downloading settings",
                description=ex.message,
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

        try:
            contents = await get_attachment_as_text(file)
            guild_server = await self._orchestrator.upload_server_votemap_settings(
                interaction.guild_id,
                server,
                contents,
            )
        except OrchestrationError as ex:
            embed = get_error_embed(
                title="Error uploading settings",
                description=ex.message,
            )
            await interaction.delete_original_response()
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            self.bot.logger.info("Votemap settings uploaded for server %s", guild_server.id)
            content = f"Votemap settings were uploaded for server **{escape_markdown(guild_server.name)}**."
            embed = get_success_embed(title="Votemap settings uploaded", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="enable", description="Enable the votemap bot for a server")
    @app_commands.guild_only()
    @app_commands.autocomplete(server=_autocomplete_servers)
    async def enable_votemaps(self, interaction: Interaction, server: str) -> None:
        if interaction.guild_id is None:
            self.bot.logger.error("enable_votemaps interaction has no guild_id")
            return

        await interaction.response.defer()

        try:
            guild_server, updated = await self._orchestrator.set_server_votemap_enabled(
                interaction.guild_id,
                server,
                True,
            )
        except OrchestrationError as ex:
            embed = get_error_embed(
                title="Error enabling votemap",
                description=ex.message,
            )
            await interaction.delete_original_response()
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            if not updated:
                content = f"Votemap bot already enabled for server **{escape_markdown(guild_server.name)}**."
                embed = get_success_embed(title="No change", description=to_discord_markdown(content))
                await interaction.delete_original_response()
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                content = f"Votemap bot enabled for server **{escape_markdown(guild_server.name)}**."
                embed = get_success_embed(title="Votemap enabled", description=to_discord_markdown(content))
                await interaction.followup.send(embed=embed)

    @app_commands.command(name="disable", description="Disable the votemap bot for a server")
    @app_commands.guild_only()
    @app_commands.autocomplete(server=_autocomplete_servers)
    async def disable_votemaps(self, interaction: Interaction, server: str) -> None:
        if interaction.guild_id is None:
            self.bot.logger.error("disable_votemaps interaction has no guild_id")
            return

        await interaction.response.defer()

        try:
            guild_server, updated = await self._orchestrator.set_server_votemap_enabled(
                interaction.guild_id,
                server,
                False,
            )
        except OrchestrationError as ex:
            embed = get_error_embed(
                title="Error disabling votemaps",
                description=ex.message,
            )
            await interaction.delete_original_response()
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            if not updated:
                content = f"Votemap bot already disabled for server **{escape_markdown(guild_server.name)}**."
                embed = get_success_embed(title="No change", description=to_discord_markdown(content))
                await interaction.delete_original_response()
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                content = f"Votemap bot disabled for server **{escape_markdown(guild_server.name)}**."
                embed = get_success_embed(title="Votemap disabled", description=to_discord_markdown(content))
                await interaction.followup.send(embed=embed)

    @app_commands.command(name="help", description="Display help on votemap settings")
    @app_commands.guild_only()
    async def get_help(self, interaction: Interaction) -> None:
        content = r"""
        # About Votemap Settings

        Polebot provides an enhanced votemap experience for your servers. It overrides the standard votemap behaviour in
        CRCON and provides a more flexible and powerful way to manage the votemap choices on your server. Instead of all
        maps being equally likely to be selected, you can assign weights to each map and environment to influence the
        selection process.


        Votemap settings are stored in a JSON file that you can upload and download. The settings file contains a list
        of maps and "environments" (weather conditions, e.g. day / night / dusk) and their weights. Polebot uses this
        file to determine which maps to favour when building its votemap selections.


        The JSON file must conform to [this JSON
        schema](https://github.com/bwcc-clan/polebot/blob/main/src/polebot/services/settings_loader/weighting_parameters.schema.json).
        You can use the [JSON Schema Validator](https://www.jsonschemavalidator.net/) to check your file before
        uploading it.

        ## Commands
        """

        embed = discord.Embed(title="Votemaps help", description=to_discord_markdown(content))
        embed.set_thumbnail(
            url="https://github.com/bwcc-clan/polebot/blob/main/assets/polebot.png?raw=true",
        )
        embed.add_field(
            name=await get_command_mention(self.bot.tree, "votemaps", "uploadsettings"),
            value="Upload a votemap settings file for a server.",
            inline=False,
        )
        embed.add_field(
            name=await get_command_mention(self.bot.tree, "votemaps", "downloadsettings"),
            value="Download the votemap settings file for a server.",
            inline=False,
        )
        embed.add_field(
            name=await get_command_mention(self.bot.tree, "votemaps", "enable"),
            value="Enable the votemap bot for a server.",
            inline=False,
        )
        embed.add_field(
            name=await get_command_mention(self.bot.tree, "votemaps", "disable"),
            value="Disable the votemap bot for a server, and revert to the standard CRCON mechanism.",
            inline=False,
        )
        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    """Adds the cog to the bot."""
    if not isinstance(bot, Polebot):
        raise TypeError("This cog is designed to be used with Polebot.")
    await bot.add_cog(Votemaps(bot))
