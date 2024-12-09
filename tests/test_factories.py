"functions and classes for testing the factories for populating classes"
from factory.alchemy import SQLAlchemyModelFactory
from sqlmodel import Session, select

from models.project import Project


def test_factories_all(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    person_factory: SQLAlchemyModelFactory,
    member_factory: SQLAlchemyModelFactory,
    code_factory: SQLAlchemyModelFactory,
    research_drive_service_factory: SQLAlchemyModelFactory,
    drive_offboard_submission_factory: SQLAlchemyModelFactory,
    project_factory: SQLAlchemyModelFactory,
) -> None:
    "Test the basic functionality of all factories"
    person_factory.build()
    member_factory.build()
    code_factory.build()
    research_drive_service_factory.build()
    drive_offboard_submission_factory.build()
    project_factory.build()


def test_project_retrieval(
    project_factory: SQLAlchemyModelFactory, session: Session
) -> None:
    "test factories create within DB correctly"
    project = project_factory.create(title="test12345")

    project_query = select(Project).where(Project.title == "test12345")
    project_found = session.exec(project_query).first()
    assert project_found == project


def test_project_session_scope(
    project_factory: SQLAlchemyModelFactory, session: Session
) -> None:
    "check session scope is only within each unit test for factories"
    project_factory.create(title="test54321")

    project_query = select(Project).where(Project.title == "test12345")
    project_found = session.exec(project_query).first()
    assert project_found is None
