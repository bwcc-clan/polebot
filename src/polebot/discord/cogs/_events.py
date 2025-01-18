import inspect

import discord
from discord.ext import commands

from polebot.discord.discord_bot import DiscordBot

from ...services.polebot_database import PolebotDatabase
from ..bot import Polebot
from ..discord_utils import get_command_mention


class _events(commands.Cog):  # noqa: N801
    """A class with most events in it."""

    def __init__(self, bot: DiscordBot, guild_repo: PolebotDatabase) -> None:
        self.bot = bot
        self.logger = self.bot.logger
        self._guild_repo = guild_repo
        # self.update_status.start()

        # @bot.tree.error
        # async def on_interaction_error(interaction: Interaction, error: Exception) -> None:
        #     await handle_error(interaction, error)

    # @commands.Cog.listener()
    # async def on_command_error(self, ctx: commands.Context, error: errors.CommandError) -> None:
    #     await handle_error(ctx, error)

    # @tasks.loop(minutes=5.0)
    # async def update_status(self) -> None:
    #     # TODO: Implement this
    #     # await self.bot.change_presence(
    #     #     activity=discord.Activity(name=f"over {len(SESSIONS)} sessions", type=discord.ActivityType.watching),
    #     # )
    #     pass

    # @update_status.before_loop
    # async def before_status(self) -> None:
    #     await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        self.logger.debug("on_guild_join, guild=%d", guild.id)
        if guild.public_updates_channel and guild.public_updates_channel.permissions_for(guild.me).send_messages:
            channel = guild.public_updates_channel
        elif guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
            channel = guild.system_channel
        else:
            return

        markdown = f"""
        Let me quickly introduce myself, I am **The Polebot**

        I can help you manage your Hell Let Loose server, by sending messages to multiple clan members at a time.

        Before you can let me loose, you need to set a couple of things up first. Don't worry, this will only take a few
        minutes!

        1. **Add your server details** → {await get_command_mention(self.bot.tree, 'servers', 'add')}
        2. **Configure bot permissions** → TODO (Optional)

        That's all there is to it! Thanks for using The Polebot!
        """
        embed = discord.Embed(
            title="Thank you for adding me 👋",
            description=inspect.cleandoc(markdown),
            color=discord.Colour(7722980),
        ).set_image(url="https://github.com/timraay/HLLLogUtilities/blob/main/assets/banner.png?raw=true")

        await channel.send(embed=embed)

    # @commands.Cog.listener()
    # async def on_guild_remove(self, guild: discord.Guild) -> None:
    #     all_credentials = Credentials.in_guild(guild.id)
    #     for credentials in all_credentials:
    #         if credentials.autosession.enabled:
    #             credentials.autosession.logger.info("Disabling AutoSession since its credentials are being deleted")
    #             credentials.autosession.disable()

    #         for session in credentials.get_sessions():
    #             if session.active_in() is True:
    #                 session.logger.info("Stopping ongoing session since its credentials are being deleted")
    #                 await session.stop()

    #             session.logger.info("Deleting session since it's being removed from a guild")
    #             await session.delete()

    #         credentials.delete()


async def setup(bot: commands.Bot) -> None:
    if not isinstance(bot, Polebot):
        raise TypeError("This cog is designed to be used with Polebot.")
    container = bot.container
    await bot.add_cog(_events(bot, guild_repo=container[PolebotDatabase]))
