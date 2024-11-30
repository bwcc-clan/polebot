import asyncio
import contextlib
import logging
from types import TracebackType
from typing import Optional, Self

from .crcon_server_details import CRCONServerDetails
from .models import LogStreamObject, VoteMapUserConfig

logger = logging.getLogger(__name__)


class VotemapManager(contextlib.AbstractAsyncContextManager):
    def __init__(self, server_details: CRCONServerDetails, queue: asyncio.Queue[LogStreamObject]) -> None:
        self.server_details = server_details
        self.votemap_config: Optional[VoteMapUserConfig] = None
        self._task: asyncio.Task[None] | None = None
        self._queue = queue
        self._exit_stack = contextlib.AsyncExitStack()


    async def __aenter__(self) -> Self:
        await self._exit_stack.__aenter__()
        return self

    async def __aexit__(
        self, exc_t: type[BaseException] | None, exc_v: BaseException | None, exc_tb: TracebackType | None
    )  -> bool:
        return await self._exit_stack.__aexit__(exc_t, exc_v, exc_tb)


    def start(self, task_group: asyncio.TaskGroup) -> asyncio.Task[None]:
        self._task = task_group.create_task(self._run(), name="votemap-manager")
        return self._task

    def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()

    async def _run(self) -> None:
        try:
            while True:
                log = await self._queue.get()
                print(log)
        except asyncio.CancelledError:
            logger.info("Cancellation received, shutting down")
            raise


    async def _read_settings(self) -> None:
        pass
