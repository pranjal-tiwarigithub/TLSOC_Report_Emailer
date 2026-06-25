"""Locating report files on disk.

Phase 2 scope
-------------
A single responsibility: find the newest PDF inside the configured report
directory (``config.REPORT_DIR``).

"Newest" is defined by **modification time (mtime)** — the most recently
written file wins. This module does NOT yet check the filename format, the
date, or the PDF magic bytes; those validations arrive in Phases 3 and 4.

The directory is taken from configuration and is never hardcoded here.
"""

from __future__ import annotations

from pathlib import Path

import config
from logger import get_logger

logger = get_logger(__name__)

# Only files with this (case-insensitive) suffix are considered PDFs here.
_PDF_SUFFIX = ".pdf"


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
