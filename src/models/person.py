from pydantic import BaseModel, Field


class Person(BaseModel):
    "Data class describing a person."
    id: int
    email: str = Field(alias="person.email")
    full_name: str = Field(alias="person.full_name")
    identities: dict = Field(alias="person.identities")
