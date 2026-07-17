#!/usr/bin/env python3
"""Daily Report Sender — application entry point.

Phase 13 scope
--------------
The orchestrator sends **every** report PDF produced today, one email per
report type:

* initialises logging and logs a startup banner,
* validates configuration (fail fast),
* finds all PDFs modified today in the configured report directory,
* for each PDF: derives its type from the filename, validates it, and — unless
  it was already sent today — emails it to that type's configured recipients
  with a type-specific subject and body,
* skips files whose type is unknown/unconfigured (and notes them),
* records each successful send per type (dedup), and
* sends a single admin alert summarising any skipped/failed reports — including
  on an unexpected exception caught by the top-level guard.

Flags:
* ``--dry-run``  exercise the whole flow without connecting to SMTP.
* ``--force``    send even if a report type was already sent today (manual resend).

Exit codes:
* ``0`` success — all found reports sent (or already sent / nothing to do).
* ``1`` failure — invalid config, a report failed to validate or send, or crash.
"""

from __future__ import annotations

import argparse
import sys

import config
import state_store
from email_sender import send_alert_email, send_report_email
from file_checker import (
    extract_report_type,
    find_todays_pdfs,
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
        description="Validate today's PDF reports and email each via Gmail SMTP."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the full pipeline but do not actually connect to SMTP.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Send even if a report type was already sent today (bypass dedup).",
    )
    return parser.parse_args(argv)


def _run(dry_run: bool, force: bool) -> int:
    """Process all of today's reports. Returns an exit code."""
    # Fail fast on missing/malformed configuration before doing any work.
    problems = config.validate_config()
    if problems:
        for problem in problems:
            logger.error("Config error: %s", problem)
        logger.error("Invalid configuration. Stopping before any work is done.")
        return EXIT_FAILURE

    pdfs = find_todays_pdfs()
    if not pdfs:
        logger.info(
            "Nothing to do — no report PDFs modified today in %s.", config.REPORT_DIR
        )
        return EXIT_SUCCESS

    sent = 0
    skipped = 0
    alert_notes: list[str] = []  # unrecognized files + failures, for one alert
    had_failure = False          # drives the exit code (validation/send errors)

    for pdf in pdfs:
        rtype = extract_report_type(pdf)
        if rtype is None or rtype not in config.REPORT_CONFIGS:
            detail = (
                f"type '{rtype}' not in REPORT_TYPES"
                if rtype
                else "filename does not match daily_<type>_report_<date>.pdf"
            )
            note = f"Skipped unrecognized/unconfigured report {pdf.name} ({detail})."
            logger.warning(note)
            alert_notes.append(note)
            continue

        # Per-file validation (defence in depth; find_todays_pdfs already
        # guaranteed .pdf + today's mtime, but we re-check name/content/mtime).
        if not validate_report_filename(pdf):
            note = f"Filename validation failed for {pdf.name}."
            logger.error(note)
            alert_notes.append(note)
            had_failure = True
            continue
        if not is_pdf_file(pdf):
            note = f"PDF content validation failed for {pdf.name}."
            logger.error(note)
            alert_notes.append(note)
            had_failure = True
            continue
        if not validate_modification_date(pdf):
            note = f"Modification-date validation failed for {pdf.name}."
            logger.error(note)
            alert_notes.append(note)
            had_failure = True
            continue

        # Dedup per type (unless forced).
        if not force and state_store.already_sent_today(rtype):
            logger.info("Skipping '%s' — already sent today (%s).", rtype, pdf.name)
            skipped += 1
            continue

        report = config.REPORT_CONFIGS[rtype]
        ok = send_report_email(
            pdf,
            subject=config.subject_for(rtype),
            body=config.body_for(rtype),
            to=report.to,
            cc=report.cc,
            bcc=report.bcc,
            dry_run=dry_run,
        )
        if not ok:
            note = f"Sending the '{rtype}' report email failed for {pdf.name}."
            logger.error(note)
            alert_notes.append(note)
            had_failure = True
            continue

        # Only record real sends, so a dry-run never blocks a real one.
        if not dry_run:
            state_store.mark_sent_today(rtype)
        sent += 1
        logger.info("Sent '%s' report: %s", rtype, pdf.name)

    logger.info(
        "Run summary: %d sent, %d skipped (already sent), %d problem(s).",
        sent,
        skipped,
        len(alert_notes),
    )

    # One consolidated admin alert for everything that went wrong this run.
    if alert_notes:
        summary = (
            "The Daily Report Sender finished with the following issue(s):\n\n- "
            + "\n- ".join(alert_notes)
        )
        send_alert_email(summary, dry_run=dry_run)

    logger.info("=== Daily Report Sender finished ===")
    return EXIT_FAILURE if had_failure else EXIT_SUCCESS


def main(argv: list[str] | None = None) -> int:
    """Run the pipeline with a top-level exception guard.

    Returns:
        Process exit code (``0`` success, ``1`` failure).
    """
    args = _parse_args(argv)
    dry_run = args.dry_run

    logger.info(
        "=== Daily Report Sender starting (Phase 13%s%s) ===",
        ", DRY-RUN" if dry_run else "",
        ", FORCE" if args.force else "",
    )
    logger.info("Department: %s", config.DEPARTMENT)
    logger.info("Report types: %s", ", ".join(config.REPORT_TYPES) or "(none)")
    logger.info("Monitored report directory: %s", config.REPORT_DIR)
    logger.info("Log level: %s | Log file: %s", config.LOG_LEVEL, config.LOG_FILE)

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
