"""Memory profiling helpers for DriveOff heavy-lifting paths."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import psutil
from memory_profiler import profile

# Ensure local src imports work when running from repository root.
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"

# config.get_env_file() expects `modes/` relative to cwd.
os.chdir(REPO_ROOT)

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from api.main import build_crate_contents_async
from api import manifests as api_manifests
from crate.ro_builder import ROBuilder
from crate.ro_loader import ROLoader, zip_existing_crate
from models.common import DataClassification
from models.submission import ArchiveSubmission


def _make_submission(project_id: int = 1234) -> ArchiveSubmission:
    return ArchiveSubmission(
        drive_id=1,
        project_id=project_id,
        drive_name="ressci202300019-testresearchdrive",
        retention_period_years=7,
        retention_period_justification="Standard retention",
        data_classification=DataClassification.SENSITIVE,
        archive_date=datetime(2026, 1, 15),
        archive_location="/tmp/archive/path",
        manifest_id=None,
        is_completed=False,
        created_timestamp=datetime(2026, 1, 15),
    )


def _make_project(project_id: int = 1234) -> dict[str, object]:
    return {
        "id": project_id,
        "title": "Memory Profile Project",
        "description": "Synthetic project for memory profiling",
        "division": "CTRERSH",
        "start_date": datetime(2022, 1, 1),
        "end_date": datetime(2024, 11, 4),
        "codes": {
            "items": [{"code": "CODE-001"}, {"code": "CODE-002"}, {"code": "CODE-003"}]
        },
    }


def _make_drive(name: str = "ressci202300019-testresearchdrive") -> dict[str, object]:
    return {
        "id": 1,
        "name": name,
        "allocated_gb": 4000.0,
        "free_gb": 1800.0,
        "used_gb": 2200.0,
        "date": "2026-03-09",
        "first_day": "2021-02-01",
        "percentage_used": 55.0,
    }


def _make_members(count: int) -> list[dict[str, object]]:
    members: list[dict[str, object]] = []
    roles = ["Principal Investigator", "Researcher", "Data Custodian", "Analyst"]
    for i in range(count):
        username = f"user{i:05d}"
        members.append(
            {
                "person": {
                    "username": username,
                    "full_name": f"User {i}",
                    "email": f"{username}@example.com",
                    "identities": {"items": [{"username": username}]},
                },
                "role": {"name": roles[i % len(roles)]},
            }
        )
    return members


@profile
def _run_add_project_profile(
    project_data: dict[str, object],
    members_list: list[dict[str, object]],
    submission: ArchiveSubmission,
    drive_data: dict[str, object],
) -> None:
    loader = ROLoader()
    loader.init_crate()
    builder = ROBuilder(loader.crate)
    builder.add_project(
        project=project_data,
        members=members_list,
        submission=submission,
        drive=drive_data,
    )


@profile
def _run_build_crate_profile(
    project_data: dict[str, object],
    members_list: list[dict[str, object]],
    submission: ArchiveSubmission,
    drive_data: dict[str, object],
) -> None:
    # BagIt multiprocessing can fail on Windows in synthetic temp dirs due to
    # relative path resolution inside worker processes.
    api_manifests.PROCESSES = 1

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        drive_location = root / "Vault"
        drive_location.mkdir(parents=True, exist_ok=True)

        output_location = root / "Archive"
        output_location.mkdir(parents=True, exist_ok=True)

        build_crate_contents_async(
            drive=drive_data,
            submission=submission,
            members_list=members_list,
            project_data=project_data,
            drive_location=drive_location,
            output_location=output_location,
        )


@profile
def _run_full_archive_profile(
    project_data: dict[str, object],
    members_list: list[dict[str, object]],
    submission: ArchiveSubmission,
    drive_data: dict[str, object],
) -> None:
    # Keep bagit single-process for consistent behavior in profiling runs.
    api_manifests.PROCESSES = 1

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        drive_location = root / "Vault"
        drive_location.mkdir(parents=True, exist_ok=True)

        output_location = root / "Archive"
        output_location.mkdir(parents=True, exist_ok=True)

        # 1) Build metadata + bag + manifests dir
        build_crate_contents_async(
            drive=drive_data,
            submission=submission,
            members_list=members_list,
            project_data=project_data,
            drive_location=drive_location,
            output_location=output_location,
        )

        # 2) Zip archive, 3) file-list manifest generation
        zip_existing_crate(output_location / str(submission.drive_name), drive_location)
        _ = api_manifests.generate_manifest(drive_location)


def _run_with_rss_delta(name: str, func, repeat: int = 1) -> None:
    if repeat == 1:
        process = psutil.Process()
        rss_before = process.memory_info().rss / (1024 * 1024)
        func()
        rss_after = process.memory_info().rss / (1024 * 1024)
        print(
            f"{name}: rss_before={rss_before:.2f} MiB "
            f"rss_after={rss_after:.2f} MiB delta={rss_after - rss_before:.2f} MiB"
        )
    else:
        process = psutil.Process()
        print(f"{name} ({repeat} repeats for leak detection):")
        deltas = []
        for run_idx in range(repeat):
            rss_before = process.memory_info().rss / (1024 * 1024)
            func()
            rss_after = process.memory_info().rss / (1024 * 1024)
            delta = rss_after - rss_before
            deltas.append(delta)
            print(
                f"  run {run_idx + 1}: rss_before={rss_before:.2f} MiB "
                f"rss_after={rss_after:.2f} MiB delta={delta:.2f} MiB"
            )
        avg_delta = sum(deltas) / len(deltas)
        max_delta = max(deltas)
        min_delta = min(deltas)
        print(
            f"  summary: min_delta={min_delta:.2f} MiB avg_delta={avg_delta:.2f} MiB "
            f"max_delta={max_delta:.2f} MiB (leak if growing)"
        )


def _configure_logging(quiet_logs: bool) -> None:
    if not quiet_logs:
        return
    logging.getLogger("api.main").setLevel(logging.WARNING)
    logging.getLogger("bagit").setLevel(logging.WARNING)
    logging.getLogger("crate.ro_loader").setLevel(logging.WARNING)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Profile memory usage of DriveOff hotspots"
    )
    parser.add_argument(
        "--scenario",
        choices=["add-project", "build-crate", "full-archive", "all"],
        default="all",
        help="Which profiling scenario to run",
    )
    parser.add_argument(
        "--members",
        type=int,
        default=500,
        help="Number of synthetic members to include in each scenario",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.05,
        help="Unused in RSS mode; kept for CLI compatibility",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of times to repeat each scenario (for leak detection)",
    )
    parser.add_argument(
        "--quiet-logs",
        action="store_true",
        help="Suppress verbose INFO logs from bagit and API modules",
    )
    args = parser.parse_args()

    _configure_logging(args.quiet_logs)

    print(
        "Running memory profiling "
        f"(scenario={args.scenario}, members={args.members}, repeat={args.repeat})"
    )

    if args.repeat == 1:
        # Single run: use prebuilt data
        project_data = _make_project()
        members_list = _make_members(args.members)
        submission = _make_submission()
        drive_data = _make_drive()

        if args.scenario in {"add-project", "all"}:
            _run_with_rss_delta(
                "ROBuilder.add_project",
                lambda: _run_add_project_profile(
                    project_data,
                    members_list,
                    submission,
                    drive_data,
                ),
                repeat=1,
            )

        if args.scenario in {"build-crate", "all"}:
            _run_with_rss_delta(
                "build_crate_contents_async",
                lambda: _run_build_crate_profile(
                    project_data,
                    members_list,
                    submission,
                    drive_data,
                ),
                repeat=1,
            )

        if args.scenario in {"full-archive", "all"}:
            _run_with_rss_delta(
                "full_archive_pipeline",
                lambda: _run_full_archive_profile(
                    project_data,
                    members_list,
                    submission,
                    drive_data,
                ),
                repeat=1,
            )
    else:
        # Multiple runs: rebuild data each iteration for realistic lifecycle
        def run_add_project_repeated() -> None:
            project_data = _make_project()
            members_list = _make_members(args.members)
            submission = _make_submission()
            drive_data = _make_drive()
            _run_add_project_profile(
                project_data,
                members_list,
                submission,
                drive_data,
            )

        def run_build_crate_repeated() -> None:
            project_data = _make_project()
            members_list = _make_members(args.members)
            submission = _make_submission()
            drive_data = _make_drive()
            _run_build_crate_profile(
                project_data,
                members_list,
                submission,
                drive_data,
            )

        def run_full_archive_repeated() -> None:
            project_data = _make_project()
            members_list = _make_members(args.members)
            submission = _make_submission()
            drive_data = _make_drive()
            _run_full_archive_profile(
                project_data,
                members_list,
                submission,
                drive_data,
            )

        if args.scenario in {"add-project", "all"}:
            _run_with_rss_delta(
                "ROBuilder.add_project",
                run_add_project_repeated,
                repeat=args.repeat,
            )

        if args.scenario in {"build-crate", "all"}:
            _run_with_rss_delta(
                "build_crate_contents_async",
                run_build_crate_repeated,
                repeat=args.repeat,
            )

        if args.scenario in {"full-archive", "all"}:
            _run_with_rss_delta(
                "full_archive_pipeline",
                run_full_archive_repeated,
                repeat=args.repeat,
            )


if __name__ == "__main__":
    main()
