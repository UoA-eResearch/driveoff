"""API routers package."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlmodel import Session, select

from config import get_settings
from models.submission import ArchiveSubmission


def require_worker_patch_endpoints_enabled() -> None:
    """Guard dependency for the worker PATCH endpoints.

    These endpoints are reserved for the future split-worker architecture
    (workers on a separate host reporting stage transitions back to the API).
    Until that exists they are disabled by default and respond 404, so they
    are indistinguishable from a nonexistent route.
    """
    if not get_settings().worker_patch_endpoints_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


def _get_submission_or_404(session: Session, drive_name: str) -> ArchiveSubmission:
    """Look up an ArchiveSubmission by drive name, raising 404 if not found."""
    submission = session.exec(select(ArchiveSubmission).where(ArchiveSubmission.drive_name == drive_name)).first()
    if submission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No archive submission found for drive {drive_name}.",
        )
    return submission
