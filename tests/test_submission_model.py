"""Tests for the Drive Offboarding Submission model."""

from datetime import datetime
from typing import Any

import pytest

from models.common import DataClassification
from models.submission import DriveOffboardSubmission


@pytest.fixture(name="submission")
def submission_fixture() -> dict[str, Any]:
    """Fixture with a working submission.

    Returns:
        dict[str, Any]: submission data.
    """
    return {
        "retentionPeriodYears": 6,
        "dataClassification": DataClassification.PUBLIC,
        "isCompleted": True,
        "updatedTime": datetime.now(),
        "isProjectUpdated": True,
        "driveId": 1,
        "activescaleFileKey": None,
        "archiveUploaded": None,
    }


def test_submission_can_create(submission: dict[str, Any]) -> None:
    """Tests whether a submission instance can be made"""
    DriveOffboardSubmission.model_validate(submission)


def test_submission_with_activescale_metadata(
    submission: dict[str, Any],
) -> None:
    """Tests submission with ActiveScale upload metadata."""
    submission["activescaleFileKey"] = "ro-crates/test-drive/archive.zip"
    submission["archiveUploaded"] = True
    instance = DriveOffboardSubmission.model_validate(submission)
    assert instance.activescale_file_key == "ro-crates/test-drive/archive.zip"
    assert instance.archive_uploaded is True


def test_submission_with_failed_upload(
    submission: dict[str, Any],
) -> None:
    """Tests submission with failed upload metadata."""
    submission["activescaleFileKey"] = "ro-crates/test-drive/archive.zip"
    submission["archiveUploaded"] = False
    instance = DriveOffboardSubmission.model_validate(submission)
    assert instance.activescale_file_key == "ro-crates/test-drive/archive.zip"
    assert instance.archive_uploaded is False
