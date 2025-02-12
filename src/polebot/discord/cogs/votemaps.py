import io

import discord
from discord import File, Interaction, app_commands
from discord.ext import commands

from polebot.discord.bot import Polebot
from polebot.orchestrator import OrchestrationError
from polebot.services.settings_loader._settings_loader import SettingsLoader

from ..discord_utils import (
    get_attachment_as_text,
    get_autocomplete_servers,
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
            content = f"Votemap settings were uploaded for server **{guild_server.name}**."
            embed = get_success_embed(title="Votemap settings uploaded", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Adds the cog to the bot."""
    if not isinstance(bot, Polebot):
        raise TypeError("This cog is designed to be used with Polebot.")
    await bot.add_cog(Votemaps(bot))
