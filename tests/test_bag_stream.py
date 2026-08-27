"""Tests for virtual bagging - streaming a BagIt bag structure into a tar.

The bagit library is used as the validation oracle: whatever our streamer
writes must extract into a bag that the independent implementation accepts.
"""

from __future__ import annotations

import tarfile
from pathlib import Path

import bagit
import pytest

from packaging.archive_chunks import (
    _verify_bag_payload_hashes,
    build_chunked_tar_archive,
    verify_tar_parts_stream,
)
from packaging.archive_reassembly import reassemble_archive_from_manifest
from packaging.bag_stream import write_bagged_tree


def _make_source(tmp_path: Path) -> Path:
    src = tmp_path / "resbag000000001-testing"
    (src / "nested" / "deeper").mkdir(parents=True)
    (src / "empty-dir").mkdir()
    (src / "a.txt").write_bytes(b"alpha")
    (src / "nested" / "b.bin").write_bytes(b"B" * 3000)
    (src / "nested" / "deeper" / "c with spaces.txt").write_bytes(b"gamma")
    (src / "däta.txt").write_bytes(b"unicode name")
    (src / "empty.txt").write_bytes(b"")
    return src


def _snapshot(src: Path) -> list[str]:
    return sorted(p.relative_to(src).as_posix() for p in src.rglob("*"))


def test_write_bagged_tree_roundtrip_validates_with_bagit(tmp_path: Path) -> None:
    src = _make_source(tmp_path)
    before = _snapshot(src)

    crate = tmp_path / "scratch" / "ro-crate-metadata.json"
    crate.parent.mkdir()
    crate.write_text('{"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": []}', encoding="utf-8")

    tar_path = tmp_path / "bag.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        result = write_bagged_tree(
            tar,
            source_dir=src,
            arcname_root=src.name,
            bag_info={"project_id": "123", "drive_name": src.name},
            extra_payload_files=[(crate, crate.name)],
        )

    # The source directory is never modified.
    assert _snapshot(src) == before
    assert not (src / "bagit.txt").exists()

    # Payload-Oxum covers the source files plus the injected crate file.
    source_files = [p for p in src.rglob("*") if p.is_file()]
    assert result.payload_file_count == len(source_files) + 1
    assert result.payload_byte_count == sum(p.stat().st_size for p in source_files) + crate.stat().st_size

    # Extract and let the bagit library judge the result.
    extract_dir = tmp_path / "extracted"
    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(extract_dir, filter="data")

    bag_root = extract_dir / src.name
    bag = bagit.Bag(str(bag_root))
    bag.validate(processes=1)

    assert (bag_root / "data" / "ro-crate-metadata.json").is_file()
    assert (bag_root / "data" / "empty-dir").is_dir()
    assert (bag_root / "data" / "däta.txt").read_bytes() == b"unicode name"
    assert bag.info["project_id"] == "123"
    assert bag.info["Payload-Oxum"] == result.payload_oxum
    assert "Bagging-Date" in bag.info


def test_write_bagged_tree_rejects_already_bagged_source(tmp_path: Path) -> None:
    src = tmp_path / "drive"
    (src / "data").mkdir(parents=True)
    (src / "bagit.txt").write_text("BagIt-Version: 0.97\n", encoding="utf-8")

    with tarfile.open(tmp_path / "t.tar.gz", "w:gz") as tar:
        with pytest.raises(ValueError, match="already an on-disk BagIt bag"):
            write_bagged_tree(tar, source_dir=src, arcname_root="drive")


def test_write_bagged_tree_missing_source_raises(tmp_path: Path) -> None:
    with tarfile.open(tmp_path / "t.tar.gz", "w:gz") as tar:
        with pytest.raises(FileNotFoundError):
            write_bagged_tree(tar, source_dir=tmp_path / "nope", arcname_root="nope")


def test_chunked_bag_archive_verifies_and_reassembles(tmp_path: Path) -> None:
    """Full pipeline: bag-stream into chunked parts, verify, reassemble, validate."""
    src = _make_source(tmp_path)
    parts_dir = tmp_path / "parts"

    result = build_chunked_tar_archive(
        source_dir=src,
        output_dir=parts_dir,
        base_name=src.name,
        part_size_bytes=512,
        content_writer=lambda tar: write_bagged_tree(tar, source_dir=src, arcname_root=src.name),
    )
    assert len(result.parts) > 1

    # Streaming verification includes payload hashes vs the in-tar manifest.
    verify_tar_parts_stream(result.parts, parts_dir)

    out_tar = tmp_path / "out.tar.gz"
    reassemble_archive_from_manifest(
        parts_dir=parts_dir,
        manifest_path=result.manifest_path,
        output_tar_path=out_tar,
    )
    extract_dir = tmp_path / "extracted"
    with tarfile.open(out_tar, "r:gz") as tar:
        tar.extractall(extract_dir, filter="data")

    bag = bagit.Bag(str(extract_dir / src.name))
    bag.validate(processes=1)


def test_verify_bag_payload_hashes_detects_problems() -> None:
    manifest = b"abc  data/a.txt\n"

    # Matching hashes pass silently.
    _verify_bag_payload_hashes(manifest, {"data/a.txt": "abc"})

    with pytest.raises(tarfile.TarError, match="checksum mismatch"):
        _verify_bag_payload_hashes(manifest, {"data/a.txt": "zzz"})

    with pytest.raises(tarfile.TarError, match="missing from the archive"):
        _verify_bag_payload_hashes(manifest, {})

    with pytest.raises(tarfile.TarError, match="not listed in the bag manifest"):
        _verify_bag_payload_hashes(manifest, {"data/a.txt": "abc", "data/extra.txt": "def"})
