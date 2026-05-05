# driveoff
Prototype for research drive offboarding and archiving, from IDS team.

## Folder structure
```
    src - Namespace for Python packages
    - api - web API server for offboarding status and project infomration.
    - cli - interactive scripts to initiate offboarding
    web - JavaScript web frontend.
    Project-Archive-RoCrate-Profile - ROCrate profile that this prototype will create.
```
## Modes
Both the FastAPI backend (`src/api`) and web frontend (`web`) read configuration dotenv files from the `modes` directory. There are currently two modes specified - `development` and `production`. More modes (e.g. for staging deployments) can be added.

There are two files for each mode - `.env.[mode]` and `.env.[mode].local`. The .local files are ignored in `.gitignore`, and are suitable for storing secrets such as API keys and passwords.

For both web frontend and FastAPI backend, an explicitly set environment variable will override values in dotenv files.

Web frontend: Vite has been configured to read from `modes` directory - see `web/vite.config.ts`. Read more at the [Vite env variables page](https://vite.dev/guide/env-and-mode.html#env-variables-and-modes).

FastAPI backend: See `src/config.py` and [pydantic-settings page](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).

## Local Python Tasks
This project defines local developer tasks in `pyproject.toml` using `poethepoet`.

Install dependencies first:

```bash
poetry install
```

Run all CI-style checks locally:

```bash
poetry run poe check
```

Run auto-fix formatting tasks:

```bash
poetry run poe fix
```

Run an individual task:

```bash
poetry run poe isort-check
poetry run poe black-check
poetry run poe isort-fix
poetry run poe black-fix
poetry run poe pylint-check
poetry run poe mypy-check
poetry run poe pytest-check
```

## ActiveScale CLI
Use the repo-local CLI launcher to run simple inspection commands against ActiveScale:

```bash
poetry run python scripts/activescale_cli.py list-buckets
poetry run python scripts/activescale_cli.py list-objects research-archive-test --prefix ro-crates/
poetry run python scripts/activescale_cli.py object-exists research-archive-test ro-crates/archive.zip
poetry run python scripts/activescale_cli.py download-object research-archive-test ro-crates/archive.zip ./downloads/archive.zip
poetry run python scripts/activescale_cli.py --json object-exists research-archive-test ro-crates/archive.zip
poetry run python scripts/activescale_cli.py --json download-object research-archive-test ro-crates/archive.zip ./downloads/archive.zip
```

