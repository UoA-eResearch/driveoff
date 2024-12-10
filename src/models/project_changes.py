"""Class for representing updates to project details. """

from typing import TYPE_CHECKING

from sqlmodel import Field, SQLModel

if TYPE_CHECKING:
    from models.project import Project


class ProjectChanges(SQLModel):
    """A model for describing updates to a project."""

    title: str | None = Field(default=None)
    description: str | None = Field(default=None)

    def apply_changes(self, to: "Project") -> bool:
        """Update a project based on changed values in this instance.

        Args:
            to (Project): The project model to apply changes to.

        Returns:
            bool: If there were any changes applied.
        """
        applied_changes: bool = False
        if self.title is not None and self.title != to.title:
            to.title = self.title
            applied_changes = True
        if self.description is not None and self.description != to.description:
            to.description = self.description
            applied_changes = True
        return applied_changes
