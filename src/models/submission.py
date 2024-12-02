"""Classes related to user submission for offboarding."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pydantic import ConfigDict
from sqlmodel import Field, Relationship, SQLModel

from models.common import DataClassification

if TYPE_CHECKING:
    from models.services import ResearchDriveService


class DriveOffboardSubmission(SQLModel):
    """Model that represents a user's submission in the drive
    offboarding process retrieved."""

    # Bug with SQLModel library causing typing error:
    # https://github.com/fastapi/sqlmodel/discussions/855
    model_config = ConfigDict(str_strip_whitespace=True)  # type: ignore

    id: int | None = Field(default=None, primary_key=True)
    retention_period_years: int
    retention_period_justification: str | None = None
    data_classification: DataClassification
    is_completed: bool
    updated_time: datetime
    is_project_updated: bool
    drive_id: int | None = Field(default=None, foreign_key="researchdriveservice.id")
    drive: Optional["ResearchDriveService"] = Relationship(back_populates="submission")
