"""Definition of endpoints/routers for the webserver."""

import re
from typing import Annotated, Any

from fastapi import FastAPI, Security
from pydantic.functional_validators import AfterValidator

from api.security import ApiKey, validate_api_key, validate_permissions
from config.config import settings

app = FastAPI()

# Define a regex pattern for Research Drive identifiers
RESEARCH_DRIVE_REGEX = re.compile(r"res[a-z]{3}[0-9]{9}-[a-zA-Z0-9-_]+")

ENDPOINT_PREFIX = "/api/v1"


def validate_resdrive_identifier(drive_id: str) -> str:
    """Check if the string is a valid Research Drive identifier."""
    if RESEARCH_DRIVE_REGEX.match(drive_id) is None:
        raise ValueError(f"'{drive_id}' is not a valid Research Drive identifier.")

    return drive_id

# Annotate ResearchDriveID type to validate
ResearchDriveID = Annotated[str, AfterValidator(validate_resdrive_identifier)]

@app.post(ENDPOINT_PREFIX + "/resdriveinfo")
async def set_drive_info(
    drive_id: ResearchDriveID,
    ro_crate_metadata: dict[str, Any],
    api_key: ApiKey = Security(validate_api_key),
) -> dict[str, str]:
    """Submit initial RO-Crate metadata. NOTE: this may also need to accept the manifest data."""
    validate_permissions("POST", api_key)
    _ = ro_crate_metadata
    return {
        "message": f"Received RO-Crate metadata for {drive_id}.",
        "data": ro_crate_metadata,
    }


@app.put(ENDPOINT_PREFIX + "/resdriveinfo")
async def append_drive_info(
    drive_id: ResearchDriveID,
    ro_crate_metadata: dict[str, str],
    api_key: ApiKey = Security(validate_api_key),
) -> dict[str, str]:
    """Submit additional RO-Crate metadata. NOTE: this may need to accept manifest deltas too."""
    if settings.environment == "production":
        validate_permissions("PUT", api_key)

    _ = ro_crate_metadata
    return {
        "message": f"Received additional RO-Crate metadata for {drive_id}.",
    }


@app.get(ENDPOINT_PREFIX + "/resdriveinfo")
async def get_drive_info(
    drive_id: ResearchDriveID,
    api_key: ApiKey = Security(validate_api_key),
) -> dict[str, str]:
    """Retrieve information about the specified Research Drive."""
    if settings.environment == "production":
        validate_permissions("GET", api_key)

    return {
        "drive_id": drive_id,
        "ro_crate": "TODO: Make RO-Crate",
        "manifest": "TODO: Make manifest",
    }
