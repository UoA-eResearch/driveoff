"Test creation and writing of RO-Crates"
from pathlib import Path

import bagit
from conftest import ROCRATEHelpers
from factory.alchemy import SQLAlchemyModelFactory
from sqlmodel import Session

from api.main import generate_ro_crate
from crate.ro_builder import ROBuilder

METADATA_FILE_NAME = "ro-crate-metadata.json"
BAG_DIR_NAME = "data"


def test_generate_crate(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    data_dir: Path,
    archive_dir: Path,
    session: Session,
    research_drive_service_factory: SQLAlchemyModelFactory,
    project_factory: SQLAlchemyModelFactory,
    drive_offboard_submission_factory: SQLAlchemyModelFactory,
    ro_crate_helpers: ROCRATEHelpers,
    test_ro_builder: ROBuilder,
) -> None:
    "Test generation of an RO-Crate in a bagit package"
    drive_name = "test_drive"
    target_drive = research_drive_service_factory.create(name=drive_name)
    project = project_factory.create(research_drives=[target_drive])
    drive_offboard_submission_factory.create(drive=target_drive)

    generate_ro_crate(
        drive_id=drive_name,
        session=session,
        drive_location=data_dir,
        output_location=archive_dir,
    )

    # check bagit created correctly
    assert Path(data_dir / BAG_DIR_NAME).is_dir()
    assert list(Path(data_dir).glob("*manifest-*.txt"))
    assert list(Path(data_dir).glob("*bag-info.txt"))
    bag = bagit.Bag(data_dir.as_posix())
    assert bag.validate()

    # check and validate RO-Crate
    assert Path(data_dir / BAG_DIR_NAME / METADATA_FILE_NAME).is_file()
    entities = ro_crate_helpers.read_json_entities(Path(data_dir / BAG_DIR_NAME))
    ro_crate_helpers.check_crate(entities)

    # create entities to check they have been created within RO-Crate json correctly
    ro_project = test_ro_builder.add_project(project)
    ro_drive = test_ro_builder.add_research_drive_service(target_drive)
    ro_drive.append_to("project", ro_project)
    entities_created = [ro_project]
    entities_created.append(ro_drive)
    entities_created.extend(ro_project.get("member"))
    entities_created.extend(ro_project.get("services"))
    ro_crate_helpers.check_crate_contains(entities, entities_created)