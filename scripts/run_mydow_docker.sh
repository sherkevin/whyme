#!/usr/bin/env bash
set -euo pipefail

NO_OPEN=0
NO_BUILD=0
NO_NGINX=0
NO_PROMPT=0
REQUIRE_DEEPSEEK=0
SEED_DEMO_DATA=0
PORT=8000
HTTP_PORT=8080

usage() {
  cat <<'EOF'
Usage: ./run-mydow.sh [options]

Options:
  --no-open              Do not open the browser after startup.
  --no-build             Reuse existing images.
  --no-nginx             Start app/Postgres/Redis only; skip nginx.
  --no-prompt            Do not prompt for secrets.
  --require-deepseek     Fail when DEEPSEEK_API_KEY/API_KEY is missing.
  --seed-demo-data       Optional: add demo seed data to the real local DB.
  --port N               Host port for direct FastAPI app access (default: 8000).
  --http-port N          Host port for nginx access (default: 8080).
  -h, --help             Show this help.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --no-open) NO_OPEN=1 ;;
    --no-build) NO_BUILD=1 ;;
    --no-nginx) NO_NGINX=1 ;;
    --no-prompt) NO_PROMPT=1 ;;
    --require-deepseek) REQUIRE_DEEPSEEK=1 ;;
    --seed-demo-data) SEED_DEMO_DATA=1 ;;
    --port) PORT="${2:?missing value for --port}"; shift ;;
    --http-port) HTTP_PORT="${2:?missing value for --http-port}"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[mydow] unknown option: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env.docker.local"
COMPOSE_FILE="${ROOT}/docker-compose.prd10.yml"
APP_BASE_URL="http://localhost:${PORT}"
NGINX_BASE_URL="http://localhost:${HTTP_PORT}"
if [ "$NO_NGINX" -eq 1 ]; then
  BASE_URL="$APP_BASE_URL"
else
  BASE_URL="$NGINX_BASE_URL"
fi
FRONTEND_URL="${BASE_URL}/"
DIRECT_FRONTEND_URL="${APP_BASE_URL}/mydow/biz_v14/"
HEALTH_URL="${BASE_URL}/health"

env_file_value() {
  local file="$1"
  local name="$2"
  [ -f "$file" ] || return 0
  awk -F= -v key="$name" '
    $0 ~ "^[[:space:]]*" key "[[:space:]]*=" {
      sub(/^[^=]*=/, "", $0)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", $0)
      gsub(/^"|"$/, "", $0)
      gsub(/^'\''|'\''$/, "", $0)
      print $0
      exit
    }
  ' "$file"
}

project_env_value() {
  local name="$1"
  local value="${!name:-}"
  if [ -n "$value" ]; then
    printf '%s' "$value"
    return 0
  fi
  for file in "${ROOT}/.env.local" "${ROOT}/.env"; do
    value="$(env_file_value "$file" "$name" || true)"
    if [ -n "$value" ]; then
      printf '%s' "$value"
      return 0
    fi
  done
}

new_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  elif command -v python3 >/dev/null 2>&1; then
    python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
  else
    date +%s%N | sha256sum | awk '{print $1}'
  fi
}

set_env_value() {
  local name="$1"
  local value="$2"
  if [ -f "$ENV_FILE" ] && grep -Eq "^[[:space:]]*${name}[[:space:]]*=" "$ENV_FILE"; then
    local tmp="${ENV_FILE}.tmp"
    awk -v key="$name" -v val="$value" '
      $0 ~ "^[[:space:]]*" key "[[:space:]]*=" { print key "=" val; next }
      { print }
    ' "$ENV_FILE" > "$tmp"
    mv "$tmp" "$ENV_FILE"
  else
    printf '%s=%s\n' "$name" "$value" >> "$ENV_FILE"
  fi
}

resolve_deepseek_key() {
  local key
  key="$(project_env_value DEEPSEEK_API_KEY || true)"
  if [ -z "$key" ]; then key="$(project_env_value API_KEY || true)"; fi
  if [ -z "$key" ] && [ "$NO_PROMPT" -eq 0 ]; then
    printf '[mydow] Paste DeepSeek API Key (leave blank to start without AI): ' >&2
    stty -echo 2>/dev/null || true
    IFS= read -r key || true
    stty echo 2>/dev/null || true
    printf '\n' >&2
  fi
  if [ -z "$key" ] && [ "$REQUIRE_DEEPSEEK" -eq 1 ]; then
    echo "[mydow] DEEPSEEK_API_KEY is required." >&2
    exit 1
  fi
  printf '%s' "$key"
}

