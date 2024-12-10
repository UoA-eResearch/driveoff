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
    }


def test_submission_can_create(submission: dict[str, Any]) -> None:
    """Tests whether a submission instance can be made"""
    DriveOffboardSubmission.model_validate(submission)
