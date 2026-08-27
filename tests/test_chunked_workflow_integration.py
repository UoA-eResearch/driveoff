"""Integration-style tests for chunked archive workflow stages."""

from __future__ import annotations

import json
import tarfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import bagit
from sqlalchemy.engine import Engine
from sqlmodel import Session

from models.common import DataClassification
from models.submission import ArchiveJobStage, ArchiveSubmission
from packaging.archive_reassembly import reassemble_archive_from_manifest
from workers.submission_worker import generate_ro_crate


class _ProjectDbStub:
    def get_project(self, pid: int, expand=None):  # noqa: ANN001
        return {
            "id": pid,
            "division": "CTRERSH",
            "end_date": "2024-11-04",
            "codes": {"items": [{"code": "TEST-001"}]},
        }

    def get_project_members(self, project_id: int, expand=None):  # noqa: ANN001
        return [
            {
                "person": {
                    "email": "owner@example.com",
                    "identities": {"items": [{"username": "owner1"}]},
                },
                "role": {"name": "Project Owner"},
            }
        ]


def _create_submission(engine, drive_name: str, project_id: int = 123) -> int:
    with Session(engine) as session:
        submission = ArchiveSubmission(
            drive_id=1,
            project_id=project_id,
            drive_name=drive_name,
            retention_period_years=7,
            retention_period_justification="Standard retention",
            data_classification=DataClassification.SENSITIVE,
            stage=ArchiveJobStage.QUEUED,
            started_timestamp=datetime.now(),
            last_updated_timestamp=datetime.now(),
        )
        session.add(submission)
        session.commit()
        session.refresh(submission)
        assert submission.id is not None
        return submission.id


