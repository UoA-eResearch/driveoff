"""Archive retrieval job model."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class RetrievalJobStage(str, Enum):
    """Lifecycle stages for an archive retrieval job.

    State transitions:
        queued -> restoring -> downloading -> extracting -> completed
        any non-terminal stage -> failed  (on unhandled exception)
    """

    QUEUED = "queued"
    RESTORING = "restoring"
    DOWNLOADING = "downloading"
    EXTRACTING = "extracting"
    COMPLETED = "completed"
    FAILED = "failed"


#: Stages that represent still-active (non-terminal) work.
ACTIVE_RETRIEVAL_STAGES = frozenset(
    [
        RetrievalJobStage.QUEUED,
        RetrievalJobStage.RESTORING,
        RetrievalJobStage.DOWNLOADING,
        RetrievalJobStage.EXTRACTING,
    ]
)


class ArchiveRetrieval(SQLModel, table=True):
    """Record of an archive retrieval job.

    Tracks the request to retrieve and restore a completed archive back to a
    Vast view so researchers can access their data with existing tools.
    """

    id: int | None = Field(default=None, primary_key=True)

    # Which archive this retrieval is for
    drive_name: str = Field(index=True)
    submission_id: int = Field(
        description="ID of the ArchiveSubmission record that holds the archive metadata"
    )

    # Where to extract the restored archive
    destination_path: str = Field(
        description="Filesystem path of the Vast view to extract the archive into"
    )

    # Lifecycle stage
    stage: RetrievalJobStage = Field(default=RetrievalJobStage.QUEUED)

    # Failure details
    failure_reason: str | None = Field(default=None)

    # Timestamps
    started_timestamp: datetime | None = Field(default=None)
    last_updated_timestamp: datetime | None = Field(default=None)
    completed_timestamp: datetime | None = Field(default=None)
    failed_timestamp: datetime | None = Field(default=None)
