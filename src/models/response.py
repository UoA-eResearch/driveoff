"""Read-only response models for the API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from models.common import DataClassification


class RoleResponse(BaseModel):
    """Project role."""

    id: int | None = None
    name: str


class PersonResponse(BaseModel):
    """Person summary for display."""

    id: int | None = None
    email: str | None = None
    full_name: str
    username: str | None = None


class MemberResponse(BaseModel):
    """Project member with role."""

    role: RoleResponse
    person: PersonResponse


class CodeResponse(BaseModel):
    """Project code."""

    id: int | None = None
    code: str


class DriveResponse(BaseModel):
    """Research drive storage info."""

    id: int
    name: str
    allocated_gb: float
    used_gb: float
    free_gb: float
    percentage_used: float
    date: str
    first_day: str | None = None
    last_day: str | None = None


class ProjectResponse(BaseModel):
    """Project summary for display."""

    id: int
    title: str
    description: str
    division: str
    start_date: str
    end_date: str
    codes: list[CodeResponse] = []
    members: list[MemberResponse] = []


class DriveInfoResponse(BaseModel):
    """Combined drive + project info returned by the driveinfo endpoint."""

    drive: DriveResponse
    project: ProjectResponse


class CreateSubmissionResponse(BaseModel):
    """Response returned after creating an archive submission."""

    message: str


class ErrorResponse(BaseModel):
    """Error response returned by the API."""

    detail: str


class SubmissionResponse(BaseModel):
    """Archive submission record returned by the submission endpoint."""

    drive_id: int
    project_id: int
    drive_name: str
    retention_period_years: int
    retention_period_justification: str | None
    data_classification: DataClassification
    archive_date: datetime
    archive_location: str
    is_completed: bool
    created_timestamp: datetime
    manifest: str | None
