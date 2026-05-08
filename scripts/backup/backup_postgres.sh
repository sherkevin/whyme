#!/usr/bin/env bash
# =============================================================================
# Mydow / PRD10 — Postgres logical backup (custom format).
#
# Produces ``${BACKUP_DIR}/postgres/${stamp}_${db}.dump.gz`` with a sibling
# ``.sha256`` file, then prunes anything older than ``RETENTION_DAYS`` and
# (optionally) uploads to S3/R2.
#
# Required environment (or .env file in repo root):
#   DATABASE_URL                 — postgresql[+asyncpg]://user:pass@host:port/db
# Optional environment:
#   BACKUP_DIR                   — default ./.tmp/backups
#   AGENTOS_BACKUP_RETENTION_DAYS — default 14
#   AGENTOS_BACKUP_S3_BUCKET     — when set, ``aws s3 cp`` is invoked
#   AGENTOS_BACKUP_S3_PREFIX     — default mydow/postgres
#
# Exit codes:
#   0 — success
#   1 — bad config / missing tools
#   2 — pg_dump failed
#   3 — checksum / upload failed
#
# Usage::
#
#   bash scripts/backup/backup_postgres.sh
#
# Designed to be safe under cron (uses absolute paths derived from the
# script location, captures both stderr/stdout to a sidecar log).
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "${SCRIPT_DIR}/../.." && pwd )"

BACKUP_DIR="${BACKUP_DIR:-${REPO_ROOT}/.tmp/backups}"
RETENTION_DAYS="${AGENTOS_BACKUP_RETENTION_DAYS:-14}"
S3_BUCKET="${AGENTOS_BACKUP_S3_BUCKET:-}"
S3_PREFIX="${AGENTOS_BACKUP_S3_PREFIX:-mydow/postgres}"

mkdir -p "${BACKUP_DIR}/postgres"

LOG_FILE="${BACKUP_DIR}/postgres/_backup.log"

log() {
    local ts
    ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "[${ts}] $*" | tee -a "${LOG_FILE}"
}

if [[ -z "${DATABASE_URL:-}" ]] && [[ -f "${REPO_ROOT}/.env" ]]; then
    # shellcheck disable=SC2046
    export $(grep -E "^DATABASE_URL=" "${REPO_ROOT}/.env" | xargs -d '\n' -I {} echo {})
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
    log "ERROR: DATABASE_URL is not set; cannot back up."
    exit 1
fi

# pg_dump understands postgresql:// but not postgresql+asyncpg://; strip
# the dialect suffix safely.
PG_URL="${DATABASE_URL/postgresql+asyncpg:\/\//postgresql:\/\/}"
PG_URL="${PG_URL/postgresql+psycopg:\/\//postgresql:\/\/}"

if ! command -v pg_dump >/dev/null 2>&1; then
    log "ERROR: pg_dump is not on PATH (install postgresql-client)."
    exit 1
fi

# Extract bare DB name for the filename (strip ?query).
DB_NAME="$(printf '%s' "${PG_URL}" | sed -E 's@.*/([^/?]+).*@\1@')"
STAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
DUMP_PATH="${BACKUP_DIR}/postgres/${STAMP}_${DB_NAME}.dump.gz"
SHA_PATH="${DUMP_PATH}.sha256"

log "Starting pg_dump of ${DB_NAME} -> ${DUMP_PATH}"

# -Fc = custom format (compressed, restorable by pg_restore)
# -Z9 = max compression
# --no-acl / --no-owner = portable across hosts
# We pipe through gzip -1 because -Fc is already compressed.
if ! pg_dump \
    --format=custom \
    --compress=9 \
    --quote-all-identifiers \
    --no-acl \
    --no-owner \
    --dbname="${PG_URL}" \
    --file="${DUMP_PATH%.gz}"
then
    log "ERROR: pg_dump exited non-zero."
    exit 2
fi

# Wrap in gzip for the rotation listing convenience (custom-format already
# compresses, so this is an outer envelope; pg_restore handles a gzipped
# custom dump via gunzip pipe in restore script).
gzip -f -9 "${DUMP_PATH%.gz}"

if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${DUMP_PATH}" > "${SHA_PATH}"
elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${DUMP_PATH}" > "${SHA_PATH}"
else
    log "WARN: no sha256sum/shasum available; skipping checksum sidecar."
fi

if [[ -n "${S3_BUCKET}" ]]; then
    if ! command -v aws >/dev/null 2>&1; then
        log "ERROR: AGENTOS_BACKUP_S3_BUCKET set but 'aws' CLI is not on PATH."
        exit 3
    fi
    log "Uploading to s3://${S3_BUCKET}/${S3_PREFIX}/$(basename "${DUMP_PATH}")"
    aws s3 cp "${DUMP_PATH}" "s3://${S3_BUCKET}/${S3_PREFIX}/$(basename "${DUMP_PATH}")"
    if [[ -f "${SHA_PATH}" ]]; then
        aws s3 cp "${SHA_PATH}" "s3://${S3_BUCKET}/${S3_PREFIX}/$(basename "${SHA_PATH}")"
    fi
fi

log "Pruning local dumps older than ${RETENTION_DAYS} days"
find "${BACKUP_DIR}/postgres" -maxdepth 1 -type f \
    \( -name "*_${DB_NAME}.dump.gz" -o -name "*_${DB_NAME}.dump.gz.sha256" \) \
    -mtime "+${RETENTION_DAYS}" -print -delete \
    | tee -a "${LOG_FILE}" || true

log "Backup OK ($(stat --printf="%s" "${DUMP_PATH}" 2>/dev/null || stat -f%z "${DUMP_PATH}") bytes)"
