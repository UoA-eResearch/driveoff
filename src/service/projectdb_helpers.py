"""ProjectDB response projection helpers.

These functions convert raw ProjectDB API dicts into typed response models.
They are used by both the API routers (for drive info responses) and the
submission worker (for building RO-Crate metadata).
"""

from __future__ import annotations

import logging
from typing import Any

from models.response import CodeResponse, MemberResponse, PersonResponse, RoleResponse
from utils.logging import log_event


def build_codes(project_data: dict[str, Any]) -> list[CodeResponse]:
    """Extract project codes from project data."""
    codes_items = project_data.get("codes", {})
    if isinstance(codes_items, dict):
        codes_items = codes_items.get("items", [])
    return [CodeResponse(id=c.get("id"), code=c["code"]) for c in codes_items]


def build_members(members_raw: list[dict[str, Any]]) -> list[MemberResponse]:
    """Convert raw member dicts into MemberResponse objects."""
    members = []
    for m in members_raw:
        person = m.get("person", {})
        username = None
        for ident in person.get("identities", {}).get("items", []):
            uname = ident.get("username", "")
            if uname and "@" not in uname:
                username = uname
                break

        members.append(
            MemberResponse(
                role=RoleResponse(
                    id=m.get("role", {}).get("id"),
                    name=m["role"]["name"],
                ),
                person=PersonResponse(
                    id=person.get("id"),
                    email=person.get("email"),
                    full_name=person.get("full_name", ""),
                    username=username,
                ),
            )
        )
    return members


def filter_member_identities(members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter out identities where the username is an email address."""
    try:
        members = [
            {
                **member,
                "person": {
                    **member.get("person", {}),
                    "identities": {
                        "items": [
                            item
                            for item in member.get("person", {})
                            .get("identities", {})
                            .get("items", [])
                            if not item.get("username", "").endswith("@auckland.ac.nz")
                        ]
                    },
                },
            }
            for member in members
        ]
    except (TypeError, AttributeError) as e:
        # Log error but don't fail the whole process - just return unfiltered members
        log_event(logging.WARNING, "members.filter_failed", error=str(e))
    return members


def get_project_owner_email(members: Any) -> str:
    """Get the project owner's email from the members list."""
    for member in members:
        if member["role"]["name"] == "Project Owner":
            return member["person"]["email"] or "Unknown"
    return "Unknown"
