from typing import Any

import pytest
from pydantic import ValidationError

from models.submission import DriveOffboardSubmission


def test_submission_can_create(submission: dict[str, Any]):
    DriveOffboardSubmission.model_validate(submission)


def test_non_standard_retention_period_fail_without_justification(
    submission: dict[str, Any]
):
    submission["retention_period_years"] = 5
    with pytest.raises(ValidationError):
        DriveOffboardSubmission.model_validate(submission)


def test_non_standard_retention_period_can_create_with_justification(
    submission: dict[str, Any]
):
    submission["retention_period_years"] = 5
    submission["retention_period_justification"] = (
        "Data sharing agreement says it can be deleted in 5 years."
    )
    DriveOffboardSubmission.model_validate(submission)


def test_data_classificiation_is_validated(submission: dict[str, Any]):
    submission["data_classification"] = "My own classification"
    with pytest.raises(ValidationError):
        DriveOffboardSubmission.model_validate(submission)
