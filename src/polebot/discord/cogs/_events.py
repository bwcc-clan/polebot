import inspect

import discord
from discord import app_commands
from discord.ext import commands, tasks

from ..bot import Polebot
from ..discord_utils import dummy_awaitable_callable, get_command_mention


class _events(commands.Cog):  # noqa: N801
    """A class with most events in it."""

    def __init__(self, bot: Polebot) -> None:
        self.bot = bot
        self.logger = self.bot.logger
        self._orchestrator = self.bot.orchestrator
        self.default_error_message = "🕳️ There is an error."
        # self.update_status.start()

        @bot.tree.error
        async def _dispatch_to_app_command_handler(
            interaction: discord.Interaction,
            error: discord.app_commands.AppCommandError,
        ) -> None:
            self.bot.dispatch("app_command_error", interaction, error)

    # @commands.Cog.listener()
    # async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
    #     await handle_error(ctx, error)

    async def _ensure_response_to_interaction(self, interaction: discord.Interaction) -> bool:
        try:
            await interaction.response.send_message(content=self.default_error_message, ephemeral=True)
            return True
        except discord.errors.InteractionResponded:
            return False

    @commands.Cog.listener("on_app_command_error")
    async def get_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ) -> None:
        """App command Error Handler.

        doc: https://discordpy.readthedocs.io/en/latest/interactions/api.html#exception-hierarchy
        """
        edit = dummy_awaitable_callable
        try:
            await self._ensure_response_to_interaction(interaction)
            edit = interaction.edit_original_response  # type:ignore[assignment]

            raise error
        except app_commands.CommandInvokeError as d_error:
            if isinstance(d_error.original, discord.errors.InteractionResponded):
                await edit(content=f"🕳️ {d_error.original}")
            elif isinstance(d_error.original, discord.errors.Forbidden):
                await edit(content=f"🕳️ `{type(d_error.original).__name__}` : {d_error.original.text}")
            else:
                await edit(content=f"🕳️ `{type(d_error.original).__name__}` : {d_error.original}")
        except app_commands.CheckFailure as d_error:
            if isinstance(d_error, app_commands.errors.CommandOnCooldown):
                await edit(content=f"🕳️ Command is on cooldown, wait `{str(d_error).split(' ')[7]}` !")
            else:
                await edit(content=f"🕳️ `{type(d_error).__name__}` : {d_error}")
        except app_commands.CommandNotFound:
            msg = """
            🕳️ Command was not found... seems to be a discord bug, probably due to desynchronization.

            Maybe there are multiple commands with the same name, you should try the other one.
            """
            await edit(content=msg)
        except (
            app_commands.TransformerError,
            app_commands.CommandLimitReached,
            app_commands.CommandAlreadyRegistered,
            app_commands.CommandSignatureMismatch,
        ) as e:
            self.logger.error("get_app_command_error", e)
            raise

    @tasks.loop(minutes=1.0)
    async def update_status(self) -> None:
        count = self._orchestrator.get_server_count()
        await self.bot.change_presence(
            activity=discord.Activity(name=f"{count} servers", type=discord.ActivityType.watching),
        )

    @update_status.before_loop
    async def before_status(self) -> None:
        await self.bot.wait_until_ready()

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

        1. **Add your server details** → {await get_command_mention(self.bot.tree, "servers", "add")}
        2. **Create a player group** → {await get_command_mention(self.bot.tree, "playergroups", "add")}
        3. **Configure bot permissions** → You probably want to edit the permissions of the bot to only allow certain
           roles to use it. You can do this by right-clicking the bot icon in the server and selecting "Apps" and then
           "Manage Server Integration".

        That's all there is to it! Thanks for using The Polebot!
        """
        embed = discord.Embed(
            title="Thank you for adding me 👋",
            description=inspect.cleandoc(markdown),
            color=discord.Colour(7722980),
        ).set_image(url="https://github.com/bwcc-clan/polebot/blob/main/assets/polebot_banner.png?raw=true")

        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        self.bot.logger.debug("on_guild_remove, guild=%d", guild.id)
        await self._orchestrator.delete_guild_data(guild.id)


async def setup(bot: commands.Bot) -> None:
    if not isinstance(bot, Polebot):
        raise TypeError("This cog is designed to be used with Polebot.")
    await bot.add_cog(_events(bot))
