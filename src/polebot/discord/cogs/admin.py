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

    def help_custom(self) -> tuple[str, str, str]:
        emoji = "⚙️"
        label = "Admin"
        description = "Show the list of admin commands."
        return emoji, label, description

    @bot_has_permissions(send_messages=True)
    @commands.command(name="loadcog")
    @commands.is_owner()
    async def load_cog(self, ctx: commands.Context, cog: str) -> None:
        """Load a cog."""
        await self.bot.load_cog(cog)
        await ctx.send(f":point_right: Cog {cog} loaded!")

    @bot_has_permissions(send_messages=True)
    @commands.command(name="unloadcog")
    @commands.is_owner()
    async def unload_cog(self, ctx: commands.Context, cog: str) -> None:
        """Unload a cog."""
        await self.bot.unload_cog(cog)
        await ctx.send(f":point_left: Cog {cog} unloaded!")

    @bot_has_permissions(send_messages=True)
    @commands.command(name="reloadallcogs", aliases=["rell"])
    @commands.is_owner()
    async def reload_all_cogs(self, ctx: commands.Context) -> None:
        """Reload all cogs."""
        cogs = list(self.bot.extensions)
        for cog in cogs:
            await self.bot.reload_cog(cog)

        await ctx.send(f":muscle: All cogs reloaded: `{len(cogs)}`!")

    @bot_has_permissions(send_messages=True)
    @commands.command(name="reload", aliases=["rel"], require_var_positional=True)
    @commands.is_owner()
    async def reload_specified_cogs(self, ctx: commands.Context, *cogs: str) -> None:
        """Reload specific cogs."""
        for cog in cogs:
            await self.bot.reload_cog(cog)

        await ctx.send(f":thumbsup: `{'` `'.join(cogs)}` reloaded!")

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

    @bot_has_permissions(send_messages=True)
    @commands.command(name="shutdown")
    @commands.is_owner()
    async def shutdown_structure(self, ctx: commands.Context) -> None:
        """Shutdown the bot."""
        await ctx.send(f":wave: `{self.bot.user}` is shutting down...")

        await self.bot.close()


async def setup(bot: DiscordBot) -> None:
    await bot.add_cog(Admin(bot))
