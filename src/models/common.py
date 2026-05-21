"""Classes common to other models."""

import re
from datetime import datetime
from enum import Enum
from typing import Annotated

from dateutil.relativedelta import relativedelta
from pydantic.functional_validators import AfterValidator

# The set of default retention periods we are offering.
DEFAULT_RETENTION_PERIODS = {6, 10, 20, 26}

RESEARCH_DRIVE_REGEX = re.compile(r"res[a-z]{3}[0-9]{9}[-_][a-zA-Z0-9._-]+")


def validate_resdrive_name(drive_name: str) -> str:
    """Check if the string is a valid Research Drive name."""
    if RESEARCH_DRIVE_REGEX.fullmatch(drive_name) is None:
        raise ValueError(f"'{drive_name}' is not a valid Research Drive name.")

    return drive_name


def calculate_retention_end_date(start_date: datetime, retention_years: int) -> str:
    """Return the date on which retained data may be deleted.

    Args:
        start_date: The starting date (typically project end date or today).
        retention_years: Number of full years to add.
    """
    return (start_date + relativedelta(years=retention_years)).strftime("%Y-%m-%d")


ResearchDriveName = Annotated[str, AfterValidator(validate_resdrive_name)]


class DataClassification(str, Enum):
    """Data classification labels defined in Research
    Data Management Policy."""

    PUBLIC = "Public"
    INTERNAL = "Internal"
    SENSITIVE = "Sensitive"
    RESTRICTED = "Restricted"
