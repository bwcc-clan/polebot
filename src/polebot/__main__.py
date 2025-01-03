"""The main entry point for the application."""

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
from .config import AppConfig, ServerConfig, get_server_config
from .logging_utils import configure_logger
from .server_manager import ServerManager

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


async def run_server_manager(
    server_config: ServerConfig, container: Container,
) -> None:
    """Runs the server manager for the specified server configuration.

    Creates a DI context for the server, then instantiates and runs the server manager from within that context.

    Args:
        server_config (ServerConfig): The server configuration.
        container (Container): The root DI container.
    """
    with begin_server_context(
        container, server_config, _stop_event,
    ) as context_container:
        server_manager = context_container[ServerManager]
        async with server_manager:
            await server_manager.run()

async def async_main(loop: asyncio.AbstractEventLoop) -> None:
    """The main async entry point for the application."""
    load_dotenv()
    cfg = environ.to_config(AppConfig)
    container = init_container(app_config=cfg, loop=loop)

    async with asyncio.TaskGroup() as tg:
        server_config = get_server_config(cfg)
        tg.create_task(
            run_server_manager(server_config, container), name="server-manager",
        )


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
