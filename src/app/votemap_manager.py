import asyncio
import contextlib
import logging
from collections import deque
from collections.abc import Iterable
from itertools import chain
from types import TracebackType
from typing import Any, Optional, Self

import cachetools
import cachetools.keys

from .api_client import CRCONApiClient
from .api_models import (
    Layer,
    LogMessageType,
    LogStreamObject,
    ServerStatus,
    VoteMapUserConfig,
)
from .cache_utils import CacheItem, cache_item_ttu, ttl_cached
from .config import ServerConfig
from .map_selector import MapSelector

logger = logging.getLogger(__name__)


class VotemapManager(contextlib.AbstractAsyncContextManager):
    def __init__(
        self,
        server_config: ServerConfig,
        queue: asyncio.Queue[LogStreamObject],
        api_client: CRCONApiClient,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._server_config = server_config
        self._votemap_config: Optional[VoteMapUserConfig] = None
        self._queue = queue
        self._api_client = api_client
        self._loop = loop
        self._exit_stack = contextlib.AsyncExitStack()
        self._cache = cachetools.TLRUCache(maxsize=100, ttu=cache_item_ttu)
        self._layer_history: deque[str] = deque(maxlen=10)

    async def __aenter__(self) -> Self:
        await self._exit_stack.__aenter__()
        await self._exit_stack.enter_async_context(self._api_client)
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

    def get_cache(self, cache_hint: Optional[str] = None) -> cachetools.TLRUCache[Any, CacheItem[Any]]:
        return self._cache

    async def _receive_and_process_message(self) -> None:
        """
        This is the main message processing loop. It will block until a message is received from the queue, then process
        it. It swallows all Exceptions (therefore not system exceptions).

        Note that the message types are filtered in the log stream client, so we only expect to receive messages that
        pass the filter. If you add new message types to the filter, you will need to update this method to handle them,
        and vice-versa. Likewise if you remove message types. Keep them in sync. The filter is configured in the server
        manager class.
        """

        log = await self._queue.get()
        try:
            logger.debug("Message received of type %s", log.log.action)
            match log.log.action:
                case LogMessageType.match_start:
                    await self._process_map_started()
                case LogMessageType.match_end:
                    await self._process_map_ended()
                case _:
                    logger.warning("Unsupported log message type: %s", log.log.action)
        except Exception as ex:
            logger.error("Error processing message", exc_info=ex)
        finally:
            self._queue.task_done()

    async def _process_map_started(self) -> None:
        logger.info("Processing map started")
        selection = list(await self._generate_votemap_selection())
        if len(selection):
            await self._set_votemap_selection(selection)

    async def _process_map_ended(self) -> None:
        logger.info("Processing map ended")

        status = await self._get_server_status()
        logger.debug("Saving current map [%s] to layer history", status.map.id)
        current_map = status.map.id
        self._layer_history.appendleft(current_map)

    async def _generate_votemap_selection(self) -> Iterable[str]:
        logger.debug("Generating a votemap selection")
        status = await self._get_server_status()
        layers = await self._get_server_maps()
        votemap_config = await self._get_votemap_config()
        votemap_whitelist = await self._get_votemap_whitelist()
        layers = [layer for layer in layers if layer.id in votemap_whitelist]
        selector = MapSelector(
            server_status=status,
            layers=layers,
            server_config=self._server_config,
            votemap_config=votemap_config,
            recent_layer_history=self._layer_history,
        )
        selection = chain(selector._get_warfare(), selector._get_offensive(), selector._get_skirmish())
        logger.debug("Selection: [%s]", ",".join(selection))
        return selection

    async def _set_votemap_selection(self, selection: Iterable[str]) -> None:
        logger.info("Setting votemap selection to [%s]", ",".join(selection))
        assert self._api_client
        try:
            saved_votemap_whitelist = await self._get_votemap_whitelist()
            logger.info("Saved votemap whitelist = [%s]", ",".join(saved_votemap_whitelist))
            logger.debug("Setting votemap whitelist = [%s]", ",".join(selection))
            await self._api_client.set_votemap_whitelist(selection)
            await asyncio.sleep(2)
            logger.debug("Resetting votemap state")
            await self._api_client.reset_votemap_state()
            await asyncio.sleep(2)
            logger.debug("Restoring votemap whitelist")
            await self._api_client.set_votemap_whitelist(saved_votemap_whitelist)
            logger.info("Votemap selection set")

        except Exception as ex:
            logger.error("Error setting votemap selection", exc_info=ex)

    @ttl_cached(time_to_live=10)
    async def _get_server_status(self) -> ServerStatus:
        assert self._api_client
        logger.debug("Getting server status")
        return await self._api_client.get_status()

    @ttl_cached(time_to_live=60 * 60 * 8)
    async def _get_server_maps(self) -> Iterable[Layer]:
        assert self._api_client
        logger.debug("Getting server maps")
        return await self._api_client.get_maps()

    @ttl_cached(time_to_live=600)
    async def _get_votemap_config(self) -> VoteMapUserConfig:
        assert self._api_client
        logger.debug("Getting votemap config")
        return await self._api_client.get_votemap_config()

    async def _get_votemap_whitelist(self) -> Iterable[str]:
        assert self._api_client
        logger.debug("Getting votemap whitelist")
        return await self._api_client.get_votemap_whitelist()
