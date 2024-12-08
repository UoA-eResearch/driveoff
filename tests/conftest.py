from datetime import datetime
from typing import Any

import pytest
from _pytest.stash import D
from fastapi.testclient import TestClient
from sqlalchemy.orm import session
from sqlalchemy.sql.functions import user
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from api.main import app, get_session
from models.member import Member
from models.person import Person
from models.project import Code, Project
from models.services import ResearchDriveService


@pytest.fixture(name="session")
def session_fixture() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture():
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# @pytest.fixture
# def project_and_drive():
#     drive = ResearchDriveService(
#         allocated_gb=25600,
#         free_gb=24004.5,
#         used_gb=1596,
#         date=datetime(2024, 10, 13),
#         first_day=datetime(2022, 1, 9),
#         last_day=None,
#         name="reslig202200001-Tītoki-metabolomics",
#         percentage_used=2.75578,
#         id=None,
#     )
#     people = [
#         Person(
#             email="s.nicolas@test.auckland.ac.nz",
#             full_name="Samina Nicholas",
#             username="snic021",
#             id=1421,
#         ),
#         Person(
#             username="jhos225",
#             full_name="Jarrod Hossam",
#             email="j.hossam@test.auckland.ac.nz",
#             id=188,
#         ),
#         Person(
#             username="medr894",
#             email="m.edric@test.auckland.ac.nz",
#             full_name="Melisa Edric",
#             id=44,
#         ),
#     ]
#     project = Project(
#         codes=[Code(code="uoa00001", id=550), Code(code="reslig202200001", id=630)],
#         title="Tītoki metabolomics",
#         description="""
#         Stress in plants could be defined as any change in
#         growth condition(s) that disrupts metabolic homeostasis
#         and requires an adjustment of metabolic pathways in a
#         process that is usually referred to as acclimation.
#         Metabolomics could contribute significantly to the study of stress
#         biology in plants and other organisms by identifying different
#          compounds, such as by-products of stress metabolism,
#          stress signal transduction molecules or molecules that
#          are part of the acclimation response of plants.
#          """,
#         division="Liggins Institute",
#         start_date=datetime(2022, 1, 1),
#         end_date=datetime(2024, 11, 4),
#     )
#     members = [Member(person_id=1421, role_id=3)]
#     return Project()
