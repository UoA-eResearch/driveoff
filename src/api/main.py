"""Definition of endpoints/routers for the webserver."""

import re
from typing import Annotated, Any

from fastapi import FastAPI
from pydantic.functional_validators import AfterValidator

app = FastAPI()


RESEARCH_DRIVE_REGEX = re.compile(r"res[a-z]{3}[0-9]{9}-[a-zA-Z0-9-_]+")

ENDPOINT_PREFIX = "/api/v1"


def validate_resdrive_identifier(drive_id: str) -> str:
    """Check if the string is a valid Research Drive identifier."""
    if RESEARCH_DRIVE_REGEX.match(drive_id) is None:
        raise ValueError(f"'{drive_id}' is not a valid Research Drive identifier.")

    return drive_id


ResearchDriveID = Annotated[str, AfterValidator(validate_resdrive_identifier)]


@app.post(ENDPOINT_PREFIX + "/resdriveinfo")
def set_drive_info(
    drive_id: ResearchDriveID, ro_crate_metadata: dict[str, Any]
) -> dict[str, str]:
    """Submit initial RO-Crate metadata. NOTE: this may also need to accept the manifest data."""
    _ = ro_crate_metadata
    return {
        "message": f"Received RO-Crate metadata for {drive_id}.",
    }


@app.put(ENDPOINT_PREFIX + "/resdriveinfo")
def append_drive_info(
    drive_id: ResearchDriveID, ro_crate_metadata: dict[str, str]
) -> dict[str, str]:
    """Submit additional RO-Crate metadata. NOTE: this may need to accept manifest deltas too."""
    _ = ro_crate_metadata
    return {
        "message": f"Received additional RO-Crate metadata for {drive_id}.",
    }


@app.get(ENDPOINT_PREFIX + "/resdriveinfo")
def get_drive_info(drive_id: ResearchDriveID) -> dict[str, str]:
    """Retrieve information about the specified Research Drive."""
    return {
        "drive_id": drive_id,
        "ro_crate": "TODO: Make RO-Crate",
        "manifest": "TODO: Make manifest",
    }
