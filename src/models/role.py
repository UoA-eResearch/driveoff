"""Data model and code representing project roles."""

from typing import Optional

from sqlmodel import Field, SQLModel


class Role(SQLModel, table=True):
    """Project roles for people."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str


def prepopulate_roles() -> list[Role]:
    """Returns fixtures for known roles in the CeR database."""
    return [
        Role(id=9, name="CeR Contact"),
        Role(id=4, name="Contact Person"),
        Role(id=13, name="Data Contact"),
        Role(id=12, name="Data Owner"),
        Role(id=14, name="Former Team Member"),
        Role(id=6, name="Grant PI"),
        Role(id=7, name="Primary Adviser"),
        Role(id=10, name="Primary Reviewer"),
        Role(id=1, name="Project Owner"),
        Role(id=3, name="Project Team Member"),
        Role(id=11, name="Reviewer"),
        Role(id=2, name="Supervisor"),
        Role(id=8, name="Support"),
    ]
