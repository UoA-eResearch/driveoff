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
            f"/api/v1/retrieval/{_DRIVE_NAME}",
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
            f"/api/v1/retrieval/{_DRIVE_NAME}",
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
            f"/api/v1/retrieval/{_DRIVE_NAME}",
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
        "/api/v1/retrieval/restst000000999-notfound",
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
        f"/api/v1/retrieval/{_DRIVE_NAME}",
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
        f"/api/v1/retrieval/{_DRIVE_NAME}",
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
            f"/api/v1/retrieval/{_DRIVE_NAME}",
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
            f"/api/v1/retrieval/{_DRIVE_NAME}",
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
            f"/api/v1/retrieval/{_DRIVE_NAME}",
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
            f"/api/v1/retrieval/{_DRIVE_NAME}",
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
            f"/api/v1/retrieval/{_DRIVE_NAME}",
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
        f"/api/v1/retrieval/{_DRIVE_NAME}",
        json={},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /retrieval/{retrieval_id} – update retrieval record
# ---------------------------------------------------------------------------


@pytest.fixture(name="queued_retrieval")
def queued_retrieval_fixture(
    session: Session, completed_submission: ArchiveSubmission
) -> ArchiveRetrieval:
    """A QUEUED ArchiveRetrieval persisted to the test database."""
    retrieval = ArchiveRetrieval(
        drive_name=_DRIVE_NAME,
        submission_id=completed_submission.id,
        destination_path=_DEST_PATH,
        stage=RetrievalJobStage.QUEUED,
        started_timestamp=datetime(2024, 10, 14, 10, 0, 0),
        last_updated_timestamp=datetime(2024, 10, 14, 10, 0, 0),
    )
    session.add(retrieval)
    session.commit()
    session.refresh(retrieval)
    return retrieval


