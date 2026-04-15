"""Archive submission model - minimal reference to ProjectDB records."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import orm
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

    # Locally stored references to ProjectDB records
    drive_id: int
    project_id: int
    drive_name: str = Field(index=True, unique=True)

    # Archiving metadata from submission form
    retention_period_years: int
    retention_period_justification: str | None = Field(default=None)
    data_classification: DataClassification

    # Archive tracking
    archive_date: datetime
    archive_location: str  # Path to zipped RO-Crate (stored as string for SQLite)

    # ActiveScale upload metadata (optional, only populated after upload attempt)
    activescale_file_key: str | None = Field(
        default=None, description="S3/ActiveScale path where archive was uploaded"
    )
    archive_uploaded: bool | None = Field(
        default=None,
        description="True if archive successfully uploaded, False if upload failed",
    )

    # Manifest relationship
    manifest_id: int | None = Field(default=None, foreign_key="manifest.id")
    manifest: Optional[Manifest] = Relationship(
        sa_relationship=orm.relationship("Manifest")
    )

    # Status and audit
    is_completed: bool = Field(default=False)
    is_failed: bool = Field(default=False)
    failure_reason: str | None = Field(default=None)
    failed_timestamp: datetime | None = Field(default=None)
    created_timestamp: datetime = Field(default_factory=datetime.now)
