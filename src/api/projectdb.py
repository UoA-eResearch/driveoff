from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, Request

from ceradmin_cli.api_client.eresearch_project import ProjectDBApi


def init_projectdb(app: FastAPI, environment: Optional[str] = None) -> None:
    """Initialize a ProjectDBApi client and attach it to the FastAPI app state.

    The environment can be provided or read from the `PROJECTDB_ENV`
    environment variable (defaults to "test").
    """
    env = environment or os.environ.get("PROJECTDB_ENV", "test")
    client = ProjectDBApi.from_config(environment=env)
    app.state.projectdb = client


def get_projectdb_client(request: Request) -> ProjectDBApi:
    """FastAPI dependency to retrieve the initialized ProjectDBApi client.

    Endpoints can use ``Depends(get_projectdb_client)`` to receive the client.
    """
    client = getattr(request.app.state, "projectdb", None)
    if client is None:
        raise RuntimeError("ProjectDB client not initialised on application state")
    return client
