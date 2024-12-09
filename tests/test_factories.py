
"functions and classes for testing the factories for populating classes"
from factory.alchemy import SQLAlchemyModelFactory


def test_factories_all(# pylint: disable=too-many-arguments,too-many-positional-arguments
    person_factory: SQLAlchemyModelFactory,
    member_factory: SQLAlchemyModelFactory,
    code_factory: SQLAlchemyModelFactory,
    research_drive_service_factory: SQLAlchemyModelFactory,
    drive_offboard_submission_factory: SQLAlchemyModelFactory,
    project_factory: SQLAlchemyModelFactory
    ) -> None:
    "Test the basic functionality of all factories"
    person_factory.build()
    member_factory.build()
    code_factory.build()
    research_drive_service_factory.build()
    drive_offboard_submission_factory.build()
    project_factory.build()
