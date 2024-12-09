# pylint: disable=missing-class-docstring,too-few-public-methods,missing-module-docstring,missing-module-docstring
# factory meta classes don't need docstrings
import random
from datetime import datetime
from typing import Any

import factory
import pytest
from factory.alchemy import SQLAlchemyModelFactory
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel
from sqlmodel.pool import StaticPool

from models.common import DataClassification
from models.member import Member
from models.person import Person
from models.project import Code, Project
from models.role import Role, prepopulate_roles
from models.services import ResearchDriveService
from models.submission import DriveOffboardSubmission

ROLES = prepopulate_roles()


def random_role() -> Role:
    "Choose a random role from the prepoulated roles"
    return random.choice(ROLES)


@pytest.fixture(name="session")
def session_fixture() -> Session:
    "scoped session for each unit test"
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
        session.rollback()
        session.close()


@pytest.fixture
def submission() -> dict[str, Any]:
    """Fixture with a working submission.

    Returns:
        dict[str, Any]: submission data.
    """
    return {
        "retention_period_years": 6,
        "data_classification": DataClassification.PUBLIC,
        "is_completed": True,
        "updated_time": datetime.now(),
        "is_project_updated": True,
        "drive_id": 1,
    }


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
def drive_offboard_submission_factory(session: Session) -> SQLAlchemyModelFactory:
    "fixture for DriveOffboardSubmission factories"

    class DriveOffboardSubmissionFactory(SQLAlchemyModelFactory):
        """factory for generating test submission objects"""

        class Meta:
            model = DriveOffboardSubmission
            sqlalchemy_session = session

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

    return DriveOffboardSubmissionFactory


@pytest.fixture
def research_drive_service_factory(
    session: Session, drive_offboard_submission_factory: SQLAlchemyModelFactory
) -> SQLAlchemyModelFactory:
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
        submission = factory.SubFactory(drive_offboard_submission_factory)

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
