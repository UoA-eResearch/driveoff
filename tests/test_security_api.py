"""Tests for API key authentication, permissions, and key redaction in logs."""

from __future__ import annotations

import json
import logging

from fastapi.testclient import TestClient

from api.main import _redact_query, app
from api.security import ApiKey, HttpAction, read_api_keys

_DRIVE_NAME = "restst000000001-testing"
_KEY_VALUE = "test-key-123"


def _install_known_key(actions: list[HttpAction]) -> None:
    """Replace the conftest key override with a known key limited to *actions*."""

    def override() -> dict[str, ApiKey]:
        return {_KEY_VALUE: ApiKey(value=_KEY_VALUE, actions=actions)}

    app.dependency_overrides[read_api_keys] = override


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def test_missing_api_key_returns_401(client: TestClient) -> None:
    """Requests without an x-api-key header are rejected."""
    bare = TestClient(app)
    response = bare.get("/api/v1/submission", params={"drive_name": _DRIVE_NAME})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API Key"


def test_wrong_api_key_returns_401(client: TestClient) -> None:
    """Requests with an unknown key value are rejected."""
    response = client.get(
        "/api/v1/submission",
        params={"drive_name": _DRIVE_NAME},
        headers={"x-api-key": "not-a-real-key"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API Key"


def test_valid_header_key_authenticates(client: TestClient) -> None:
    """A valid x-api-key header authenticates (404 here means auth passed)."""
    _install_known_key(["GET"])
    bare = TestClient(app)
    response = bare.get(
        "/api/v1/submission",
        params={"drive_name": "restst000000999-testing"},
        headers={"x-api-key": _KEY_VALUE},
    )
    assert response.status_code == 404


def test_query_param_api_key_not_accepted(client: TestClient) -> None:
    """A valid key value sent as a query parameter must NOT authenticate.

    Query strings end up in request logs, proxy logs, and browser history,
    so API keys are header-only.
    """
    _install_known_key(["GET"])
    bare = TestClient(app)
    response = bare.get(
        "/api/v1/submission",
        params={"drive_name": _DRIVE_NAME, "api-key": _KEY_VALUE},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


def test_key_without_action_permission_is_rejected(client: TestClient) -> None:
    """A valid key lacking the required action gets 403 (authenticated but
    not authorised), distinct from the 401 for a missing/invalid key."""
    _install_known_key(["GET"])
    bare = TestClient(app)
    response = bare.post(
        "/api/v1/submission",
        json={
            "drive_name": _DRIVE_NAME,
            "retention_period_years": 7,
            "data_classification": "Sensitive",
        },
        headers={"x-api-key": _KEY_VALUE},
    )
    assert response.status_code == 403
    assert "does not have POST rights" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Query string redaction in request logs
# ---------------------------------------------------------------------------


def test_redact_query_masks_sensitive_params() -> None:
    assert _redact_query("") == ""
    assert _redact_query("drive_name=abc") == "drive_name=abc"
    assert _redact_query("api-key=secret") == "api-key=REDACTED"
    assert _redact_query("API-KEY=secret") == "API-KEY=REDACTED"
    assert _redact_query("api_key=secret&x-api-key=secret") == "api_key=REDACTED&x-api-key=REDACTED"
    redacted = _redact_query("drive_name=abc&api-key=secret")
    assert "secret" not in redacted
    assert "drive_name=abc" in redacted


def test_api_key_query_param_never_reaches_logs(client: TestClient, caplog) -> None:
    """The request log must not contain a key sent (incorrectly) via query."""
    caplog.set_level(logging.INFO)
    secret = "super-secret-key-value"

    bare = TestClient(app)
    response = bare.get(
        "/api/v1/submission",
        params={"drive_name": _DRIVE_NAME, "api-key": secret},
    )
    assert response.status_code == 401

    api_events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "utils.logging" and '"event": "api.request.completed"' in record.message
    ]
    assert api_events
    event = api_events[-1]
    assert "REDACTED" in event["query"]
    assert secret not in event["query"]
    assert f"drive_name={_DRIVE_NAME}" in event["query"]
    # No log line emitted by the application may contain the secret.
    # (httpx's own client-side request log is test infrastructure, not ours.)
    assert all(secret not in record.message for record in caplog.records if record.name == "utils.logging")
