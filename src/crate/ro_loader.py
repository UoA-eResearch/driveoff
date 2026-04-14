"""Classes and functions for loading and archiving RO-Crates"""

import json
import logging
import shutil
from pathlib import Path
from typing import Any

import orjson
from bagit import Bag
from rocrate.rocrate import ROCrate

JsonType = dict[str, Any]


PROFILE = "https://uoa-eresearch.github.io/Project-Archive-RoCrate-Profile/"

logger = logging.getLogger(__name__)


def _log_event(level: int, event: str, **context: Any) -> None:
    payload = {"event": event, **context}
    logger.log(level, json.dumps(payload, default=str))


class ROLoader:
    """class for reading and writing crates"""

    crate: ROCrate

    def __init__(self, crate_path: Path | JsonType | None = None) -> None:
        if crate_path is not None:
            self.crate = self.read_crate(crate_path)

    def read_crate(self, read_path: Path | JsonType) -> ROCrate:
        """Load a crate from a source on disk.
            Then set this source to none.
        Args:
            read_path (Path): the location of the crate to read

        Returns:
            ROCrate: an ROCrate from that source
        """
        self.crate = ROCrate(source=read_path, init=False)
        self.crate.source = None
        if PROFILE not in self.crate.metadata.get_norm_value("conformsTo"):
            self.crate.metadata.append_to("conformsTo", {"@id": PROFILE})
        return self.crate

    def init_crate(self) -> ROCrate:
        """Initiate an RO-Crate,
        with source as None as we are not moving files.

        Returns:
            ROCrate: The RO-Crate to be constructed
        """
        self.crate = ROCrate(source=None, init=False)
        self.crate.metadata.append_to("conformsTo", {"@id": PROFILE})
        return self.crate

    def write_crate(self, crate_destination: Path) -> None:
        """Write the ro_crate_metadata.json to the given destination

        Args:
            crate_destination (Path): the path to write the RO-Crate file to
        """
        if not crate_destination.exists():
            crate_destination.mkdir(parents=True, exist_ok=True)

        crate_metadata_entity = self.crate.metadata
        write_path = crate_destination / crate_metadata_entity.id
        as_jsonld = crate_metadata_entity.generate()
        with open(write_path, "w", encoding="utf-8") as outfile:
            outfile.write(  # pylint does not recognize orjson members....
                orjson.dumps(  # pylint: disable=no-member
                    as_jsonld,
                    option=orjson.OPT_SORT_KEYS  # pylint: disable=no-member
                    | orjson.OPT_INDENT_2,  # pylint: disable=no-member
                ).decode("utf-8")
            )


def zip_existing_crate(crate_destination: Path, crate_location: Path) -> None:
    """Move an existing RO-Crate into a Zip Archive"""
    if crate_destination.suffix == ".zip":
        crate_destination = crate_destination.parent / crate_destination.stem
    if not crate_location.is_dir():
        raise FileExistsError("RO-Crate Source should be a directory")
    bag = Bag(str(crate_location))
    if not bag.validate():
        raise ValueError("RO-Crate Source should be a valid BagIt")
    if not Path(crate_location / "data" / "ro-crate-metadata.json").is_file():
        raise FileExistsError("No RO-Crate metadata found in RO-Crate source")
    _log_event(
        logging.INFO,
        "crate.zip.start",
        source=str(crate_location),
        destination=str(crate_destination),
    )
    shutil.make_archive(str(crate_destination), "zip", str(crate_location))
