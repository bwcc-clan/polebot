import asyncio
import json
import logging
import socket
from collections.abc import Generator
from typing import Optional, Union

import websockets
import websockets.asyncio
import websockets.asyncio.client
from websockets.asyncio.client import ClientConnection
from websockets.asyncio.client import process_exception as process_exception_standard_rules

from . import converters
from .crcon_server_details import CRCONServerDetails
from .exceptions import LogStreamMessageError
from .models import LogMessageType, LogStreamObject, LogStreamResponse
from .utils import backoff

logger = logging.getLogger(__name__)


class CRCONLogStreamClient:
    def __init__(
        self,
        server_details: CRCONServerDetails,
        queue: asyncio.Queue[LogStreamObject],
        log_types: Optional[list[LogMessageType]] = None,
    ):
        self.server_details = server_details
        self.log_types = log_types

        self.websocket_url = self.server_details.websocket_url + "/ws/logs"
        self.last_seen_id: str | None = None
        self._first_connection = True
        self._converter = converters.rcon_converter
        self._queue = queue
        self._task: asyncio.Task[None] | None = None

    def start(self, task_group: asyncio.TaskGroup) -> asyncio.Task[None]:
        """
        Starts a task in the specified task group that continually reads the log stream from a CRCON server.

        Args:
            task_group (asyncio.TaskGroup): The task group in which the task is created.

        Returns:
            asyncio.Task[None]: The task that was created.
        """
        self._task = task_group.create_task(self._run(), name="log-stream-client")
        return self._task

    def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()

    async def _run(self) -> None:
        try:
            delays: Generator[float] | None = None
            async for websocket in self._connect():
                logger.info(f"Connected to CRCON websocket {self.websocket_url}")

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
                            logger.warning(f"Remote server indicates error: {ex.message}")

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
        headers = {"Authorization": f"Bearer {self.server_details.api_key}"}
        if self.server_details.rcon_headers:
            headers.update(self.server_details.rcon_headers)

        # Note that we handle exceptions more aggressively on first connection, because e.g. DNS errors are more
        # likely to be configuration mistakes. On subsequent re-connection attempts, since the configuration has
        # worked at least once, we assume that DNS errors are likely to be transient so we use the standard rules
        if self._first_connection:
            self._first_connection = False
            process_exception = process_exception_fail_on_dns_error
        else:
            process_exception = process_exception_standard_rules

        logger.info(f"Connecting to {self.websocket_url}")

        ws = websockets.connect(
            uri=self.websocket_url,
            additional_headers=headers,
            max_size=1_000_000_000,
            process_exception=process_exception,
        )
        return ws

    async def _send_init_message(self, websocket: ClientConnection) -> None:
        """
        Sends the initialization message that starts the log stream.

        Args:
            websocket (ClientConnection): The websocket on which to send the message.
        """
        body_obj: dict[str, Union[str, list[LogMessageType], list[str], None]] = {}
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
            logger.debug("Message received: %s", str(message))
            obj = json.loads(message)
            response = self._converter.structure(obj, LogStreamResponse)
            if response:
                if response.error:
                    logger.debug(f"Response message error: {response.error}")
                    raise LogStreamMessageError(response.error)

                self.last_seen_id = response.last_seen_id
                logs_bundle = response.logs
                # do stuff with the logs
                for log in logs_bundle:
                    await self._queue.put(log)

        except LogStreamMessageError:
            raise
        except Exception as e:
            logger.error(
                "Error during handling of message",
                exc_info=e,
            )


def process_exception_fail_on_dns_error(exc: Exception) -> Exception | None:
    """
    Determine whether a connection error is retryable or fatal. This implementation differs from the websockets
    default because it indicates not to retry on `socket.gaierror`, enabling us to fail if DNS lookup fails.
    """
    if isinstance(exc, socket.gaierror):
        # DNS lookup failed - most likely because of misconfiguration
        return exc
    if isinstance(exc, (EOFError, OSError, asyncio.TimeoutError)):
        return None
    if isinstance(exc, websockets.InvalidStatus) and exc.response.status_code in [
        500,  # Internal Server Error
        502,  # Bad Gateway
        503,  # Service Unavailable
        504,  # Gateway Timeout
    ]:
        return None
    return exc
