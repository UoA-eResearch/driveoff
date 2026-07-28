"""Tests for chunked tar archive packaging."""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest

from packaging.archive_chunks import build_chunked_tar_archive, verify_tar_parts_stream

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


# ── verify_tar_parts_stream ──────────────────────────────────────────────────


def test_verify_tar_parts_stream_passes_for_valid_archive(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    _write_file(source_dir / "a.txt", 1000)
    _write_file(source_dir / "b.txt", 1000)

    output_dir = tmp_path / "output"
    result = build_chunked_tar_archive(
        source_dir=source_dir,
        output_dir=output_dir,
        base_name="drive-archive",
        part_size_bytes=500,
    )

    # Should not raise
    verify_tar_parts_stream(parts=result.parts, parts_dir=output_dir)


def test_verify_tar_parts_stream_raises_on_missing_part(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    _write_file(source_dir / "a.txt", 1000)

    output_dir = tmp_path / "output"
    result = build_chunked_tar_archive(
        source_dir=source_dir,
        output_dir=output_dir,
        base_name="drive-archive",
        part_size_bytes=300,
    )

    # Delete the first part
    (output_dir / result.parts[0].file_name).unlink()

    with pytest.raises(FileNotFoundError, match="Archive part file not found"):
        verify_tar_parts_stream(parts=result.parts, parts_dir=output_dir)


def test_verify_tar_parts_stream_raises_on_corrupt_part(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    _write_file(source_dir / "a.txt", 2000)

    output_dir = tmp_path / "output"
    result = build_chunked_tar_archive(
        source_dir=source_dir,
        output_dir=output_dir,
        base_name="drive-archive",
        part_size_bytes=400,
    )

    # Overwrite the last part with garbage to corrupt the gzip stream
    last_part = output_dir / result.parts[-1].file_name
    last_part.write_bytes(b"\xff" * last_part.stat().st_size)

    with pytest.raises(tarfile.TarError):
        verify_tar_parts_stream(parts=result.parts, parts_dir=output_dir)


def test_verify_tar_parts_stream_single_part(tmp_path: Path) -> None:
    """Works correctly when the archive fits in a single part."""
    source_dir = tmp_path / "source"
    _write_file(source_dir / "small.txt", 50)

    output_dir = tmp_path / "output"
    result = build_chunked_tar_archive(
        source_dir=source_dir,
        output_dir=output_dir,
        base_name="drive-archive",
        part_size_bytes=512 * 1024 * 1024,  # 512 MB — file will be one part
    )

    assert len(result.parts) == 1
    verify_tar_parts_stream(parts=result.parts, parts_dir=output_dir)
