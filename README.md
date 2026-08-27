# driveoff
Prototype for research drive offboarding and archiving, from IDS team.

## Archive workflow precondition: access freeze
Before an archive job is submitted for a drive, all researcher access to that drive must be removed (an operational step performed outside driveoff). This means the drive is a frozen snapshot for the duration of the archive job, which several design assumptions rely on: file contents cannot change mid-job, and checksums reflect the archived state.

## Folder structure
```
    src - Namespace for Python packages
    - api - web API server for offboarding status, drive and project information, triggering offboarding jobs and retrieval of archived data.
    - crate - RO-Crate generation and validation utilities.
    - models - Pydantic/SQLModel schemas for API requests/responses and database models.
    - service - external service clients (e.g. ProjectDB)
    tests - Pytest test cases for API endpoints and core logic.
    web - JavaScript web frontend.
    Project-Archive-RoCrate-Profile - ROCrate profile that this prototype will create.
```
## Modes
Both the FastAPI backend (`src/api`) and web frontend (`web`) read configuration dotenv files from the `modes` directory. There are currently two modes specified - `development` and `production`. More modes (e.g. for staging deployments) can be added.

There are two files for each mode - `.env.[mode]` and `.env.[mode].local`. The .local files are ignored in `.gitignore`, and are suitable for storing secrets such as API keys and passwords.

For both web frontend and FastAPI backend, an explicitly set environment variable will override values in dotenv files.

Web frontend: Vite has been configured to read from `modes` directory - see `web/vite.config.ts`. Read more at the [Vite env variables page](https://vite.dev/guide/env-and-mode.html#env-variables-and-modes).

FastAPI backend: See `src/config.py` and [pydantic-settings page](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).

Notifications:
- Archive submission and retrieval success/failure alerts can be enabled with `notifications_enabled=true`.
- Set `notifications_slack_webhook_url` to the incoming Slack webhook for the alerts channel.
- The alert channel is `drive-offboarding-alerts`.
- Alerts are best-effort only; notification failures are logged and do not affect the job result.
- In non-production modes, alerts are prefixed with the mode name so they are easy to distinguish.

File logging:
- Enable rotating file logs with `log_to_file_enabled=true`.
- Set `log_file_path` to a local or mounted-volume path (for example `/mnt/driveoff-logs/driveoff.log`).
- Rotation is configured with `log_file_rotation_when` and `log_file_rotation_interval` (defaults: `midnight`, `1`).
- Retention is controlled by `log_file_backup_count` (default: `14` rotated files).
- File logging setup is best-effort; if file handler setup fails, logging continues to stdout.

Archive packaging (virtual bagging):
- The archive tar contains a BagIt bag that is synthesized during streaming - the source drive is never modified. Payload files appear under `<drive>/data/`, the BagIt tag files (manifest, bagit.txt, bag-info.txt, tagmanifest) are generated in-stream, and the RO-Crate metadata is injected as `data/ro-crate-metadata.json`.
- Why not bag in place with `bagit.make_bag()`? That was the original design, but `make_bag` restructures the drive in place and is neither crash-safe nor idempotent: it moves all content into `data/` first, spends hours checksumming, and only then writes `bagit.txt` - so a crash mid-job leaves a state that a retry silently re-wraps into a garbled archive (stray temp dirs or a double-nested `data/data/`). It also requires write access to the drive and reads every byte twice (once to checksum, once to tar).
- The trade-off accepted for this: bag *creation* is now ~250 lines of our own code (`src/packaging/bag_stream.py`) replicating bagit's simple, well-specified output formats, which we must keep spec-compliant ourselves. This is mitigated by keeping the bagit library as the independent validation oracle - the test suite round-trips bags through it, and retrievals validate extracted bags with it - so any drift from the spec fails loudly rather than silently.
- Checksums are computed from the same read pass that feeds the tar (pure Python, platform-agnostic), so the manifest is guaranteed to match the archived bytes, and each drive is read only once.
- Because the source is only ever read, drives can be mounted read-only by the archiving host.
- The pre-upload verification pass streams the chunked parts and re-checks every payload file's hash against the in-tar manifest before anything is uploaded.
- Drives that were bagged in place by earlier prototype runs must be un-bagged (contents moved back out of `data/`, bag metadata files removed) before archiving; the job fails fast with a clear error if `bagit.txt` + `data/` are detected at the drive root.
- The `bagit` library remains the validation oracle: extracted archives are validated with it during retrieval, and the test suite validates round-tripped bags with it.

Retrieval destination allowlist:
- Archive retrievals may only extract into a path under the drive storage base - the same Vast Data storage that hosts the research drives. The allowed base is derived from the existing settings: `SMB_DRIVE_BASE_PATH` on Windows (or when it is a local path), and `SMB_LINUX_MOUNT_BASE_PATH` on Linux when the SMB base is a UNC path.
- If the relevant setting is not configured, retrieval requests are rejected (fail closed).
- Destination paths are fully resolved before the check, so `..` segments and symlinks cannot escape the allowed base.

Linux note for SMB archive jobs:
- If `SMB_DRIVE_BASE_PATH` is configured as a UNC path (for example `//server/share`), set `SMB_LINUX_MOUNT_BASE_PATH` to the local CIFS mount parent (for example `/mnt`).
- Drive paths are then resolved as `<SMB_LINUX_MOUNT_BASE_PATH>/<drive_name>` for bagit/RO-Crate filesystem operations.
- Archive output artifacts (tar + manifests) are written to local temp storage under `ARCHIVE_TEMP_BASE_PATH` (defaults to the OS temp directory).

## Local Python Tasks
This project uses `uv` for Python dependency management and `ruff` for formatting, import sorting, and linting.

Install dependencies first:

```bash
uv sync --group dev --group test
```

Run all CI-style checks locally:

```bash
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy --install-types --non-interactive
uv run pytest -v --cov=src/ tests/
```

Auto-fix formatting and import ordering:

```bash
uv run ruff format src tests
uv run ruff check --fix src tests
```
