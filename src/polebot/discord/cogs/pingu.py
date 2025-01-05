from os import name

import discord
from discord import Interaction, app_commands
from discord.ext import commands
from discord.ext.commands import errors


@app_commands.guild_only()
class pingu(commands.GroupCog, name="pingu", description="Manage your pings"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # Group = app_commands.Group(name="pingu", description="Manage your pings")

    @app_commands.command(name="ping", description="Get a pong response")
    @app_commands.guild_only()
    async def ping(self, interaction: Interaction, description: str) -> None:
        await interaction.response.send_message(f"{description}: Pong!")

async def setup(bot: commands.Bot) -> None:
    """Adds the cog to the bot."""
    await bot.add_cog(pingu(bot))