def test_generate_ro_crate_chunked_success_and_manifest_integrity(
    tmp_path: Path,
    monkeypatch,
    test_engine: Engine,
) -> None:
    drive_name = "resint000000001-testing"
    drive_path = tmp_path / drive_name
    drive_path.mkdir(parents=True, exist_ok=True)
    (drive_path / "a.bin").write_bytes(b"A" * 5000)
    (drive_path / "nested").mkdir(exist_ok=True)
    (drive_path / "nested" / "b.bin").write_bytes(b"B" * 7000)

    output_path = tmp_path / "output"
    output_path.mkdir(parents=True, exist_ok=True)

    submission_id = _create_submission(test_engine, drive_name)

    monkeypatch.setattr("workers.submission_worker.engine", test_engine)
    monkeypatch.setattr(
        "workers.submission_worker.resolve_drive_path_for_archive",
        lambda _name: drive_path,
    )
    monkeypatch.setattr(
        "workers.submission_worker.resolve_archive_output_location",
        lambda _name: output_path,
    )
    monkeypatch.setattr(
        "workers.submission_worker._cleanup_job_artifacts",
        lambda *_args, **_kwargs: (True, None),
    )

    settings = SimpleNamespace(
        archive_chunk_size_bytes=1024,
        archive_chunk_manifest_file_name="archive-manifest.json",
        activescale_upload_timeout=60,
        activescale_bucket_name="research-archive-test",
        activescale_enable_object_retention=False,
        activescale_default_retention_years=6,
        activescale_retention_override_days=None,
    )
    monkeypatch.setattr("workers.submission_worker.get_settings", lambda: settings)

    @contextmanager
    def fake_client_context():
        yield object()

    monkeypatch.setattr("workers.submission_worker.get_activescale_client_context", fake_client_context)

    notifications: list[dict[str, Any]] = []

    def fake_notify_job_result(**kwargs: Any) -> bool:
        notifications.append(kwargs)
        return True

    monkeypatch.setattr("workers.submission_worker.notify_job_result", fake_notify_job_result)

    upload_calls: list[dict[str, object]] = []

    def fake_upload(
        _client,
        _bucket: str,
        key: str,
        file_path: str,
        timeout: int,
        metadata=None,
    ) -> bool:
        upload_calls.append(
            {
                "key": key,
                "file_path": file_path,
                "timeout": timeout,
                "metadata": metadata,
            }
        )
        return True

    monkeypatch.setattr("workers.submission_worker.upload_file", fake_upload)
    monkeypatch.setattr(
        "workers.submission_worker.verify_uploaded_part_size",
        lambda *_args, **_kwargs: True,
    )

    generate_ro_crate(
        drive={"id": 1, "name": drive_name},
        submission_id=submission_id,
        projectdb_client=_ProjectDbStub(),
    )

    with Session(test_engine) as session:
        submission = session.get(ArchiveSubmission, submission_id)
        assert submission is not None
        assert submission.stage == ArchiveJobStage.COMPLETED
        assert submission.archive_part_count is not None
        assert submission.archive_part_count > 0
        assert submission.archive_object_prefix == f"{drive_name}/"
        assert submission.archive_manifest_key == f"{drive_name}/archive-manifest.json"

        part_keys = json.loads(submission.archive_part_keys_json or "[]")
        assert len(part_keys) == submission.archive_part_count

    assert upload_calls
    manifest_upload = upload_calls[-1]
    assert str(manifest_upload["key"]).endswith("archive-manifest.json")
    assert manifest_upload["metadata"] is not None

    with open(Path(str(manifest_upload["file_path"])), encoding="utf-8") as mf:
        manifest = json.load(mf)
    assert manifest["part_count"] == submission.archive_part_count
    assert manifest["total_bytes"] == submission.archive_total_bytes
    assert len(manifest["parts"]) == submission.archive_part_count

    part_uploads = [call for call in upload_calls if "archive-manifest.json" not in str(call["key"])]
    assert part_uploads
    for upload in part_uploads:
        metadata = upload["metadata"]
        assert metadata is not None
        assert metadata["cer_project_id"] == "123"
        assert metadata["division"] == "CTRERSH"
        assert metadata["data_classification"] == "Sensitive"
        assert metadata["retention_period_years"] == "7"
        assert metadata["archive_part_count"] == str(submission.archive_part_count)

    manifest_metadata = manifest_upload["metadata"]
    assert manifest_metadata is not None
    assert manifest_metadata["cer_project_id"] == "123"
    assert manifest_metadata["division"] == "CTRERSH"
    assert manifest_metadata["data_classification"] == "Sensitive"
    assert manifest_metadata["retention_period_years"] == "7"
    assert manifest_metadata["archive_part_count"] == str(submission.archive_part_count)
    assert notifications == [
        {
            "job_type": "submission",
            "status": "completed",
            "drive_name": drive_name,
            "submission_id": submission_id,
            "project_id": 123,
            "stage": "completed",
            "retry_count": 0,
            "extra_context": {
                "archive_manifest_key": f"{drive_name}/archive-manifest.json",
            },
        }
    ]

    # End-to-end: reassemble the parts, extract, and let the bagit library
    # validate the bag; the RO-Crate metadata must be inside the payload and
    # the source drive must be untouched.
    out_tar = tmp_path / "reassembled.tar.gz"
    reassemble_archive_from_manifest(
        parts_dir=output_path / "archive_parts",
        manifest_path=Path(str(manifest_upload["file_path"])),
        output_tar_path=out_tar,
    )
    extract_dir = tmp_path / "extracted"
    with tarfile.open(out_tar, "r:gz") as tar:
        tar.extractall(extract_dir, filter="data")

    bag_root = extract_dir / drive_name
    bag = bagit.Bag(str(bag_root))
    bag.validate(processes=1)
    assert (bag_root / "data" / "ro-crate-metadata.json").is_file()
    assert (bag_root / "data" / "a.bin").is_file()
    assert (bag_root / "data" / "nested" / "b.bin").is_file()
    assert not (drive_path / "bagit.txt").exists()
    assert not (drive_path / "data").exists()


