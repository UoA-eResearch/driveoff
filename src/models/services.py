"""Data models representing CeR services."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from pydantic import field_serializer
from sqlmodel import Field, Relationship, SQLModel

from models.manifest import Manifest, ManifestDriveLink
from models.submission import DriveOffboardSubmission

if TYPE_CHECKING:
    from models.project import Project


class BaseDriveService(SQLModel):
    """Base model for describing a drive service."""

    name: str
    allocated_gb: float
    free_gb: float
    used_gb: float
    percentage_used: float
    date: datetime
    first_day: datetime
    last_day: Optional[datetime]


class ResearchDriveProjectLink(SQLModel, table=True):
    """Linking table between research drive service and a project's service."""

    project_id: int | None = Field(
        default=None, foreign_key="project.id", primary_key=True
    )
    research_drive_id: int | None = Field(
        default=None, foreign_key="researchdriveservice.id", primary_key=True
    )


class ResearchDriveService(BaseDriveService, table=True):
    """Object describing a research drive service."""

    id: Optional[int] = Field(default=None, primary_key=True)
    projects: list["Project"] = Relationship(
        link_model=ResearchDriveProjectLink, back_populates="research_drives"
    )
    manifest: Manifest = Relationship(
        link_model=ManifestDriveLink, back_populates="research_drive"
    )
    submission: DriveOffboardSubmission | None = Relationship(back_populates="drive")

    @field_serializer("first_day", "date", "last_day")
    def serialize_date(self, dt: Any) -> Any:
        """serialize dates as isoformat"""
        if isinstance(dt, datetime):
            return dt.isoformat()
        return dt


class InputServices(SQLModel):
    """Input object describing relevant storage services."""

    research_drive: list[ResearchDriveService]


class ResearchDriveServicePublic(BaseDriveService):
    """Public model for Research Drive Service."""

    manifest: Manifest
