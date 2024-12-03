"""sql models for storing maninfests
"""

from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from models.services import ResearchDriveService


class ManifestDriveLink(SQLModel, table=True):
    """Linking table between research drive service and a manifest of files"""

    manifest_id: int | None = Field(
        default=None, foreign_key="manifest.id", primary_key=True
    )
    research_drive_id: int | None = Field(
        default=None, foreign_key="researchdriveservice.id", primary_key=True
    )


class Manifest(SQLModel, table=True):
    """SQL model for storing simple file manifests"""

    id: int = Field(primary_key=True)
    manifest: str
    research_drive: "ResearchDriveService" = Relationship(
        link_model=ManifestDriveLink, back_populates="manifest"
    )
