from datetime import datetime

import pytest

from models.project import Project
from models.project_changes import ProjectChanges


@pytest.fixture
def project() -> Project:
    return Project(
        title="Original title",
        description="This is a description.",
        division="Liggins Institute",
        start_date=datetime(2024, 1, 2),
        end_date=datetime(2024, 6, 5),
    )


def test_project_change_applied(project: Project):
    changes = ProjectChanges(
        title="A different title", description="Changed description."
    )
    assert changes.apply_changes(project) is True
    assert project.title == "A different title"
    assert project.description == "Changed description."


def test_no_changes_returns_false(project: Project):
    changes = ProjectChanges()
    assert changes.apply_changes(project) is False
    assert project.title == "Original title"
    assert project.description == "This is a description."
