"""Tests for chunked archive upload helpers."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlmodel import Session

from api.main import _parse_uploaded_part_keys, _upload_chunked_archive_parts
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
    assert _parse_uploaded_part_keys(None) == []
    assert _parse_uploaded_part_keys("") == []
    assert _parse_uploaded_part_keys("{}") == []
    assert _parse_uploaded_part_keys("not-json") == []
    assert _parse_uploaded_part_keys('["a", "b"]') == ["a", "b"]


def test_upload_chunked_parts_resumes_skipping_existing(
    tmp_path: Path,
    session: Session,
    monkeypatch,
) -> None:
    archive_parts_dir = tmp_path / "parts"
    archive_parts_dir.mkdir(parents=True, exist_ok=True)
    first = archive_parts_dir / "drive.tar.part-00001"
    second = archive_parts_dir / "drive.tar.part-00002"
    first.write_bytes(b"part1")
    second.write_bytes(b"part2")

    prefix = "drive/"
    first_key = f"{prefix}{first.name}"
    second_key = f"{prefix}{second.name}"

    submission = _create_submission(session, drive_name="resmed202200024-testing")
    submission.activescale_part_keys_json = json.dumps([first_key])
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

    monkeypatch.setattr("api.main.object_exists", fake_exists)
    monkeypatch.setattr("api.main.upload_file", fake_upload)

    success, result_keys = _upload_chunked_archive_parts(
        session=session,
        submission=submission,
        client=object(),
        bucket_name="bucket",
        object_prefix=prefix,
        archive_parts_dir=archive_parts_dir,
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
    first = archive_parts_dir / "drive.tar.part-00001"
    first.write_bytes(b"part1")

    prefix = "drive/"
    expected_key = f"{prefix}{first.name}"

    submission = _create_submission(session, drive_name="resmed202200024-testing")

    monkeypatch.setattr("api.main.object_exists", lambda *_args, **_kwargs: (False, None))
    monkeypatch.setattr("api.main.upload_file", lambda *_args, **_kwargs: False)

    success, result_keys = _upload_chunked_archive_parts(
        session=session,
        submission=submission,
        client=object(),
        bucket_name="bucket",
        object_prefix=prefix,
        archive_parts_dir=archive_parts_dir,
        timeout_seconds=60,
    )

    assert success is False
    assert result_keys == []
    assert expected_key not in result_keys
