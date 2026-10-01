"""Stream a BagIt bag structure into a tar archive without modifying the source.

"Virtual bagging": instead of restructuring the source drive in place with
``bagit.make_bag`` (which is neither crash-safe nor idempotent), the bag is
synthesized inside the tar stream. Payload files are written under
``<root>/data/`` and hashed as their bytes stream through, and the BagIt tag
files (manifest, bagit.txt, bag-info.txt, tagmanifest) are generated in
memory and appended as tar entries. The source directory is only ever read.

Extracting the resulting tar yields a bag that validates with the ``bagit``
library, which remains the validation oracle in tests and at retrieval time.

Everything here is standard library (``tarfile``, ``hashlib``, ``os``) and
platform-agnostic; hashing rides the same read pass that feeds the tar.
"""

from __future__ import annotations

import hashlib
import io
import logging
import os
import stat as stat_module
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, cast

from utils import utc_now
from utils.logging import log_event

#: Written byte-for-byte as bagit.py writes it, so validators treat the bag
#: identically to a library-created one.
BAGIT_TXT = "BagIt-Version: 0.97\nTag-File-Character-Encoding: UTF-8\n"

BAG_SOFTWARE_AGENT = "driveoff bag_stream <https://github.com/UoA-eResearch/driveoff>"

CHECKSUM_ALGORITHM = "sha256"


@dataclass
class BagStreamResult:
    """Summary of a bag written into a tar stream."""

    payload_file_count: int
    payload_byte_count: int

    @property
    def payload_oxum(self) -> str:
        """Payload-Oxum value as defined by the BagIt spec: octets.count."""
        return f"{self.payload_byte_count}.{self.payload_file_count}"


class _HashingReader:
    """File-like reader that updates a hash with every chunk it hands out.

    tarfile pulls the file's bytes through ``read()``, so the digest is
    computed from exactly the bytes that enter the archive - one read pass,
    no separate checksum pass, and no platform-specific tooling.
    """

    def __init__(self, fp: BinaryIO, hasher: hashlib._Hash) -> None:
        self._fp = fp
        self._hasher = hasher

    def read(self, size: int = -1) -> bytes:
        chunk = self._fp.read(size)
        if chunk:
            self._hasher.update(chunk)
        return chunk


def encode_manifest_path(name: str) -> str:
    """Encode CR/LF in manifest paths exactly as bagit.py does."""
    return name.replace("\r", "%0D").replace("\n", "%0A")


def _add_bytes_entry(tar: tarfile.TarFile, arcname: str, payload: bytes, mtime: int) -> None:
    """Add an in-memory file to the tar."""
    info = tarfile.TarInfo(arcname)
    info.size = len(payload)
    info.mtime = mtime
    info.mode = 0o644
    tar.addfile(info, io.BytesIO(payload))


def _add_dir_entry(tar: tarfile.TarFile, arcname: str, mtime: int, mode: int = 0o755) -> None:
    """Add a directory entry to the tar."""
    info = tarfile.TarInfo(arcname + "/")
    info.type = tarfile.DIRTYPE
    info.mtime = mtime
    info.mode = mode
    tar.addfile(info)


def _add_payload_file(
    tar: tarfile.TarFile,
    file_path: Path,
    arcname: str,
) -> tuple[str, int]:
    """Stream one file into the tar, hashing it in the same pass.

    Returns (sha256 hex digest, size in bytes). Follows file symlinks and
    stores them as regular files so the extracted bag is self-contained.
    """
    st = os.stat(file_path)
    info = tarfile.TarInfo(arcname)
    info.size = st.st_size
    info.mtime = int(st.st_mtime)
    info.mode = st.st_mode & 0o7777

    hasher = hashlib.sha256()
    with open(file_path, "rb") as fp:
        tar.addfile(info, cast(BinaryIO, _HashingReader(fp, hasher)))
    return hasher.hexdigest(), st.st_size


def source_is_already_bagged(source_dir: Path) -> bool:
    """Return True when the source looks like an on-disk BagIt bag."""
    return (source_dir / "bagit.txt").is_file() and (source_dir / "data").is_dir()


