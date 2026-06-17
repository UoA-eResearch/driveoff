# TODO

## Scale and Performance
- [ ] Add configurable limits for archive jobs (for example max files, max bytes, max runtime) and enforce them in backend checks.
- [x] Optimise for large drives and high file counts (streaming, batching, incremental processing or splitting into multiple RO-Crates). Max file size for ActiveScale is 50TB.
- [ ] Reassess background execution approach; replace FastAPI `BackgroundTasks` with a durable queue (such as Celery or RQ) if reliability requirements increase.

## Large Archive Datamodel and API (Draft)
- [x] Extend `ArchiveSubmission` schema to track archive transport metadata (`archive_part_count`, byte sizes, object prefix, manifest key, and ordered part keys).
- [x] Extend `ArchiveJobStage` vocabulary for chunked archive workflow (`packaging`, `uploading`, `writing_manifest`) while retaining legacy stage values for compatibility.
- [x] Extend `GET /api/v1/submission` response payload with new archive transport fields.
- [x] Implement chunked archive writer (single logical tar split into ordered parts below ActiveScale object limit).
- [x] Upload each part as a separate object under a deterministic prefix and persist uploaded part keys incrementally.
- [x] Write sidecar archive manifest file (`archive-manifest.json`) during packaging with part ordering, per-part checksum, and total byte count.
- [x] Upload sidecar archive manifest object to ActiveScale alongside uploaded parts.
- [x] Replace single-object upload call in archive worker with chunked upload pipeline.
- [x] Add retry/resume support to skip already uploaded parts and continue from persisted metadata.
- [x] Add archive retrieval/reassembly utility using persisted part ordering from manifest.
- [x] Add integration tests for chunked upload success, interrupted upload resume, and manifest integrity checks.

## Quality and Validation
- [ ] Improve end-to-end tests that cover submission -> manifest -> RO-Crate build -> upload flow.
- [ ] Validate generated RO-Crate output against the profile.
- [ ] Improved object and Tar integrity checks (e.g. validate checksums of uploaded parts, verify manifest integrity, and ensure reassembled archive matches original input).
- [ ] Question: should custom s3 metadata be added on every uploaded object/prat of the archive? Currently just the archive manifest object has the metadata added.

## Features and Enhancements
- [x] Add archive retrieval endpoint that reassembles chunked archive on-the-fly and uploads it into a Vast view. This would allow admins to retrieve a researchers' archived data without needing to interact directly with ActiveScale or S3 APIs. It needs to put the reassembled archive into a Vast view (i.e. back into the drive namespace that it came from) for users to access with existing tools. The workflow would be: researcher asks for archive retrieval -> administrator creates vast view with the research drive name -> administrator sends request to backend -> backend retrieves manifest (NOTE: object retrieval might require command restore-object to 'thaw' the data to disk before download. This can take time and so will need to poll s3 for the object status to change from archived to restored.) -> backend streams chunked archive parts from ActiveScale into Vast -> backend validates checksums andreassembles the archive -> backend extracts files and validates bagIt -> notify administrator that job is completed (and whether success/failure) -> researcher accesses the view with their tools. This would require careful handling of streaming and temporary storage to avoid memory issues with large archives. Question: should a record be stored in projectdb for retrieval jobs to track their status and metadata?
- [ ] Notifications module to send slack messages to admins when jobs complete or fail
- [ ] Logging to a durable store (e.g. file, database, or logging service) instead of just stdout for better traceability and debugging.
- [x] Refactor main.py to separate API route definitions from core business logic / background tasks.
