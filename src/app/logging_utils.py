import atexit
import logging
import logging.config
import os
from queue import Queue


class OneLineExceptionFormatter(logging.Formatter):
    def formatException(self, exc_info) -> str:  # type: ignore[no-untyped-def]
        result = super().formatException(exc_info)
        return repr(result)  # or format into one line however you want to

    def format(self, record: logging.LogRecord) -> str:
        s = super().format(record)
        if record.exc_text:
            s = s.replace("\n", "") + "|"
        else:
            s = s.replace("\n", "\\n")
        return s


def configure_logger(log_path: str, log_level: str = "INFO") -> None:
    q = Queue()  # type: ignore
    os.makedirs(log_path, exist_ok=True)
    logfile = os.path.join(log_path, "votemapper.log")
    logging.config.dictConfig(
        {
            "version": 1,
            "formatters": {
                "default": {
                    "()": "app.logging_utils.OneLineExceptionFormatter",
                    "format": "%(asctime)s (%(name)s) [%(levelname)s] %(message)s",
                    "datefmt": "%Y-%m-%dT%H:%M:%S",
                }
            },
            "handlers": {
                "console": {
                    "level": log_level,
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                },
                "file": {
                    "level": log_level,
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
                    "queue": q,
                },
            },
            "loggers": {
                "root": {"level": log_level, "handlers": ["queue_handler"]},
                "urllib3.connectionpool": {"level": "INFO"},
            },
            "disable_existing_loggers": False,
        }
    )
    qh = logging.getHandlerByName("queue_handler")
    qh.listener.start()  # type: ignore
    atexit.register(qh.listener.stop)  # type: ignore[union-attr]
