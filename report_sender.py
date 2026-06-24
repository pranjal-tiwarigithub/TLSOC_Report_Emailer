#!/usr/bin/env python3
"""Daily Report Sender — application entry point.

Phase 1 scope
-------------
This is the orchestrator skeleton. For now it only:

* initialises logging, and
* logs a startup banner showing the effective configuration.

The real pipeline (locate latest PDF -> validate -> email) is added in later
phases. Running this file is the primary way to smoke-test the Phase 1
skeleton.
"""

from __future__ import annotations

import sys

import config
from logger import get_logger

logger = get_logger(__name__)


def main() -> int:
    """Run the Phase 1 skeleton.

    Returns:
        Process exit code (0 = success). Wired to ``sys.exit`` below so cron
        can detect failures in later phases.
    """
    logger.info("=== Daily Report Sender starting (Phase 1 skeleton) ===")
    logger.info("Monitored report directory: %s", config.REPORT_DIR)
    logger.info("Log level: %s", config.LOG_LEVEL)
    logger.info("Log file: %s", config.LOG_FILE)
    logger.debug("Debug logging is enabled.")
    logger.info("Phase 1 skeleton ran successfully. Nothing else to do yet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
