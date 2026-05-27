"""Application-wide logging utilities."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from config import get_settings

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Initialize logging once and align root level with configured settings."""
    root_logger = logging.getLogger()
    configured_level = get_settings().log_level
    if not root_logger.handlers:
        logging.basicConfig(
            level=configured_level,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        )
    else:
        root_logger.setLevel(configured_level)


def log_event(
    level: int,
    event: str,
    *,
    exc_info: bool = False,
    **context: Any,
) -> None:
    """Emit a structured JSON log entry."""
    payload = {"event": event, **context}
    logger.log(level, json.dumps(payload, default=str), exc_info=exc_info)


def elapsed_ms(started_at: datetime) -> int:
    """Compute elapsed milliseconds from a start timestamp."""
    return int((datetime.now() - started_at).total_seconds() * 1000)