resolve_llm_api_base() {
  local api_base
  api_base="$(project_env_value LLM_BASE_URL || true)"
  [ -n "$api_base" ] || api_base="$(project_env_value DEEPSEEK_OPENAI_BASE_URL || true)"
  [ -n "$api_base" ] || api_base="$(project_env_value API_BASE || true)"
  if [ -z "$api_base" ] && [ "$NO_PROMPT" -eq 0 ]; then
    printf '[mydow] LLM API URL [https://api.deepseek.com]: ' >&2
    IFS= read -r api_base || true
  fi
  [ -n "$api_base" ] || api_base="https://api.deepseek.com"
  printf '%s' "$api_base"
}

ensure_env() {
  local api_key api_base model model_fallback cors pg_user pg_pass pg_db redis_pass
  api_key="$(resolve_deepseek_key)"
  api_base="$(resolve_llm_api_base)"
  model="$(project_env_value LLM_MODEL || true)"
  [ -n "$model" ] || model="$(project_env_value MODEL || true)"
  [ -n "$model" ] || model="$(project_env_value DEEPSEEK_MODEL || true)"
  [ -n "$model" ] || model="deepseek-v4-flash"
  model_fallback="$(project_env_value LLM_MODEL_FALLBACK || true)"
  [ -n "$model_fallback" ] || model_fallback="$(project_env_value MODEL_FALLBACK || true)"
  [ -n "$model_fallback" ] || model_fallback="deepseek-v4-pro"
  cors="${BASE_URL},${APP_BASE_URL},http://127.0.0.1:${PORT},http://127.0.0.1:${HTTP_PORT}"

  if [ ! -f "$ENV_FILE" ]; then
    pg_user="mydow"
    pg_pass="$(new_secret)"
    pg_db="mydow_prd10"
    redis_pass="$(new_secret)"
    cat > "$ENV_FILE" <<EOF
# Generated by run-mydow. Do not commit this file.
SECRET_KEY=$(new_secret)
JWT_SECRET_KEY=$(new_secret)
FIELD_ENCRYPTION_KEY=
DATABASE_URL=postgresql+asyncpg://${pg_user}:${pg_pass}@postgres:5432/${pg_db}
POSTGRES_USER=${pg_user}
POSTGRES_PASSWORD=${pg_pass}
POSTGRES_DB=${pg_db}
POSTGRES_HOST_PORT=15432
REDIS_PASSWORD=${redis_pass}
REDIS_HOST_PORT=16379
ENVIRONMENT=production
AGENTOS_DEMO_MODE=off
AGENTOS_PRD10_WORKER=on
AGENTOS_AI_LLM=on
AGENTOS_AI_OFFLINE_PLACEHOLDER=off
AGENTOS_AI_TEMPERATURE=0.3
AGENTOS_AI_MAX_TOKENS=2000
API_KEY=${api_key}
DEEPSEEK_API_KEY=${api_key}
LLM_BASE_URL=${api_base}
LLM_MODEL=${model}
LLM_MODEL_FALLBACK=${model_fallback}
DEEPSEEK_OPENAI_BASE_URL=${api_base}
DEEPSEEK_MODEL=${model}
CAPTURE_ENRICH_MODEL=
APP_PORT=${PORT}
HTTP_PORT=${HTTP_PORT}
BASE_URL=${BASE_URL}
CORS_ORIGINS=${cors}
AGENTOS_CORS_ORIGINS=${cors}
AGENTOS_CORS_ALLOW_ALL=false
CORS_ALLOW_ALL=false
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
SMTP_FROM=noreply@localhost
SMTP_USE_TLS=true
MYDOW_ROOT_REDIRECT=on
LOG_LEVEL=info
EOF
    echo "[mydow] generated ${ENV_FILE}"
  else
    set_env_value APP_PORT "$PORT"
    set_env_value HTTP_PORT "$HTTP_PORT"
    set_env_value BASE_URL "$BASE_URL"
    set_env_value CORS_ORIGINS "$cors"
    set_env_value AGENTOS_CORS_ORIGINS "$cors"
    set_env_value AGENTOS_CORS_ALLOW_ALL "false"
    set_env_value CORS_ALLOW_ALL "false"
    set_env_value AGENTOS_DEMO_MODE "off"
    set_env_value AGENTOS_AI_OFFLINE_PLACEHOLDER "off"
    set_env_value MYDOW_ROOT_REDIRECT "on"
    [ -n "$(env_file_value "$ENV_FILE" SECRET_KEY || true)" ] || set_env_value SECRET_KEY "$(new_secret)"
    [ -n "$(env_file_value "$ENV_FILE" JWT_SECRET_KEY || true)" ] || set_env_value JWT_SECRET_KEY "$(new_secret)"
    [ -n "$(env_file_value "$ENV_FILE" POSTGRES_USER || true)" ] || set_env_value POSTGRES_USER "mydow"
    [ -n "$(env_file_value "$ENV_FILE" POSTGRES_DB || true)" ] || set_env_value POSTGRES_DB "mydow_prd10"
    [ -n "$(env_file_value "$ENV_FILE" POSTGRES_PASSWORD || true)" ] || set_env_value POSTGRES_PASSWORD "$(new_secret)"
    [ -n "$(env_file_value "$ENV_FILE" REDIS_PASSWORD || true)" ] || set_env_value REDIS_PASSWORD "$(new_secret)"
    if [ -z "$(env_file_value "$ENV_FILE" DATABASE_URL || true)" ]; then
      pg_user="$(env_file_value "$ENV_FILE" POSTGRES_USER)"
      pg_pass="$(env_file_value "$ENV_FILE" POSTGRES_PASSWORD)"
      pg_db="$(env_file_value "$ENV_FILE" POSTGRES_DB)"
      set_env_value DATABASE_URL "postgresql+asyncpg://${pg_user}:${pg_pass}@postgres:5432/${pg_db}"
    fi
    if [ -n "$api_key" ]; then
      [ -n "$(env_file_value "$ENV_FILE" API_KEY || true)" ] || set_env_value API_KEY "$api_key"
      [ -n "$(env_file_value "$ENV_FILE" DEEPSEEK_API_KEY || true)" ] || set_env_value DEEPSEEK_API_KEY "$api_key"
    fi
    echo "[mydow] updated ${ENV_FILE}"
  fi

  if [ -z "$(env_file_value "$ENV_FILE" DEEPSEEK_API_KEY || true)" ] && [ -z "$(env_file_value "$ENV_FILE" API_KEY || true)" ]; then
    echo "[mydow] warning: no DeepSeek key configured; AI calls will fail until DEEPSEEK_API_KEY is set." >&2
  fi
}

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

