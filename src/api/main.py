"""Definition of endpoints/routers for the webserver."""

import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, AsyncGenerator, Iterable

from fastapi import Depends, FastAPI, HTTPException, Security
from pydantic.functional_validators import AfterValidator
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from api.manifests import generate_manifest
from api.security import ApiKey, validate_api_key, validate_permissions
from models.member import Member
from models.person import Person
from models.project import InputProject, Project
from models.role import prepopulate_roles
from models.services import ResearchDriveService

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


@app.put(ENDPOINT_PREFIX + "/resdriveinfo")
async def append_drive_info(
    drive_id: ResearchDriveID,
    ro_crate_metadata: dict[str, str],
    api_key: ApiKey = Security(validate_api_key),
) -> dict[str, str]:
    """Submit additional RO-Crate metadata. NOTE: this may need to accept manifest deltas too."""

    validate_permissions("PUT", api_key)

    _ = ro_crate_metadata
    return {
        "message": f"Received additional RO-Crate metadata for {drive_id}.",
    }


@app.get(ENDPOINT_PREFIX + "/resdriveinfo")
async def get_drive_info(
    drive_id: ResearchDriveID,
    session: SessionDep,
    api_key: ApiKey = Security(validate_api_key),
) -> dict[str, str]:
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

    return {
        "drive_id": drive_id,
        "ro_crate": "TODO: Make RO-Crate from: " + str(projects),
    }


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

    return {
        "manifest": manifest,
    }
