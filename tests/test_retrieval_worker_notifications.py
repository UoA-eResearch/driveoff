"""Focused tests for retrieval worker notifications."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sqlalchemy.engine import Engine
from sqlmodel import Session

from models.common import DataClassification
from models.retrieval import ArchiveRetrieval, RetrievalJobStage
from models.submission import ArchiveJobStage, ArchiveSubmission
from workers.retrieval_worker import run_archive_retrieval


class _FakeTarFile:
    def __init__(self, destination_path: Path, drive_name: str):
        self._destination_path = destination_path
        self._drive_name = drive_name

    def __enter__(self) -> _FakeTarFile:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def extractall(self, path: Path, filter: str) -> None:
        del filter
        target = path / self._drive_name
        target.mkdir(parents=True, exist_ok=True)
        (target / "restored.txt").write_text("ok", encoding="utf-8")


def _create_submission_and_retrieval(engine: Engine, destination_path: str) -> tuple[int, int, str]:
    drive_name = "resret000000001-testing"
    with Session(engine) as session:
        submission = ArchiveSubmission(
            drive_id=1,
            project_id=123,
            drive_name=drive_name,
            retention_period_years=7,
            retention_period_justification="Standard retention",
            data_classification=DataClassification.SENSITIVE,
            stage=ArchiveJobStage.COMPLETED,
            archive_object_prefix=f"{drive_name}/",
            archive_manifest_key=f"{drive_name}/archive-manifest.json",
            started_timestamp=datetime.now(),
            completed_timestamp=datetime.now(),
            last_updated_timestamp=datetime.now(),
        )
        session.add(submission)
        session.commit()
        session.refresh(submission)
        assert submission.id is not None

        retrieval = ArchiveRetrieval(
            drive_name=drive_name,
            submission_id=submission.id,
            destination_path=destination_path,
            stage=RetrievalJobStage.QUEUED,
            started_timestamp=datetime.now(),
            last_updated_timestamp=datetime.now(),
        )
        session.add(retrieval)
        session.commit()
        session.refresh(retrieval)
        assert retrieval.id is not None
        return submission.id, retrieval.id, drive_name


def test_run_archive_retrieval_sends_completed_notification(tmp_path: Path, monkeypatch, test_engine: Engine) -> None:
    engine = test_engine
    destination_path = tmp_path / "restored"
    destination_path.mkdir(parents=True, exist_ok=True)
    submission_id, retrieval_id, drive_name = _create_submission_and_retrieval(engine, str(destination_path))

    monkeypatch.setattr("workers.retrieval_worker.engine", engine)
    settings = SimpleNamespace(
        activescale_bucket_name="research-archive-test",
        archive_temp_base_path=str(tmp_path),
        archive_chunk_manifest_file_name="archive-manifest.json",
        activescale_restore_poll_interval_seconds=1,
        activescale_restore_poll_max_seconds=5,
        activescale_restore_days=1,
    )
    monkeypatch.setattr("workers.retrieval_worker.get_settings", lambda: settings)

    @contextmanager
    def fake_client_context():
        yield object()

    monkeypatch.setattr("workers.retrieval_worker.get_activescale_client_context", fake_client_context)
    monkeypatch.setattr("workers.retrieval_worker.initiate_object_restore", lambda *_args, **_kwargs: False)

    def fake_download(_client, _bucket: str, key: str, dest: Path) -> bool:
        if str(key).endswith("archive-manifest.json"):
            dest.write_text(json.dumps({"source_root": drive_name}), encoding="utf-8")
        else:
            dest.write_bytes(b"part")
        return True

    monkeypatch.setattr("workers.retrieval_worker.download_file_to_disk", fake_download)
    monkeypatch.setattr("workers.retrieval_worker.load_archive_manifest", lambda _path: {"source_root": drive_name})
    monkeypatch.setattr(
        "workers.retrieval_worker.ordered_part_object_keys",
        lambda prefix, _manifest: [f"{prefix}archive.tar.gz.part-00001"],
    )
    monkeypatch.setattr(
        "workers.retrieval_worker.reassemble_archive_from_manifest",
        lambda **kwargs: Path(str(kwargs["output_tar_path"])).write_bytes(b"tar"),
    )
    monkeypatch.setattr(
        "workers.retrieval_worker.tarfile.open",
        lambda *_args, **_kwargs: _FakeTarFile(destination_path, drive_name),
    )
    monkeypatch.setattr("workers.retrieval_worker.bagit_exists", lambda _path: False)

    notifications: list[dict[str, Any]] = []

    def fake_notify_job_result(**kwargs: Any) -> bool:
        notifications.append(kwargs)
        return True

    monkeypatch.setattr("workers.retrieval_worker.notify_job_result", fake_notify_job_result)

    run_archive_retrieval(retrieval_id)

    with Session(engine) as session:
        retrieval = session.get(ArchiveRetrieval, retrieval_id)
        assert retrieval is not None
        assert retrieval.stage == RetrievalJobStage.COMPLETED
        assert retrieval.completed_timestamp is not None

    assert notifications == [
        {
            "job_type": "retrieval",
            "status": "completed",
            "drive_name": drive_name,
            "submission_id": submission_id,
            "retrieval_id": retrieval_id,
            "project_id": 123,
            "stage": "completed",
            "extra_context": {"destination_path": str(destination_path)},
        }
    ]


def test_run_archive_retrieval_sends_failed_notification(tmp_path: Path, monkeypatch, test_engine: Engine) -> None:
    engine = test_engine
    destination_path = tmp_path / "restored"
    destination_path.mkdir(parents=True, exist_ok=True)
    _, retrieval_id, drive_name = _create_submission_and_retrieval(engine, str(destination_path))

    monkeypatch.setattr("workers.retrieval_worker.engine", engine)
    settings = SimpleNamespace(
        activescale_bucket_name="research-archive-test",
        archive_temp_base_path=str(tmp_path),
        archive_chunk_manifest_file_name="archive-manifest.json",
        activescale_restore_poll_interval_seconds=1,
        activescale_restore_poll_max_seconds=5,
        activescale_restore_days=1,
    )
    monkeypatch.setattr("workers.retrieval_worker.get_settings", lambda: settings)

    @contextmanager
    def fake_client_context():
        yield object()

    monkeypatch.setattr("workers.retrieval_worker.get_activescale_client_context", fake_client_context)
    monkeypatch.setattr("workers.retrieval_worker.initiate_object_restore", lambda *_args, **_kwargs: False)

    def fake_download(_client, _bucket: str, key: str, dest: Path) -> bool:
        if str(key).endswith("archive-manifest.json"):
            dest.write_text(json.dumps({"source_root": drive_name}), encoding="utf-8")
            return True
        return False

    monkeypatch.setattr("workers.retrieval_worker.download_file_to_disk", fake_download)
    monkeypatch.setattr("workers.retrieval_worker.load_archive_manifest", lambda _path: {"source_root": drive_name})
    monkeypatch.setattr(
        "workers.retrieval_worker.ordered_part_object_keys",
        lambda prefix, _manifest: [f"{prefix}archive.tar.gz.part-00001"],
    )

    notifications: list[dict[str, Any]] = []

    def fake_notify_job_result(**kwargs: Any) -> bool:
        notifications.append(kwargs)
        return True

    monkeypatch.setattr("workers.retrieval_worker.notify_job_result", fake_notify_job_result)

    run_archive_retrieval(retrieval_id)

    with Session(engine) as session:
        retrieval = session.get(ArchiveRetrieval, retrieval_id)
        assert retrieval is not None
        assert retrieval.stage == RetrievalJobStage.FAILED
        assert retrieval.failure_reason == f"Failed to download archive part: {drive_name}/archive.tar.gz.part-00001"

    assert notifications == [
        {
            "job_type": "retrieval",
            "status": "failed",
            "drive_name": drive_name,
            "submission_id": 1,
            "retrieval_id": retrieval_id,
            "project_id": 123,
            "stage": "failed",
            "failure_reason": f"Failed to download archive part: {drive_name}/archive.tar.gz.part-00001",
            "extra_context": {"destination_path": str(destination_path)},
        }
    ]
