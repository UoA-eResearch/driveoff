"""Data models representing people and their identities."""

from typing import Optional

from pydantic import AliasGenerator, ConfigDict, model_validator
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

    @model_validator(mode="before")
    def normalize_person_input(cls, values: dict):
        """Normalize nested and flattened person input shapes.

        Accepts either {'person': {...}} or flattened keys like 'person.email'.
        Ensures `identities` is in the form {'items': [...] } for model parsing.
        """
        if not isinstance(values, dict):
            return values

        # If a nested 'person' dict exists, prefer its fields
        person = values.get("person")
        if isinstance(person, dict):
            # populate flattened/expected fields from nested dict
            if "email" in person:
                values.setdefault("email", person.get("email"))
            if "full_name" in person or "name" in person:
                values.setdefault(
                    "full_name", person.get("full_name") or person.get("name")
                )
            identities = person.get("identities")
        else:
            # look for flattened keys
            identities = values.get("person.identities") or values.get(
                "person.identities.items"
            )
            if "person.email" in values:
                values.setdefault("email", values.get("person.email"))
            if "person.full_name" in values:
                values.setdefault("full_name", values.get("person.full_name"))

        # Normalise identities shape and filter unwanted usernames
        items_list = []
        if isinstance(identities, dict) and "items" in identities:
            items_list = identities.get("items", [])
        elif isinstance(identities, list):
            items_list = identities

        # Filter out internal usernames (e.g. @auckland.ac.nz)
        filtered = []
        for it in items_list:
            uname = None
            if isinstance(it, dict):
                uname = it.get("username")
            else:
                uname = getattr(it, "username", None)
            if isinstance(uname, str) and uname.endswith("@auckland.ac.nz"):
                continue
            filtered.append(it)

        values.setdefault("identities", {"items": filtered})

        return values


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
