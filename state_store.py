"""Send-deduplication state for the Daily Report Sender.

Phase 7 + 12 scope
------------------
A tiny persistent marker that records the date of the last successful send,
so that a second run on the same day (a manual re-run, or cron firing twice)
does not deliver the report again.

Phase 12: the marker is now **per report type** — each type gets its own file
``last_sent_<type>.txt`` next to ``config.STATE_FILE``. This keeps the types
independent: web being sent must not mark proxy as sent, and a report that
arrives later in the day is still delivered even after another type already went.

Each marker holds a single ISO date (``YYYY-MM-DD``). Reads and writes are
defensive: a missing, empty, or corrupt file is treated as "nothing sent yet"
rather than an error, and a write failure is logged but never crashes the caller
(the email has already gone out by the time we record it).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import config
from logger import get_logger

logger = get_logger(__name__)


def _state_path(report_type: str, state_file: Path | None = None) -> Path:
    """Return the per-type marker path, e.g. ``state/last_sent_web.txt``.

    Derived from ``config.STATE_FILE`` (or ``state_file`` override): the marker
    lives in the same directory, named ``last_sent_<type>.txt``.
    """
    base = state_file or config.STATE_FILE
    return base.parent / f"last_sent_{report_type.lower()}.txt"


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
    report_type: str,
    today: date | None = None,
    state_file: Path | None = None,
) -> bool:
    """Return True if ``report_type`` was already sent successfully today.

    Args:
        report_type: The report type whose marker to check (e.g. "web").
        today: Date to check. Defaults to ``date.today()`` (injectable for tests).
        state_file: Override the base state-file path (defaults to
            ``config.STATE_FILE``); the per-type marker is derived from it.
    """
    today = today or date.today()
    marker = _state_path(report_type, state_file)

    last_sent = _read_last_sent_date(marker)
    if last_sent == today:
        logger.info(
            "'%s' report already sent today (%s) — recorded in %s.",
            report_type,
            today.isoformat(),
            marker,
        )
        return True
    return False


def mark_sent_today(
    report_type: str,
    today: date | None = None,
    state_file: Path | None = None,
) -> None:
    """Record that ``report_type`` was successfully sent today.

    A failure to write the marker is logged but not raised: the email has
    already been delivered, so the run still succeeded.
    """
    today = today or date.today()
    marker = _state_path(report_type, state_file)

    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(today.isoformat() + "\n", encoding="utf-8")
        logger.info(
            "Recorded successful send of '%s' for %s in %s.",
            report_type,
            today.isoformat(),
            marker,
        )
    except OSError as exc:
        logger.error("Could not update state file %s: %s", marker, exc)
