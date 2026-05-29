"""Read-only response models for the API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from models.common import DataClassification
from models.retrieval import RetrievalJobStage
from models.submission import ArchiveJobStage


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
    codes: list[CodeResponse] = Field(default_factory=list)
    members: list[MemberResponse] = Field(default_factory=list)


class DriveInfoResponse(BaseModel):
    """Combined drive + project info returned by the driveinfo endpoint."""

    drive: DriveResponse
    project: ProjectResponse


class CreateSubmissionResponse(BaseModel):
    """Response returned after creating an archive submission."""

    message: str


class CreateRetrievalResponse(BaseModel):
    """Response returned after scheduling an archive retrieval job."""

    message: str


class ErrorResponse(BaseModel):
    """Error response returned by the API."""

    detail: str


class SubmissionResponse(BaseModel):
    """Archive submission record returned by the submission endpoint."""

    model_config = ConfigDict(from_attributes=True)

    drive_id: int
    project_id: int
    drive_name: str
    retention_period_years: int
    retention_period_justification: str | None
    data_classification: DataClassification
    stage: ArchiveJobStage
    failure_reason: str | None
    failed_timestamp: datetime | None
    started_timestamp: datetime | None
    last_updated_timestamp: datetime | None
    completed_timestamp: datetime | None
    retry_count: int
    cleanup_succeeded: bool | None
    cleanup_error: str | None
    archive_file_key: str | None
    archive_object_prefix: str | None
    archive_manifest_key: str | None
    archive_part_keys_json: str | None
    archive_part_count: int | None
    archive_total_bytes: int | None


class RetrievalResponse(BaseModel):
    """Archive retrieval record returned by the retrieval endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None
    drive_name: str
    submission_id: int
    destination_path: str
    stage: RetrievalJobStage
    failure_reason: str | None
    started_timestamp: datetime | None
    last_updated_timestamp: datetime | None
    completed_timestamp: datetime | None
    failed_timestamp: datetime | None
