"""Tests for local artifact cleanup helpers."""

from pathlib import Path

from workers.submission_worker import _cleanup_job_artifacts


def test_cleanup_job_artifacts_removes_generated_outputs(tmp_path: Path) -> None:
    """Cleanup removes output directory and contents."""
    drive_name = "restst000000001-testing"
    output_location = tmp_path / "bagit_temp" / drive_name
    output_location.mkdir(parents=True, exist_ok=True)

    archive_parts_dir = output_location / "archive_parts"
    archive_parts_dir.mkdir()
    (archive_parts_dir / f"{drive_name}.tar.gz.part-00001").write_bytes(
        b"fake-tar-bytes"
    )
    (archive_parts_dir / "archive-manifest.json").write_text("{}", encoding="utf-8")
    manifests_dir = output_location / f"{drive_name}_manifests"
    manifests_dir.mkdir()
    (manifests_dir / "manifest-sha256.txt").write_text("hash", encoding="utf-8")

    success, error = _cleanup_job_artifacts(drive_name, output_location)

    assert success is True
    assert error is None
    assert not archive_parts_dir.exists()
    assert not manifests_dir.exists()
    assert not output_location.exists()


def test_cleanup_job_artifacts_is_idempotent_when_nothing_exists(
    tmp_path: Path,
) -> None:
    """Cleanup succeeds when files are already missing."""
    drive_name = "restst000000001-testing"
    output_location = tmp_path / "bagit_temp" / drive_name
    output_location.mkdir(parents=True, exist_ok=True)

    success, error = _cleanup_job_artifacts(drive_name, output_location)

    assert success is True
    assert error is None
