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

from .app_config import AppConfig
from .crcon.api_client import CRCONApiClient
from .crcon.api_models import LogStreamObject
from .crcon.log_stream_client import CRCONLogStreamClient
from .models import ServerCRCONDetails, ServerParameters
from .services.map_selector.selector import MapSelector
from .services.polebot_database import PolebotDatabase
from .services.server_manager import ServerManager
from .services.votemap_manager import VotemapManager

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

    _container[AppConfig] = app_config
    mongo_client: AsyncIOMotorClient = AsyncIOMotorClient(app_config.mongodb.connection_string, tz_aware=True)
    mongo_db: AsyncIOMotorDatabase = mongo_client[app_config.mongodb.db_name]
    _container[AsyncIOMotorClient] = mongo_client
    _container[AsyncIOMotorDatabase] = mongo_db
    _container[PolebotDatabase] = await create_polebot_database(app_config, mongo_db)

    @dependency_definition(_container, singleton=True)
    def _get_event_loop() -> asyncio.AbstractEventLoop:
        return loop

    define_context_dependency(_container, ServerManager)
    define_context_dependency(_container, CRCONLogStreamClient)
    define_context_dependency(_container, VotemapManager)
    define_context_dependency(_container, MapSelector)
    define_context_dependency(_container, CRCONApiClient)

    _container_initialized = True
    return _container


_QUEUE_SIZE = 1000


def begin_server_context(
    container: Container,
    server_params: ServerParameters,
    stop_event: asyncio.Event | None = None,
) -> ContextContainer:
    """Begin the server context by creating a nested DI container context.

    Args:
        container (Container): The parent container.
        server_params (ServerParameters): The server configuration for the server within this context.
        stop_event (asyncio.Event | None, optional): If specified, an event that terminates the application. Defaults to
        None.

    Returns:
        ContextContainer: _description_
    """
    context_container = ContextContainer(
        container,
        context_types=[],
        context_singletons=[
            ServerManager,
            CRCONLogStreamClient,
            VotemapManager,
            MapSelector,
            CRCONApiClient,
        ],
    )
    context_container[ServerParameters] = server_params
    context_container[ServerCRCONDetails] = server_params.crcon_details
    if stop_event:
        context_container[asyncio.Event] = stop_event
    context_container[asyncio.Queue[LogStreamObject]] = asyncio.Queue[LogStreamObject](_QUEUE_SIZE)
    return context_container


def create_api_client(
    container: Container,
    crcon_details: ServerCRCONDetails,
) -> CRCONApiClient:
    factory = container.magic_partial(CRCONApiClient)
    api_client = factory(crcon_details)
    return api_client
