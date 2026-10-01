#!/usr/bin/env bash
# List (and optionally abort) stale incomplete multipart uploads in the
# archive bucket.
#
# ActiveScale does not support the AbortIncompleteMultipartUpload lifecycle
# rule, so incomplete MPUs left behind by crashed archive jobs accumulate
# invisibly (they hold billable storage but do not appear in normal object
# listings). This script covers the same hygiene manually via the
# ListMultipartUploads / AbortMultipartUpload API operations. Run it
# occasionally, or from cron on the archiving host.
#
# Usage:
#   ./scripts/cleanup_incomplete_uploads.sh [bucket]
#
# Environment:
#   MODE=development|production  which modes/.env files to load (default: development)
#   MIN_AGE_DAYS=7               only touch uploads initiated at least this many days ago
#   APPLY=1                      actually abort the stale uploads; without it this is a DRY RUN
#   BYPASS_PROXY=1               bypass the corporate proxy for the ActiveScale host (default: on)
#
# Exit codes: 0 success, 1 API/credential failure, 3 operation not supported
# by ActiveScale, 124 timeout.
set -euo pipefail

MODE="${MODE:-development}"
BUCKET="${1:-research-archive-test}"
MIN_AGE_DAYS="${MIN_AGE_DAYS:-7}"
APPLY="${APPLY:-0}"
CHECK_TIMEOUT_SECONDS="${CHECK_TIMEOUT_SECONDS:-120}"
BYPASS_PROXY="${BYPASS_PROXY:-1}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_BASE="${REPO_ROOT}/modes/.env.${MODE}"
ENV_LOCAL="${REPO_ROOT}/modes/.env.${MODE}.local"

