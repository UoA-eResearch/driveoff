"""Chunked archive packaging helpers for very large drive uploads."""

from __future__ import annotations

import hashlib
import json
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


@dataclass
class ArchivePartInfo:
    """Metadata for a single archive part file."""

    index: int
    file_name: str
    size_bytes: int
    sha256: str


@dataclass
class ChunkedArchiveResult:
    """Result of packaging a directory into chunked tar parts."""

    parts: list[ArchivePartInfo]
    total_bytes: int
    manifest_path: Path


class _SplitPartWriter:
    """Write byte streams into sequentially numbered part files."""

    def __init__(self, output_dir: Path, base_name: str, part_size_bytes: int) -> None:
        if part_size_bytes <= 0:
            raise ValueError("part_size_bytes must be greater than zero")

        self.output_dir = output_dir
        self.base_name = base_name
        self.part_size_bytes = part_size_bytes

        self._parts: list[ArchivePartInfo] = []
        self._current_fp: BinaryIO | None = None
        self._current_index = 0
        self._current_size = 0
        self._current_hasher: hashlib._Hash | None = None
        self._total_bytes = 0

    @property
    def parts(self) -> list[ArchivePartInfo]:
        return self._parts

    @property
    def total_bytes(self) -> int:
        return self._total_bytes

    def writable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._total_bytes

    def write(self, data: bytes) -> int:
        if not data:
            return 0

        start = 0
        data_len = len(data)
        while start < data_len:
            if self._current_fp is None or self._current_size >= self.part_size_bytes:
                self._open_new_part()

            assert self._current_fp is not None
            assert self._current_hasher is not None
            remaining = self.part_size_bytes - self._current_size
            chunk = data[start : start + remaining]
            self._current_fp.write(chunk)
            self._current_hasher.update(chunk)
            written = len(chunk)
            self._current_size += written
            self._total_bytes += written
            start += written

            if self._current_size >= self.part_size_bytes:
                self._finalize_current_part()

        return data_len

    def flush(self) -> None:
        if self._current_fp is not None:
            self._current_fp.flush()

    def close(self) -> None:
        if self._current_fp is not None:
            self._finalize_current_part()

    def _open_new_part(self) -> None:
        if self._current_fp is not None:
            self._finalize_current_part()

        self._current_index += 1
        self._current_size = 0
        self._current_hasher = hashlib.sha256()

        file_name = f"{self.base_name}.tar.part-{self._current_index:05d}"
        file_path = self.output_dir / file_name
        self._current_fp = open(file_path, "wb")

    def _finalize_current_part(self) -> None:
        assert self._current_fp is not None
        assert self._current_hasher is not None

        file_name = Path(self._current_fp.name).name
        self._current_fp.flush()
        self._current_fp.close()
        self._parts.append(
            ArchivePartInfo(
                index=self._current_index,
                file_name=file_name,
                size_bytes=self._current_size,
                sha256=self._current_hasher.hexdigest(),
            )
        )

        self._current_fp = None
        self._current_hasher = None
        self._current_size = 0


def build_chunked_tar_archive(
    source_dir: Path,
    output_dir: Path,
    base_name: str,
    part_size_bytes: int,
    manifest_file_name: str = "archive-manifest.json",
) -> ChunkedArchiveResult:
    """Create a streamed tar split into sequential part files.

    The resulting part files are plain byte segments of one logical tar stream.
    Reassembly is done by concatenating parts in index order.
    """
    if not source_dir.exists() or not source_dir.is_dir():
        raise FileNotFoundError(f"source_dir does not exist or is not a directory: {source_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    writer = _SplitPartWriter(output_dir=output_dir, base_name=base_name, part_size_bytes=part_size_bytes)

    try:
        with tarfile.open(fileobj=writer, mode="w|", format=tarfile.PAX_FORMAT) as tar_stream:
            tar_stream.add(str(source_dir), arcname=source_dir.name, recursive=True)
    finally:
        writer.close()

    manifest = {
        "archive_name": base_name,
        "archive_format": "tar",
        "layout": "chunked_objects",
        "source_root": source_dir.name,
        "total_bytes": writer.total_bytes,
        "part_count": len(writer.parts),
        "parts": [
            {
                "index": p.index,
                "file_name": p.file_name,
                "size_bytes": p.size_bytes,
                "sha256": p.sha256,
            }
            for p in writer.parts
        ],
    }
    manifest_path = output_dir / manifest_file_name
    with open(manifest_path, "w", encoding="utf-8") as manifest_file:
        json.dump(manifest, manifest_file, indent=2, sort_keys=True)

    return ChunkedArchiveResult(
        parts=writer.parts,
        total_bytes=writer.total_bytes,
        manifest_path=manifest_path,
    )
