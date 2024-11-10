import asyncio
import datetime as dt
import json
import logging
import os
import random
import threading
from collections.abc import Generator
from enum import StrEnum
from typing import Any, Optional, Union

import websockets
from websockets.asyncio.client import ClientConnection

from app.exceptions import LogStreamMessageError

from .crcon_server_details import CRCONServerDetails

logger = logging.getLogger(__name__)


class AllLogTypes(StrEnum):
    """Both native (from the game server) and synthetic (created by CRCON) log types"""

    admin = "ADMIN"
    admin_anti_cheat = "ADMIN ANTI-CHEAT"
    admin_banned = "ADMIN BANNED"
    admin_idle = "ADMIN IDLE"
    admin_kicked = "ADMIN KICKED"
    admin_misc = "ADMIN MISC"
    admin_perma_banned = "ADMIN PERMA BANNED"
    allies_chat = "CHAT[Allies]"
    allies_team_chat = "CHAT[Allies][Team]"
    allies_unit_chat = "CHAT[Allies][Unit]"
    axis_chat = "CHAT[Axis]"
    axis_team_chat = "CHAT[Axis][Team]"
    axis_unit_chat = "CHAT[Axis][Unit]"
    camera = "CAMERA"
    chat = "CHAT"
    connected = "CONNECTED"
    disconnected = "DISCONNECTED"
    kill = "KILL"
    match = "MATCH"
    match_end = "MATCH ENDED"
    match_start = "MATCH START"
    team_kill = "TEAM KILL"
    team_switch = "TEAMSWITCH"
    # Automatic kicks for team kills
    tk = "TK"
    tk_auto = "TK AUTO"
    tk_auto_banned = "TK AUTO BANNED"
    tk_auto_kicked = "TK AUTO KICKED"
    # Vote kicks
    vote = "VOTE"
    vote_completed = "VOTE COMPLETED"
    vote_expired = "VOTE EXPIRED"
    vote_passed = "VOTE PASSED"
    vote_started = "VOTE STARTED"


class CustomDecoder(json.JSONDecoder):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(object_hook=self.try_datetime, *args, **kwargs)

    @staticmethod
    def try_datetime(d: dict[str, Any]) -> Any:
        ret: dict[str, Any] = {}
        for key, value in d.items():
            try:
                ret[key] = dt.datetime.fromisoformat(value)
            except (ValueError, TypeError):
                ret[key] = value
        return ret


class CRCONLogStreamClient:
    def __init__(
        self,
        server_details: CRCONServerDetails,
        log_types: Optional[list[AllLogTypes]] = None,
        stop_event: Optional[threading.Event] = None,
    ):
        self.server_details = server_details
        self.log_types = log_types

        self.stop_event = stop_event or threading.Event()
        self.websocket_url = self.server_details.websocket_url + "/ws/logs"
        self.last_seen_id: str | None = None

    async def run(self) -> None:
        while not self.stop_event.is_set():
            delays: Generator[float] | None = None
            async for websocket in self._connect():
                if self.stop_event.is_set():
                    break

                try:
                    body_obj: dict[str, Union[str, list[AllLogTypes], list[str], None]] = {}
                    if self.last_seen_id:
                        body_obj["last_seen_id"] = self.last_seen_id
                    if self.log_types:
                        body_obj["actions"] = self.log_types
                    body_obj["last_seen_id"] = self.last_seen_id
                    body = json.dumps(body_obj)
                    logger.debug("Sending init message: %s", body)
                    await websocket.send(body)
                    logger.info(f"Connected to CRCON websocket {self.websocket_url}")

                    while not self.stop_event.is_set():
                        try:
                            # Receive with timeout so that we don't wait indefinitely, this gives us a chance to
                            # check the stop event
                            async with asyncio.timeout(5):
                                message = await websocket.recv()

                            await self._handle_incoming_message(websocket, message)
                        except asyncio.TimeoutError:
                            continue

                except Exception as ex:
                    if isinstance(ex, websockets.ConnectionClosed):
                        if isinstance(ex, websockets.ConnectionClosedError):
                            logger.warning("Connection was closed abnormally")
                        else:
                            logger.warning("Connection was closed normally")
                    elif isinstance(ex, LogStreamMessageError):
                        logger.warning(f"Remote server indicates error: {ex.message}")
                        await websocket.close()
                    else:
                        raise

                    if delays is None:
                        delays = backoff()
                    delay = next(delays)

                    logger.info("Reconnecting in %.1f seconds", delay)
                    self.stop_event.wait(delay)

                    continue

                else:
                    delays = None

        logger.info("Shutdown signalled")

    def stop(self) -> None:
        self.stop_event.set()

    def _connect(self) -> websockets.connect:
        headers = {"Authorization": f"Bearer {self.server_details.api_key}"}
        if self.server_details.rcon_headers:
            headers.update(self.server_details.rcon_headers)

        logger.info(f"Connecting to {self.websocket_url}")

        ws = websockets.connect(self.websocket_url, additional_headers=headers, max_size=1_000_000_000)
        return ws

    async def _handle_incoming_message(self, websocket: ClientConnection, message: websockets.Data) -> None:
        try:
            logger.debug("Message received: %s", str(message))
            json_object = json.loads(message, cls=CustomDecoder)
            if json_object:
                error: str | None = json_object.get("error", None)
                if error:
                    logger.debug(f"Response message error: {error}")
                    raise LogStreamMessageError(error)

                self.last_seen_id = json_object.get("last_seen_id", None)
                logs_bundle = json_object.get("logs", [])
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


BACKOFF_INITIAL_DELAY = float(os.environ.get("LOGSTREAM_BACKOFF_INITIAL_DELAY", "5"))
BACKOFF_MIN_DELAY = float(os.environ.get("LOGSTREAM_BACKOFF_MIN_DELAY", "3.1"))
BACKOFF_MAX_DELAY = float(os.environ.get("LOGSTREAM_BACKOFF_MAX_DELAY", "90.0"))
BACKOFF_FACTOR = float(os.environ.get("LOGSTREAM_BACKOFF_FACTOR", "1.618"))


def backoff(
    initial_delay: float = BACKOFF_INITIAL_DELAY,
    min_delay: float = BACKOFF_MIN_DELAY,
    max_delay: float = BACKOFF_MAX_DELAY,
    factor: float = BACKOFF_FACTOR,
) -> Generator[float]:
    """
    Generate a series of backoff delays between reconnection attempts.

    Yields:
        How many seconds to wait before retrying to connect.

    """
    # Add a random initial delay between 0 and 5 seconds.
    # See 7.2.3. Recovering from Abnormal Closure in RFC 6455.
    yield random.random() * initial_delay
    delay = min_delay
    while delay < max_delay:
        yield delay
        delay *= factor
    while True:
        yield max_delay
