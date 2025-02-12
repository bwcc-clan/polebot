import asyncio
import json
import logging

from aiohttp import ClientConnectorDNSError, ContentTypeError
from lagom import Container

from crcon.exceptions import ApiClientError
from crcon.server_connection_details import ServerConnectionDetails
from polebot.exceptions import DatastoreError
from polebot.models import GuildServer
from polebot.services import cattrs_helpers
from polebot.services.settings_loader._settings_loader import SettingsLoader

from .app_config import AppConfig
from .composition_root import begin_server_context, create_api_client
from .discord.bot import make_bot
from .services.di import ContainerProvider
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
        try:
            guild_server = await self.db.update(guild_server)
        except DatastoreError as ex:
            raise OrchestrationError(f"Unable to save votemap settings for server {server_label}.") from ex
        else:
            return guild_server

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
            async with server_controller:
                await server_controller.run()

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
