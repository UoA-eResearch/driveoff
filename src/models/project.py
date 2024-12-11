"""Data models representing projects."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pydantic import AliasGenerator, ConfigDict
from pydantic.alias_generators import to_camel
from sqlmodel import Field, Relationship, SQLModel

from models.member import MemberPublic
from models.person import InputPerson
from models.services import (
    InputServices,
    ResearchDriveProjectLink,
    ResearchDriveService,
    ResearchDriveServicePublic,
)

# Only import Member during typechecking to prevent circular dependency error.
if TYPE_CHECKING:
    from models.member import Member


class Code(SQLModel, table=True):
    """Model for project codes."""

    id: Optional[int] = Field(primary_key=True)
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


class ROCrateProject(BaseProject):
    """Project model to be serialized as part of an RO-Crate"""

    # Bug with SQLModel library causing typing error:
    # https://github.com/fastapi/sqlmodel/discussions/855
    model_config = ConfigDict(  # type: ignore
        alias_generator=AliasGenerator(
            serialization_alias=to_camel,
        )
    )
    id: int
    title: str = Field(schema_extra={"serialization_alias": "name"})
    schema_type: str = Field(
        default="ResearchProject", schema_extra={"serialization_alias": "@type"}
    )

    def __init__(self, project: Project):
        super().__init__(**project.model_dump())
