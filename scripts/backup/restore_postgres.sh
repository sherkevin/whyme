#!/usr/bin/env bash
# =============================================================================
# Mydow / PRD10 — Postgres logical restore (custom format).
#
# Reads a dump produced by ``backup_postgres.sh`` and applies it to the
# database in ``DATABASE_URL`` (or ``--target`` flag).
#
# Usage::
#
#   bash scripts/backup/restore_postgres.sh path/to/20260506T...dump.gz
#   bash scripts/backup/restore_postgres.sh latest        # picks most recent dump
#   bash scripts/backup/restore_postgres.sh latest --target postgresql://user:pass@host/db
#
# Safety:
#   * Refuses to run when DATABASE_URL or --target points at a host that
#     contains the substring "prod" / "production" unless ``--force`` is set.
#   * Always uses ``--clean --if-exists`` so re-applying onto a populated DB
#     is idempotent.
#   * Verifies the SHA-256 sidecar (when present) before restoring.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "${SCRIPT_DIR}/../.." && pwd )"
BACKUP_DIR="${BACKUP_DIR:-${REPO_ROOT}/.tmp/backups}"

DUMP_ARG="${1:-}"
TARGET=""
FORCE=0
shift || true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)
            TARGET="$2"; shift 2 ;;
        --force)
            FORCE=1; shift ;;
        *)
            echo "Unknown arg: $1"; exit 1 ;;
    esac
done

if [[ -z "${DUMP_ARG}" ]]; then
    echo "Usage: restore_postgres.sh <path/to/dump.gz | latest> [--target URL] [--force]"
    exit 1
fi

if [[ "${DUMP_ARG}" == "latest" ]]; then
    DUMP_PATH="$(ls -1t "${BACKUP_DIR}/postgres/"*.dump.gz 2>/dev/null | head -n1 || true)"
    if [[ -z "${DUMP_PATH}" ]]; then
        echo "No dumps found under ${BACKUP_DIR}/postgres/"
        exit 1
    fi
else
    DUMP_PATH="${DUMP_ARG}"
fi

if [[ ! -f "${DUMP_PATH}" ]]; then
    echo "Dump not found: ${DUMP_PATH}"
    exit 1
fi

if [[ -z "${TARGET}" ]]; then
    TARGET="${DATABASE_URL:-}"
fi

if [[ -z "${TARGET}" ]]; then
    echo "ERROR: --target or DATABASE_URL is required."
    exit 1
fi

PG_URL="${TARGET/postgresql+asyncpg:\/\//postgresql:\/\/}"
PG_URL="${PG_URL/postgresql+psycopg:\/\//postgresql:\/\/}"

if [[ "${FORCE}" -ne 1 ]] && echo "${PG_URL}" | grep -E -i 'prod|production' >/dev/null; then
    echo "Refusing to restore into a host that looks like production: ${PG_URL}"
    echo "Pass --force to override."
    exit 1
fi

SHA_PATH="${DUMP_PATH}.sha256"
if [[ -f "${SHA_PATH}" ]]; then
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum -c "${SHA_PATH}"
    elif command -v shasum >/dev/null 2>&1; then
        # shasum -c expects the same format as sha256sum -c
        shasum -a 256 -c "${SHA_PATH}"
    else
        echo "WARN: no sha256sum/shasum installed; skipping checksum verification."
    fi
fi

echo "Restoring ${DUMP_PATH} into ${PG_URL}"

# Pipe through gunzip → pg_restore so we don't need to keep an uncompressed copy on disk.
gunzip -c "${DUMP_PATH}" | pg_restore \
    --clean \
    --if-exists \
    --no-acl \
    --no-owner \
    --dbname="${PG_URL}"

echo "Restore complete."