load_env_file() {
  local env_file="$1"
  if [[ -f "${env_file}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${env_file}"
    set +a
    echo "Loaded ${env_file}"
  fi
}

if ! command -v uv >/dev/null 2>&1; then
  echo "Error: uv is not installed or not on PATH."
  exit 1
fi

if [[ ! -f "${ENV_BASE}" && ! -f "${ENV_LOCAL}" ]]; then
  echo "Error: no env files found for MODE=${MODE}."
  echo "Expected at least one of:"
  echo "  ${ENV_BASE}"
  echo "  ${ENV_LOCAL}"
  exit 1
fi

load_env_file "${ENV_BASE}"
load_env_file "${ENV_LOCAL}"

export MODE
cd "${REPO_ROOT}"

if [[ "${APPLY}" == "1" ]]; then
  ACTION="ABORT stale uploads"
else
  ACTION="DRY RUN (set APPLY=1 to abort)"
fi
echo "Incomplete multipart upload cleanup (mode=${MODE}, bucket=${BUCKET})"
echo "Minimum age: ${MIN_AGE_DAYS} day(s) | Action: ${ACTION}"

if [[ "${BYPASS_PROXY}" == "1" ]]; then
    host="${ACTIVESCALE_HOSTNAME:-}"
    if [[ -n "${host}" ]]; then
        export NO_PROXY="${host}${NO_PROXY:+,${NO_PROXY}}"
        export no_proxy="${host}${no_proxy:+,${no_proxy}}"
    fi

    unset HTTPS_PROXY https_proxy HTTP_PROXY http_proxy ALL_PROXY all_proxy
    echo "Proxy bypass enabled for this run"
fi

if command -v timeout >/dev/null 2>&1; then
    RUN_CMD=(timeout "${CHECK_TIMEOUT_SECONDS}" uv run python - "${BUCKET}" "${MIN_AGE_DAYS}" "${APPLY}")
else
    RUN_CMD=(uv run python - "${BUCKET}" "${MIN_AGE_DAYS}" "${APPLY}")
fi

set +e
"${RUN_CMD[@]}" <<'PY'
from __future__ import annotations

import pathlib
import sys
from datetime import UTC, datetime, timedelta

from botocore.config import Config
from botocore.exceptions import ClientError

sys.path.insert(0, str(pathlib.Path.cwd() / "src"))

from config import get_settings
from service.activescale import _create_activescale_session

#: Error codes that mean the S3 implementation does not offer the operation.
UNSUPPORTED_CODES = {"NotImplemented", "MethodNotAllowed", "OperationNotSupported"}

bucket = sys.argv[1]
min_age_days = int(sys.argv[2])
apply_changes = sys.argv[3] == "1"
settings = get_settings()

session = _create_activescale_session()
client = session.client(
    "s3",
    endpoint_url=f"https://{settings.activescale_hostname}",
    config=Config(
        retries={"total_max_attempts": max(settings.activescale_retry_attempts, 1), "mode": "standard"},
        signature_version="s3v4",
        connect_timeout=max(settings.activescale_connect_timeout, 1),
        read_timeout=max(settings.activescale_read_timeout, 1),
    ),
)


def error_code(error: ClientError) -> str:
    return str(error.response.get("Error", {}).get("Code", "Unknown"))


try:
    uploads = []
    try:
        paginator = client.get_paginator("list_multipart_uploads")
        for page in paginator.paginate(Bucket=bucket):
            uploads.extend(page.get("Uploads", []))
    except ClientError as e:
        code = error_code(e)
        if code in UNSUPPORTED_CODES:
            print(f"UNSUPPORTED: ListMultipartUploads is not supported by this endpoint ({code}).")
            print("Incomplete uploads can only be inspected via the vendor's admin console.")
            raise SystemExit(3)
        print(f"FAIL: ListMultipartUploads error ({code}): {e}")
        raise SystemExit(1)

    print(f"In-progress multipart uploads in '{bucket}': {len(uploads)}")

    cutoff = datetime.now(UTC) - timedelta(days=min_age_days)
    stale = []
    for upload in uploads:
        initiated = upload.get("Initiated")
        if initiated is None:
            continue
        if initiated.tzinfo is None:
            initiated = initiated.replace(tzinfo=UTC)
        if initiated < cutoff:
            stale.append(upload)

    if not stale:
        print(f"Nothing to do: no uploads older than {min_age_days} day(s).")
        raise SystemExit(0)

    print(f"Stale uploads (older than {min_age_days} day(s)): {len(stale)}")
    for upload in stale:
        initiated = upload.get("Initiated")
        age_days = (datetime.now(UTC) - initiated).days if initiated else "?"
        print(f"  key={upload.get('Key')} upload_id={upload.get('UploadId')} initiated={initiated} age={age_days}d")

    if not apply_changes:
        print("DRY RUN complete: nothing aborted. Re-run with APPLY=1 to abort these uploads.")
        raise SystemExit(0)

    aborted = 0
    failures = 0
    for upload in stale:
        try:
            client.abort_multipart_upload(
                Bucket=bucket,
                Key=upload["Key"],
                UploadId=upload["UploadId"],
            )
            aborted += 1
            print(f"Aborted: key={upload['Key']} upload_id={upload['UploadId']}")
        except ClientError as e:
            code = error_code(e)
            if code in UNSUPPORTED_CODES:
                print(f"UNSUPPORTED: AbortMultipartUpload is not supported by this endpoint ({code}).")
                raise SystemExit(3)
            # NoSuchUpload means it completed or was aborted since listing - fine.
            if code == "NoSuchUpload":
                print(f"Already gone: key={upload['Key']} upload_id={upload['UploadId']}")
                continue
            failures += 1
            print(f"FAILED to abort key={upload['Key']} upload_id={upload['UploadId']} ({code}): {e}")

    print(f"Done: {aborted} aborted, {failures} failed, of {len(stale)} stale upload(s).")
    raise SystemExit(1 if failures else 0)
finally:
    client.close()
PY
run_exit=$?
set -e

if [[ "${run_exit}" -eq 124 ]]; then
    echo "FAIL: cleanup run timed out after ${CHECK_TIMEOUT_SECONDS}s."
    echo "Hint: verify DNS/routing/firewall for the ActiveScale hostname."
    exit 124
fi

exit "${run_exit}"
