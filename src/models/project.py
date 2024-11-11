from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from models.person import Person
from models.services import Services


class Project(BaseModel):
    """Model for describing a project."""

    id: Optional[int] = Field(default=None)
    title: Optional[str]
    description: Optional[str]
    division: Optional[str]
    codes: Optional[list[dict]]
    start_date: datetime
    end_date: datetime
    services: Services
    members: Optional[list[Person]]
