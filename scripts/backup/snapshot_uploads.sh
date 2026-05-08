#!/usr/bin/env bash
# =============================================================================
# Mydow / PRD10 — Snapshot the local uploads directory (PRD10_UPLOADS_BASE).
#
# Produces a tar.gz archive + SHA-256 sidecar, retained per
# AGENTOS_BACKUP_RETENTION_DAYS. This is the V1 file-storage versioning step
# for §11.7; once we move to S3/R2 in production this script will gain an
# ``s3 sync`` branch (already wired below if AGENTOS_BACKUP_S3_BUCKET is set).
#
# Usage::
#
#   bash scripts/backup/snapshot_uploads.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "${SCRIPT_DIR}/../.." && pwd )"

UPLOADS_BASE="${PRD10_UPLOADS_BASE:-${REPO_ROOT}/data/uploads}"
BACKUP_DIR="${BACKUP_DIR:-${REPO_ROOT}/.tmp/backups}"
RETENTION_DAYS="${AGENTOS_BACKUP_RETENTION_DAYS:-14}"
S3_BUCKET="${AGENTOS_BACKUP_S3_BUCKET:-}"
S3_PREFIX="${AGENTOS_BACKUP_S3_PREFIX:-mydow/uploads}"

if [[ ! -d "${UPLOADS_BASE}" ]]; then
    echo "Uploads dir does not exist: ${UPLOADS_BASE} — nothing to snapshot."
    exit 0
fi

mkdir -p "${BACKUP_DIR}/uploads"
STAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
ARCHIVE_PATH="${BACKUP_DIR}/uploads/${STAMP}_uploads.tar.gz"
SHA_PATH="${ARCHIVE_PATH}.sha256"
LOG_FILE="${BACKUP_DIR}/uploads/_snapshot.log"

log() {
    local ts; ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "[${ts}] $*" | tee -a "${LOG_FILE}"
}

log "Archiving ${UPLOADS_BASE} -> ${ARCHIVE_PATH}"

# tar -C cd into the uploads parent so the archive stores the leaf path
# (avoids absolute / leading-slash entries when restoring on a different
# host). --hard-dereference keeps any symlinks resolved.
PARENT_DIR="$(dirname "${UPLOADS_BASE}")"
LEAF="$(basename "${UPLOADS_BASE}")"

tar --create \
    --gzip \
    --hard-dereference \
    --file="${ARCHIVE_PATH}" \
    -C "${PARENT_DIR}" "${LEAF}"

if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${ARCHIVE_PATH}" > "${SHA_PATH}"
elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${ARCHIVE_PATH}" > "${SHA_PATH}"
fi

if [[ -n "${S3_BUCKET}" ]] && command -v aws >/dev/null 2>&1; then
    log "Uploading to s3://${S3_BUCKET}/${S3_PREFIX}/$(basename "${ARCHIVE_PATH}")"
    aws s3 cp "${ARCHIVE_PATH}" "s3://${S3_BUCKET}/${S3_PREFIX}/$(basename "${ARCHIVE_PATH}")"
    if [[ -f "${SHA_PATH}" ]]; then
        aws s3 cp "${SHA_PATH}" "s3://${S3_BUCKET}/${S3_PREFIX}/$(basename "${SHA_PATH}")"
    fi
fi

log "Pruning local snapshots older than ${RETENTION_DAYS} days"
find "${BACKUP_DIR}/uploads" -maxdepth 1 -type f \
    \( -name "*_uploads.tar.gz" -o -name "*_uploads.tar.gz.sha256" \) \
    -mtime "+${RETENTION_DAYS}" -print -delete \
    | tee -a "${LOG_FILE}" || true

log "Snapshot OK ($(stat --printf="%s" "${ARCHIVE_PATH}" 2>/dev/null || stat -f%z "${ARCHIVE_PATH}") bytes)"
