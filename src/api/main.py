"""Definition of endpoints/routers for the webserver."""

import json
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
from api.fake_resdrive import make_fake_resdrive
from api.manifests import (
    bag_directory,
    bagit_exists,
    create_manifests_directory,
    generate_manifest,
)
from api.projectdb import get_projectdb_client, init_projectdb, ProjectDBApi
from api.security import ApiKey, validate_api_key, validate_permissions
from ceradmin_cli.utils import get_dict_properties
from crate.ro_builder import ROBuilder
from crate.ro_loader import ROLoader, zip_existing_crate
from models.member import Member
from models.person import Person
from models.project import InputProject, Project, ProjectWithDriveMember, Code
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


@app.post(ENDPOINT_PREFIX + "/resdriveinfo")
async def set_drive_info(
    input_project: InputProject,
    session: SessionDep,
    api_key: ApiKey = Security(validate_api_key),
) -> Project:
    """Submit initial RO-Crate metadata. NOTE: this may also need to accept the manifest data."""
    validate_permissions("POST", api_key)
    project = transform_project_data(input_project)
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

    print(f"Scheduling background task to generate RO-Crate for drive {drive.name}")
    background_tasks.add_task(
        generate_ro_crate,
        drive_name=drive.name,
        session=session,
    )

    return {
        "message": f"RO-Crate generation is in progress for {drive.name}.",
    }


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
    drive_name: ResearchDriveName,
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
    ro_crate_location = drive_location
    if bagit_exists(ro_crate_location):
        ro_crate_location = ro_crate_location / "data"
    print(f"Writing RO-Crate to {ro_crate_location}")
    ro_crate_loader.write_crate(ro_crate_location)
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
    drive_name: ResearchDriveName,
    session: SessionDep,
) -> None:
    """Async task for generating the RO-crate in a research drive
    then moving all files into archive"""
    drive_path = get_resdrive_path(drive_name)
    drive_location = drive_path / "Vault"
    output_location = drive_path / "Archive"
    print(f"Generating RO-Crate contents...")
    build_crate_contents(
        drive_name,
        session,
        drive_location=drive_path / "Vault",
        output_location=drive_path / "Archive",
    )
    zip_existing_crate(output_location / str(drive_name), drive_location)


@app.get(ENDPOINT_PREFIX + "/resdriveinfo", response_model=ProjectWithDriveMember)
async def get_drive_info(
    drive_name: ResearchDriveName,
    session: SessionDep,
    api_key: ApiKey = Security(validate_api_key),
) -> Project:
    """Retrieve information about the specified Research Drive."""

    validate_permissions("GET", api_key)

    code_query = select(ResearchDriveService).where(
        ResearchDriveService.name == drive_name
    )
    drive_found = session.exec(code_query).first()

    if drive_found is None:
        raise HTTPException(
            status_code=404,
            detail=f"Research Drive {drive_name} not found in local database.",
        )

    projects = drive_found.projects
    if len(projects) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No Projects associated with {drive_name} in local database",
        )

    return projects[0]


@app.get(ENDPOINT_PREFIX + "/resdrivemanifest")
async def get_drive_manifest(
    drive_name: ResearchDriveName,
    session: SessionDep,
    api_key: ApiKey = Security(validate_api_key),
) -> dict[str, str]:
    """Retrieve a manifest from a research drive that has been loaded into the backend"""
    validate_permissions("GET", api_key)
    code_query = select(ResearchDriveService).where(
        ResearchDriveService.name == drive_name
    )
    drive_found = session.exec(code_query).first()

    if drive_found is None:
        raise HTTPException(
            status_code=404,
            detail=f"Research Drive {drive_name} not found in local database.",
        )
    manifest = drive_found.manifest.manifest

    if manifest is None:
        raise HTTPException(
            status_code=404,
            detail=f"Manifest not available for {drive_name}",
        )

    return {"manifest": manifest}


@app.get(ENDPOINT_PREFIX + "/initiate-offboard")
async def initiate_offboard(
    drive_name: ResearchDriveName,
    session: SessionDep,
    projectdb: ProjectDbDep,
    api_key: ApiKey = Security(validate_api_key),
    project_id: int | None = None,
) -> dict[str, str]:
    """Endpoint to initialise the data required for offboarding a research drive.
    Drive, project and member data will be prepared and stored in the offboarding database
    based on the drive name. This should be called before triggering the RO-Crate generation
    to ensure all necessary metadata is available for the RO-Crate.

    Args:
        drive_name (str): the name of the research drive to offboard, e.g. "ressci202300019-testresearchdrive"
        project_id (int, optional): the ID of the project to offboard. This is optional as the project can be identified based on the drive name, but can be included to disambiguate if there are multiple projects associated with a drive.
    """
    validate_permissions("POST", api_key)

    # Get the drive info from the ProjectDB based on the drive name.
    # This is to confirm the drive exists and get any relevant info needed for offboarding.
    # drive = projectdb.get_drive_by_name(drive_name) TODO: this method doesnt exist yet - waiting on pr to merge

    # mock a drive for now
    drive = [
        {
            "allocated_gb": 4000.0,
            "archived": 0,
            "date": "2026-03-09",
            "deleted": 0,
            "free_gb": 4000.0,
            "id": 6904394,
            "name": "ressci202300019-testresearchdrive",
            "num_files": 4,
            "percentage_used": 0.0,
            "used_gb": 0.0,
        }
    ]

    if drive is None or len(drive) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Research Drive {drive_name} not found in ProjectDB.",
        )
    drive = drive[0]

    if project_id is None:
        # Find associated project
        drive_project = projectdb.get_research_drive_projects(
            drive["id"], expand=["project"]
        )
        if drive_project is None or len(drive_project) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No project associated with Research Drive {drive_name} found in ProjectDB.",
            )
        if len(drive_project) > 1:
            raise HTTPException(
                status_code=400,
                detail=f"Multiple projects associated with Research Drive {drive_name} found in ProjectDB. Please provide project_id as a query parameter to disambiguate.",
            )

        # Get project id
        project_id = drive_project[0]["project"]["id"]

    if project_id is None:
        raise HTTPException(
            status_code=404,
            detail=f"Project ID for Research Drive {drive_name} could not be identified. Please provide project_id as a query parameter to disambiguate.",
        )

    # Get associated project from project id
    raw_project = get_project_data(pid=project_id, projectdb=projectdb)

    # Get associated members and attach to the raw project dict
    raw_project["members"] = fetch_member_data(pid=project_id, projectdb=projectdb)

    # Validate & normalize at the model boundary so downstream code works
    input_project = InputProject.model_validate(raw_project)

    # Transform to internal Project model
    project = transform_project_data(input_project, drive_name=drive_name)

    # Upsert the project to the database for use in the RO-Crate generation and manifest creation steps.
    session.merge(project)
    session.commit()

    return {
        "message": f"Offboarding data initiated for {drive_name}. You may now proceed to trigger the archiving process."
    }


