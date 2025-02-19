from discord import Interaction, app_commands
from discord.ext import commands

from polebot.discord.bot import Polebot
from polebot.orchestrator import OrchestrationError
from polebot.services.settings_loader._settings_loader import SettingsLoader

from ..discord_utils import (
    DiscordDateFormat,
    discord_date,
    get_autocomplete_servers,
    get_error_embed,
    get_success_embed,
    to_discord_markdown,
)


@app_commands.guild_only()
class Vip(commands.GroupCog, name="vip", description="View VIP information on a server"):
    def __init__(self, bot: Polebot) -> None:
        self.bot = bot

        self._orchestrator = self.bot.orchestrator
        self._settings_loader = SettingsLoader()

    async def _autocomplete_servers(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await get_autocomplete_servers(self._orchestrator, interaction, current)

    @app_commands.command(name="show", description="Show how much VIP time a player has left")
    @app_commands.guild_only()
    @app_commands.autocomplete(server=_autocomplete_servers)
    async def show_vip(self, interaction: Interaction, server: str) -> None:
        if interaction.guild_id is None:
            self.bot.logger.error("show_vip interaction has no guild_id")
            return

        await interaction.response.defer(ephemeral=True)

        try:
            player_name = interaction.user.display_name
            result = await self._orchestrator.get_player_vip_info(interaction.guild_id, server, player_name)
            if result is None:
                content = f"You don't currently have VIP on server **{server}**."
            else:
                if result.vip_expiry is None:
                    content = f"You have VIP on server **{server}** indefinitely."
                else:
                    date = discord_date(result.vip_expiry, DiscordDateFormat.relative)
                    content = f"Your VIP on server **{server}** expires {date}."
            embed = get_success_embed(title="VIP status", description=to_discord_markdown(content))
            await interaction.followup.send(embed=embed, ephemeral=True)

        except OrchestrationError as ex:
            embed = get_error_embed(
                title="Error getting VIP information",
                description=ex.message,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Adds the cog to the bot."""
    if not isinstance(bot, Polebot):
        raise TypeError("This cog is designed to be used with Polebot.")
    await bot.add_cog(Vip(bot))
