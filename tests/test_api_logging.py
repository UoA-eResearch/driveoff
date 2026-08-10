"""Tests for centralized API request and exception logging."""

from __future__ import annotations

import json
import logging

from fastapi.testclient import TestClient

from api.dependencies import get_session
from api.main import app


def test_request_logging_middleware_logs_completed_request(client: TestClient, caplog) -> None:
    caplog.set_level(logging.INFO)

    response = client.get("/api/v1/submission", params={"drive_name": "restst000000999-testing"})

    assert response.status_code == 404
    assert response.headers.get("X-Request-ID")

    api_events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "utils.logging" and '"event": "api.request.completed"' in record.message
    ]
    assert api_events
    event = api_events[-1]
    assert event["method"] == "GET"
    assert event["path"] == "/api/v1/submission"
    assert event["status_code"] == 404
    assert event["request_id"] == response.headers["X-Request-ID"]
    assert "error_detail" in event


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
    assert response.headers.get("X-Request-ID")

    exception_events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "utils.logging" and '"event": "api.unhandled_exception"' in record.message
    ]
    assert exception_events
    exception_event = exception_events[-1]
    assert exception_event["error_type"] == "RuntimeError"
    assert exception_event["request_id"] == response.headers["X-Request-ID"]

    completion_events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "utils.logging" and '"event": "api.request.completed"' in record.message
    ]
    assert completion_events
    completion_event = completion_events[-1]
    assert completion_event["status_code"] == 500
    assert completion_event["request_id"] == response.headers["X-Request-ID"]
    assert completion_event["error_detail"] == "Internal Server Error"
