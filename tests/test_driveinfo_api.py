"""Tests for the /driveinfo endpoint."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import requests
from fastapi.testclient import TestClient

from api.main import app
from service.projectdb import get_projectdb_client

_DRIVE_NAME = "restst000000001-testing"


@contextmanager
def _projectdb_override(client_factory: Any) -> Iterator[None]:
    """Temporarily replace the ProjectDB dependency, restoring the previous override."""
    original = app.dependency_overrides.get(get_projectdb_client)
    app.dependency_overrides[get_projectdb_client] = client_factory
    try:
        yield
    finally:
        if original is None:
            app.dependency_overrides.pop(get_projectdb_client, None)
        else:
            app.dependency_overrides[get_projectdb_client] = original


def test_get_drive_info_returns_combined_drive_and_project(client: TestClient) -> None:
    """Happy path: drive data merged with project, codes, and members."""
    response = client.get("/api/v1/driveinfo", params={"drive_name": _DRIVE_NAME})
    assert response.status_code == 200
    data = response.json()

    assert data["drive"]["name"] == _DRIVE_NAME
    assert data["drive"]["allocated_gb"] == 4000.0
    # first_day comes from the project's research_drive service entry
    assert data["drive"]["first_day"] == "2023-04-13"

    assert data["project"]["id"] == 123
    assert data["project"]["title"] == "Test Project"
    assert [c["code"] for c in data["project"]["codes"]] == ["TEST-001"]

    members = data["project"]["members"]
    assert len(members) == 1
    assert members[0]["person"]["full_name"] == "User One"
    assert members[0]["person"]["username"] == "user1"
    assert members[0]["role"]["name"] == "Principal Investigator"


def test_get_drive_info_404_when_drive_unknown(client: TestClient) -> None:
    class NoDriveClient:
        def get_research_drive_by_name(self, drive_name: str) -> None:
            return None

    with _projectdb_override(lambda: NoDriveClient()):
        response = client.get("/api/v1/driveinfo", params={"drive_name": _DRIVE_NAME})
    assert response.status_code == 404
    assert "not found in ProjectDB" in response.json()["detail"]


def test_get_drive_info_404_when_no_projects(client: TestClient) -> None:
    class NoProjectsClient:
        def get_research_drive_by_name(self, drive_name: str) -> dict[str, Any]:
            return {"id": 1, "name": drive_name}

        def get_research_drive_projects(self, drive_id: int, expand=None):  # noqa: ANN001
            return []

    with _projectdb_override(lambda: NoProjectsClient()):
        response = client.get("/api/v1/driveinfo", params={"drive_name": _DRIVE_NAME})
    assert response.status_code == 404
    assert "No projects associated" in response.json()["detail"]


def test_get_drive_info_409_when_multiple_projects(client: TestClient) -> None:
    """A drive with more than one project cannot be displayed unambiguously."""

    class MultiProjectClient:
        def get_research_drive_by_name(self, drive_name: str) -> dict[str, Any]:
            return {"id": 1, "name": drive_name}

        def get_research_drive_projects(self, drive_id: int, expand=None):  # noqa: ANN001
            return [{"project": {"id": 123}}, {"project": {"id": 456}}]

    with _projectdb_override(lambda: MultiProjectClient()):
        response = client.get("/api/v1/driveinfo", params={"drive_name": _DRIVE_NAME})
    assert response.status_code == 409
    assert "Multiple projects are associated" in response.json()["detail"]


def test_get_drive_info_502_when_projectdb_unavailable(client: TestClient) -> None:
    class BrokenClient:
        def get_research_drive_by_name(self, drive_name: str):  # noqa: ANN001
            raise requests.exceptions.ConnectionError("projectdb unreachable")

    with _projectdb_override(lambda: BrokenClient()):
        response = client.get("/api/v1/driveinfo", params={"drive_name": _DRIVE_NAME})
    assert response.status_code == 502
    assert "ProjectDB request failed" in response.json()["detail"]
