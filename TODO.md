# TODO

## Core Integrations
- [ ] Implement mapping to real research drives (service account or temporary credentials). Evaluate `smbprotocol` or equivalent for traversing and processing drive contents.

## Scale and Performance
- [ ] Add configurable limits for archive jobs (for example max files, max bytes, max runtime) and enforce them in backend checks.
- [ ] Optimise for large drives and high file counts (streaming, batching, incremental processing or splitting into multiple RO-Crates). Max file size for ActiveScale is 50TB. 
- [ ] Reassess background execution approach; replace FastAPI `BackgroundTasks` with a durable queue (such as Celery or RQ) if reliability requirements increase.

## Quality and Validation
- [ ] Improve end-to-end tests that cover submission -> manifest -> RO-Crate build -> upload flow.
- [ ] Validate generated RO-Crate output against the profile as part of CI.
