"""Chunked archive packaging helpers for very large drive uploads."""

from __future__ import annotations

import hashlib
import json
import os
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, cast


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


class _SplitPartWriter:  # pylint: disable=too-many-instance-attributes
    """Write byte streams into sequentially numbered part files."""

    def __init__(self, output_dir: Path, base_name: str, part_size_bytes: int) -> None:
        """Initialise the writer.

        Args:
            output_dir: Directory where part files will be written.
            base_name: Stem used to derive part file names.
            part_size_bytes: Maximum number of bytes per part file.
        """

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
        """Get the list of archive part information."""
        return self._parts

    @property
    def total_bytes(self) -> int:
        """Get the total number of bytes written across all parts."""
        return self._total_bytes

    def writable(self) -> bool:
        """Indicate whether this object supports writing."""
        return True

    def tell(self) -> int:
        """Return the current stream position (total bytes written so far).

        Required by the ``BinaryIO`` protocol; called internally by :mod:`tarfile`.
        """
        return self._total_bytes

    def write(self, data: bytes) -> int:
        """Write *data* to the current part, rolling over to a new part when full.

        Returns the number of bytes consumed (always ``len(data)``).
        """
        if not data:
            return 0

        start = 0
        data_len = len(data)
        while start < data_len:
            if self._current_fp is None:
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
        """Flush the current part file to the OS buffer."""
        if self._current_fp is not None:
            self._current_fp.flush()

    def close(self) -> None:
        """Finalise and close the current part file, if one is open."""
        if self._current_fp is not None:
            self._finalize_current_part()

    def __enter__(self) -> _SplitPartWriter:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, *_: object) -> None:
        self.close()
        if exc_type is not None:
            # Archive creation failed; delete every part file written so far
            # so that the output directory is clean for a retry.
            for part in self._parts:
                (self.output_dir / part.file_name).unlink(missing_ok=True)

    def _open_new_part(self) -> None:
        """Open the next numbered part file, ready to receive data.

        The caller is responsible for finalising any current part before
        calling this method.  This method only ever opens a new file.
        """
        self._current_index += 1
        self._current_hasher = hashlib.sha256()

        file_name = f"{self.base_name}.tar.gz.part-{self._current_index:05d}"
        file_path = self.output_dir / file_name
        self._current_fp = open(  # noqa: SIM115  # pylint: disable=consider-using-with
            file_path, "wb"
        )

    def _finalize_current_part(self) -> None:
        """Flush, close, and record :class:`ArchivePartInfo` for the current part."""
        assert self._current_fp is not None
        assert self._current_hasher is not None

        file_name = Path(self._current_fp.name).name
        self._current_fp.flush()
        os.fsync(self._current_fp.fileno())
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


class _ChainReader:
    """Read sequentially across an ordered list of part files without loading them into memory.

    Presents a file-like ``read()`` interface so the concatenated byte stream
    can be passed directly to :func:`tarfile.open` without first assembling a
    single file on disk.
    """

    def __init__(self, parts: list[ArchivePartInfo], parts_dir: Path) -> None:
        self._paths = [
            parts_dir / p.file_name for p in sorted(parts, key=lambda p: p.index)
        ]
        self._file_index = 0
        self._current_fp: BinaryIO | None = None

    def read(self, size: int = -1) -> bytes:
        """Read up to *size* bytes across part boundaries, or all remaining bytes if -1."""
        if size == 0:
            return b""

        buf = bytearray()
        remaining = size  # -1 means read everything

        while True:
            if self._current_fp is None:
                if self._file_index >= len(self._paths):
                    break
                self._current_fp = (
                    open(  # noqa: SIM115  # pylint: disable=consider-using-with
                        self._paths[self._file_index], "rb"
                    )
                )
                self._file_index += 1

            chunk = self._current_fp.read(remaining if remaining != -1 else -1)
            if chunk:
                buf.extend(chunk)
                if remaining != -1:
                    remaining -= len(chunk)
                    if remaining == 0:
                        break
            else:
                # Current file exhausted — move to next
                self._current_fp.close()
                self._current_fp = None

        return bytes(buf)

    def close(self) -> None:
        """Close any open file handle."""
        if self._current_fp is not None:
            self._current_fp.close()
            self._current_fp = None

    def __enter__(self) -> _ChainReader:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def verify_tar_parts_stream(parts: list[ArchivePartInfo], parts_dir: Path) -> None:
    """Verify the integrity of a chunked tar.gz archive by streaming all parts.

    Chains the ordered part files into a single logical byte stream and passes
    it to :func:`tarfile.open` in streaming read mode (``r|gz``).  Iterating
    :meth:`~tarfile.TarFile.getmembers` forces full decompression and gzip CRC
    validation without writing anything to disk.

    Raises:
        FileNotFoundError: If any part file is missing.
        tarfile.TarError: If the gzip stream is corrupt or the tar structure is invalid.
    """
    for part in parts:
        part_path = parts_dir / part.file_name
        if not part_path.exists():
            raise FileNotFoundError(f"Archive part file not found: {part_path}")

    with _ChainReader(parts, parts_dir) as chain:
        with tarfile.open(fileobj=cast(BinaryIO, chain), mode="r|gz") as tar:
            member_count = 0
            for _ in tar:
                member_count += 1

    if member_count == 0:
        raise tarfile.TarError(
            "Tar stream contained no members — archive may be empty or corrupt"
        )


def build_chunked_tar_archive(
    source_dir: Path,
    output_dir: Path,
    base_name: str,
    part_size_bytes: int,
    manifest_file_name: str = "archive-manifest.json",
) -> ChunkedArchiveResult:
    """Create a gzip-compressed streamed tar split into sequential part files.

    The resulting part files are contiguous byte segments of one logical
    gzip-compressed tar stream.  Reassembly is done by concatenating parts
    in index order and then extracting the resulting ``.tar.gz``.
    """
    if not source_dir.exists() or not source_dir.is_dir():
        raise FileNotFoundError(
            f"source_dir does not exist or is not a directory: {source_dir}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    with _SplitPartWriter(
        output_dir=output_dir, base_name=base_name, part_size_bytes=part_size_bytes
    ) as writer:
        with tarfile.open(
            fileobj=cast(BinaryIO, writer),
            mode="w|gz",
        ) as tar_stream:
            tar_stream.add(str(source_dir), arcname=source_dir.name)

    manifest = {
        "archive_name": base_name,
        "archive_format": "tar.gz",
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
