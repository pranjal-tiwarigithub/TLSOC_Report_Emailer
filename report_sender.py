#!/usr/bin/env python3
"""Daily Report Sender — application entry point.

Phase 2 scope
-------------
The orchestrator now:

* initialises logging,
* logs a startup banner showing the effective configuration, and
* locates the newest PDF in the configured report directory.

Validation (filename format, dates, PDF magic bytes) and emailing are added
in later phases. Running this file is the primary way to smoke-test progress.
"""

from __future__ import annotations

import sys

import config
from file_checker import find_latest_pdf
from logger import get_logger

logger = get_logger(__name__)


def main() -> int:
    """Run the Phase 2 pipeline (locate latest PDF).

    Returns:
        Process exit code: ``0`` if a latest PDF was found, ``1`` if none was
        found. Wired to ``sys.exit`` below so cron can detect failures.
    """
    logger.info("=== Daily Report Sender starting (Phase 2) ===")
    logger.info("Monitored report directory: %s", config.REPORT_DIR)
    logger.info("Log level: %s", config.LOG_LEVEL)
    logger.info("Log file: %s", config.LOG_FILE)

    latest_pdf = find_latest_pdf()
    if latest_pdf is None:
        logger.error("No latest PDF available. Stopping for this run.")
        return 1

    logger.info("Selected report for further processing: %s", latest_pdf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
