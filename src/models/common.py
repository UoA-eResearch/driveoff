"""Classes common to other models."""

from enum import Enum

# The set of default retention periods we are offering.
DEFAULT_RETENTION_PERIODS = set([6, 10, 20, 26])


class DataClassification(str, Enum):
    """Data classification labels defined in Research
    Data Management Policy."""

    PUBLIC = "Public"
    INTERNAL = "Internal"
    SENSITIVE = "Sensitive"
    RESTRICTED = "Restricted"
