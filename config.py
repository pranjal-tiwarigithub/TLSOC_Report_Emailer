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
* Email    — sender and admin alert address.
* Reports  — ``DEPARTMENT`` (branding), ``REPORT_TYPES`` and the per-type
             recipient config (``EMAIL_TO_<TYPE>`` etc.) exposed as
             ``REPORT_CONFIGS``; plus the ``subject_for`` / ``body_for`` helpers
             that weave the report type into each email.

Call :func:`validate_config` at startup to fail fast (with clear messages)
when a required value is missing or malformed, rather than crashing mid-run.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
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

# --- Dedup state (Phase 7) --------------------------------------------------
# Records the date of the last successful send so a re-run on the same day
# does not resend. Relative paths resolve from the project root.
STATE_FILE: Path = _resolve_path(os.getenv("STATE_FILE", "state/last_sent.txt"))

# --- SMTP / email settings (Phase 5) ---------------------------------------
# Gmail SMTP defaults; overridable via .env. Port 587 uses STARTTLS.
SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = _get_int("SMTP_PORT", 587)

# Secrets — provided via .env only, NEVER hardcoded. Empty until you set them.
SMTP_USER: str = os.getenv("SMTP_USER", "")          # Gmail username/address
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")  # Gmail App Password

# Sender address. Defaults to the SMTP username when not set separately.
EMAIL_FROM: str = os.getenv("EMAIL_FROM", "") or SMTP_USER

# Admin address(es) that receive failure alerts (Phase 5 decision).
ALERT_EMAIL_TO: list[str] = _split_csv(os.getenv("ALERT_EMAIL_TO", ""))

# --- Department name (Phase 9) ---------------------------------------------
# Shown in every email subject/body. Configurable so each deployment can brand
# its reports (e.g. "ASC", "SOC", a team name).
DEPARTMENT: str = os.getenv("DEPARTMENT", "TLSOC").strip()

# --- Report types and per-type recipients (Phase 9) ------------------------
# The folder now holds multiple report PDFs per day, one per source (web,
# email, proxy, …). REPORT_TYPES declares which types this deployment sends;
# each type has its own recipient lists read from EMAIL_TO_<TYPE> etc.
REPORT_TYPES: list[str] = _split_csv(os.getenv("REPORT_TYPES", "web,email,proxy"))


@dataclass(frozen=True)
class ReportType:
    """Configuration for one report type (e.g. web / email / proxy)."""

    name: str              # lowercase type token, e.g. "web"
    display_name: str      # human-facing, e.g. "Web"
    to: list[str]
    cc: list[str]
    bcc: list[str]

    def has_recipients(self) -> bool:
        """True if at least one To/CC/BCC address is configured."""
        return bool(self.to or self.cc or self.bcc)


def _load_report_config(name: str) -> ReportType:
    """Build a :class:`ReportType` for ``name`` from its EMAIL_*_<TYPE> vars."""
    suffix = name.upper()
    return ReportType(
        name=name,
        display_name=name.capitalize(),
        to=_split_csv(os.getenv(f"EMAIL_TO_{suffix}", "")),
        cc=_split_csv(os.getenv(f"EMAIL_CC_{suffix}", "")),
        bcc=_split_csv(os.getenv(f"EMAIL_BCC_{suffix}", "")),
    )


# Map of declared type name -> its resolved configuration.
REPORT_CONFIGS: dict[str, ReportType] = {
    name: _load_report_config(name) for name in REPORT_TYPES
}


def subject_for(report_type: str, today: date | None = None) -> str:
    """Return the email subject for ``report_type`` on ``today``.

    Format: ``"<DEPARTMENT> Daily <Type> Report - <YYYY-MM-DD>"``.
    """
    today = today or date.today()
    display = REPORT_CONFIGS[report_type].display_name if report_type in REPORT_CONFIGS \
        else report_type.capitalize()
    return f"{DEPARTMENT} Daily {display} Report - {today.isoformat()}"


def body_for(report_type: str) -> str:
    """Return the email body for ``report_type``.

    The report type is woven into the text so the wording matches whatever is
    being sent (e.g. "Proxy Monitoring Report" / "monitored proxy assets"),
    rather than the previously hardcoded "web".
    """
    display = REPORT_CONFIGS[report_type].display_name if report_type in REPORT_CONFIGS \
        else report_type.capitalize()
    name = report_type.lower()
    return (
        "Hello Team,\n\n"
        f"Please find attached the {DEPARTMENT} {display} Monitoring Report for today. "
        "This report provides a summary of the monitoring activities, "
        "key observations of past 24 hours, "
        f"and the current status of the monitored {name} assets.\n\n"
        "Kindly review the attached report for the latest updates. "
        "If you have any questions or require additional information, "
        f"please feel free to contact the {DEPARTMENT} team.\n\n"
        "Regards,\n"
        f"Team {DEPARTMENT}\n"
    )


def validate_config() -> list[str]:
    """Return a list of configuration problems (empty list means all good).

    Checks the values that must be present and well-formed for a real run:
    the report directory, SMTP credentials, a sender, a department name, and at
    least one report type — each declared type having at least one recipient.
    Returning a list (rather than raising) lets the caller report every problem
    at once and decide how to react.
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

    if not DEPARTMENT:
        problems.append("DEPARTMENT is empty.")

    if not REPORT_TYPES:
        problems.append("No report types configured (REPORT_TYPES).")
    for name, report in REPORT_CONFIGS.items():
        if not report.has_recipients():
            problems.append(
                f"Report type '{name}' has no recipients "
                f"(EMAIL_TO_{name.upper()} / EMAIL_CC_{name.upper()} / "
                f"EMAIL_BCC_{name.upper()})."
            )

    return problems
