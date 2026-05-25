"""Tests for the ArchiveRetrieval model."""

from datetime import datetime
from typing import Any

import pytest

from models.retrieval import (
    ACTIVE_RETRIEVAL_STAGES,
    ArchiveRetrieval,
    RetrievalJobStage,
)


@pytest.fixture(name="retrieval_data")
def retrieval_data_fixture() -> dict[str, Any]:
    """Valid data for constructing an ArchiveRetrieval instance."""
    return {
        "drive_name": "restst000000001-testing",
        "submission_id": 1,
        "destination_path": "/mnt/vast/restst000000001-testing",
        "started_timestamp": datetime(2024, 10, 13),
    }


def test_retrieval_can_create(retrieval_data: dict[str, Any]) -> None:
    """ArchiveRetrieval can be instantiated with valid data."""
    retrieval = ArchiveRetrieval.model_validate(retrieval_data)
    assert retrieval.drive_name == "restst000000001-testing"
    assert retrieval.submission_id == 1
    assert retrieval.destination_path == "/mnt/vast/restst000000001-testing"


def test_retrieval_defaults_to_queued(retrieval_data: dict[str, Any]) -> None:
    """Stage defaults to QUEUED when not explicitly set."""
    retrieval = ArchiveRetrieval.model_validate(retrieval_data)
    assert retrieval.stage == RetrievalJobStage.QUEUED


def test_retrieval_required_fields_raises_on_empty() -> None:
    """Model validation fails when no fields are provided."""
    with pytest.raises(Exception):
        ArchiveRetrieval.model_validate({})


def test_retrieval_required_field_drive_name() -> None:
    """drive_name is required."""
    with pytest.raises(Exception):
        ArchiveRetrieval.model_validate(
            {"submission_id": 1, "destination_path": "/tmp"}
        )


def test_retrieval_required_field_submission_id() -> None:
    """submission_id is required."""
    with pytest.raises(Exception):
        ArchiveRetrieval.model_validate(
            {"drive_name": "restst000000001-testing", "destination_path": "/tmp"}
        )


def test_retrieval_required_field_destination_path() -> None:
    """destination_path is required."""
    with pytest.raises(Exception):
        ArchiveRetrieval.model_validate(
            {"drive_name": "restst000000001-testing", "submission_id": 1}
        )


def test_retrieval_job_stage_string_values() -> None:
    """RetrievalJobStage members have the expected string values."""
    assert RetrievalJobStage.QUEUED == "queued"
    assert RetrievalJobStage.RESTORING == "restoring"
    assert RetrievalJobStage.DOWNLOADING == "downloading"
    assert RetrievalJobStage.EXTRACTING == "extracting"
    assert RetrievalJobStage.COMPLETED == "completed"
    assert RetrievalJobStage.FAILED == "failed"


def test_active_retrieval_stages_contains_non_terminal_stages() -> None:
    """All non-terminal stages are in ACTIVE_RETRIEVAL_STAGES."""
    assert RetrievalJobStage.QUEUED in ACTIVE_RETRIEVAL_STAGES
    assert RetrievalJobStage.RESTORING in ACTIVE_RETRIEVAL_STAGES
    assert RetrievalJobStage.DOWNLOADING in ACTIVE_RETRIEVAL_STAGES
    assert RetrievalJobStage.EXTRACTING in ACTIVE_RETRIEVAL_STAGES


def test_active_retrieval_stages_excludes_terminal_stages() -> None:
    """Terminal stages are not in ACTIVE_RETRIEVAL_STAGES."""
    assert RetrievalJobStage.COMPLETED not in ACTIVE_RETRIEVAL_STAGES
    assert RetrievalJobStage.FAILED not in ACTIVE_RETRIEVAL_STAGES


def test_retrieval_with_failure_info(retrieval_data: dict[str, Any]) -> None:
    """FAILED state fields are correctly stored."""
    retrieval_data["stage"] = RetrievalJobStage.FAILED
    retrieval_data["failure_reason"] = "Download failed"
    retrieval_data["failed_timestamp"] = datetime(2024, 10, 14)
    retrieval = ArchiveRetrieval.model_validate(retrieval_data)
    assert retrieval.stage == RetrievalJobStage.FAILED
    assert retrieval.failure_reason == "Download failed"
    assert retrieval.failed_timestamp == datetime(2024, 10, 14)


def test_retrieval_optional_timestamps_default_none() -> None:
    """All optional timestamp fields default to None."""
    retrieval = ArchiveRetrieval.model_validate(
        {
            "drive_name": "restst000000001-testing",
            "submission_id": 1,
            "destination_path": "/mnt/vast/restst000000001-testing",
        }
    )
    assert retrieval.started_timestamp is None
    assert retrieval.last_updated_timestamp is None
    assert retrieval.completed_timestamp is None
    assert retrieval.failed_timestamp is None


def test_retrieval_failure_reason_defaults_none(retrieval_data: dict[str, Any]) -> None:
    """failure_reason defaults to None for a new retrieval."""
    retrieval = ArchiveRetrieval.model_validate(retrieval_data)
    assert retrieval.failure_reason is None


def test_retrieval_id_defaults_none(retrieval_data: dict[str, Any]) -> None:
    """id is None before the record is persisted."""
    retrieval = ArchiveRetrieval.model_validate(retrieval_data)
    assert retrieval.id is None
