
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

from utils.logging import configure_logger

from .app_config import AppConfig
from .composition_root import (
    begin_server_context,
    init_container,
)
from .discord.bot import make_bot
from .models import ServerParameters, get_server_params
from .services.server_manager import ServerManager

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
    server_params: ServerParameters,
    container: Container,
) -> None:
    """Runs the server manager for the specified server configuration.

    Creates a DI context for the server, then instantiates and runs the server manager from within that context.

    Args:
        server_params (ServerParameters): The server configuration.
        container (Container): The root DI container.
    """
    with begin_server_context(
        container,
        server_params,
        _stop_event,
    ) as context_container:
        server_manager = context_container[ServerManager]
        async with server_manager:
            await server_manager.run()

async def run_polebot(container: Container, app_config: AppConfig) -> None:
    bot = make_bot(container)
    await bot.start(app_config.discord_token)

async def async_main(loop: asyncio.AbstractEventLoop) -> None:
    """The main async entry point for the application."""
    load_dotenv()
    cfg = environ.to_config(AppConfig)
    container = await init_container(app_config=cfg, loop=loop)

    async with asyncio.TaskGroup() as tg:
        tg.create_task(run_polebot(container, cfg), name="polebot")
        server_params = get_server_params(cfg)
        tg.create_task(
            run_server_manager(server_params, container),
            name="server-manager",
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
