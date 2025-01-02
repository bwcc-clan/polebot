
"""This module contains the logging configuration for the application."""

import atexit
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


def configure_logger(log_path: str, log_level: str = "INFO") -> None:
    """Configures the logger for the application.

    Args:
        log_path (str): The path to where to store the log files.
        log_level (str, optional): The console log level. Defaults to "INFO".
    """
    buffer_queue = Queue()  # type: ignore
    log_path_l = Path(log_path)
    log_path_l.mkdir(parents=True, exist_ok=True)
    logfile = log_path_l / "polebot.log"
    logging.config.dictConfig(
        {
            "version": 1,
            "formatters": {
                "default": {
                    "()": "polebot.logging_utils.OneLineExceptionFormatter",
                    "format": "%(asctime)s (%(name)s) [%(levelname)s] %(message)s",
                    "datefmt": "%Y-%m-%dT%H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "level": log_level,
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
                "root": {"level": log_level, "handlers": ["queue_handler"]},
                "urllib3.connectionpool": {"level": "INFO"},
            },
            "disable_existing_loggers": False,
        },
    )
    qh = logging.getHandlerByName("queue_handler")
    qh.listener.start()  # type: ignore
    atexit.register(qh.listener.stop)  # type: ignore[union-attr]
