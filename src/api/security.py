"""Security features for the webserver."""

from pathlib import Path
from typing import Literal

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, APIKeyQuery
from pydantic import BaseModel

HttpAction = Literal["GET", "POST", "PUT"]

_api_key_query = APIKeyQuery(name="api-key", auto_error=False)
_api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


# Ideally set this in main module and inject
API_KEY_PATH = Path.home() / ".driveoff" / "api_keys.json"


class ApiKey(BaseModel):
    """Container for an API key and its metadata (access-level)"""

    value: str
    actions: list[HttpAction]


class KeyList(BaseModel):
    """A set of API keys"""

    keys: list[ApiKey]


def read_api_keys(path: Path = API_KEY_PATH) -> dict[str, ApiKey]:
    """Read a set of API keys from a JSON file."""

    if not path.is_file() or not path.suffix == ".json":
        raise ValueError(f"API key path '{path}' does not refer to a valid JSON file")

    with open(path, encoding="utf-8") as f:
        file_data = f.read()
        key_list = KeyList.model_validate_json(file_data)

    return {key.value: key for key in key_list.keys}


def validate_api_key(
    api_keys: dict[str, ApiKey] = Depends(read_api_keys, use_cache=True),
    api_key_query: str = Security(_api_key_query),
    api_key_header: str = Security(_api_key_header),
) -> ApiKey:
    """Retrieve and validate an API key from the query parameters or HTTP header.

    Args:
        api_key_query: The API key passed as a query parameter.
        api_key_header: The API key passed in the HTTP header.

    Returns:
        The validated API key.

    Raises:
        HTTPException: If the API key is invalid or missing.
    """
    if key_info := api_keys.get(api_key_query):
        return key_info
    if key_info := api_keys.get(api_key_header):
        return key_info

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API Key",
    )


def validate_permissions(action: HttpAction, key: ApiKey) -> None:
    """Validate that an API key has permission for the given action."""
    if action not in key.actions:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"API Key does not have {action} rights.",
        )
