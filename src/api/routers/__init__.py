"""API routers package."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlmodel import Session, select

from models.submission import ArchiveSubmission


def _get_submission_or_404(session: Session, drive_name: str) -> ArchiveSubmission:
    """Look up an ArchiveSubmission by drive name, raising 404 if not found."""
    submission = session.exec(
        select(ArchiveSubmission).where(ArchiveSubmission.drive_name == drive_name)
    ).first()
    if submission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No archive submission found for drive {drive_name}.",
        )
    return submission
