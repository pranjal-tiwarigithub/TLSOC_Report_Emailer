#!/usr/bin/env python3
"""Daily Report Sender — application entry point.

Phase 4 scope
-------------
The orchestrator now runs the full validation chain:

* initialises logging and logs a startup banner,
* locates the newest PDF in the configured report directory,
* validates that the filename contains today's date (YYYY-MM-DD),
* confirms the file really is a PDF (magic bytes), and
* confirms the file's modification time falls on today's date.

Emailing the validated report is added in later phases.
"""

from __future__ import annotations

import sys

import config
from file_checker import (
    find_latest_pdf,
    is_pdf_file,
    validate_modification_date,
    validate_report_filename,
)
from logger import get_logger

logger = get_logger(__name__)


def main() -> int:
    """Run the Phase 2 pipeline (locate latest PDF).

    Returns:
        Process exit code: ``0`` if a latest PDF was found, ``1`` if none was
        found. Wired to ``sys.exit`` below so cron can detect failures.
    """
    logger.info("=== Daily Report Sender starting (Phase 4) ===")
    logger.info("Monitored report directory: %s", config.REPORT_DIR)
    logger.info("Log level: %s", config.LOG_LEVEL)
    logger.info("Log file: %s", config.LOG_FILE)

    latest_pdf = find_latest_pdf()
    if latest_pdf is None:
        logger.error("No latest PDF available. Stopping for this run.")
        return 1

    if not validate_report_filename(latest_pdf):
        logger.error("Filename validation failed. Stopping for this run.")
        return 1

    if not is_pdf_file(latest_pdf):
        logger.error("PDF content validation failed. Stopping for this run.")
        return 1

    if not validate_modification_date(latest_pdf):
        logger.error("Modification-date validation failed. Stopping for this run.")
        return 1

    logger.info("Selected report for further processing: %s", latest_pdf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
