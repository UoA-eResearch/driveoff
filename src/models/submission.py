"""Archive submission model - minimal reference to ProjectDB records."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel

from models.common import DataClassification


class JobStage(str, Enum):
    """Lifecycle stages for an archive job.

    State transitions:
        queued -> packaging -> uploading_parts -> writing_manifest -> cleanup -> completed
        any non-terminal stage -> failed  (on unhandled exception)
        any non-terminal stage -> abandoned  (on API restart mid-job)
    """

    QUEUED = "queued"
    PACKAGING = "packaging"
    UPLOADING_PARTS = "uploading_parts"
    WRITING_MANIFEST = "writing_manifest"

    # Legacy states retained for compatibility with in-flight/tests during refactor.
    RUNNING = "running"
    UPLOADING = "uploading"
    CLEANUP = "cleanup"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


class ArchiveObjectLayout(str, Enum):
    """How archive bytes are stored in object storage."""

    SINGLE_OBJECT = "single_object"
    CHUNKED_OBJECTS = "chunked_objects"


class ArchivePackageFormat(str, Enum):
    """Container format used before upload."""

    ZIP = "zip"
    TAR = "tar"


#: Stages that represent still-active (non-terminal) work.
ACTIVE_STAGES = frozenset(
    [
        JobStage.QUEUED,
        JobStage.PACKAGING,
        JobStage.UPLOADING_PARTS,
        JobStage.WRITING_MANIFEST,
        JobStage.RUNNING,
        JobStage.UPLOADING,
        JobStage.CLEANUP,
    ]
)

#: Stages that allow a retry to be submitted.
RETRYABLE_STAGES = frozenset([JobStage.FAILED, JobStage.ABANDONED])


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

    # ActiveScale upload metadata (optional, only populated after upload attempt)
    activescale_file_key: str | None = Field(
        default=None, description="S3/ActiveScale path where archive was uploaded"
    )
    activescale_object_prefix: str | None = Field(
        default=None,
        description=(
            "S3 prefix that groups all objects for this archive (used for chunked uploads)"
        ),
    )
    activescale_manifest_key: str | None = Field(
        default=None,
        description="S3 key for an archive sidecar manifest that lists all uploaded parts",
    )
    activescale_part_keys_json: str | None = Field(
        default=None,
        description="JSON-encoded ordered list of uploaded part object keys",
    )
    archive_layout: ArchiveObjectLayout = Field(
        default=ArchiveObjectLayout.SINGLE_OBJECT
    )
    archive_package_format: ArchivePackageFormat = Field(
        default=ArchivePackageFormat.ZIP
    )
    archive_part_count: int | None = Field(default=None)
    archive_part_size_bytes: int | None = Field(default=None)
    archive_total_bytes: int | None = Field(default=None)

    # Status and audit
    failure_reason: str | None = Field(default=None)
    failed_timestamp: datetime | None = Field(default=None)

    # Lifecycle stage (authoritative status for the archive job)
    stage: JobStage = Field(default=JobStage.QUEUED)

    # Timestamps for operational visibility
    started_timestamp: datetime | None = Field(default=None)
    last_updated_timestamp: datetime | None = Field(default=None)
    completed_timestamp: datetime | None = Field(default=None)

    # Retry tracking
    retry_count: int = Field(default=0)

    # Cleanup outcome (populated after the cleanup block runs)
    cleanup_succeeded: bool | None = Field(default=None)
    cleanup_error: str | None = Field(default=None)
