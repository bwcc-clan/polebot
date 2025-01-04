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

from .api_client import CRCONApiClient
from .api_models import LogStreamObject
from .app_config import AppConfig
from .log_stream_client import CRCONLogStreamClient
from .map_selector.selector import MapSelector
from .server_manager import ServerManager
from .server_params import ServerParameters
from .votemap_manager import VotemapManager

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


container = Container()

_container_initialized = False


def init_container(app_config: AppConfig, loop: asyncio.AbstractEventLoop) -> Container:
    """Initialises the dependency injection container.

    Args:
        app_config (AppConfig): The application configuration.
        loop (asyncio.AbstractEventLoop): The event loop.

    Returns:
        Container: The initialised container.
    """
    global _container_initialized

    if _container_initialized:
        return container

    container[AppConfig] = app_config
    container[AsyncIOMotorClient] = AsyncIOMotorClient(app_config.mongodb.connection_string, tz_aware=True)
    container[AsyncIOMotorDatabase] = container[AsyncIOMotorClient][app_config.mongodb.db_name]

    @dependency_definition(container, singleton=True)
    def _get_event_loop() -> asyncio.AbstractEventLoop:
        return loop

    define_context_dependency(container, ServerManager)
    define_context_dependency(container, CRCONLogStreamClient)
    define_context_dependency(container, VotemapManager)
    define_context_dependency(container, MapSelector)
    define_context_dependency(container, CRCONApiClient)

    _container_initialized = True
    return container


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
    if stop_event:
        context_container[asyncio.Event] = stop_event
    context_container[asyncio.Queue[LogStreamObject]] = asyncio.Queue[LogStreamObject](_QUEUE_SIZE)
    return context_container


# def create_server_manager(
#     container: Container,
#     server_params: ServerParameters,
#     stop_event: asyncio.Event | None = None,
# ) -> ServerManager:
#     factory = container.magic_partial(ServerManager)
#     server_manager = factory(server_params, stop_event=stop_event)
#     return server_manager
