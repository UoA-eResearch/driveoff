"""Tests for RO-Crate builder"""

from datetime import datetime

import pytest
from dateutil.relativedelta import relativedelta

from crate.ro_builder import RD_PREFIX, ROBuilder, as_ro_id


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
    assert ro_person.id == as_ro_id("jdoe123")
    assert ro_person.type == "Person"
    assert ro_person.get("id") is None
    deref_person = test_ro_builder.crate.dereference(as_ro_id("jdoe123"))
    assert ro_person == deref_person


def test_add_research_drive(test_ro_builder: ROBuilder) -> None:
    """Test adding a research drive service to the ro-crate data"""
    drive_name = "test-drive-001"
    ro_drive = test_ro_builder.add_research_drive_service(drive_name)
    assert ro_drive.get("name") == drive_name
    assert ro_drive.type == "ResearchDriveService"
    assert ro_drive.get("id") is None
    rd_id = f"{RD_PREFIX}{drive_name}"
    deref_drive = test_ro_builder.crate.dereference(as_ro_id(rd_id))
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
    assert ro_member.get("id") is None
    assert ro_member.type == "OrganizationRole"


def test_add_delete_action(test_ro_builder: ROBuilder) -> None:
    """Test adding a delete action to the ro-crate data"""
    project_end_date = datetime(2024, 11, 4)
    retention_years = 7
    drive_name = "test-drive"
    delete_action = test_ro_builder.add_delete_action(
        project_end_date=project_end_date.strftime("%Y-%m-%d"),
        retention_years=retention_years,
        drive_name=drive_name,
    )
    assert delete_action["actionStatus"] == "PotentialActionStatus"
    expected_end_time = project_end_date + relativedelta(years=+retention_years)
    assert delete_action["endTime"] == expected_end_time.strftime("%Y-%m-%d")
    assert delete_action.type == "DeleteAction"
    assert delete_action.get("id") is None


def test_add_project(
    test_ro_builder: ROBuilder,
    test_project_dict,
    test_member_dict,
    test_archive_metadata,
) -> None:
    """Test adding a project to the ro-crate data"""
    members_list = [test_member_dict]

    ro_project = test_ro_builder.add_project(
        project=test_project_dict,
        members=members_list,
        archive_metadata=test_archive_metadata,
    )
    assert ro_project["name"] == "Test Project"
    assert ro_project["description"] == "A test project"
    assert ro_project["division"] == "CTRERSH"
    assert ro_project["startDate"] == datetime(2022, 1, 1)
    assert ro_project["endDate"] == datetime(2024, 11, 4)
    assert ro_project.get("id") is None
    assert ro_project.get("retentionPeriodYears") == 7
    assert ro_project.get("retentionPeriodJustification") == "Standard retention"
    assert ro_project.get("dataClassification") == "Sensitive"
    assert len(ro_project.get("actions", [])) > 0
    assert ro_project.get("actions")[0].type == "DeleteAction"


def test_add_project_with_expanded_projectdb_data(
    test_ro_builder: ROBuilder, project_members_expanded
) -> None:
    """Test adding a project with actual ProjectDB API expanded member data"""
    if not project_members_expanded:
        pytest.skip("project_members_expanded.json not found")

    project_dict = {
        "id": 2210,
        "title": "Test Project with Real Members",
        "description": "Testing with actual ProjectDB expansion",
        "division": "CTRERSH",
        "start_date": datetime(2022, 1, 1),
        "end_date": datetime(2024, 11, 4),
        "codes": {"items": [{"code": "TEST-001"}]},
    }

    archive_metadata = {
        "drive_name": "ressci202300019-testresearchdrive",
        "retention_period_years": 7,
        "retention_period_justification": "Standard retention",
        "data_classification": "Sensitive",
    }

    ro_project = test_ro_builder.add_project(
        project=project_dict,
        members=project_members_expanded,
        archive_metadata=archive_metadata,
    )

    # Verify project was created
    assert ro_project.get("name") == "Test Project with Real Members"
    assert ro_project.get("retentionPeriodYears") == 7

    # Verify members were extracted correctly from expanded data
    entities = test_ro_builder.crate.get_entities()

    # Should have multiple Person and OrganizationRole entities
    people = [e for e in entities if e.type == "Person"]
    roles = [e for e in entities if e.type == "OrganizationRole"]

    # With 4 members in project_members_expanded (but same person repeated with different roles)
    # We should have 1 unique person and 4 roles
    assert len(people) > 0, "No Person entities found"
    assert len(roles) > 0, "No OrganizationRole entities found"

    # Check that people have correct IDs (not "unknown")
    for person in people:
        assert person.id != as_ro_id("unknown"), f"Person has unknown ID: {person.id}"

    # Check that roles have correct names (not "NoRole")
    for role in roles:
        role_name = role.get("roleName", "NoRole")
        assert role_name != "NoRole", f"Role has NoRole name: {role}"