wait_healthy() {
  echo "[mydow] waiting for backend health: ${HEALTH_URL}"
  for _ in $(seq 1 90); do
    if curl -fsS "$HEALTH_URL" 2>/dev/null | grep -q '"healthy"'; then
      echo "[mydow] backend is healthy"
      return 0
    fi
    sleep 2
  done
  compose logs --tail 120 app || true
  echo "[mydow] backend did not become healthy" >&2
  exit 1
}

wait_database_ready() {
  local probe encoded
  probe='import asyncio
from sqlalchemy import text
from agent_os.db.base import get_sessionmaker

async def main():
    async with get_sessionmaker()() as db:
        await db.execute(text("select 1 from prd10_jobs limit 1"))

asyncio.run(main())
'
  encoded="$(printf '%s' "$probe" | base64 | tr -d '\n')"
  echo "[mydow] waiting for database schema"
  for _ in $(seq 1 45); do
    if compose exec -T app python -c "import base64; exec(base64.b64decode('${encoded}').decode('utf-8'))" >/dev/null 2>&1; then
      echo "[mydow] database schema is ready"
      return 0
    fi
    sleep 2
  done
  compose logs --tail 160 app || true
  echo "[mydow] database schema is not ready" >&2
  exit 1
}

cd "$ROOT"

if ! docker ps >/dev/null 2>&1; then
  echo "[mydow] Docker is not running. Start Docker Desktop or Docker Engine and rerun ./run-mydow.sh." >&2
  exit 1
fi

ensure_env

up_args=()
if [ "$NO_NGINX" -eq 1 ]; then
  up_args=(up -d)
else
  up_args=(--profile nginx up -d)
fi
if [ "$NO_BUILD" -eq 0 ]; then up_args+=(--build); fi
if [ "$NO_NGINX" -eq 1 ]; then
  up_args+=(app postgres redis)
else
  up_args+=(app postgres redis nginx)
fi
compose "${up_args[@]}"

wait_healthy
wait_database_ready

if [ "$SEED_DEMO_DATA" -eq 1 ]; then
  echo "[mydow] seeding optional demo data into the persisted database"
  compose exec -T app python scripts/seed_prd10.py
fi

cat <<EOF

[mydow] ready: ${FRONTEND_URL}
[mydow] direct app URL: ${DIRECT_FRONTEND_URL}
[mydow] env file: ${ENV_FILE}
[mydow] stop: docker compose --env-file .env.docker.local -f docker-compose.prd10.yml --profile nginx down
[mydow] reset data: docker compose --env-file .env.docker.local -f docker-compose.prd10.yml --profile nginx down -v

EOF

if [ "$NO_OPEN" -eq 0 ]; then
  if command -v open >/dev/null 2>&1; then
    open "$FRONTEND_URL"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$FRONTEND_URL" >/dev/null 2>&1 || true
  fi
fi
