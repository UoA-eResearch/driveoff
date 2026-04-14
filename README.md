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



## Still To Do:
- Once ProjectDB API has new endpoint deployed for getting drive by name, implement drive lookup in FastAPI backend. For now, drive information is mocked based on the drive name provided by the user.
- Implement actual mapping to real research drives (service account / temporary credentials to access drive). Use smbprotocol or similar to process drive contents.
- Integrate with ActiveScale to automatically transfer archived data to long-term storage.
- Add authentication and authorization, e.g. through integration with UoA's Single Sign-On (SSO) system.
- Improve test coverage.
- Optimise for large drives, and/or large number of files, and/or potentially impose some limits on how much data can be archived through this tool, and implement checks for these limits.
- Add more detailed error handling and user feedback in the frontend.
- Improve logging and monitoring for the FastAPI backend, especially for the background archiving tasks.
