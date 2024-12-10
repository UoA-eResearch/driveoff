"""Classes related to user submission for offboarding."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pydantic import AliasGenerator, ConfigDict
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

    drive_name: str
    project_changes: ProjectChanges | None = Field(default=None)


class DriveOffboardSubmission(BaseDriveOffboardSubmission, table=True):
    """Model that represents a user's submission in the drive
    offboarding process retrieved."""

    id: int | None = Field(default=None, primary_key=True)
    updated_time: datetime
    id: Optional[int] = Field(default=None, primary_key=True)
    drive_id: int | None = Field(default=None, foreign_key="researchdriveservice.id")
    drive: Optional["ResearchDriveService"] = Relationship(back_populates="submission")


class ROCrateDriveOffboardSubmission(BaseDriveOffboardSubmission):
    "Data class for a submission model to be written as part of an RO-Crate"
    model_config = ConfigDict(  # type: ignore
        alias_generator=AliasGenerator(
            serialization_alias=to_camel,
        )
    )
    id: int
    updated_time: datetime

    def __init__(self, submission: DriveOffboardSubmission):
        super().__init__(**submission.model_dump())


class ROCrateDeleteAction(SQLModel):
    """Model to capture delete actions in an RO-Crate
    that are derived from submissions"""

    model_config = ConfigDict(  # type: ignore
        alias_generator=AliasGenerator(
            serialization_alias=to_camel,
        )
    )
    schema_type: str = Field(
        default="DeleteAction", schema_extra={"serialization_alias": "@type"}
    )
    action_Status: str = Field(default="PotentialActionStatus")
    end_time: datetime
