"""Definition of endpoints/routers for the webserver."""

# pylint: disable=too-many-lines

from __future__ import annotations

import json
import logging
import shutil
from collections.abc import AsyncGenerator, Iterable
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, cast

import requests
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Security, status
from sqlmodel import Session, SQLModel, create_engine, select

from api.activescale import (
    get_activescale_client_context,
    init_activescale,
    object_exists,
    upload_file,
)
from api.cors import add_cors_middleware
from api.fake_resdrive import make_fake_resdrive
from api.manifests import bag_directory, bagit_exists, create_manifests_directory
from api.security import ApiKey, validate_api_key, validate_permissions
from config import get_settings
from crate.ro_builder import ROBuilder
from crate.ro_loader import ROLoader, zip_existing_crate
from models.common import ResearchDriveName
from models.request import CreateSubmissionRequest
from models.response import (
    CodeResponse,
    CreateSubmissionResponse,
    DriveInfoResponse,
    DriveResponse,
    ErrorResponse,
    MemberResponse,
    PersonResponse,
    ProjectResponse,
    RoleResponse,
    SubmissionResponse,
)
from models.submission import (
    ACTIVE_STAGES,
    RETRYABLE_STAGES,
    ArchiveSubmission,
    JobStage,
)
from service.projectdb import get_projectdb_client, init_projectdb
from service.projectdb_client import ProjectDBClient

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

logger = logging.getLogger(__name__)


def _log_event(level: int, event: str, **context: Any) -> None:
    payload = {"event": event, **context}
    logger.log(level, json.dumps(payload, default=str))


def _elapsed_ms(started_at: datetime) -> int:
    """Compute elapsed milliseconds from a start timestamp."""
    return int((datetime.now() - started_at).total_seconds() * 1000)


