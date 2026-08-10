"""Tests for logging configuration setup."""

from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from types import SimpleNamespace

from utils.logging import configure_logging


def test_configure_logging_adds_single_file_handler(tmp_path: Path, monkeypatch) -> None:
    log_file = tmp_path / "driveoff.log"
    settings = SimpleNamespace(
        log_level="INFO",
        log_to_file_enabled=True,
        log_file_path=str(log_file),
        log_file_rotation_when="midnight",
        log_file_rotation_interval=1,
        log_file_backup_count=14,
    )
    monkeypatch.setattr("utils.logging.get_settings", lambda: settings)

    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level

    try:
        root.handlers = []
        configure_logging()
        configure_logging()

        file_handlers = [handler for handler in root.handlers if isinstance(handler, TimedRotatingFileHandler)]
        assert len(file_handlers) == 1
        assert Path(file_handlers[0].baseFilename).resolve() == log_file.resolve()
        watchfiles_record = logging.LogRecord(
            name="watchfiles.main",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="change detected",
            args=(),
            exc_info=None,
        )
        assert not file_handlers[0].filter(watchfiles_record)

        app_record = logging.LogRecord(
            name="workers.submission_worker",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="job completed",
            args=(),
            exc_info=None,
        )
        assert file_handlers[0].filter(app_record)
    finally:
        for handler in list(root.handlers):
            handler.close()
        root.handlers = original_handlers
        root.setLevel(original_level)


def test_configure_logging_keeps_stdout_when_file_handler_fails(monkeypatch) -> None:
    settings = SimpleNamespace(
        log_level="INFO",
        log_to_file_enabled=True,
        log_file_path="logs/driveoff.log",
        log_file_rotation_when="midnight",
        log_file_rotation_interval=1,
        log_file_backup_count=14,
    )
    monkeypatch.setattr("utils.logging.get_settings", lambda: settings)

    def raise_oserror(*_args, **_kwargs):
        raise OSError("disk unavailable")

    monkeypatch.setattr("utils.logging.TimedRotatingFileHandler", raise_oserror)

    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level

    try:
        root.handlers = []
        configure_logging()
        assert any(isinstance(handler, logging.StreamHandler) for handler in root.handlers)
        assert not any(isinstance(handler, TimedRotatingFileHandler) for handler in root.handlers)
    finally:
        for handler in list(root.handlers):
            handler.close()
        root.handlers = original_handlers
        root.setLevel(original_level)
