import asyncio
import json
import logging
from collections.abc import Iterable

from aiohttp import ClientConnectorDNSError, ContentTypeError
from bson import ObjectId
from lagom import Container

from crcon.exceptions import ApiClientError
from crcon.server_connection_details import ServerConnectionDetails
from polebot.exceptions import DatastoreError, DuplicateKeyError
from polebot.models import GuildPlayerGroup, GuildServer
from polebot.services import cattrs_helpers
from polebot.services.player_matcher import PlayerMatcher, PlayerProperties
from polebot.services.settings_loader._settings_loader import SettingsLoader

from .app_config import AppConfig
from .composition_root import begin_server_context, create_api_client
from .container_provider import ContainerProvider
from .discord.bot import make_bot
from .services.polebot_database import PolebotDatabase
from .services.server_controller import ServerController

_logger = logging.getLogger(__name__)


class OrchestrationError(Exception):
    """Exception raised by the orchestrator."""

    def __init__(self, message: str) -> None:
        """Creates a new instance of `OrchestrationError`.

        Args:
            message (str): The error message.
        """
        self.message = message
        super().__init__(self.message)


class Orchestrator:
    def __init__(
        self,
        container_provider: ContainerProvider,
        db: PolebotDatabase,
        stop_event: asyncio.Event,
        app_config: AppConfig,
        logger: logging.Logger | None = None,
    ) -> None:
        self._container_provider = container_provider
        self.db = db
        self._stop_event = stop_event
        self._app_config = app_config
        self._logger = logger or _logger

        self._converter = cattrs_helpers.make_params_converter()
        self._bot = make_bot(self, self._container_provider.container)
        self._tg = asyncio.TaskGroup()
        self._db = container_provider.container[PolebotDatabase]
        self._settings_loader = SettingsLoader()
        self._server_controllers: dict[ObjectId, ServerController] = {}

    async def run(self) -> None:
        self._logger.info("Orchestrator started")

        servers = await self._get_servers()

        async with self._tg:
            self._tg.create_task(self._run_polebot(), name="polebot")

            for server in servers:
                self._tg.create_task(
                    self._run_server_controller(server, self._container_provider.container),
                    name=f"server-controller-{server.id}",
                )

        self._logger.info("Orchestrator stopped")

    async def add_guild_server(self, guild_id: int, label: str, crcon_details: ServerConnectionDetails) -> str:
        result = await self._attempt_connect_to_server(crcon_details)
        if not result[0]:
            message = f"Unable to connect to the server with the details provided: {result[1]}"
            raise OrchestrationError(message)

        server_name = result[1]
        guild_server = GuildServer(
            guild_id=guild_id,
            label=label,
            name=server_name,
            crcon_details=crcon_details,
        )
        try:
            await self.db.insert(guild_server)
        except DatastoreError as ex:
            self._logger.warning("Unable to add server", exc_info=ex)
            content = f"Unable to add server {server_name}."
            raise OrchestrationError(content) from None
        else:
            return server_name

    async def remove_guild_server(self, guild_id: int, label: str) -> None:
        guild_server = await self.db.find_one(
            GuildServer,
            guild_id=guild_id,
            attr_name="label",
            attr_value=label,
        )
        if guild_server:
            try:
                await self.db.delete(GuildServer, guild_server.id)
            except DatastoreError as ex:
                self._logger.error("Error removing server", exc_info=ex)
                raise OrchestrationError(f"Unable to remove server {label}.") from None
        else:
            raise OrchestrationError(f"No server labelled '{label}' exists.")

    async def get_guild_servers(self, guild_id: int) -> list[GuildServer]:
        return await self.db.fetch_all(GuildServer, guild_id, sort="label")

    async def get_guild_server(self, guild_id: int, label: str) -> GuildServer | None:
        return await self.db.find_one(
            GuildServer,
            guild_id=guild_id,
            attr_name="label",
            attr_value=label,
        )

    async def get_server_votemap_settings(self, guild_id: int, server_label: str) -> str:
        guild_server = await self.db.find_one(
            GuildServer,
            guild_id=guild_id,
            attr_name="label",
            attr_value=server_label,
        )
        if not guild_server:
            raise OrchestrationError(f"Server {server_label} not found")
        if not guild_server.weighting_parameters:
            raise OrchestrationError(f"Server {server_label} does not have any votemap settings")
        try:
            content = self._converter.unstructure(guild_server.weighting_parameters)
            json_contents = json.dumps(content, indent=4)
            return json_contents
        except UnicodeEncodeError:
            return f"Server {server_label} settings could not be downloaded"

    async def upload_server_votemap_settings(self, guild_id: int, server_label: str, file_contents: str) -> GuildServer:
        result = self._settings_loader.load_weighting_parameters(file_contents)
        if isinstance(result, list):
            raise OrchestrationError(
                "Invalid settings file:\n\n" + "\n\n".join([f"{e.message} at {e.path}" for e in result]),
            )

        guild_server = await self.db.find_one(
            GuildServer,
            guild_id=guild_id,
            attr_name="label",
            attr_value=server_label,
        )
        if not guild_server:
            raise OrchestrationError(f"No server with label {server_label} found")

        guild_server.weighting_parameters = result
        self._server_controllers[guild_server.id].weighting_parameters = result
        try:
            guild_server = await self.db.update(guild_server)
        except DatastoreError as ex:
            raise OrchestrationError(f"Unable to save votemap settings for server {server_label}.") from ex
        else:
            return guild_server

    async def set_server_votemap_enabled(
        self,
        guild_id: int,
        server_label: str,
        enabled: bool,
    ) -> tuple[GuildServer, bool]:
        guild_server = await self.db.find_one(
            GuildServer,
            guild_id=guild_id,
            attr_name="label",
            attr_value=server_label,
        )
        if not guild_server:
            raise OrchestrationError(f"Server {server_label} not found")
        if not guild_server.weighting_parameters:
            raise OrchestrationError(
                f"Server {server_label} does not have any votemap settings, can't enable votemap bot",
            )
        try:
            if guild_server.enable_votemap != enabled:
                self._server_controllers[guild_server.id].votemap_enabled = enabled
                guild_server.enable_votemap = enabled
                guild_server = await self.db.update(guild_server)
                self._logger.info(
                    "Votemap bot %s for server %s",
                    "enabled" if enabled else "disabled",
                    guild_server.id,
                )
            return (guild_server, guild_server.enable_votemap != enabled)
        except DatastoreError as ex:
            raise OrchestrationError(f"Unable to save changes for server {server_label}.") from ex

    async def get_player_groups(self, guild_id: int) -> list[GuildPlayerGroup]:
        return await self.db.fetch_all(GuildPlayerGroup, guild_id, sort="label")

    async def add_player_group(self, guild_id: int, label: str, selector: str) -> GuildPlayerGroup:
        player_group = GuildPlayerGroup(
            guild_id=guild_id,
            label=label,
            selector=selector,
        )
        try:
            player_group = await self.db.insert(player_group)
        except DatastoreError as ex:
            self._logger.warning("Failed to add player group", exc_info=ex)
            if isinstance(ex, DuplicateKeyError):
                raise OrchestrationError(f"Player group {label} already exists.") from ex
            else:
                raise OrchestrationError(f"Unable to add player group {label}.") from ex
        return player_group

    async def remove_player_group(self, guild_id: int, label: str) -> None:
        player_group = await self.db.find_one(
            GuildPlayerGroup,
            guild_id=guild_id,
            attr_name="label",
            attr_value=label,
        )
        if player_group:
            try:
                await self.db.delete(GuildPlayerGroup, player_group.id)
                self._logger.info("Player group %s removed", player_group.id)
            except DatastoreError as ex:
                self._logger.error("Error removing player group %s", player_group.id, exc_info=ex)
                raise OrchestrationError(f"Unable to remove player group {label}.") from None
        else:
            raise OrchestrationError(f"No player group labelled '{label}' exists.")

    async def send_message_to_player_group(
        self, guild_id: int, server: str, group: str, message: str,
    ) -> Iterable[PlayerProperties]:
        guild_server = await self.db.find_one(
            GuildServer,
            guild_id=guild_id,
            attr_name="label",
            attr_value=server,
        )
        if not guild_server:
            raise OrchestrationError(f"Server {server} not found")

        player_group = await self.db.find_one(
            GuildPlayerGroup,
            guild_id=guild_id,
            attr_name="label",
            attr_value=group,
        )
        if not player_group:
            raise OrchestrationError(f"Player group {group} not found")
        server_controller = self._server_controllers.get(guild_server.id)
        if not server_controller:
            raise OrchestrationError(f"Server controller for {server} not found")
        player_matcher = PlayerMatcher(player_group.selector)
        players = await server_controller.send_group_message(player_matcher, message)
        self._logger.info("Message sent to player group %s(%s)", player_group.label, player_group.id)
        return players

    async def _run_server_controller(
        self,
        server: GuildServer,
        container: Container,
    ) -> None:
        """Runs the server controller for the specified server configuration.

        Creates a DI context for the server, then instantiates and runs the server controller from within that context.

            server (GuildServer): The server configuration.
            container (Container): The root DI container.
        """
        _logger.info("Starting server controller for %s", server.name)
        with begin_server_context(
            container,
            server.crcon_details,
            self._stop_event,
        ) as context_container:
            server_controller = context_container[ServerController]
            server_controller.weighting_parameters = server.weighting_parameters
            if server.enable_votemap:
                server_controller.votemap_enabled = True

            self._server_controllers[server.id] = server_controller

            async with server_controller:
                await server_controller.run()

        self._server_controllers.pop(server.id, None)
        _logger.info("Server controller for %s stopped", server.name)

    async def _run_polebot(self) -> None:
        await self._bot.start(self._app_config.discord_token)

    async def _get_servers(self) -> list[GuildServer]:
        return await self._db.fetch_all(GuildServer, None, sort=None)

    async def _attempt_connect_to_server(self, crcon_details: ServerConnectionDetails) -> tuple[bool, str]:
        api_client = create_api_client(self._container_provider.container, crcon_details)
        result: tuple[bool, str] = (False, "Oops, an error occurred!")
        async with api_client:
            try:
                status = await api_client.get_status()
            except ApiClientError as ex:
                if ex.error == "You must be logged in to use this":
                    error = "Invalid API Key"
                else:
                    error = f"Server returned an error: {ex.error}"
                result = (False, error)
            except ClientConnectorDNSError:
                result = (False, f"Server `{crcon_details.api_url}` not found")
            except ContentTypeError:
                result = (False, f"`{crcon_details.api_url}` does not have a CRCON API endpoint")
            except Exception as ex:
                self._logger.error("Unhandled error contacting new server", exc_info=ex)
                raise
            else:
                result = (True, status.name)
        return result
