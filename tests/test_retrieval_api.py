"""Tests for the archive retrieval API endpoint."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from models.common import DataClassification
from models.retrieval import ACTIVE_RETRIEVAL_STAGES, ArchiveRetrieval, RetrievalJobStage
from models.submission import ArchiveSubmission, JobStage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DRIVE_NAME = "restst000000001-testing"
_DEST_PATH = "/mnt/vast/restst000000001-testing"


@pytest.fixture(name="completed_submission")
def completed_submission_fixture(session: Session) -> ArchiveSubmission:
    """A COMPLETED ArchiveSubmission persisted to the test database."""
    submission = ArchiveSubmission(
        drive_id=1234,
        project_id=123,
        drive_name=_DRIVE_NAME,
        retention_period_years=7,
        retention_period_justification="Standard research data retention",
        data_classification=DataClassification.SENSITIVE,
        stage=JobStage.COMPLETED,
        archive_manifest_key=f"{_DRIVE_NAME}/archive-manifest.json",
        archive_object_prefix=f"{_DRIVE_NAME}/",
        archive_part_count=2,
        archive_total_bytes=1024,
        started_timestamp=datetime(2024, 10, 13),
        completed_timestamp=datetime(2024, 10, 14),
    )
    session.add(submission)
    session.commit()
    session.refresh(submission)
    return submission


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_create_retrieval_returns_201(
    client: TestClient,
    session: Session,
    completed_submission: ArchiveSubmission,
) -> None:
    """A valid retrieval request returns 201 with a message."""
    with patch("api.routers.retrievals.run_archive_retrieval"), patch(
        "api.routers.retrievals.validate_destination_path", return_value=Path(_DEST_PATH)
    ):
        response = client.post(
            f"/api/v1/submission/{_DRIVE_NAME}/retrieve",
            json={"destination_path": _DEST_PATH},
        )
    assert response.status_code == 201
    data = response.json()
    assert "message" in data
    assert _DRIVE_NAME in data["message"]


def test_create_retrieval_persists_record(
    client: TestClient,
    session: Session,
    completed_submission: ArchiveSubmission,
) -> None:
    """A retrieval record is written to the database with the correct fields."""
    with patch("api.routers.retrievals.run_archive_retrieval"), patch(
        "api.routers.retrievals.validate_destination_path", return_value=Path(_DEST_PATH)
    ):
        response = client.post(
            f"/api/v1/submission/{_DRIVE_NAME}/retrieve",
            json={"destination_path": _DEST_PATH},
        )

    assert response.status_code == 201

    row = session.exec(
        select(ArchiveRetrieval).where(ArchiveRetrieval.drive_name == _DRIVE_NAME)
    ).first()

    assert row is not None
    assert row.stage == RetrievalJobStage.QUEUED
    assert row.destination_path == _DEST_PATH
    assert row.submission_id == completed_submission.id
    assert row.started_timestamp is not None


def test_create_retrieval_schedules_background_task(
    client: TestClient,
    session: Session,
    completed_submission: ArchiveSubmission,
) -> None:
    """The background task is invoked with the new retrieval record's ID."""
    with patch("api.routers.retrievals.run_archive_retrieval") as mock_task, patch(
        "api.routers.retrievals.validate_destination_path", return_value=Path(_DEST_PATH)
    ):
        response = client.post(
            f"/api/v1/submission/{_DRIVE_NAME}/retrieve",
            json={"destination_path": _DEST_PATH},
        )

    assert response.status_code == 201
    mock_task.assert_called_once()

    # The task should have been called with the retrieval record's ID.
    row = session.exec(
        select(ArchiveRetrieval).where(ArchiveRetrieval.drive_name == _DRIVE_NAME)
    ).first()
    assert row is not None
    call_args = mock_task.call_args
    assert call_args.args[0] == row.id


# ---------------------------------------------------------------------------
# 404 – no submission
# ---------------------------------------------------------------------------


def test_create_retrieval_404_when_no_submission(
    client: TestClient,
) -> None:
    """Returns 404 when no submission exists for the requested drive."""
    response = client.post(
        "/api/v1/submission/restst000000999-notfound/retrieve",
        json={"destination_path": _DEST_PATH},
    )
    assert response.status_code == 404
    assert "No archive submission found" in response.json()["detail"]


