"""Data models representing CeR services."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from models.project import Project


class ResearchDriveServicesLink(SQLModel, table=True):
    """Linking table between research drive service and a project's service."""

    service_id: int | None = Field(
        default=None, foreign_key="services.id", primary_key=True
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
    service: list["Services"] = Relationship(link_model=ResearchDriveServicesLink)


class InputServices(SQLModel):
    """Input object describing relevant storage services."""

    research_drive: list[ResearchDriveService]


class Services(SQLModel, table=True):
    """Object describing relevant storage services."""

    id: Optional[int] = Field(default=None, primary_key=True)
    projects: list["Project"] = Relationship(back_populates="services")
    research_drive: list[ResearchDriveService] = Relationship(
        link_model=ResearchDriveServicesLink, back_populates="service"
    )
