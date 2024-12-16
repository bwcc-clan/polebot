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

from .api_models import LogStreamObject
from .config import AppConfig
from .crcon_server_details import CRCONServerDetails
from .log_stream_client import CRCONLogStreamClient
from .server_manager import ServerManager

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

    define_context_dependency(container, CRCONLogStreamClient)

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
    server_details: CRCONServerDetails,
    stop_event: Optional[asyncio.Event] = None,
) -> ContextContainer:
    context_container = ContextContainer(
        container, context_types=[], context_singletons=[CRCONLogStreamClient]
    )
    context_container[CRCONServerDetails] = server_details
    if stop_event:
        context_container[asyncio.Event] = stop_event
    context_container[asyncio.Queue[LogStreamObject]] = asyncio.Queue[LogStreamObject](
        _QUEUE_SIZE
    )
    return context_container


def create_server_manager(
    container: Container,
    server_details: CRCONServerDetails,
    stop_event: Optional[asyncio.Event] = None,
) -> ServerManager:
    factory = container.magic_partial(ServerManager)
    server_manager = factory(server_details, stop_event=stop_event)
    return server_manager
