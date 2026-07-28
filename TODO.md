# TODO

## Scale and Performance
- [ ] Add configurable limits for archive jobs (for example max files, max bytes, max runtime) and enforce them in backend checks. Especially once we know the limit of whatever the prod infrastructure will be.
- [ ] Reassess background execution approach; replace FastAPI `BackgroundTasks` with a durable queue (such as Celery or RQ) if reliability requirements increase. OR make it so only one archiving job can be run at a time to avoid concurrency issues with the current implementation.


## Quality and Validation
- [x] Improved object and Tar integrity checks (e.g. validate checksums of uploaded parts, verify manifest integrity, and ensure reassembled archive matches original input).
- [ ] Add minimum metadata validation for the archive job (required fields are documented in the Wiki). This should be checked upfront in the API request validation so a job fails fast if there is missing metadata. Allow force flag to override this check if needed.
- [ ] Validate generated RO-Crate output against the profile (follows on from the previous item). This should be done after the RO-Crate is generated, but before the archive is uploaded. If the RO-Crate fails validation, the job should fail and log an error message indicating what was invalid.
- [ ] Ensure temp files are cleaned up properly from disk after a job completes or fails. Consider sdelete for permanent deletion of data.
- [ ] Improve end-to-end tests that cover submission -> manifest -> RO-Crate build -> upload flow.
- [ ] Question: should custom s3 metadata be added on every uploaded object/prat of the archive? Currently just the archive manifest object has the metadata added.

## Features and Enhancements
- [x] Set retention policies on the stored archive objects to prevent accidental deletion, and ensure long-term preservation of the archived data.
- [ ] Convert this project to use uv and replace linting etc with Ruff
- [ ] The ProjectDB now stores data retention and classification metadata (Storage Properties table). The archive submission workflow should be updated to use this metadata from ProjectDB instead of requiring it to be provided in the API request. If values are provided in the request, they should override the ProjectDB values (but not alter the values in the ProjectDB). If the retention and classification are incorect in the projectDB they can be updated via the ProjectDB API, but driveoff s not responsible for updating ProjectDB values.
- [ ] Add workflow for deleting the original drive data after successful archive. Key steps would be: flagging the source data as ready for deletion, running a separate cleanup job that verifies the archive integrity, and verifies the object exists before deleting, and handling any edge cases (e.g. what if the archive is corrupted?). It would also need to retain a copy of the archive manifest, and location of the stored archive, in the research drive (the drives/views/shares themselves will not be deleted). This may be a completely separate workflow from the archiving process, OR could be triggered from the archive submission API endpoint by adding an additional parameter to indicate whether deletion should be performed after archiving - design decision needed.
- [ ] Notifications module to send slack messages to admins when jobs complete or fail

## Infrastructure and Deployment
- [ ] Add scripts/playbook for setting up the VM this will run on. Initial thought is to use Ansible for configuration management to set up the application and its dependencies. This will help automate the deployment process and ensure consistency across environments. Key steps would include: set squid proxy variables, configure git, clone repo, install Python, install Poetry (or uv if we switch), install dependencies, setup api keys file for driveoff (expects allowed keys to be in api_keys.json file), set up environment variables for configuration, and setup a process manager (e.g. systemd or supervisor) to run the application as a service and ensure it restarts on failure (for initial phase we may just run the fastapi manually though).
- [ ] Setup autofs for auto mount and unmount of drives (if we will use linux)
- [ ] Setup secrets management service - investigate options (Barbican, AWS Parameter Store, Hashicorp Vault, etc.).
- [ ] Following on from the above item, set up a better solution for storing and managing API keys for the driveoff service. Currently, the allowed keys are stored in a JSON file, but a more secure and manageable solution should be implemented (e.g. using a secrets management service or encrypted storage).
- [ ] Setup a monitoring tool and external log aggregation - investigate options for logging to a durable store (e.g. file, database, or logging service) instead of just stdout for better traceability and debugging.
