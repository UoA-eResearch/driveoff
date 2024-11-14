"""Data models representing project members - person in a project and their role."""

from sqlmodel import Field, Relationship, SQLModel

from models.person import Person
from models.project import Project
from models.role import Role


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
