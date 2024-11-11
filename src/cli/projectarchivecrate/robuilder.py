# pylint: disable-all
from pathlib import Path

from rocrate.rocrate import ROCrate


class ROBuilder:
    """Builder for Project Archive Crate RO-Cratess"""

    crate: ROCrate

    def __init__(self, crate: ROCrate) -> None:
        self.crate = crate

    def add_project(self) -> None:
        """stub for adding project"""
        pass

    def add_person(self) -> None:
        """stub for adding person"""
        pass

    def add_service(self) -> None:
        """stub for adding service"""
        pass
