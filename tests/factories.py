# pylint: disable=missing-class-docstring,too-few-public-methods
# factory meta classes don't need docstrings
"""Factories generating dataclasses for testing"""

import random

import factory
from factory.alchemy import SQLAlchemyModelFactory
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

from models.common import DataClassification
from models.member import Member
from models.person import Person
from models.project import Code, Project
from models.role import Role, prepopulate_roles
from models.services import ResearchDriveService
from models.submission import DriveOffboardSubmission

engine = create_engine("sqlite://")
session = scoped_session(sessionmaker(bind=engine))
Base = declarative_base()
Base.metadata.create_all(engine)

ROLES = prepopulate_roles()


def random_role() -> Role:
    "Choose a random role from the prepoulated roles"
    return random.choice(ROLES)


class PersonFactory(SQLAlchemyModelFactory):
    """Factory for generating test person objects"""

    class Meta:
        model = Person
        sqlalchemy_session_factory = session

    id: int = factory.sequence(lambda n: n)
    email = random.choice([factory.Faker("email"), None])
    full_name = factory.Faker("name")
    username = factory.Faker(
        "bothify", text="????###", letters="abcdefghijklmnopqrstuvwxyz"
    )


class DriveOffboardSubmissionFactory(SQLAlchemyModelFactory):
    """factory for generating test submission objects"""

    class Meta:
        model = DriveOffboardSubmission
        sqlalchemy_session_factory = session

    retention_period_years = random.choice([6, 10, 20, 26, random.randrange(7, 100)])
    retention_period_justification = random.choice([factory.Faker("sentence"), None])
    data_classification = random.choice(list(DataClassification))
    is_completed = True
    updated_time = factory.Faker("date_time")
    is_project_updated = False


class ResearchDriveServiceFactory(SQLAlchemyModelFactory):
    """factory for generating test person objects"""

    class Meta:
        model = ResearchDriveService
        sqlalchemy_session_factory = session

    id: int = factory.sequence(lambda n: n)

    date = factory.Faker("date_time")
    first_day = factory.Faker("date_time")
    free_gb = random.random() * random.randrange(1, 5000)
    used_gb = random.random() * random.randrange(1, 5000)
    allocated_gb = free_gb + used_gb
    percentage_used = used_gb / (allocated_gb)
    last_day = random.choice([factory.Faker("date_time"), None])
    name = factory.Faker(
        "bothify", text="res???#########-????????", letters="abcdefghijklmnopqrstuvwxyz"
    )
    submission = factory.SubFactory(DriveOffboardSubmissionFactory)


class MemberFactory(SQLAlchemyModelFactory):
    """factory for generating test member objects"""

    class Meta:
        model = Member
        sqlalchemy_session_factory = session

    role = random_role()
    project = None
    person = factory.SubFactory(PersonFactory)


class CodeFactory(SQLAlchemyModelFactory):
    """factory for generating test code objects"""

    class Meta:
        model = Code
        sqlalchemy_session_factory = session

    code = factory.Faker("bothify", text="????????#####")


class ProjectFactory(SQLAlchemyModelFactory):
    """factory for generating test project objects"""

    class Meta:
        model = Project
        sqlalchemy_session_factory = session

    title = factory.Faker("sentence")
    description = factory.Faker("paragraph")
    division = factory.Faker("company")
    start_date = factory.Faker("date_time")
    end_date = factory.Faker("date_time")
    members = factory.List(
        [factory.SubFactory(MemberFactory) for _ in range(random.randrange(0, 10))]
    )
    codes = factory.List(
        [factory.SubFactory(CodeFactory) for _ in range(random.randrange(0, 5))]
    )
    research_drives = factory.List([factory.SubFactory(ResearchDriveServiceFactory)])
