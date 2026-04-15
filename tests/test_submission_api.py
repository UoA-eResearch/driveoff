"""Tests for the archive submission API endpoints."""

from unittest.mock import patch

import requests
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from api.main import app
from models.manifest import Manifest
from models.submission import ArchiveSubmission
from service.projectdb import get_projectdb_client


def test_post_submission_can_create(
    client: TestClient,
) -> None:
    """Test creating a new archive submission"""
    # Mock the background task so it doesn't try to access the database
    with patch("api.main.generate_ro_crate_async"):
        response = client.post(
            "/api/v1/submission",
            json={
                "drive_name": "restst000000001-testing",
                "project_id": 123,
                "retention_period_years": 7,
                "retention_period_justification": "Standard retention",
                "data_classification": "Sensitive",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "message" in data
        assert "Archive submission created" in data["message"]
        assert "RO-Crate generation is in progress" in data["message"]


def test_post_submission_updates_existing_single_row(
    client: TestClient,
    session: Session,
) -> None:
    """Repeated submission for the same drive updates one existing row."""
    with patch("api.main.generate_ro_crate_async"):
        create_response = client.post(
            "/api/v1/submission",
            json={
                "drive_name": "restst000000001-testing",
                "project_id": 123,
                "retention_period_years": 7,
                "retention_period_justification": "Initial reason",
                "data_classification": "Sensitive",
            },
        )
        assert create_response.status_code == 201

        update_response = client.post(
            "/api/v1/submission",
            json={
                "drive_name": "restst000000001-testing",
                "project_id": 123,
                "retention_period_years": 10,
                "retention_period_justification": "Updated reason",
                "data_classification": "Restricted",
            },
        )
        assert update_response.status_code == 201
        update_payload = update_response.json()
        assert "Archive submission updated" in update_payload["message"]

    rows = session.exec(
        select(ArchiveSubmission).where(
            ArchiveSubmission.drive_name == "restst000000001-testing"
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].retention_period_years == 10
    assert rows[0].retention_period_justification == "Updated reason"
    assert rows[0].data_classification.value == "Restricted"


def test_post_submission_rejects_completed_drive(
    client: TestClient,
    session: Session,
    submission: ArchiveSubmission,
) -> None:
    """A drive that is already successfully archived cannot be resubmitted."""
    submission.is_completed = True
    session.add(submission)
    session.commit()

    with patch("api.main.generate_ro_crate_async"):
        response = client.post(
            "/api/v1/submission",
            json={
                "drive_name": "restst000000001-testing",
                "project_id": 123,
                "retention_period_years": 7,
                "retention_period_justification": "Standard retention",
                "data_classification": "Sensitive",
            },
        )
    assert response.status_code == 409
    assert "already been successfully archived" in response.json()["detail"]


def test_post_submission_returns_502_when_projectdb_project_lookup_fails(
    client: TestClient,
) -> None:
    """Upstream ProjectDB failures should surface as 502, not 404."""

    class BrokenProjectDbClient:
        def get_research_drive_by_name(self, drive_name: str) -> dict[str, object]:
            return {
                "allocated_gb": 4000.0,
                "date": "2026-03-09",
                "free_gb": 4000.0,
                "id": 6904394,
                "name": drive_name,
                "percentage_used": 0.0,
                "used_gb": 0.0,
            }

        def get_research_drive_projects(
            self, drive_id: int, expand=None
        ):  # noqa: ANN001
            raise requests.exceptions.Timeout("upstream timeout")

    original_projectdb_override = app.dependency_overrides.get(get_projectdb_client)
    app.dependency_overrides[get_projectdb_client] = lambda: BrokenProjectDbClient()

    try:
        with patch("api.main.generate_ro_crate_async"):
            response = client.post(
                "/api/v1/submission",
                json={
                    "drive_name": "restst000000001-testing",
                    "project_id": 123,
                    "retention_period_years": 7,
                    "retention_period_justification": "Standard retention",
                    "data_classification": "Sensitive",
                },
            )
        assert response.status_code == 502
        assert "ProjectDB request failed" in response.json()["detail"]
    finally:
        if original_projectdb_override is None:
            app.dependency_overrides.pop(get_projectdb_client, None)
        else:
            app.dependency_overrides[get_projectdb_client] = original_projectdb_override


def test_get_submission_returns_archive_record(
    session: Session,
    client: TestClient,
    submission: ArchiveSubmission,
    manifest: Manifest,
) -> None:
    """Test retrieving an archive submission"""
    # Add test data to session
    manifest.id = 1
    session.add(manifest)
    session.flush()

    submission.manifest_id = manifest.id
    session.add(submission)
    session.commit()

    response = client.get(
        "/api/v1/submission", params={"drive_name": "restst000000001-testing"}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert data["drive_id"] == submission.drive_id
    assert data["project_id"] == submission.project_id
    assert data["drive_name"] == submission.drive_name
    assert data["retention_period_years"] == submission.retention_period_years
    assert (
        data["retention_period_justification"]
        == submission.retention_period_justification
    )
    assert data["data_classification"] == submission.data_classification.value
    assert data["archive_location"] == submission.archive_location
    assert data["is_completed"] is False
    assert data["is_failed"] is False
    assert data["failure_reason"] is None
    assert data["failed_timestamp"] is None
    assert data["manifest"] == manifest.manifest


def test_post_submission_validates_retention_years(
    client: TestClient,
) -> None:
    """Test that retention period validation works"""
    with patch("api.main.generate_ro_crate_async"):
        response = client.post(
            "/api/v1/submission",
            json={
                "drive_name": "restst000000001-testing",
                "project_id": 123,
                "retention_period_years": "Z",  # Invalid
                "retention_period_justification": "Invalid",
                "data_classification": "Sensitive",
            },
        )
        # Should fail validation - invalid retention years
        assert response.status_code == 422


def test_post_submission_validates_classification(
    client: TestClient,
) -> None:
    """Test that data classification validation works"""
    with patch("api.main.generate_ro_crate_async"):
        response = client.post(
            "/api/v1/submission",
            json={
                "drive_name": "restst000000001-testing",
                "project_id": 123,
                "retention_period_years": 7,
                "retention_period_justification": "Standard",
                "data_classification": "INVALID_CLASS",
            },
        )
        # Should fail validation
        assert response.status_code == 422


def test_post_submission_requires_drive_name(
    client: TestClient,
) -> None:
    """Test that drive_name is required"""
    with patch("api.main.generate_ro_crate_async"):
        response = client.post(
            "/api/v1/submission",
            json={
                "project_id": 123,
                "retention_period_years": 7,
                "retention_period_justification": "Standard",
                "data_classification": "Sensitive",
            },
        )
        # Should fail validation - missing drive_name
        assert response.status_code == 422


def test_post_submission_accepts_drive_name_with_fullstop(
    client: TestClient,
) -> None:
    """Drive names with dot in suffix are accepted by validation."""
    with patch("api.main.generate_ro_crate_async"):
        response = client.post(
            "/api/v1/submission",
            json={
                "drive_name": "resmed202200024_adm.eresearch",
                "project_id": 123,
                "retention_period_years": 7,
                "retention_period_justification": "Standard",
                "data_classification": "Sensitive",
            },
        )
        assert response.status_code == 201
