Driveoff CLI
============

This small CLI helps create RO‑Crates by sending project/drive JSON to the running API.

Quick start
-----------

- Prepare a JSON payload matching your API model (see `web/src/client/types.gen.ts` for input shapes).
- Run with Python directly (no install required):

```bash
python src/cli/cli.py <command> path/to/payload.json --api-url http://localhost:8000
```

Where `<command>` is either `post-resdriveinfo` or `create-crate` (see below). The API URL defaults to `http://localhost:8000` if not provided.

Options
-------
- `--dry-run`: print the payload instead of sending it
- `--pretty`: pretty-print JSON when used with `--dry-run`

API key
-------

The API requires an API key. You can provide it in two ways:

- Command-line: pass `--api-key YOUR_KEY` to the subcommand.
- Environment variable: set `DRIVEOFF_API_KEY` and the CLI will use it when `--api-key` is omitted.

The key is sent in an `X-API-Key: <key>` header.

Commands
---------------

- `post-resdriveinfo` always POSTs to `/api/v1/resdriveinfo` on the configured `--api-url`. This endpoint is used for sending the initial project/drive metadata to the API before creating the RO-Crate.
- `create-crate` always POSTs to `/api/v1/submission` on the configured `--api-url`. This endpoint is used to kick off the RO-Crate creation process after the project/drive metadata has been sent.

Example post-resdriveinfo payload:
----------------
```json
{
  "title": "Project Title",
  "description": "Project Description.",
  "division": "Centre for eResearch",
  "start_date": "2022-01-01",
  "end_date": "2026-11-04",
  "id": 100,
  "members": [
    {
      "id": null,
      "person.email": "test1234@auckland.ac.nz",
      "person.full_name": "Test Person",
      "person.identities": {
        "items": [
          {
            "username": "test1234"
          }
        ]
      },
      "role": {
        "id": 1,
        "name": "Project Owner"
      }
    },
    {
      "id": null,
      "person.email": "test5678@auckland.ac.nz",
      "person.full_name": "Another Person",
      "person.identities": {
        "items": [
          {
            "username": "test5678"
          }
        ]
      },
      "role": {
        "id": 3,
        "name": "Project Team Member"
      }
    }
  ],
  "codes": [
    {
      "id": null,
      "code": "uoa00001"
    },
    {
      "id": null,
      "code": "rescer201200001"
    }
  ],
  "services": {
    "research_drive": [
      {
        "allocated_gb": 25600.0,
        "date": "2024-10-13",
        "first_day": "2022-01-09",
        "free_gb": 24004.5,
        "id": null,
        "last_day": null,
        "name": "rescer201200001-example-drive-name",
        "percentage_used": 2.75578,
        "used_gb": 1596.0
      }
    ]
  }
}
```

Example create-crate payload:
----------------
```json
{
  "retentionPeriodYears": 6,
  "retentionPeriodJustification": "Something here",
  "dataClassification": "Public",
  "isCompleted": true,
  "driveName": "rescer201200001-example-drive-name",
  "projectChanges": {
    "title": "New title",
    "description": "New description"
  }
}
```