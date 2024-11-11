from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from models.person import InputPerson, Person
from models.services import Services


class InputCode(SQLModel):
    """Input model for project codes."""

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

    members: list[InputPerson]
    codes: list[InputCode]
    services: Services


class Project(BaseProject):
    """Project model for data stored in database"""

    id: Optional[int] = Field(default=None, primary_key=True)
    members: list[Person]
    codes: list[str]
    services: Services
