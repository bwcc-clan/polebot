"""Composition root that configures dependency injection for the application."""

import asyncio
from collections.abc import Iterable
from contextlib import AbstractContextManager
from typing import TypeVar

from lagom import (
    Container,
    ContextContainer,
    context_dependency_definition,
    dependency_definition,
)
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typeguard import TypeCheckError, check_type

from crcon import ApiClient, LogStreamClient, LogStreamClientSettings
from crcon.api_models import LogStreamObject
from crcon.server_connection_details import ServerConnectionDetails
from polebot.container_provider import ContainerProvider
from polebot.services.message_sender import MessageSender
from polebot.services.vip_manager import VipManager

from .app_config import AppConfig
from .services.polebot_database import PolebotDatabase
from .services.server_controller import ServerController
from .services.votemap_processor import VotemapProcessor

X = TypeVar("X")


def define_context_dependency(ctr: Container, dep_type: type[X]) -> None:
    """Defines a context dependency for a given container and provides a factory method.

    Args:
        ctr (Container): The container to define the dependency in.
        dep_type (type[X]): The type of the dependency to define.

    Yields:
        X: The dependency instance.
    """

    @context_dependency_definition(ctr)
    def _factory(c: Container) -> Iterable[dep_type]:  # type: ignore[valid-type]
        instance = c.resolve(dep_type, skip_definitions=True)
        try:
            cm = check_type(instance, AbstractContextManager[X])
            with cm:
                yield cm
        except TypeCheckError:
            yield instance


_container = Container()

_container_initialized = False


async def create_polebot_database(app_config: AppConfig, mongo_db: AsyncIOMotorDatabase) -> PolebotDatabase:
    db = PolebotDatabase(app_config, mongo_db)
    await db.initialize()
    return db


async def init_container(app_config: AppConfig, loop: asyncio.AbstractEventLoop) -> Container:
    """Initialises the dependency injection container.

    Args:
        app_config (AppConfig): The application configuration.
        loop (asyncio.AbstractEventLoop): The event loop.

    Returns:
        Container: The initialised container.
    """
    global _container_initialized

    if _container_initialized:
        return _container

    # *** SINGLETON ***
    _container[ContainerProvider] = ContainerProvider(_container)
    _container[AppConfig] = app_config
    mongo_client: AsyncIOMotorClient = AsyncIOMotorClient(app_config.mongodb.connection_string, tz_aware=True)
    mongo_db: AsyncIOMotorDatabase = mongo_client[app_config.mongodb.db_name]
    _container[AsyncIOMotorClient] = mongo_client
    _container[AsyncIOMotorDatabase] = mongo_db
    _container[PolebotDatabase] = await create_polebot_database(app_config, mongo_db)

    @dependency_definition(_container, singleton=True)
    def _get_event_loop() -> asyncio.AbstractEventLoop:
        return loop

    @dependency_definition(_container, singleton=True)
    def _get_crcon_log_stream_client_settings(c: Container) -> LogStreamClientSettings:
        return LogStreamClientSettings(
            max_websocket_connection_attempts=c[AppConfig].max_websocket_connection_attempts,
        )

    # *** LIFETIME SCOPE ***
    define_context_dependency(_container, ServerController)
    define_context_dependency(_container, LogStreamClient)
    define_context_dependency(_container, VotemapProcessor)
    define_context_dependency(_container, MessageSender)
    define_context_dependency(_container, ApiClient)
    define_context_dependency(_container, VipManager)

    _container_initialized = True
    return _container


_QUEUE_SIZE = 1000


def begin_server_context(
    container: Container,
    connection_details: ServerConnectionDetails,
    stop_event: asyncio.Event | None = None,
) -> ContextContainer:
    """Begin the server context by creating a nested DI container context.

    Args:
        container (Container): The parent container.
        connection_details (ServerConnectionDetails): The connection details for the CRCON server within this context.
        stop_event (asyncio.Event | None, optional): If specified, an event that terminates the application. Defaults to
        None.

    Returns:
        ContextContainer: _description_
    """
    context_container = ContextContainer(
        container,
        context_types=[],
        context_singletons=[ServerController, LogStreamClient, VotemapProcessor, MessageSender, ApiClient, VipManager],
    )
    context_container[ServerConnectionDetails] = connection_details
    if stop_event:
        context_container[asyncio.Event] = stop_event
    context_container[asyncio.Queue[LogStreamObject]] = asyncio.Queue[LogStreamObject](_QUEUE_SIZE)
    return context_container


def create_api_client(
    container: Container,
    crcon_details: ServerConnectionDetails,
) -> ApiClient:
    factory = container.magic_partial(ApiClient)
    api_client = factory(crcon_details)
    return api_client
