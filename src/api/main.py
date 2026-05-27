"""FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.cors import add_cors_middleware
from api.dependencies import create_db_and_tables, engine
from api.routers import drives, retrievals, submissions
from service.activescale import init_activescale
from service.projectdb import init_projectdb
from utils.logging import configure_logging, log_event
from utils.paths import validate_archive_path_configuration
from workers.retrieval_worker import _reconcile_interrupted_retrievals
from workers.submission_worker import _reconcile_interrupted_jobs

configure_logging()

ENDPOINT_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncGenerator[None, None]:
    """Lifecycle method for the API.

    Creates DB tables and initialises service clients during application startup
    so routes can depend on them.  Also reconciles any archive jobs that were
    in-flight when the process last exited so operators can retry them.
    """
    create_db_and_tables()
    validate_archive_path_configuration()
    init_projectdb(app_instance)
    init_activescale(app_instance)

    try:
        _reconcile_interrupted_jobs()
    except Exception as e:  # pylint: disable=broad-exception-caught
        log_event(
            logging.WARNING,
            "startup.reconciliation_failed",
            error=str(e),
            exc_info=True,
        )

    try:
        _reconcile_interrupted_retrievals()
    except Exception as e:  # pylint: disable=broad-exception-caught
        log_event(
            logging.WARNING,
            "startup.retrieval_reconciliation_failed",
            error=str(e),
            exc_info=True,
        )

    yield
    engine.dispose()


app = FastAPI(lifespan=lifespan, title="Research Drive Archive API", version="1.0.0")

add_cors_middleware(app)

app.include_router(drives.router, prefix=ENDPOINT_PREFIX)
app.include_router(submissions.router, prefix=ENDPOINT_PREFIX)
app.include_router(retrievals.router, prefix=ENDPOINT_PREFIX)
