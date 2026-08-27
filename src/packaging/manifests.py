"""BagIt bag validation helpers.

Bag *creation* lives in packaging.bag_stream ("virtual bagging"): the bag
structure is synthesized inside the archive tar and the source drive is never
modified. This module keeps the bagit-library-backed validation used by the
retrieval workflow, so extracted archives are checked by the same independent
implementation that defined the format.
"""

import multiprocessing
import os
from pathlib import Path

import bagit

# bagit uses multiprocessing.Pool for checksum validation when processes > 1.
# On Linux, exceptions raised during validation can leave semaphore resources
# behind at shutdown, so we keep it single-process there for deterministic
# cleanup.
PROCESSES = 1 if os.name != "nt" else max(multiprocessing.cpu_count() - 2, 1)


def bagit_exists(drive_path: Path) -> bool:
    """Return true if something looking like a bagIT is at this location"""
    return (drive_path / "bagit.txt").is_file() and (drive_path / "data").is_dir()


def validate_bag(bag_path: Path) -> None:
    """Validate a BagIt bag at the given path.

    Raises:
        bagit.BagValidationError: if the bag does not pass validation.
        bagit.BagError: if the path does not look like a valid bag at all.
    """
    bag = bagit.Bag(str(bag_path))
    bag.validate(processes=PROCESSES)
