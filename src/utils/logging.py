"""Application-wide logging utilities."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

from asgi_correlation_id import correlation_id

from config import get_settings
from utils import utc_now

logger = logging.getLogger(__name__)
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
FILE_LOG_EXCLUDED_LOGGER_PREFIXES = ("watchfiles",)


class _ExcludeLoggerPrefixFilter(logging.Filter):
    """Exclude log records from logger names with specific prefixes."""

    def __init__(self, excluded_prefixes: tuple[str, ...]):
        super().__init__()
        self._excluded_prefixes = excluded_prefixes

    def filter(self, record: logging.LogRecord) -> bool:
        return not record.name.startswith(self._excluded_prefixes)


def _has_stream_handler(root_logger: logging.Logger) -> bool:
    return any(isinstance(handler, logging.StreamHandler) for handler in root_logger.handlers)


def _has_file_handler(root_logger: logging.Logger, file_path: Path) -> bool:
    expected = file_path.resolve()
    for handler in root_logger.handlers:
        if not isinstance(handler, TimedRotatingFileHandler):
            continue
        base_filename = getattr(handler, "baseFilename", None)
        if base_filename is None:
            continue
        if Path(base_filename).resolve() == expected:
            return True
    return False


def _add_file_handler(root_logger: logging.Logger) -> None:
    settings = get_settings()
    file_path = Path(settings.log_file_path).expanduser()
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if _has_file_handler(root_logger, file_path):
        return

    handler = TimedRotatingFileHandler(
        filename=str(file_path),
        when=settings.log_file_rotation_when,
        interval=settings.log_file_rotation_interval,
        backupCount=settings.log_file_backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.addFilter(_ExcludeLoggerPrefixFilter(FILE_LOG_EXCLUDED_LOGGER_PREFIXES))
    root_logger.addHandler(handler)


def configure_logging() -> None:
    """Initialize logging with stdout and optional file rotation.

    File logging setup is best-effort; failures are logged and stdout logging remains active.
    """

    root_logger = logging.getLogger()
    settings = get_settings()
    root_logger.setLevel(settings.log_level)

    if not _has_stream_handler(root_logger):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root_logger.addHandler(stream_handler)

    if settings.log_to_file_enabled:
        try:
            _add_file_handler(root_logger)
        except Exception as error:  # pragma: no cover - defensive startup guard
            logger.warning("Failed to configure file logging: %s", error)


def log_event(
    level: int,
    event: str,
    *,
    exc_info: bool = False,
    **context: Any,
) -> None:
    """Emit a structured JSON log entry."""
    payload = {"event": event, **context}
    request_id = correlation_id.get()
    if request_id is not None and "request_id" not in payload:
        payload["request_id"] = request_id
    logger.log(level, json.dumps(payload, default=str), exc_info=exc_info)


def elapsed_ms(started_at: datetime) -> int:
    """Compute elapsed milliseconds from a start timestamp (UTC-aware, from utc_now)."""
    return int((utc_now() - started_at).total_seconds() * 1000)
