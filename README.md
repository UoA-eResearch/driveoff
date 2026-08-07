# driveoff
Prototype for research drive offboarding and archiving, from IDS team.

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
