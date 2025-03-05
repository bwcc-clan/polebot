import datetime as dt

import discord
from discord.ext import commands
from discord.utils import format_dt

from ..discord_bot import DiscordBot
from ..discord_utils import bot_has_permissions


class Admin(commands.Cog, name="admin"):
    """Admin commands.

    Require intents:
            - message_content

    Require bot permission:
            - read_messages
            - send_messages
            - attach_files
    """

    def __init__(self, bot: DiscordBot) -> None:
        self.bot = bot

    @bot_has_permissions(send_messages=True)
    @commands.command(name="synctree", aliases=["st"])
    @commands.is_owner()
    async def sync_tree(self, ctx: commands.Context, guild_id: str | None = None) -> None:
        """Sync application commands."""
        if guild_id:
            if ctx.guild and (guild_id == "guild" or guild_id == "~"):
                guild_id = str(ctx.guild.id)
            tree = await self.bot.tree.sync(guild=discord.Object(id=guild_id))
        else:
            tree = await self.bot.tree.sync()

        self.bot.logger.info("%s synced the tree(%d): %s", ctx.author, len(tree), tree)
        await ctx.send(f":pinched_fingers: `{len(tree)}` synced!")

    @bot_has_permissions(send_messages=True)
    @commands.command(name="uptime")
    @commands.is_owner()
    async def show_uptime(self, ctx: commands.Context) -> None:
        """Show the bot uptime."""
        uptime = dt.datetime.now(tz=dt.UTC) - self.bot.uptime
        await ctx.send(f":clock1: {format_dt(self.bot.uptime, 'R')} ||`{uptime}`||")


async def setup(bot: DiscordBot) -> None:
    await bot.add_cog(Admin(bot))
