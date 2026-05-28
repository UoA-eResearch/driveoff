"""Archive submission model - minimal reference to ProjectDB records."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel

from models.common import DataClassification


class ArchiveJobStage(str, Enum):
    """Lifecycle stages for an archive job.

    State transitions:
        queued -> packaging -> uploading -> writing_manifest -> cleanup -> completed
        any non-terminal stage -> failed  (on unhandled exception)
        any non-terminal stage -> abandoned  (on API restart mid-job)
    """

    QUEUED = "queued"
    PACKAGING = "packaging"
    WRITING_MANIFEST = "writing_manifest"
    UPLOADING = "uploading"
    CLEANUP = "cleanup"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


#: Stages that represent still-active (non-terminal) work.
ACTIVE_STAGES = frozenset(
    [
        ArchiveJobStage.QUEUED,
        ArchiveJobStage.PACKAGING,
        ArchiveJobStage.WRITING_MANIFEST,
        ArchiveJobStage.UPLOADING,
        ArchiveJobStage.CLEANUP,
    ]
)

#: Stages that allow a retry to be submitted.
RETRYABLE_STAGES = frozenset([ArchiveJobStage.FAILED, ArchiveJobStage.ABANDONED])


class ArchiveSubmission(SQLModel, table=True):
    """Minimal archive record storing references to ProjectDB and archive metadata.

    This replaces the old DriveOffboardSubmission and removes all duplicate data
    storage. We only store IDs that reference ProjectDB records plus archive-specific
    metadata (retention, classification, and lifecycle state).
    """

    id: int | None = Field(default=None, primary_key=True)

    # Locally stored references to ProjectDB records
    drive_id: int
    project_id: int
    drive_name: str = Field(index=True, unique=True)

    # Archiving metadata from submission form
    retention_period_years: int
    retention_period_justification: str | None = Field(default=None)
    data_classification: DataClassification

    # Archive upload metadata (optional, only populated after upload attempt)
    archive_file_key: str | None = Field(
        default=None, description="S3 path where archive was uploaded"
    )
    archive_object_prefix: str | None = Field(
        default=None,
        description=(
            "S3 prefix that groups all objects for this archive (used for chunked uploads)"
        ),
    )
    archive_manifest_key: str | None = Field(
        default=None,
        description="S3 key for an archive sidecar manifest that lists all uploaded parts",
    )
    archive_part_keys_json: str | None = Field(
        default=None,
        description="JSON-encoded ordered list of uploaded part object keys",
    )
    archive_part_count: int | None = Field(default=None)
    archive_total_bytes: int | None = Field(default=None)

    # Status and audit
    failure_reason: str | None = Field(default=None)
    failed_timestamp: datetime | None = Field(default=None)

    # Lifecycle stage (authoritative status for the archive job)
    stage: ArchiveJobStage = Field(default=ArchiveJobStage.QUEUED)

    # Timestamps for operational visibility
    started_timestamp: datetime | None = Field(default=None)
    last_updated_timestamp: datetime | None = Field(default=None)
    completed_timestamp: datetime | None = Field(default=None)

    # Retry tracking
    retry_count: int = Field(default=0)

    # Cleanup outcome (populated after the cleanup block runs)
    cleanup_succeeded: bool | None = Field(default=None)
    cleanup_error: str | None = Field(default=None)
