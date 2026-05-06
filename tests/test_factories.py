"""Tests for fixture functionality"""

from sqlmodel import Session

from models.submission import ArchiveSubmission


def test_submission_fixture_creation(submission: ArchiveSubmission) -> None:
    """Test that submission fixture creates valid submission"""
    assert submission.drive_id == 1234
    assert submission.project_id == 123
    assert submission.drive_name == "restst000000001-testing"
    assert submission.retention_period_years == 7


def test_submission_persists_to_db(
    session: Session, submission: ArchiveSubmission
) -> None:
    """Test that submission fixture can be persisted to database"""
    session.add(submission)
    session.commit()
    session.refresh(submission)
    assert submission.id is not None
    assert submission.drive_name == "restst000000001-testing"
