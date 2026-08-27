# driveoff

Prototype for research drive offboarding and archiving, from the IDS team.

driveoff archives research drives to long-term object storage and retrieves them again on request. A FastAPI backend accepts archive submissions, packages the drive as a chunked `.tar.gz` containing a [BagIt](https://datatracker.ietf.org/doc/html/rfc8493) bag with [RO-Crate](https://www.researchobject.org/ro-crate/) metadata, and uploads it to ActiveScale (S3-compatible, tape-backed). Retrieval restores the archive from tape and extracts it back onto Vast Data storage.

Status: prototype - not yet in production. The target production architecture (split workers, queue-based dispatch, job records in ProjectDB) is described in [TODO.md](TODO.md) under Infrastructure and Deployment.

## Repository layout

```
src/       Python packages: api (FastAPI server), models, packaging, service, utils, workers
tests/     Pytest suite for API endpoints and core logic
scripts/   Operational scripts (connectivity check, incomplete-upload cleanup)
modes/     Per-mode dotenv configuration files (see Configuration)
docs/      Design documents (e.g. the virtual bagging proposal)
web/       JavaScript web frontend (not currently used)
Project-Archive-RoCrate-Profile/   RO-Crate profile that the generated crates conform to
```

See [src/api/README.md](src/api/README.md) for running the API server, API key setup, the endpoint summary, and a detailed description of the archive submission and retrieval workflows.

## Archive workflow preconditions

### Access freeze
Before an archive job is submitted for a drive, all researcher access to that drive must be removed (an operational step performed outside driveoff). This means the drive is a frozen snapshot for the duration of the archive job, which several design assumptions rely on: file contents cannot change mid-job, and checksums reflect the archived state.

### ActiveScale bucket configuration
The archive job uploads the tar to an ActiveScale bucket. The bucket must be pre-created (by ASI - contact Allan Ha) with:

- **Object lock enabled at bucket creation.** Uploaded objects are protected with COMPLIANCE-mode retention (`activescale_enable_object_retention`, on by default), which requires the bucket to have been created with object lock; it cannot be enabled later, and jobs fail at the retention step without it.
- **The lifecycle policy** in [lifecycle-policy.json](lifecycle-policy.json) applied. It transitions uploaded archives into the deep archive (tape) tier; without it they remain in the standard storage tier.

The bucket name is configured with `ACTIVESCALE_BUCKET_NAME` (defaults to `research-archive-test` in [config.py](src/config.py)).

Note: ActiveScale does not support the `AbortIncompleteMultipartUpload` lifecycle rule, so incomplete multipart uploads left behind by crashed jobs accumulate invisibly (they hold billable storage but do not appear in object listings). Run [scripts/cleanup_incomplete_uploads.sh](scripts/cleanup_incomplete_uploads.sh) occasionally to list and abort them - it is a dry run unless invoked with `APPLY=1`.

## Configuration

The FastAPI backend (and the web frontend, when used) read dotenv files from the `modes` directory, selected by the `MODE` environment variable (default: `development`). There are two files per mode - `.env.[mode]` and `.env.[mode].local`. The `.local` files are gitignored and hold secrets such as API keys. An explicitly set environment variable overrides values from the dotenv files.

All backend settings and their defaults are defined in [src/config.py](src/config.py) via [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/); the frontend uses [Vite env modes](https://vite.dev/guide/env-and-mode.html#env-variables-and-modes) (see `web/vite.config.ts`). The groups you are most likely to touch:

### Storage paths
- `SMB_DRIVE_BASE_PATH` - base path of the research drive storage. On Linux, if this is a UNC path (for example `//server/share`), also set `SMB_LINUX_MOUNT_BASE_PATH` to the local CIFS mount parent (for example `/mnt`); drive paths then resolve as `<SMB_LINUX_MOUNT_BASE_PATH>/<drive_name>`.
- `ARCHIVE_TEMP_BASE_PATH` - local scratch for generated artifacts (tar parts, RO-Crate metadata, retrieval downloads). Defaults to the OS temp directory.
- `ARCHIVE_CHUNK_SIZE_BYTES` - maximum size of each archive part file.

### ActiveScale connection
- `ACTIVESCALE_HOSTNAME`, `ACTIVESCALE_REGION`, `ACTIVESCALE_ACCESS_KEY`, `ACTIVESCALE_SECRET_KEY` (secrets belong in the `.local` file).
- `ACTIVESCALE_READ_TIMEOUT` (default 60s) is the hang defence for uploads and downloads: it is a socket-level timeout applied to every blocking operation, so a dead connection fails within roughly `read_timeout x retry_attempts`. There is deliberately no wall-clock upload timeout - slow but progressing transfers are allowed to continue, and stalls are logged.
- Restore/retrieval polling: `ACTIVESCALE_RESTORE_DAYS`, `ACTIVESCALE_RESTORE_POLL_INTERVAL_SECONDS`, `ACTIVESCALE_RESTORE_POLL_MAX_SECONDS`.
- Retention: `ACTIVESCALE_ENABLE_OBJECT_RETENTION`, `ACTIVESCALE_DEFAULT_RETENTION_YEARS`, and `ACTIVESCALE_RETENTION_OVERRIDE_DAYS` for TEST environments where objects should expire quickly.

### Notifications
- Archive submission and retrieval success/failure alerts can be enabled with `NOTIFICATIONS_ENABLED=true`.
- Set `NOTIFICATIONS_SLACK_WEBHOOK_URL` to the incoming Slack webhook for the alerts channel (`drive-offboarding-alerts`).
- Alerts are best-effort only; notification failures are logged and do not affect the job result. In non-production modes, alerts are prefixed with the mode name.

### File logging
- Enable rotating file logs with `LOG_TO_FILE_ENABLED=true` and set `LOG_FILE_PATH` to a local or mounted-volume path (for example `/mnt/driveoff-logs/driveoff.log`).
- Rotation: `LOG_FILE_ROTATION_WHEN` / `LOG_FILE_ROTATION_INTERVAL` (defaults: `midnight`, `1`). Retention: `LOG_FILE_BACKUP_COUNT` (default 14 rotated files).
- File logging setup is best-effort; if the file handler fails, logging continues to stdout.

## Operational notes

### Archive packaging (virtual bagging)
The archive tar contains a BagIt bag that is synthesized during streaming ([src/packaging/bag_stream.py](src/packaging/bag_stream.py)) - the source drive is never modified. Payload files appear under `<drive>/data/`, the BagIt tag files (manifest, bagit.txt, bag-info.txt, tagmanifest) are generated in-stream with checksums computed from the same read pass that feeds the tar, and the RO-Crate metadata is injected as `data/ro-crate-metadata.json`. A pre-upload verification pass re-checks every payload file's hash against the in-tar manifest.

This replaced the original bag-in-place design (`bagit.make_bag` on the drive itself), which was not crash-safe and required write access to the drive; the trade-off is that bag creation is now our own code to keep spec-compliant, mitigated by using the bagit library as the independent validation oracle in tests and at retrieval. Full rationale: [docs/virtual-bagging.html](docs/virtual-bagging.html).

Note: drives that were bagged in place by earlier prototype runs must be un-bagged (contents moved back out of `data/`, bag metadata files removed) before archiving; the job fails fast with a clear error if `bagit.txt` + `data/` are detected at the drive root.

### Retrieval destination allowlist
- Archive retrievals may only extract into a path under the drive storage base - the same Vast Data storage that hosts the research drives. The allowed base is derived from the storage path settings: `SMB_DRIVE_BASE_PATH` on Windows (or when it is a local path), and `SMB_LINUX_MOUNT_BASE_PATH` on Linux when the SMB base is a UNC path.
- If the relevant setting is not configured, retrieval requests are rejected (fail closed).
- Destination paths are fully resolved before the check, so `..` segments and symlinks cannot escape the allowed base.

### Scripts
- [scripts/check_activescale.sh](scripts/check_activescale.sh) - verifies ActiveScale connectivity and bucket access for the current mode. Bypasses the corporate proxy for the ActiveScale host.
- [scripts/cleanup_incomplete_uploads.sh](scripts/cleanup_incomplete_uploads.sh) - lists (and with `APPLY=1`, aborts) stale incomplete multipart uploads; see ActiveScale bucket configuration above.

## Local Python tasks
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
