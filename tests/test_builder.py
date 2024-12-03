import random
from datetime import datetime
from typing import Any

import factory
import pytest
from rocrate.rocrate import ROCrate
from sqlalchemy import Column, Integer, Unicode, create_engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

from crate.ro_builder import ROBuilder, as_ro_id
from models.person import Person
from models.services import ResearchDriveService

engine = create_engine("sqlite://")
session = scoped_session(sessionmaker(bind=engine))
Base = declarative_base()
Base.metadata.create_all(engine)


class PersonFactory(factory.alchemy.SQLAlchemyModelFactory):
    """factory for generating test person objects"""

    class Meta:
        model = Person
        sqlalchemy_session_factory = session
        # sqlalchemy_session_factory = lambda: common.Session()

    id: int = factory.Faker("random_int")
    email = random.choice([factory.Faker("email"), None])
    full_name = factory.Faker("name")
    username = factory.Faker(
        "bothify", text="????###", letters="abcdefghijklmnopqrstuvwxyz"
    )


class ResearchDriveServiceFactory(factory.alchemy.SQLAlchemyModelFactory):
    """factory for generating test person objects"""

    class Meta:
        model = ResearchDriveService
        sqlalchemy_session_factory = session

    # id: Optional[int] = factory.Faker('random_int')
    id: int = factory.Faker("random_int")
    allocated_gb = random.random()
    date = factory.Faker("date_time")
    first_day = factory.Faker("date_time")
    free_gb = random.random()
    last_day = random.choice([factory.Faker("date_time"), None])
    name = factory.Faker("sentence")
    percentage_used = random.random()
    used_gb = random.random()


def test_add_person(test_ro_builder: ROBuilder) -> None:
    for _ in range(1, 10):
        person = PersonFactory.build()
        ro_person = test_ro_builder.add_person(person)
        assert ro_person.get("email") == person.email
        assert ro_person.get("fullName") == person.full_name
        assert ro_person.id == as_ro_id(person.username)


def test_add_research_drive(test_ro_builder: ROBuilder) -> None:
    for _ in range(1, 10):
        drive_service = ResearchDriveServiceFactory.build()
        ro_person = test_ro_builder.add_research_drive_service(drive_service)
