"""Scripts for generating file manifests"""

import multiprocessing
import shutil
from pathlib import Path

import bagit

PROCESSES = max(multiprocessing.cpu_count() - 2, 1)
DEFAULT_CHECKSUM = ["sha512"]


def bagit_exists(drive_path: Path) -> bool:
    """Return true if something looking like a bagIT is at this location"""
    return (drive_path / "bagit.txt").is_file() and (drive_path / "data").is_dir()


def bag_directory(drive_path: Path, bag_info: dict[str, str]) -> None:
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
    output_location: Path | None = None,
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
