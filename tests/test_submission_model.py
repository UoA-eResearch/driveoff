"""Tests for the Drive Offboarding Submission model."""

from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from models.common import DataClassification
from models.submission import DriveOffboardSubmission, InputDriveOffboardSubmission


@pytest.fixture
def submission() -> dict[str, Any]:
    """Fixture with a working submission.

    Returns:
        dict[str, Any]: submission data.
    """
    return {
        "retention_period_years": 6,
        "data_classification": DataClassification.PUBLIC,
        "is_completed": True,
        "updated_time": datetime.now(),
        "is_project_updated": True,
        "drive_id": 1,
    }


def test_submission_can_create(submission: dict[str, Any]) -> None:
    """Tests whether a submission instance can be made"""
    DriveOffboardSubmission.model_validate(submission)


def test_post_submission_can_create(session: Session, client: TestClient):
    # client.
    