"""Definition of endpoints/routers for the webserver."""

import re
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, AsyncGenerator, Iterable

from ceradmin_cli.api_client.eresearch_project import ProjectDBApi
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Security, status
from pydantic import BaseModel, field_validator
from pydantic.functional_validators import AfterValidator
from sqlmodel import Session, SQLModel, create_engine, select

from api.cors import add_cors_middleware
from api.fake_resdrive import make_fake_resdrive
from api.manifests import (
    bag_directory,
    bagit_exists,
    create_manifests_directory,
    generate_manifest,
)
from api.projectdb import get_projectdb_client, init_projectdb
from api.security import ApiKey, validate_api_key, validate_permissions
from crate.ro_builder import ROBuilder
from crate.ro_loader import ROLoader, zip_existing_crate
from models.common import DataClassification
from models.submission import ArchiveSubmission

# Ensure driveoff directory is created
(Path.home() / ".driveoff").mkdir(exist_ok=True)
DB_FILE_NAME = Path.home() / ".driveoff" / "database.db"
DB_URL = f"sqlite:///{DB_FILE_NAME}"

connect_args = {"check_same_thread": False}
engine = create_engine(DB_URL, connect_args=connect_args, echo=True)


def create_db_and_tables() -> None:
    """Create database structure for archive submissions and manifests."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterable[Session]:
    """Return a Session object."""
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
ProjectDbDep = Annotated[ProjectDBApi, Depends(get_projectdb_client)]


@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncGenerator[None, None]:
    """Lifecycle method for the API

    This creates DB tables and initialises the ProjectDB client during
    application startup so routes can depend on it.
    """
    create_db_and_tables()
    # initialise ProjectDB client for use in endpoints
    try:
        init_projectdb(app_instance)
    except (RuntimeError, ValueError) as e:
        # If the ProjectDB client cannot be initialised, allow app to start
        # but the dependency will raise if used.
        print(f"Warning: ProjectDB client initialization failed: {e}")
    yield


app = FastAPI(lifespan=lifespan)

# Send CORS headers to enable frontend to contact API.
add_cors_middleware(app)

RESEARCH_DRIVE_REGEX = re.compile(r"res[a-z]{3}[0-9]{9}-[a-zA-Z0-9-_]+")

ENDPOINT_PREFIX = "/api/v1"


def validate_resdrive_name(drive_name: str) -> str:
    """Check if the string is a valid Research Drive name."""
    if RESEARCH_DRIVE_REGEX.match(drive_name) is None:
        raise ValueError(f"'{drive_name}' is not a valid Research Drive name.")

    return drive_name


ResearchDriveName = Annotated[str, AfterValidator(validate_resdrive_name)]


# ── Read-only response models for drive info endpoint ──


class RoleResponse(BaseModel):
    """Project role."""

    id: int | None = None
    name: str


class PersonResponse(BaseModel):
    """Person summary for display."""

    id: int | None = None
    email: str | None = None
    full_name: str
    username: str | None = None


class MemberResponse(BaseModel):
    """Project member with role."""

    role: RoleResponse
    person: PersonResponse


class CodeResponse(BaseModel):
    """Project code."""

    id: int | None = None
    code: str


class DriveResponse(BaseModel):
    """Research drive storage info."""

    id: int | None = None
    name: str
    allocated_gb: float
    used_gb: float
    free_gb: float
    percentage_used: float
    date: str
    first_day: str | None = None
    last_day: str | None = None


class ProjectResponse(BaseModel):
    """Project summary for display."""

    id: int
    title: str
    description: str
    division: str
    start_date: str
    end_date: str
    codes: list[CodeResponse] = []
    members: list[MemberResponse] = []


class DriveInfoResponse(BaseModel):
    """Combined drive + project info returned by the driveinfo endpoint."""

    drive: DriveResponse
    project: ProjectResponse


class CreateSubmissionRequest(SQLModel):
    """Request body for creating an archive submission."""

    drive_name: ResearchDriveName
    retention_period_years: int
    retention_period_justification: str | None = None
    data_classification: DataClassification = DataClassification.SENSITIVE
    project_id: int | None = None

    @field_validator("retention_period_years")
    @classmethod
    def check_minimum_retention(cls, v: int) -> int:
        """Enforce a minimum retention period of 6 years."""
        if v < 6:
            raise ValueError("Retention period must be at least 6 years.")
        return v


@app.get(ENDPOINT_PREFIX + "/driveinfo", response_model=DriveInfoResponse)
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
    # TODO: Replace mock with projectdb.get_research_drive_by_name() when available pylint: disable=fixme
    drive_data = {
        "allocated_gb": 4000.0,
        "archived": 0,
        "date": "2026-03-09",
        "deleted": 0,
        "free_gb": 4000.0,
        "id": 6904394,
        "name": drive_name,
        "num_files": 4,
        "percentage_used": 0.0,
        "used_gb": 0.0,
    }

    if not drive_data:
        raise HTTPException(
            status_code=404,
            detail=f"Research Drive {drive_name} not found in ProjectDB.",
        )

    # Resolve project from drive
    try:
        drive_projects = projectdb.get_research_drive_projects(
            drive_data["id"], expand=["project"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch projects for drive {drive_name}: {str(e)}",
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
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch project {project_id}: {str(e)}",
        ) from e

    # Fetch members
    try:
        members_raw = projectdb.get_project_members(
            project_id,
            expand=["person", "role", "person.identities", "person.status"],
        )
        members_raw = filter_member_identities(members_raw)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch members for project {project_id}: {str(e)}",
        ) from e

    # Build drive response, preferring service-level data (has first_day/last_day)
    drive_service = None
    for rd in project_data.get("services", {}).get("research_drive", []):
        if rd.get("name") == drive_name:
            drive_service = rd
            break

    drive_resp = DriveResponse(
        id=drive_data.get("id"),
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


@app.post(ENDPOINT_PREFIX + "/submission", status_code=status.HTTP_201_CREATED)
async def create_submission(
    request: CreateSubmissionRequest,
    session: SessionDep,
    background_tasks: BackgroundTasks,
    projectdb: ProjectDbDep,
    api_key: ApiKey = Security(validate_api_key),
) -> dict[str, str]:
    """Create a new archive submission for a research drive.

    Validates drive exists in ProjectDB, resolves project_id if needed,
    and schedules RO-Crate generation as a background task.
    """
    validate_permissions("POST", api_key)

    # Fetch drive info from ProjectDB to validate it exists
    try:
        # pylint: disable=fixme
        # TODO: Using mock data for now
        # ProjectDB API is currently being updated to add get_research_drive_by_name() method
        # Once available, this mock should be replaced with:
        #   drive = projectdb.get_research_drive_by_name(request.drive_name)
        drive = {
            "allocated_gb": 4000.0,
            "archived": 0,
            "date": "2026-03-09",
            "deleted": 0,
            "free_gb": 4000.0,
            "id": 6904394,
            "name": request.drive_name,
            "num_files": 4,
            "percentage_used": 0.0,
            "used_gb": 0.0,
        }

        if not drive:
            raise HTTPException(
                status_code=404,
                detail=f"Research Drive {request.drive_name} not found in ProjectDB.",
            )

        # Resolve project_id if not provided
        project_id = None
        try:
            # Find associated project
            drive_projects = projectdb.get_research_drive_projects(
                drive["id"], expand=["project"]
            )
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail=f"Could not fetch projects for drive {request.drive_name}: {str(e)}",
            ) from e

        if not drive_projects or len(drive_projects) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No projects associated with drive {request.drive_name}",
            )
        if len(drive_projects) > 1:
            # Choose correct project based on request parameter if provided,
            # otherwise raise error to disambiguate
            if request.project_id:
                for dp in drive_projects:
                    if dp["project"]["id"] == request.project_id:
                        project_id = request.project_id
                        break
            else:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Multiple projects associated with drive {request.drive_name}."
                        "Please provide project_id to disambiguate.",
                    ),
                )

        else:
            project_id = drive_projects[0]["project"]["id"]

        if project_id is None:
            raise HTTPException(
                status_code=400,
                detail="Could not determine project_id for archive",
            )

        # Create archive submission record
        archive_date = datetime.now()
        archive_location = str(Path.home() / "mnt" / request.drive_name / "Archive")

        submission = ArchiveSubmission(
            drive_id=drive["id"],
            project_id=project_id,
            drive_name=request.drive_name,
            retention_period_years=request.retention_period_years,
            retention_period_justification=request.retention_period_justification,
            data_classification=request.data_classification,
            archive_date=archive_date,
            archive_location=archive_location,
            is_completed=False,
        )

        session.add(submission)
        session.commit()
        # we need the submission id to pass to the background task,
        # so we refresh to get the generated id
        session.refresh(submission)
        if submission.id is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to create archive submission record.",
            )

        # Schedule async RO-Crate generation
        print(
            f"Scheduling background task to generate RO-Crate for drive {request.drive_name}"
        )
        background_tasks.add_task(
            generate_ro_crate_async,
            drive,
            submission.id,
            projectdb_client=projectdb,
        )

        return {
            "message": (
                f"Archive submission created for {request.drive_name}."
                " RO-Crate generation is in progress."
            )
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while creating archive submission for {request.drive_name}.",
        ) from e


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

    print(f"Writing RO-Crate to {ro_crate_location}")
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


async def generate_ro_crate_async(
    drive: dict[str, Any],
    submission_id: int,
    projectdb_client: ProjectDBApi,
) -> None:
    """Async background task for generating RO-Crate and updating archive record.

    Fetches live project data from ProjectDB, generates crate, and updates
    the ArchiveSubmission record with completion status and manifest.

    Args:
    drive: Dictionary containing research drive information
    submission_id: ID of the ArchiveSubmission record
    projectdb_client: Client for interacting with ProjectDB
    """
    drive_name = drive.get("name", None)
    if drive_name is None:
        print("Drive name is missing from drive data. Cannot generate RO-Crate.")
        return

    # Create a new session for this background task
    with Session(engine) as session:
        try:
            submission = session.get(ArchiveSubmission, submission_id)
            if submission is None:
                print(f"ArchiveSubmission with id {submission_id} not found.")
                return

            # Fetch project and member data from ProjectDB
            project_id = submission.project_id
            print(f"Fetching project data from ProjectDB for project {project_id}...")
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

            print(f"Building RO-Crate for {drive_name}...")
            build_crate_contents_async(
                drive=drive,
                submission=submission,
                members_list=members_list,
                project_data=project_data,
                drive_location=drive_location,
                output_location=output_location,
            )

            # Zip the generated crate
            zip_existing_crate(output_location / str(drive_name), drive_location)

            # Generate and store manifest
            manifest = generate_manifest(drive_location)
            session.add(manifest)
            session.commit()

            # Update archive submission with manifest and completion status
            submission.manifest_id = manifest.id
            submission.is_completed = True
            session.add(submission)
            session.commit()

            print(f"RO-Crate generation completed for {drive_name}")
        except Exception as e:
            print(f"Error generating RO-Crate for {drive_name}: {e}")
            raise


@app.get(ENDPOINT_PREFIX + "/submission")
async def get_submission(
    drive_name: ResearchDriveName,
    session: SessionDep,
    api_key: ApiKey = Security(validate_api_key),
) -> dict[str, Any]:
    """Retrieve archive submission record for a research drive."""
    validate_permissions("GET", api_key)

    stmt = select(ArchiveSubmission).where(ArchiveSubmission.drive_name == drive_name)
    submission = session.exec(stmt).first()

    if submission is None:
        raise HTTPException(
            status_code=404,
            detail=f"No archive submission found for drive {drive_name}",
        )

    # Return submission with full manifest if available
    result = {
        "id": submission.id,
        "drive_id": submission.drive_id,
        "project_id": submission.project_id,
        "drive_name": submission.drive_name,
        "retention_period_years": submission.retention_period_years,
        "retention_period_justification": submission.retention_period_justification,
        "data_classification": submission.data_classification,
        "archive_date": submission.archive_date,
        "archive_location": submission.archive_location,
        "is_completed": submission.is_completed,
        "created_timestamp": submission.created_timestamp,
        "manifest": submission.manifest.manifest if submission.manifest else None,
    }
    return result


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
    except Exception as e:  # pylint: disable=broad-exception-caught
        # Log error but don't fail the whole process - just return unfiltered members
        print(f"Error filtering member identities: {e}")
    return members
