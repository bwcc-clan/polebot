import datetime as dt

# from classes.discordbot import DiscordBot
# from classes.utilities import (
#     GuildContext,
#     bot_has_permissions,
#     load_config,
#     cogs_manager,
#     reload_views,
#     cogs_directory,
#     root_directory,
# )
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

    # @bot_has_permissions(send_messages=True)
    # @commands.command(name="reloadlatest", aliases=["rl"])
    # @commands.is_owner()
    # async def reload_latest_cogs(self, ctx: commands.Context, n_cogs: int = 1) -> None:
    #     """Reload the latest edited n cogs."""

    #     def sort_cogs(cogs_last_edit: list[list]) -> list[list]:
    #         return sorted(cogs_last_edit, reverse=True, key=lambda x: x[1])

    #     cogs = []
    #     for file in os.listdir(cogs_directory):
    #         actual = os.path.splitext(file)
    #         if actual[1] == ".py":
    #             file_path = os.path.join(cogs_directory, file)
    #             latest_edit = os.path.getmtime(file_path)
    #             cogs.append([actual[0], latest_edit])

    #     sorted_cogs = sort_cogs(cogs)
    #     reload_cogs = [f"cogs.{cog[0]}" for cog in sorted_cogs[:n_cogs]]
    #     await cogs_manager(self.bot, "reload", reload_cogs)

    #     await ctx.send(f":point_down: `{'` `'.join(reload_cogs)}` reloaded!")

    # @bot_has_permissions(send_messages=True)
    # @commands.command(name="reloadviews", aliases=["rv"])
    # @commands.is_owner()
    # async def reload_view(self, ctx: commands.Context) -> None:
    #     """Reload each registered views."""
    #     infants = reload_views()
    #     succes_text = f"👌 All views reloaded ! | 🔄 __`{sum(1 for _ in infants)} view(s) reloaded`__ : "
    #     for infant in infants:
    #         succes_text += f"`{infant.replace('views.', '')}` "
    #     await ctx.send(succes_text)

    # @bot_has_permissions(send_messages=True)
    # @commands.command(name="reloadconfig", aliases=["rc"])
    # @commands.is_owner()
    # async def reload_config(self, ctx: commands.Context) -> None:
    #     """Reload each json config file."""
    #     self.bot.config = load_config()
    #     await ctx.send(f":handshake: `{len(self.bot.config)}` config file(s) reloaded!")

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

    # @bot_has_permissions(send_messages=True, attach_files=True)
    # @commands.command(name="botlogs", aliases=["bl"])
    # @commands.is_owner()
    # async def show_bot_logs(self, ctx: commands.Context) -> None:
    #     """Upload the bot logs"""
    #     logs_file = os.path.join(root_directory, "discord.log")

    #     await ctx.send(file=discord.File(fp=logs_file, filename="bot.log"))

    # @bot_has_permissions(send_messages=True)
    # @commands.command(name="changeprefix", aliases=["cp", "prefix"], require_var_positional=True)
    # @commands.has_guild_permissions(administrator=True)
    # @commands.guild_only()
    # async def change_guild_prefix(self, ctx: GuildContext, new_prefix: str) -> None:
    #     """Change the guild prefix."""
    #     if not self.bot.usedatabase or not ctx.guild:
    #         await ctx.send(":warning: Database not used, prefix not changed.")
    #         return
    #     try:
    #         table = self.bot.config["bot"]["prefix_table"]["table"]
    #         await self.bot.database.insert_onduplicate(table, {"guild_id": ctx.guild.id, "guild_prefix": new_prefix})

    #         self.bot.prefixes[ctx.guild.id] = new_prefix
    #         await ctx.send(f":warning: Prefix changed to `{new_prefix}`")
    #     except Exception as e:
    #         await ctx.send(f"Error: {e}")

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
