"""Tests for archive reassembly utilities."""

from __future__ import annotations

import tarfile
from pathlib import Path

import pytest

from api.archive_chunks import build_chunked_tar_archive
from api.archive_reassembly import (
    ordered_part_object_keys,
    reassemble_archive_from_manifest,
)


def _write_file(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as file_obj:
        file_obj.write(b"Z" * size)


def test_reassemble_archive_from_manifest_rebuilds_valid_tar(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    _write_file(source_dir / "a.bin", 1500)
    _write_file(source_dir / "nested" / "b.bin", 1800)

    parts_dir = tmp_path / "parts"
    chunked = build_chunked_tar_archive(
        source_dir=source_dir,
        output_dir=parts_dir,
        base_name="drive",
        part_size_bytes=700,
    )

    rebuilt_tar = tmp_path / "rebuilt" / "archive.tar"
    reassemble_archive_from_manifest(
        parts_dir=parts_dir,
        manifest_path=chunked.manifest_path,
        output_tar_path=rebuilt_tar,
    )

    with tarfile.open(rebuilt_tar, "r:gz") as tar_obj:
        names = tar_obj.getnames()

    assert any(name.endswith("source/a.bin") for name in names)
    assert any(name.endswith("source/nested/b.bin") for name in names)


def test_reassemble_archive_fails_on_checksum_mismatch(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    _write_file(source_dir / "a.bin", 1300)

    parts_dir = tmp_path / "parts"
    chunked = build_chunked_tar_archive(
        source_dir=source_dir,
        output_dir=parts_dir,
        base_name="drive",
        part_size_bytes=512,
    )

    first_part = sorted(parts_dir.glob("*.tar.gz.part-*"))[0]
    first_part_size = first_part.stat().st_size
    first_part.write_bytes(b"X" * first_part_size)

    with pytest.raises(ValueError, match="Part checksum mismatch"):
        reassemble_archive_from_manifest(
            parts_dir=parts_dir,
            manifest_path=chunked.manifest_path,
            output_tar_path=tmp_path / "rebuilt.tar",
        )


def test_ordered_part_object_keys_uses_manifest_order(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    _write_file(source_dir / "a.bin", 1100)

    parts_dir = tmp_path / "parts"
    chunked = build_chunked_tar_archive(
        source_dir=source_dir,
        output_dir=parts_dir,
        base_name="drive",
        part_size_bytes=300,
    )

    # manifest already ordered, but this verifies key assembly from manifest entries
    from api.archive_reassembly import load_archive_manifest

    manifest = load_archive_manifest(chunked.manifest_path)
    keys = ordered_part_object_keys("drive/", manifest)

    assert keys
    assert keys[0].startswith("drive/")
    assert keys[0].endswith(".tar.gz.part-00001")
