"""Data models representing people and their identities."""

from typing import Optional

from pydantic import AliasGenerator, ConfigDict
from pydantic.alias_generators import to_camel
from sqlmodel import Field, SQLModel

from models.role import Role


class InputIdentity(SQLModel):
    """Data class for the identity list in POST request."""

    username: str


class InputIdentityResultItems(SQLModel):
    """The set of result items from Project DB API."""

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


class ROCratePerson(SQLModel):
    "Data class for a Person model to be written as part of an RO-Crate"
    # Bug with SQLModel library causing typing error:
    # https://github.com/fastapi/sqlmodel/discussions/855
    model_config = ConfigDict(  # type: ignore
        alias_generator=AliasGenerator(
            serialization_alias=to_camel,
        )
    )
    email: Optional[str]
    full_name: str = Field(schema_extra={"serialization_alias": "name"})

    def __init__(self, person: Person):
        super().__init__(**person.model_dump())
