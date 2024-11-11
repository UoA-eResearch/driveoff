from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ResearchDriveService(BaseModel):
    """Object describing a research drive service."""

    allocated_gb: float
    date: datetime
    first_day: datetime
    free_gb: float
    id: int
    last_day: Optional[datetime]
    name: str
    percentage_used: float
    used_gb: float


class Services(BaseModel):
    """Object describing relevant storage services."""

    research_drive: list[ResearchDriveService]
