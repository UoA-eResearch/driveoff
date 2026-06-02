"""Archive submission background worker."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session

from api.dependencies import engine
from config import get_settings
from models.common import calculate_retention_end_date
from models.submission import ArchiveJobStage, ArchiveSubmission
from packaging.archive_chunks import build_chunked_tar_archive
from packaging.crate.ro_builder import ROBuilder
from packaging.crate.ro_loader import ROLoader
from packaging.manifests import bag_directory, bagit_exists, create_manifests_directory
from service.activescale import (
    get_activescale_client_context,
    object_exists,
    upload_file,
)
from service.projectdb_client import ProjectDBClient
from service.projectdb_helpers import filter_member_identities, get_project_owner_emails
from utils.logging import elapsed_ms, log_event
from utils.paths import resolve_archive_output_location, resolve_drive_path_for_archive
from workers import parse_part_keys_json


def _cleanup_job_artifacts(
    drive_name: str, output_location: Path | None
) -> tuple[bool, str | None]:
    """Delete generated local archive artifacts for a submission.

    This intentionally only removes generated artifacts in the archive output
    area and does not remove source drive content.
    """
    if output_location is None:
        log_event(
            logging.INFO,
            "submission.cleanup.skipped",
            drive_name=drive_name,
            reason="no output path resolved",
        )
        return True, None

    if not output_location.exists():
        log_event(
            logging.INFO,
            "submission.cleanup.skipped",
            drive_name=drive_name,
            output_location=str(output_location),
            reason="path does not exist",
        )
        return True, None

    try:
        if output_location.is_file():
            output_location.unlink()
        else:
            shutil.rmtree(output_location)
    except OSError as e:  # pragma: no cover - best effort cleanup
        cleanup_error = f"{output_location}: {e}"
        log_event(
            logging.WARNING,
            "submission.cleanup.failed",
            drive_name=drive_name,
            output_location=str(output_location),
            cleanup_error=cleanup_error,
        )
        return False, cleanup_error

    log_event(
        logging.INFO,
        "submission.cleanup.completed",
        drive_name=drive_name,
        output_location=str(output_location),
    )
    return True, None


def _persist_uploaded_part_keys(
    session: Session,
    submission: ArchiveSubmission,
    uploaded_keys: list[str],
) -> None:
    """Persist uploaded part key progress so retries can resume."""
    submission.archive_part_keys_json = json.dumps(uploaded_keys)
    submission.last_updated_timestamp = datetime.now()
    session.add(submission)
    session.commit()


def _upload_chunked_archive_parts(  # pylint: disable=too-many-arguments
    *,
    session: Session,
    submission: ArchiveSubmission,
    client: Any,
    bucket_name: str,
    object_prefix: str,
    archive_parts_dir: Path,
    timeout_seconds: int,
) -> tuple[bool, list[str]]:
    """Upload chunked archive part files with resume support.

    A part key is considered already uploaded only if:
    - it appears in persisted submission state, and
    - the key currently exists in object storage.
    """
    part_files = sorted(archive_parts_dir.glob("*.tar.gz.part-*"))
    uploaded_keys = parse_part_keys_json(submission.archive_part_keys_json)

    for part_file in part_files:
        part_key = f"{object_prefix}{part_file.name}"
        if part_key in uploaded_keys:
            exists, _ = object_exists(client, bucket_name, part_key)
            if exists:
                log_event(
                    logging.INFO,
                    "crate.upload.part.skipped",
                    submission_id=submission.id,
                    drive_name=submission.drive_name,
                    part_key=part_key,
                    reason="already_uploaded",
                )
                continue

        success = upload_file(
            client,
            bucket_name,
            part_key,
            file_path=str(part_file),
            timeout=timeout_seconds,
        )
        if not success:
            log_event(
                logging.ERROR,
                "crate.upload.part.failed",
                submission_id=submission.id,
                drive_name=submission.drive_name,
                part_key=part_key,
            )
            return False, uploaded_keys

        uploaded_keys.append(part_key)
        _persist_uploaded_part_keys(session, submission, uploaded_keys)
        log_event(
            logging.INFO,
            "crate.upload.part.completed",
            submission_id=submission.id,
            drive_name=submission.drive_name,
            part_key=part_key,
        )

    return True, uploaded_keys


def build_crate_contents(  # pylint: disable=too-many-arguments, too-many-positional-arguments
    drive: dict[str, Any],
    submission: ArchiveSubmission,
    members_list: list[dict[str, Any]],
    project_data: dict[str, Any],
    drive_location: Path,
    output_location: Path,
) -> None:
    """Generate RO-Crate with data from ProjectDB.

    Args:
        drive: Research drive data dictionary
        submission: ArchiveSubmission record for this crate generation
        members_list: List of project members from ProjectDB
        project_data: Project data from ProjectDB
        drive_location: Source drive location path
        output_location: Output archive location path
    """
    ro_crate_loader = ROLoader()
    ro_crate_loader.init_crate()
    ro_crate_builder = ROBuilder(ro_crate_loader.crate)

    # Add project to crate with archive metadata
    project_entity = ro_crate_builder.add_project(
        project_data, members_list, submission, drive
    )

    # Add drive service as main entity
    drive_entity = ro_crate_builder.add_research_drive_service(drive)

    ro_crate_builder.crate.root_dataset.append_to("mainEntity", drive_entity)
    drive_entity.append_to("project", [project_entity])

    ro_crate_location = drive_location
    if bagit_exists(ro_crate_location):
        ro_crate_location = ro_crate_location / "data"

    log_event(
        logging.INFO,
        "crate.write.metadata",
        ro_crate_location=str(ro_crate_location),
        drive_name=submission.drive_name,
    )
    ro_crate_loader.write_crate(ro_crate_location)

    log_event(
        logging.INFO,
        "bag_directory.start",
        drive_name=submission.drive_name,
    )
    bag_directory(
        drive_location,
        bag_info={
            "project_id": str(project_data.get("id", "")),
            "drive_name": submission.drive_name,
        },
    )

    # Create output location after bagit processing so it doesn't get included in bag
    output_location.mkdir(parents=True, exist_ok=True)

    create_manifests_directory(
        drive_path=drive_location,
        output_location=output_location,
        drive_name=str(submission.drive_name),
    )


def generate_ro_crate(  # pylint: disable=too-many-locals,too-many-statements,too-many-branches
    drive: dict[str, Any],
    submission_id: int,
    projectdb_client: ProjectDBClient,
) -> None:
    """Background task for generating RO-Crate and updating archive record.

    Fetches live project data from ProjectDB, generates crate,
    uploads the archive to ActiveScale for long-term storage, and updates
    the ArchiveSubmission record with stage and operational metadata.

    Implements persisted checkpoints so retries can skip completed steps:
    - queued→running: After loading submission from DB
    - running→uploading: After crate build and tar generation
    - uploading→completed/failed: After upload attempt

    Args:
        drive: Dictionary containing research drive information
        submission_id: ID of the ArchiveSubmission record
        projectdb_client: Client for interacting with ProjectDB
    """
    drive_name = drive.get("name", None)
    started_at = datetime.now()
    if drive_name is None:
        log_event(
            logging.ERROR,
            "crate.build.invalid_drive",
            drive=drive,
            elapsed_ms=elapsed_ms(started_at),
        )
        return

    # Create a new session for this background task
    with Session(engine) as session:
        submission: ArchiveSubmission | None = None
        output_location: Path | None = None
        file_key: str | None = None
        project_id: int | None = None
        processing_error: str | None = None
        upload_success = False
        try:
            submission = session.get(ArchiveSubmission, submission_id)
            if submission is None:
                log_event(
                    logging.ERROR,
                    "crate.build.submission_not_found",
                    submission_id=submission_id,
                    drive_name=drive_name,
                    elapsed_ms=elapsed_ms(started_at),
                )
                return

            # Transition: queued → packaging
            previous_stage = submission.stage
            submission.stage = ArchiveJobStage.PACKAGING
            submission.last_updated_timestamp = datetime.now()
            session.add(submission)
            session.commit()

            log_event(
                logging.INFO,
                "submission.stage_transition",
                submission_id=submission_id,
                drive_name=drive_name,
                from_stage=previous_stage.value,
                to_stage=ArchiveJobStage.PACKAGING.value,
                stage=submission.stage.value,
                retry_count=submission.retry_count,
                elapsed_ms=elapsed_ms(started_at),
            )

            # Fetch project and member data from ProjectDB
            project_id = submission.project_id
            log_event(
                logging.INFO,
                "crate.build.projectdb_fetch_start",
                submission_id=submission_id,
                drive_name=drive_name,
                project_id=project_id,
                stage=submission.stage.value,
                retry_count=submission.retry_count,
                elapsed_ms=elapsed_ms(started_at),
            )
            project_data = projectdb_client.get_project(
                pid=project_id,
                expand=["codes", "status", "services", "properties"],
            )
            members_list = projectdb_client.get_project_members(
                project_id,
                expand=[
                    "person",
                    "role",
                    "person.identities",
                    "person.status",
                ],
            )
            members_list = filter_member_identities(members_list)

            # Source data and output locations
            drive_path = resolve_drive_path_for_archive(drive_name)
            output_location = resolve_archive_output_location(drive_name)

            log_event(
                logging.INFO,
                "crate.build.start",
                submission_id=submission_id,
                drive_name=drive_name,
                project_id=project_id,
                stage=submission.stage.value,
                retry_count=submission.retry_count,
                elapsed_ms=elapsed_ms(started_at),
            )

            # Build crate contents (idempotent, safe to retry)
            build_crate_contents(
                drive=drive,
                submission=submission,
                members_list=members_list,
                project_data=project_data,
                drive_location=drive_path,
                output_location=output_location,
            )

            # Build chunked tar archive package for upload.
            settings = get_settings()
            archive_parts_dir = output_location / "archive_parts"
            log_event(
                logging.INFO,
                "crate.package.chunked_tar.start",
                submission_id=submission_id,
                drive_name=drive_name,
                archive_parts_dir=str(archive_parts_dir),
                chunk_size_bytes=settings.archive_chunk_size_bytes,
                stage=submission.stage.value,
                retry_count=submission.retry_count,
                elapsed_ms=elapsed_ms(started_at),
            )
            chunk_result = build_chunked_tar_archive(
                source_dir=drive_path,
                output_dir=archive_parts_dir,
                base_name=str(drive_name),
                part_size_bytes=settings.archive_chunk_size_bytes,
                manifest_file_name=settings.archive_chunk_manifest_file_name,
            )

            object_prefix = f"{drive_name}/"
            submission.archive_part_count = len(chunk_result.parts)
            submission.archive_total_bytes = chunk_result.total_bytes
            submission.archive_object_prefix = object_prefix
            submission.archive_manifest_key = (
                f"{object_prefix}{chunk_result.manifest_path.name}"
            )
            if submission.archive_part_keys_json is None:
                submission.archive_part_keys_json = "[]"
            submission.last_updated_timestamp = datetime.now()
            session.add(submission)
            session.commit()

            log_event(
                logging.INFO,
                "crate.package.chunked_tar.completed",
                submission_id=submission_id,
                drive_name=drive_name,
                part_count=len(chunk_result.parts),
                total_bytes=chunk_result.total_bytes,
                manifest_path=str(chunk_result.manifest_path),
                stage=submission.stage.value,
                retry_count=submission.retry_count,
                elapsed_ms=elapsed_ms(started_at),
            )

            # Transition: packaging → uploading
            previous_stage = submission.stage
            submission.stage = ArchiveJobStage.UPLOADING
            submission.last_updated_timestamp = datetime.now()
            session.add(submission)
            session.commit()

            log_event(
                logging.INFO,
                "submission.stage_transition",
                submission_id=submission_id,
                drive_name=drive_name,
                from_stage=previous_stage.value,
                to_stage=ArchiveJobStage.UPLOADING.value,
                stage=submission.stage.value,
                retry_count=submission.retry_count,
                elapsed_ms=elapsed_ms(started_at),
            )

            # Upload the archive to ActiveScale
            log_event(
                logging.INFO,
                "crate.upload.start",
                submission_id=submission_id,
                drive_name=drive_name,
                stage=submission.stage.value,
                retry_count=submission.retry_count,
                elapsed_ms=elapsed_ms(started_at),
            )

            with get_activescale_client_context() as client:
                bucket_name = settings.activescale_bucket_name

                upload_success, uploaded_part_keys = _upload_chunked_archive_parts(
                    session=session,
                    submission=submission,
                    client=client,
                    bucket_name=bucket_name,
                    object_prefix=object_prefix,
                    archive_parts_dir=archive_parts_dir,
                    timeout_seconds=settings.activescale_upload_timeout,
                )

                if upload_success:
                    # Transition: uploading -> writing_manifest
                    previous_stage = submission.stage
                    submission.stage = ArchiveJobStage.WRITING_MANIFEST
                    submission.last_updated_timestamp = datetime.now()
                    session.add(submission)
                    session.commit()

                    log_event(
                        logging.INFO,
                        "submission.stage_transition",
                        submission_id=submission_id,
                        drive_name=drive_name,
                        from_stage=previous_stage.value,
                        to_stage=ArchiveJobStage.WRITING_MANIFEST.value,
                        stage=submission.stage.value,
                        retry_count=submission.retry_count,
                        elapsed_ms=elapsed_ms(started_at),
                    )

                    file_key = f"{object_prefix}{chunk_result.manifest_path.name}"
                    upload_success = upload_file(
                        client,
                        bucket_name,
                        file_key,
                        file_path=str(chunk_result.manifest_path),
                        timeout=settings.activescale_upload_timeout,
                        metadata={
                            "cer_project_id": str(project_data.get("id", "")),
                            "project_owners": json.dumps(get_project_owner_emails(members_list)),
                            "division": project_data.get("division") or "Unknown",
                            "data_classification": submission.data_classification
                            or "Unknown",
                            "retention_period_years": str(
                                submission.retention_period_years
                            )
                            or "Unknown",
                            "review_date": (
                                calculate_retention_end_date(
                                    datetime.now(),
                                    submission.retention_period_years,
                                )
                                if submission.retention_period_years is not None
                                else "Unknown"
                            ),
                            "archive_part_count": str(len(uploaded_part_keys)),
                        },
                    )
                    submission.archive_manifest_key = file_key
                    submission.archive_part_keys_json = json.dumps(uploaded_part_keys)
                    session.add(submission)
                    session.commit()

            # Transition: uploading → cleanup
            previous_stage = submission.stage
            submission.stage = ArchiveJobStage.CLEANUP
            submission.last_updated_timestamp = datetime.now()
            session.add(submission)
            session.commit()

            log_event(
                logging.INFO,
                "submission.stage_transition",
                submission_id=submission_id,
                drive_name=drive_name,
                from_stage=previous_stage.value,
                to_stage=ArchiveJobStage.CLEANUP.value,
                stage=submission.stage.value,
                retry_count=submission.retry_count,
                elapsed_ms=elapsed_ms(started_at),
            )

            cleanup_succeeded, cleanup_error = _cleanup_job_artifacts(
                str(drive_name), output_location
            )
            submission.cleanup_succeeded = cleanup_succeeded
            submission.cleanup_error = cleanup_error

            # Update submission record with upload result
            now = datetime.now()
            if upload_success:
                submission.stage = ArchiveJobStage.COMPLETED
                submission.failure_reason = None
                submission.failed_timestamp = None
                submission.archive_file_key = file_key
                submission.completed_timestamp = now
                submission.last_updated_timestamp = now
                session.add(submission)
                session.commit()

                log_event(
                    logging.INFO,
                    "crate.upload.completed",
                    submission_id=submission_id,
                    drive_name=drive_name,
                    file_key=file_key,
                    stage=submission.stage.value,
                    retry_count=submission.retry_count,
                    cleanup_succeeded=submission.cleanup_succeeded,
                    elapsed_ms=elapsed_ms(started_at),
                )
            else:
                submission.stage = ArchiveJobStage.FAILED
                submission.failure_reason = "Archive upload failed"
                submission.failed_timestamp = now
                submission.archive_file_key = file_key
                submission.last_updated_timestamp = now
                session.add(submission)
                session.commit()
                log_event(
                    logging.ERROR,
                    "crate.upload.failed",
                    submission_id=submission_id,
                    drive_name=drive_name,
                    file_key=file_key,
                    stage=submission.stage.value,
                    retry_count=submission.retry_count,
                    cleanup_succeeded=submission.cleanup_succeeded,
                    elapsed_ms=elapsed_ms(started_at),
                )

            log_event(
                logging.INFO,
                "crate.build.completed",
                submission_id=submission_id,
                drive_name=drive_name,
                project_id=project_id,
                stage=submission.stage.value,
                retry_count=submission.retry_count,
                cleanup_succeeded=submission.cleanup_succeeded,
                elapsed_ms=elapsed_ms(started_at),
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            processing_error = str(e)
            if submission is not None:
                now = datetime.now()

                # Transition to cleanup before final failed state.
                previous_stage = submission.stage
                submission.stage = ArchiveJobStage.CLEANUP
                submission.last_updated_timestamp = now
                session.add(submission)
                session.commit()

                log_event(
                    logging.WARNING,
                    "submission.stage_transition",
                    submission_id=submission_id,
                    drive_name=drive_name,
                    from_stage=previous_stage.value,
                    to_stage=ArchiveJobStage.CLEANUP.value,
                    stage=submission.stage.value,
                    retry_count=submission.retry_count,
                    elapsed_ms=elapsed_ms(started_at),
                )

                cleanup_succeeded, cleanup_error = _cleanup_job_artifacts(
                    str(drive_name), output_location
                )
                submission.cleanup_succeeded = cleanup_succeeded
                submission.cleanup_error = cleanup_error

                submission.stage = ArchiveJobStage.FAILED
                submission.failure_reason = processing_error
                submission.failed_timestamp = now
                submission.last_updated_timestamp = now
                session.add(submission)
                session.commit()
            log_event(
                logging.ERROR,
                "crate.build.failed",
                submission_id=submission_id,
                drive_name=drive_name,
                error=processing_error,
                stage=(submission.stage.value if submission is not None else None),
                retry_count=(
                    submission.retry_count if submission is not None else None
                ),
                cleanup_succeeded=(
                    submission.cleanup_succeeded if submission is not None else None
                ),
                elapsed_ms=elapsed_ms(started_at),
            )
            log_event(
                logging.ERROR,
                "crate.build.exception",
                submission_id=submission_id,
                drive_name=drive_name,
                exc_info=True,
                elapsed_ms=elapsed_ms(started_at),
            )
