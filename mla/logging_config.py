"""Logging configuration for MyLittleAnsible.

Log lines are prefixed with the target host IP and a timestamp so that
multi-host runs stay readable.

Author: Sandro Bakuradze.
"""

import logging

LOG_FORMAT = "%(asctime)s [%(host)s] %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class _HostDefaultFilter(logging.Filter):
    """Inject a default ``host`` attribute on records that lack one."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "host"):
            record.host = "-"
        return True


def setup_logging(debug: bool = False) -> None:
    """Configure the root logger with host-aware formatting."""
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    handler.addFilter(_HostDefaultFilter())
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if debug else logging.INFO)


def get_logger(host: str = "-") -> logging.LoggerAdapter:
    """Return a ``LoggerAdapter`` that tags records with ``host``."""
    return logging.LoggerAdapter(logging.getLogger("mla"), {"host": host})
