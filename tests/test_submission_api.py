from pathlib import Path

from fastapi.testclient import TestClient
from mock import MagicMock, patch
from sqlmodel import Session, select

from models.common import DataClassification
from models.project import Project
from models.services import ResearchDriveService
from models.submission import DriveOffboardSubmission


@patch("api.main.get_resdrive_path")
def test_post_submission_can_create(
    mock_get_resdrive_path: MagicMock,
    session: Session,
    client: TestClient,
    project: Project,
    tmpdir: Path,
) -> None:
    mock_get_resdrive_path.return_value = tmpdir
    session.add(project)
    session.commit()
    response = client.post(
        "/api/v1/submission",
        json={
            "retentionPeriodYears": 6,
            "dataClassification": "Sensitive",
            "isCompleted": True,
            "driveName": "restst000000001-testing",
        },
    )
    assert response.status_code == 201
    stmt = (
        select(DriveOffboardSubmission, ResearchDriveService)
        .join(ResearchDriveService)
        .where(ResearchDriveService.name == "restst000000001-testing")
    )
    result = session.exec(stmt).first()
    assert result is not None
    saved_submission, drive = result
    project = drive.projects[0]
    # Check project title and description are not modified
    assert project.title == project.title
    assert project.description == project.description
    # Check submission is created.
    assert saved_submission.data_classification == DataClassification.SENSITIVE
    assert saved_submission.is_completed
    assert saved_submission.retention_period_years == 6
    assert not saved_submission.is_project_updated


@patch("api.main.get_resdrive_path")
def test_post_submission_can_update_project(
    mock_get_resdrive_path: MagicMock,
    session: Session,
    client: TestClient,
    project: Project,
    tmpdir: Path,
):
    mock_get_resdrive_path.return_value = tmpdir
    session.add(project)
    session.commit()
    response = client.post(
        "/api/v1/submission",
        json={
            "retentionPeriodYears": 6,
            "dataClassification": "Sensitive",
            "isCompleted": True,
            "driveName": "restst000000001-testing",
            "projectChanges": {
                "title": "My new title",
                "description": "My new description",
            },
        },
    )
    assert response.status_code == 201
    stmt = (
        select(DriveOffboardSubmission, ResearchDriveService)
        .join(ResearchDriveService)
        .where(ResearchDriveService.name == "restst000000001-testing")
    )
    result = session.exec(stmt).first()
    assert result is not None
    submission, drive = result
    assert len(drive.projects) == 1
    project = drive.projects[0]
    assert project.title == "My new title"
    assert project.description == "My new description"
    assert submission.is_project_updated


@patch("api.main.get_resdrive_path")
def test_post_submission_reject_already_submitted(
    mock_get_resdrive_path: MagicMock,
    session: Session,
    client: TestClient,
    project: Project,
    tmpdir: Path,
):
    mock_get_resdrive_path.return_value = tmpdir
    session.add(project)
    session.commit()
    response = client.post(
        "/api/v1/submission",
        json={
            "retentionPeriodYears": 6,
            "dataClassification": "Sensitive",
            "isCompleted": True,
            "driveName": "restst000000001-testing",
            "projectChanges": {
                "title": "My new title",
                "description": "My new description",
            },
        },
    )
    assert response.status_code == 201
    second_response = client.post(
        "/api/v1/submission",
        json={
            "retentionPeriodYears": 10,
            "dataClassification": "Sensitive",
            "isCompleted": False,
            "driveName": "restst000000001-testing",
            "projectChanges": {
                "title": "My new title",
                "description": "My new description",
            },
        },
    )
    assert second_response.status_code == 400


def test_post_submission_reject_drive_with_no_project(
    session: Session, client: TestClient, project: Project
):
    # Unlink drive from project
    drive = project.research_drives[0]
    project.research_drives = []
    session.add(project)
    session.add(drive)
    session.commit()
    response = client.post(
        "/api/v1/submission",
        json={
            "retentionPeriodYears": 6,
            "dataClassification": "Sensitive",
            "isCompleted": True,
            "driveName": "restst000000001-testing",
            "projectChanges": {
                "title": "My new title",
                "description": "My new description",
            },
        },
    )
    assert response.status_code == 404


def test_post_submission_handle_wrong_drive_name(client: TestClient):
    response = client.post(
        "/api/v1/submission",
        json={
            "retentionPeriodYears": 6,
            "dataClassification": "Sensitive",
            "isCompleted": True,
            "driveName": "restst000000001-testing",
            "projectChanges": {
                "title": "My new title",
                "description": "My new description",
            },
        },
    )
    assert response.status_code == 404
