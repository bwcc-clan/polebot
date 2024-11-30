import asyncio
import contextlib
import logging
from types import TracebackType
from typing import Optional, Self

from .crcon_server_details import CRCONServerDetails
from .log_stream_client import CRCONLogStreamClient, LogMessageType
from .models import LogStreamObject
from .votemap_manager import VotemapManager

logger = logging.getLogger(__name__)


_QUEUE_SIZE = 1000


class ServerManager(contextlib.AbstractAsyncContextManager):
    def __init__(
        self,
        server_details: CRCONServerDetails,
        loop: asyncio.AbstractEventLoop,
        stop_event: Optional[asyncio.Event] = None,
    ) -> None:
        self.server_details = server_details
        self._loop = loop

        self.stop_event = stop_event
        self._queue = asyncio.Queue[LogStreamObject](_QUEUE_SIZE)
        self.log_stream_client = CRCONLogStreamClient(
            server_details=self.server_details, queue=self._queue, log_types=[LogMessageType.match_start]
        )
        self.votemap_manager: VotemapManager | None = None
        self._monitor_task: asyncio.Task[None] | None = None
        self._exit_stack = contextlib.AsyncExitStack()

    async def __aenter__(self) -> Self:
        await self._exit_stack.__aenter__()
        self.votemap_manager = await self._exit_stack.enter_async_context(
            VotemapManager(self.server_details, self._queue)
        )
        return self

    async def __aexit__(
        self, exc_t: type[BaseException] | None, exc_v: BaseException | None, exc_tb: TracebackType | None
    ) -> bool:
        return await self._exit_stack.__aexit__(exc_t, exc_v, exc_tb)

    async def run(self) -> None:
        if not self.votemap_manager:
            raise RuntimeError("Context must be entered")

        tasks: list[asyncio.Task] = []
        with contextlib.suppress(ExceptionGroup):
            async with asyncio.TaskGroup() as tg:
                if self.stop_event:
                    self._monitor_task = tg.create_task(self._monitor_stop_event(), name="stop-event-monitor")
                    tasks.append(self._monitor_task)
                tasks.append(self.votemap_manager.start(tg))
                tasks.append(self.log_stream_client.start(tg))

        for task in tasks:
            logger.debug("Task %s: cancelled=%s", task.get_name(), task.cancelled())
            if not task.cancelled() and task.exception():
                logger.exception(f"Task {task.get_name()} failed", exc_info=task.exception())

    def stop(self) -> None:
        self._stop_internal(True)

    def _stop_internal(self, stop_monitor: bool) -> None:
        self.log_stream_client.stop()
        if self.votemap_manager:
            self.votemap_manager.stop()
        if stop_monitor and self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()

    async def _monitor_stop_event(self) -> None:
        if not self.stop_event:
            raise RuntimeError("Stop event not configured")
        try:
            await self.stop_event.wait()
            logger.info("Stop event signalled, stopping")
            self._stop_internal(False)
        except asyncio.CancelledError:
            logger.info("Stop event monitor cancelled")
            raise
