import asyncio
import contextlib
import logging
from types import TracebackType
from typing import Optional, Self

from .api_client import CRCONApiClient
from .crcon_server_details import CRCONServerDetails
from .models import LogMessageType, LogStreamObject, VoteMapUserConfig

logger = logging.getLogger(__name__)


class VotemapManager(contextlib.AbstractAsyncContextManager):
    def __init__(
        self,
        server_details: CRCONServerDetails,
        queue: asyncio.Queue[LogStreamObject],
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._server_details = server_details
        self._votemap_config: Optional[VoteMapUserConfig] = None
        self._queue = queue
        self._loop = loop
        self._exit_stack = contextlib.AsyncExitStack()
        self._api_client: CRCONApiClient | None = None

    async def __aenter__(self) -> Self:
        await self._exit_stack.__aenter__()
        self._api_client = await self._exit_stack.enter_async_context(
            CRCONApiClient(server_details=self._server_details, loop=self._loop)
        )
        return self

    async def __aexit__(
        self, exc_t: type[BaseException] | None, exc_v: BaseException | None, exc_tb: TracebackType | None
    ) -> bool:
        return await self._exit_stack.__aexit__(exc_t, exc_v, exc_tb)

    async def run(self) -> None:
        """
        Runs the votemap manager. Will continue indefinitely unless a fatal exception occurs. This should be called as
        an async task, which can be cancelled to terminate processing.
        """
        if self._api_client is None:
            raise RuntimeError("VotemapManager context must be entered")

        try:
            while True:
                log = await self._queue.get()
                print(log)
                match log.log.action:
                    case LogMessageType.match_end:
                        await self._process_map_ended()
                    case _:
                        logger.warning("Unsupported log message type: %s", log.log.action)

        except asyncio.CancelledError:
            logger.info("Cancellation received, shutting down")
            raise

    async def _process_map_ended(self) -> None:
        assert self._api_client
        layers = await self._api_client.get_maps()

    async def _read_settings(self) -> None:
        pass
