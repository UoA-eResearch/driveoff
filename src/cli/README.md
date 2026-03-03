Driveoff CLI
============

This small CLI helps create RO‑Crates by sending project/drive JSON to the running API.

Quick start
-----------

- Prepare a JSON payload matching your API model (see `web/src/client/types.gen.ts` for input shapes).
- Run with Python directly (no install required):

```bash
python src/cli/cli.py create-crate path/to/payload.json --api-url http://localhost:8000 --endpoint /api/v1/submission
```

Options
-------
- `--dry-run`: print the payload instead of sending it
- `--pretty`: pretty-print JSON when used with `--dry-run`
- `--endpoint`: API endpoint path or full URL (default: `/api/v1/submission`)

Example payload
----------------
```json
{
  "title": "Tītoki metabolomics",
  "description": "Metabolomics study of stress responses in Tītoki plants.",
  "division": "Liggins Institute",
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
        "id": null,
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
        "id": null,
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
      "code": "reslig202200001"
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
        "name": "reslig202200001-Tītoki-metabolomics",
        "percentage_used": 2.75578,
        "used_gb": 1596.0
      }
    ]
  }
}
```