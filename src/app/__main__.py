import asyncio
import logging
import os
import signal
import time

import environ
import uvloop
from dotenv import load_dotenv
from lagom import Container

from .composition_root import (
    begin_server_context,
    init_container,
)
from .config import AppConfig, get_server_details
from .crcon_server_details import CRCONServerDetails
from .logging_utils import configure_logger
from .server_manager import ServerManager

log_level = os.getenv("LOG_LEVEL", "INFO")
log_location = os.getenv("LOG_LOCATION", "./logs")
configure_logger(log_location, log_level)
logger = logging.getLogger("votemapper")

os.environ["TZ"] = "UTC"
time.tzset()


_loop: asyncio.AbstractEventLoop | None = None
_stop_event = asyncio.Event()


def shutdown(sig: signal.Signals) -> None:
    global _loop
    if _loop:
        logger.info("Received %s, signalling shutdown", sig.name)
        _loop.call_soon_threadsafe(_stop_event.set)
    else:
        logger.info("Received %s", sig.name)


async def run_server_manager(
    server_details: CRCONServerDetails, container: Container
) -> None:
    with begin_server_context(
        container, server_details, _stop_event
    ) as context_container:
        server_manager = context_container[ServerManager]
        async with server_manager:
            await server_manager.run()


async def async_main(loop: asyncio.AbstractEventLoop) -> None:
    load_dotenv()
    cfg = environ.to_config(AppConfig)
    container = init_container(app_config=cfg, loop=loop)
    async with asyncio.TaskGroup() as tg:
        server_details = get_server_details()
        tg.create_task(
            run_server_manager(server_details, container), name="server-manager"
        )


def main() -> None:
    global _loop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    _loop = asyncio.new_event_loop()

    _loop.add_signal_handler(signal.SIGINT, lambda: shutdown(signal.SIGINT))
    _loop.add_signal_handler(signal.SIGTERM, lambda: shutdown(signal.SIGTERM))

    try:
        _loop.run_until_complete(async_main(_loop))
    except Exception as ex:
        logger.fatal(f"Unhandled exception {ex}", exc_info=ex)


if __name__ == "__main__":
    main()
