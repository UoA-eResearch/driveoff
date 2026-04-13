# pylint: disable=missing-class-docstring,redefined-outer-name,too-few-public-methods,missing-module-docstring
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from collections.abc import Generator
from typing import Any

import orjson
import pytest
from fastapi.testclient import TestClient
from rocrate.model import ContextEntity as RO_Entity
from rocrate.rocrate import ROCrate
from rocrate.utils import get_norm_value
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel
from sqlmodel.pool import StaticPool

from api.main import app, get_session
from service.projectdb import get_projectdb_client
from api.security import ApiKey, read_api_keys
from crate.ro_builder import ROBuilder
from crate.ro_loader import PROFILE as ARCHIVE_PROFILE
from crate.ro_loader import ROLoader
from models.common import DataClassification
from models.manifest import Manifest
from models.submission import ArchiveSubmission

THIS_DIR = Path(__file__).absolute().parent
TEST_DATA_NAME = "restst000000001-testing"
TEST_INPUT_NAME = "Vault"
TEST_OUTPUT_NAME = "Archive"


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, Any, None]:
    """scoped session for each unit test"""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
        session.rollback()
        session.close()


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, Any, None]:
    """test client with mocked dependencies"""
    from unittest.mock import MagicMock

    def get_session_override() -> Session:
        return session

    # Generate a random API key and use it for the tests.
    test_api_key: str = str(uuid.uuid4())

    def read_api_keys_override():
        api_key_obj = ApiKey(value=test_api_key, actions=["GET", "PUT", "POST"])
        return {test_api_key: api_key_obj}

    # Mock ProjectDB client for API tests
    def get_projectdb_client_override():
        mock_projectdb = MagicMock()
        mock_projectdb.get_research_drive_by_name = {
            "allocated_gb": 4000.0,
            "archived": 0,
            "date": "2026-03-09",
            "deleted": 0,
            "free_gb": 4000.0,
            "id": 6904394,
            "name": "restst000000001-testing",
            "num_files": 4,
            "percentage_used": 0.0,
            "used_gb": 0.0,
        }
        mock_projectdb.get_research_drive_projects.return_value = [
            {
                "project": {
                    "id": 123,
                    "title": "Test Project",
                    "description": "Test Description",
                }
            }
        ]
        mock_projectdb.get_project.return_value = {
            "id": 123,
            "title": "Test Project",
            "description": "Test Description",
            "division": "CTRERSH",
            "end_date": "2024-11-04",
            "codes": {"items": [{"code": "TEST-001"}]},
            "services": {
                "research_drive": [
                    {
                        "allocated_gb": 4000.0,
                        "archived": 0,
                        "date": "2026-03-18",
                        "deleted": 0,
                        "first_day": "2023-04-13",
                        "free_gb": 4000.0,
                        "id": 6904394,
                        "name": "restst000000001-testing",
                        "num_files": 4,
                        "percentage_used": 0.0,
                        "project_code": "restst000000001",
                        "used_gb": 0.0,
                    }
                ]
            },
        }
        mock_projectdb.get_project_members.return_value = [
            {
                "person": {
                    "full_name": "User One",
                    "email": "user1@example.com",
                    "identities": {"items": [{"username": "user1"}]},
                    "status": {"name": "Active"},
                },
                "role": {"role": "Principal Investigator"},
            }
        ]
        return mock_projectdb

    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[read_api_keys] = read_api_keys_override
    app.dependency_overrides[get_projectdb_client] = get_projectdb_client_override
    client = TestClient(app, headers={"x-api-key": test_api_key})
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def tmpdir(tmpdir: str) -> Path:
    """convert temporary directory to path"""
    return Path(tmpdir)


@pytest.fixture
def data_dir(tmpdir: Path) -> Path:
    """temporary directory for input files"""
    d = tmpdir / TEST_DATA_NAME / TEST_INPUT_NAME
    shutil.copytree(THIS_DIR / TEST_DATA_NAME, d)
    return d


@pytest.fixture
def archive_dir(tmpdir: Path) -> Path:
    """temporary directory for archived files"""
    d = tmpdir / TEST_DATA_NAME / TEST_OUTPUT_NAME
    return d


