"""This module contains the ServerManager class.

This class is responsible for managing the server lifecycle of a single CRCON server instance.
"""

import asyncio
import contextlib
import logging
from types import TracebackType
from typing import NoReturn, Self

from crcon import LogStreamClient
from crcon.api_models import LogMessageType, LogStreamObject

from ..exceptions import TerminateTaskGroup
from ..models import ServerParameters
from .votemap_processor import VotemapProcessor

logger = logging.getLogger(__name__)


_QUEUE_SIZE = 1000


class ServerController(contextlib.AbstractAsyncContextManager):
    """Responsible for controlling a single CRCON server instance."""
    def __init__(
        self,
        server_params: ServerParameters,
        loop: asyncio.AbstractEventLoop,
        log_stream_client: LogStreamClient,
        votemap_processor: VotemapProcessor,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """Initialise the server manager.

        Args:
            server_params (ServerParameters): The server parameters.
            loop (asyncio.AbstractEventLoop): The event loop to use for async operations.
            log_stream_client (LogStreamClient): The log stream client to use for log message retrieval.
            votemap_processor (VotemapProcessor): The votemap manager to use for votemap selection.
            stop_event (asyncio.Event | None, optional): If specified, an event that will stop the instance when fired.
        """
        self._server_params = server_params
        self._loop = loop
        self._stop_event = stop_event
        self._queue = asyncio.Queue[LogStreamObject](_QUEUE_SIZE)
        self._log_stream_client = log_stream_client
        self._votemap_processor = votemap_processor

        self._task_group: asyncio.TaskGroup | None = None
        self._exit_stack = contextlib.AsyncExitStack()

    async def __aenter__(self) -> Self:
        """This method is a part of the context manager protocol. It is called when entering the context manager."""
        await self._exit_stack.__aenter__()

        await self._exit_stack.enter_async_context(self._votemap_processor)

        self._log_stream_client.log_types = [LogMessageType.match_start, LogMessageType.match_end]
        await self._exit_stack.enter_async_context(self._log_stream_client)

        return self

    async def __aexit__(
        self, exc_t: type[BaseException] | None, exc_v: BaseException | None, exc_tb: TracebackType | None,
    ) -> bool:
        """This method is a part of the context manager protocol. It is called when exiting the context manager."""
        return await self._exit_stack.__aexit__(exc_t, exc_v, exc_tb)

    async def run(self) -> None:
        """Run the server manager."""
        if not self._votemap_processor or not self._log_stream_client:
            raise RuntimeError("ServerManager context must be entered")

        tasks: list[asyncio.Task] = []
        try:
            async with asyncio.TaskGroup() as tg:
                self._task_group = tg
                if self._stop_event:
                    tasks.append(tg.create_task(self._monitor_stop_event(), name="stop-event-monitor"))
                tasks.append(tg.create_task(self._votemap_processor.run(), name="votemap-manager"))
                tasks.append(tg.create_task(self._log_stream_client.run(), name="log-stream-client"))
        except* TerminateTaskGroup:
           pass
        finally:
            self._task_group = None

        for task in tasks:
            logger.debug("Task %s: cancelled=%s", task.get_name(), task.cancelled())
            if not task.cancelled() and task.exception():
                logger.exception("Task %s failed", task.get_name(), exc_info=task.exception())

    def stop(self) -> None:
        """Stop the server manager."""
        self._stop_internal(True)

    def _stop_internal(self, stop_monitor: bool) -> None:
        if self._task_group:
            # add an exception-raising task to force the group to terminate
            self._task_group.create_task(self._force_terminate_task_group())

    async def _monitor_stop_event(self) -> None:
        assert self._stop_event  # noqa: S101
        try:
            await self._stop_event.wait()
            logger.info("Stop event signalled, stopping")
            self._stop_internal(False)
        except asyncio.CancelledError:
            logger.info("Stop event monitor cancelled")
            raise

    async def _force_terminate_task_group(self) -> NoReturn:
       """Used to force termination of a task group."""
       raise TerminateTaskGroup()
