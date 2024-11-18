

import asyncio
import contextlib
import logging
from typing import Optional

from .crcon_server_details import CRCONServerDetails
from .log_stream_client import AllLogTypes, CRCONLogStreamClient
from .votemap_manager import VotemapManager

logger = logging.getLogger(__name__)

class ServerManager:
    def __init__(self, server_details: CRCONServerDetails, stop_event: Optional[asyncio.Event] = None,) -> None:
        self.server_details = server_details

        self.stop_event = stop_event
        self.log_stream_client = CRCONLogStreamClient(self.server_details, log_types=[AllLogTypes.match_start])
        self.votemap_manager = VotemapManager(self.server_details)
        self._monitor_task: asyncio.Task[None] | None = None
        self._tasks: list[asyncio.Task] = []
        self._monitor_stopping = False

    async def run(self) -> None:
        with contextlib.suppress(ExceptionGroup):
            async with asyncio.TaskGroup() as tg:
                if self.stop_event:
                    self._monitor_task = tg.create_task(self._monitor_signal(), name="signal-monitor")
                    self._tasks.append(self._monitor_task)
                self._tasks.append(tg.create_task(self.log_stream_client.run(), name="log-stream-client"))
                self._tasks.append(tg.create_task(self.votemap_manager.run(), name="votemap-manager"))

        for task in self._tasks:
            logger.debug("Task %s: cancelled=%s", task.get_name(), task.cancelled())
            if not task.cancelled() and task.exception():
                logger.exception(f"Task {task.get_name()} failed", exc_info=task.exception())
        self._tasks.clear()

    def stop(self) -> None:
        self.log_stream_client.stop()
        self.votemap_manager.stop()
        if self._monitor_task and not self._monitor_task.done() and not self._monitor_stopping:
            self._monitor_task.cancel()

    async def _monitor_signal(self) -> None:
        if not self.stop_event:
            raise RuntimeError("Stop event not defined")
        try:
            await self.stop_event.wait()
            logger.info("Stop event signalled, stopping")
            self._monitor_stopping = True
            self.stop()
        except asyncio.CancelledError:
            logger.info("Stop event monitor cancelled")
