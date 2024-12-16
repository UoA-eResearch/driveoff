"""Scripts for generating file manifests
"""

import multiprocessing
import os
import shutil
from pathlib import Path
from typing import Dict, Generator, Optional

import bagit

from models.manifest import Manifest

PROCESSES = max(multiprocessing.cpu_count() - 2, 1)
DEFAULT_CHECKSUM = ["sha256", "sha512"]


def _sorted_walk(data_dir: str, dirs_only: bool = False) -> Generator[str, None, None]:
    "Generate a sorted list of filenames or directory names"
    for dirpath, dirnames, filenames in os.walk(data_dir):
        relative_dirpath = Path(dirpath).relative_to(data_dir)
        dirnames.sort()
        if len(filenames) > 1000 or dirs_only:
            for dn in dirnames:
                path = os.path.join(relative_dirpath, dn)
                yield path
        else:
            filenames.sort()
            for fn in filenames:
                path = os.path.join(relative_dirpath, fn)
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


def generate_manifest(drive_path: Path) -> Manifest:
    """Generate a manifest from a drive ID.
    in future provide logic for a service account to mount a research drive.
    Currently generate a mockup from a test directory.
    """
    # mount drive based on ID
    # use service account to mount drive to mountpoint
    manifest = genertate_filelist(drive_path)
    return Manifest(manifest=manifest)


def bagit_exists(drive_path: Path) -> bool:
    """Return true if something looking like a bagIT is at this location"""
    return (drive_path / "bagit.txt").is_file() and (drive_path / "data").is_dir()


def bag_directory(drive_path: Path, bag_info: Dict[str, str]) -> None:
    """Create a bagit bag from a given directory

    Args:
        drive_path (Path): the path to the directory to bag
        bag_info (Dict[str,str]): a dictionary documenting ownership of the bag
    """
    # if a bagit already exists update it
    if bagit_exists(drive_path):
        bag = bagit.Bag(str(drive_path))
        bag.info = bag.info | bag_info
        bag.save(processes=PROCESSES, manifests=True)
        return

    _ = bagit.make_bag(
        bag_dir=drive_path.as_posix(),
        bag_info=bag_info,
        processes=PROCESSES,
        checksums=DEFAULT_CHECKSUM,
    )


def get_manifests_in_bag(drive_path: Path) -> list[Path]:
    """Return a list of all manifest type files in the RO-Crate.

    Args:
        drive_path (Path): root directory of the RO-Crate or BagIt directory

    Returns:
        List[Path]: a list of all bagit manifest or RO-crate metadata paths
    """
    result: list[Path] = []
    # avoid recursion as RO-Crates may contain a large volume of files
    result.extend(drive_path.glob("*manifest-*.txt"))
    result.extend(drive_path.glob("*bag-info.txt"))
    if len(result) > 0:  # if there is a bagit manifest check data dir
        result.extend((drive_path / "data").glob("*ro-crate-metadata.json"))
        return result
    # otherwise check for un-bagged RO-Crate
    result.extend(drive_path.glob("*ro-crate-metadata.json"))
    return result


def create_manifests_directory(
    drive_path: Path,
    output_location: Optional[Path] = None,
    drive_name: str = "",
) -> None:
    """Creates a directory containing relevant manifest files for an archived Crate.

    Args:
        output_location (Path): the path to where the manifests should be written,
            defaults to the drive_path
        drive_path (Path): the root path of the un-archived RO-Crate

    Raises:
        ValueError: if no manifests are found in the RO-Crate
    """
    if output_location is None:
        output_location = drive_path.parent
    manifests = get_manifests_in_bag(drive_path)
    if not manifests:
        raise ValueError(
            "No Manifests found in directory. Please confirm the dir is a BagIt and/or RO-Crate"
        )
    manifest_dir = output_location / (drive_name + drive_path.name + "_manifests")
    manifest_dir.mkdir(parents=True, exist_ok=True)
    for manifest in manifests:
        shutil.copy(str(manifest), str(manifest_dir / manifest.name))
