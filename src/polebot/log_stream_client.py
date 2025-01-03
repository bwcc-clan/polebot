"""A client for the CRCON log stream."""

import asyncio
import contextlib
import json
import logging
import socket
from collections.abc import Generator
from types import TracebackType
from typing import Self

import websockets
import websockets.asyncio
import websockets.asyncio.client
from websockets.asyncio.client import ClientConnection
from websockets.asyncio.client import (
    process_exception as process_exception_standard_rules,
)

from . import converters
from .api_models import LogMessageType, LogStreamObject, LogStreamResponse
from .config import ServerConfig
from .exceptions import LogStreamMessageError
from .utils import backoff

logger = logging.getLogger(__name__)


class CRCONLogStreamClient:
    """A client for the CRCON log stream.

    This client is used to connect to the CRCON log stream, which provides a stream of log messages from the Hell Let
    Loose server. The client will connect to the CRCON server and read log messages, then forward them onto a processing
    queue.
    """
    def __init__(
        self,
        server_config: ServerConfig,
        queue: asyncio.Queue[LogStreamObject],
        log_types: list[LogMessageType] | None = None,
    ) -> None:
        """Initialises the CRCON log stream client.

        Args:
            server_config (ServerConfig): The server configuration.
            queue (asyncio.Queue[LogStreamObject]): The queue to which log messages should be forwarded.
            log_types (list[LogMessageType] | None, optional): The allowable log message types. Defaults to None,
            which indicates that all are allowed.
        """
        self.server_config = server_config
        self._queue = queue
        self.log_types: list[LogMessageType] | None = log_types

        self.websocket_url = self.server_config.crcon_details.websocket_url / "ws/logs"
        self.last_seen_id: str | None = None
        self._first_connection = True
        self._converter = converters.make_rcon_converter()
        self._exit_stack = contextlib.AsyncExitStack()

    async def __aenter__(self) -> Self:
        """Enters the context manager and connects to the CRCON server."""
        await self._exit_stack.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_t: type[BaseException] | None,
        exc_v: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """Closes the connection to the CRCON server."""
        return await self._exit_stack.__aexit__(exc_t, exc_v, exc_tb)

    async def run(self) -> None:
        """Continually reads the log stream from a CRCON server.

        Will reconnect indefinitely unless a permanent exception occurs. This should be called as an async task, which
        can be cancelled to terminate processing.
        """
        try:
            delays: Generator[float] | None = None
            async for websocket in self._connect():
                logger.info("Connected to CRCON websocket %s", self.websocket_url)

                try:
                    await self._send_init_message(websocket)

                    while True:
                        message = await websocket.recv()
                        await self._handle_incoming_message(message)

                except (websockets.ConnectionClosed, LogStreamMessageError) as ex:
                    match ex:
                        case websockets.ConnectionClosedError():
                            logger.warning("Connection was closed abnormally")
                        case websockets.ConnectionClosedOK():
                            logger.info("Connection was closed normally")
                        case LogStreamMessageError():
                            logger.warning("Remote server indicates error: %s", ex.message)

                    # Retry the above exceptions with a backoff delay
                    if delays is None:
                        delays = backoff()
                    delay = next(delays)

                    logger.info("Reconnecting in %.1f seconds", delay)
                    await asyncio.sleep(delay)
                    continue

                else:
                    delays = None

                finally:
                    await websocket.close()

        except asyncio.CancelledError:
            logger.info("Cancellation received, stopping")
            raise

    def _connect(self) -> websockets.connect:
        headers = {"Authorization": f"Bearer {self.server_config.crcon_details.api_key}"}
        if self.server_config.crcon_details.rcon_headers:
            headers.update(self.server_config.crcon_details.rcon_headers)

        # Note that we handle exceptions more aggressively on first connection, because e.g. DNS errors are more
        # likely to be configuration mistakes. On subsequent re-connection attempts, since the configuration has
        # worked at least once, we assume that DNS errors are likely to be transient so we use the standard rules
        if self._first_connection:
            self._first_connection = False
            process_exception = process_exception_fail_on_dns_error
        else:
            process_exception = process_exception_standard_rules

        logger.info("Connecting to %s", self.websocket_url)

        ws = websockets.connect(
            uri=str(self.websocket_url),
            additional_headers=headers,
            max_size=1_000_000_000,
            process_exception=process_exception,
        )
        return ws

    async def _send_init_message(self, websocket: ClientConnection) -> None:
        """Sends the initialization message that starts the log stream.

        Args:
            websocket (ClientConnection): The websocket on which to send the message.
        """
        body_obj: dict[str, str | list[LogMessageType] | list[str] | None] = {}
        if self.last_seen_id:
            body_obj["last_seen_id"] = self.last_seen_id
        if self.log_types:
            body_obj["actions"] = self.log_types
        body_obj["last_seen_id"] = self.last_seen_id
        body = json.dumps(body_obj)
        logger.debug("Sending init message: %s", body)
        await websocket.send(body)

    async def _handle_incoming_message(self, message: websockets.Data) -> None:
        try:
            obj = json.loads(message)
            response = self._converter.structure(obj, LogStreamResponse)
            if response:
                if response.error:
                    logger.debug("Response message error: %s", response.error)
                    raise LogStreamMessageError(response.error)

                self.last_seen_id = response.last_seen_id
                logs_bundle = response.logs
                # do stuff with the logs
                for log in logs_bundle:
                    await self._queue.put(log)

        except LogStreamMessageError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error(
                "Error during handling of message",
                exc_info=e,
            )
            logger.info("Failed message: %s", str(message))


def process_exception_fail_on_dns_error(exc: Exception) -> Exception | None:
    """Determine whether a connection error is retryable or fatal.

    This implementation differs from the websockets default because it indicates not to retry on `socket.gaierror`,
    enabling us to fail if DNS lookup fails.
    """
    if isinstance(exc, socket.gaierror):
        # DNS lookup failed - most likely because of misconfiguration
        return exc
    if isinstance(exc, EOFError | OSError | asyncio.TimeoutError):
        return None
    if isinstance(exc, websockets.InvalidStatus) and exc.response.status_code in [
        500,  # Internal Server Error
        502,  # Bad Gateway
        503,  # Service Unavailable
        504,  # Gateway Timeout
    ]:
        return None
    return exc
