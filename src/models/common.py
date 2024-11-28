"""Classes common to other models."""

from enum import Enum


class DataClassification(str, Enum):
    """Data classification labels defined in Research
    Data Management Policy."""

    PUBLIC = "Public"
    INTERNAL = "Internal"
    SENSITIVE = "Sensitive"
    RESTRICTED = "Restricted"