# Configure logging with level from environment
logging.basicConfig(
    level=get_settings().log_level,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Ensure driveoff directory is created
(Path.home() / ".driveoff").mkdir(exist_ok=True)
DB_FILE_NAME = Path.home() / ".driveoff" / "database.db"
DB_URL = f"sqlite:///{DB_FILE_NAME}"

connect_args = {"check_same_thread": False}
engine = create_engine(DB_URL, connect_args=connect_args, echo=False)


def create_db_and_tables() -> None:
    """Create database structure for archive submissions and manifests."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterable[Session]:
    """Return a Session object."""
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
ProjectDbDep = Annotated[ProjectDBClient, Depends(get_projectdb_client)]


@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncGenerator[None, None]:
    """Lifecycle method for the API

    This creates DB tables and initialises the ProjectDB client during
    application startup so routes can depend on it.
    """
    create_db_and_tables()

    # initialize external services
    # initialise ProjectDB client for use in endpoints
    _reconcile_interrupted_jobs()

    try:
        init_projectdb(app_instance)
    except (RuntimeError, ValueError) as e:
        # If the ProjectDB client cannot be initialised, allow app to start
        # but the dependency will raise if used.
        _log_event(logging.WARNING, "projectdb.init_failed", error=str(e))
    try:
        init_activescale(app_instance)
    except (RuntimeError, ValueError) as e:
        # If the Activescale client cannot be initialised, allow app to start
        # but the dependency will raise if used.
        _log_event(logging.WARNING, "activescale.init_failed", error=str(e))
    yield
    engine.dispose()


def _reconcile_interrupted_jobs() -> None:
    """Mark any jobs that were active when the process last exited as abandoned.

    FastAPI BackgroundTasks are volatile; if the process restarts while a job
    is in an active stage (queued/running/uploading/cleanup) that work is lost.
    We surface this to operators as 'abandoned' so they can trigger a manual retry.
    """
    with Session(engine) as session:
        active_stage_values = [s.value for s in ACTIVE_STAGES]
        stage_column = cast(Any, ArchiveSubmission.stage)
        interrupted = session.exec(
            select(ArchiveSubmission).where(stage_column.in_(active_stage_values))
        ).all()
        if not interrupted:
            return
        now = datetime.now()
        for submission in interrupted:
            previous_stage = submission.stage
            _log_event(
                logging.WARNING,
                "submission.abandoned_on_startup",
                submission_id=submission.id,
                drive_name=submission.drive_name,
                previous_stage=previous_stage,
            )
            submission.stage = JobStage.ABANDONED
            submission.failure_reason = (
                f"Process restarted while job was in stage '{previous_stage.value}'."
                " Retry this job to resume."
            )
            submission.failed_timestamp = now
            submission.last_updated_timestamp = now
            session.add(submission)
        session.commit()
        _log_event(
            logging.WARNING,
            "startup.reconciliation_complete",
            abandoned_count=len(interrupted),
        )


app = FastAPI(lifespan=lifespan)

# Send CORS headers to enable frontend to contact API.
add_cors_middleware(app)

ENDPOINT_PREFIX = "/api/v1"


@app.get(
    ENDPOINT_PREFIX + "/driveinfo",
    response_model=DriveInfoResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or missing API key"},
        404: {"model": ErrorResponse, "description": "Drive or project not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_drive_info(
    drive_name: ResearchDriveName,
    projectdb: ProjectDbDep,
    api_key: ApiKey = Security(validate_api_key),
) -> DriveInfoResponse:
    """Retrieve drive and project info from ProjectDB for display.

    Looks up the drive by name, resolves the associated project,
    and returns combined info including members and codes.
    """
    validate_permissions("GET", api_key)

    # Look up drive in ProjectDB
    try:
        drive_data = projectdb.get_research_drive_by_name(drive_name)
        if not drive_data:
            raise HTTPException(
                status_code=404,
                detail=f"Research Drive {drive_name} not found in ProjectDB.",
            )
        if isinstance(drive_data, list):
            drive_data = drive_data[0]
    except (requests.RequestException, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "ProjectDB request failed while fetching drive"
                f" {drive_name}: {str(e)}"
            ),
        ) from e

    # Resolve project from drive
    try:
        drive_projects = projectdb.get_research_drive_projects(
            drive_data["id"], expand=["project"]
        )
    except (requests.RequestException, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "ProjectDB request failed while fetching projects"
                f" for drive {drive_name}: {str(e)}"
            ),
        ) from e

    if not drive_projects or len(drive_projects) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No projects associated with drive {drive_name}",
        )

    # Use the first project (single-project drives are the common case)
    project_id = drive_projects[0]["project"]["id"]

    # Fetch full project data with codes and services
    try:
        project_data = projectdb.get_project(
            pid=project_id,
            expand=["codes", "status", "services"],
        )
    except (requests.RequestException, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "ProjectDB request failed while fetching project"
                f" {project_id}: {str(e)}"
            ),
        ) from e

    # Fetch members
    try:
        members_raw = projectdb.get_project_members(
            project_id,
            expand=["person", "role", "person.identities", "person.status"],
        )
        members_raw = filter_member_identities(members_raw)
    except (requests.RequestException, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "ProjectDB request failed while fetching members"
                f" for project {project_id}: {str(e)}"
            ),
        ) from e

    # Build drive response, preferring service-level data (has first_day/last_day)
    drive_service = None
    for rd in project_data.get("services", {}).get("research_drive", []):
        if rd.get("name") == drive_name:
            drive_service = rd
            break

    drive_resp = DriveResponse(
        id=drive_data["id"],
        name=drive_name,
        allocated_gb=drive_data["allocated_gb"],
        used_gb=drive_data["used_gb"],
        free_gb=drive_data["free_gb"],
        percentage_used=drive_data["percentage_used"],
        date=drive_data["date"],
        first_day=drive_service.get("first_day") if drive_service else None,
        last_day=drive_service.get("last_day") if drive_service else None,
    )

    # Build codes
    codes = _build_codes(project_data)

    # Build members
    members = _build_members(members_raw)

    project_resp = ProjectResponse(
        id=project_data["id"],
        title=project_data.get("title", ""),
        description=project_data.get("description", ""),
        division=project_data.get("division", ""),
        start_date=project_data.get("start_date", ""),
        end_date=project_data.get("end_date", ""),
        codes=codes,
        members=members,
    )

    return DriveInfoResponse(drive=drive_resp, project=project_resp)


@app.post(
    ENDPOINT_PREFIX + "/submission",
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

    if existing_submission and existing_submission.stage == JobStage.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Drive {request.drive_name} has already been successfully archived."
            ),
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

        # Schedule async RO-Crate generation
        _log_event(
            logging.INFO,
            "submission.background_task_scheduled",
            drive_name=request.drive_name,
            submission_id=submission.id,
        )

        background_tasks.add_task(
            generate_ro_crate_async,
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=(
                "An error occurred while creating archive submission"
                f" for {request.drive_name}."
            ),
        ) from e


@app.post(
    ENDPOINT_PREFIX + "/submission/{drive_name}/retry",
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
) -> CreateSubmissionResponse:
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

    if submission.stage == JobStage.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Drive {drive_name} has already been successfully archived.",
        )

    if submission.stage not in RETRYABLE_STAGES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Drive {drive_name} submission is in stage '{submission.stage.value}'"
                " which cannot be retried."
            ),
        )

    # Reset to QUEUED for the new attempt
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

    _log_event(
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

    drive = _validate_drive(projectdb, drive_name)
    background_tasks.add_task(
        generate_ro_crate_async,
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
        existing_submission.activescale_file_key = None
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


def get_resdrive_path(drive_name: str) -> Path:
    """Get a path for a research drive.
    Please update when service acc logic is finalized"""
    drive_path = Path.home() / "mnt" / drive_name
    ###WHILE TESTING MAKE THE DRIVE
    make_fake_resdrive(drive_path)
    if not drive_path.is_dir():
        raise FileNotFoundError(
            "Research Drive must be mounted in order to generate RO-Crate"
        )
    return drive_path


def _cleanup_job_artifacts(
    drive_name: str, output_location: Path
) -> tuple[bool, str | None]:
    """Delete generated local archive artifacts for a submission.

    This intentionally only removes generated artifacts in the archive output
    area and does not remove source drive content under Vault.
    """
    generated_paths = [
        output_location / f"{drive_name}.zip",
        output_location / str(drive_name),
        output_location / f"{drive_name}Vault_manifests",
    ]

    cleanup_errors: list[str] = []
    removed_count = 0
    for path in generated_paths:
        try:
            if path.is_file():
                path.unlink()
                removed_count += 1
            elif path.is_dir():
                shutil.rmtree(path)
                removed_count += 1
        except FileNotFoundError:
            continue
        except OSError as e:  # pragma: no cover - best effort cleanup
            cleanup_errors.append(f"{path}: {e}")

    if cleanup_errors:
        _log_event(
            logging.WARNING,
            "submission.cleanup.failed",
            drive_name=drive_name,
            output_location=str(output_location),
            removed_count=removed_count,
            cleanup_error="; ".join(cleanup_errors),
        )
        return False, "; ".join(cleanup_errors)

    _log_event(
        logging.INFO,
        "submission.cleanup.completed",
        drive_name=drive_name,
        output_location=str(output_location),
        removed_count=removed_count,
    )
    return True, None


def build_crate_contents_async(  # pylint: disable=too-many-arguments, too-many-positional-arguments
    drive: dict[str, Any],
    submission: ArchiveSubmission,
    members_list: list[dict[str, Any]],
    project_data: dict[str, Any],
    drive_location: Path,
    output_location: Path,
) -> None:
    """Generate RO-Crate with data from ProjectDB.

    Args:
        submission: ArchiveSubmission record for this crate generation
        members_list: List of project members from ProjectDB
        project_data: Project data from ProjectDB
        drive_location: Source drive location path
        output_location: Output archive location path
    """
    # Build RO-Crate
    ro_crate_loader = ROLoader()
    ro_crate_loader.init_crate()
    ro_crate_builder = ROBuilder(ro_crate_loader.crate)

    # Add project to crate with archive metadata
    project_entity = ro_crate_builder.add_project(
        project_data, members_list, submission, drive
    )

    # Add drive service as main entity
    drive_entity = ro_crate_builder.add_research_drive_service(drive)

    ro_crate_builder.crate.root_dataset.append_to("mainEntity", drive_entity)
    drive_entity.append_to("project", [project_entity])

    ro_crate_location = drive_location
    if bagit_exists(ro_crate_location):
        ro_crate_location = ro_crate_location / "data"

    _log_event(
        logging.INFO,
        "crate.write.metadata",
        ro_crate_location=str(ro_crate_location),
        drive_name=submission.drive_name,
    )
    ro_crate_loader.write_crate(ro_crate_location)
    bag_directory(
        drive_location,
        bag_info={
            "project_id": str(project_data.get("id", "")),
            "drive_name": submission.drive_name,
        },
    )
    create_manifests_directory(
        drive_path=drive_location,
        output_location=output_location,
        drive_name=str(submission.drive_name),
    )


async def generate_ro_crate_async(  # pylint: disable=too-many-locals,too-many-statements
    drive: dict[str, Any],
    submission_id: int,
    projectdb_client: ProjectDBClient,
) -> None:
    """Async background task for generating RO-Crate and updating archive record.

    Fetches live project data from ProjectDB, generates crate,
    uploads the archive to ActiveScale for long-term storage, and updates
    the ArchiveSubmission record with stage and operational metadata.

    Implements persisted checkpoints so retries can skip completed steps:
    - queued→running: After loading submission from DB
    - running→uploading: After crate build and zip generation
    - uploading→completed/failed: After upload attempt

    Args:
        drive: Dictionary containing research drive information
        submission_id: ID of the ArchiveSubmission record
        projectdb_client: Client for interacting with ProjectDB
    """
    drive_name = drive.get("name", None)
    started_at = datetime.now()
    if drive_name is None:
        _log_event(
            logging.ERROR,
            "crate.build.invalid_drive",
            drive=drive,
            elapsed_ms=_elapsed_ms(started_at),
        )
        return

    # Create a new session for this background task
    with Session(engine) as session:
        submission: ArchiveSubmission | None = None
        output_location = Path.home() / "mnt" / str(drive_name) / "Archive"
        file_key: str | None = None
        project_id: int | None = None
        processing_error: str | None = None
        upload_success = False
        try:
            submission = session.get(ArchiveSubmission, submission_id)
            if submission is None:
                _log_event(
                    logging.ERROR,
                    "crate.build.submission_not_found",
                    submission_id=submission_id,
                    drive_name=drive_name,
                    elapsed_ms=_elapsed_ms(started_at),
                )
                return

            # Transition: queued → running
            previous_stage = submission.stage
            submission.stage = JobStage.RUNNING
            submission.last_updated_timestamp = datetime.now()
            session.add(submission)
            session.commit()

            _log_event(
                logging.INFO,
                "submission.stage_transition",
                submission_id=submission_id,
                drive_name=drive_name,
                from_stage=previous_stage.value,
                to_stage=JobStage.RUNNING.value,
                stage=submission.stage.value,
                retry_count=submission.retry_count,
                elapsed_ms=_elapsed_ms(started_at),
            )

            # Fetch project and member data from ProjectDB
            project_id = submission.project_id
            _log_event(
                logging.INFO,
                "crate.build.projectdb_fetch_start",
                submission_id=submission_id,
                drive_name=drive_name,
                project_id=project_id,
                stage=submission.stage.value,
                retry_count=submission.retry_count,
                elapsed_ms=_elapsed_ms(started_at),
            )
            project_data = projectdb_client.get_project(
                pid=project_id,
                expand=["codes", "status", "services", "properties"],
            )
            members_list = projectdb_client.get_project_members(
                project_id,
                expand=[
                    "person",
                    "role",
                    "person.identities",
                    "person.status",
                ],
            )
            members_list = filter_member_identities(members_list)

            # Generate RO-Crate
            drive_path = get_resdrive_path(drive_name)
            drive_location = drive_path / "Vault"
            output_location = drive_path / "Archive"

            _log_event(
                logging.INFO,
                "crate.build.start",
                submission_id=submission_id,
                drive_name=drive_name,
                project_id=project_id,
                stage=submission.stage.value,
                retry_count=submission.retry_count,
                elapsed_ms=_elapsed_ms(started_at),
            )

            # Build crate contents (idempotent, safe to retry)
            build_crate_contents_async(
                drive=drive,
                submission=submission,
                members_list=members_list,
                project_data=project_data,
                drive_location=drive_location,
                output_location=output_location,
            )

            # Zip the generated crate (check if already exists and skip if so)
            zip_path = output_location / f"{drive_name}.zip"
            if not zip_path.exists():
                _log_event(
                    logging.INFO,
                    "crate.zip.start",
                    submission_id=submission_id,
                    drive_name=drive_name,
                    stage=submission.stage.value,
                    retry_count=submission.retry_count,
                    elapsed_ms=_elapsed_ms(started_at),
                )
                zip_existing_crate(output_location / str(drive_name), drive_location)
                _log_event(
                    logging.INFO,
                    "crate.zip.completed",
                    submission_id=submission_id,
                    drive_name=drive_name,
                    zip_size_mb=(
                        zip_path.stat().st_size / (1024 * 1024)
                        if zip_path.exists()
                        else 0
                    ),
                    stage=submission.stage.value,
                    retry_count=submission.retry_count,
                    elapsed_ms=_elapsed_ms(started_at),
                )
            else:
                _log_event(
                    logging.INFO,
                    "crate.zip.skipped",
                    submission_id=submission_id,
                    drive_name=drive_name,
                    reason="zip file already exists",
                    zip_size_mb=zip_path.stat().st_size / (1024 * 1024),
                    stage=submission.stage.value,
                    retry_count=submission.retry_count,
                    elapsed_ms=_elapsed_ms(started_at),
                )

            # Transition: running → uploading
            previous_stage = submission.stage
            submission.stage = JobStage.UPLOADING
            submission.last_updated_timestamp = datetime.now()
            session.add(submission)
            session.commit()

            _log_event(
                logging.INFO,
                "submission.stage_transition",
                submission_id=submission_id,
                drive_name=drive_name,
                from_stage=previous_stage.value,
                to_stage=JobStage.UPLOADING.value,
                stage=submission.stage.value,
                retry_count=submission.retry_count,
                elapsed_ms=_elapsed_ms(started_at),
            )

            # Upload the archive to ActiveScale
            logger.info(
                "About to start uploading RO-Crate archive for %s to ActiveScale",
                drive_name,
            )

            with get_activescale_client_context() as client:
                # Upload to ActiveScale with drive_name as the key
                bucket_name = "research-archive-test"
                file_key = f"ro-crates/{drive_name}/{drive_name}.zip"
                metadata = {
                    "drive-name": drive_name,
                    "archived-datetime": datetime.now().isoformat(),
                }

                # Check if object already exists on S3 and skip upload if so
                _log_event(
                    logging.INFO,
                    "S3.object_exists.check_start",
                    submission_id=submission_id,
                    drive_name=drive_name,
                    file_key=file_key,
                    stage=submission.stage.value,
                    retry_count=submission.retry_count,
                    elapsed_ms=_elapsed_ms(started_at),
                )
                obj_exists, obj_metadata = object_exists(client, bucket_name, file_key)
                if obj_exists:
                    _log_event(
                        logging.INFO,
                        "S3.upload.skipped",
                        submission_id=submission_id,
                        drive_name=drive_name,
                        file_key=file_key,
                        reason="object already exists on S3",
                        object_size_bytes=(
                            obj_metadata.get("content_length") if obj_metadata else None
                        ),
                        stage=submission.stage.value,
                        retry_count=submission.retry_count,
                        elapsed_ms=_elapsed_ms(started_at),
                    )
                    success = True
                else:
                    success = upload_file(
                        client,
                        bucket_name,
                        file_key,
                        file_path=str(output_location / f"{drive_name}.zip"),
                        metadata=metadata,
                        timeout=get_settings().activescale_upload_timeout,
                    )
                upload_success = success

            # Transition: uploading → cleanup
            previous_stage = submission.stage
            submission.stage = JobStage.CLEANUP
            submission.last_updated_timestamp = datetime.now()
            session.add(submission)
            session.commit()

            _log_event(
                logging.INFO,
                "submission.stage_transition",
                submission_id=submission_id,
                drive_name=drive_name,
                from_stage=previous_stage.value,
                to_stage=JobStage.CLEANUP.value,
                stage=submission.stage.value,
                retry_count=submission.retry_count,
                elapsed_ms=_elapsed_ms(started_at),
            )

            cleanup_succeeded, cleanup_error = _cleanup_job_artifacts(
                str(drive_name), output_location
            )
            submission.cleanup_succeeded = cleanup_succeeded
            submission.cleanup_error = cleanup_error

            # Update submission record with upload result
            now = datetime.now()
            if upload_success:
                submission.stage = JobStage.COMPLETED
                submission.failure_reason = None
                submission.failed_timestamp = None
                submission.activescale_file_key = file_key
                submission.completed_timestamp = now
                submission.last_updated_timestamp = now
                session.add(submission)
                session.commit()

                logger.info(
                    "Successfully uploaded RO-Crate archive for %s to "
                    "ActiveScale at %s",
                    drive_name,
                    file_key,
                )
                _log_event(
                    logging.INFO,
                    "crate.upload.completed",
                    submission_id=submission_id,
                    drive_name=drive_name,
                    file_key=file_key,
                    stage=submission.stage.value,
                    retry_count=submission.retry_count,
                    cleanup_succeeded=submission.cleanup_succeeded,
                    elapsed_ms=_elapsed_ms(started_at),
                )
            else:
                submission.stage = JobStage.FAILED
                submission.failure_reason = "ActiveScale upload failed"
                submission.failed_timestamp = now
                submission.activescale_file_key = file_key
                submission.last_updated_timestamp = now
                session.add(submission)
                session.commit()
                logger.error(
                    "Failed to upload RO-Crate archive for %s to ActiveScale",
                    drive_name,
                )
                _log_event(
                    logging.ERROR,
                    "crate.upload.failed",
                    submission_id=submission_id,
                    drive_name=drive_name,
                    file_key=file_key,
                    stage=submission.stage.value,
                    retry_count=submission.retry_count,
                    cleanup_succeeded=submission.cleanup_succeeded,
                    elapsed_ms=_elapsed_ms(started_at),
                )

            _log_event(
                logging.INFO,
                "crate.build.completed",
                submission_id=submission_id,
                drive_name=drive_name,
                project_id=project_id,
                stage=submission.stage.value,
                retry_count=submission.retry_count,
                cleanup_succeeded=submission.cleanup_succeeded,
                elapsed_ms=_elapsed_ms(started_at),
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            processing_error = str(e)
            if submission is not None:
                now = datetime.now()

                # Transition to cleanup before final failed state.
                previous_stage = submission.stage
                submission.stage = JobStage.CLEANUP
                submission.last_updated_timestamp = now
                session.add(submission)
                session.commit()

                _log_event(
                    logging.WARNING,
                    "submission.stage_transition",
                    submission_id=submission_id,
                    drive_name=drive_name,
                    from_stage=previous_stage.value,
                    to_stage=JobStage.CLEANUP.value,
                    stage=submission.stage.value,
                    retry_count=submission.retry_count,
                    elapsed_ms=_elapsed_ms(started_at),
                )

                cleanup_succeeded, cleanup_error = _cleanup_job_artifacts(
                    str(drive_name), output_location
                )
                submission.cleanup_succeeded = cleanup_succeeded
                submission.cleanup_error = cleanup_error

                submission.stage = JobStage.FAILED
                submission.failure_reason = processing_error
                submission.failed_timestamp = now
                submission.last_updated_timestamp = now
                session.add(submission)
                session.commit()
            _log_event(
                logging.ERROR,
                "crate.build.failed",
                submission_id=submission_id,
                drive_name=drive_name,
                error=processing_error,
                stage=(submission.stage.value if submission is not None else None),
                retry_count=(
                    submission.retry_count if submission is not None else None
                ),
                cleanup_succeeded=(
                    submission.cleanup_succeeded if submission is not None else None
                ),
                elapsed_ms=_elapsed_ms(started_at),
            )
            logger.exception("Background crate generation failed")


@app.get(
    ENDPOINT_PREFIX + "/submission",
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
        activescale_file_key=submission.activescale_file_key,
    )


def _build_codes(project_data: dict[str, Any]) -> list[CodeResponse]:
    """Extract project codes from project data."""
    codes_items = project_data.get("codes", {})
    if isinstance(codes_items, dict):
        codes_items = codes_items.get("items", [])
    return [CodeResponse(id=c.get("id"), code=c["code"]) for c in codes_items]


def _build_members(members_raw: list[dict[str, Any]]) -> list[MemberResponse]:
    """Convert raw member dicts into MemberResponse objects."""
    members = []
    for m in members_raw:
        person = m.get("person", {})
        username = None
        for ident in person.get("identities", {}).get("items", []):
            uname = ident.get("username", "")
            if uname and "@" not in uname:
                username = uname
                break

        members.append(
            MemberResponse(
                role=RoleResponse(
                    id=m.get("role", {}).get("id"),
                    name=m["role"]["name"],
                ),
                person=PersonResponse(
                    id=person.get("id"),
                    email=person.get("email"),
                    full_name=person.get("full_name", ""),
                    username=username,
                ),
            )
        )
    return members


def filter_member_identities(members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter out identities where the username is an email address."""
    try:
        members = [
            {
                **member,
                "person": {
                    **member.get("person", {}),
                    "identities": {
                        "items": [
                            item
                            for item in member.get("person", {})
                            .get("identities", {})
                            .get("items", [])
                            if not item.get("username", "").endswith("@auckland.ac.nz")
                        ]
                    },
                },
            }
            for member in members
        ]
    except (TypeError, AttributeError) as e:
        # Log error but don't fail the whole process - just return unfiltered members
        _log_event(logging.WARNING, "members.filter_failed", error=str(e))
    return members
