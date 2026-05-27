"""Archive submission endpoints."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import requests
from fastapi import APIRouter, BackgroundTasks, HTTPException, Security, status
from sqlmodel import Session, select

from api.dependencies import ProjectDbDep, SessionDep
from api.security import ApiKey, validate_api_key, validate_permissions
from models.common import ResearchDriveName
from models.request import CreateSubmissionRequest
from models.response import (
    CreateSubmissionResponse,
    ErrorResponse,
    SubmissionResponse,
)
from models.submission import (
    ACTIVE_STAGES,
    RETRYABLE_STAGES,
    ArchiveSubmission,
    JobStage,
)
from service.projectdb_client import ProjectDBClient
from utils.logging import log_event
from utils.paths import validate_archive_path_access
from workers.submission_worker import generate_ro_crate

router = APIRouter()


# ── HTTP-layer helpers ────────────────────────────────────────────────────────
# These raise HTTPException so they belong in the router, not the worker.


def _validate_drive(projectdb: ProjectDBClient, drive_name: str) -> Any:
    """Fetch and validate drive from ProjectDB."""
    drive = projectdb.get_research_drive_by_name(drive_name)
    if not drive:
        raise HTTPException(
            status_code=404,
            detail=f"Research Drive {drive_name} not found in ProjectDB.",
        )
    if isinstance(drive, list):
        drive = drive[0]
    if not drive:
        raise HTTPException(
            status_code=404,
            detail=f"Research Drive {drive_name} not found in ProjectDB.",
        )
    return drive


def _resolve_project_id(
    projectdb: ProjectDBClient,
    drive: dict[str, Any],
    request: CreateSubmissionRequest,
) -> Any:
    """Resolve the project_id for a drive from ProjectDB."""
    try:
        drive_projects = projectdb.get_research_drive_projects(
            drive["id"], expand=["project"]
        )
    except (requests.RequestException, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "ProjectDB request failed while fetching projects"
                f" for drive {request.drive_name}: {e}"
            ),
        ) from e

    if not drive_projects:
        raise HTTPException(
            status_code=404,
            detail=f"No projects associated with drive {request.drive_name}",
        )

    if len(drive_projects) == 1:
        return drive_projects[0]["project"]["id"]

    # Multiple projects – need project_id from request to disambiguate
    if request.project_id:
        for dp in drive_projects:
            if dp["project"]["id"] == request.project_id:
                return request.project_id
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Multiple projects associated with drive {request.drive_name}. "
                "Please provide project_id to disambiguate."
            ),
        )

    raise HTTPException(
        status_code=400,
        detail="Could not determine project_id for archive",
    )


def _upsert_submission(
    session: Session,
    existing_submission: ArchiveSubmission | None,
    drive: dict[str, Any],
    project_id: int,
    request: CreateSubmissionRequest,
) -> ArchiveSubmission:
    """Update an existing pending submission or create a new one."""
    if existing_submission:
        existing_submission.drive_id = drive["id"]
        existing_submission.project_id = project_id
        existing_submission.retention_period_years = request.retention_period_years
        existing_submission.retention_period_justification = (
            request.retention_period_justification
        )
        existing_submission.data_classification = request.data_classification
        existing_submission.failure_reason = None
        existing_submission.failed_timestamp = None
        existing_submission.archive_file_key = None
        existing_submission.archive_object_prefix = None
        existing_submission.archive_manifest_key = None
        existing_submission.archive_part_keys_json = None
        existing_submission.archive_part_count = None
        existing_submission.archive_total_bytes = None
        submission = existing_submission
    else:
        submission = ArchiveSubmission(
            drive_id=drive["id"],
            project_id=project_id,
            drive_name=request.drive_name,
            retention_period_years=request.retention_period_years,
            retention_period_justification=request.retention_period_justification,
            data_classification=request.data_classification,
        )

    now = datetime.now()
    submission.stage = JobStage.QUEUED
    submission.started_timestamp = now
    submission.last_updated_timestamp = now
    submission.completed_timestamp = None
    submission.cleanup_succeeded = None
    submission.cleanup_error = None

    session.add(submission)
    session.commit()
    session.refresh(submission)
    if submission.id is None:
        raise HTTPException(
            status_code=500,
            detail="Failed to create archive submission record.",
        )
    return submission


def _as_bad_request_for_archive_path(
    drive_name: str,
    error: FileNotFoundError | PermissionError | RuntimeError,
) -> HTTPException:
    """Convert archive path validation errors into consistent client errors."""
    log_event(
        logging.WARNING,
        "submission.archive_path_validation_failed",
        drive_name=drive_name,
        error=str(error),
        error_type=type(error).__name__,
    )
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(f"Archive path validation failed for drive {drive_name}: {error}"),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/submission",
    status_code=status.HTTP_201_CREATED,
    response_model=CreateSubmissionResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid submission request"},
        401: {"model": ErrorResponse, "description": "Invalid or missing API key"},
        404: {"model": ErrorResponse, "description": "Drive or project not found"},
        409: {
            "model": ErrorResponse,
            "description": "Drive has already been archived",
        },
        422: {"description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        502: {
            "model": ErrorResponse,
            "description": "ProjectDB upstream request failed",
        },
    },
)
async def create_submission(
    request: CreateSubmissionRequest,
    session: SessionDep,
    background_tasks: BackgroundTasks,
    projectdb: ProjectDbDep,
    api_key: ApiKey = Security(validate_api_key),
) -> CreateSubmissionResponse:
    """Create a new archive submission for a research drive.

    Validates drive exists in ProjectDB, resolves project_id if needed,
    and schedules RO-Crate generation as a background task.
    """
    validate_permissions("POST", api_key)
    existing_submission = session.exec(
        select(ArchiveSubmission).where(
            ArchiveSubmission.drive_name == request.drive_name
        )
    ).first()

    if (
        existing_submission
        and existing_submission.stage == JobStage.COMPLETED
        and not request.force
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Drive {request.drive_name} has already been successfully archived."
                " Use force=true to re-run."
            ),
        )

    if (
        existing_submission
        and existing_submission.stage == JobStage.COMPLETED
        and request.force
    ):
        log_event(
            logging.WARNING,
            "submission.force_rerun",
            drive_name=request.drive_name,
            previous_stage=existing_submission.stage.value,
            submission_id=existing_submission.id,
        )

    if existing_submission and existing_submission.stage in ACTIVE_STAGES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Drive {request.drive_name} already has an active archive job"
                f" in stage '{existing_submission.stage.value}'."
                " Wait for it to finish or use the retry endpoint if it has failed."
            ),
        )

    try:
        drive = _validate_drive(projectdb, request.drive_name)
        project_id = _resolve_project_id(projectdb, drive, request)

        # Validate drive paths are accessible before creating submission record
        # This ensures we fail fast with clear errors before returning 201
        validate_archive_path_access(request.drive_name)

        submission = _upsert_submission(
            session,
            existing_submission,
            drive,
            project_id,
            request,
        )

        if submission.id is None:
            raise HTTPException(
                status_code=500,
                detail="Archive submission record is missing ID after creation.",
            )

        log_event(
            logging.INFO,
            "submission.background_task_scheduled",
            drive_name=request.drive_name,
            submission_id=submission.id,
        )

        background_tasks.add_task(
            generate_ro_crate,
            drive,
            submission.id,
            projectdb_client=projectdb,
        )

        status_word = "updated" if existing_submission else "created"
        return CreateSubmissionResponse(
            message=(
                f"Archive submission {status_word}"
                f" for {request.drive_name}."
                " RO-Crate generation and upload to ActiveScale is in progress."
            )
        )
    except (FileNotFoundError, PermissionError, RuntimeError) as e:
        raise _as_bad_request_for_archive_path(request.drive_name, e) from e
    except HTTPException:
        raise
    except Exception as e:
        log_event(
            logging.ERROR,
            "submission.create.unexpected_error",
            drive_name=request.drive_name,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=(
                "An error occurred while creating archive submission"
                f" for {request.drive_name}."
            ),
        ) from e


@router.post(
    "/submission/{drive_name}/retry",
    status_code=status.HTTP_200_OK,
    response_model=CreateSubmissionResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or missing API key"},
        404: {"model": ErrorResponse, "description": "No submission found for drive"},
        409: {
            "model": ErrorResponse,
            "description": "Job is active or already completed",
        },
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def retry_submission(
    drive_name: ResearchDriveName,
    session: SessionDep,
    background_tasks: BackgroundTasks,
    projectdb: ProjectDbDep,
    api_key: ApiKey = Security(validate_api_key),
    force: bool = False,
) -> CreateSubmissionResponse:  # pylint: disable=too-many-arguments,too-many-positional-arguments
    """Retry a failed or abandoned archive job for a research drive."""
    validate_permissions("POST", api_key)

    submission = session.exec(
        select(ArchiveSubmission).where(ArchiveSubmission.drive_name == drive_name)
    ).first()

    if submission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No archive submission found for drive {drive_name}.",
        )

    if submission.stage in ACTIVE_STAGES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Drive {drive_name} already has an active archive job"
                f" in stage '{submission.stage.value}'."
                " Wait for it to finish."
            ),
        )

    if submission.stage == JobStage.COMPLETED and not force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Drive {drive_name} has already been successfully archived."
                " Use force=true to re-run."
            ),
        )

    if submission.stage not in RETRYABLE_STAGES and not (
        force and submission.stage == JobStage.COMPLETED
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Drive {drive_name} submission is in stage '{submission.stage.value}'"
                " which cannot be retried."
            ),
        )

    if force and submission.stage == JobStage.COMPLETED:
        log_event(
            logging.WARNING,
            "submission.force_rerun",
            drive_name=drive_name,
            previous_stage=submission.stage.value,
            submission_id=submission.id,
        )

    drive = _validate_drive(projectdb, drive_name)

    try:
        validate_archive_path_access(drive_name)
    except (FileNotFoundError, PermissionError, RuntimeError) as e:
        raise _as_bad_request_for_archive_path(drive_name, e) from e

    now = datetime.now()
    submission.stage = JobStage.QUEUED
    submission.failure_reason = None
    submission.failed_timestamp = None
    submission.retry_count = (submission.retry_count or 0) + 1
    submission.last_updated_timestamp = now
    submission.completed_timestamp = None
    submission.cleanup_succeeded = None
    submission.cleanup_error = None
    session.add(submission)
    session.commit()
    session.refresh(submission)

    log_event(
        logging.INFO,
        "submission.retry_scheduled",
        drive_name=drive_name,
        submission_id=submission.id,
        retry_count=submission.retry_count,
    )

    if submission.id is None:
        raise HTTPException(
            status_code=500,
            detail="Archive submission record is missing ID.",
        )

    background_tasks.add_task(
        generate_ro_crate,
        drive,
        submission.id,
        projectdb_client=projectdb,
    )

    return CreateSubmissionResponse(
        message=(
            f"Archive job for {drive_name} queued for retry"
            f" (attempt {submission.retry_count})."
            " RO-Crate generation and upload to ActiveScale is in progress."
        )
    )


@router.get(
    "/submission",
    response_model=SubmissionResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or missing API key"},
        404: {
            "model": ErrorResponse,
            "description": "No archive submission found for drive",
        },
    },
)
async def get_submission(
    drive_name: ResearchDriveName,
    session: SessionDep,
    api_key: ApiKey = Security(validate_api_key),
) -> SubmissionResponse:
    """Retrieve archive submission record for a research drive."""
    validate_permissions("GET", api_key)

    stmt = select(ArchiveSubmission).where(ArchiveSubmission.drive_name == drive_name)
    submission = session.exec(stmt).first()

    if submission is None:
        raise HTTPException(
            status_code=404,
            detail=f"No archive submission found for drive {drive_name}",
        )

    return SubmissionResponse(
        drive_id=submission.drive_id,
        project_id=submission.project_id,
        drive_name=submission.drive_name,
        retention_period_years=submission.retention_period_years,
        retention_period_justification=submission.retention_period_justification,
        data_classification=submission.data_classification,
        stage=submission.stage,
        failure_reason=submission.failure_reason,
        failed_timestamp=submission.failed_timestamp,
        started_timestamp=submission.started_timestamp,
        last_updated_timestamp=submission.last_updated_timestamp,
        completed_timestamp=submission.completed_timestamp,
        retry_count=submission.retry_count,
        cleanup_succeeded=submission.cleanup_succeeded,
        cleanup_error=submission.cleanup_error,
        archive_file_key=submission.archive_file_key,
        archive_object_prefix=submission.archive_object_prefix,
        archive_manifest_key=submission.archive_manifest_key,
        archive_part_keys_json=submission.archive_part_keys_json,
        archive_part_count=submission.archive_part_count,
        archive_total_bytes=submission.archive_total_bytes,
    )
