"""Tests for chunked tar archive packaging."""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

from api.archive_chunks import build_chunked_tar_archive


def _write_file(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as file_obj:
        file_obj.write(b"A" * size)


def test_build_chunked_tar_archive_writes_parts_and_manifest(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    _write_file(source_dir / "a.txt", 900)
    _write_file(source_dir / "nested" / "b.bin", 2100)
    _write_file(source_dir / "nested" / "c.bin", 1800)

    output_dir = tmp_path / "output"
    result = build_chunked_tar_archive(
        source_dir=source_dir,
        output_dir=output_dir,
        base_name="drive-archive",
        part_size_bytes=100,
    )

    assert len(result.parts) > 1
    assert result.total_bytes > 0
    assert result.manifest_path.exists()
    for part in result.parts:
        assert part.size_bytes <= 100
        assert (output_dir / part.file_name).exists()

    with open(result.manifest_path, "r", encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    assert manifest["archive_name"] == "drive-archive"
    assert manifest["archive_format"] == "tar.gz"
    assert manifest["part_count"] == len(result.parts)
    assert manifest["total_bytes"] == result.total_bytes


def test_chunked_parts_reassemble_into_valid_tar(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    _write_file(source_dir / "one.txt", 1500)
    _write_file(source_dir / "two.txt", 1600)

    output_dir = tmp_path / "output"
    result = build_chunked_tar_archive(
        source_dir=source_dir,
        output_dir=output_dir,
        base_name="drive-archive",
        part_size_bytes=700,
    )

    reassembled_tar = tmp_path / "reassembled.tar"
    with open(reassembled_tar, "wb") as destination:
        for part in sorted(result.parts, key=lambda p: p.index):
            with open(output_dir / part.file_name, "rb") as source:
                destination.write(source.read())

    with tarfile.open(reassembled_tar, "r:gz") as tar_obj:
        names = tar_obj.getnames()

    assert any(name.endswith("source/one.txt") for name in names)
    assert any(name.endswith("source/two.txt") for name in names)
