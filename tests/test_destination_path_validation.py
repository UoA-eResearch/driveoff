"""Tests for retrieval destination path allowlist validation.

The allowed retrieval base is derived from the drive storage settings:
SMB_DRIVE_BASE_PATH on Windows (or when it is a local path), and
SMB_LINUX_MOUNT_BASE_PATH on Linux when the SMB base is a UNC path.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from config import get_settings
from utils.paths import resolve_storage_base_path, validate_destination_path


@pytest.fixture(name="vast_base")
def vast_base_fixture(tmp_path: Path, monkeypatch) -> Path:
    """Point SMB_DRIVE_BASE_PATH at a local base under tmp_path.

    A local (non-UNC) base is used directly on every platform, so these tests
    exercise the same code path on Windows and Linux.
    """
    base = tmp_path / "vast"
    base.mkdir()
    monkeypatch.setattr(get_settings(), "smb_drive_base_path", str(base))
    return base


def test_destination_under_base_is_accepted(vast_base: Path) -> None:
    dest = vast_base / "restst000000001-testing"
    dest.mkdir()
    assert validate_destination_path(str(dest)) == dest.resolve()


def test_destination_equal_to_base_is_accepted(vast_base: Path) -> None:
    assert validate_destination_path(str(vast_base)) == vast_base.resolve()


def test_destination_outside_base_is_rejected(vast_base: Path, tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    with pytest.raises(PermissionError, match="not within the allowed retrieval location"):
        validate_destination_path(str(outside))


def test_destination_traversal_out_of_base_is_rejected(vast_base: Path, tmp_path: Path) -> None:
    """A path textually under the base must not escape it via `..` segments."""
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    sneaky = vast_base / ".." / "elsewhere"
    with pytest.raises(PermissionError, match="not within the allowed retrieval location"):
        validate_destination_path(str(sneaky))


def test_relative_destination_is_rejected(vast_base: Path) -> None:
    with pytest.raises(PermissionError, match="must be absolute"):
        validate_destination_path("relative/path")


def test_unconfigured_storage_base_fails_closed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "smb_drive_base_path", "")
    dest = tmp_path / "anywhere"
    dest.mkdir()
    with pytest.raises(RuntimeError, match="SMB_DRIVE_BASE_PATH is not configured"):
        validate_destination_path(str(dest))


def test_missing_destination_under_base_raises_not_found(vast_base: Path) -> None:
    with pytest.raises(FileNotFoundError, match="does not exist"):
        validate_destination_path(str(vast_base / "nonexistent"))


def test_symlink_escaping_base_is_rejected(vast_base: Path, tmp_path: Path) -> None:
    """A symlink inside the base pointing outside it must be rejected."""
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    link = vast_base / "sneaky-link"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation not permitted on this platform")
    with pytest.raises(PermissionError, match="not within the allowed retrieval location"):
        validate_destination_path(str(link))


# ---------------------------------------------------------------------------
# Linux + UNC branch: the allowed base is the CIFS mount parent
# ---------------------------------------------------------------------------


def test_linux_unc_base_uses_mount_parent(tmp_path: Path, monkeypatch) -> None:
    """On Linux with a UNC SMB base, destinations are validated against
    SMB_LINUX_MOUNT_BASE_PATH."""
    mount_base = tmp_path / "mnt"
    dest = mount_base / "restst000000001-testing"
    dest.mkdir(parents=True)
    monkeypatch.setattr("utils.paths.is_windows_runtime", lambda: False)
    monkeypatch.setattr(get_settings(), "smb_drive_base_path", "//server/share")
    monkeypatch.setattr(get_settings(), "smb_linux_mount_base_path", str(mount_base))

    assert resolve_storage_base_path() == mount_base
    assert validate_destination_path(str(dest)) == dest.resolve()

    outside = tmp_path / "elsewhere"
    outside.mkdir()
    with pytest.raises(PermissionError, match="not within the allowed retrieval location"):
        validate_destination_path(str(outside))


def test_linux_unc_base_without_mount_parent_fails_closed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("utils.paths.is_windows_runtime", lambda: False)
    monkeypatch.setattr(get_settings(), "smb_drive_base_path", "//server/share")
    monkeypatch.setattr(get_settings(), "smb_linux_mount_base_path", "")
    dest = tmp_path / "anywhere"
    dest.mkdir()
    with pytest.raises(RuntimeError, match="SMB_LINUX_MOUNT_BASE_PATH is required"):
        validate_destination_path(str(dest))