def get_project_data(pid: int, projectdb: ProjectDbDep) -> dict:
    """Retrieve project data"""
    project = projectdb.get_project(
        pid=pid,
        expand=["codes", "status", "services", "properties", "external_references"],
    )
    columns = [
        "id",
        "title",
        "description",
        "division",
        "codes",
        "status",
        "start_date",
        "end_date",
        "next_review_date",
        "last_modified",
        "requirements",
        "services",
        "members",
        "properties",
        "external_references",
    ]
    project_data = get_dict_properties(project, columns, formatters=None)
    return dict(zip(columns, project_data))


def fetch_member_data(pid: int, projectdb: ProjectDbDep) -> list:
    """Retrieve project member data"""
    members = projectdb.get_project_members(
        pid,
        expand=["person", "role", "division", "person.identities", "person.status"],
    )
    columns = [
        "id",
        "person.email",
        "person.full_name",
        "person.identities",
        "person.status",
        "role",
        "notes",
    ]
    return [
        dict(zip(columns, get_dict_properties(member, columns, formatters=None)))
        for member in members
    ]


def transform_project_data(input_project: InputProject, drive_name: str) -> Project:
    """Transform a validated `InputProject` into a `Project` suitable for DB upsert."""
    project = Project(
        id=input_project.id,
        title=input_project.title,
        description=input_project.description,
        division=input_project.division,
        start_date=input_project.start_date or datetime.now(),
        end_date=input_project.end_date or datetime.now(),
    )

    # Ensure codes are Code model instances
    codes_list: list[Code] = []
    for c in input_project.codes or []:
        if isinstance(c, Code):
            codes_list.append(c)
        elif isinstance(c, dict):
            codes_list.append(Code(id=c.get("id"), code=c.get("code")))
    project.codes = codes_list

    # Members: InputPerson -> Person + Member
    members: list[Member] = []
    for im in input_project.members or []:
        # identities items may be InputIdentity objects or dicts
        username = ""
        ids = getattr(im, "identities", None)
        if ids:
            items = getattr(ids, "items", []) or []
            if len(items) > 0:
                it = items[0]
                username = (
                    getattr(it, "username", None)
                    if not isinstance(it, dict)
                    else it.get("username")
                )
                username = username or ""

        person = Person(
            id=getattr(im, "id", None),
            email=getattr(im, "email", None),
            full_name=getattr(im, "full_name", ""),
            username=username,
        )
        role_obj = getattr(im, "role", None)
        role_id = getattr(role_obj, "id", None) if role_obj is not None else None
        member = Member(project=project, person=person, role_id=role_id)
        members.append(member)
    project.members = members

    # Research drives: extract from services and filter to the requested drive
    drives = []
    services = getattr(input_project, "services", None)
    research_list = []
    if services is not None:
        research_list = getattr(services, "research_drive", []) or []

    from datetime import datetime as _dt

    def _coerce_date(value):
        if value is None:
            return None
        if isinstance(value, _dt):
            return value
        if isinstance(value, str):
            try:
                return _dt.fromisoformat(value)
            except Exception:
                for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                    try:
                        return _dt.strptime(value, fmt)
                    except Exception:
                        continue
        return value

    for d in research_list:
        name = getattr(d, "name", None) if not isinstance(d, dict) else d.get("name")
        if name != drive_name:
            continue

        if isinstance(d, ResearchDriveService):
            drive_obj = d
        else:
            # coerce date-like fields on the raw dict before model validation
            raw = dict(d)
            for date_field in ("date", "first_day", "last_day"):
                if date_field in raw:
                    raw[date_field] = _coerce_date(raw[date_field])
            drive_obj = ResearchDriveService.model_validate(raw)

        # defensive: if model has string dates, coerce them to datetime
        try:
            if isinstance(getattr(drive_obj, "date", None), str):
                drive_obj.date = _coerce_date(drive_obj.date)
        except Exception:
            pass
        try:
            if isinstance(getattr(drive_obj, "first_day", None), str):
                drive_obj.first_day = _coerce_date(drive_obj.first_day)
        except Exception:
            pass
        try:
            if isinstance(getattr(drive_obj, "last_day", None), str):
                drive_obj.last_day = _coerce_date(drive_obj.last_day)
        except Exception:
            pass

        drives.append(drive_obj)

    project.research_drives = drives
    for drive in drives:
        drive_path = get_resdrive_path(drive.name)
        drive.manifest = generate_manifest(drive_path / "Vault")

    return project
