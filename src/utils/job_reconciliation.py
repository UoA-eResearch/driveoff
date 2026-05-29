"""Job reconciliation utilities for handling interrupted archiving and retrieval jobs."""

import logging
from datetime import datetime
from typing import Any, cast

from sqlmodel import Session, select

from api.dependencies import engine
from models.retrieval import (
    ACTIVE_RETRIEVAL_STAGES,
    ArchiveRetrieval,
    RetrievalJobStage,
)
from models.submission import ACTIVE_STAGES, ArchiveJobStage, ArchiveSubmission
from utils.logging import log_event


def reconcile_interrupted_archiving_jobs() -> None:
    """Mark any jobs that were active when the process last exited as abandoned.

    FastAPI BackgroundTasks are volatile; if the process restarts while a job
    is in an active stage (queued/running/uploading/cleanup) that work is lost.
    We surface this to operators as 'abandoned' so they can trigger a manual retry.
    """
    with Session(engine) as session:
        active_stage_values = [s.value for s in ACTIVE_STAGES]
        stage_column = cast(Any, ArchiveSubmission.stage)
        interrupted = session.exec(
            select(ArchiveSubmission).where(stage_column.in_(active_stage_values))
        ).all()
        if not interrupted:
            return
        now = datetime.now()
        for submission in interrupted:
            previous_stage = submission.stage
            log_event(
                logging.WARNING,
                "submission.abandoned_on_startup",
                submission_id=submission.id,
                drive_name=submission.drive_name,
                previous_stage=previous_stage,
            )
            submission.stage = ArchiveJobStage.ABANDONED
            submission.failure_reason = (
                f"Process restarted while job was in stage '{previous_stage.value}'."
                " Retry this job to resume."
            )
            submission.failed_timestamp = now
            submission.last_updated_timestamp = now
            session.add(submission)
        session.commit()
        log_event(
            logging.WARNING,
            "startup.reconciliation_complete",
            abandoned_count=len(interrupted),
        )


def reconcile_interrupted_retrieval_jobs() -> None:
    """Mark any retrieval jobs that were active when the process last exited as failed.

    FastAPI BackgroundTasks are volatile; if the process restarts while a retrieval
    is in an active stage the work is permanently lost.  We surface this as 'failed'
    so operators know to re-submit a retrieval request.
    """
    with Session(engine) as session:
        active_stage_values = [s.value for s in ACTIVE_RETRIEVAL_STAGES]
        stage_column = cast(Any, ArchiveRetrieval.stage)
        interrupted = session.exec(
            select(ArchiveRetrieval).where(stage_column.in_(active_stage_values))
        ).all()
        if not interrupted:
            return
        now = datetime.now()
        for retrieval in interrupted:
            previous_stage = retrieval.stage
            log_event(
                logging.WARNING,
                "retrieval.abandoned_on_startup",
                retrieval_id=retrieval.id,
                drive_name=retrieval.drive_name,
                previous_stage=previous_stage.value,
            )
            retrieval.stage = RetrievalJobStage.FAILED
            retrieval.failure_reason = (
                f"Process restarted while retrieval was in stage '{previous_stage.value}'."
                " Re-submit a retrieval request to restart."
            )
            retrieval.failed_timestamp = now
            retrieval.last_updated_timestamp = now
            session.add(retrieval)
        session.commit()
        log_event(
            logging.WARNING,
            "startup.retrieval_reconciliation_complete",
            failed_count=len(interrupted),
        )