# ---------------------------------------------------------------------------
# 409 – submission not in COMPLETED state
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stage",
    [
        JobStage.QUEUED,
        JobStage.PACKAGING,
        JobStage.UPLOADING,
        JobStage.WRITING_MANIFEST,
        JobStage.CLEANUP,
        JobStage.FAILED,
        JobStage.ABANDONED,
    ],
)
def test_create_retrieval_409_for_non_completed_stages(
    client: TestClient,
    session: Session,
    submission: ArchiveSubmission,
    stage: JobStage,
) -> None:
    """Any non-COMPLETED submission stage results in 409."""
    submission.stage = stage
    session.add(submission)
    session.commit()

    response = client.post(
        f"/api/v1/submission/{_DRIVE_NAME}/retrieve",
        json={"destination_path": _DEST_PATH},
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "not in a completed state" in detail
    assert stage.value in detail


def test_create_retrieval_409_when_manifest_key_missing(
    client: TestClient,
    session: Session,
    submission: ArchiveSubmission,
) -> None:
    """Returns 409 when submission is COMPLETED but archive_manifest_key is absent."""
    submission.stage = JobStage.COMPLETED
    submission.archive_manifest_key = None
    session.add(submission)
    session.commit()

    response = client.post(
        f"/api/v1/submission/{_DRIVE_NAME}/retrieve",
        json={"destination_path": _DEST_PATH},
    )
    assert response.status_code == 409
    assert "manifest" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 409 – active retrieval already running
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("active_stage", list(ACTIVE_RETRIEVAL_STAGES))
def test_create_retrieval_409_when_active_retrieval_exists(
    client: TestClient,
    session: Session,
    completed_submission: ArchiveSubmission,
    active_stage: RetrievalJobStage,
) -> None:
    """Returns 409 for every active retrieval stage when a job already exists."""
    existing = ArchiveRetrieval(
        drive_name=_DRIVE_NAME,
        submission_id=completed_submission.id,
        destination_path=_DEST_PATH,
        stage=active_stage,
        started_timestamp=datetime.now(),
        last_updated_timestamp=datetime.now(),
    )
    session.add(existing)
    session.commit()

    with patch(
        "api.routers.retrievals.validate_destination_path", return_value=Path(_DEST_PATH)
    ):
        response = client.post(
            f"/api/v1/submission/{_DRIVE_NAME}/retrieve",
            json={"destination_path": _DEST_PATH},
        )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "already active" in detail
    assert active_stage.value in detail


def test_create_retrieval_allows_new_job_after_completed_retrieval(
    client: TestClient,
    session: Session,
    completed_submission: ArchiveSubmission,
) -> None:
    """A new retrieval job can be started after a previous one completed."""
    previous = ArchiveRetrieval(
        drive_name=_DRIVE_NAME,
        submission_id=completed_submission.id,
        destination_path=_DEST_PATH,
        stage=RetrievalJobStage.COMPLETED,
        started_timestamp=datetime.now(),
        completed_timestamp=datetime.now(),
    )
    session.add(previous)
    session.commit()

    with patch("api.routers.retrievals.run_archive_retrieval"), patch(
        "api.routers.retrievals.validate_destination_path", return_value=Path(_DEST_PATH)
    ):
        response = client.post(
            f"/api/v1/submission/{_DRIVE_NAME}/retrieve",
            json={"destination_path": _DEST_PATH},
        )
    assert response.status_code == 201


def test_create_retrieval_allows_new_job_after_failed_retrieval(
    client: TestClient,
    session: Session,
    completed_submission: ArchiveSubmission,
) -> None:
    """A new retrieval job can be started after a previous one failed."""
    previous = ArchiveRetrieval(
        drive_name=_DRIVE_NAME,
        submission_id=completed_submission.id,
        destination_path=_DEST_PATH,
        stage=RetrievalJobStage.FAILED,
        failure_reason="Network error",
        started_timestamp=datetime.now(),
        failed_timestamp=datetime.now(),
    )
    session.add(previous)
    session.commit()

    with patch("api.routers.retrievals.run_archive_retrieval"), patch(
        "api.routers.retrievals.validate_destination_path", return_value=Path(_DEST_PATH)
    ):
        response = client.post(
            f"/api/v1/submission/{_DRIVE_NAME}/retrieve",
            json={"destination_path": _DEST_PATH},
        )
    assert response.status_code == 201


# ---------------------------------------------------------------------------
# 400 – destination path validation failures
# ---------------------------------------------------------------------------


def test_create_retrieval_400_when_destination_path_not_found(
    client: TestClient,
    session: Session,
    completed_submission: ArchiveSubmission,
) -> None:
    """Returns 400 when the destination path does not exist."""
    with patch(
        "api.routers.retrievals.validate_destination_path",
        side_effect=FileNotFoundError("path does not exist"),
    ):
        response = client.post(
            f"/api/v1/submission/{_DRIVE_NAME}/retrieve",
            json={"destination_path": "/mnt/vast/nonexistent"},
        )
    assert response.status_code == 400
    assert "Destination path validation failed" in response.json()["detail"]


def test_create_retrieval_400_when_destination_not_writable(
    client: TestClient,
    session: Session,
    completed_submission: ArchiveSubmission,
) -> None:
    """Returns 400 when the destination path is not writable."""
    with patch(
        "api.routers.retrievals.validate_destination_path",
        side_effect=PermissionError("cannot write"),
    ):
        response = client.post(
            f"/api/v1/submission/{_DRIVE_NAME}/retrieve",
            json={"destination_path": "/mnt/vast/readonly"},
        )
    assert response.status_code == 400
    assert "Destination path validation failed" in response.json()["detail"]


# ---------------------------------------------------------------------------
# 422 – request validation
# ---------------------------------------------------------------------------


def test_create_retrieval_422_when_destination_path_missing(
    client: TestClient,
    session: Session,
    completed_submission: ArchiveSubmission,
) -> None:
    """Returns 422 when the required destination_path field is absent."""
    response = client.post(
        f"/api/v1/submission/{_DRIVE_NAME}/retrieve",
        json={},
    )
    assert response.status_code == 422
