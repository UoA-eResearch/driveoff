"""Tests for the ArchiveSubmission model."""

from datetime import datetime
from typing import Any

import pytest

from models.common import DataClassification
from models.submission import ArchiveSubmission


@pytest.fixture(name="submission_data")
def submission_data_fixture() -> dict[str, Any]:
    """Fixture with valid submission data.

    Returns:
        dict[str, Any]: submission data matching ArchiveSubmission fields.
    """
    return {
        "drive_id": 1234,
        "project_id": 123,
        "drive_name": "test-drive",
        "retention_period_years": 7,
        "retention_period_justification": "Standard research retention",
        "data_classification": DataClassification.SENSITIVE,
        "started_timestamp": datetime(2024, 10, 13),
        "activescale_file_key": None,
    }


def test_submission_can_create(submission_data: dict[str, Any]) -> None:
    """Tests whether a submission instance can be created"""
    submission = ArchiveSubmission.model_validate(submission_data)
    assert submission.drive_id == 1234
    assert submission.project_id == 123
    assert submission.drive_name == "test-drive"
    assert submission.retention_period_years == 7


def test_submission_required_fields() -> None:
    """Tests that required fields must be provided"""
    with pytest.raises(Exception):  # Pydantic validation error
        ArchiveSubmission.model_validate({})


def test_submission_data_classification_enum() -> None:
    """Tests that data classification validates as enum"""
    data = {
        "drive_id": 1234,
        "project_id": 123,
        "drive_name": "test-drive",
        "retention_period_years": 7,
        "retention_period_justification": "Standard",
        "data_classification": "Sensitive",
        "started_timestamp": datetime.now(),
    }
    submission = ArchiveSubmission.model_validate(data)
    assert submission.data_classification == DataClassification.SENSITIVE


def test_submission_with_activescale_metadata(
    submission_data: dict[str, Any],
) -> None:
    """Tests submission with ActiveScale upload metadata."""
    submission_data["activescale_file_key"] = "ro-crates/test-drive/archive.zip"
    instance = ArchiveSubmission.model_validate(submission_data)
    assert instance.activescale_file_key == "ro-crates/test-drive/archive.zip"


def test_submission_with_failed_upload(
    submission_data: dict[str, Any],
) -> None:
    """Tests submission with failed upload metadata."""
    submission_data["activescale_file_key"] = "ro-crates/test-drive/archive.zip"
    instance = ArchiveSubmission.model_validate(submission_data)
    assert instance.activescale_file_key == "ro-crates/test-drive/archive.zip"
