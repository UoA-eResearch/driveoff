"""Tests for the archive submission API endpoints."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from models.manifest import Manifest
from models.submission import ArchiveSubmission


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
        assert "RO-Crate generation is in progress" in data["message"]


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
    assert "drive_id" in data
    assert "project_id" in data
    assert "manifest" in data


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
        assert response.status_code in [400, 422]  # Validation error


def test_post_submission_validates_classification(
    client: TestClient,
) -> None:
    """Test that data classification validation works"""
    with patch("api.main.get_projectdb_client") as mock_dep:
        mock_dep.return_value = MagicMock()
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
        assert response.status_code in [400, 422]  # Validation error


def test_post_submission_requires_drive_name(
    client: TestClient,
) -> None:
    """Test that drive_name is required"""
    with patch("api.main.get_projectdb_client") as mock_dep:
        mock_dep.return_value = MagicMock()
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
        assert response.status_code in [400, 422]  # Validation error
