"""Tests for local artifact cleanup helpers."""

from pathlib import Path

from api.main import _cleanup_job_artifacts


def test_cleanup_job_artifacts_removes_generated_outputs(tmp_path: Path) -> None:
    """Cleanup removes output directory and contents."""
    drive_name = "restst000000001-testing"
    output_location = tmp_path / "bagit_temp"
    output_location.mkdir(parents=True, exist_ok=True)

    zip_file = output_location / f"{drive_name}.zip"
    manifests_dir = output_location / f"{drive_name}_manifests"

    zip_file.write_text("zip-bytes", encoding="utf-8")
    manifests_dir.mkdir(parents=True, exist_ok=True)
    (manifests_dir / "manifest-sha256.txt").write_text("hash", encoding="utf-8")

    success, error = _cleanup_job_artifacts(drive_name, output_location)

    assert success is True
    assert error is None
    assert not zip_file.exists()
    assert not manifests_dir.exists()
    assert not output_location.exists()


def test_cleanup_job_artifacts_is_idempotent_when_nothing_exists(
    tmp_path: Path,
) -> None:
    """Cleanup succeeds when files are already missing."""
    drive_name = "restst000000001-testing"
    output_location = tmp_path / "bagit_temp"
    output_location.mkdir(parents=True, exist_ok=True)

    success, error = _cleanup_job_artifacts(drive_name, output_location)

    assert success is True
    assert error is None
