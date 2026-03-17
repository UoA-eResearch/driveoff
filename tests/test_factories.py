"""Tests for fixture functionality"""

from datetime import datetime

from sqlmodel import Session

from models.common import DataClassification
from models.manifest import Manifest
from models.submission import ArchiveSubmission


def test_submission_fixture_creation(submission: ArchiveSubmission) -> None:
    """Test that submission fixture creates valid submission"""
    assert submission.drive_id == 1234
    assert submission.project_id == 123
    assert submission.drive_name == "restst000000001-testing"
    assert submission.retention_period_years == 7


def test_manifest_fixture_creation(manifest: Manifest) -> None:
    """Test that manifest fixture creates valid manifest"""
    assert manifest.manifest is not None
    assert "files" in manifest.manifest


def test_submission_persists_to_db(
    session: Session, submission: ArchiveSubmission
) -> None:
    """Test that submission fixture can be persisted to database"""
    session.add(submission)
    session.commit()
    session.refresh(submission)
    assert submission.id is not None
    assert submission.drive_name == "restst000000001-testing"
