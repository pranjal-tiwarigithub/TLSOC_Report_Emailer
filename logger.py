"""Logging setup for the Daily Report Sender.

Provides a single factory, :func:`get_logger`, that returns a configured
logger writing to BOTH:

* a rotating log file (``logs/sender.log`` by default), so history survives
  across the daily cron runs without growing unbounded, and
* the console (stderr), which is convenient during manual testing and is
  captured by cron's own mail/output handling in production.

The configuration is idempotent: calling :func:`get_logger` more than once
will not attach duplicate handlers.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import config

# Shared log line format: timestamp, level, module, message.
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Rotating-file limits: keep the active log under ~1 MB and retain 5 backups.
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 5


def get_logger(name: str = "report_sender") -> logging.Logger:
    """Return a configured logger with file + console handlers.

    Args:
        name: Logger name, typically the module name. Defaults to the
            application name so all components share one logger by default.

    Returns:
        A :class:`logging.Logger` ready for use. Safe to call repeatedly.
    """
    logger = logging.getLogger(name)

    # If handlers are already attached (e.g. second call), do nothing more.
    if logger.handlers:
        return logger

    level = getattr(logging, config.LOG_LEVEL, logging.INFO)
    logger.setLevel(level)
    # Avoid messages propagating to the root logger and printing twice.
    logger.propagate = False

    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # Ensure the log directory exists before the file handler opens the file.
    log_file: Path = config.LOG_FILE
    log_file.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
