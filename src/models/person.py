from typing import Optional

from sqlmodel import Field, SQLModel

from models.role import Role


class InputIdentity(SQLModel):
    username: str


class InputIdentityResultItems(SQLModel):
    """The set of result items from Project DB API."""

    href: str
    items: list[InputIdentity]


class InputPerson(SQLModel):
    "Data class for a Person model in POST request."
    id: Optional[int] = Field(default=None, primary_key=True)
    email: Optional[str] = Field(schema_extra={"validation_alias": "person.email"})
    full_name: str = Field(schema_extra={"validation_alias": "person.full_name"})
    identities: InputIdentityResultItems = Field(
        schema_extra={"validation_alias": "person.identities"}
    )
    role: Role


class Person(SQLModel, table=True):
    "Data class for a Person model in database."
    id: Optional[int] = Field(default=None, primary_key=True)
    email: Optional[str]
    full_name: str
    username: str
