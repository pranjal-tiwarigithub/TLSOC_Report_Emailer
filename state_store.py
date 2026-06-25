"""Send-deduplication state for the Daily Report Sender.

Phase 7 scope
-------------
A tiny persistent marker that records the date of the last successful send,
so that a second run on the same day (a manual re-run, or cron firing twice)
does not deliver the report again.

The state is a single ISO date (``YYYY-MM-DD``) written to
``config.STATE_FILE``. Reads and writes are defensive: a missing, empty, or
corrupt file is treated as "nothing sent yet" rather than an error, and a
write failure is logged but never crashes the caller (the email has already
gone out by the time we record it).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import config
from logger import get_logger

logger = get_logger(__name__)


def _read_last_sent_date(state_file: Path) -> date | None:
    """Return the date stored in ``state_file``, or ``None`` if unavailable."""
    try:
        text = state_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.error("Could not read state file %s: %s", state_file, exc)
        return None

    if not text:
        return None

    try:
        return date.fromisoformat(text)
    except ValueError:
        logger.warning(
            "Ignoring unrecognised content in state file %s: %r", state_file, text
        )
        return None


def already_sent_today(
    today: date | None = None, state_file: Path | None = None
) -> bool:
    """Return True if a successful send was already recorded for today.

    Args:
        today: Date to check. Defaults to ``date.today()`` (injectable for tests).
        state_file: Override the state-file path (defaults to ``config.STATE_FILE``).
    """
    today = today or date.today()
    state_file = state_file or config.STATE_FILE

    last_sent = _read_last_sent_date(state_file)
    if last_sent == today:
        logger.info(
            "Report already sent today (%s) — recorded in %s.",
            today.isoformat(),
            state_file,
        )
        return True
    return False


def mark_sent_today(
    today: date | None = None, state_file: Path | None = None
) -> None:
    """Record that the report was successfully sent today.

    A failure to write the marker is logged but not raised: the email has
    already been delivered, so the run still succeeded.
    """
    today = today or date.today()
    state_file = state_file or config.STATE_FILE

    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(today.isoformat() + "\n", encoding="utf-8")
        logger.info(
            "Recorded successful send for %s in %s.", today.isoformat(), state_file
        )
    except OSError as exc:
        logger.error("Could not update state file %s: %s", state_file, exc)
