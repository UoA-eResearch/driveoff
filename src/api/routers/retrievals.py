"""Archive retrieval endpoint."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, cast

from fastapi import APIRouter, BackgroundTasks, HTTPException, Security, status
from sqlmodel import select

from api.dependencies import SessionDep
from api.security import ApiKey, validate_api_key, validate_permissions
from models.common import ResearchDriveName
from models.request import CreateRetrievalRequest
from models.response import CreateRetrievalResponse, ErrorResponse
from models.retrieval import ACTIVE_RETRIEVAL_STAGES, ArchiveRetrieval, RetrievalJobStage
from models.submission import ArchiveSubmission, JobStage
from utils.logging import log_event
from utils.paths import validate_destination_path
from workers.retrieval_worker import run_archive_retrieval

router = APIRouter()


@router.post(
    "/submission/{drive_name}/retrieve",
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
async def create_retrieval(
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
    submission = session.exec(
        select(ArchiveSubmission).where(ArchiveSubmission.drive_name == drive_name)
    ).first()

    if submission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No archive submission found for drive {drive_name}.",
        )

    if submission.stage != JobStage.COMPLETED:
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
            stage_column.in_(active_stage_values),
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
