"""Tests for RO-Crate builder"""

from datetime import datetime

from dateutil.relativedelta import relativedelta

from crate.ro_builder import RD_PREFIX, ROBuilder, as_ro_id
from models.common import DataClassification
from models.submission import ArchiveSubmission


def test_add_person(test_ro_builder: ROBuilder) -> None:
    """Test adding a Person to the ro-crate data"""
    person_dict = {
        "username": "jdoe123",
        "full_name": "John Doe",
        "email": "j.doe@example.com",
        "identities": {"items": [{"username": "jdoe123"}]},
    }
    ro_person = test_ro_builder.add_person(person_dict)
    assert ro_person.get("email") == "j.doe@example.com"
    assert ro_person.get("name") == "John Doe"
    assert ro_person.id == "#jdoe123"
    assert ro_person.type == "Person"
    deref_person = test_ro_builder.crate.dereference("#jdoe123")
    assert ro_person == deref_person


def test_add_research_drive(test_ro_builder: ROBuilder) -> None:
    """Test adding a research drive service to the ro-crate data"""
    drive_data = {
        "name": "test-drive-001",
        "allocated_gb": 100.0,
        "free_gb": 50.0,
        "used_gb": 50.0,
        "date": "2026-03-09",
        "percentage_used": 50.0,
    }
    ro_drive = test_ro_builder.add_research_drive_service(drive_data)
    assert ro_drive.get("name") == "test-drive-001"
    assert ro_drive.type == "ResearchDriveService"
    rd_id = as_ro_id(f"{RD_PREFIX}test-drive-001")
    deref_drive = test_ro_builder.crate.dereference(rd_id)
    assert ro_drive == deref_drive


def test_add_member(test_ro_builder: ROBuilder) -> None:
    """Test adding a member to the ro-crate data"""
    # Add a person first
    person_dict = {
        "username": "jdoe123",
        "full_name": "John Doe",
        "email": "j.doe@example.com",
        "identities": {"items": [{"username": "jdoe123"}]},
    }
    member_dict = {
        "person": person_dict,
        "role": {"role": "Principal Investigator"},
    }
    ro_member = test_ro_builder.add_member(member_dict)
    assert ro_member.get("roleName") == "Principal Investigator"
    assert ro_member.type == "OrganizationRole"


def test_add_delete_action(test_ro_builder: ROBuilder) -> None:
    """Test adding a delete action to the ro-crate data"""
    project_end_date = datetime(2024, 11, 4)
    retention_years = 7
    drive = {
        "name": "test-drive",
        "allocated_gb": 100.0,
        "free_gb": 50.0,
        "used_gb": 50.0,
        "date": "2026-03-09",
        "percentage_used": 50.0,
    }
    delete_action = test_ro_builder.add_delete_action(
        project_end_date=project_end_date.strftime("%Y-%m-%d"),
        retention_years=retention_years,
        drive=drive,
    )
    assert delete_action["actionStatus"] == "PotentialActionStatus"
    expected_end_time = project_end_date + relativedelta(years=+retention_years)
    assert delete_action["endTime"] == expected_end_time.strftime("%Y-%m-%d")
    assert delete_action.type == "DeleteAction"


def test_add_project(
    test_ro_builder: ROBuilder,
    test_project_dict,
    test_member_dict,
    test_submission,
    test_drive_dict,
) -> None:
    """Test adding a project to the ro-crate data"""
    members_list = [test_member_dict]

    ro_project = test_ro_builder.add_project(
        project=test_project_dict,
        members=members_list,
        submission=test_submission,
        drive=test_drive_dict,
    )
    assert ro_project["name"] == "Test Project"
    assert ro_project["description"] == "A test project"
    assert ro_project["division"] == "CTRERSH"
    assert ro_project["startDate"] == datetime(2022, 1, 1)
    assert ro_project["endDate"] == datetime(2024, 11, 4)
    assert ro_project.get("retentionPeriodYears") == 7
    assert ro_project.get("retentionPeriodJustification") == "Standard retention"
    assert ro_project.get("dataClassification") == "Sensitive"
    assert len(ro_project.get("actions", [])) > 0
    assert ro_project.get("actions")[0].type == "DeleteAction"


def test_add_project_with_multiple_members(
    test_ro_builder: ROBuilder,
) -> None:
    """Test adding a project with multiple members with different roles"""
    project_dict = {
        "id": 2210,
        "title": "Test Project with Multiple Members",
        "description": "Testing with multiple members",
        "division": "CTRERSH",
        "start_date": datetime(2022, 1, 1),
        "end_date": datetime(2024, 11, 4),
        "codes": {"items": [{"code": "TEST-001"}]},
    }

    members_list = [
        {
            "person": {
                "full_name": "Alice Smith",
                "email": "a.smith@example.com",
                "identities": {"items": [{"username": "asmith"}]},
                "status": {"name": "Active"},
            },
            "role": {"role": "Principal Investigator"},
        },
        {
            "person": {
                "full_name": "Bob Jones",
                "email": "b.jones@example.com",
                "identities": {"items": [{"username": "bjones"}]},
                "status": {"name": "Active"},
            },
            "role": {"role": "Researcher"},
        },
        {
            "person": {
                "full_name": "Alice Smith",
                "email": "a.smith@example.com",
                "identities": {"items": [{"username": "asmith"}]},
                "status": {"name": "Active"},
            },
            "role": {"role": "Data Custodian"},
        },
    ]

    drive_data = {
        "name": "ressci202300019-testresearchdrive",
        "allocated_gb": 4000.0,
        "free_gb": 4000.0,
        "used_gb": 0.0,
        "date": "2026-03-09",
        "percentage_used": 0.0,
    }

    submission = ArchiveSubmission(
        drive_id=1,
        project_id=2210,
        drive_name="ressci202300019-testresearchdrive",
        retention_period_years=7,
        retention_period_justification="Standard retention",
        data_classification=DataClassification.SENSITIVE,
        archive_date=datetime(2024, 10, 13),
        archive_location="/archive/path",
        manifest_id=None,
        is_completed=False,
        created_timestamp=datetime(2024, 10, 13),
    )

    ro_project = test_ro_builder.add_project(
        project=project_dict,
        members=members_list,
        submission=submission,
        drive=drive_data,
    )

    assert ro_project.get("name") == "Test Project with Multiple Members"
    assert ro_project.get("retentionPeriodYears") == 7

    entities = test_ro_builder.crate.get_entities()
    people = [e for e in entities if e.type == "Person"]
    roles = [e for e in entities if e.type == "OrganizationRole"]

    # 2 unique people (Alice appears twice with different roles)
    assert len(people) == 2, f"Expected 2 Person entities, got {len(people)}"
    # 3 roles (PI, Researcher, Data Custodian)
    assert len(roles) == 3, f"Expected 3 OrganizationRole entities, got {len(roles)}"

    for person in people:
        assert person.id != as_ro_id("unknown"), f"Person has unknown ID: {person.id}"

    for role in roles:
        role_name = role.get("roleName", "NoRole")
        assert role_name != "NoRole", f"Role has NoRole name: {role}"
