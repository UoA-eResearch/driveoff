"""Archive retrieval background worker."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import tarfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

from sqlmodel import Session, select

from api.dependencies import engine
from config import get_settings
from models.retrieval import (
    ACTIVE_RETRIEVAL_STAGES,
    ArchiveRetrieval,
    RetrievalJobStage,
)
from models.submission import ArchiveSubmission
from packaging.archive_reassembly import (
    load_archive_manifest,
    ordered_part_object_keys,
    reassemble_archive_from_manifest,
)
from packaging.manifests import bagit_exists, validate_bag
from service.activescale import (
    download_file_to_disk,
    get_activescale_client_context,
    initiate_object_restore,
    is_object_ready_for_download,
)
from utils.logging import elapsed_ms, log_event


def _transition_retrieval_stage(
    session: Session,
    retrieval: ArchiveRetrieval,
    to_stage: RetrievalJobStage,
    started_at: datetime,
) -> None:
    """Transition a retrieval job to *to_stage*, commit, and log the change."""
    previous_stage = retrieval.stage
    now = datetime.now()
    if to_stage == RetrievalJobStage.RESTORING and retrieval.started_timestamp is None:
        retrieval.started_timestamp = now
    retrieval.stage = to_stage
    retrieval.last_updated_timestamp = now
    session.add(retrieval)
    session.commit()
    log_event(
        logging.INFO,
        "retrieval.stage_transition",
        retrieval_id=retrieval.id,
        drive_name=retrieval.drive_name,
        from_stage=previous_stage.value,
        to_stage=to_stage.value,
        elapsed_ms=elapsed_ms(started_at),
    )


def _parse_retrieved_part_keys(part_keys_json: str | None) -> list[str]:
    """Decode the JSON-encoded list of already-downloaded part object keys."""
    if not part_keys_json:
        return []
    try:
        parsed = json.loads(part_keys_json)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if isinstance(item, str)]


def _persist_retrieved_part_keys(
    session: Session,
    retrieval: ArchiveRetrieval,
    downloaded_keys: list[str],
) -> None:
    """Persist the current list of downloaded part keys to the retrieval record."""
    retrieval.retrieved_part_keys_json = json.dumps(downloaded_keys)
    retrieval.last_updated_timestamp = datetime.now()
    session.add(retrieval)
    session.commit()


async def run_archive_retrieval(retrieval_id: int) -> None:  # pylint: disable=too-many-statements
    """Background task: restore, download, and extract a completed archive.

    Workflow:
      1. RESTORING  - Download the manifest from S3; initiate a restore request
                      for every archive part; poll until all parts are available.
      2. DOWNLOADING - Download each archive part to a local temp directory,
                      persisting progress so a future retry can resume mid-download.
      3. EXTRACTING  - Reassemble the chunked parts into a single .tar.gz; extract
                      into destination_path; validate the resulting BagIt bag;
                      clean up temp files.
      4. COMPLETED / FAILED - Final state written to the ArchiveRetrieval record.
    """
    # Yield to the event loop so uvicorn can flush the HTTP response to the client
    # before this blocking-heavy task begins.
    await asyncio.sleep(0)

    started_at = datetime.now()
    settings = get_settings()

    with Session(engine) as session:
        retrieval: ArchiveRetrieval | None = None
        download_dir: Path | None = None

        try:
            retrieval = session.get(ArchiveRetrieval, retrieval_id)
            if retrieval is None:
                log_event(
                    logging.ERROR,
                    "retrieval.run.record_not_found",
                    retrieval_id=retrieval_id,
                )
                return

            submission = session.get(ArchiveSubmission, retrieval.submission_id)
            if submission is None:
                raise RuntimeError(
                    f"ArchiveSubmission {retrieval.submission_id} not found in database"
                )

            drive_name = submission.drive_name
            manifest_key = submission.archive_manifest_key
            if not manifest_key:
                raise RuntimeError(
                    "Submission has no archive_manifest_key; archive may not have"
                    " uploaded completely"
                )

            object_prefix = submission.archive_object_prefix or f"{drive_name}/"
            bucket_name = settings.activescale_bucket_name

            # Isolated temp directory for this retrieval job (keyed by ID so
            # concurrent retrievals never share scratch space).
            temp_base = Path(settings.archive_temp_base_path).expanduser()
            download_dir = temp_base / "retrieval" / f"{retrieval_id}_{drive_name}"
            download_dir.mkdir(parents=True, exist_ok=True)

            log_event(
                logging.INFO,
                "retrieval.run.started",
                retrieval_id=retrieval_id,
                drive_name=drive_name,
                destination_path=retrieval.destination_path,
                bucket_name=bucket_name,
            )

            # ─── Phase 1: RESTORING ───────────────────────────────────────────
            _transition_retrieval_stage(
                session, retrieval, RetrievalJobStage.RESTORING, started_at
            )

            manifest_local = download_dir / settings.archive_chunk_manifest_file_name
            poll_interval = settings.activescale_restore_poll_interval_seconds
            max_wait = settings.activescale_restore_poll_max_seconds

            # Step 1a: Restore and download the manifest.
            # The manifest itself may be on tape and require a restore before
            # it can be read.  We only need to do this if it has not already
            # been downloaded to the local scratch directory (e.g. on a resume).
            if not manifest_local.exists():
                with get_activescale_client_context() as client:
                    manifest_needs_restore = initiate_object_restore(
                        client,
                        bucket_name,
                        manifest_key,
                        days=settings.activescale_restore_days,
                    )

                if manifest_needs_restore:
                    deadline = datetime.now() + timedelta(seconds=max_wait)
                    while True:
                        with get_activescale_client_context() as client:
                            ready = is_object_ready_for_download(
                                client, bucket_name, manifest_key
                            )
                        if ready:
                            break
                        if datetime.now() >= deadline:
                            raise TimeoutError(
                                f"Archive manifest not restored within {max_wait}s."
                                " Re-submit a retrieval request to try again."
                            )
                        log_event(
                            logging.INFO,
                            "retrieval.restore.manifest.waiting",
                            retrieval_id=retrieval_id,
                            drive_name=drive_name,
                            manifest_key=manifest_key,
                            poll_interval_seconds=poll_interval,
                            elapsed_ms=elapsed_ms(started_at),
                        )
                        await asyncio.sleep(poll_interval)

                with get_activescale_client_context() as client:
                    if not download_file_to_disk(
                        client, bucket_name, manifest_key, manifest_local
                    ):
                        raise RuntimeError(
                            f"Failed to download archive manifest: {manifest_key}"
                        )

            manifest_data = load_archive_manifest(manifest_local)
            part_keys = ordered_part_object_keys(object_prefix, manifest_data)

            # Step 1b: Restore archive parts.
            log_event(
                logging.INFO,
                "retrieval.restore.initiating",
                retrieval_id=retrieval_id,
                drive_name=drive_name,
                part_count=len(part_keys),
                bucket_name=bucket_name,
            )

            # Send restore requests; track only parts that are on tape
            # (parts already in active storage skip the polling loop).
            needs_restore: list[str] = []
            with get_activescale_client_context() as client:
                for part_key in part_keys:
                    if initiate_object_restore(
                        client,
                        bucket_name,
                        part_key,
                        days=settings.activescale_restore_days,
                    ):
                        needs_restore.append(part_key)

            # Poll until all tape-tier parts have been thawed.
            if needs_restore:
                deadline = datetime.now() + timedelta(seconds=max_wait)

                while True:
                    with get_activescale_client_context() as client:
                        all_ready = all(
                            is_object_ready_for_download(client, bucket_name, k)
                            for k in needs_restore
                        )
                    if all_ready:
                        log_event(
                            logging.INFO,
                            "retrieval.restore.complete",
                            retrieval_id=retrieval_id,
                            drive_name=drive_name,
                            elapsed_ms=elapsed_ms(started_at),
                        )
                        break
                    if datetime.now() >= deadline:
                        raise TimeoutError(
                            f"Archive objects not restored within {max_wait}s."
                            " Re-submit a retrieval request to try again."
                        )
                    log_event(
                        logging.INFO,
                        "retrieval.restore.polling",
                        retrieval_id=retrieval_id,
                        drive_name=drive_name,
                        pending_count=len(needs_restore),
                        poll_interval_seconds=poll_interval,
                        elapsed_ms=elapsed_ms(started_at),
                    )
                    await asyncio.sleep(poll_interval)

            # ─── Phase 2: DOWNLOADING ─────────────────────────────────────────
            _transition_retrieval_stage(
                session, retrieval, RetrievalJobStage.DOWNLOADING, started_at
            )

            already_downloaded = _parse_retrieved_part_keys(
                retrieval.retrieved_part_keys_json
            )

            with get_activescale_client_context() as client:
                for part_key in part_keys:
                    if part_key in already_downloaded:
                        log_event(
                            logging.DEBUG,
                            "retrieval.download.part.skip",
                            retrieval_id=retrieval_id,
                            part_key=part_key,
                        )
                        continue

                    # Derive local filename from the trailing segment of the object key.
                    part_filename = part_key.removeprefix(object_prefix)
                    dest = download_dir / part_filename

                    log_event(
                        logging.INFO,
                        "retrieval.download.part.start",
                        retrieval_id=retrieval_id,
                        part_key=part_key,
                        dest=str(dest),
                        elapsed_ms=elapsed_ms(started_at),
                    )

                    if not download_file_to_disk(client, bucket_name, part_key, dest):
                        raise RuntimeError(
                            f"Failed to download archive part: {part_key}"
                        )

                    already_downloaded.append(part_key)
                    _persist_retrieved_part_keys(session, retrieval, already_downloaded)

            # ─── Phase 3: EXTRACTING ──────────────────────────────────────────
            _transition_retrieval_stage(
                session, retrieval, RetrievalJobStage.EXTRACTING, started_at
            )

            reassembled_tar = download_dir / f"{drive_name}.tar.gz"
            reassemble_archive_from_manifest(
                parts_dir=download_dir,
                manifest_path=manifest_local,
                output_tar_path=reassembled_tar,
                verify_parts=True,
            )

            log_event(
                logging.INFO,
                "retrieval.extract.start",
                retrieval_id=retrieval_id,
                drive_name=drive_name,
                tar_path=str(reassembled_tar),
                elapsed_ms=elapsed_ms(started_at),
            )

            dest_path = Path(retrieval.destination_path)
            with tarfile.open(reassembled_tar, "r:gz") as tar:
                tar.extractall(path=dest_path, filter="data")

            # Validate BagIt integrity of the extracted archive.
            # ``source_root`` from the manifest tells us the top-level directory
            # name that was stored in the tar (mirrors tarfile.add arcname).
            source_root = str(manifest_data.get("source_root", drive_name))
            extracted_bag_path = dest_path / source_root
            if bagit_exists(extracted_bag_path):
                validate_bag(extracted_bag_path)
                log_event(
                    logging.INFO,
                    "retrieval.bagit.validated",
                    retrieval_id=retrieval_id,
                    bag_path=str(extracted_bag_path),
                    elapsed_ms=elapsed_ms(started_at),
                )
            else:
                log_event(
                    logging.WARNING,
                    "retrieval.bagit.not_found",
                    retrieval_id=retrieval_id,
                    expected_path=str(extracted_bag_path),
                )

            # Clean up scratch space now that extraction has been verified.
            shutil.rmtree(download_dir, ignore_errors=True)
            download_dir = None

            # Mark COMPLETED
            now = datetime.now()
            retrieval.stage = RetrievalJobStage.COMPLETED
            retrieval.completed_timestamp = now
            retrieval.last_updated_timestamp = now
            session.add(retrieval)
            session.commit()

            log_event(
                logging.INFO,
                "retrieval.completed",
                retrieval_id=retrieval_id,
                drive_name=drive_name,
                destination_path=retrieval.destination_path,
                elapsed_ms=elapsed_ms(started_at),
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            if download_dir is not None:
                shutil.rmtree(download_dir, ignore_errors=True)

            if retrieval is not None:
                now = datetime.now()
                retrieval.stage = RetrievalJobStage.FAILED
                retrieval.failure_reason = str(e)
                retrieval.failed_timestamp = now
                retrieval.last_updated_timestamp = now
                session.add(retrieval)
                session.commit()

            log_event(
                logging.ERROR,
                "retrieval.failed",
                retrieval_id=retrieval_id,
                error_type=type(e).__name__,
                error=str(e),
                exc_info=True,
            )


def _reconcile_interrupted_retrievals() -> None:
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
