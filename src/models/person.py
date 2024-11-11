from typing import Optional

from sqlmodel import Field, SQLModel


class InputIdentity(SQLModel):
    username: str


class InputIdentityResultItems(SQLModel):
    """The set of result items from Project DB API."""

    href: str
    items: list[InputIdentity]


class InputPerson(SQLModel):
    "Data class for a Person model in POST request."
    email: Optional[str] = Field(schema_extra={"validation_alias": "person.email"})
    full_name: str = Field(schema_extra={"validation_alias": "person.full_name"})
    identities: InputIdentityResultItems = Field(
        schema_extra={"validation_alias": "person.identities"}
    )


class Person(SQLModel, table=True):
    "Data class for a Person model in database."
    id: Optional[int] = Field(default=None, primary_key=True)
    email: Optional[str]
    full_name: str
    username: str
