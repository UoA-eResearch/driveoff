from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ALLOWED_CORS_ORIGINS = [
    # The current host for the web app.
    "https://uoa-eresearch.github.io",
    # When running locally.
    "http://localhost:5173",
]


def add_cors_middleware(app: FastAPI):
    """Adds CORS middleware to the server app.

    Args:
        app (FastAPI): The FastAPI app to add middleware to.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
