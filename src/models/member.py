"""Data models representing project members - person in a project and their role."""

from typing import TYPE_CHECKING

from pydantic import BaseModel
from sqlmodel import Field, Relationship, SQLModel

from models.person import Person
from models.role import Role

if TYPE_CHECKING:
    from models.project import Project


class Member(SQLModel, table=True):
    """Linking table between projects, people and their roles."""

    project_id: int | None = Field(
        default=None, foreign_key="project.id", primary_key=True
    )
    person_id: int | None = Field(
        default=None, foreign_key="person.id", primary_key=True
    )
    role_id: int | None = Field(default=None, foreign_key="role.id", primary_key=True)

    role: "Role" = Relationship()
    project: "Project" = Relationship(back_populates="members")
    person: "Person" = Relationship()


class MemberPublic(BaseModel):
    "Public model for project members."

    role: Role
    person: Person
