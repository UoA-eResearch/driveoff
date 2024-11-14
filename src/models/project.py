from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from models.person import InputPerson
from models.services import InputServices, Services

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
    services_id: int | None = Field(default=None, foreign_key="services.id")
    codes: list[Code] = Relationship(link_model=ProjectCodeLink)
    services: Services = Relationship()
    members: list["Member"] = Relationship(
        back_populates="project", cascade_delete=True
    )
