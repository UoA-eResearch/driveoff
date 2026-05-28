"""Request models for the API."""

from __future__ import annotations

from pydantic import BaseModel, field_validator
from sqlmodel import SQLModel

from models.common import DataClassification, ResearchDriveName
from models.retrieval import RetrievalJobStage
from models.submission import ArchiveJobStage


class CreateSubmissionRequest(SQLModel):
    """Request body for creating an archive submission."""

    drive_name: ResearchDriveName
    retention_period_years: int
    retention_period_justification: str | None = None
    data_classification: DataClassification = DataClassification.SENSITIVE
    project_id: int | None = None
    force: bool = False

    @field_validator("retention_period_years")
    @classmethod
    def check_minimum_retention(cls, v: int) -> int:
        """Enforce a minimum retention period of 6 years."""
        if v < 6:
            raise ValueError("Retention period must be at least 6 years.")
        return v


class PatchSubmissionRequest(BaseModel):
    """Request body for partially updating an archive submission record.

    Only fields present in the request body are applied; omitted fields are
    left unchanged. Timestamps (last_updated, completed) are managed
    server-side based on the resulting stage value.
    """

    stage: ArchiveJobStage | None = None
    failure_reason: str | None = None
    cleanup_succeeded: bool | None = None
    cleanup_error: str | None = None
    archive_file_key: str | None = None
    archive_object_prefix: str | None = None
    archive_manifest_key: str | None = None
    archive_part_keys_json: str | None = None
    archive_part_count: int | None = None
    archive_total_bytes: int | None = None


class CreateRetrievalRequest(SQLModel):
    """Request body for starting an archive retrieval job."""

    destination_path: str


class PatchRetrievalRequest(BaseModel):
    """Request body for partially updating an archive retrieval record.

    Only fields present in the request body are applied; omitted fields are
    left unchanged.  Timestamps (last_updated, completed, failed) are managed
    server-side based on the resulting stage value.
    """

    stage: RetrievalJobStage | None = None
    failure_reason: str | None = None
    retrieved_part_keys_json: str | None = None
