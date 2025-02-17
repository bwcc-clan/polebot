"""The main entry point for the application."""

import asyncio
import logging
import os
import signal
import time

import environ
import uvloop
from dotenv import load_dotenv

from polebot.orchestrator import Orchestrator
from utils.log_tools import configure_logger

from .app_config import AppConfig
from .composition_root import (
    init_container,
)

log_level = os.getenv("LOG_LEVELS", ":INFO")
log_location = os.getenv("LOG_LOCATION", "./logs")
configure_logger(log_location, log_level)
logger = logging.getLogger("polebot")

os.environ["TZ"] = "UTC"
time.tzset()


_loop: asyncio.AbstractEventLoop | None = None
_stop_event = asyncio.Event()


def shutdown(sig: signal.Signals) -> None:
    """Signal handler for SIGINT and SIGTERM that initiates application shutdown."""
    global _loop
    if _loop:
        logger.info("Received %s, signalling shutdown", sig.name)
        _loop.call_soon_threadsafe(_stop_event.set)
    else:
        logger.info("Received %s", sig.name)

async def async_main(loop: asyncio.AbstractEventLoop) -> None:
    """The main async entry point for the application."""
    load_dotenv()
    cfg = environ.to_config(AppConfig)
    container = await init_container(app_config=cfg, loop=loop)

    orchestrator_instance = container[Orchestrator]
    await orchestrator_instance.run()


def main() -> None:
    """The main entry point for the application."""
    global _loop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    _loop = asyncio.new_event_loop()

    _loop.add_signal_handler(signal.SIGINT, lambda: shutdown(signal.SIGINT))
    _loop.add_signal_handler(signal.SIGTERM, lambda: shutdown(signal.SIGTERM))

    try:
        _loop.run_until_complete(async_main(_loop))
    except Exception as ex:  # noqa: BLE001
        logger.fatal(f"Unhandled exception {ex}", exc_info=ex)


if __name__ == "__main__":
    main()