@pytest.fixture
def submission() -> ArchiveSubmission:
    """minimal test ArchiveSubmission"""
    return ArchiveSubmission(
        drive_id=1234,
        project_id=123,
        drive_name="restst000000001-testing",
        retention_period_years=7,
        retention_period_justification="Standard research data retention",
        data_classification=DataClassification.SENSITIVE,
        archive_date=datetime(2024, 10, 13),
        archive_location="/archive/path",
        manifest_id=None,
        is_completed=False,
        created_timestamp=datetime(2024, 10, 13),
    )


@pytest.fixture
def manifest() -> Manifest:
    """minimal test Manifest"""
    return Manifest(
        manifest=json.dumps(
            {"files": [{"name": "file.txt", "size": 1024, "hash": "abc123"}]}
        )
    )


@pytest.fixture()
def test_ro_loader() -> ROLoader:
    """RO-loader fixture"""
    return ROLoader()


@pytest.fixture()
def test_ro_crate(test_ro_loader: ROLoader) -> ROCrate:
    """RO-Crate for testing"""
    test_ro_loader.init_crate()
    return test_ro_loader.crate


@pytest.fixture()
def test_ro_builder(test_ro_crate: ROCrate) -> ROBuilder:
    """RO-Builder using test RO-Crate"""
    return ROBuilder(test_ro_crate)


@pytest.fixture()
def test_project_dict() -> dict[str, Any]:
    """Reusable test project data matching ProjectDB structure"""
    from datetime import datetime

    return {
        "id": 123,
        "title": "Test Project",
        "description": "A test project",
        "division": "CTRERSH",
        "start_date": datetime(2022, 1, 1),
        "end_date": datetime(2024, 11, 4),
        "codes": {"items": [{"code": "CODE-001"}, {"code": "CODE-002"}]},
    }


@pytest.fixture()
def test_member_dict() -> dict[str, Any]:
    """Reusable test member data matching ProjectDB structure"""
    return {
        "person": {
            "username": "jdoe123",
            "full_name": "John Doe",
            "email": "j.doe@example.com",
            "identities": {"items": [{"username": "jdoe123"}]},
            "status": {"name": "Active"},
        },
        "role": {"role": "Principal Investigator"},
    }


@pytest.fixture()
def test_drive_dict() -> dict[str, Any]:
    """Reusable drive data matching ProjectDB structure"""
    return {
        "allocated_gb": 4000.0,
        "archived": 0,
        "date": "2026-03-09",
        "deleted": 0,
        "free_gb": 4000.0,
        "id": 6904394,
        "name": "restst000000001-testing",
        "num_files": 4,
        "percentage_used": 0.0,
        "used_gb": 0.0,
    }


@pytest.fixture()
def test_submission() -> ArchiveSubmission:
    """Reusable ArchiveSubmission for builder tests"""
    return ArchiveSubmission(
        drive_id=6904394,
        project_id=123,
        drive_name="restst000000001-testing",
        retention_period_years=7,
        retention_period_justification="Standard retention",
        data_classification=DataClassification.SENSITIVE,
        archive_date=datetime(2024, 10, 13),
        archive_location="/archive/path",
        manifest_id=None,
        is_completed=False,
        created_timestamp=datetime(2024, 10, 13),
    )


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
    def read_json_entities(cls, crate_base_path: Path) -> dict[str, Any]:
        """Read entities from RO-Crate json into a dictionary"""
        metadata_path = crate_base_path / cls.METADATA_FILE_NAME
        with open(metadata_path, "rt", encoding="utf8") as f:
            json_data = json.load(f)
        return {_["@id"]: _ for _ in json_data["@graph"]}

    @classmethod
    def check_crate(
        cls,
        json_entities: dict[str, Any],
        root_id: str = "./",
        data_entity_ids: set[str] | list[str] | None = None,
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
        cls, json_entities: dict[str, Any], ro_crate_entities: list[RO_Entity]
    ) -> None:
        """Check specific entities have been created within the RO-Crate json"""
        for entity in ro_crate_entities:
            assert json_entities[entity.id] is not None
            assert json_entities[entity.id] == json.loads(
                orjson.dumps(entity.as_jsonld()).decode(  # pylint: disable=no-member
                    "utf-8"
                )
            )


@pytest.fixture()
def ro_crate_helpers() -> type:
    """Fixture wrapper for RO-crate helper functions"""
    return ROCRATEHelpers
