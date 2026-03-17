"""Tests for the archive submission API endpoints."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models.common import DataClassification
from models.manifest import Manifest
from models.submission import ArchiveSubmission


def test_post_submission_can_create(
    session: Session,
    client: TestClient,
    submission: ArchiveSubmission,
    project_members_expanded,
) -> None:
    """Test creating a new archive submission"""
    # Mock ProjectDB API responses using actual expanded data
    with patch("api.main.ProjectDBApi") as mock_projectdb:
        mock_api = MagicMock()
        mock_projectdb.return_value = mock_api
        mock_api.get_project.return_value = {
            "id": 123,
            "title": "Test Project",
            "end_date": "2024-11-04",
        }
        # Use actual ProjectDB API response format with full person/role expansion
        mock_api.get_project_members.return_value = (
            project_members_expanded
            if project_members_expanded
            else [
                {
                    "person": {
                        "username": "user1",
                        "identities": {"items": [{"username": "user1"}]},
                    },
                    "role": {"role": "Principal Investigator"},
                }
            ]
        )

        response = client.post(
            "/api/v1/submission",
            json={
                "drive_name": "test-drive",
                "project_id": 123,
                "retention_period_years": 7,
                "retention_period_justification": "Standard retention",
                "data_classification": "OPEN",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["drive_name"] == "test-drive"


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

    response = client.get("/api/v1/submission")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        assert "drive_id" in data[0]
        assert "project_id" in data[0]
        assert "manifest_id" in data[0]


def test_post_submission_validates_retention_years(
    client: TestClient,
) -> None:
    """Test that retention period validation works"""
    with patch("api.main.get_projectdb_client") as mock_dep:
        mock_dep.return_value = MagicMock()
        response = client.post(
            "/api/v1/submission",
            json={
                "drive_name": "test-drive",
                "project_id": 123,
                "retention_period_years": -1,  # Invalid
                "retention_period_justification": "Invalid",
                "data_classification": "OPEN",
            },
        )
        # Should fail validation
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
                "drive_name": "test-drive",
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
                "data_classification": "OPEN",
            },
        )
        # Should fail validation - missing drive_name
        assert response.status_code in [400, 422]  # Validation error
