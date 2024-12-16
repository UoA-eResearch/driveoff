""""
Functions for faking a mounted research drive on the local home directory

Only for demonstration purposes, 
please replace once service accounts can mount a research drive
"""

import shutil
from pathlib import Path

TEST_DATA_NAME = Path("tests/restst000000001-testing")


def make_fake_resdrive(drive_path: Path) -> None:
    "TESTING/DEMONSTRATION FUNCTION TO POPULATE RESEARCH DRIVE PATHS"
    (drive_path / "Archive").mkdir(parents=True, exist_ok=True)
    data_path = drive_path / "Vault"
    if not data_path.exists():
        data_path.mkdir(parents=True, exist_ok=False)
        populate_fake_resdrive(data_path)


def populate_fake_resdrive(input_path: Path) -> None:
    "Populate the vault directory with fake data"
    shutil.copytree(TEST_DATA_NAME, input_path, dirs_exist_ok=True)
