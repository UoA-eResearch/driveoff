# TODO

## Scale and Performance
- [ ] Add configurable limits for archive jobs (for example max files, max bytes, max runtime) and enforce them in backend checks. Especially once we know the limit of whatever the prod infrastructure will be.
- [ ] Reassess background execution approach; replace FastAPI `BackgroundTasks` with a durable queue (such as Celery or RQ) if reliability requirements increase. OR make it so only one archiving job can be run at a time to avoid concurrency issues with the current implementation.


## Quality and Validation
- [ ] Improve end-to-end tests that cover submission -> manifest -> RO-Crate build -> upload flow.
- [ ] Validate generated RO-Crate output against the profile.
- [ ] Improved object and Tar integrity checks (e.g. validate checksums of uploaded parts, verify manifest integrity, and ensure reassembled archive matches original input).
- [ ] Question: should custom s3 metadata be added on every uploaded object/prat of the archive? Currently just the archive manifest object has the metadata added.

## Features and Enhancements
- [ ] Notifications module to send slack messages to admins when jobs complete or fail
- [ ] Logging to a durable store (e.g. file, database, or logging service) instead of just stdout for better traceability and debugging.
- [ ] Add workflow for deleting the original drive data after successful archive. Key steps would be: flagging the source data as ready for deletion, running a separate cleanup job that verifies the archive integrity, and verifies the object exists before deleting, and handling any edge cases (e.g. what if the archive is corrupted?). It would also need to retain a copy of the archive manifest, and location of the stored archive, in the research drive (the drives/views/shares themselves will not be deleted). This may be a separate workflow from the archiving process, but could be triggered from the same API endpoint by adding an additional parameter to indicate whether deletion should be performed after archiving.
