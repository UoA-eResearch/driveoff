"""Tests for centralized API request and exception logging."""

from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from api.dependencies import get_session
from api.main import app


def test_request_logging_middleware_logs_completed_request(client: TestClient, caplog) -> None:
    caplog.set_level(logging.INFO)

    response = client.get("/api/v1/submission", params={"drive_name": "restst000000999-testing"})

    assert response.status_code == 404
    assert '"event": "api.request.completed"' in caplog.text
    assert '"method": "GET"' in caplog.text
    assert '"path": "/api/v1/submission"' in caplog.text
    assert '"status_code": 404' in caplog.text


def test_unhandled_exception_handler_logs_exception(client: TestClient, caplog) -> None:
    caplog.set_level(logging.INFO)

    original_session_override = app.dependency_overrides[get_session]

    def broken_session_override():
        raise RuntimeError("db unavailable")

    app.dependency_overrides[get_session] = broken_session_override
    try:
        response = client.get("/api/v1/submission", params={"drive_name": "restst000000001-testing"})
    finally:
        app.dependency_overrides[get_session] = original_session_override

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal Server Error"}
    assert '"event": "api.unhandled_exception"' in caplog.text
    assert '"error_type": "RuntimeError"' in caplog.text
    assert '"event": "api.request.completed"' in caplog.text
    assert '"status_code": 500' in caplog.text
