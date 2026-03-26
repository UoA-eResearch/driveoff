"""Request models for the API."""

from pydantic import field_validator
from sqlmodel import SQLModel

from models.common import DataClassification, ResearchDriveName


class CreateSubmissionRequest(SQLModel):
    """Request body for creating an archive submission."""

    drive_name: ResearchDriveName
    retention_period_years: int
    retention_period_justification: str | None = None
    data_classification: DataClassification = DataClassification.SENSITIVE
    project_id: int | None = None

    @field_validator("retention_period_years")
    @classmethod
    def check_minimum_retention(cls, v: int) -> int:
        """Enforce a minimum retention period of 6 years."""
        if v < 6:
            raise ValueError("Retention period must be at least 6 years.")
        return v
