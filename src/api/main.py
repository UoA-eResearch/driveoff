"""Definition of endpoints/routers for the webserver."""

import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Security
from pydantic.functional_validators import AfterValidator
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from api.security import ApiKey, validate_api_key, validate_permissions
from models.member import Member
from models.person import Person
from models.project import InputProject, Project
from models.role import Role, prepopulate_roles
from models.services import ResearchDriveService, Services

DB_FILE_NAME = Path.home() / ".driveoff" / "database.db"
db_url = f"sqlite:///{DB_FILE_NAME}"

connect_args = {"check_same_thread": False}
engine = create_engine(db_url, connect_args=connect_args, echo=True)


def create_db_and_tables():
    """Create database structure and pre-populate with fixtures."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        roles = prepopulate_roles()
        session.add_all(roles)
        try:
            session.commit()
        except IntegrityError:
            pass  # Roles already inserted, skip.


def get_session():
    """Return a Session object."""
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(_):
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


@app.post(ENDPOINT_PREFIX + "/resdriveinfo", response_model=Project)
async def set_drive_info(
    project: InputProject,
    session: SessionDep,
    api_key: ApiKey = Security(validate_api_key),
) -> Project:
    """Submit initial RO-Crate metadata. NOTE: this may also need to accept the manifest data."""
    validate_permissions("POST", api_key)
    stored_project = Project(
        id=project.id,
        title=project.title,
        description=project.description,
        division=project.division,
        start_date=project.start_date,
        end_date=project.end_date,
        codes=project.codes,
    )
    # Break up role and person information.
    stored_members: list[Member] = []
    for member in project.members:
        # logger.debug("Looking up role for member %s", member.full_name)
        role_stmt = select(Role).where(Role.id == member.role.id)
        result = session.exec(role_stmt)
        role = list(result)[0]

        person = Person(
            id=member.id,
            email=member.email,
            full_name=member.full_name,
            username=member.identities.items[0].username,
        )
        stored_member = Member(project=stored_project, person=person, role=role)
        stored_members.append(stored_member)
    # Add the drive info into services.
    drives = [
        ResearchDriveService.model_validate(drive)
        for drive in project.services.research_drive
    ]
    stored_services = Services(research_drive=drives)
    # Add the validated services and members into the project
    stored_project.services = stored_services
    stored_project.members = stored_members
    # Upsert the project.
    session.merge(stored_project)
    session.commit()
    return stored_project


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
    api_key: ApiKey = Security(validate_api_key),
) -> dict[str, str]:
    """Retrieve information about the specified Research Drive."""

    validate_permissions("GET", api_key)

    return {
        "drive_id": drive_id,
        "ro_crate": "TODO: Make RO-Crate",
        "manifest": "TODO: Make manifest",
    }
