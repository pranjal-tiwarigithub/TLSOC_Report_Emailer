"""Centralised configuration for the Daily Report Sender.

This is the single source of truth for every tunable setting and secret. All
values come from a git-ignored ``.env`` file (or the real environment), with
sensible defaults where one exists. No other module reads ``os.environ`` or
hardcodes a path, credential, or recipient — they import from here.

Settings groups
---------------
* Paths    — ``REPORT_DIR`` (monitored directory, configurable).
* Logging  — ``LOG_LEVEL``, ``LOG_FILE``.
* SMTP     — host/port and the ``SMTP_USER`` / ``SMTP_PASSWORD`` secrets.
* Email    — sender, To/CC/BCC recipients, admin alert address, subject/body.

Call :func:`validate_config` at startup to fail fast (with clear messages)
when a required value is missing or malformed, rather than crashing mid-run.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Project root = directory that contains this file. Relative paths from .env
# (e.g. LOG_FILE) are resolved against this so the app behaves the same no
# matter what working directory cron launches it from.
PROJECT_ROOT: Path = Path(__file__).resolve().parent

# Load variables from .env into the process environment if the file exists.
# Existing real environment variables always take precedence (override=False).
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _resolve_path(raw: str) -> Path:
    """Resolve a possibly-relative path against the project root."""
    path = Path(raw).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def _split_csv(raw: str) -> list[str]:
    """Split a comma-separated string into a clean list of non-empty items."""
    return [item.strip() for item in raw.split(",") if item.strip()]


def _get_int(name: str, default: int) -> int:
    """Read an integer env var, falling back to ``default`` if unset/invalid."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        # Defer surfacing this to validate_config so all problems report at once.
        return -1


# --- Monitored report directory (configurable, never hardcoded) ------------
# Default mirrors the production location, but any deployment can override it
# by setting REPORT_DIR in .env or the environment.
REPORT_DIR: Path = Path(
    os.getenv("REPORT_DIR", "/opt/TLSOCDockerDeploy/reporting/output/pdf")
).expanduser()

# --- Logging settings -------------------------------------------------------
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE: Path = _resolve_path(os.getenv("LOG_FILE", "logs/sender.log"))

# --- SMTP / email settings (Phase 5) ---------------------------------------
# Gmail SMTP defaults; overridable via .env. Port 587 uses STARTTLS.
SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = _get_int("SMTP_PORT", 587)

# Secrets — provided via .env only, NEVER hardcoded. Empty until you set them.
SMTP_USER: str = os.getenv("SMTP_USER", "")          # Gmail username/address
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")  # Gmail App Password

# Sender address. Defaults to the SMTP username when not set separately.
EMAIL_FROM: str = os.getenv("EMAIL_FROM", "") or SMTP_USER

# Recipients — comma-separated lists in .env (To / CC / BCC).
EMAIL_TO: list[str] = _split_csv(os.getenv("EMAIL_TO", ""))
EMAIL_CC: list[str] = _split_csv(os.getenv("EMAIL_CC", ""))
EMAIL_BCC: list[str] = _split_csv(os.getenv("EMAIL_BCC", ""))

# Admin address(es) that receive failure alerts (Phase 5 decision).
ALERT_EMAIL_TO: list[str] = _split_csv(os.getenv("ALERT_EMAIL_TO", ""))

# Fixed subject and body per the project spec.
EMAIL_SUBJECT: str = os.getenv("EMAIL_SUBJECT", "Daily Web Report")
EMAIL_BODY: str = (
    "Hello,\n\n"
    "This is today's web report.\n\n"
    "Regards,\n"
    "TLSOC\n"
)


def validate_config() -> list[str]:
    """Return a list of configuration problems (empty list means all good).

    Checks the values that must be present and well-formed for a real run:
    the report directory, SMTP credentials, a sender, and at least one
    recipient. Returning a list (rather than raising) lets the caller report
    every problem at once and decide how to react.
    """
    problems: list[str] = []

    if not str(REPORT_DIR).strip():
        problems.append("REPORT_DIR is empty.")

    if SMTP_PORT <= 0:
        problems.append("SMTP_PORT must be a positive integer.")
    if not SMTP_HOST.strip():
        problems.append("SMTP_HOST is empty.")
    if not SMTP_USER.strip():
        problems.append("SMTP_USER is not set (Gmail address).")
    if not SMTP_PASSWORD.strip():
        problems.append("SMTP_PASSWORD is not set (Gmail App Password).")
    if not EMAIL_FROM.strip():
        problems.append("EMAIL_FROM is empty (and no SMTP_USER to fall back to).")

    if not (EMAIL_TO or EMAIL_CC or EMAIL_BCC):
        problems.append("No recipients set (EMAIL_TO / EMAIL_CC / EMAIL_BCC).")

    return problems
