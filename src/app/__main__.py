import asyncio
import logging
import os
import signal
import time
from contextlib import suppress

import uvloop
from dotenv import load_dotenv

from .config import get_server_details
from .crcon_server_details import CRCONServerDetails
from .logging_utils import configure_logger
from .server_manager import ServerManager

log_level = os.getenv("LOG_LEVEL", "INFO")
log_location = os.getenv("LOG_LOCATION", "./logs")
configure_logger(log_location, log_level)
logger = logging.getLogger("votemapper")

os.environ["TZ"] = "UTC"
time.tzset()


loop: asyncio.AbstractEventLoop | None = None
stop_event = asyncio.Event()

def shutdown(sig: signal.Signals) -> None:
    global loop
    if loop:
        logger.info("Received %s, signalling shutdown", sig.name)
        loop.call_soon_threadsafe(stop_event.set)
    else:
        logger.info("Received %s", sig.name)


async def run_server_manager(server_details: CRCONServerDetails) -> None:
    manager = ServerManager(server_details=server_details, stop_event=stop_event)
    await manager.run()


async def async_main() -> None:
    try:
        load_dotenv()
        server_details = get_server_details()
        task = asyncio.ensure_future(run_server_manager(server_details))
        await task
    except Exception as ex:
        logger.fatal(f"Unhandled exception {ex}", exc_info=ex)


def main() -> None:
    global loop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = asyncio.new_event_loop()

    loop.add_signal_handler(signal.SIGINT, lambda: shutdown(signal.SIGINT))
    loop.add_signal_handler(signal.SIGTERM, lambda: shutdown(signal.SIGTERM))

    try:
        loop.run_until_complete(async_main())
    except Exception as ex:
        logger.exception("Unhandled exception", exc_info=ex)

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
