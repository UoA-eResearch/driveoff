"""Archive part reassembly utilities driven by manifest ordering."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def load_archive_manifest(manifest_path: Path) -> dict[str, Any]:
    """Load and validate a chunked archive manifest JSON file."""
    with open(manifest_path, "r", encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)

    if not isinstance(manifest, dict):
        raise ValueError("Archive manifest must be a JSON object")
    if not isinstance(manifest.get("parts"), list):
        raise ValueError("Archive manifest is missing 'parts' list")
    return manifest


def ordered_part_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Return part entries sorted by numeric index from the manifest."""
    parts = manifest.get("parts", [])
    if not isinstance(parts, list):
        raise ValueError("Archive manifest has invalid 'parts' value")

    validated: list[dict[str, Any]] = []
    for part in parts:
        if not isinstance(part, dict):
            raise ValueError("Archive manifest part entry must be an object")
        index = part.get("index")
        file_name = part.get("file_name")
        if not isinstance(index, int) or not isinstance(file_name, str):
            raise ValueError("Archive manifest part entry is missing index/file_name")
        validated.append(part)

    return sorted(validated, key=lambda item: int(item["index"]))


def ordered_part_object_keys(object_prefix: str, manifest: dict[str, Any]) -> list[str]:
    """Build ordered object keys from prefix + manifest part ordering."""
    return [f"{object_prefix}{part['file_name']}" for part in ordered_part_entries(manifest)]


def _sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as file_obj:
        while True:
            chunk = file_obj.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def reassemble_archive_from_manifest(
    *,
    parts_dir: Path,
    manifest_path: Path,
    output_tar_path: Path,
    verify_parts: bool = True,
) -> Path:
    """Rebuild a tar file by concatenating manifest-ordered part files.

    Args:
        parts_dir: Directory containing part files downloaded from object storage.
        manifest_path: Local path to archive-manifest.json.
        output_tar_path: Destination tar path.
        verify_parts: Whether to verify per-part size and sha256 values.
    """
    manifest = load_archive_manifest(manifest_path)
    parts = ordered_part_entries(manifest)

    output_tar_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_tar_path, "wb") as output_file:
        for part in parts:
            part_path = parts_dir / part["file_name"]
            if not part_path.exists() or not part_path.is_file():
                raise FileNotFoundError(f"Missing archive part file: {part_path}")

            if verify_parts:
                expected_size = part.get("size_bytes")
                if isinstance(expected_size, int) and part_path.stat().st_size != expected_size:
                    raise ValueError(
                        f"Part size mismatch for {part_path.name}: "
                        f"expected {expected_size}, got {part_path.stat().st_size}"
                    )

                expected_sha = part.get("sha256")
                if isinstance(expected_sha, str) and _sha256_file(part_path) != expected_sha:
                    raise ValueError(f"Part checksum mismatch for {part_path.name}")

            with open(part_path, "rb") as part_file:
                while True:
                    chunk = part_file.read(1024 * 1024)
                    if not chunk:
                        break
                    output_file.write(chunk)

    expected_total_bytes = manifest.get("total_bytes")
    if isinstance(expected_total_bytes, int):
        actual_total_bytes = output_tar_path.stat().st_size
        if actual_total_bytes != expected_total_bytes:
            raise ValueError(
                "Reassembled tar size mismatch: "
                f"expected {expected_total_bytes}, got {actual_total_bytes}"
            )

    return output_tar_path
