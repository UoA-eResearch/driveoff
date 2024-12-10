"""Data models representing projects."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from models.person import InputPerson
from models.services import (
    InputServices,
    ResearchDriveProjectLink,
    ResearchDriveService,
    ResearchDriveServicePublic,
)
from models.member import MemberPublic

# Only import Member during typechecking to prevent circular dependency error.
if TYPE_CHECKING:
    from models.member import Member


class Code(SQLModel, table=True):
    """Model for project codes."""

    id: Optional[int] = Field(primary_key=True)
    code: str

class CodePublic(Code):
    """Public model for project codes."""

    id: int
    code: str


class BaseProject(SQLModel):
    """Base model for describing a project."""

    title: str
    description: str
    division: str
    start_date: datetime
    end_date: datetime


class InputProject(BaseProject):
    """Input project model for data received from POST"""

    id: Optional[int] = Field(default=None, primary_key=True)
    members: list[InputPerson]
    codes: list[Code]
    services: InputServices

class ProjectCodeLink(SQLModel, table=True):
    """Linking table between project and codes"""

    code_id: int | None = Field(default=None, foreign_key="code.id", primary_key=True)
    project_id: int | None = Field(
        default=None, foreign_key="project.id", primary_key=True
    )


class Project(BaseProject, table=True):
    """Project model for data stored in database"""

    id: Optional[int] = Field(default=None, primary_key=True)
    # services_id: int | None = Field(default=None, foreign_key="services.id")
    codes: list[Code] = Relationship(link_model=ProjectCodeLink)
    research_drives: list[ResearchDriveService] = Relationship(
        link_model=ResearchDriveProjectLink, back_populates="projects"
    )
    members: list["Member"] = Relationship(
        # cascade_delete enabled so session.merge() works for project save.
        back_populates="project",
        cascade_delete=True,
    )

class ProjectWithDriveMember(BaseProject):
    """Public model for project with drive and member information."""

    id: int
    codes: list[Code]
    research_drives: list[ResearchDriveServicePublic]
    members: list[MemberPublic]
