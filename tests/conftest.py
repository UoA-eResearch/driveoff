# pylint: disable=missing-class-docstring,redefined-outer-name,too-few-public-methods,missing-module-docstring,missing-module-docstring
# factory meta classes don't need docstrings
import json
import random
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List

import factory
import orjson
import pytest
from factory.alchemy import SQLAlchemyModelFactory
from fastapi.testclient import TestClient
from rocrate.model import ContextEntity as RO_Entity
from rocrate.rocrate import ROCrate
from rocrate.utils import get_norm_value
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel
from sqlmodel.pool import StaticPool

from api.main import app, get_session
from api.security import ApiKey, read_api_keys
from crate.ro_builder import ROBuilder
from crate.ro_loader import PROFILE as ARCHIVE_PROFILE
from crate.ro_loader import ROLoader
from models.common import DataClassification
from models.member import Member
from models.person import Person
from models.project import Code, Project
from models.role import Role, prepopulate_roles
from models.services import ResearchDriveService
from models.submission import DriveOffboardSubmission

ROLES = prepopulate_roles()
THIS_DIR = Path(__file__).absolute().parent
TEST_DATA_NAME = "restst000000001-testing"
TEST_INPUT_NAME = "Vault"
TEST_OUTPUT_NAME = "Archive"


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, Any, Any]:
    "scoped session for each unit test"
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
        session.rollback()
        session.close()


@pytest.fixture(name="client")
def client_fixture(session: Session) -> TestClient:
    def get_session_override() -> Session:
        return session

    # Generate a random API key and use it for the tests.
    test_api_key: str = str(uuid.uuid4())

    def read_api_keys_override() -> ApiKey:
        return {
            test_api_key: ApiKey(value=test_api_key, actions=["GET", "PUT", "POST"])
        }

    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[read_api_keys] = read_api_keys_override
    client = TestClient(app, headers={"x-api-key": test_api_key})
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def tmpdir(tmpdir: str) -> Path:
    """converty temporary directory to path"""
    return Path(tmpdir)


@pytest.fixture
def data_dir(tmpdir: Path) -> Path:
    "temporary directory for input files"
    d = tmpdir / TEST_DATA_NAME / TEST_INPUT_NAME
    shutil.copytree(THIS_DIR / TEST_DATA_NAME, d)
    return d


@pytest.fixture
def archive_dir(tmpdir: Path) -> Path:
    "temporary directory for archived files"
    d = tmpdir / TEST_DATA_NAME / TEST_OUTPUT_NAME
    return d


def random_role() -> Role:
    "Choose a random role from the prepoulated roles"
    return random.choice(ROLES)


@pytest.fixture
def person_factory(session: Session) -> SQLAlchemyModelFactory:
    "fixture for person factories"

    class PersonFactory(SQLAlchemyModelFactory):
        """Factory for generating test person objects"""

        class Meta:
            model = Person
            sqlalchemy_session = session

        id: int = factory.sequence(lambda n: n)
        email = random.choice([factory.Faker("email"), None])
        full_name = factory.Faker("name")
        username = factory.Faker(
            "bothify", text="????###", letters="abcdefghijklmnopqrstuvwxyz"
        )

    return PersonFactory


@pytest.fixture
def drive_offboard_submission_factory(
    session: Session, research_drive_service_factory: SQLAlchemyModelFactory
) -> SQLAlchemyModelFactory:
    "fixture for DriveOffboardSubmission factories"

    class DriveOffboardSubmissionFactory(SQLAlchemyModelFactory):
        """factory for generating test submission objects"""

        class Meta:
            model = DriveOffboardSubmission
            sqlalchemy_session = session

        id: int = factory.sequence(lambda n: n)
        retention_period_years = random.choice(
            [6, 10, 20, 26, random.randrange(7, 100)]
        )
        retention_period_justification = random.choice(
            [factory.Faker("sentence"), None]
        )
        data_classification = random.choice(list(DataClassification))
        is_completed = True
        updated_time = factory.Faker("date_time")
        is_project_updated = False
        drive = factory.SubFactory(research_drive_service_factory)

    return DriveOffboardSubmissionFactory


