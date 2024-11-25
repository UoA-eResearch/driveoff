# pylint: disable-all
from pathlib import Path
from typing import Tuple

from rocrate.model.contextentity import ContextEntity
from rocrate.model.person import Person as RoPerson
from rocrate.rocrate import ROCrate
from rocrate.utils import is_url
from sqlmodel import SQLModel

from models.member import Member
from models.person import Person
from models.project import Project
from models.role import Role
from models.services import ResearchDriveService

PROJECT_PREFIX = "project/"
ROLE_PREFIX = "role/"
MEMBER_PREFIX = "member/"
RD_PREFIX = "research_drive_service/"


def as_ro_id(obj_id: str) -> str:
    if is_url(obj_id):
        return obj_id
    return f"#{obj_id}"


class ROBuilder:
    """Builder for Project Archive Crate RO-Cratess"""

    crate: ROCrate

    def __init__(self, crate: ROCrate) -> None:
        self.crate = crate

    def add_project(self, project: Project) -> ContextEntity:

        project_id = f"{PROJECT_PREFIX}{project.id}"
        project_entity = ContextEntity(
            crate=self.crate,
            identifier=project_id,
            properties=project.model_dump(exclude={"id,codes,members,research_drives"}),
        )
        project_entity.append_to("identifier", [code.code for code in project.codes])
        project_entity.properties()["@type"] = "Project"
        project_people = [self.add_member(person) for person in project.members]
        project_entity.append_to("members", project_people)
        project_services = [
            self.add_research_drive_service(drive) for drive in project.research_drives
        ]
        project_entity.append_to("services", project_services)
        return self.crate.add(project_entity)

    def add_member(self, member: Member) -> ContextEntity:
        member_id = f"{MEMBER_PREFIX}{member.project_id}/{member.role.name}/{member.person.username}"
        person_entity = self.add_person(member.person)
        member_entity = ContextEntity(self.crate, identifier=member_id, properties=None)
        member_entity["name"] = member.role.name
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
            properties=person.model_dump(exclude={"username, id, identities"}),
        )
        return self.crate.add(person_entity)

    def add_research_drive_service(
        self, rd_service: ResearchDriveService
    ) -> ContextEntity:
        rd_id = f"{RD_PREFIX}{rd_service.name}"
        if rd_entity := self.crate.dereference(as_ro_id(rd_id)):
            return rd_entity
        rd_entity = ContextEntity(
            self.crate,
            identifier=rd_id,
            properties=rd_service.model_dump(exclude={"id,projects"}),
        )
        rd_entity.properties()["@type"] = "ResearchDriveService"
        return self.crate.add(rd_entity)
