#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="${ROOT_DIR}/.tmp/deploy"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/vps-preflight-$(date -u +%Y%m%dT%H%M%SZ).log"
exec > >(tee "$LOG_FILE") 2>&1

ENV_FILE="${1:-.env}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prd10.yml}"

info() { printf '[INFO] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*"; }
fail() { printf '[FAIL] %s\n' "$*"; exit 1; }

read_env_value() {
  local key="$1"
  awk -F= -v key="$key" '
    $0 ~ "^[[:space:]]*#" { next }
    $1 == key {
      sub(/^[^=]*=/, "", $0)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", $0)
      gsub(/^"|"$/, "", $0)
      gsub(/^'\''|'\''$/, "", $0)
      print $0
      exit
    }
  ' "$ENV_FILE"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing command: $1"
}

require_env_key() {
  local key="$1"
  local value
  value="$(read_env_value "$key" || true)"
  if [ -z "$value" ]; then
    fail "Missing required env key in ${ENV_FILE}: ${key}"
  fi
  printf '[OK] %s is set\n' "$key"
}

warn_placeholder() {
  local key="$1"
  local value
  value="$(read_env_value "$key" || true)"
  case "$value" in
    "" ) return 0 ;;
    *change_me*|*CHANGE_ME*|agentos|agentos_db|redis123|demo-password-123|your-*|example.com|http://localhost* )
      warn "${key} still looks like a local/example value: ${value}"
      ;;
  esac
}

info "Mydow VPS preflight"
info "Project: ${ROOT_DIR}"
info "Env file: ${ENV_FILE}"
info "Compose file: ${COMPOSE_FILE}"
info "Log: ${LOG_FILE}"

[ -f "$ENV_FILE" ] || fail "Env file not found: ${ENV_FILE}"
[ -f "$COMPOSE_FILE" ] || fail "Compose file not found: ${COMPOSE_FILE}"

require_command docker
require_command awk
require_command sed

docker compose version >/dev/null 2>&1 || fail "Docker Compose plugin is not available"
info "Docker Compose is available"

for key in \
  SECRET_KEY \
  JWT_SECRET_KEY \
  POSTGRES_PASSWORD \
  REDIS_PASSWORD \
  BASE_URL \
  CORS_ORIGINS \
  DEEPSEEK_API_KEY
do
  require_env_key "$key"
done

for key in \
  SECRET_KEY \
  JWT_SECRET_KEY \
  POSTGRES_USER \
  POSTGRES_PASSWORD \
  POSTGRES_DB \
  REDIS_PASSWORD \
  BASE_URL \
  CORS_ORIGINS \
  AGENTOS_CORS_ORIGINS \
  DEEPSEEK_API_KEY \
  SMTP_FROM
do
  warn_placeholder "$key"
done

BASE_URL_VALUE="$(read_env_value BASE_URL || true)"
CORS_VALUE="$(read_env_value CORS_ORIGINS || true)"
if [ -n "$BASE_URL_VALUE" ] && [ -n "$CORS_VALUE" ]; then
  case ",${CORS_VALUE}," in
    *",${BASE_URL_VALUE},"*) printf '[OK] CORS_ORIGINS includes BASE_URL\n' ;;
    *) warn "CORS_ORIGINS does not include BASE_URL (${BASE_URL_VALUE})" ;;
  esac
fi

DEMO_MODE="$(read_env_value AGENTOS_DEMO_MODE || true)"
PLACEHOLDER_MODE="$(read_env_value AGENTOS_AI_OFFLINE_PLACEHOLDER || true)"
ALLOW_ALL="$(read_env_value AGENTOS_CORS_ALLOW_ALL || true)"

case "${DEMO_MODE:-off}" in
  off|false|0|no|"") printf '[OK] AGENTOS_DEMO_MODE is not enabled\n' ;;
  *) warn "AGENTOS_DEMO_MODE is enabled; disable it for production" ;;
esac

case "${PLACEHOLDER_MODE:-off}" in
  off|false|0|no|"") printf '[OK] AGENTOS_AI_OFFLINE_PLACEHOLDER is not enabled\n' ;;
  *) warn "AGENTOS_AI_OFFLINE_PLACEHOLDER is enabled; production should fail visibly instead of using placeholders" ;;
esac

case "${ALLOW_ALL:-false}" in
  off|false|0|no|"") printf '[OK] AGENTOS_CORS_ALLOW_ALL is not enabled\n' ;;
  *) warn "AGENTOS_CORS_ALLOW_ALL is enabled; production should use explicit origins" ;;
esac

info "Validating docker compose config..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" --profile nginx config --quiet
printf '[OK] docker compose config is valid\n'

info "Checking host port bindings in rendered compose..."
RENDERED="$(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" --profile nginx config)"
printf '%s\n' "$RENDERED" | awk '
  /host_ip:/ { host=$2 }
  /target:/ { target=$2 }
  /published:/ {
    published=$2
    gsub(/"/, "", published)
    if (target == "5432" || target == "6379" || target == "8000" || target == "5050") {
      if (host != "127.0.0.1") {
        printf("[WARN] target %s published on host_ip %s port %s\n", target, host, published)
      } else {
        printf("[OK] target %s is localhost-bound on port %s\n", target, published)
      }
    }
  }
'

info "Preflight finished"
info "Next deployment command:"
printf '  docker compose --env-file %s -f %s --profile nginx up -d --build\n' "$ENV_FILE" "$COMPOSE_FILE"
info "Keep this log locally and copy it to the server deployment log folder after provisioning."
