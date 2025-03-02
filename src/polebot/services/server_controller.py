"""This module contains the ServerController class.

This class is responsible for managing the server lifecycle of a single CRCON server instance.
"""

import asyncio
import contextlib
import logging
from collections.abc import Iterable
from types import TracebackType
from typing import NoReturn, Self

from crcon import LogStreamClient
from crcon.api_models import LogMessageType, LogStreamObject
from polebot.models import VipInfo, WeightingParameters
from polebot.services.message_sender import MessageSender
from polebot.services.player_matcher import PlayerMatcher, PlayerProperties
from polebot.services.vip_manager import VipManager

from ..exceptions import TerminateTaskGroup
from .votemap_processor import VotemapProcessor

logger = logging.getLogger(__name__)


_QUEUE_SIZE = 1000


class ServerController(contextlib.AbstractAsyncContextManager):
    """Responsible for controlling a single CRCON server instance."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        log_stream_client: LogStreamClient,
        votemap_processor: VotemapProcessor,
        message_sender: MessageSender,
        vip_manager: VipManager,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """Initialise the server manager.

        Args:
            loop (asyncio.AbstractEventLoop): The event loop to use for async operations.
            log_stream_client (LogStreamClient): The log stream client to use for log message retrieval.
            votemap_processor (VotemapProcessor): The votemap manager to use for votemap selection.
            message_sender (MessageSender): The message sender to use for sending messages to players on the server.
            vip_manager (VipManager): The VIP manager to use for VIP information retrieval.
            stop_event (asyncio.Event | None, optional): If specified, an event that will stop the instance when fired.
        """
        self._loop = loop
        self._queue = asyncio.Queue[LogStreamObject](_QUEUE_SIZE)
        self._log_stream_client = log_stream_client
        self._votemap_processor = votemap_processor
        self._message_sender = message_sender
        self._vip_manager = vip_manager
        self._stop_event = stop_event

        self._task_group: asyncio.TaskGroup | None = None
        self._exit_stack = contextlib.AsyncExitStack()
        self._task_group_ended_event = asyncio.Event()
        self._task_group_ended_event.set()  # signal initially to indicate task group is not running

    @property
    def votemap_enabled(self) -> bool:
        return self._votemap_processor.enabled

    @votemap_enabled.setter
    def votemap_enabled(self, value: bool) -> None:
        self._votemap_processor.enabled = value

    @property
    def weighting_parameters(self) -> WeightingParameters | None:
        return self._votemap_processor._weighting_parameters

    @weighting_parameters.setter
    def weighting_parameters(self, value: WeightingParameters | None) -> None:
        self._votemap_processor._weighting_parameters = value

    async def __aenter__(self) -> Self:
        """This method is a part of the context manager protocol. It is called when entering the context manager."""
        await self._exit_stack.__aenter__()

        await self._exit_stack.enter_async_context(self._votemap_processor)

        self._log_stream_client.log_types = [LogMessageType.match_start, LogMessageType.match_end]
        await self._exit_stack.enter_async_context(self._log_stream_client)

        return self

    async def __aexit__(
        self,
        exc_t: type[BaseException] | None,
        exc_v: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """This method is a part of the context manager protocol. It is called when exiting the context manager."""
        return await self._exit_stack.__aexit__(exc_t, exc_v, exc_tb)

    async def run(self) -> None:
        """Run the server manager."""
        if not self._votemap_processor or not self._log_stream_client:
            raise RuntimeError("ServerManager context must be entered")

        tasks: list[asyncio.Task] = []
        try:
            self._task_group_ended_event.clear()
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
            self._task_group_ended_event.set()
            await asyncio.sleep(0)  # allow other tasks to run
            for task in tasks:
                logger.debug("Task %s: cancelled=%s", task.get_name(), task.cancelled())
                if not task.cancelled() and task.exception():
                    logger.exception("Task %s failed", task.get_name(), exc_info=task.exception())

    async def stop(self, wait: bool = True) -> None:
        """Stop the server controller and optionally wait for it to shut down."""
        self._stop_internal()
        if wait:
            await self._task_group_ended_event.wait()

    async def send_group_message(self, player_matcher: PlayerMatcher, message: str) -> Iterable[PlayerProperties]:
        """Send a message to the player group."""
        players = await self._message_sender.send_group_message(player_matcher, message)
        logger.info("Sent message to %d players", len(list(players)))
        return players

    async def get_players_in_group(self, player_matcher: PlayerMatcher) -> Iterable[PlayerProperties]:
        """Get the players in the specified group."""
        return await self._message_sender.get_players_in_group(player_matcher)

    async def get_player_vip_info(self, player_name: str) -> VipInfo | None:
        """Get the VIP information for the specified player."""
        return await self._vip_manager.get_vip_by_name_or_id(player_name)

    def _stop_internal(self) -> None:
        if self._task_group:
            # add an exception-raising task to force the group to terminate
            self._task_group.create_task(self._force_terminate_task_group())

    async def _monitor_stop_event(self) -> None:
        assert self._stop_event  # noqa: S101
        try:
            await self._stop_event.wait()
            logger.info("Stop event signalled, stopping")
            self._stop_internal()
        except asyncio.CancelledError:
            logger.info("Stop event monitor cancelled")
            raise

    async def _force_terminate_task_group(self) -> NoReturn:
        """Used to force termination of a task group."""
        raise TerminateTaskGroup()
