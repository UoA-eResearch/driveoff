"""Data models representing CeR services."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from models.manifest import Manifest, ManifestDriveLink
from models.submission import DriveOffboardSubmission

if TYPE_CHECKING:
    from models.project import Project


class ResearchDriveProjectLink(SQLModel, table=True):
    """Linking table between research drive service and a project's service."""

    project_id: int | None = Field(
        default=None, foreign_key="project.id", primary_key=True
    )
    research_drive_id: int | None = Field(
        default=None, foreign_key="researchdriveservice.id", primary_key=True
    )


class ResearchDriveService(SQLModel, table=True):
    """Object describing a research drive service."""

    allocated_gb: float
    date: datetime
    first_day: datetime
    free_gb: float
    id: Optional[int] = Field(primary_key=True)
    last_day: Optional[datetime]
    name: str
    percentage_used: float
    used_gb: float
    projects: list["Project"] = Relationship(
        link_model=ResearchDriveProjectLink, back_populates="research_drives"
    )
    manifest: Manifest = Relationship(
        link_model=ManifestDriveLink, back_populates="research_drive"
    )
    submission: DriveOffboardSubmission | None = Relationship(back_populates="drive")


class InputServices(SQLModel):
    """Input object describing relevant storage services."""

    research_drive: list[ResearchDriveService]
