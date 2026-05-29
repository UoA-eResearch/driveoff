"""Archive retrieval endpoint."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, cast

from fastapi import APIRouter, BackgroundTasks, HTTPException, Security, status
from sqlmodel import select

from api.dependencies import SessionDep
from api.routers import _get_submission_or_404
from api.security import ApiKey, validate_api_key, validate_permissions
from models.common import ResearchDriveName
from models.request import CreateRetrievalRequest, PatchRetrievalRequest
from models.response import CreateRetrievalResponse, ErrorResponse, RetrievalResponse
from models.retrieval import (
    ACTIVE_RETRIEVAL_STAGES,
    ArchiveRetrieval,
    RetrievalJobStage,
)
from models.submission import ArchiveJobStage
from utils.logging import log_event
from utils.paths import validate_destination_path
from workers.retrieval_worker import run_archive_retrieval

router = APIRouter(tags=["retrievals"])


@router.post(
    "/retrieval/{drive_name}",
    status_code=status.HTTP_201_CREATED,
    response_model=CreateRetrievalResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid retrieval request"},
        401: {"model": ErrorResponse, "description": "Invalid or missing API key"},
        404: {
            "model": ErrorResponse,
            "description": "No completed archive submission found for drive",
        },
        409: {
            "model": ErrorResponse,
            "description": "A retrieval job for this drive is already active",
        },
        422: {"description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def create_retrieval(
    drive_name: ResearchDriveName,
    request: CreateRetrievalRequest,
    session: SessionDep,
    background_tasks: BackgroundTasks,
    api_key: ApiKey = Security(validate_api_key),
) -> CreateRetrievalResponse:
    """Schedule an archive retrieval job for a research drive.

    Validates that a completed archive exists for the drive and that the
    destination path is accessible, then schedules a background task to
    restore, download, and extract the archive into the destination.
    """
    validate_permissions("POST", api_key)

    # 1. Verify a completed archive submission exists for this drive.
    submission = _get_submission_or_404(session, drive_name)

    if submission.stage != ArchiveJobStage.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Archive for drive {drive_name} is not in a completed state"
                f" (current stage: '{submission.stage.value}')."
                " Retrieval requires a successfully completed archive."
            ),
        )

    if not submission.archive_manifest_key:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Archive submission for drive {drive_name} has no manifest key."
                " The archive may be incomplete."
            ),
        )

    # 2. Check there is no active retrieval job already running for this drive.
    active_stage_values = [s.value for s in ACTIVE_RETRIEVAL_STAGES]
    stage_column = cast(Any, ArchiveRetrieval.stage)
    active_retrieval = session.exec(
        select(ArchiveRetrieval).where(
            ArchiveRetrieval.drive_name == drive_name,
            stage_column.in_(active_stage_values),  # pylint: disable=no-member
        )
    ).first()

    if active_retrieval is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"A retrieval job for drive {drive_name} is already active"
                f" (stage: '{active_retrieval.stage.value}')."
            ),
        )

    # 3. Validate the destination path exists and is writable.
    try:
        validate_destination_path(request.destination_path)
    except (FileNotFoundError, PermissionError) as e:
        log_event(
            logging.WARNING,
            "retrieval.destination_path_validation_failed",
            drive_name=drive_name,
            destination_path=request.destination_path,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Destination path validation failed: {e}",
        ) from e

    # 4. Create the retrieval record.
    if submission.id is None:
        raise HTTPException(
            status_code=500,
            detail="Archive submission record is missing ID.",
        )

    now = datetime.now()
    retrieval = ArchiveRetrieval(
        drive_name=drive_name,
        submission_id=submission.id,
        destination_path=request.destination_path,
        stage=RetrievalJobStage.QUEUED,
        started_timestamp=now,
        last_updated_timestamp=now,
    )
    session.add(retrieval)
    session.commit()
    session.refresh(retrieval)

    if retrieval.id is None:
        raise HTTPException(
            status_code=500,
            detail="Failed to create archive retrieval record.",
        )

    log_event(
        logging.INFO,
        "retrieval.background_task_scheduled",
        retrieval_id=retrieval.id,
        drive_name=drive_name,
        destination_path=request.destination_path,
        submission_id=submission.id,
    )

    # 5. Schedule the background task.
    background_tasks.add_task(run_archive_retrieval, retrieval.id)

    return CreateRetrievalResponse(
        message=(
            f"Archive retrieval job created for {drive_name}."
            f" Restoring archive to {request.destination_path}."
        )
    )


@router.get(
    "/retrieval/{drive_name}",
    status_code=status.HTTP_200_OK,
    response_model=RetrievalResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or missing API key"},
        404: {
            "model": ErrorResponse,
            "description": "No archive retrieval job found for drive",
        },
        422: {"description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def get_retrieval(
    drive_name: ResearchDriveName,
    session: SessionDep,
    api_key: ApiKey = Security(validate_api_key),
) -> RetrievalResponse:
    """Check if an archive retrieval job exists for the drive and return it."""
    validate_permissions("GET", api_key)

    retrieval = session.exec(
        select(ArchiveRetrieval).where(ArchiveRetrieval.drive_name == drive_name)
    ).first()

    if retrieval is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No archive retrieval job found for drive {drive_name}.",
        )

    return RetrievalResponse.model_validate(retrieval)


@router.patch(
    "/retrieval/{retrieval_id}",
    status_code=status.HTTP_200_OK,
    response_model=RetrievalResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or missing API key"},
        404: {"model": ErrorResponse, "description": "Retrieval job not found"},
        422: {"description": "Validation error"},
    },
)
def patch_retrieval(
    retrieval_id: int,
    patch: PatchRetrievalRequest,
    session: SessionDep,
    api_key: ApiKey = Security(validate_api_key),
) -> RetrievalResponse:
    """Partially update an archive retrieval record.

    Intended for worker processes to report stage transitions and progress.
    Only fields present in the request body are applied.  Timestamps are
    managed server-side: last_updated_timestamp is always refreshed;
    completed_timestamp and failed_timestamp are set automatically on the
    corresponding stage transition.
    """
    validate_permissions("PATCH", api_key)

    retrieval = session.get(ArchiveRetrieval, retrieval_id)
    if retrieval is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No retrieval job found with id {retrieval_id}.",
        )

    update_data = patch.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(retrieval, field, value)

    now = datetime.now()
    retrieval.last_updated_timestamp = now
    if "stage" in update_data:
        if (
            retrieval.stage == RetrievalJobStage.COMPLETED
            and retrieval.completed_timestamp is None
        ):
            retrieval.completed_timestamp = now
        elif (
            retrieval.stage == RetrievalJobStage.FAILED
            and retrieval.failed_timestamp is None
        ):
            retrieval.failed_timestamp = now

    session.add(retrieval)
    session.commit()
    session.refresh(retrieval)

    return RetrievalResponse.model_validate(retrieval)
