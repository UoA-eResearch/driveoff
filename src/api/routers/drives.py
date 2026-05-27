"""Drive info endpoint."""

from __future__ import annotations

from typing import Any

import requests
from fastapi import APIRouter, HTTPException, Security, status

from api.dependencies import ProjectDbDep
from api.security import ApiKey, validate_api_key, validate_permissions
from models.common import ResearchDriveName
from models.response import (
    DriveInfoResponse,
    DriveResponse,
    ErrorResponse,
    ProjectResponse,
)
from service.projectdb_helpers import (
    build_codes,
    build_members,
    filter_member_identities,
)

router = APIRouter()


@router.get(
    "/driveinfo",
    response_model=DriveInfoResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or missing API key"},
        404: {"model": ErrorResponse, "description": "Drive or project not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_drive_info(
    drive_name: ResearchDriveName,
    projectdb: ProjectDbDep,
    api_key: ApiKey = Security(validate_api_key),
) -> DriveInfoResponse:
    """Retrieve drive and project info from ProjectDB for display.

    Looks up the drive by name, resolves the associated project,
    and returns combined info including members and codes.
    """
    validate_permissions("GET", api_key)

    # Look up drive in ProjectDB
    try:
        drive_data: Any = projectdb.get_research_drive_by_name(drive_name)
        if not drive_data:
            raise HTTPException(
                status_code=404,
                detail=f"Research Drive {drive_name} not found in ProjectDB.",
            )
        if isinstance(drive_data, list):
            drive_data = drive_data[0]
    except (requests.RequestException, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "ProjectDB request failed while fetching drive"
                f" {drive_name}: {str(e)}"
            ),
        ) from e

    # Resolve project from drive
    try:
        drive_projects = projectdb.get_research_drive_projects(
            drive_data["id"], expand=["project"]
        )
    except (requests.RequestException, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "ProjectDB request failed while fetching projects"
                f" for drive {drive_name}: {str(e)}"
            ),
        ) from e

    if not drive_projects or len(drive_projects) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No projects associated with drive {drive_name}",
        )

    # Use the first project (single-project drives are the common case)
    project_id = drive_projects[0]["project"]["id"]

    # Fetch full project data with codes and services
    try:
        project_data = projectdb.get_project(
            pid=project_id,
            expand=["codes", "status", "services"],
        )
    except (requests.RequestException, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "ProjectDB request failed while fetching project"
                f" {project_id}: {str(e)}"
            ),
        ) from e

    # Fetch members
    try:
        members_raw = projectdb.get_project_members(
            project_id,
            expand=["person", "role", "person.identities", "person.status"],
        )
        members_raw = filter_member_identities(members_raw)
    except (requests.RequestException, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "ProjectDB request failed while fetching members"
                f" for project {project_id}: {str(e)}"
            ),
        ) from e

    # Build drive response, preferring service-level data (has first_day/last_day)
    drive_service = None
    for rd in project_data.get("services", {}).get("research_drive", []):
        if rd.get("name") == drive_name:
            drive_service = rd
            break

    drive_resp = DriveResponse(
        id=drive_data["id"],
        name=drive_name,
        allocated_gb=drive_data["allocated_gb"],
        used_gb=drive_data["used_gb"],
        free_gb=drive_data["free_gb"],
        percentage_used=drive_data["percentage_used"],
        date=drive_data["date"],
        first_day=drive_service.get("first_day") if drive_service else None,
        last_day=drive_service.get("last_day") if drive_service else None,
    )

    codes = build_codes(project_data)
    members = build_members(members_raw)
    project_resp = ProjectResponse(
        id=project_data["id"],
        title=project_data.get("title", ""),
        description=project_data.get("description", ""),
        division=project_data.get("division", ""),
        start_date=project_data.get("start_date", ""),
        end_date=project_data.get("end_date", ""),
        codes=codes,
        members=members,
    )

    return DriveInfoResponse(drive=drive_resp, project=project_resp)
