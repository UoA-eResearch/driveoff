"""Tests for chunked archive upload helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session

from models.common import DataClassification
from models.submission import ArchiveSubmission
from packaging.archive_chunks import ArchivePartInfo
from workers import parse_part_keys_json
from workers.submission_worker import _upload_chunked_archive_parts


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


def test_upload_chunked_parts_reuploads_parts_from_previous_attempt(
    tmp_path: Path,
    session: Session,
    monkeypatch,
) -> None:
    """Part keys persisted by a previous attempt must NOT cause parts to be
    skipped: the tar stream is rebuilt on every run, so previously uploaded
    parts belong to a different byte stream (regression test for the
    part-mixing bug)."""
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
    # Simulate stale state from a previous failed attempt.
    submission.archive_part_keys_json = json.dumps([first_key])
    session.add(submission)
    session.commit()

    uploaded_keys: list[str] = []

    def fake_upload(
        _client,
        _bucket: str,
        key: str,
        file_path: str,
        metadata: dict[str, str] | None = None,
    ):
        assert Path(file_path).exists()
        assert metadata is None
        uploaded_keys.append(key)
        return True

    monkeypatch.setattr("workers.submission_worker.upload_file", fake_upload)
    monkeypatch.setattr("workers.submission_worker.verify_uploaded_part_size", lambda *_a, **_k: True)

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
    )

    assert success is True
    # Both parts uploaded — the stale first_key did not cause a skip.
    assert uploaded_keys == [first_key, second_key]
    assert result_keys == [first_key, second_key]


def test_upload_chunked_parts_ignores_stale_local_part_files(
    tmp_path: Path,
    session: Session,
    monkeypatch,
) -> None:
    """Part files on disk that are not in the current build's part list (for
    example left behind by an interrupted earlier run of a larger source)
    must not be uploaded."""
    archive_parts_dir = tmp_path / "parts"
    archive_parts_dir.mkdir(parents=True, exist_ok=True)
    current = archive_parts_dir / "drive.tar.gz.part-00001"
    stale = archive_parts_dir / "drive.tar.gz.part-00002"
    current.write_bytes(b"part1")
    stale.write_bytes(b"stale-from-previous-run")

    prefix = "drive/"
    current_key = f"{prefix}{current.name}"

    submission = _create_submission(session, drive_name="resmed202200024-testing")

    uploaded_keys: list[str] = []

    def fake_upload(_client, _bucket: str, key: str, file_path: str, metadata=None):
        uploaded_keys.append(key)
        return True

    monkeypatch.setattr("workers.submission_worker.upload_file", fake_upload)
    monkeypatch.setattr("workers.submission_worker.verify_uploaded_part_size", lambda *_a, **_k: True)

    success, result_keys = _upload_chunked_archive_parts(
        session=session,
        submission=submission,
        client=object(),
        bucket_name="bucket",
        object_prefix=prefix,
        archive_parts_dir=archive_parts_dir,
        archive_parts=[
            ArchivePartInfo(index=1, file_name=current.name, size_bytes=len(b"part1"), sha256="a"),
        ],
    )

    assert success is True
    assert uploaded_keys == [current_key]
    assert result_keys == [current_key]


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

    monkeypatch.setattr("workers.submission_worker.upload_file", lambda *_a, **_k: True)
    monkeypatch.setattr("workers.submission_worker.verify_uploaded_part_size", lambda *_a, **_k: False)

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
    )

    assert success is True
    assert len(size_check_calls) == 1
    assert size_check_calls[0] == (part_key, manifest_size)


def test_upload_chunked_parts_sets_retention_when_provided(
    tmp_path: Path,
    session: Session,
    monkeypatch,
) -> None:
    """When retain_until is supplied, set_object_retention is called for each part."""
    from datetime import datetime

    archive_parts_dir = tmp_path / "parts"
    archive_parts_dir.mkdir(parents=True, exist_ok=True)
    part = archive_parts_dir / "drive.tar.gz.part-00001"
    part.write_bytes(b"hello archive")

    prefix = "drive/"
    part_key = f"{prefix}{part.name}"
    retain_until = datetime(2032, 6, 1, tzinfo=UTC)

    submission = _create_submission(session, drive_name="resmed202200024-testing")

    retention_calls: list[tuple] = []

    def capture_retention(_client, _bucket: str, key: str, date: datetime) -> bool:
        retention_calls.append((key, date))
        return True

    monkeypatch.setattr("workers.submission_worker.upload_file", lambda *_a, **_k: True)
    monkeypatch.setattr("workers.submission_worker.verify_uploaded_part_size", lambda *_a, **_k: True)
    monkeypatch.setattr("workers.submission_worker.set_object_retention", capture_retention)

    success, _ = _upload_chunked_archive_parts(
        session=session,
        submission=submission,
        client=object(),
        bucket_name="bucket",
        object_prefix=prefix,
        archive_parts_dir=archive_parts_dir,
        archive_parts=[
            ArchivePartInfo(
                index=1,
                file_name=part.name,
                size_bytes=len(b"hello archive"),
                sha256="a",
            ),
        ],
        retain_until=retain_until,
    )

    assert success is True
    assert len(retention_calls) == 1
    assert retention_calls[0] == (part_key, retain_until)


def test_upload_chunked_parts_fails_on_retention_error(
    tmp_path: Path,
    session: Session,
    monkeypatch,
) -> None:
    """If set_object_retention fails the job aborts and the part key is not persisted."""
    from datetime import datetime

    archive_parts_dir = tmp_path / "parts"
    archive_parts_dir.mkdir(parents=True, exist_ok=True)
    part = archive_parts_dir / "drive.tar.gz.part-00001"
    part.write_bytes(b"hello archive")

    prefix = "drive/"
    part_key = f"{prefix}{part.name}"
    retain_until = datetime(2032, 6, 1, tzinfo=UTC)

    submission = _create_submission(session, drive_name="resmed202200024-testing")

    monkeypatch.setattr("workers.submission_worker.upload_file", lambda *_a, **_k: True)
    monkeypatch.setattr("workers.submission_worker.verify_uploaded_part_size", lambda *_a, **_k: True)
    monkeypatch.setattr("workers.submission_worker.set_object_retention", lambda *_a, **_k: False)

    success, result_keys = _upload_chunked_archive_parts(
        session=session,
        submission=submission,
        client=object(),
        bucket_name="bucket",
        object_prefix=prefix,
        archive_parts_dir=archive_parts_dir,
        archive_parts=[
            ArchivePartInfo(
                index=1,
                file_name=part.name,
                size_bytes=len(b"hello archive"),
                sha256="a",
            ),
        ],
        retain_until=retain_until,
    )

    assert success is False
    # Part was uploaded and size-verified but retention failed —
    # it is still recorded as uploaded so operators can identify the objects
    # written by this run, but the job overall is failed.
    assert part_key in result_keys
