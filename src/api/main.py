"""Definition of endpoints/routers for the webserver."""

import re
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Security
from pydantic.functional_validators import AfterValidator
from sqlmodel import Session, SQLModel, create_engine

from api.security import ApiKey, validate_api_key, validate_permissions
from models.project import Project

db_file_name = "database.db"
db_url = f"sqlite:///{db_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(db_url, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    project_archive: Project,
    # session: SessionDep,
    api_key: ApiKey = Security(validate_api_key),
) -> Project:
    """Submit initial RO-Crate metadata. NOTE: this may also need to accept the manifest data."""
    validate_permissions("POST", api_key)
    # session.add(project_archive)
    # session.commit()
    # session.refresh(project_archive)
    return project_archive


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
