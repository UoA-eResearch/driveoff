"""Integration-style tests for chunked archive workflow stages."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel
from sqlmodel.pool import StaticPool

from api.main import generate_ro_crate
from models.common import DataClassification
from models.submission import ArchiveSubmission, JobStage


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


@pytest.fixture()
def test_engine() -> Generator[Engine, Any, None]:
    """Provide a fresh in-memory SQLite engine, disposed after each test."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def _create_submission(engine, drive_name: str, project_id: int = 123) -> int:
    with Session(engine) as session:
        submission = ArchiveSubmission(
            drive_id=1,
            project_id=project_id,
            drive_name=drive_name,
            retention_period_years=7,
            retention_period_justification="Standard retention",
            data_classification=DataClassification.SENSITIVE,
            stage=JobStage.QUEUED,
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

    monkeypatch.setattr("api.main.engine", test_engine)
    monkeypatch.setattr("api.main._resolve_drive_path_for_archive", lambda _name: drive_path)
    monkeypatch.setattr(
        "api.main._resolve_archive_output_location", lambda _name: output_path
    )
    monkeypatch.setattr("api.main._cleanup_job_artifacts", lambda *_args, **_kwargs: (True, None))

    # Avoid heavy crate generation internals; this test focuses on chunked workflow.
    monkeypatch.setattr("api.main.build_crate_contents", lambda **_kwargs: None)

    settings = SimpleNamespace(
        archive_chunk_size_bytes=1024,
        archive_chunk_manifest_file_name="archive-manifest.json",
        activescale_upload_timeout=60,
        activescale_bucket_name="research-archive-test",
    )
    monkeypatch.setattr("api.main.get_settings", lambda: settings)

    @contextmanager
    def fake_client_context():
        yield object()

    monkeypatch.setattr("api.main.get_activescale_client_context", fake_client_context)

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

    monkeypatch.setattr("api.main.upload_file", fake_upload)
    monkeypatch.setattr("api.main.object_exists", lambda *_args, **_kwargs: (False, None))

    asyncio.run(
        generate_ro_crate(
            drive={"id": 1, "name": drive_name},
            submission_id=submission_id,
            projectdb_client=_ProjectDbStub(),
        )
    )

    with Session(test_engine) as session:
        submission = session.get(ArchiveSubmission, submission_id)
        assert submission is not None
        assert submission.stage == JobStage.COMPLETED
        assert submission.archive_part_count is not None
        assert submission.archive_part_count > 0
        assert submission.archive_object_prefix == f"{drive_name}/"
        assert submission.archive_manifest_key == f"{drive_name}/archive-manifest.json"

        part_keys = json.loads(submission.archive_part_keys_json or "[]")
        assert len(part_keys) == submission.archive_part_count

    assert upload_calls
    manifest_upload = upload_calls[-1]
    assert str(manifest_upload["key"]).endswith("archive-manifest.json")

    with open(Path(str(manifest_upload["file_path"])), "r", encoding="utf-8") as mf:
        manifest = json.load(mf)
    assert manifest["part_count"] == submission.archive_part_count
    assert manifest["total_bytes"] == submission.archive_total_bytes
    assert len(manifest["parts"]) == submission.archive_part_count


def test_generate_ro_crate_resumes_after_interrupted_part_upload(
    tmp_path: Path,
    monkeypatch,
    test_engine: Engine,
) -> None:
    drive_name = "resint000000002-testing"
    drive_path = tmp_path / drive_name
    drive_path.mkdir(parents=True, exist_ok=True)
    (drive_path / "a.bin").write_bytes(b"A" * 3000)
    (drive_path / "b.bin").write_bytes(b"B" * 3000)

    output_path = tmp_path / "output"
    output_path.mkdir(parents=True, exist_ok=True)

    submission_id = _create_submission(test_engine, drive_name)

    monkeypatch.setattr("api.main.engine", test_engine)
    monkeypatch.setattr("api.main._resolve_drive_path_for_archive", lambda _name: drive_path)
    monkeypatch.setattr(
        "api.main._resolve_archive_output_location", lambda _name: output_path
    )
    monkeypatch.setattr("api.main._cleanup_job_artifacts", lambda *_args, **_kwargs: (True, None))
    monkeypatch.setattr("api.main.build_crate_contents", lambda **_kwargs: None)

    settings = SimpleNamespace(
        archive_chunk_size_bytes=100,  # small enough to produce multiple parts after gzip
        archive_chunk_manifest_file_name="archive-manifest.json",
        activescale_upload_timeout=60,
        activescale_bucket_name="research-archive-test",
    )
    monkeypatch.setattr("api.main.get_settings", lambda: settings)

    @contextmanager
    def fake_client_context():
        yield object()

    monkeypatch.setattr("api.main.get_activescale_client_context", fake_client_context)

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

    monkeypatch.setattr("api.main.upload_file", fail_on_second_part)
    monkeypatch.setattr("api.main.object_exists", lambda *_args, **_kwargs: (False, None))

    asyncio.run(
        generate_ro_crate(
            drive={"id": 1, "name": drive_name},
            submission_id=submission_id,
            projectdb_client=_ProjectDbStub(),
        )
    )

    with Session(test_engine) as session:
        submission = session.get(ArchiveSubmission, submission_id)
        assert submission is not None
        assert submission.stage == JobStage.FAILED
        first_run_keys = json.loads(submission.archive_part_keys_json or "[]")
        assert len(first_run_keys) == 1
        assert first_run_keys[0] in first_run_uploaded

        # Simulate retry endpoint behavior.
        submission.stage = JobStage.QUEUED
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

    monkeypatch.setattr("api.main.upload_file", upload_all)

    def exists_if_previously_uploaded(_client, _bucket: str, key: str):
        return (key in first_run_uploaded), None

    monkeypatch.setattr("api.main.object_exists", exists_if_previously_uploaded)

    asyncio.run(
        generate_ro_crate(
            drive={"id": 1, "name": drive_name},
            submission_id=submission_id,
            projectdb_client=_ProjectDbStub(),
        )
    )

    with Session(test_engine) as session:
        submission = session.get(ArchiveSubmission, submission_id)
        assert submission is not None
        assert submission.stage == JobStage.COMPLETED
        assert submission.archive_manifest_key == f"{drive_name}/archive-manifest.json"
        final_part_keys = json.loads(submission.archive_part_keys_json or "[]")
        assert submission.archive_part_count is not None
        assert len(final_part_keys) == submission.archive_part_count

    # Resume should not re-upload first successfully uploaded part.
    assert all(key not in first_run_uploaded for key in second_run_uploaded if "part-00001" in key)
