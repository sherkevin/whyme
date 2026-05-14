#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-${BASE_URL:-}}"
[ -n "$BASE_URL" ] || {
  printf 'Usage: %s https://your.domain\n' "$0" >&2
  exit 2
}

BASE_URL="${BASE_URL%/}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_DIR="${ROOT_DIR}/.tmp/deploy"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/vps-smoke-$(date -u +%Y%m%dT%H%M%SZ).log"
exec > >(tee "$LOG_FILE") 2>&1
CURL_TLS_ARGS=()
if [ "${CURL_INSECURE:-}" = "1" ]; then
  CURL_TLS_ARGS=(-k)
fi

check() {
  local path="$1"
  local expected="$2"
  local code
  code="$(curl "${CURL_TLS_ARGS[@]}" -sS -o /tmp/mydow-smoke-body.$$ -w '%{http_code}' "${BASE_URL}${path}")"
  if [ "$code" != "$expected" ]; then
    printf '[FAIL] GET %s expected %s got %s\n' "$path" "$expected" "$code"
    sed -n '1,20p' /tmp/mydow-smoke-body.$$
    rm -f /tmp/mydow-smoke-body.$$
    exit 1
  fi
  printf '[OK] GET %s -> %s\n' "$path" "$code"
  rm -f /tmp/mydow-smoke-body.$$
}

printf '[INFO] Mydow smoke target: %s\n' "$BASE_URL"
printf '[INFO] Log: %s\n' "$LOG_FILE"

check /health 200
check /ready 200

code="$(curl "${CURL_TLS_ARGS[@]}" -sS -L -o /tmp/mydow-smoke-body.$$ -w '%{http_code}' "${BASE_URL}/mydow/")"
if [ "$code" != "200" ]; then
  printf '[FAIL] GET /mydow/ expected 200 after redirects got %s\n' "$code"
  sed -n '1,20p' /tmp/mydow-smoke-body.$$
  rm -f /tmp/mydow-smoke-body.$$
  exit 1
fi
if ! grep -qi 'mydow' /tmp/mydow-smoke-body.$$; then
  printf '[FAIL] /mydow/ did not look like the Mydow frontend\n'
  rm -f /tmp/mydow-smoke-body.$$
  exit 1
fi
rm -f /tmp/mydow-smoke-body.$$
printf '[OK] GET /mydow/ -> 200 and frontend marker found\n'
printf '[INFO] Smoke finished\n'
