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


# --- Monitored report directory (configurable, never hardcoded) ------------
# Default mirrors the production location, but any deployment can override it
# by setting REPORT_DIR in .env or the environment.
REPORT_DIR: Path = Path(
    os.getenv("REPORT_DIR", "/opt/TLSOCDockerDeploy/reporting/output/pdf")
).expanduser()

# --- Logging settings -------------------------------------------------------
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE: Path = _resolve_path(os.getenv("LOG_FILE", "logs/sender.log"))
