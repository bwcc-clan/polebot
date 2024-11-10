import asyncio
import logging
import os
import signal
import threading
import time
from contextlib import suppress

import uvloop
from dotenv import load_dotenv

from .config import get_server_details
from .crcon_server_details import CRCONServerDetails
from .log_stream_client import CRCONLogStreamClient
from .log_utils import configure_logger

log_level = os.getenv("LOG_LEVEL", "INFO")
log_location = os.getenv("LOG_LOCATION", "./logs")
configure_logger(log_location, log_level)
logger = logging.getLogger("votemapper")

os.environ["TZ"] = "UTC"
time.tzset()

STOP_EVENT = threading.Event()


def shutdown(sig: signal.Signals):
    logger.info("Received %s, signalling shutdown", sig.name)
    STOP_EVENT.set()


async def run_client(server_details: CRCONServerDetails):
    client = CRCONLogStreamClient(server_details=server_details, stop_event=STOP_EVENT)
    await client.run()


async def async_main():
    try:
        load_dotenv()
        server_details = get_server_details()
        task = asyncio.ensure_future(run_client(server_details))  # fire and forget
        await task
    except Exception as ex:
        logger.fatal(f"Unhandled exception {ex}", exc_info=ex)


def main() -> None:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = asyncio.new_event_loop()

    loop.add_signal_handler(signal.SIGINT, lambda: shutdown(signal.SIGINT))
    loop.add_signal_handler(signal.SIGTERM, lambda: shutdown(signal.SIGTERM))

    loop.run_until_complete(async_main())

    # Let's also cancel all running tasks:
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
        # Now we should await task to execute it's cancellation.
        # Cancelled task raises asyncio.CancelledError that we can suppress:
        with suppress(asyncio.CancelledError):
            loop.run_until_complete(task)


if __name__ == "__main__":
    main()
