"""Chunked archive packaging helpers for very large drive uploads."""

from __future__ import annotations

import hashlib
import json
import os
import tarfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, cast

#: Writes the archive's content into an open TarFile (e.g. the bag streamer).
TarContentWriter = Callable[[tarfile.TarFile], None]


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
        self._paths = [parts_dir / p.file_name for p in sorted(parts, key=lambda p: p.index)]
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
                self._current_fp = open(  # noqa: SIM115  # pylint: disable=consider-using-with
                    self._paths[self._file_index], "rb"
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

    Chains the ordered part files into a single logical byte stream and reads
    it with :func:`tarfile.open` in streaming mode (``r|gz``), forcing full
    decompression and gzip CRC validation without writing anything to disk.

    When the stream contains a BagIt bag (a ``<root>/manifest-sha256.txt``
    entry), every payload file under ``<root>/data/`` is additionally hashed
    during the same pass and checked against the manifest, in both
    directions - end-to-end integrity confirmation before upload. Archives
    without a bag manifest are only structurally verified, as before.

    Raises:
        FileNotFoundError: If any part file is missing.
        tarfile.TarError: If the gzip stream is corrupt, the tar structure is
            invalid, or the bag payload does not match its manifest.
    """
    for part in parts:
        part_path = parts_dir / part.file_name
        if not part_path.exists():
            raise FileNotFoundError(f"Archive part file not found: {part_path}")

    computed_payload_hashes: dict[str, str] = {}
    bag_manifest_bytes: bytes | None = None

    with _ChainReader(parts, parts_dir) as chain:
        with tarfile.open(fileobj=cast(BinaryIO, chain), mode="r|gz") as tar:
            member_count = 0
            for member in tar:
                member_count += 1
                if not member.isreg():
                    continue
                name_parts = member.name.split("/")
                if len(name_parts) == 2 and name_parts[1] == "manifest-sha256.txt":
                    manifest_file = tar.extractfile(member)
                    if manifest_file is not None:
                        bag_manifest_bytes = manifest_file.read()
                elif len(name_parts) >= 3 and name_parts[1] == "data":
                    payload_file = tar.extractfile(member)
                    if payload_file is not None:
                        hasher = hashlib.sha256()
                        while chunk := payload_file.read(1024 * 1024):
                            hasher.update(chunk)
                        computed_payload_hashes["/".join(name_parts[1:])] = hasher.hexdigest()

    if member_count == 0:
        raise tarfile.TarError("Tar stream contained no members — archive may be empty or corrupt")

    if bag_manifest_bytes is not None:
        _verify_bag_payload_hashes(bag_manifest_bytes, computed_payload_hashes)


def _verify_bag_payload_hashes(manifest_bytes: bytes, computed: dict[str, str]) -> None:
    """Check streamed payload hashes against a BagIt manifest, both ways."""
    # Imported here to avoid a circular import at module load.
    from packaging.bag_stream import encode_manifest_path  # pylint: disable=import-outside-toplevel

    manifest: dict[str, str] = {}
    for line in manifest_bytes.decode("utf-8").splitlines():
        if not line.strip():
            continue
        digest, _, rel_path = line.partition("  ")
        manifest[rel_path] = digest

    encoded_computed = {encode_manifest_path(path): digest for path, digest in computed.items()}

    for rel_path, expected_digest in manifest.items():
        actual_digest = encoded_computed.get(rel_path)
        if actual_digest is None:
            raise tarfile.TarError(f"Bag manifest lists a payload file missing from the archive: {rel_path}")
        if actual_digest != expected_digest:
            raise tarfile.TarError(f"Bag payload checksum mismatch for {rel_path}")

    unlisted = set(encoded_computed) - set(manifest)
    if unlisted:
        raise tarfile.TarError(f"Archive contains payload files not listed in the bag manifest: {sorted(unlisted)[:5]}")


def build_chunked_tar_archive(
    source_dir: Path,
    output_dir: Path,
    base_name: str,
    part_size_bytes: int,
    manifest_file_name: str = "archive-manifest.json",
    content_writer: TarContentWriter | None = None,
) -> ChunkedArchiveResult:
    """Create a gzip-compressed streamed tar split into sequential part files.

    The resulting part files are contiguous byte segments of one logical
    gzip-compressed tar stream.  Reassembly is done by concatenating parts
    in index order and then extracting the resulting ``.tar.gz``.

    By default the whole *source_dir* is added as-is. Pass *content_writer*
    to take over writing the tar's content instead (e.g. the bag streamer,
    which synthesizes a BagIt layout without modifying the source).
    """
    if not source_dir.exists() or not source_dir.is_dir():
        raise FileNotFoundError(f"source_dir does not exist or is not a directory: {source_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    with _SplitPartWriter(output_dir=output_dir, base_name=base_name, part_size_bytes=part_size_bytes) as writer:
        with tarfile.open(
            fileobj=cast(BinaryIO, writer),
            mode="w|gz",
        ) as tar_stream:
            if content_writer is not None:
                content_writer(tar_stream)
            else:
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
