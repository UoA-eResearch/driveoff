"""Scripts for generating file manifests
"""

import multiprocessing
import os
from pathlib import Path
from typing import Dict, Generator

import bagit

from models.manifest import Manifest

PROCESSES = max(multiprocessing.cpu_count() - 2, 1)
DEFAULT_CHECKSUM = "sha512"


def _sorted_walk(data_dir: str) -> Generator[str, None, None]:
    for dirpath, dirnames, filenames in os.walk(data_dir):
        filenames.sort()
        dirnames.sort()
        for fn in filenames:
            path = os.path.join(dirpath, fn)
            yield path


def _encode_filename(s: str) -> str:
    s = s.replace("\r", "%0D")
    s = s.replace("\n", "%0A")
    return s


def genertate_filelist(drive_path: Path) -> str:
    """Generate a list of all the files in a path separated by newlines.
    Sorts on filenames and dirnames to mirror bagit process.
    """
    if PROCESSES > 1:
        with multiprocessing.Pool(processes=PROCESSES) as pool:
            filenames = pool.map(_encode_filename, _sorted_walk(drive_path.as_posix()))
        # pool.close()
        # pool.join()
    else:
        filenames = [_encode_filename(i) for i in _sorted_walk(drive_path.as_posix())]
    return "\n".join(filenames)


def generate_manifest(drive_id: str) -> Manifest:
    """Generate a manifest from a drive ID.
    in future provide logic for a service account to mount a research drive.
    Currently generate a mockup from a test directory.
    """
    # mount drive based on ID
    # use service account to mount drive to mountpoint
    _ = f"//files.auckland.ac.nz/research/{drive_id}"
    mountpoint = Path("tests/restst000000001-testing")
    manifest = genertate_filelist(mountpoint)
    return Manifest(manifest=manifest)


def bag_directory(drive_path: Path, bag_info: Dict[str, str]) -> None:
    """Create a bagit bag from a given directory

    Args:
        drive_path (Path): the path to the directory to bag
        bag_info (Dict[str,str]): a dictionary documenting ownership of the bag
    """
    _ = bagit.make_bag(
        bag_dir=drive_path.as_posix(),
        bag_info=bag_info,
        processes=PROCESSES,
        checksums=DEFAULT_CHECKSUM,
    )