def test_generate_ro_crate_retry_reuploads_all_parts_after_failure(
    tmp_path: Path,
    monkeypatch,
    test_engine: Engine,
) -> None:
    """A retry rebuilds the tar stream, so it must re-upload EVERY part.

    Parts are byte-slices of a single gzip stream; skipping parts uploaded by
    a previous attempt would mix slices of two different streams and corrupt
    the archive (regression test for the part-mixing bug). The retry must
    also replace the stale persisted part keys with the new run's keys.
    """
    drive_name = "resint000000002-testing"
    drive_path = tmp_path / drive_name
    drive_path.mkdir(parents=True, exist_ok=True)
    (drive_path / "a.bin").write_bytes(b"A" * 3000)
    (drive_path / "b.bin").write_bytes(b"B" * 3000)

    output_path = tmp_path / "output"
    output_path.mkdir(parents=True, exist_ok=True)

    submission_id = _create_submission(test_engine, drive_name)

    monkeypatch.setattr("workers.submission_worker.engine", test_engine)
    monkeypatch.setattr(
        "workers.submission_worker.resolve_drive_path_for_archive",
        lambda _name: drive_path,
    )
    monkeypatch.setattr(
        "workers.submission_worker.resolve_archive_output_location",
        lambda _name: output_path,
    )
    monkeypatch.setattr(
        "workers.submission_worker._cleanup_job_artifacts",
        lambda *_args, **_kwargs: (True, None),
    )
    monkeypatch.setattr("workers.submission_worker.build_crate_contents", lambda **_kwargs: None)

    settings = SimpleNamespace(
        archive_chunk_size_bytes=100,  # small enough to produce multiple parts after gzip
        archive_chunk_manifest_file_name="archive-manifest.json",
        activescale_upload_timeout=60,
        activescale_bucket_name="research-archive-test",
        activescale_enable_object_retention=False,
        activescale_default_retention_years=6,
        activescale_retention_override_days=None,
    )
    monkeypatch.setattr("workers.submission_worker.get_settings", lambda: settings)

    @contextmanager
    def fake_client_context():
        yield object()

    monkeypatch.setattr("workers.submission_worker.get_activescale_client_context", fake_client_context)

    notifications: list[dict[str, Any]] = []

    def fake_notify_job_result(**kwargs: Any) -> bool:
        notifications.append(kwargs)
        return True

    monkeypatch.setattr("workers.submission_worker.notify_job_result", fake_notify_job_result)

    first_run_uploaded: set[str] = set()

    def fail_on_second_part(
        _client,
        _bucket: str,
        key: str,
        file_path: str,
        timeout: int,
        metadata=None,
    ) -> bool:
        if key.endswith("archive-manifest.json"):
            return True
        # Fail once when attempting second part upload to simulate interruption.
        part_index = int(str(key).split("part-")[-1])
        if part_index == 2:
            return False
        first_run_uploaded.add(key)
        return True

    monkeypatch.setattr("workers.submission_worker.upload_file", fail_on_second_part)
    monkeypatch.setattr(
        "workers.submission_worker.verify_uploaded_part_size",
        lambda *_args, **_kwargs: True,
    )

    generate_ro_crate(
        drive={"id": 1, "name": drive_name},
        submission_id=submission_id,
        projectdb_client=_ProjectDbStub(),
    )

    with Session(test_engine) as session:
        submission = session.get(ArchiveSubmission, submission_id)
        assert submission is not None
        assert submission.stage == ArchiveJobStage.FAILED
        first_run_keys = json.loads(submission.archive_part_keys_json or "[]")
        assert len(first_run_keys) == 1
        assert first_run_keys[0] in first_run_uploaded
        assert notifications == [
            {
                "job_type": "submission",
                "status": "failed",
                "drive_name": drive_name,
                "submission_id": submission_id,
                "project_id": 123,
                "stage": "failed",
                "retry_count": 0,
                "failure_reason": "Archive upload failed",
                "extra_context": {
                    "archive_manifest_key": f"{drive_name}/archive-manifest.json",
                },
            }
        ]

        # Simulate retry endpoint behavior.
        submission.stage = ArchiveJobStage.QUEUED
        submission.failure_reason = None
        submission.failed_timestamp = None
        submission.last_updated_timestamp = datetime.now()
        session.add(submission)
        session.commit()

    second_run_uploaded: list[str] = []

    def upload_all(
        _client,
        _bucket: str,
        key: str,
        file_path: str,
        timeout: int,
        metadata=None,
    ) -> bool:
        second_run_uploaded.append(key)
        return True

    monkeypatch.setattr("workers.submission_worker.upload_file", upload_all)
    monkeypatch.setattr(
        "workers.submission_worker.verify_uploaded_part_size",
        lambda *_args, **_kwargs: True,
    )

    generate_ro_crate(
        drive={"id": 1, "name": drive_name},
        submission_id=submission_id,
        projectdb_client=_ProjectDbStub(),
    )

    with Session(test_engine) as session:
        submission = session.get(ArchiveSubmission, submission_id)
        assert submission is not None
        assert submission.stage == ArchiveJobStage.COMPLETED
        assert submission.archive_manifest_key == f"{drive_name}/archive-manifest.json"
        final_part_keys = json.loads(submission.archive_part_keys_json or "[]")
        assert submission.archive_part_count is not None
        assert len(final_part_keys) == submission.archive_part_count

        # The stale key from the first attempt was replaced, not appended to:
        # every persisted key corresponds to a part uploaded by the second run.
        assert set(final_part_keys) <= set(second_run_uploaded)

    # The retry re-uploaded every part of the rebuilt stream, including the
    # part the first attempt had already uploaded — no parts were skipped.
    second_run_part_uploads = [key for key in second_run_uploaded if "archive-manifest.json" not in key]
    assert first_run_uploaded <= set(second_run_part_uploads)
    assert len(second_run_part_uploads) == len(final_part_keys)
    assert notifications[-1] == {
        "job_type": "submission",
        "status": "completed",
        "drive_name": drive_name,
        "submission_id": submission_id,
        "project_id": 123,
        "stage": "completed",
        "retry_count": 0,
        "extra_context": {
            "archive_manifest_key": f"{drive_name}/archive-manifest.json",
        },
    }
