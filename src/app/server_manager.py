import asyncio
import contextlib
import logging
from types import TracebackType
from typing import NoReturn, Optional, Self

from .api_models import LogMessageType, LogStreamObject
from .config import ServerConfig
from .exceptions import TerminateTaskGroup
from .log_stream_client import CRCONLogStreamClient
from .votemap_manager import VotemapManager

logger = logging.getLogger(__name__)


_QUEUE_SIZE = 1000


class ServerManager(contextlib.AbstractAsyncContextManager):
    def __init__(
        self,
        server_config: ServerConfig,
        loop: asyncio.AbstractEventLoop,
        log_stream_client: CRCONLogStreamClient,
        votemap_manager: VotemapManager,
        stop_event: Optional[asyncio.Event] = None,
    ) -> None:
        self.server_config = server_config
        self._loop = loop
        self._stop_event = stop_event
        self._queue = asyncio.Queue[LogStreamObject](_QUEUE_SIZE)
        self._log_stream_client = log_stream_client
        self._votemap_manager = votemap_manager

        self._task_group: asyncio.TaskGroup | None = None
        self._exit_stack = contextlib.AsyncExitStack()

    async def __aenter__(self) -> Self:
        await self._exit_stack.__aenter__()

        await self._exit_stack.enter_async_context(self._votemap_manager)

        self._log_stream_client.log_types = [LogMessageType.match_start, LogMessageType.match_end]
        await self._exit_stack.enter_async_context(self._log_stream_client)

        return self

    async def __aexit__(
        self, exc_t: type[BaseException] | None, exc_v: BaseException | None, exc_tb: TracebackType | None
    ) -> bool:
        return await self._exit_stack.__aexit__(exc_t, exc_v, exc_tb)

    async def run(self) -> None:
        if not self._votemap_manager or not self._log_stream_client:
            raise RuntimeError("ServerManager context must be entered")

        tasks: list[asyncio.Task] = []
        try:
            async with asyncio.TaskGroup() as tg:
                self._task_group = tg
                if self._stop_event:
                    tasks.append(tg.create_task(self._monitor_stop_event(), name="stop-event-monitor"))
                tasks.append(tg.create_task(self._votemap_manager.run(), name="votemap-manager"))
                tasks.append(tg.create_task(self._log_stream_client.run(), name="log-stream-client"))
        except* TerminateTaskGroup:
           pass
        finally:
            self._task_group = None

        for task in tasks:
            logger.debug("Task %s: cancelled=%s", task.get_name(), task.cancelled())
            if not task.cancelled() and task.exception():
                logger.exception(f"Task {task.get_name()} failed", exc_info=task.exception())

    def stop(self) -> None:
        self._stop_internal(True)

    def _stop_internal(self, stop_monitor: bool) -> None:
        if self._task_group:
            # add an exception-raising task to force the group to terminate
            self._task_group.create_task(self._force_terminate_task_group())

    async def _monitor_stop_event(self) -> None:
        assert self._stop_event
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
