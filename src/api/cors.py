"""Module for CORS-related functionality."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings


def add_cors_middleware(app: FastAPI) -> None:
    """Adds CORS middleware to the server app.

    Args:
        app (FastAPI): The FastAPI app to add middleware to.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_allow_host,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