def write_bagged_tree(  # pylint: disable=too-many-locals
    tar: tarfile.TarFile,
    source_dir: Path,
    arcname_root: str,
    bag_info: dict[str, str] | None = None,
    extra_payload_files: list[tuple[Path, str]] | None = None,
) -> BagStreamResult:
    """Write *source_dir* into *tar* as a BagIt bag rooted at *arcname_root*.

    Args:
        tar: An open TarFile in write mode (streaming ``w|gz`` works).
        source_dir: Directory to archive. Never modified.
        arcname_root: Top-level directory name inside the tar; payload files
            appear as ``<arcname_root>/data/<relative path>``.
        bag_info: Extra key/value metadata for bag-info.txt. Bagging-Date,
            Bag-Software-Agent, and Payload-Oxum are added automatically.
        extra_payload_files: Generated files to inject into the payload, as
            (local path, path relative to ``data/``) pairs - for example the
            RO-Crate metadata JSON. Their hashes and sizes are included in
            the manifest and Payload-Oxum like any other payload file.

    Raises:
        ValueError: if *source_dir* is already an on-disk bag (archiving it
            would double-nest the payload; un-bag it first).
        FileNotFoundError: if *source_dir* does not exist.
    """
    if not source_dir.is_dir():
        raise FileNotFoundError(f"source_dir does not exist or is not a directory: {source_dir}")
    if source_is_already_bagged(source_dir):
        raise ValueError(
            f"Source directory {source_dir} is already an on-disk BagIt bag (bagit.txt + data/)."
            " Archiving it would double-nest the payload; un-bag the directory before archiving."
        )

    now = utc_now()
    tag_mtime = int(now.timestamp())
    data_root = f"{arcname_root}/data"

    #: (sha256, path relative to bag root using forward slashes) per payload file
    manifest_entries: list[tuple[str, str]] = []
    total_bytes = 0
    total_files = 0

    _add_dir_entry(tar, arcname_root, tag_mtime)
    _add_dir_entry(tar, data_root, tag_mtime)

    for dirpath_str, dirnames, filenames in os.walk(source_dir):
        dirnames.sort()
        filenames.sort()
        dirpath = Path(dirpath_str)

        # Do not descend into symlinked directories: following them could
        # loop, and silently archiving half a link target is worse than a
        # visible skip.
        skipped_dirs = [d for d in dirnames if (dirpath / d).is_symlink()]
        for skipped in skipped_dirs:
            dirnames.remove(skipped)
            log_event(
                logging.WARNING,
                "bag_stream.symlinked_dir_skipped",
                path=str(dirpath / skipped),
            )

        rel_dir = dirpath.relative_to(source_dir).as_posix()
        if rel_dir != ".":
            _add_dir_entry(tar, f"{data_root}/{rel_dir}", int(dirpath.stat().st_mtime))

        for file_name in filenames:
            file_path = dirpath / file_name
            st = os.stat(file_path)
            if not stat_module.S_ISREG(st.st_mode):
                log_event(
                    logging.WARNING,
                    "bag_stream.special_file_skipped",
                    path=str(file_path),
                )
                continue
            rel_file = file_path.relative_to(source_dir).as_posix()
            digest, size = _add_payload_file(tar, file_path, f"{data_root}/{rel_file}")
            manifest_entries.append((digest, f"data/{rel_file}"))
            total_bytes += size
            total_files += 1

    for local_path, rel_arcname in extra_payload_files or []:
        digest, size = _add_payload_file(tar, local_path, f"{data_root}/{rel_arcname}")
        manifest_entries.append((digest, f"data/{rel_arcname}"))
        total_bytes += size
        total_files += 1

    result = BagStreamResult(payload_file_count=total_files, payload_byte_count=total_bytes)

    # Tag files. Two-space separator and CR/LF encoding mirror bagit.py so
    # the extracted bag is indistinguishable from a library-created one.
    manifest_bytes = "".join(
        f"{digest}  {encode_manifest_path(rel_path)}\n"
        for digest, rel_path in sorted(manifest_entries, key=lambda e: e[1])
    ).encode("utf-8")

    full_bag_info: dict[str, str] = dict(bag_info or {})
    full_bag_info.setdefault("Bagging-Date", now.strftime("%Y-%m-%d"))
    full_bag_info.setdefault("Bag-Software-Agent", BAG_SOFTWARE_AGENT)
    full_bag_info["Payload-Oxum"] = result.payload_oxum
    bag_info_bytes = "".join(f"{key}: {full_bag_info[key]}\n" for key in sorted(full_bag_info)).encode("utf-8")

    bagit_bytes = BAGIT_TXT.encode("utf-8")

    tag_files = [
        (f"manifest-{CHECKSUM_ALGORITHM}.txt", manifest_bytes),
        ("bagit.txt", bagit_bytes),
        ("bag-info.txt", bag_info_bytes),
    ]
    for tag_name, tag_bytes in tag_files:
        _add_bytes_entry(tar, f"{arcname_root}/{tag_name}", tag_bytes, tag_mtime)

    tagmanifest_bytes = "".join(
        f"{hashlib.sha256(tag_bytes).hexdigest()} {tag_name}\n" for tag_name, tag_bytes in sorted(tag_files)
    ).encode("utf-8")
    _add_bytes_entry(tar, f"{arcname_root}/tagmanifest-{CHECKSUM_ALGORITHM}.txt", tagmanifest_bytes, tag_mtime)

    log_event(
        logging.INFO,
        "bag_stream.completed",
        source_dir=str(source_dir),
        arcname_root=arcname_root,
        payload_file_count=result.payload_file_count,
        payload_byte_count=result.payload_byte_count,
    )
    return result
