"""Archive submission model - minimal reference to ProjectDB records."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, Relationship, SQLModel

from models.common import DataClassification
from models.manifest import Manifest


class ArchiveSubmission(SQLModel, table=True):
    """Minimal archive record storing references to ProjectDB and archive metadata.

    This replaces the old DriveOffboardSubmission and removes all duplicate data
    storage. We only store IDs that reference ProjectDB records plus archive-specific
    metadata (retention, classification, location).
    """

    id: int | None = Field(default=None, primary_key=True)

    # ProjectDB references (not stored in local DB)
    drive_id: int
    project_id: int
    drive_name: str = Field(index=True)

    # Archiving metadata from submission form
    retention_period_years: int
    retention_period_justification: str | None = Field(default=None)
    data_classification: DataClassification

    # Archive tracking
    archive_date: datetime
    archive_location: str  # Path to zipped RO-Crate (stored as string for SQLite)

    # Manifest relationship
    manifest_id: int | None = Field(default=None, foreign_key="manifest.id")
    manifest: Manifest | None = Relationship()

    # Status and audit
    is_completed: bool = Field(default=False)
    created_timestamp: datetime = Field(default_factory=datetime.now)

    # Index for efficient queries by drive and timestamp
    __table_args__ = (
        # This will be added as composite index in migration
    )
