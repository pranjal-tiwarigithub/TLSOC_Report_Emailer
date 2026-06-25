#!/usr/bin/env python3
"""Daily Report Sender — application entry point.

Phase 5 scope
-------------
The orchestrator runs the full pipeline:

* initialises logging and logs a startup banner,
* locates the newest PDF in the configured report directory,
* validates filename date, PDF magic bytes, and modification date,
* emails the validated report (PDF attached) to the To/CC/BCC recipients, and
* sends an admin alert email if any step fails.

Use ``--dry-run`` to exercise the whole flow without connecting to SMTP.
"""

from __future__ import annotations

import argparse
import sys

import config
from email_sender import send_alert_email, send_report_email
from file_checker import (
    find_latest_pdf,
    is_pdf_file,
    validate_modification_date,
    validate_report_filename,
)
from logger import get_logger

logger = get_logger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Validate the day's PDF report and email it via Gmail SMTP."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the full pipeline but do not actually connect to SMTP.",
    )
    return parser.parse_args(argv)


def _fail(reason: str, *, dry_run: bool) -> int:
    """Log an error, send an admin alert, and return the failure exit code."""
    logger.error("%s", reason)
    send_alert_email(reason, dry_run=dry_run)
    return 1


def main(argv: list[str] | None = None) -> int:
    """Run the Phase 5 pipeline (validate + email).

    Returns:
        Process exit code: ``0`` on a successful send, ``1`` on any failure.
    """
    args = _parse_args(argv)
    dry_run = args.dry_run

    logger.info("=== Daily Report Sender starting (Phase 5%s) ===",
                ", DRY-RUN" if dry_run else "")
    logger.info("Monitored report directory: %s", config.REPORT_DIR)
    logger.info("Log level: %s", config.LOG_LEVEL)
    logger.info("Log file: %s", config.LOG_FILE)

    latest_pdf = find_latest_pdf()
    if latest_pdf is None:
        return _fail("No latest PDF available in the report directory.", dry_run=dry_run)

    if not validate_report_filename(latest_pdf):
        return _fail(f"Filename validation failed for {latest_pdf.name}.", dry_run=dry_run)

    if not is_pdf_file(latest_pdf):
        return _fail(f"PDF content validation failed for {latest_pdf.name}.", dry_run=dry_run)

    if not validate_modification_date(latest_pdf):
        return _fail(f"Modification-date validation failed for {latest_pdf.name}.", dry_run=dry_run)

    logger.info("Validated report ready to send: %s", latest_pdf)

    if not send_report_email(latest_pdf, dry_run=dry_run):
        return _fail(f"Sending the report email failed for {latest_pdf.name}.", dry_run=dry_run)

    logger.info("=== Daily Report Sender finished successfully ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
