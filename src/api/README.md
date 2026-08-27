# API server for offboarding

A FastAPI-based REST API server for managing project offboarding and archival workflows.

Configuration (modes, ActiveScale, storage paths, notifications, logging) is documented in the [root README](../../README.md) - this file covers running the server, authentication, the endpoints, and how the archive and retrieval jobs work.

## Quick start

### Prerequisites
- Python 3.14+
- uv for dependency management (see [Installing uv](https://docs.astral.sh/uv/getting-started/installation/))

### Installation

1. **Install dependencies** from the project root:
   ```bash
   uv sync --group dev --group test
   ```
   This installs the `driveoff` package and all required dependencies including FastAPI, and development/test dependencies.

2. **Set up API keys** (see [API Key Setup](#api-key-setup) below)

3. **Run the server** in development mode:
   ```bash
   uv run fastapi dev src/api/main.py
   ```
   The server will start on `http://localhost:8000` by default.

To run with production environment variables and settings:
```bash
MODE=production uv run fastapi run src/api/main.py
```

When `MODE=production` is set, ensure your production `api_keys.json` is configured with secure keys.

## API Key Setup

The API server uses API keys for authentication and access control. Each key is associated with the HTTP actions it may perform (`GET`, `POST`, `PUT`, `PATCH`).

### Creating the API keys file

The server reads keys from `~/.driveoff/api_keys.json` (that is, `$HOME/.driveoff/api_keys.json` on Linux or `C:\Users\<YourUsername>\.driveoff\api_keys.json` on Windows).

1. **Create the configuration directory** in your home folder:

   Linux/macOS:
   ```bash
   mkdir -p ~/.driveoff
   ```
   Windows (PowerShell):
   ```powershell
   New-Item -ItemType Directory -Force -Path (Join-Path $env:USERPROFILE ".driveoff")
   ```

2. **Create `api_keys.json`** in the `.driveoff` directory with your API keys:
   ```json
   {
     "keys": [
       {
         "value": "your-api-key-here",
         "actions": ["GET", "POST", "PUT", "PATCH"]
       }
     ]
   }
   ```
   Grant each key only the actions it needs (for example, a status-dashboard key needs only `GET`).

   Generate a secure random key with:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

3. **Verify** the file is valid JSON and located at the path above.

### Using API keys

Include your API key in the `x-api-key` HTTP header on every request:

```bash
curl -H "x-api-key: your-api-key-here" http://localhost:8000/api/v1/driveinfo?drive_name=...
```

Keys are accepted from the header **only** - query-parameter keys are deliberately unsupported, because query strings end up in request logs, proxy logs, and browser history. A valid key lacking the required action for an endpoint receives `403`; a missing or unknown key receives `401`.

## Endpoints

All endpoints are under the `/api/v1` prefix and require an API key.

| Endpoint | Purpose |
| --- | --- |
| `GET /driveinfo?drive_name=` | Drive and project info from ProjectDB (members, codes, dates) |
| `POST /submission` | Create an archive submission and start the archive job |
| `GET /submission?drive_name=` | Archive submission status for a drive |
| `POST /submission/{drive_name}/retry` | Retry a failed or abandoned archive job |
| `POST /retrieval/{drive_name}` | Start an archive retrieval job (body: `destination_path`) |
| `GET /retrieval/{drive_name}` | Retrieval jobs for a drive, newest first (`?latest=true` for just the newest) |
| `PATCH /submission/{id}`, `PATCH /retrieval/{id}` | Disabled (404) - reserved for the future split-worker architecture; enable with `worker_patch_endpoints_enabled` |

Interactive documentation with full request/response schemas: `http://localhost:8000/docs` (Swagger UI) or `http://localhost:8000/redoc`.

**Archive workflow precondition:** all researcher access to a drive must be removed before an archive submission is made for it (an operational step performed outside this API) - see the root README.

## Project structure

```
src/
├── config.py                   # Application settings (pydantic-settings)
├── api/
│   ├── main.py                 # FastAPI app entry point, request logging, lifespan setup
│   ├── dependencies.py         # FastAPI dependency providers and DB engine setup
│   ├── security.py             # API key validation and authentication
│   ├── cors.py                 # CORS configuration
│   ├── routers/
│   │   ├── drives.py           # Drive info endpoint
│   │   ├── submissions.py      # Archive submission endpoints
│   │   └── retrievals.py       # Archive retrieval endpoints
│   └── README.md               # This file
├── models/
│   ├── common.py               # Shared types (ResearchDriveName, retention helpers)
│   ├── request.py              # API request bodies
│   ├── response.py             # API response models
│   ├── submission.py           # ArchiveSubmission SQLModel table + ArchiveJobStage enum
│   └── retrieval.py            # ArchiveRetrieval SQLModel table + RetrievalJobStage enum
├── packaging/
│   ├── bag_stream.py           # Virtual bagging: BagIt bag synthesized inside the tar stream
│   ├── archive_chunks.py       # Chunked tar packaging + streaming verification
│   ├── archive_reassembly.py   # Reassembly of downloaded archive parts
│   ├── manifests.py            # BagIt bag validation (creation lives in bag_stream)
│   └── crate/
│       ├── ro_builder.py       # RO-Crate construction
│       └── ro_loader.py        # RO-Crate loading/writing
├── service/
│   ├── activescale.py          # ActiveScale / S3 client (upload, download, restore)
│   ├── notifications.py        # Best-effort Slack alerts for job results
│   ├── projectdb.py            # ProjectDB FastAPI dependency + initialisation
│   ├── projectdb_client.py     # ProjectDB HTTP client
│   └── projectdb_helpers.py    # ProjectDB response projection helpers
├── utils/
│   ├── __init__.py             # utc_now (all timestamps are UTC)
│   ├── job_reconciliation.py   # Startup handling of jobs interrupted by a restart
│   ├── logging.py              # Structured logging helpers
│   └── paths.py                # Filesystem path resolution and validation
└── workers/
    ├── submission_worker.py    # Background task: archive packaging and upload
    └── retrieval_worker.py     # Background task: archive restore and extraction
```

## Archive Submission Workflow

Send a `POST /api/v1/submission` request with the drive name, data classification, and retention period. The API validates the request synchronously (drive and project exist in ProjectDB, no active job already running, drive path is readable) and immediately returns `201`. The actual archiving job runs as a background task through five stages:

**PACKAGING** — Project, drive, and member metadata is fetched from ProjectDB and used to generate [RO-Crate](https://www.researchobject.org/ro-crate/) metadata in a local staging directory. The drive contents are then streamed into a gzip-compressed tar that contains a [BagIt](https://datatracker.ietf.org/doc/html/rfc8493) bag synthesized on the fly ("virtual bagging" - see the root README): payload files land under `<drive>/data/` with SHA-256 checksums computed from the same read pass, the RO-Crate metadata is injected as `data/ro-crate-metadata.json`, and the BagIt tag files are generated in-stream. The source drive is only ever read - it is never modified. The tar stream is split into ordered parts below the ActiveScale object-size limit, and a sidecar `archive-manifest.json` is written listing each part with its index, filename, size, and SHA-256 checksum. Before any upload, a verification pass streams all parts back, validates the gzip/tar structure, and re-checks every payload file's hash against the in-tar BagIt manifest.

**UPLOADING** — Each archive part is streamed to ActiveScale under a deterministic object prefix, its uploaded size is verified, and (when enabled) COMPLIANCE-mode object retention is applied. Uploaded part keys are persisted to the database after each part for operator visibility. Because the parts are byte-slices of a single tar stream, a retry rebuilds the stream and **re-uploads every part** (overwriting same-named objects from the failed attempt) - parts are never mixed between attempts, since slices from two different streams cannot be reassembled.

**WRITING_MANIFEST** — The `archive-manifest.json` sidecar is uploaded to ActiveScale alongside the parts, with S3 object metadata (project ID, owner, classification, retention, part count) attached. The submission record is updated with the manifest key and the final list of part keys.

**CLEANUP** — The local staging directory (RO-Crate metadata, tar parts) is deleted from disk. Cleanup failure is non-fatal and is recorded separately in `cleanup_error`; the job still advances to COMPLETED.

**COMPLETED / FAILED** — The final state and any error message are written to the `ArchiveSubmission` database record. A failed or abandoned job can be retried via `POST /api/v1/submission/{drive_name}/retry`, which reuses the existing record, increments `retry_count`, and re-runs the whole job from packaging onwards.

## Archive Retrieval Workflow

Send a `POST /api/v1/retrieval/{drive_name}` request with a `destination_path` body field. The API validates the request synchronously (completed submission exists, no active retrieval in progress, destination is under the allowlisted storage base and writable) and immediately returns `201`. The actual retrieval runs as a background task through four stages:

**RESTORING** — The archive manifest and all chunked archive parts are requested from tape/archival storage. If any are on tape, the task polls until they are thawed (up to 24 h by default, configurable via `activescale_restore_poll_max_seconds`). Files already in active storage skip the restore step.

**DOWNLOADING** — Each archive part is streamed from ActiveScale to a local scratch directory keyed by the retrieval job's ID. Downloaded part keys are recorded on the retrieval record for visibility; note that a *new* retrieval request always starts from scratch (resuming a failed retrieval's downloads is not currently supported).

**EXTRACTING** — The parts are reassembled into a single `.tar.gz`, per-part SHA-256 checksums are verified against the archive manifest, and the archive is extracted into `destination_path`. BagIt integrity validation (the `bagit` library re-checking every payload hash) is then run on the extracted directory. Scratch files are deleted on success.

**COMPLETED / FAILED** — The final state and any error message are written to the `ArchiveRetrieval` database record. On failure, re-submit a retrieval request to start again.

## Development tips

- **Auto-reload:** Changes to `.py` files trigger automatic server restart (development mode only)
- **Interactive API docs:** Visit `http://localhost:8000/docs` for Swagger UI
- **Alternative docs:** Visit `http://localhost:8000/redoc` for ReDoc
- **Debug mode:** Check FastAPI logs in the terminal for request/response details

## Troubleshooting

### "API key path is not a valid JSON file" error
- Verify the file exists at `~/.driveoff/api_keys.json` (`C:\Users\<YourUsername>\.driveoff\api_keys.json` on Windows)
- Ensure the file contains valid JSON (no trailing commas, proper quotes)
- Check file encoding is UTF-8

### "Invalid or missing API Key" error
- Verify you're including the correct API key in your request
- Check that the key exists in your `api_keys.json` file
- Confirm the request sends the key in the `x-api-key` header (query-parameter keys are not accepted)

### "API Key does not have ... rights" (403)
- The key authenticated but is not permitted that HTTP action - add the action to the key's `actions` list in `api_keys.json`

### Server fails to start
- Ensure FastAPI and dependencies are installed: `uv sync --group dev --group test`
- Check that port 8000 is not already in use (change with `--port` flag if needed)
- Review error messages in the terminal output
