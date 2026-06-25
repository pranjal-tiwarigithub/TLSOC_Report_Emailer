"""Locating and validating report files on disk.

Phase 2 + 3 + 4 scope
---------------------
* Phase 2 — ``find_latest_pdf``: find the newest PDF (by modification time)
  inside the configured report directory.
* Phase 3 — ``validate_report_filename``: confirm the chosen file's name
  contains today's (server local) date written as ``YYYY-MM-DD``. The rest of
  the filename can be anything; only the date matters here.
* Phase 4 — ``is_pdf_file`` / ``validate_modification_date``: confirm the file
  really is a PDF (``%PDF-`` magic bytes) and that its modification time falls
  on today's date.

The directory is taken from configuration and is never hardcoded here.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import config
from logger import get_logger

logger = get_logger(__name__)

# Only files with this (case-insensitive) suffix are considered PDFs here.
_PDF_SUFFIX = ".pdf"

# Every valid PDF begins with this signature, e.g. "%PDF-1.7".
_PDF_MAGIC = b"%PDF-"

# Matches any ISO-style date token (YYYY-MM-DD) appearing anywhere in the
# filename. The filename is otherwise unconstrained — only the presence of
# today's date is required.
_DATE_TOKEN_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def find_latest_pdf(report_dir: Path | None = None) -> Path | None:
    """Return the most recently modified PDF in ``report_dir``.

    Args:
        report_dir: Directory to search. Defaults to ``config.REPORT_DIR``
            when not supplied (kept as a parameter so tests can point it at a
            temporary directory without touching global config).

    Returns:
        The :class:`~pathlib.Path` of the newest ``*.pdf`` file, or ``None``
        if the directory is missing, is not a directory, or contains no PDFs.
    """
    search_dir = report_dir if report_dir is not None else config.REPORT_DIR

    if not search_dir.exists():
        logger.error("Report directory does not exist: %s", search_dir)
        return None

    if not search_dir.is_dir():
        logger.error("Report path is not a directory: %s", search_dir)
        return None

    # Collect regular files whose suffix is ".pdf" (case-insensitive). A
    # directory named "something.pdf" would be excluded by the is_file check.
    pdf_files = [
        entry
        for entry in search_dir.iterdir()
        if entry.is_file() and entry.suffix.lower() == _PDF_SUFFIX
    ]

    if not pdf_files:
        logger.warning("No PDF files found in report directory: %s", search_dir)
        return None

    # Pick the newest by modification time. ``key`` reads each file's mtime;
    # max() returns the single most recently modified entry.
    latest = max(pdf_files, key=lambda path: path.stat().st_mtime)

    logger.info(
        "Latest PDF found: %s (out of %d PDF file(s))",
        latest,
        len(pdf_files),
    )
    return latest


def _extract_valid_dates(filename: str) -> list[date]:
    """Return every real calendar date written as YYYY-MM-DD in ``filename``.

    Tokens that look like dates but are not valid calendar dates (e.g.
    ``2026-13-40``) are skipped rather than raising.
    """
    found: list[date] = []
    for token in _DATE_TOKEN_RE.findall(filename):
        year, month, day = (int(part) for part in token.split("-"))
        try:
            found.append(date(year, month, day))
        except ValueError:
            # Not a real date (bad month/day); ignore this token.
            logger.debug("Ignoring invalid date token '%s' in filename.", token)
    return found


def validate_report_filename(path: Path, today: date | None = None) -> bool:
    """Check that ``path``'s filename contains today's date (YYYY-MM-DD).

    The filename may be anything else; only the presence of today's date as an
    ISO date token is required. The ``.pdf`` extension is already guaranteed by
    :func:`find_latest_pdf`.

    Args:
        path: The candidate report file.
        today: Date to compare against. Defaults to ``date.today()`` (server
            local date); injectable so tests are not tied to the real clock.

    Returns:
        ``True`` if today's date appears in the filename, otherwise ``False``.
    """
    today = today or date.today()
    filename = path.name

    dates_in_name = _extract_valid_dates(filename)
    if not dates_in_name:
        logger.error(
            "Filename has no valid YYYY-MM-DD date token: %s", filename
        )
        return False

    if today not in dates_in_name:
        logger.error(
            "Filename date(s) %s do not match today's date %s: %s",
            [d.isoformat() for d in dates_in_name],
            today.isoformat(),
            filename,
        )
        return False

    logger.info(
        "Filename date matches today (%s): %s", today.isoformat(), filename
    )
    return True


def is_pdf_file(path: Path) -> bool:
    """Check that ``path`` really is a PDF by inspecting its magic bytes.

    A genuine PDF starts with the ``%PDF-`` signature. This catches files that
    merely *look* like PDFs by name (e.g. a renamed text file) and truncated
    or empty files.

    Args:
        path: The candidate report file.

    Returns:
        ``True`` if the file begins with the PDF signature, else ``False``.
    """
    try:
        with path.open("rb") as handle:
            header = handle.read(len(_PDF_MAGIC))
    except OSError as exc:
        logger.error("Could not read file to verify PDF header: %s (%s)", path, exc)
        return False

    if header != _PDF_MAGIC:
        logger.error(
            "File is not a valid PDF (missing %r signature): %s",
            _PDF_MAGIC,
            path,
        )
        return False

    logger.info("Confirmed PDF signature: %s", path)
    return True


def validate_modification_date(path: Path, today: date | None = None) -> bool:
    """Check that ``path``'s modification time falls on today's date.

    Guards against a stale file lingering in the directory: even if the name
    carries today's date, the file itself must have been written today.

    Args:
        path: The candidate report file.
        today: Date to compare against. Defaults to ``date.today()`` (server
            local date); injectable so tests are not tied to the real clock.

    Returns:
        ``True`` if the file's mtime date equals ``today``, else ``False``.
    """
    today = today or date.today()

    try:
        mtime = path.stat().st_mtime
    except OSError as exc:
        logger.error("Could not read modification time: %s (%s)", path, exc)
        return False

    # Convert the mtime to a local-time date for comparison with `today`.
    mtime_date = datetime.fromtimestamp(mtime).date()

    if mtime_date != today:
        logger.error(
            "File modification date %s is not today's date %s: %s",
            mtime_date.isoformat(),
            today.isoformat(),
            path,
        )
        return False

    logger.info(
        "File modification date matches today (%s): %s", today.isoformat(), path
    )
    return True
