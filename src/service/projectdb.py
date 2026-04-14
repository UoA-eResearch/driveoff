"""ProjectDB client initialization and dependency injection for FastAPI."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request

from config import get_settings
from service.projectdb_client import ProjectDBClient


def init_projectdb(app: FastAPI) -> None:
    """Initialize a ProjectDBClient and attach it to the FastAPI app state.

    Reads base_url and api_key from the application Settings (sourced from
    the mode-specific .env files).
    """
    settings = get_settings()
    print(
        f"Initializing ProjectDB client with base URL: {settings.projectdb_base_url}"
    )  # Debug logging
    if not settings.projectdb_base_url or not settings.projectdb_api_key:
        raise ValueError(
            "PROJECTDB_BASE_URL and PROJECTDB_API_KEY must be set in the environment."
        )
    client = ProjectDBClient(
        base_url=settings.projectdb_base_url,
        api_key=settings.projectdb_api_key,
    )
    app.state.projectdb = client


def get_projectdb_client(request: Request) -> Any:
    """FastAPI dependency to retrieve the initialized ProjectDBClient.

    Endpoints can use ``Depends(get_projectdb_client)`` to receive the client.
    """
    client = getattr(request.app.state, "projectdb", None)
    if client is None:
        raise RuntimeError("ProjectDB client not initialised on application state")
    return client
