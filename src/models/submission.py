"""Classes related to user submission for offboarding."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pydantic.alias_generators import to_camel
from sqlmodel import Field, Relationship, SQLModel

from models.common import DataClassification
from models.project_changes import ProjectChanges

if TYPE_CHECKING:
    from models.services import ResearchDriveService


class BaseDriveOffboardSubmission(SQLModel):
    """Model of drive offboarding submission with common fields."""

    # https://github.com/fastapi/sqlmodel/discussions/855
    model_config = {  # pyright: ignore
        "alias_generator": to_camel,
        "str_strip_whitespace": True,
    }

    retention_period_years: int
    retention_period_justification: str | None = Field(default=None)
    data_classification: DataClassification
    is_completed: bool


class InputDriveOffboardSubmission(BaseDriveOffboardSubmission):
    """Submission data model for the POST request."""

    drive_name: str = Field(schema_extra={"validation_alias": "driveName"})
    project_changes: ProjectChanges | None = Field(
        default=None, schema_extra={"validation_alias": "projectChanges"}
    )


class DriveOffboardSubmission(BaseDriveOffboardSubmission, table=True):
    """Model that represents a user's submission in the drive
    offboarding process retrieved."""

    id: int | None = Field(default=None, primary_key=True)
    updated_time: datetime
    is_project_updated: bool
    drive_id: int | None = Field(default=None, foreign_key="researchdriveservice.id")
    drive: Optional["ResearchDriveService"] = Relationship(back_populates="submission")
