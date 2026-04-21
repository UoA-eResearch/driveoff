#!/usr/bin/env bash
set -euo pipefail

MODE="${MODE:-development}"
BUCKET="${1:-research-archive-test}"
CHECK_TIMEOUT_SECONDS="${CHECK_TIMEOUT_SECONDS:-60}"
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

if ! command -v poetry >/dev/null 2>&1; then
  echo "Error: poetry is not installed or not on PATH."
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

echo "Starting ActiveScale check (mode=${MODE}, bucket=${BUCKET})"
echo "Timeout: ${CHECK_TIMEOUT_SECONDS}s"

if [[ "${BYPASS_PROXY}" == "1" ]]; then
    host="${ACTIVESCALE_HOSTNAME:-}"
    if [[ -n "${host}" ]]; then
        export NO_PROXY="${host}${NO_PROXY:+,${NO_PROXY}}"
        export no_proxy="${host}${no_proxy:+,${no_proxy}}"
    fi

    unset HTTPS_PROXY https_proxy HTTP_PROXY http_proxy ALL_PROXY all_proxy
    echo "Proxy bypass enabled for this check"
fi

if command -v timeout >/dev/null 2>&1; then
    CHECK_CMD=(timeout "${CHECK_TIMEOUT_SECONDS}" poetry run python - "${BUCKET}")
else
    CHECK_CMD=(poetry run python - "${BUCKET}")
fi

set +e
"${CHECK_CMD[@]}" <<'PY'
from __future__ import annotations

import pathlib
import sys

from botocore.config import Config

sys.path.insert(0, str(pathlib.Path.cwd() / "src"))

from api.activescale import _create_activescale_session, verify_connection
from config import get_settings

bucket = sys.argv[1]
settings = get_settings()

print("Python check started", flush=True)

access_key = (
    settings.activescale_access_key.get_secret_value()
    if settings.activescale_access_key
    else ""
)
secret_key = (
    settings.activescale_secret_key.get_secret_value()
    if settings.activescale_secret_key
    else ""
)

missing = []
if not settings.activescale_hostname:
    missing.append("ACTIVESCALE_HOSTNAME")
if not access_key:
    missing.append("ACTIVESCALE_ACCESS_KEY")
if not secret_key:
    missing.append("ACTIVESCALE_SECRET_KEY")

if missing:
    print("Error: missing required settings: " + ", ".join(missing))
    raise SystemExit(2)

print("Creating ActiveScale session", flush=True)
session = _create_activescale_session()
print("Creating S3 client", flush=True)

retry_attempts = max(settings.activescale_retry_attempts, 1)
connect_timeout = max(settings.activescale_connect_timeout, 1)
read_timeout = max(settings.activescale_read_timeout, 1)

client = session.client(
    "s3",
    endpoint_url=f"https://{settings.activescale_hostname}",
    config=Config(
        retries={"total_max_attempts": retry_attempts, "mode": "standard"},
        signature_version="s3v4",
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
    ),
)

try:
    print("Checking bucket access", flush=True)
    ok = verify_connection(client, bucket)
    if ok:
        print(f"PASS: ActiveScale connection verified for bucket '{bucket}'.")
        raise SystemExit(0)

    print(f"FAIL: Could not verify ActiveScale access to bucket '{bucket}'.")
    raise SystemExit(1)
finally:
    client.close()
PY
check_exit=$?
set -e

if [[ "${check_exit}" -eq 124 ]]; then
    echo "FAIL: ActiveScale check timed out after ${CHECK_TIMEOUT_SECONDS}s."
    echo "Hint: verify DNS/routing/firewall for the ActiveScale hostname."
    exit 124
fi

exit "${check_exit}"
