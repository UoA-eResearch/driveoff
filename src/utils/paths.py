"""Filesystem path resolution and validation utilities for archive operations."""

from __future__ import annotations

import logging
import platform
from pathlib import Path

from config import get_settings
from utils.logging import log_event


def is_windows_runtime() -> bool:
    """Return True when running on Windows.

    Uses platform.system() instead of os.name to avoid some static analysers
    folding branches as unreachable based on host/editor platform settings.
    """
    return platform.system().lower().startswith("win")


def validate_archive_path_configuration() -> None:
    """Validate archive path configuration at startup.

    On non-Windows with UNC SMB base paths, a local mount base is required so
    bagit/rocrate can perform filesystem operations.
    """
    settings = get_settings()
    smb_base = settings.smb_drive_base_path.strip()
    if is_windows_runtime() or not smb_base.startswith("//"):
        return

    mount_base = settings.smb_linux_mount_base_path.strip()
    if not mount_base:
        raise RuntimeError(
            "SMB_LINUX_MOUNT_BASE_PATH is required on Linux when "
            "SMB_DRIVE_BASE_PATH is a UNC path."
        )

    mount_path = Path(mount_base)
    if not mount_path.exists() or not mount_path.is_dir():
        raise RuntimeError(
            "Configured SMB_LINUX_MOUNT_BASE_PATH is invalid: "
            f"{mount_path}. Ensure the CIFS mount parent exists."
        )

    log_event(
        logging.INFO,
        "startup.archive_path_config_validated",
        smb_drive_base_path=smb_base,
        smb_linux_mount_base_path=str(mount_path),
    )


def resolve_drive_path_for_archive(drive_name: str) -> Path:
    """Resolve a filesystem path usable by bagit/rocrate for archive operations.

    On Linux, UNC paths (//server/share) are not valid local filesystem targets.
    In that case, require SMB_LINUX_MOUNT_BASE_PATH and resolve to:
    <mount_base>/<drive_name>.
    """
    settings = get_settings()
    smb_base = settings.smb_drive_base_path.strip()
    drive_path = Path(smb_base) / drive_name

    if is_windows_runtime() or not str(drive_path).startswith("//"):
        return drive_path

    mount_base = settings.smb_linux_mount_base_path.strip()
    if not mount_base:
        raise RuntimeError(
            "SMB_LINUX_MOUNT_BASE_PATH is required on Linux when "
            "SMB_DRIVE_BASE_PATH is a UNC path."
        )

    mounted_drive_path = Path(mount_base) / drive_name
    if not mounted_drive_path.exists():
        raise FileNotFoundError(
            "Configured mounted drive path does not exist: "
            f"{mounted_drive_path}. Ensure the CIFS mount is available."
        )
    return mounted_drive_path


def validate_archive_path_access(drive_name: str) -> Path:
    """Validate drive path can be read and written before scheduling archive job.

    Synchronous validation to be called from submission endpoints (before 201).
    Resolves the archive path and validates read/write permissions early.
    """
    drive_path = resolve_drive_path_for_archive(drive_name)

    if not drive_path.exists() or not drive_path.is_dir():
        raise FileNotFoundError(
            f"Drive path does not exist or is not a directory: {drive_path}"
        )

    # Read probe to validate source permissions
    try:
        _ = next(drive_path.iterdir(), None)
    except Exception as e:
        raise PermissionError(f"Cannot read source directory {drive_path}: {e}") from e

    # Write probe to validate output permissions
    probe_file = drive_path / ".driveoff_write_probe"
    try:
        with open(probe_file, "wb") as f:
            f.write(b"ok")
        probe_file.unlink(missing_ok=True)
    except Exception as e:
        raise PermissionError(f"Cannot write to directory {drive_path}: {e}") from e

    # Validate local temp base is writable for generated archive artifacts.
    temp_base = Path(get_settings().archive_temp_base_path).expanduser()
    try:
        temp_base.mkdir(parents=True, exist_ok=True)
        temp_probe = temp_base / ".driveoff_temp_probe"
        with open(temp_probe, "wb") as f:
            f.write(b"ok")
        temp_probe.unlink(missing_ok=True)
    except Exception as e:
        raise PermissionError(
            f"Cannot write to local archive temp base {temp_base}: {e}"
        ) from e

    return drive_path


def resolve_archive_output_location(drive_name: str) -> Path:
    """Resolve local output directory for generated archive artifacts."""
    temp_base = Path(get_settings().archive_temp_base_path).expanduser()
    safe_drive_name = drive_name.replace("/", "_").replace("\\", "_")
    return temp_base / "bagit_temp" / safe_drive_name


def validate_destination_path(destination_path: str) -> Path:
    """Validate that a destination path for archive retrieval exists and is writable.

    Raises FileNotFoundError if the path does not exist or is not a directory,
    and PermissionError if write access is denied.
    """
    dest = Path(destination_path)
    if not dest.exists() or not dest.is_dir():
        raise FileNotFoundError(
            f"Destination path does not exist or is not a directory: {dest}"
        )
    probe_file = dest / ".driveoff_dest_probe"
    try:
        with open(probe_file, "wb") as f:
            f.write(b"ok")
        probe_file.unlink(missing_ok=True)
    except Exception as e:
        raise PermissionError(f"Cannot write to destination path {dest}: {e}") from e
    return dest
