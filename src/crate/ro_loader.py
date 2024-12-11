"""Classes and functions for loading and archiving RO-Crates
"""

import tarfile
from enum import Enum
from pathlib import Path
from typing import Any, Dict

import orjson
from rocrate.rocrate import ROCrate

JsonType = Dict[str, Any]


class ARCHIVETYPE(str, Enum):
    "Enum for Archive types it is possible to write the RO-Crate as"
    ZIP = "zip"
    TAR = "tar"
    TAR_GZ = "tar.gz"


PROFILE = "https://uoa-eresearch.github.io/Project-Archive-RoCrate-Profile/"


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

    def deserialize_crate(self, input_json: JsonType) -> None:
        """Read an RO-Crate from a json dictionary input

        Args:
            input_json (Path): the path to write the RO-Crate file to
        """
        if not isinstance(input_json, dict):
            raise ValueError("cannot deseralize RO-Crate json file must be a dict")
        self.crate = ROCrate(source=input_json)

    def serialize_crate(self) -> JsonType:
        """Write the ro crate metadata to a json string and return it"""
        as_jsonld: JsonType = self.crate.metadata.generate()
        print("serialized crate is", as_jsonld)
        return as_jsonld

    def archive_crate(
        self, crate_destination: Path, archive_type: ARCHIVETYPE, crate_location: Path
    ) -> None:
        """Write the RO-Crate as a Zip, TAR or TarGZ output

        Args:
            crate_destination (Path): where the crate should be written to
            archive_type (ARCHIVE_TYPE): the format of the archive TAR, TAR_GZ or ZIP
            crate_location (Path): _description_
        """
        self.crate.source = crate_location
        file_location = crate_destination.parent / (
            f"{crate_destination.name}.{archive_type}"
        )
        match archive_type:
            case ARCHIVETYPE.TAR_GZ:
                with tarfile.open(
                    file_location,
                    mode="w:gz",
                ) as out_tar:
                    out_tar.add(
                        crate_location,
                        arcname=crate_location.name,
                        recursive=True,
                    )
                out_tar.close()
            case ARCHIVETYPE.TAR:
                with tarfile.open(file_location, mode="w") as out_tar:
                    out_tar.add(
                        crate_location,
                        arcname=crate_location.name,
                        recursive=True,
                    )
                out_tar.close()
            case ARCHIVETYPE.ZIP:
                self.crate.write_zip(file_location)
