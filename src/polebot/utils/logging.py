
"""This module contains the logging configuration for the application."""

import atexit
import contextlib
import logging
import logging.config
from pathlib import Path
from queue import Queue


class OneLineExceptionFormatter(logging.Formatter):
    """A custom formatter that formats exceptions into one line."""
    def formatException(self, exc_info) -> str:  # type: ignore[no-untyped-def]  # noqa: N802 , D102 , ANN001 (overriden method)
        result = super().formatException(exc_info)
        return repr(result)  # or format into one line however you want to

    def format(self, record: logging.LogRecord) -> str:  # noqa: D102 (overriden method)
        s = super().format(record)
        s = s.replace("\n", "") + "|" if record.exc_text else s.replace("\n", "\\n")
        return s


def configure_logger(log_dir: str, log_levels: str = ":INFO") -> None:
    """Configures the logger for the application.

    Args:
        log_dir (str): The path to where to store the log files.
        log_levels (str, optional): A string that defines log levels for various named loggers. Defaults to ":INFO".


    A valid `log_levels` string looks something like this:
        discord:DEBUG,discord.http:INFO,:ERROR,custom:35

    The above would set the following log levels:
        * root:               ERROR
        * discord             DEBUG
        * discord.http        INFO
        * custom              35

    A special case is the logger named `!console` which will set the `console` log handler to the specified level.
    """
    logger_level_map = _parse_log_levels(log_levels)
    buffer_queue = Queue()  # type: ignore
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    logfile = log_path / "polebot.log"
    logging.config.dictConfig(
        {
            "version": 1,
            "formatters": {
                "default": {
                    "()": "polebot.utils.logging.OneLineExceptionFormatter",
                    "format": "%(asctime)s (%(name)s) [%(levelname)s] %(message)s",
                    "datefmt": "%Y-%m-%dT%H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "level": logger_level_map.get("!console", None) or logger_level_map["root"],
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                },
                "file": {
                    "level": "DEBUG",
                    "class": "logging.handlers.TimedRotatingFileHandler",
                    "formatter": "default",
                    "filename": logfile,
                    "when": "midnight",
                    "interval": 1,
                    "backupCount": 14,
                    "utc": True,
                },
                "queue_handler": {
                    "class": "logging.handlers.QueueHandler",
                    "handlers": ["console", "file"],
                    "respect_handler_level": True,
                    "queue": buffer_queue,
                },
            },
            "loggers": {
                "root": {"level": logger_level_map["root"], "handlers": ["queue_handler"]},
                "urllib3.connectionpool": {"level": "INFO"},
            },
            "disable_existing_loggers": False,
        },
    )
    qh = logging.getHandlerByName("queue_handler")
    qh.listener.start()  # type: ignore
    atexit.register(qh.listener.stop)  # type: ignore[union-attr]

    for logger_name, level_text in logger_level_map.items():
        if logger_name == "!console":
            continue
        logger = logging.getLogger() if logger_name in ["", "root"] else logging.getLogger(logger_name)
        logger.setLevel(level_text)
    _update_log_handlers()
    logging.getLogger().info("Log levels = '%s'", log_levels)


def _parse_log_levels(log_levels: str) -> dict[str, str]:
    level_map = logging.getLevelNamesMapping()
    levels: dict[str, str] = {}
    for item in [x.split(":") for x in [c.strip() for c in log_levels.split(",") if c.strip()]]:
        with contextlib.suppress(ValueError):  # Ignore badly-formatted input values
            logger_name, level_text, *_ = item
            logger_name = logger_name.strip()
            level_text = level_text.strip()

            logger_name = "root" if logger_name == "" else logger_name
            if level_text not in level_map:
                if level_text.isdigit():
                    # level_text is a numeric value - we can use it directly
                    levels[logger_name] = level_text
                # level_text is an invalid numeric value - just ignore
                continue
            else:
                levels[logger_name] = level_text

    if "root" not in levels:
        levels["root"] = "INFO"
    return levels

def _update_log_handlers() -> None:
    """Reconfigure all loggers to use the same handlers as the root logger.

    Removes individual handlers in all loggers and enables propagation so they use the same handler as root. This is so
    that any loggers that were instantiated during program initialisation will use our configured values instead of
    their default values.
    """
    loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]

    for logger in loggers:
        logger.propagate = True
        logger.handlers.clear()
