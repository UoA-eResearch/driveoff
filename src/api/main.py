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
    Response,
    Security,
    status,
)
from pydantic.functional_validators import AfterValidator
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from api.cors import add_cors_middleware
from api.manifests import bag_directory, create_manifests_directory, generate_manifest
from api.security import ApiKey, validate_api_key, validate_permissions
from crate.ro_builder import ROBuilder
from crate.ro_loader import ROLoader, zip_existing_crate
from models.member import Member
from models.person import Person
from models.project import InputProject, Project, ProjectWithDriveMember
from models.role import prepopulate_roles
from models.services import ResearchDriveService
from models.submission import DriveOffboardSubmission, InputDriveOffboardSubmission

# Ensure driveoff directory is created
(Path.home() / ".driveoff").mkdir(exist_ok=True)
DB_FILE_NAME = Path.home() / ".driveoff" / "database.db"
DB_URL = f"sqlite:///{DB_FILE_NAME}"

connect_args = {"check_same_thread": False}
engine = create_engine(DB_URL, connect_args=connect_args, echo=True)


def create_db_and_tables() -> None:
    """Create database structure and pre-populate with fixtures."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        roles = prepopulate_roles()
        session.add_all(roles)
        try:
            session.commit()
        except IntegrityError:
            pass  # Roles already inserted, skip.


def get_session() -> Iterable[Session]:
    """Return a Session object."""
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Lifecycle method for the API"""
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)

# Send CORS headers to enable frontend to contact API.
add_cors_middleware(app)

RESEARCH_DRIVE_REGEX = re.compile(r"res[a-z]{3}[0-9]{9}-[a-zA-Z0-9-_]+")

ENDPOINT_PREFIX = "/api/v1"


def validate_resdrive_identifier(drive_id: str) -> str:
    """Check if the string is a valid Research Drive identifier."""
    if RESEARCH_DRIVE_REGEX.match(drive_id) is None:
        raise ValueError(f"'{drive_id}' is not a valid Research Drive identifier.")

    return drive_id


ResearchDriveID = Annotated[str, AfterValidator(validate_resdrive_identifier)]


@app.post(ENDPOINT_PREFIX + "/resdriveinfo")
async def set_drive_info(
    input_project: InputProject,
    session: SessionDep,
    api_key: ApiKey = Security(validate_api_key),
) -> Project:
    """Submit initial RO-Crate metadata. NOTE: this may also need to accept the manifest data."""
    validate_permissions("POST", api_key)
    project = Project(
        id=input_project.id,
        title=input_project.title,
        description=input_project.description,
        division=input_project.division,
        start_date=input_project.start_date,
        end_date=input_project.end_date,
        codes=input_project.codes,
    )
    # Break up role and person information.
    members: list[Member] = []
    for input_member in input_project.members:
        person = Person(
            id=input_member.id,
            email=input_member.email,
            full_name=input_member.full_name,
            username=input_member.identities.items[0].username,
        )
        member = Member(project=project, person=person, role_id=input_member.role.id)
        members.append(member)
    # Add the drive info into services.
    drives = [
        ResearchDriveService.model_validate(drive)
        for drive in input_project.services.research_drive
    ]
    project.research_drives = drives
    for drive in drives:
        drive.manifest = generate_manifest(drive.name)
    # Add the validated services and members into the project
    project.members = members
    # Upsert the project.
    session.merge(project)
    session.commit()
    return project


@app.post(ENDPOINT_PREFIX + "/submission", status_code=status.HTTP_201_CREATED)
async def append_drive_info(
    input_submission: InputDriveOffboardSubmission,
    session: SessionDep,
    response: Response,
    background_tasks: BackgroundTasks,
    api_key: ApiKey = Security(validate_api_key),
) -> dict[str, str]:
    """Handle requests to create new form submission."""
    validate_permissions("PUT", api_key)

    # Find the related drive and project
    find_drive_stmt = select(ResearchDriveService).where(
        ResearchDriveService.name == input_submission.drive_name
    )
    result = session.exec(find_drive_stmt)
    drive = result.first()
    if drive is None:
        # If there isn't a drive associated, return error.
        response.status_code = status.HTTP_404_NOT_FOUND
        return {"message": "Could not find drive with drive_name."}
    if drive.submission is not None:
        # Reject request to POST if there is already a post submission.
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "Drive already has a submission."}
    if len(drive.projects) == 0:
        # Unlikely to happen, but handle if the drive does not have a project associated.
        response.status_code = status.HTTP_404_NOT_FOUND
        return {"message": "Drive does not have a project associated."}
    related_project = drive.projects[0]
    is_project_updated = False
    if input_submission.project_changes is not None:
        # Apply changes from input to project, if any.
        is_project_updated = input_submission.project_changes.apply_changes(
            related_project
        )
    submission = DriveOffboardSubmission(
        data_classification=input_submission.data_classification,
        retention_period_years=input_submission.retention_period_years,
        retention_period_justification=input_submission.retention_period_justification,
        is_completed=input_submission.is_completed,
        drive_id=drive.id,
        is_project_updated=is_project_updated,
        updated_time=datetime.now(),
    )
    session.add(related_project)
    session.add(submission)
    session.commit()

    # generate the RO-Crate now that db has been updated
    # for now assume "Real" research drive has been mounted somewhere on VM home directory

    background_tasks.add_task(
        generate_ro_crate,
        drive_name=drive.name,
        session=session,
    )

    return {
        "message": f"Received additional RO-Crate metadata for {drive.name}.",
    }


