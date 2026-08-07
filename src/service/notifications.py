"""Notification helpers for job terminal-state alerts."""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

from config import get_settings
from utils.logging import log_event


def _current_mode() -> str:
    """Return current runtime mode for alert labeling."""
    return os.environ.get("MODE", "development")


def _nonprod_prefix(mode: str) -> str:
    """Return a label prefix for non-production notifications."""
    if mode.lower() == "production":
        return ""
    return f"[NONPROD:{mode}] "


def _truncate(value: str | None, max_chars: int = 400) -> str | None:
    """Trim long text fields to keep Slack messages readable."""
    if value is None:
        return None
    if len(value) <= max_chars:
        return value
    return f"{value[:max_chars]}..."


def notify_job_result(
    *,
    job_type: str,
    status: str,
    drive_name: str,
    submission_id: int | None = None,
    retrieval_id: int | None = None,
    project_id: int | None = None,
    stage: str | None = None,
    retry_count: int | None = None,
    failure_reason: str | None = None,
    extra_context: dict[str, Any] | None = None,
) -> bool:
    """Best-effort Slack alert for terminal job states.

    Returns True if a request was sent and accepted by Slack, otherwise False.
    Any failure is logged and intentionally non-fatal to job processing.
    """
    settings = get_settings()

    if not settings.notifications_enabled:
        log_event(
            logging.DEBUG,
            "notifications.skipped",
            reason="disabled",
            job_type=job_type,
            status=status,
            drive_name=drive_name,
        )
        return False

    webhook = settings.notifications_slack_webhook_url
    if webhook is None:
        log_event(
            logging.WARNING,
            "notifications.skipped",
            reason="missing_webhook",
            job_type=job_type,
            status=status,
            drive_name=drive_name,
        )
        return False

    mode = _current_mode()
    prefix = _nonprod_prefix(mode)
    upper_status = status.upper()
    emoji = ":white_check_mark:" if upper_status == "COMPLETED" else ":x:"

    details: list[str] = [
        f"{emoji} {prefix}{job_type} {upper_status}",
        f"drive={drive_name}",
        f"mode={mode}",
    ]
    if submission_id is not None:
        details.append(f"submission_id={submission_id}")
    if retrieval_id is not None:
        details.append(f"retrieval_id={retrieval_id}")
    if project_id is not None:
        details.append(f"project_id={project_id}")
    if stage is not None:
        details.append(f"stage={stage}")
    if retry_count is not None:
        details.append(f"retry_count={retry_count}")

    trimmed_reason = _truncate(failure_reason)
    if trimmed_reason is not None:
        details.append(f"failure_reason={trimmed_reason}")

    if extra_context:
        compact_context = _truncate(str(extra_context), max_chars=600)
        if compact_context is not None:
            details.append(f"context={compact_context}")

    payload: dict[str, str] = {"text": " | ".join(details)}

    try:
        response = requests.post(
            webhook.get_secret_value(),
            json=payload,
            timeout=5,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        log_event(
            logging.ERROR,
            "notifications.send_failed",
            job_type=job_type,
            status=status,
            drive_name=drive_name,
            mode=mode,
            error=str(error),
        )
        return False
    except Exception as error:  # pragma: no cover - defensive best-effort guard
        log_event(
            logging.ERROR,
            "notifications.send_failed",
            job_type=job_type,
            status=status,
            drive_name=drive_name,
            mode=mode,
            error=str(error),
            error_type=type(error).__name__,
        )
        return False

    log_event(
        logging.INFO,
        "notifications.sent",
        job_type=job_type,
        status=status,
        drive_name=drive_name,
        mode=mode,
    )
    return True
