"""Tests for RO-Crate builder"""

import pytest
from dateutil.relativedelta import relativedelta
from factory.alchemy import SQLAlchemyModelFactory

from crate.ro_builder import RD_PREFIX, ROBuilder, as_ro_id

TEST_ITERATIONS = 50


def test_add_person(
    test_ro_builder: ROBuilder, person_factory: SQLAlchemyModelFactory
) -> None:
    "Test adding a Person to the ro-crate data"
    for _ in range(1, TEST_ITERATIONS):
        person = person_factory.create()
        ro_person = test_ro_builder.add_person(person)
        assert ro_person.get("email") == person.email
        assert ro_person.get("fullName") == person.full_name
        assert ro_person.id == as_ro_id(person.username)
        assert ro_person.type == "Person"
        assert ro_person.get("id") is None
        deref_person = test_ro_builder.crate.dereference(as_ro_id(person.username))
        assert ro_person == deref_person


def test_add_research_drive(
    test_ro_builder: ROBuilder, research_drive_service_factory: SQLAlchemyModelFactory
) -> None:
    "Test adding a research drive service to the ro-crate data"
    for _ in range(1, TEST_ITERATIONS):
        drive_service = research_drive_service_factory.create()
        ro_drive = test_ro_builder.add_research_drive_service(drive_service)
        assert ro_drive.get("allocatedGb") == drive_service.allocated_gb
        assert ro_drive.get("date") == drive_service.date
        assert ro_drive.get("firstDay") == drive_service.first_day
        assert ro_drive.get("freeGb") == drive_service.free_gb
        assert ro_drive.get("id") is None
        assert ro_drive.get("lastDay") == drive_service.last_day
        assert ro_drive.get("name") == drive_service.name
        assert ro_drive.get("percentageUsed") == drive_service.percentage_used
        assert ro_drive.get("usedGb") == drive_service.used_gb
        assert ro_drive.type == "ResearchDriveService"
        rd_id = f"{RD_PREFIX}{drive_service.name}"
        deref_drive = test_ro_builder.crate.dereference(as_ro_id(rd_id))
        assert ro_drive == deref_drive


def test_add_member(
    test_ro_builder: ROBuilder, member_factory: SQLAlchemyModelFactory
) -> None:
    "Test adding a member to the ro-crate data"
    for _ in range(1, TEST_ITERATIONS):
        member = member_factory.create()
        ro_member = test_ro_builder.add_member(member)
        assert ro_member.get("name") == member.role.name
        assert ro_member.get("member") == [test_ro_builder.add_person(member.person)]
        assert ro_member.get("id") is None
        assert ro_member.type == "OrganizationRole"


def test_add_delete_action(
    test_ro_builder: ROBuilder,
    project_factory: SQLAlchemyModelFactory,
    drive_offboard_submission_factory: SQLAlchemyModelFactory,
) -> None:
    "Test adding a delete action based on a project and submission to the ro-crate data"
    for _ in range(1, TEST_ITERATIONS):
        project = project_factory.create()
        submission = drive_offboard_submission_factory.create()
        delete_action = test_ro_builder.add_delete_action(
            submission=submission, project=project
        )
        assert delete_action["actionStatus"] == "PotentialActionStatus"
        assert delete_action["targetCollection"] == [
            test_ro_builder.add_research_drive_service(submission.drive)
        ]
        assert delete_action["endTime"] == project.end_date + relativedelta(
            years=+submission.retention_period_years
        )
        assert delete_action.type == "DeleteAction"
        assert delete_action.get("id") is None


def test_add_project(
    test_ro_builder: ROBuilder,
    project_factory: SQLAlchemyModelFactory,
    drive_offboard_submission_factory: SQLAlchemyModelFactory,
) -> None:
    "Test adding a project to the ro-crate data"
    for _ in range(1, TEST_ITERATIONS):
        project = project_factory.create()
        target_drive = project.research_drives[0]
        submission = drive_offboard_submission_factory.create(drive=target_drive)
        ro_project = test_ro_builder.add_project(
            project=project, project_submission=submission
        )
        assert ro_project["name"] == project.title
        assert ro_project["description"] == project.description
        assert ro_project["division"] == project.division
        assert ro_project["startDate"] == project.start_date
        assert ro_project["endDate"] == project.end_date
        assert ro_project["member"] == [
            test_ro_builder.add_member(member) for member in project.members
        ]
        assert ro_project["identifier"] == [code.code for code in project.codes]
        assert ro_project["services"] == [
            test_ro_builder.add_research_drive_service(drive)
            for drive in project.research_drives
        ]
        assert ro_project.get("id") is None
        assert (
            ro_project.get("retentionPeriodYears") == submission.retention_period_years
        )
        assert (
            ro_project.get("retentionPeriodJustification")
            == submission.retention_period_justification
        )
        assert ro_project.get("dataClassification") == submission.data_classification
        assert ro_project.get("actions")[0].type == "DeleteAction"
        assert ro_project.get("actions")[0].get("targetCollection") == [
            test_ro_builder.add_research_drive_service(target_drive)
        ]


def test_project_no_complete_submissions(
    test_ro_builder: ROBuilder,
    project_factory: SQLAlchemyModelFactory,
    drive_offboard_submission_factory: SQLAlchemyModelFactory,
) -> None:
    """Test a project will fail to be added if it's submissions are incomplete"""
    for _ in range(1, TEST_ITERATIONS):
        project = project_factory.create()
        target_drive = project.research_drives[0]
        submission = drive_offboard_submission_factory.create(
            drive=target_drive, is_completed=False
        )
        with pytest.raises(ValueError):
            _ = test_ro_builder.add_project(
                project=project, project_submission=submission
            )


def test_project_no_linked_submissions(
    test_ro_builder: ROBuilder,
    project_factory: SQLAlchemyModelFactory,
    drive_offboard_submission_factory: SQLAlchemyModelFactory,
) -> None:
    """Test a project failure if its submissions are not associated with the same drive"""
    for _ in range(1, TEST_ITERATIONS):
        project = project_factory.create()
        submission = drive_offboard_submission_factory.create(is_completed=False)
        with pytest.raises(ValueError):
            _ = test_ro_builder.add_project(
                project=project, project_submission=submission
            )