def make_fake_resdrive(drive_path: Path) -> None:
    "TESTING/DEMONSTRATION FUNCTION TO POPULATE RESEARCH DRIVE PATHS"
    (drive_path / "Vault").mkdir(parents=True, exist_ok=True)
    (drive_path / "Archive").mkdir(parents=True, exist_ok=True)


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


def build_crate_contents(
    drive_name: ResearchDriveID,
    session: SessionDep,
    drive_location: Path,
    output_location: Path,
) -> ROLoader:
    """Generate an RO-Crate from a list of projects"""

    code_query = select(ResearchDriveService).where(
        ResearchDriveService.name == str(drive_name)
    )
    drive_found = session.exec(code_query).one()

    if drive_found is None:
        raise ValueError(
            f"Research Drive ID {drive_name} no longer found in local database."
        )

    projects = drive_found.projects

    if not drive_found.submission:
        raise ValueError(
            f"Research Drive ID {drive_name} does not have a valid form submission"
        )

    drive_submission = drive_found.submission

    if len(projects) == 0:
        raise ValueError(f"No projects linked with drive {drive_name}")

    ro_crate_loader = ROLoader()
    ro_crate_loader.init_crate()
    ro_crate_builder = ROBuilder(ro_crate_loader.crate)
    project_entities = [
        ro_crate_builder.add_project(project, drive_submission) for project in projects
    ]
    drive_entity = ro_crate_builder.add_research_drive_service(drive_found)
    ro_crate_builder.crate.root_dataset.append_to("mainEntity", drive_entity)
    drive_entity.append_to("project", project_entities)
    ro_crate_loader.write_crate(drive_location)
    bag_directory(
        drive_location,
        bag_info={"projects": ",".join([project.title for project in projects])},
    )
    create_manifests_directory(
        drive_path=drive_location,
        output_location=output_location,
        drive_name=str(drive_name),
    )

    return ro_crate_loader


async def generate_ro_crate(
    drive_name: ResearchDriveID,
    session: SessionDep,
) -> None:
    """Async task for generating the RO-crate in a research drive
    then moving all files into archive"""
    drive_path = get_resdrive_path(drive_name)
    drive_location = drive_path / "Vault"
    output_location = drive_path / "Archive"
    build_crate_contents(
        drive_name,
        session,
        drive_location=drive_path / "Vault",
        output_location=drive_path / "Archive",
    )
    zip_existing_crate(output_location / str(drive_name), drive_location)


@app.get(ENDPOINT_PREFIX + "/resdriveinfo", response_model=ProjectWithDriveMember)
async def get_drive_info(
    drive_id: ResearchDriveID,
    session: SessionDep,
    api_key: ApiKey = Security(validate_api_key),
) -> Project:
    """Retrieve information about the specified Research Drive."""

    validate_permissions("GET", api_key)

    code_query = select(ResearchDriveService).where(
        ResearchDriveService.name == drive_id
    )
    drive_found = session.exec(code_query).first()

    if drive_found is None:
        raise HTTPException(
            status_code=404,
            detail=f"Research Drive ID {drive_id} not found in local database.",
        )

    projects = drive_found.projects
    if len(projects) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No Projects associated with {drive_id} in local database",
        )

    return projects[0]


@app.get(ENDPOINT_PREFIX + "/resdrivemanifest")
async def get_drive_manifest(
    drive_id: ResearchDriveID,
    session: SessionDep,
    api_key: ApiKey = Security(validate_api_key),
) -> dict[str, str]:
    """Retrieve a manifest from a research drive that has been loaded into the backend"""
    validate_permissions("GET", api_key)
    code_query = select(ResearchDriveService).where(
        ResearchDriveService.name == drive_id
    )
    drive_found = session.exec(code_query).first()

    if drive_found is None:
        raise HTTPException(
            status_code=404,
            detail=f"Research Drive ID {drive_id} not found in local database.",
        )
    manifest = drive_found.manifest.manifest

    if manifest is None:
        raise HTTPException(
            status_code=404,
            detail=f"Manifest not available for {drive_id}",
        )

    return {"manifest": manifest}
