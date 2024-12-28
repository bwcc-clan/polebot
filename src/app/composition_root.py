import asyncio
from collections.abc import Iterable
from contextlib import AbstractContextManager
from typing import Optional, TypeVar

from lagom import (
    Container,
    ContextContainer,
    context_dependency_definition,
    dependency_definition,
)
from typeguard import TypeCheckError, check_type

from .api_client import CRCONApiClient
from .api_models import LogStreamObject
from .config import AppConfig, ServerConfig
from .log_stream_client import CRCONLogStreamClient
from .map_selector import MapSelector
from .server_manager import ServerManager
from .votemap_manager import VotemapManager

X = TypeVar("X")


def define_context_dependency(ctr: Container, dep_type: type[X]) -> None:
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
    global _container_initialized

    if _container_initialized:
        return container

    container[AppConfig] = app_config

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


# context_container = ContextContainer(
#     container,
#     context_types=[],
#     context_singletons=[AnalyzeTextFileProcessor, AnalyzeRegisterEntityProcessor, DocumentAnalyzer],
# )

_QUEUE_SIZE = 1000


def begin_server_context(
    container: Container,
    server_config: ServerConfig,
    stop_event: Optional[asyncio.Event] = None,
) -> ContextContainer:
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
    context_container[ServerConfig] = server_config
    if stop_event:
        context_container[asyncio.Event] = stop_event
    context_container[asyncio.Queue[LogStreamObject]] = asyncio.Queue[LogStreamObject](_QUEUE_SIZE)
    return context_container


def create_server_manager(
    container: Container,
    server_config: ServerConfig,
    stop_event: Optional[asyncio.Event] = None,
) -> ServerManager:
    factory = container.magic_partial(ServerManager)
    server_manager = factory(server_config, stop_event=stop_event)
    return server_manager
