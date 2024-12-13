"""Data models representing CeR services."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pydantic import AliasGenerator, ConfigDict
from pydantic.alias_generators import to_camel
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


class BaseResearchDriveService(SQLModel):
    "Base Model describing a research drive service"
    allocated_gb: float
    date: datetime
    first_day: datetime
    free_gb: float
    id: Optional[int] = Field(primary_key=True)
    last_day: Optional[datetime]
    name: str
    percentage_used: float
    used_gb: float


class ResearchDriveService(BaseResearchDriveService, table=True):
    """Object describing a research drive service."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    projects: list["Project"] = Relationship(
        link_model=ResearchDriveProjectLink, back_populates="research_drives"
    )
    manifest: Manifest = Relationship(
        link_model=ManifestDriveLink, back_populates="research_drive"
    )
    submission: DriveOffboardSubmission | None = Relationship(back_populates="drive")


class ROCrateResDriveService(BaseResearchDriveService):
    """Model for serializing research drive services as part of an RO-Crate"""

    # Bug with SQLModel library causing typing error:
    # https://github.com/fastapi/sqlmodel/discussions/855
    model_config = ConfigDict(  # type: ignore
        alias_generator=AliasGenerator(
            serialization_alias=to_camel,
        )
    )
    schema_type: str = Field(
        default="ResearchDriveService", schema_extra={"serialization_alias": "@type"}
    )

    def __init__(self, research_drive_service: ResearchDriveService):
        super().__init__(**research_drive_service.model_dump())


class InputServices(SQLModel):
    """Input object describing relevant storage services."""

    research_drive: list[ResearchDriveService]


class ResearchDriveServicePublic(BaseDriveService):
    """Public model for Research Drive Service."""

    manifest: Manifest
