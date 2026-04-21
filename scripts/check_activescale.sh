#!/usr/bin/env bash
set -euo pipefail

MODE="${MODE:-development}"
BUCKET="${1:-research-archive-test}"

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

poetry run python - "${BUCKET}" <<'PY'
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path.cwd() / "src"))

from api.activescale import _create_activescale_session, verify_connection
from config import get_settings

bucket = sys.argv[1]
settings = get_settings()

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

session = _create_activescale_session()
client = session.client("s3", endpoint_url=f"https://{settings.activescale_hostname}")

try:
    ok = verify_connection(client, bucket)
    if ok:
        print(f"PASS: ActiveScale connection verified for bucket '{bucket}'.")
        raise SystemExit(0)

    print(f"FAIL: Could not verify ActiveScale access to bucket '{bucket}'.")
    raise SystemExit(1)
finally:
    client.close()
PY
