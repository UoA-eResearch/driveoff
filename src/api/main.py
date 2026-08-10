"""FastAPI application entry point."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter

from asgi_correlation_id import CorrelationIdMiddleware, correlation_id
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from api.cors import add_cors_middleware
from api.dependencies import create_db_and_tables, engine
from api.routers import drives, retrievals, submissions
from service.activescale import init_activescale
from service.projectdb import init_projectdb
from utils.job_reconciliation import (
    reconcile_interrupted_archiving_jobs,
    reconcile_interrupted_retrieval_jobs,
)
from utils.logging import configure_logging, log_event
from utils.paths import validate_archive_path_configuration

configure_logging()

ENDPOINT_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncGenerator[None]:
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
        reconcile_interrupted_archiving_jobs()
    except Exception as e:  # pylint: disable=broad-exception-caught
        log_event(
            logging.WARNING,
            "startup.reconciliation_failed",
            error=str(e),
            exc_info=True,
        )

    try:
        reconcile_interrupted_retrieval_jobs()
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
app.add_middleware(CorrelationIdMiddleware, header_name="X-Request-ID")


def _extract_error_detail(response: Response) -> str | None:
    """Extract a concise error detail from JSON error responses when available."""
    if response.status_code < 400:
        return None

    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type:
        return None

    body_bytes = getattr(response, "body", None)
    if not isinstance(body_bytes, (bytes, bytearray)) or not body_bytes:
        return None

    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except UnicodeDecodeError, json.JSONDecodeError:
        return None

    detail = payload.get("detail") if isinstance(payload, dict) else None
    if detail is None:
        return None
    if isinstance(detail, str):
        return detail
    return str(detail)


@app.middleware("http")
async def request_logging_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Log all API requests with method, path, status code, and latency.

    Also catches and logs unhandled exceptions so API-level failures have a
    consistent JSON 500 response and a centralized log event.
    """
    route_name = request.scope.get("path")
    client_host = request.client.host if request.client is not None else None

    started_at = perf_counter()
    try:
        response = await call_next(request)
    except Exception as exception:  # pylint: disable=broad-exception-caught
        request_id = request.headers.get("x-request-id") or correlation_id.get()
        log_event(
            logging.ERROR,
            "api.unhandled_exception",
            method=request.method,
            path=request.url.path,
            query=request.url.query,
            route_name=route_name,
            client_host=client_host,
            request_id=request_id,
            error=str(exception),
            error_type=type(exception).__name__,
            exc_info=True,
        )
        response = JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

    elapsed_ms = int((perf_counter() - started_at) * 1000)
    level = logging.INFO if response.status_code < 400 else logging.WARNING
    error_detail = _extract_error_detail(response)
    request_id = request.headers.get("x-request-id") or correlation_id.get()
    if request_id is not None and "X-Request-ID" not in response.headers:
        response.headers["X-Request-ID"] = request_id

    log_event(
        level,
        "api.request.completed",
        method=request.method,
        path=request.url.path,
        query=request.url.query,
        route_name=route_name,
        status_code=response.status_code,
        client_host=client_host,
        request_id=request_id,
        elapsed_ms=elapsed_ms,
        error_detail=error_detail,
    )
    return response


add_cors_middleware(app)

app.include_router(drives.router, prefix=ENDPOINT_PREFIX)
app.include_router(submissions.router, prefix=ENDPOINT_PREFIX)
app.include_router(retrievals.router, prefix=ENDPOINT_PREFIX)
