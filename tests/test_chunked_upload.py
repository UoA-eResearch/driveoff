"""Tests for chunked archive upload helpers."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlmodel import Session

from workers import parse_part_keys_json
from workers.submission_worker import _upload_chunked_archive_parts
from packaging.archive_chunks import ArchivePartInfo
from models.common import DataClassification
from models.submission import ArchiveSubmission


def _create_submission(session: Session, drive_name: str) -> ArchiveSubmission:
    submission = ArchiveSubmission(
        drive_id=1,
        project_id=101,
        drive_name=drive_name,
        retention_period_years=7,
        retention_period_justification="Standard retention",
        data_classification=DataClassification.SENSITIVE,
        started_timestamp=datetime.now(),
    )
    session.add(submission)
    session.commit()
    session.refresh(submission)
    return submission


def test_parse_uploaded_part_keys_defensive() -> None:
    assert parse_part_keys_json(None) == []
    assert parse_part_keys_json("") == []
    assert parse_part_keys_json("{}") == []
    assert parse_part_keys_json("not-json") == []
    assert parse_part_keys_json('["a", "b"]') == ["a", "b"]


def test_upload_chunked_parts_resumes_skipping_existing(
    tmp_path: Path,
    session: Session,
    monkeypatch,
) -> None:
    archive_parts_dir = tmp_path / "parts"
    archive_parts_dir.mkdir(parents=True, exist_ok=True)
    first = archive_parts_dir / "drive.tar.gz.part-00001"
    second = archive_parts_dir / "drive.tar.gz.part-00002"
    first.write_bytes(b"part1")
    second.write_bytes(b"part2")

    prefix = "drive/"
    first_key = f"{prefix}{first.name}"
    second_key = f"{prefix}{second.name}"

    submission = _create_submission(session, drive_name="resmed202200024-testing")
    submission.archive_part_keys_json = json.dumps([first_key])
    session.add(submission)
    session.commit()

    uploaded_keys: list[str] = []

    def fake_exists(_client, _bucket: str, key: str):
        return (key == first_key), None

    def fake_upload(_client, _bucket: str, key: str, file_path: str, timeout: int):
        assert timeout == 60
        assert Path(file_path).exists()
        uploaded_keys.append(key)
        return True

    monkeypatch.setattr("workers.submission_worker.object_exists", fake_exists)
    monkeypatch.setattr("workers.submission_worker.upload_file", fake_upload)
    monkeypatch.setattr(
        "workers.submission_worker.verify_uploaded_part_size", lambda *_a, **_k: True
    )

    success, result_keys = _upload_chunked_archive_parts(
        session=session,
        submission=submission,
        client=object(),
        bucket_name="bucket",
        object_prefix=prefix,
        archive_parts_dir=archive_parts_dir,
        archive_parts=[
            ArchivePartInfo(index=1, file_name=first.name, size_bytes=len(b"part1"), sha256="a"),
            ArchivePartInfo(index=2, file_name=second.name, size_bytes=len(b"part2"), sha256="b"),
        ],
        timeout_seconds=60,
    )

    assert success is True
    assert uploaded_keys == [second_key]
    assert first_key in result_keys
    assert second_key in result_keys


def test_upload_chunked_parts_stops_on_failure(
    tmp_path: Path,
    session: Session,
    monkeypatch,
) -> None:
    archive_parts_dir = tmp_path / "parts"
    archive_parts_dir.mkdir(parents=True, exist_ok=True)
    first = archive_parts_dir / "drive.tar.gz.part-00001"
    first.write_bytes(b"part1")

    prefix = "drive/"
    expected_key = f"{prefix}{first.name}"

    submission = _create_submission(session, drive_name="resmed202200024-testing")

    monkeypatch.setattr("workers.submission_worker.object_exists", lambda *_args, **_kwargs: (False, None))
    monkeypatch.setattr("workers.submission_worker.upload_file", lambda *_args, **_kwargs: False)

    success, result_keys = _upload_chunked_archive_parts(
        session=session,
        submission=submission,
        client=object(),
        bucket_name="bucket",
        object_prefix=prefix,
        archive_parts_dir=archive_parts_dir,
        archive_parts=[
            ArchivePartInfo(index=1, file_name=first.name, size_bytes=len(b"part1"), sha256="a"),
        ],
        timeout_seconds=60,
    )

    assert success is False
    assert result_keys == []
    assert expected_key not in result_keys


def test_upload_chunked_parts_fails_on_size_mismatch(
    tmp_path: Path,
    session: Session,
    monkeypatch,
) -> None:
    """Upload succeeds but post-upload size check fails → job aborts."""
    archive_parts_dir = tmp_path / "parts"
    archive_parts_dir.mkdir(parents=True, exist_ok=True)
    part = archive_parts_dir / "drive.tar.gz.part-00001"
    part.write_bytes(b"part1")

    prefix = "drive/"
    part_key = f"{prefix}{part.name}"

    submission = _create_submission(session, drive_name="resmed202200024-testing")

    monkeypatch.setattr("workers.submission_worker.object_exists", lambda *_a, **_k: (False, None))
    monkeypatch.setattr("workers.submission_worker.upload_file", lambda *_a, **_k: True)
    monkeypatch.setattr(
        "workers.submission_worker.verify_uploaded_part_size", lambda *_a, **_k: False
    )

    success, result_keys = _upload_chunked_archive_parts(
        session=session,
        submission=submission,
        client=object(),
        bucket_name="bucket",
        object_prefix=prefix,
        archive_parts_dir=archive_parts_dir,
        archive_parts=[
            ArchivePartInfo(index=1, file_name=part.name, size_bytes=len(b"part1"), sha256="a"),
        ],
        timeout_seconds=60,
    )

    assert success is False
    # Part must not be recorded as successfully uploaded when size check fails
    assert part_key not in result_keys


def test_upload_chunked_parts_size_check_called_with_correct_args(
    tmp_path: Path,
    session: Session,
    monkeypatch,
) -> None:
    """verify_uploaded_part_size is called with the correct key and file size."""
    archive_parts_dir = tmp_path / "parts"
    archive_parts_dir.mkdir(parents=True, exist_ok=True)
    part = archive_parts_dir / "drive.tar.gz.part-00001"
    part_content = b"hello archive"
    part.write_bytes(part_content)

    prefix = "drive/"
    part_key = f"{prefix}{part.name}"

    submission = _create_submission(session, drive_name="resmed202200024-testing")

    size_check_calls: list[tuple] = []

    def capture_size_check(_client, _bucket: str, key: str, expected_size: int) -> bool:
        size_check_calls.append((key, expected_size))
        return True

    manifest_size = 999  # deliberately different from len(part_content) to prove manifest wins

    monkeypatch.setattr("workers.submission_worker.object_exists", lambda *_a, **_k: (False, None))
    monkeypatch.setattr("workers.submission_worker.upload_file", lambda *_a, **_k: True)
    monkeypatch.setattr("workers.submission_worker.verify_uploaded_part_size", capture_size_check)

    success, _ = _upload_chunked_archive_parts(
        session=session,
        submission=submission,
        client=object(),
        bucket_name="bucket",
        object_prefix=prefix,
        archive_parts_dir=archive_parts_dir,
        archive_parts=[
            ArchivePartInfo(index=1, file_name=part.name, size_bytes=manifest_size, sha256="a"),
        ],
        timeout_seconds=60,
    )

    assert success is True
    assert len(size_check_calls) == 1
    assert size_check_calls[0] == (part_key, manifest_size)
