"""Models for storing manifest data from archives."""

from __future__ import annotations

from sqlmodel import Field, SQLModel


class Manifest(SQLModel, table=True):
    """Manifest of files in an archive.

    Stores the file listing generated during RO-Crate creation.
    Referenced by ArchiveSubmission via manifest_id.
    """

    id: int | None = Field(default=None, primary_key=True)
    manifest: str  # JSON or text listing of files