@pytest.fixture
def research_drive_service_factory(session: Session) -> SQLAlchemyModelFactory:
    "fixture for research drive service factories"

    class ResearchDriveServiceFactory(SQLAlchemyModelFactory):
        """factory for generating test person objects"""

        class Meta:
            model = ResearchDriveService
            sqlalchemy_session = session

        id: int = factory.sequence(lambda n: n)

        date = factory.Faker("date_time")
        first_day = factory.Faker("date_time")
        free_gb = random.random() * random.randrange(1, 5000)
        used_gb = random.random() * random.randrange(1, 5000)
        allocated_gb = free_gb + used_gb
        percentage_used = used_gb / (allocated_gb)
        last_day = random.choice([factory.Faker("date_time"), None])
        name = factory.Faker(
            "bothify",
            text="res???#########-????????",
            letters="abcdefghijklmnopqrstuvwxyz",
        )
        # submission = factory.SubFactory(drive_offboard_submission_factory)

    return ResearchDriveServiceFactory


@pytest.fixture
def member_factory(
    session: Session, person_factory: SQLAlchemyModelFactory
) -> SQLAlchemyModelFactory:
    "fixture wrapping a member factory"

    class MemberFactory(SQLAlchemyModelFactory):
        """factory for generating test member objects"""

        class Meta:
            model = Member
            sqlalchemy_session = session

        role = random_role()
        project = None
        person = factory.SubFactory(person_factory)

    return MemberFactory


@pytest.fixture
def code_factory(session: Session) -> SQLAlchemyModelFactory:
    "fixture for Code Factories"

    class CodeFactory(SQLAlchemyModelFactory):
        """factory for generating test code objects"""

        class Meta:
            model = Code
            sqlalchemy_session = session

        code = factory.Faker("bothify", text="????????#####")

    return CodeFactory


@pytest.fixture
def project_factory(
    session: Session,
    member_factory: SQLAlchemyModelFactory,
    code_factory: SQLAlchemyModelFactory,
    research_drive_service_factory: SQLAlchemyModelFactory,
) -> SQLAlchemyModelFactory:
    "fixture for project Factories"

    class ProjectFactory(SQLAlchemyModelFactory):
        """factory for generating test project objects"""

        class Meta:
            model = Project
            sqlalchemy_session = session

        id: int = factory.sequence(lambda n: n)
        title = factory.Faker("sentence")
        description = factory.Faker("paragraph")
        division = factory.Faker("company")
        start_date = factory.Faker("date_time")
        end_date = factory.Faker("date_time")
        members = factory.List(
            [factory.SubFactory(member_factory) for _ in range(random.randrange(0, 10))]
        )
        codes = factory.List(
            [factory.SubFactory(code_factory) for _ in range(random.randrange(0, 5))]
        )
        research_drives = factory.List(
            [factory.SubFactory(research_drive_service_factory)]
        )

    return ProjectFactory


