"""Classes related to user submission for offboarding."""

from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from models.services import ResearchDriveService


class DriveOffboardSubmission(SQLModel, table=True):
    """Model that represents a user's submission in the drive offboarding process."""

    id: int | None = Field(default=None, primary_key=True)
    retention_period_years: int
    retention_period_justification: str | None
    data_classification: str
    is_completed: bool
    drive_id: int = Field(default=None, foreign_key="researchdriveservice.id")
    drive: "ResearchDriveService" = Relationship(back_populates="submission")
