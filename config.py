"""Centralised configuration for the Daily Report Sender.

Phase 1 scope
-------------
This is a deliberately minimal stub. It loads settings from a git-ignored
``.env`` file (falling back to sensible defaults) and exposes only what the
Phase 1 skeleton needs: the directory to monitor and the logging settings.

The monitored directory is *configurable* via the ``REPORT_DIR`` environment
variable and is never hardcoded in the application logic. Later phases will
extend this module with SMTP credentials, recipients, and the dedup state
file path.
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
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))

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
