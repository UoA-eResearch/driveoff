"""Definition of endpoints/routers for the webserver."""

import re
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated, AsyncGenerator, Iterable

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    Security,
    status,
)
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
from api.projectdb import get_projectdb_client, init_projectdb, ProjectDBApi
from api.security import ApiKey, validate_api_key, validate_permissions
from crate.ro_builder import ROBuilder
from crate.ro_loader import ROLoader, zip_existing_crate
from models.common import DataClassification
from models.manifest import Manifest
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
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifecycle method for the API

    This creates DB tables and initialises the ProjectDB client during
    application startup so routes can depend on it.
    """
    create_db_and_tables()
    # initialise ProjectDB client for use in endpoints
    try:
        init_projectdb(app)
    except Exception:
        # If the ProjectDB client cannot be initialised, allow app to start
        # but the dependency will raise if used.
        pass
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


class CreateSubmissionRequest(SQLModel):
    """Request body for creating an archive submission."""

    drive_name: ResearchDriveName
    retention_period_years: int
    retention_period_justification: str | None = None
    data_classification: DataClassification = DataClassification.SENSITIVE
    project_id: int | None = None


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
        if request.project_id is None:
            try:
                # Find associated project
                drive_projects = projectdb.get_research_drive_projects(
                    drive["id"], expand=["project"]
                )
            except Exception as e:
                raise HTTPException(
                    status_code=404,
                    detail=f"Could not fetch projects for drive {request.drive_name}: {str(e)}",
                )

            if not drive_projects or len(drive_projects) == 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"No projects associated with drive {request.drive_name}",
                )
            if len(drive_projects) > 1:
                raise HTTPException(
                    status_code=400,
                    detail=f"Multiple projects associated with drive {request.drive_name}. Please provide project_id to disambiguate.",
                )
            project_id = drive_projects[0]["project"]["id"]
        else:
            project_id = request.project_id

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

        # Schedule async RO-Crate generation
        print(
            f"Scheduling background task to generate RO-Crate for drive {request.drive_name}"
        )
        background_tasks.add_task(
            generate_ro_crate_async,
            drive_name=request.drive_name,
            project_id=project_id,
            projectdb_client=projectdb,
        )

        return {
            "message": f"Archive submission created for {request.drive_name}. RO-Crate generation is in progress."
        }
    except HTTPException:
        raise


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


def build_crate_contents_async(
    drive_name: str,
    project_id: int,
    members_list: list,
    project_data: dict,
    archive_metadata: dict,
    drive_location: Path,
    output_location: Path,
) -> None:
    """Generate RO-Crate with data from ProjectDB."""
    # Build RO-Crate
    ro_crate_loader = ROLoader()
    ro_crate_loader.init_crate()
    ro_crate_builder = ROBuilder(ro_crate_loader.crate)

    # Add project to crate with archive metadata
    project_entity = ro_crate_builder.add_project(
        project_data,
        members_list,
        archive_metadata,
    )

    # Add drive service as main entity
    drive_entity = ro_crate_builder.add_research_drive_service(drive_name)

    ro_crate_builder.crate.root_dataset.append_to("mainEntity", drive_entity)
    drive_entity.append_to("project", [project_entity])

    ro_crate_location = drive_location
    if bagit_exists(ro_crate_location):
        ro_crate_location = ro_crate_location / "data"

    print(f"Writing RO-Crate to {ro_crate_location}")
    ro_crate_loader.write_crate(ro_crate_location)
    bag_directory(
        drive_location,
        bag_info={"project_id": str(project_id)},
    )
    create_manifests_directory(
        drive_path=drive_location,
        output_location=output_location,
        drive_name=str(drive_name),
    )


async def generate_ro_crate_async(
    drive_name: str,
    project_id: int,
    projectdb_client: ProjectDBApi,
) -> None:
    """Async background task for generating RO-Crate and updating archive record.

    Fetches live project data from ProjectDB, generates crate, and updates
    the ArchiveSubmission record with completion status and manifest.
    """
    # Create a new session for this background task
    with Session(engine) as session:
        try:
            # Get archive submission to get metadata
            stmt = select(ArchiveSubmission).where(
                ArchiveSubmission.drive_name == drive_name
            )
            submission = session.exec(stmt).first()
            if not submission:
                raise ValueError(f"No archive submission found for {drive_name}")

            # Fetch project and member data from ProjectDB
            print(f"Fetching project data from ProjectDB for project {project_id}...")
            project_data = projectdb_client.get_project(
                pid=project_id,
                expand=["codes", "status", "services", "properties"],
            )
            members_list = projectdb_client.get_project_members(
                project_id,
                expand=["person", "role"],
            )

            # Build archive metadata dict
            archive_metadata = {
                "drive_name": drive_name,
                "retention_period_years": submission.retention_period_years,
                "retention_period_justification": submission.retention_period_justification,
                "data_classification": (
                    submission.data_classification.value
                    if hasattr(submission.data_classification, "value")
                    else str(submission.data_classification)
                ),
                "archive_date": submission.archive_date,
            }

            # Generate RO-Crate
            drive_path = get_resdrive_path(drive_name)
            drive_location = drive_path / "Vault"
            output_location = drive_path / "Archive"

            print(f"Building RO-Crate for {drive_name}...")
            build_crate_contents_async(
                drive_name=drive_name,
                project_id=project_id,
                members_list=members_list,
                project_data=project_data,
                archive_metadata=archive_metadata,
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
) -> dict:
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
