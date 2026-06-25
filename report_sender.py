#!/usr/bin/env python3
"""Daily Report Sender — application entry point.

Phase 7 scope
-------------
The orchestrator runs the full, hardened pipeline:

* initialises logging and logs a startup banner,
* validates configuration (fail fast),
* skips the run if today's report was already sent (dedup state file),
* locates the newest PDF in the configured report directory,
* validates filename date, PDF magic bytes, and modification date,
* emails the validated report (PDF attached) to the To/CC/BCC recipients,
* records the successful send, and
* sends an admin alert email if any step fails — including on an unexpected
  exception caught by the top-level guard.

Flags:
* ``--dry-run``  exercise the whole flow without connecting to SMTP.
* ``--force``    send even if today's report was already sent (manual resend).

Exit codes:
* ``0`` success — report sent, or already sent earlier today (nothing to do).
* ``1`` failure — invalid config, no valid report, send error, or crash.
"""

from __future__ import annotations

import argparse
import sys

import config
import state_store
from email_sender import send_alert_email, send_report_email
from file_checker import (
    find_latest_pdf,
    is_pdf_file,
    validate_modification_date,
    validate_report_filename,
)
from logger import get_logger

logger = get_logger(__name__)

EXIT_SUCCESS = 0
EXIT_FAILURE = 1


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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Send even if today's report was already sent (bypass dedup).",
    )
    return parser.parse_args(argv)


def _fail(reason: str, *, dry_run: bool) -> int:
    """Log an error, send an admin alert, and return the failure exit code."""
    logger.error("%s", reason)
    send_alert_email(reason, dry_run=dry_run)
    return EXIT_FAILURE


def _run(dry_run: bool, force: bool) -> int:
    """Execute the validate-and-send pipeline. Returns an exit code."""
    # Fail fast on missing/malformed configuration before doing any work.
    problems = config.validate_config()
    if problems:
        for problem in problems:
            logger.error("Config error: %s", problem)
        logger.error("Invalid configuration. Stopping before any work is done.")
        return EXIT_FAILURE

    # Dedup: skip if we already sent today's report (unless --force).
    if not force and state_store.already_sent_today():
        logger.info("Nothing to do — today's report was already sent.")
        return EXIT_SUCCESS

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

    # Only record the send for real runs, so a dry-run never blocks a real one.
    if not dry_run:
        state_store.mark_sent_today()

    logger.info("=== Daily Report Sender finished successfully ===")
    return EXIT_SUCCESS


def main(argv: list[str] | None = None) -> int:
    """Run the pipeline with a top-level exception guard.

    Returns:
        Process exit code (``0`` success, ``1`` failure).
    """
    args = _parse_args(argv)
    dry_run = args.dry_run

    logger.info(
        "=== Daily Report Sender starting (Phase 7%s%s) ===",
        ", DRY-RUN" if dry_run else "",
        ", FORCE" if args.force else "",
    )
    logger.info("Monitored report directory: %s", config.REPORT_DIR)
    logger.info("Log level: %s", config.LOG_LEVEL)
    logger.info("Log file: %s", config.LOG_FILE)

    try:
        return _run(dry_run=dry_run, force=args.force)
    except Exception as exc:  # noqa: BLE001 — last-resort guard for cron safety
        # Log the full traceback and alert the admin; never let cron see a
        # raw crash with no record of why.
        logger.exception("Unexpected error during run: %s", exc)
        send_alert_email(f"Unexpected error: {exc}", dry_run=dry_run)
        return EXIT_FAILURE


if __name__ == "__main__":
    sys.exit(main())
