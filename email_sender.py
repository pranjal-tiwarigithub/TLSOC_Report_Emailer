"""Email delivery for the Daily Report Sender.

Phase 5 scope
-------------
Send the validated PDF report as a Gmail SMTP email with:

* the fixed subject and body from the spec,
* the PDF attached,
* multiple recipients across To / CC / BCC, and
* a ``dry_run`` mode that builds the full message and logs what *would* be
  sent without ever connecting to the SMTP server (used for testing before
  real credentials exist).

A separate :func:`send_alert_email` notifies an admin address when a run
fails, so silent cron failures become visible.

Transport: Gmail on port 587 with STARTTLS, authenticating with an App
Password. Credentials come from :mod:`config` (which reads them from the
git-ignored ``.env``); they are never hardcoded or logged.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path

import config
from logger import get_logger

logger = get_logger(__name__)


class EmailConfigError(Exception):
    """Raised when required email configuration is missing."""


def _all_recipients(to: list[str], cc: list[str], bcc: list[str]) -> list[str]:
    """Flatten To/CC/BCC into the envelope recipient list (de-duplicated)."""
    seen: dict[str, None] = {}
    for addr in (*to, *cc, *bcc):
        seen.setdefault(addr, None)
    return list(seen)


def _build_message(
    subject: str,
    body: str,
    to: list[str],
    cc: list[str],
    attachment: Path | None = None,
) -> EmailMessage:
    """Construct an :class:`EmailMessage` with optional PDF attachment.

    Note: BCC recipients are deliberately NOT added as a header (that is what
    makes them blind); they are passed to the transport as envelope recipients
    instead.
    """
    message = EmailMessage()
    message["From"] = config.EMAIL_FROM
    message["Subject"] = subject
    if to:
        message["To"] = ", ".join(to)
    if cc:
        message["Cc"] = ", ".join(cc)
    message.set_content(body)

    if attachment is not None:
        data = attachment.read_bytes()
        message.add_attachment(
            data,
            maintype="application",
            subtype="pdf",
            filename=attachment.name,
        )
    return message


def _validate_email_config(recipients: list[str]) -> None:
    """Ensure the minimum config needed to send is present."""
    missing: list[str] = []
    if not config.SMTP_USER:
        missing.append("SMTP_USER")
    if not config.SMTP_PASSWORD:
        missing.append("SMTP_PASSWORD")
    if not config.EMAIL_FROM:
        missing.append("EMAIL_FROM")
    if not recipients:
        missing.append("at least one recipient (EMAIL_TO/CC/BCC)")
    if missing:
        raise EmailConfigError("Missing email configuration: " + ", ".join(missing))


def _send(message: EmailMessage, recipients: list[str], *, dry_run: bool) -> None:
    """Send ``message`` to ``recipients`` over Gmail SMTP, or simulate it."""
    if dry_run:
        logger.info(
            "[DRY-RUN] Would send '%s' from %s to %d recipient(s): %s",
            message["Subject"],
            message["From"],
            len(recipients),
            ", ".join(recipients),
        )
        attachments = [
            part.get_filename()
            for part in message.iter_attachments()
            if part.get_filename()
        ]
        if attachments:
            logger.info("[DRY-RUN] Attachment(s): %s", ", ".join(attachments))
        return

    logger.info(
        "Connecting to SMTP %s:%d (STARTTLS) as %s",
        config.SMTP_HOST,
        config.SMTP_PORT,
        config.SMTP_USER,
    )
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as server:
        server.starttls()
        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.send_message(message, to_addrs=recipients)
    logger.info("Email sent to %d recipient(s).", len(recipients))


def send_report_email(pdf_path: Path, *, dry_run: bool = False) -> bool:
    """Email the validated PDF report as an attachment.

    Args:
        pdf_path: Path to the validated PDF to attach.
        dry_run: When True, build and log the message but do not connect to
            SMTP. Useful for testing without credentials.

    Returns:
        ``True`` on success (or successful dry-run), ``False`` on failure.
    """
    recipients = _all_recipients(config.EMAIL_TO, config.EMAIL_CC, config.EMAIL_BCC)
    try:
        _validate_email_config(recipients)
        message = _build_message(
            subject=config.EMAIL_SUBJECT,
            body=config.EMAIL_BODY,
            to=config.EMAIL_TO,
            cc=config.EMAIL_CC,
            attachment=pdf_path,
        )
        _send(message, recipients, dry_run=dry_run)
        return True
    except EmailConfigError as exc:
        logger.error("Cannot send report email: %s", exc)
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("Failed to send report email: %s", exc)
    return False


def send_alert_email(reason: str, *, dry_run: bool = False) -> bool:
    """Notify the admin address that a run failed.

    Args:
        reason: Human-readable description of what went wrong.
        dry_run: When True, log instead of sending.

    Returns:
        ``True`` if the alert was sent/simulated, ``False`` otherwise. Never
        raises — alerting must not crash the caller's error handling.
    """
    if not config.ALERT_EMAIL_TO:
        logger.warning("No ALERT_EMAIL_TO configured; skipping failure alert.")
        return False

    body = (
        "The Daily Report Sender failed during its run.\n\n"
        f"Reason: {reason}\n\n"
        "Please check the server and the application log (logs/sender.log).\n"
    )
    try:
        _validate_email_config(config.ALERT_EMAIL_TO)
        message = _build_message(
            subject="[ALERT] Daily Web Report failed",
            body=body,
            to=config.ALERT_EMAIL_TO,
            cc=[],
            attachment=None,
        )
        _send(message, config.ALERT_EMAIL_TO, dry_run=dry_run)
        return True
    except EmailConfigError as exc:
        logger.error("Cannot send alert email: %s", exc)
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("Failed to send alert email: %s", exc)
    return False