def test_patch_retrieval_updates_stage(
    client: TestClient,
    queued_retrieval: ArchiveRetrieval,
) -> None:
    """PATCH with a new stage returns 200 and reflects the updated stage."""
    response = client.patch(
        f"/api/v1/retrieval/{queued_retrieval.id}",
        json={"stage": RetrievalJobStage.RESTORING.value},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["stage"] == RetrievalJobStage.RESTORING.value
    assert data["id"] == queued_retrieval.id


def test_patch_retrieval_sets_last_updated_timestamp(
    client: TestClient,
    session: Session,
    queued_retrieval: ArchiveRetrieval,
) -> None:
    """PATCH always refreshes last_updated_timestamp server-side."""
    original_ts = queued_retrieval.last_updated_timestamp
    response = client.patch(
        f"/api/v1/retrieval/{queued_retrieval.id}",
        json={"stage": RetrievalJobStage.DOWNLOADING.value},
    )
    assert response.status_code == 200
    session.refresh(queued_retrieval)
    assert queued_retrieval.last_updated_timestamp != original_ts


def test_patch_retrieval_sets_completed_timestamp_on_completed_stage(
    client: TestClient,
    session: Session,
    queued_retrieval: ArchiveRetrieval,
) -> None:
    """Transitioning to COMPLETED sets completed_timestamp automatically."""
    assert queued_retrieval.completed_timestamp is None
    response = client.patch(
        f"/api/v1/retrieval/{queued_retrieval.id}",
        json={"stage": RetrievalJobStage.COMPLETED.value},
    )
    assert response.status_code == 200
    session.refresh(queued_retrieval)
    assert queued_retrieval.completed_timestamp is not None


def test_patch_retrieval_does_not_overwrite_completed_timestamp(
    client: TestClient,
    session: Session,
    queued_retrieval: ArchiveRetrieval,
) -> None:
    """completed_timestamp is only set once (not overwritten on duplicate PATCH)."""
    original_completed = datetime(2024, 10, 14, 12, 0, 0)
    queued_retrieval.completed_timestamp = original_completed
    queued_retrieval.stage = RetrievalJobStage.COMPLETED
    session.add(queued_retrieval)
    session.commit()

    response = client.patch(
        f"/api/v1/retrieval/{queued_retrieval.id}",
        json={"stage": RetrievalJobStage.COMPLETED.value},
    )
    assert response.status_code == 200
    session.refresh(queued_retrieval)
    assert queued_retrieval.completed_timestamp == original_completed


def test_patch_retrieval_sets_failed_timestamp_on_failed_stage(
    client: TestClient,
    session: Session,
    queued_retrieval: ArchiveRetrieval,
) -> None:
    """Transitioning to FAILED sets failed_timestamp automatically."""
    assert queued_retrieval.failed_timestamp is None
    response = client.patch(
        f"/api/v1/retrieval/{queued_retrieval.id}",
        json={
            "stage": RetrievalJobStage.FAILED.value,
            "failure_reason": "download error",
        },
    )
    assert response.status_code == 200
    session.refresh(queued_retrieval)
    assert queued_retrieval.failed_timestamp is not None
    assert queued_retrieval.failure_reason == "download error"


def test_patch_retrieval_does_not_overwrite_failed_timestamp(
    client: TestClient,
    session: Session,
    queued_retrieval: ArchiveRetrieval,
) -> None:
    """failed_timestamp is only set once (not overwritten on duplicate PATCH)."""
    original_failed = datetime(2024, 10, 14, 11, 0, 0)
    queued_retrieval.failed_timestamp = original_failed
    queued_retrieval.stage = RetrievalJobStage.FAILED
    session.add(queued_retrieval)
    session.commit()

    response = client.patch(
        f"/api/v1/retrieval/{queued_retrieval.id}",
        json={"stage": RetrievalJobStage.FAILED.value},
    )
    assert response.status_code == 200
    session.refresh(queued_retrieval)
    assert queued_retrieval.failed_timestamp == original_failed


def test_patch_retrieval_partial_update_only_failure_reason(
    client: TestClient,
    session: Session,
    queued_retrieval: ArchiveRetrieval,
) -> None:
    """Sending only failure_reason does not alter the stage."""
    original_stage = queued_retrieval.stage
    response = client.patch(
        f"/api/v1/retrieval/{queued_retrieval.id}",
        json={"failure_reason": "transient error"},
    )
    assert response.status_code == 200
    session.refresh(queued_retrieval)
    assert queued_retrieval.stage == original_stage
    assert queued_retrieval.failure_reason == "transient error"


def test_patch_retrieval_updates_retrieved_part_keys_json(
    client: TestClient,
    session: Session,
    queued_retrieval: ArchiveRetrieval,
) -> None:
    """PATCH can set retrieved_part_keys_json."""
    keys_json = '["part1", "part2"]'
    response = client.patch(
        f"/api/v1/retrieval/{queued_retrieval.id}",
        json={"retrieved_part_keys_json": keys_json},
    )
    assert response.status_code == 200
    session.refresh(queued_retrieval)
    assert queued_retrieval.retrieved_part_keys_json == keys_json


def test_patch_retrieval_404_when_not_found(
    client: TestClient,
) -> None:
    """Returns 404 when no retrieval job exists with the given ID."""
    response = client.patch(
        "/api/v1/retrieval/99999",
        json={"stage": RetrievalJobStage.RESTORING.value},
    )
    assert response.status_code == 404
    assert "No retrieval job found" in response.json()["detail"]


def test_patch_retrieval_returns_full_response_model(
    client: TestClient,
    queued_retrieval: ArchiveRetrieval,
    completed_submission: ArchiveSubmission,
) -> None:
    """Response body contains all expected fields from RetrievalResponse."""
    response = client.patch(
        f"/api/v1/retrieval/{queued_retrieval.id}",
        json={"stage": RetrievalJobStage.EXTRACTING.value},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == queued_retrieval.id
    assert data["drive_name"] == _DRIVE_NAME
    assert data["submission_id"] == completed_submission.id
    assert data["destination_path"] == _DEST_PATH
    assert data["stage"] == RetrievalJobStage.EXTRACTING.value
    assert "last_updated_timestamp" in data


# ---------------------------------------------------------------------------
# GET /submission/{drive_name}/retrieve – get retrieval record
# ---------------------------------------------------------------------------


def test_get_retrieval_returns_200_with_record(
    client: TestClient,
    queued_retrieval: ArchiveRetrieval,
    completed_submission: ArchiveSubmission,
) -> None:
    """GET returns 200 and the retrieval record for the drive."""
    response = client.get(f"/api/v1/retrieval/{_DRIVE_NAME}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == queued_retrieval.id
    assert data["drive_name"] == _DRIVE_NAME
    assert data["submission_id"] == completed_submission.id
    assert data["destination_path"] == _DEST_PATH
    assert data["stage"] == RetrievalJobStage.QUEUED.value


def test_get_retrieval_returns_all_response_fields(
    client: TestClient,
    queued_retrieval: ArchiveRetrieval,
) -> None:
    """GET response body contains every field defined on RetrievalResponse."""
    response = client.get(f"/api/v1/retrieval/{_DRIVE_NAME}")
    assert response.status_code == 200
    data = response.json()
    for field in (
        "id",
        "drive_name",
        "submission_id",
        "destination_path",
        "stage",
        "failure_reason",
        "started_timestamp",
        "last_updated_timestamp",
        "completed_timestamp",
        "failed_timestamp",
    ):
        assert field in data


def test_get_retrieval_404_when_no_record(
    client: TestClient,
    session: Session,
) -> None:
    """GET returns 404 when no retrieval job exists for the drive."""
    response = client.get(f"/api/v1/retrieval/{_DRIVE_NAME}")
    assert response.status_code == 404
    assert "No archive retrieval job found" in response.json()["detail"]


def test_get_retrieval_returns_most_recent_record(
    client: TestClient,
    session: Session,
    completed_submission: ArchiveSubmission,
) -> None:
    """GET returns a record when one exists (select().first() behaviour)."""
    retrieval = ArchiveRetrieval(
        drive_name=_DRIVE_NAME,
        submission_id=completed_submission.id,
        destination_path=_DEST_PATH,
        stage=RetrievalJobStage.DOWNLOADING,
        started_timestamp=datetime(2024, 10, 15, 9, 0, 0),
        last_updated_timestamp=datetime(2024, 10, 15, 9, 30, 0),
    )
    session.add(retrieval)
    session.commit()

    response = client.get(f"/api/v1/retrieval/{_DRIVE_NAME}")
    assert response.status_code == 200
    assert response.json()["stage"] == RetrievalJobStage.DOWNLOADING.value
