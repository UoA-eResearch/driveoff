# API server for offboarding

A FastAPI-based REST API server for managing project offboarding and archival workflows.

## Quick start

### Prerequisites
- Python 3.8+
- FastAPI and Uvicorn (see [Installation](#installation))

### Installation

1. **Install dependencies** from the project root:
   ```bash
   poetry install --with dev,test
   ```
   This installs the `driveoff` package and all required dependencies including FastAPI, and development/test dependencies.

2. **Set up API keys** (see [API Key Setup](#api-key-setup) below)

3. **Run the server** in development mode:
   ```bash
   poetry run fastapi dev src/api/main.py
   ```
   The server will start on `http://localhost:8000` by default.

## API Key Setup

The API server uses API keys for authentication and access control. Each key is associated with specific HTTP actions (GET, POST, PUT).

### Creating the API keys file

1. **Create the configuration directory** in your home folder:
   ```powershell
   $dir = Join-Path $env:USERPROFILE ".driveoff"
   New-Item -ItemType Directory -Force -Path $dir
   ```

2. **Create `api_keys.json`** in the `.driveoff` directory with your API keys:
   ```json
   {
     "keys": [
       {
         "value": "your-api-key-here",
         "actions": ["GET", "POST", "PUT"]
       }
     ]
   }
   ```

   **For development/PoC**, generate a secure random key using Python:
   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   Then manually add it to your `api_keys.json` file.

3. **Verify** the file is valid JSON and located at:
   ```
   C:\Users\<YourUsername>\.driveoff\api_keys.json
   ```

### Using API keys

Include your API key in requests using either:

- **Query parameter:**
  ```bash
  curl "http://localhost:8000/api/endpoint?api-key=your-api-key-here"
  ```

- **HTTP header:**
  ```bash
  curl -H "x-api-key: your-api-key-here" http://localhost:8000/api/endpoint
  ```

## Running the server

### Development mode (default)
```bash
fastapi dev src/api/main.py
```

The server runs with auto-reload enabled, restarting when code changes are detected.

### Production mode
To run in production mode with production environment variables and settings:
```bash
MODE=production fastapi run src/api/main.py
```

When `MODE=production` is set, ensure your production `api_keys.json` is properly configured with secure keys.

## Project structure

```
src/
├── config.py                   # Application settings (pydantic-settings)
├── api/
│   ├── main.py                 # FastAPI app entry point and lifespan setup
│   ├── dependencies.py         # FastAPI dependency providers and DB engine setup
│   ├── security.py             # API key validation and authentication
│   ├── cors.py                 # CORS configuration
│   ├── routers/
│   │   ├── drives.py           # Drive info endpoint
│   │   ├── submissions.py      # Archive submission endpoints
│   │   └── retrievals.py       # Archive retrieval endpoints
│   └── README.md               # This file
├── models/
│   ├── common.py               # Shared types (ResearchDriveName, etc.)
│   ├── request.py              # API request bodies
│   ├── response.py             # API response models
│   ├── submission.py           # ArchiveSubmission SQLModel table + ArchiveJobStage enum
│   └── retrieval.py            # ArchiveRetrieval SQLModel table + RetrievalJobStage enum
├── packaging/
│   ├── archive_chunks.py       # Chunked tar packaging for large archives
│   ├── archive_reassembly.py   # Reassembly of downloaded archive parts
│   ├── manifests.py            # BagIt bag creation and validation
│   └── crate/
│       ├── ro_builder.py       # RO-Crate construction
│       └── ro_loader.py        # RO-Crate loading/writing
├── service/
│   ├── activescale.py          # ActiveScale / S3 client (upload, download, restore)
│   ├── projectdb.py            # ProjectDB FastAPI dependency + initialisation
│   ├── projectdb_client.py     # ProjectDB HTTP client
│   └── projectdb_helpers.py    # ProjectDB response projection helpers
├── utils/
│   ├── logging.py              # Structured logging helpers
│   └── paths.py                # Filesystem path resolution and validation
└── workers/
    ├── submission_worker.py    # Background task: archive packaging and upload
    └── retrieval_worker.py     # Background task: archive restore and extraction
```

## Archive Submission Workflow

Send a `POST /api/v1/submission` request with the drive name, data classification, and retention period. The API validates the request synchronously (drive and project exist in ProjectDB, no active job already running, drive path is accessible) and immediately returns `201`. The actual archiving job runs as a background task through five stages:

**PACKAGING** — Project, drive, and member metadata is fetched from ProjectDB and used to build an [RO-Crate](https://www.researchobject.org/ro-crate/) inside a local staging directory. The drive contents are then packaged into [BagIt format](https://datatracker.ietf.org/doc/html/rfc8493) with checksums saved into a manifest file. The BagIt package is then compressed into a `.tar.gz` archive. The archive is chunked (split into ordered parts below the ActiveScale object-size limit). A sidecar `archive-manifest.json` is written listing each part with its index, filename, size, and SHA-256 checksum.

**UPLOADING** — Each archive part is streamed to ActiveScale under a deterministic object prefix. Successfully uploaded part keys are persisted to the database after each part, so a retry can skip already-uploaded parts and resume from where it left off.

**WRITING_MANIFEST** — The `archive-manifest.json` sidecar is uploaded to ActiveScale alongside the parts, with S3 object metadata (project ID, owner, classification, retention, part count) attached. The submission record is updated with the manifest key and the final list of part keys.

**CLEANUP** — The local staging directory (RO-Crate, tar parts) is deleted from disk. Cleanup failure is non-fatal and is recorded separately in `cleanup_error`; the job still advances to COMPLETED.

**COMPLETED / FAILED** — The final state and any error message are written to the `ArchiveSubmission` database record. A failed or abandoned job can be retried via `POST /api/v1/submission/{drive_name}/retry`, which reuses the existing record and increments `retry_count`. Already-uploaded parts are skipped on retry.

## Archive Retrieval Workflow

Send a `POST /api/v1/retrieval/{drive_name}` request with a `destination_path` body field. The API validates the request synchronously (completed submission exists, no active retrieval in progress, destination path is writable) and immediately returns `201`. The actual retrieval runs as a background task through four stages:

**RESTORING** — The archive manifest and all chunked archive parts are requested from tape/archival storage. If any are on tape, the task polls until they are thawed (up to 24 h by default, configurable via `activescale_restore_poll_max_seconds`). Files already in active storage skip the restore step.

**DOWNLOADING** — Each archive part is streamed from ActiveScale to a local scratch directory. Progress is persisted to the database after each part, so a fresh retrieval request can skip already-downloaded parts.

**EXTRACTING** — The parts are reassembled into a single `.tar.gz`, per-part SHA-256 checksums are verified, and the archive is extracted into `destination_path`. BagIt integrity validation is then run on the extracted directory. Scratch files are deleted on success.

**COMPLETED / FAILED** — The final state and any error message are written to the `ArchiveRetrieval` database record. On failure, re-submit a retrieval request to start again.

## Development tips

- **Auto-reload:** Changes to `.py` files trigger automatic server restart (development mode only)
- **Interactive API docs:** Visit `http://localhost:8000/docs` for Swagger UI
- **Alternative docs:** Visit `http://localhost:8000/redoc` for ReDoc
- **Debug mode:** Check FastAPI logs in the terminal for request/response details

## Troubleshooting

### "API key path is not a valid JSON file" error
- Verify the file exists at `C:\Users\<YourUsername>\.driveoff\api_keys.json`
- Ensure the file contains valid JSON (no trailing commas, proper quotes)
- Check file encoding is UTF-8

### "Invalid or missing API Key" error
- Verify you're including the correct API key in your request
- Check that the key exists in your `api_keys.json` file
- Confirm the request includes the key via query parameter or `x-api-key` header

### Server fails to start
- Ensure FastAPI and dependencies are installed: `poetry install`
- Check that port 8000 is not already in use (change with `--port` flag if needed)
- Review error messages in the terminal output