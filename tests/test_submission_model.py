"""Tests for the Drive Offboarding Submission model."""

from typing import Any

from models.submission import DriveOffboardSubmission


def test_submission_can_create(submission: dict[str, Any]):
    """Tests whether a submission instance can be made"""
    DriveOffboardSubmission.model_validate(submission)
