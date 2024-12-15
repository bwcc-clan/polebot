import asyncio
import contextlib
import logging
from collections.abc import Iterable
from types import TracebackType
from typing import Optional, Self

from cache import AsyncTTL

from .api_client import CRCONApiClient
from .api_models import (
    Layer,
    LogMessageType,
    LogStreamObject,
    ServerStatus,
    VoteMapUserConfig,
)
from .crcon_server_details import CRCONServerDetails

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
                await self._receive_and_process_message()

        except asyncio.CancelledError:
            logger.info("Cancellation received, shutting down")
            raise

    async def _receive_and_process_message(self) -> None:
        log = await self._queue.get()
        try:
            logger.debug("Message received of type %s", log.log.action)
            match log.log.action:
                case LogMessageType.match_start | LogMessageType.team_switch:
                    await self._process_map_started()
                case _:
                    logger.warning("Unsupported log message type: %s", log.log.action)
        finally:
            self._queue.task_done()

    async def _process_map_started(self) -> None:
        logger.debug("Processing map started")
        status = await self._get_server_status()
        layers = await self._get_server_maps()
        votemap_config = await self._get_votemap_config()
        map_history = [status.map.map.id]
        print(status)
        print(layers)
        print(votemap_config)


    @AsyncTTL(time_to_live=10)
    async def _get_server_status(self) -> ServerStatus:
        assert self._api_client
        return await self._api_client.get_status()


    @AsyncTTL(time_to_live=600)
    async def _get_server_maps(self) -> Iterable[Layer]:
        assert self._api_client
        return await self._api_client.get_maps()

    @AsyncTTL(time_to_live=600)
    async def _get_votemap_config(self) -> VoteMapUserConfig:
        assert self._api_client
        return await self._api_client.get_votemap_config()
