import re
from typing import Annotated

from fastapi import FastAPI
from pydantic.functional_validators import AfterValidator

app = FastAPI()


RESEARCH_DRIVE_REGEX = re.compile(r"res[a-z]{3}[0-9]{9}-[a-zA-Z0-9-_]+")


def validate_resdrive_identifier(drive_id: str) -> str:
    """Check if the string is a valid Research Drive identifier."""
    if RESEARCH_DRIVE_REGEX.match(drive_id) is None:
        raise ValueError(f"'{drive_id}' is not a valid Research Drive identifier.")

    return drive_id


ResearchDriveID = Annotated[str, AfterValidator(validate_resdrive_identifier)]


@app.get("/resdrive")
def get_drive_info(drive_id: ResearchDriveID) -> dict[str, str]:
    return {
        "drive_id": drive_id,
        "ro_crate": "TODO: Make RO-Crate",
        "manifest": "TODO: Make manifest",
    }
