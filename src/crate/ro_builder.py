# pylint: disable-all
from pathlib import Path
from typing import Tuple

from dateutil.relativedelta import relativedelta
from rocrate.model.contextentity import ContextEntity
from rocrate.model.person import Person as RoPerson
from rocrate.rocrate import ROCrate
from rocrate.utils import is_url
from sqlmodel import SQLModel

from models.member import Member
from models.person import Person, ROCratePerson
from models.project import Project, ROCrateProject
from models.role import Role
from models.services import ResearchDriveService, ROCrateResDriveService
from models.submission import (
    DriveOffboardSubmission,
    ROCrateDeleteAction,
    ROCrateDriveOffboardSubmission,
)

PROJECT_PREFIX = "project/"
ROLE_PREFIX = "role/"
MEMBER_PREFIX = "member/"
RD_PREFIX = "research_drive_service/"
DELETE_BUFFER = 1  # Add extra years to delete actions
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
        self, project: Project, project_submission: DriveOffboardSubmission
    ) -> ContextEntity:

        project_submissions = [
            drive.submission for drive in project.research_drives if drive.submission
        ]

        if (
            not project_submission.is_completed
            or project_submission not in project_submissions
        ):
            raise ValueError(
                "Project form has not been completed RO-Crate cannot be constructed"
            )

        sumbission_properties = ROCrateDriveOffboardSubmission(
            project_submission
        ).model_dump(exclude={"id","isCompleted"}, by_alias=True, exclude_none=True)

        crate_project = ROCrateProject(project)
        project_properties = crate_project.model_dump(
            exclude={"id", "codes"}, by_alias=True, exclude_none=True
        )
        project_id = f"{PROJECT_PREFIX}{crate_project.id}"
        project_entity = ContextEntity(
            crate=self.crate,
            identifier=project_id,
            properties=project_properties | sumbission_properties,
        )
        # generate delete action from project_submission
        project_entity.append_to("identifier", [code.code for code in project.codes])
        # update project from form content models
        project_people = [self.add_member(person) for person in project.members]
        project_entity.append_to("member", project_people)
        project_services = [
            self.add_research_drive_service(drive) for drive in project.research_drives
        ]
        project_entity.append_to("services", project_services)
        delete_action = self.add_delete_action(
            submission=project_submission, project=project
        )
        project_entity.append_to("actions", delete_action)
        return self.crate.add(project_entity)

    def add_member(self, member: Member) -> ContextEntity:
        def construct_member_id(member: Member) -> str:
            if member.role:
                role_string = "".join(member.role.name.split())
                return f"{MEMBER_PREFIX}{member.project_id}/{role_string}/{member.person.username}"
            else:
                return f"{MEMBER_PREFIX}{member.project_id}/{member.person.username}"

        member_id = construct_member_id(member)
        if member_entity := self.crate.dereference(as_ro_id(member_id)):
            return member_entity
        person_entity = self.add_person(member.person)
        member_entity = ContextEntity(self.crate, identifier=member_id, properties=None)
        member_entity["name"] = member.role.name if member.role else "No Role"
        member_entity.append_to("member", person_entity)
        member_entity.properties()["@type"] = "OrganizationRole"
        return self.crate.add(member_entity)

    def add_person(self, person: Person) -> RoPerson:
        """Add a person to the crate, if the person does not already exist"""
        person_id = person.username
        if person_entity := self.crate.dereference(as_ro_id(person_id)):
            return person_entity
        person_entity = RoPerson(
            self.crate,
            identifier=person_id,
            properties=ROCratePerson(person).model_dump(
                by_alias=True, exclude_none=True
            ),
        )
        return self.crate.add(person_entity)

    def add_research_drive_service(
        self, rd_service: ResearchDriveService
    ) -> ContextEntity:
        crate_rd_service = ROCrateResDriveService(rd_service)
        rd_id = f"{RD_PREFIX}{crate_rd_service.name}"
        if rd_entity := self.crate.dereference(as_ro_id(rd_id)):
            return rd_entity
        rd_entity = ContextEntity(
            self.crate,
            identifier=rd_id,
            properties=crate_rd_service.model_dump(
                by_alias=True, exclude={"id"}, exclude_none=True
            ),
        )
        return self.crate.add(rd_entity)

    def add_delete_action(
        self, submission: DriveOffboardSubmission, project: Project
    ) -> ContextEntity:
        if submission.drive is None:
            raise (
                ValueError(
                    f"Submission{submission.id} does not refer to a research drive"
                )
            )
        drive = self.add_research_drive_service(submission.drive)
        end_date = project.end_date + relativedelta(
            years=+submission.retention_period_years
        )
        delete_action = ROCrateDeleteAction.model_validate({"end_time": end_date})
        delete_entity = ContextEntity(
            self.crate,
            identifier=f"{DELETE_PREFIX}{drive.id}",
            properties=delete_action.model_dump(by_alias=True, exclude_none=True),
        )
        delete_entity.append_to("targetCollection", drive)
        return self.crate.add(delete_entity)
