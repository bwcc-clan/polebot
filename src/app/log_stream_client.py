import asyncio
import contextlib
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
from .models import LogMessageType, LogStreamResponse
from .utils import backoff

logger = logging.getLogger(__name__)


class CRCONLogStreamClient:
    def __init__(
        self,
        server_details: CRCONServerDetails,
        log_types: Optional[list[LogMessageType]] = None,
        stop_event: Optional[asyncio.Event] = None,
    ):
        self.server_details = server_details
        self.log_types = log_types

        self.stop_event = stop_event or asyncio.Event()
        self.websocket_url = self.server_details.websocket_url + "/ws/logs"
        self.last_seen_id: str | None = None
        self._first_connection = True
        self._converter = converters.rcon_converter

    async def run(self) -> None:
        while not self.stop_event.is_set():
            delays: Generator[float] | None = None
            async for websocket in self._connect():
                logger.info(f"Connected to CRCON websocket {self.websocket_url}")
                if self.stop_event.is_set():
                    break

                try:
                    await self._send_init_message(websocket)

                    while not self.stop_event.is_set():
                        try:
                            # Receive with timeout so that we don't wait indefinitely, this gives us a chance to
                            # check the stop event
                            async with asyncio.timeout(5):
                                message = await websocket.recv()

                            await self._handle_incoming_message(websocket, message)
                        except asyncio.TimeoutError:
                            logger.debug("No message was available")
                            continue

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
                    with contextlib.suppress(asyncio.TimeoutError):
                        async with asyncio.timeout(delay):
                            await self.stop_event.wait()

                    continue

                else:
                    delays = None

                finally:
                    await websocket.close()

        logger.info("Shutdown signalled")

    def stop(self) -> None:
        self.stop_event.set()

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

    async def _handle_incoming_message(self, websocket: ClientConnection, message: websockets.Data) -> None:
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
                    print(log)

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
