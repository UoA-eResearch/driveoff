# TODO

## Core Integrations
- [ ] Implement mapping to real research drives (service account or temporary credentials). Evaluate `smbprotocol` or equivalent for traversing and processing drive contents.
- [ ] Integrate with ActiveScale to automatically transfer archived data to long-term storage.
- [ ] Add authentication and authorization (for example via UoA Single Sign-On).

## Scale and Performance
- [ ] Add configurable limits for archive jobs (for example max files, max bytes, max runtime) and enforce them in backend checks.
- [ ] Optimise for large drives and high file counts (streaming, batching, incremental processing).
- [ ] Reassess background execution approach; replace FastAPI `BackgroundTasks` with a durable queue (such as Celery or RQ) if reliability requirements increase.

## Reliability and Operations
- [ ] Make archiving jobs resumable and idempotent (safe retry without duplicate outputs).
- [ ] Persist job status/history so progress and failures survive API restarts.
- [ ] Add structured logging and basic operational metrics around archive jobs.
- [ ] Define cleanup strategy for temporary working files after success/failure.

## Quality and Validation
- [ ] Add end-to-end tests that cover submission -> manifest -> RO-Crate build -> transfer flow.
- [ ] Validate generated RO-Crate output against the profile as part of CI.
- [ ] Document failure modes and operator runbook steps (common errors, retry behavior, recovery).