@pytest.fixture
def project() -> Project:
    drive = ResearchDriveService(
        allocated_gb=25600,
        free_gb=24004.5,
        used_gb=1596,
        date=datetime(2024, 10, 13),
        first_day=datetime(2022, 1, 9),
        last_day=None,
        name="restst000000001-testing",
        percentage_used=2.75578,
        id=None,
    )
    people = [
        Person(
            email="s.nicolas@test.auckland.ac.nz",
            full_name="Samina Nicholas",
            username="snic021",
            id=1421,
        ),
        Person(
            username="jhos225",
            full_name="Jarrod Hossam",
            email="j.hossam@test.auckland.ac.nz",
            id=188,
        ),
        Person(
            username="medr894",
            email="m.edric@test.auckland.ac.nz",
            full_name="Melisa Edric",
            id=44,
        ),
    ]
    project = Project(
        codes=[Code(code="uoa00001", id=550), Code(code="reslig202200001", id=630)],
        title="Tītoki metabolomics",
        description="""
        Stress in plants could be defined as any change in
        growth condition(s) that disrupts metabolic homeostasis
        and requires an adjustment of metabolic pathways in a
        process that is usually referred to as acclimation.
        Metabolomics could contribute significantly to the study of stress
        biology in plants and other organisms by identifying different
         compounds, such as by-products of stress metabolism,
         stress signal transduction molecules or molecules that
         are part of the acclimation response of plants.
         """,
        division="Liggins Institute",
        start_date=datetime(2022, 1, 1),
        end_date=datetime(2024, 11, 4),
    )
    members = [
        Member(person=people[0], role_id=3),
        Member(person=people[1], role_id=3),
        Member(person=people[2], role_id=1),
    ]
    project.members = members
    project.research_drives = [drive]
    return project


@pytest.fixture()
def test_ro_loader() -> ROLoader:
    "RO-loader fixture"
    return ROLoader()


@pytest.fixture()
def test_ro_crate(test_ro_loader: ROLoader) -> ROCrate:
    "RO-Crate for testing"
    test_ro_loader.init_crate()
    return test_ro_loader.crate


@pytest.fixture()
def test_ro_builder(test_ro_crate: ROCrate) -> ROBuilder:
    "RO-Builder using test RO-Crate"
    return ROBuilder(test_ro_crate)


class ROCRATEHelpers:
    """Functions for validating RO-Crate contents
    taken and modified from ro-crate.py's conftest helpers
    """

    BASE_URL = "https://w3id.org/ro/crate"
    VERSION = "1.1"
    LEGACY_VERSION = "1.0"

    PROFILE = f"{BASE_URL}/{VERSION}"
    METADATA_FILE_NAME = "ro-crate-metadata.json"

    @classmethod
    def read_json_entities(cls, crate_base_path: Path) -> Dict[str, Any]:
        """Read entities from RO-Crate json into a dictionary"""
        metadata_path = crate_base_path / cls.METADATA_FILE_NAME
        with open(metadata_path, "rt", encoding="utf8") as f:
            json_data = json.load(f)
        return {_["@id"]: _ for _ in json_data["@graph"]}

    @classmethod
    def check_crate(
        cls,
        json_entities: Dict[str, Any],
        root_id: str = "./",
        data_entity_ids: set[str] | List[str] | None = None,
    ) -> None:
        """Validate key crate information conforms to standards"""
        assert root_id in json_entities
        root = json_entities[root_id]
        assert root["@type"] == "Dataset"
        assert cls.METADATA_FILE_NAME in json_entities
        metadata = json_entities[cls.METADATA_FILE_NAME]
        assert metadata["@type"] == "CreativeWork"
        assert cls.PROFILE in get_norm_value(metadata, "conformsTo")
        assert ARCHIVE_PROFILE in get_norm_value(metadata, "conformsTo")
        assert metadata["about"] == {"@id": root_id}
        if data_entity_ids:
            data_entity_ids = set(data_entity_ids)
            assert data_entity_ids.issubset(json_entities)
            assert "hasPart" in root
            assert data_entity_ids.issubset([_["@id"] for _ in root["hasPart"]])

    @classmethod
    def check_crate_contains(
        cls, json_entities: Dict[str, Any], ro_crate_entities: List[RO_Entity]
    ) -> None:
        """Check specific entities have been created within the RO-Crate json"""
        for entity in ro_crate_entities:
            assert json_entities[entity.id] is not None
            assert json_entities[entity.id] == json.loads(
                orjson.dumps(entity.as_jsonld()).decode(# pylint: disable=no-member
                    "utf-8"
                )  
            )


@pytest.fixture()
def ro_crate_helpers() -> type:
    "Fixture wrapper for RO-crate helper functions"
    return ROCRATEHelpers
