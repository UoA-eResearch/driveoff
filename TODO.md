# TODO

## Scale and Performance
- [ ] Add configurable limits for archive jobs (for example max files, max bytes, max runtime) and enforce them in backend checks.
- [ ] Optimise for large drives and high file counts (streaming, batching, incremental processing or splitting into multiple RO-Crates). Max file size for ActiveScale is 50TB.
- [ ] Reassess background execution approach; replace FastAPI `BackgroundTasks` with a durable queue (such as Celery or RQ) if reliability requirements increase.

## Large Archive Datamodel and API (Draft)
- [x] Extend `ArchiveSubmission` schema to track archive transport metadata (`archive_layout`, `archive_package_format`, `archive_part_count`, byte sizes, object prefix, manifest key, and ordered part keys).
- [x] Extend `JobStage` vocabulary for chunked archive workflow (`packaging`, `uploading_parts`, `writing_manifest`) while retaining legacy stage values for compatibility.
- [x] Extend `GET /api/v1/submission` response payload with new archive transport fields.
- [ ] Implement chunked archive writer (single logical tar split into ordered parts below ActiveScale object limit).
- [ ] Upload each part as a separate object under a deterministic prefix and persist uploaded part keys incrementally.
- [ ] Write and upload sidecar archive manifest object (`archive-manifest.json`) containing part ordering, per-part checksum, and total byte count.
- [ ] Replace single-object upload call in archive worker with chunked upload pipeline.
- [ ] Add retry/resume support to skip already uploaded parts and continue from persisted metadata.
- [ ] Add archive retrieval/reassembly utility using persisted part ordering from manifest.
- [ ] Add integration tests for chunked upload success, interrupted upload resume, and manifest integrity checks.

## Quality and Validation
- [ ] Improve end-to-end tests that cover submission -> manifest -> RO-Crate build -> upload flow.
- [ ] Validate generated RO-Crate output against the profile as part of CI.
