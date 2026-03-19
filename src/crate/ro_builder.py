# pylint: disable-all
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from dateutil.relativedelta import relativedelta
from rocrate.model.contextentity import ContextEntity
from rocrate.model.person import Person as RoPerson
from rocrate.rocrate import ROCrate
from rocrate.utils import is_url

PROJECT_PREFIX = "project/"
ROLE_PREFIX = "role/"
MEMBER_PREFIX = "member/"
RD_PREFIX = "research_drive_service/"
DELETE_PREFIX = "retention_period_for/"


def as_ro_id(obj_id: str) -> str:
    if is_url(obj_id):
        return obj_id
    return f"#{obj_id}"


class ROBuilder:
    """Builder for Project Archive Crate RO-Cratess"""

    crate: ROCrate

    def __init__(self, crate: ROCrate) -> None:
        self.crate = crate

    def add_project(
        self,
        project: Dict[str, Any],
        members: List[Dict[str, Any]],
        archive_metadata: Dict[str, Any],
    ) -> ContextEntity:
        """Add project to RO-Crate, fetching data from ProjectDB on-demand.

        Args:
            project: Raw project dict from ProjectDB with keys: id, title, description, division, codes, etc.
            members: List of member dicts from ProjectDB with keys: id, person, role, etc.
            archive_metadata: Dict containing retention_period_years, data_classification, drive_name, etc.
        """
        # Extract project properties
        project_id = project.get("id")
        codes = project.get("codes", {})

        # Root dataset entity represents the archive with archive metadata
        project_properties = {
            "@type": "Dataset",
            "name": project.get("title", ""),
            "description": project.get("description", ""),
        }

        # Add optional project metadata fields
        if division := project.get("division"):
            project_properties["division"] = division
        if start_date := project.get("start_date"):
            project_properties["startDate"] = start_date
        if end_date := project.get("end_date"):
            project_properties["endDate"] = end_date
        if is_completed := project.get("is_completed"):
            project_properties["isCompleted"] = is_completed
        if updated_time := project.get("updated_time"):
            project_properties["updatedTime"] = updated_time

        # Add project identifiers (codes)
        if codes and codes.get("items"):
            project_properties["identifier"] = [
                code.get("code") for code in codes.get("items", []) if code.get("code")
            ]

        # Add archive metadata properties to the dataset
        archive_properties = {
            "dataClassification": archive_metadata.get(
                "data_classification", "Sensitive"
            ),
            "retentionPeriodYears": archive_metadata.get("retention_period_years", 0),
            "retentionPeriodJustification": archive_metadata.get(
                "retention_period_justification"
            ),
        }

        project_entity = ContextEntity(
            crate=self.crate,
            identifier=f"{PROJECT_PREFIX}{project_id}",
            properties=project_properties | archive_properties,
        )

        # Add members to project (pass project_id for member ID generation)
        project_people = [
            self.add_member(member, project_id=project_id) for member in members
        ]
        project_entity.append_to("member", project_people)

        # Add research drive service reference
        drive_entity = self.add_research_drive_service(
            archive_metadata.get("drive_name", "unknown")
        )
        project_entity.append_to("services", [drive_entity])

        # Add delete action from retention period
        delete_action = self.add_delete_action(
            project_end_date=project.get("end_date"),
            retention_years=archive_metadata.get("retention_period_years", 0),
            drive_name=archive_metadata.get("drive_name", "unknown"),
        )
        project_entity.append_to("actions", [delete_action])

        return cast(ContextEntity, self.crate.add(project_entity))

    def _extract_username(self, person: Dict[str, Any]) -> str:
        """Extract username from person dict, trying multiple sources.

        Args:
            person: Person dict from ProjectDB

        Returns:
            Username string, or "unknown" if not found
        """
        # Handle if person is empty or None
        if not person:
            return "unknown"

        # Try direct username field first
        if username := person.get("username"):
            return str(username)

        # Try identities.items[0].username
        identities = person.get("identities", {})
        if isinstance(identities, dict):
            items = identities.get("items", [])
            if items and len(items) > 0:
                item = items[0]
                if isinstance(item, dict) and "username" in item:
                    if username := item.get("username"):
                        return str(username)

        # Try email username part (before @)
        if email := person.get("email"):
            username_part = str(email).split("@")[0]
            if username_part:
                return username_part

        # Fallback
        return "unknown"

    def _extract_role(self, role_data: Any) -> str:
        """Extract role name from role data, trying multiple sources.

        Args:
            role_data: Role data from ProjectDB - could be dict, string, or other

        Returns:
            Role name string, or "NoRole" if not found
        """
        if not role_data:
            return "NoRole"

        # If it's already a string, return it
        if isinstance(role_data, str):
            return role_data

        # If it's a dict, try multiple keys
        if isinstance(role_data, dict):
            # Try common role field names
            for key in ["role", "name", "roleName", "role_name"]:
                if key in role_data:
                    value = role_data.get(key)
                    if isinstance(value, str):
                        return value
                    elif isinstance(value, dict):
                        # Recursively try to extract from nested dict
                        for nested_key in ["name", "role"]:
                            if nested_key in value:
                                nested_val = value.get(nested_key)
                                if isinstance(nested_val, str):
                                    return nested_val

        # Fallback
        return "NoRole"

    def add_member(
        self, member: Dict[str, Any], project_id: int | None = None
    ) -> ContextEntity:
        """Add a member to the crate from raw ProjectDB member dict.

        Args:
            member: Member dict with keys: id, person, role, etc.
            project_id: Project ID to include in member identifier
        """
        # Extract person data and username
        person_data = member.get("person", {})
        username = self._extract_username(person_data)

        # Extract role using flexible method
        role_data = member.get("role", {})
        role_name = self._extract_role(role_data)
        role_string = "".join(str(role_name).split())
        member_id = f"{MEMBER_PREFIX}{project_id}/{role_string}/{username}"

        # Check if member already exists in crate
        if member_entity := self.crate.dereference(as_ro_id(member_id)):
            return member_entity

        # Add person to crate
        person_entity = self.add_person(person_data)

        # Create member entity
        member_entity = ContextEntity(self.crate, identifier=member_id, properties=None)
        member_entity["roleName"] = role_name
        member_entity.append_to("member", person_entity)
        member_entity.properties()["@type"] = "OrganizationRole"

        return cast(ContextEntity, self.crate.add(member_entity))

    def add_person(self, person: Dict[str, Any]) -> RoPerson:
        """Add a person to the crate from raw ProjectDB person dict.

        Args:
            person: Person dict with keys: id, email, full_name, username, identities, etc.
        """
        username = self._extract_username(person)

        # Check if person already exists
        if person_entity := self.crate.dereference(as_ro_id(username)):
            return person_entity

        # Build person properties
        person_properties = {
            "name": person.get("full_name", ""),
            "email": person.get("email", ""),
        }

        person_entity = RoPerson(
            self.crate,
            identifier=username,
            properties=person_properties,
        )
        return cast(RoPerson, self.crate.add(person_entity))

    def add_research_drive_service(
        self, drive_data: dict[str, Any] | str
    ) -> ContextEntity:
        """Add a research drive service reference to the crate.

        Args:
            drive_data: Either a string (drive name) or dict with drive properties from ProjectDB
        """
        # Handle both string (legacy) and dict (full data) inputs
        if isinstance(drive_data, str):
            drive_name = drive_data
            drive_properties = {"name": drive_name}
        else:
            drive_name = drive_data.get("name", "unknown")
            # Build properties dict with all available drive attributes
            drive_properties = {
                "name": drive_name,
            }
            # Add optional drive properties if available
            for key in [
                "allocatedGb",
                "freeGb",
                "usedGb",
                "date",
                "firstDay",
                "lastDay",
                "percentageUsed",
            ]:
                if key in drive_data:
                    drive_properties[key] = drive_data[key]

        rd_id = f"{RD_PREFIX}{drive_name}"
        if rd_entity := self.crate.dereference(as_ro_id(rd_id)):
            return rd_entity

        drive_properties["@type"] = "ResearchDriveService"
        rd_entity = ContextEntity(
            self.crate,
            identifier=rd_id,
            properties=drive_properties,
        )
        return cast(ContextEntity, self.crate.add(rd_entity))

    def add_delete_action(
        self,
        project_end_date: Optional[str],
        retention_years: int,
        drive_name: str,
    ) -> ContextEntity:
        """Create a delete action based on project end date and retention period.

        Args:
            project_end_date: ISO format date string for project end date
            retention_years: Years to retain data after project end date
            drive_name: Name of the drive
        """
        # Parse project end date if it's a string
        if isinstance(project_end_date, str):
            try:
                end_date = datetime.fromisoformat(
                    project_end_date.replace("Z", "+00:00")
                )
            except Exception:
                end_date = datetime.now()
        else:
            end_date = project_end_date or datetime.now()

        # Calculate delete date
        delete_date = end_date + relativedelta(years=retention_years)

        # Create delete action entity with proper ID format
        # ID should be: retention_period_for/#research_drive_service/{drive_name}
        delete_id = f"{DELETE_PREFIX}{as_ro_id(f'{RD_PREFIX}{drive_name}')}"
        delete_entity = ContextEntity(
            self.crate,
            identifier=delete_id,
            properties={
                "@type": "DeleteAction",
                "actionStatus": "PotentialActionStatus",
                "endTime": delete_date.strftime("%Y-%m-%d"),
            },
        )

        # Link to drive service
        drive_entity = self.add_research_drive_service(drive_name)
        delete_entity.append_to("targetCollection", drive_entity)

        return cast(ContextEntity, self.crate.add(delete_entity))
