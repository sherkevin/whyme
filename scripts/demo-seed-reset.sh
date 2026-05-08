#!/usr/bin/env bash
# PRD10 §10.7 — Demo seed periodic reset (Linux/macOS cron).
#
# Re-seeds the demo@mydow.example account every 24h so investors / new
# evaluators always land on a clean dataset. Pair with crontab:
#
#   # /etc/cron.d/mydow-demo-reset
#   0 4 * * * mydow /opt/mydow/scripts/demo-seed-reset.sh >> /var/log/mydow-demo-reset.log 2>&1
#
# Or as a systemd timer:
#
#   # /etc/systemd/system/mydow-demo-reset.service
#   [Service]
#   Type=oneshot
#   User=mydow
#   WorkingDirectory=/opt/mydow
#   ExecStart=/opt/mydow/scripts/demo-seed-reset.sh
#
#   # /etc/systemd/system/mydow-demo-reset.timer
#   [Timer]
#   OnCalendar=*-*-* 04:00:00
#   Persistent=true
#   [Install]
#   WantedBy=timers.target
#
# Environment overrides:
#   DEMO_DATABASE_URL    SQLAlchemy URL of the demo DB.
#   DEMO_EMAIL           Demo account email (default demo@mydow.example).
#   DEMO_PASSWORD        Demo account password (default demo123).
#   DEMO_PROJECT_ROOT    Repo root (default the repo housing this script).

set -euo pipefail

PROJECT_ROOT="${DEMO_PROJECT_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DEMO_EMAIL="${DEMO_EMAIL:-demo@mydow.example}"
DEMO_PASSWORD="${DEMO_PASSWORD:-demo123}"
DATABASE_URL="${DEMO_DATABASE_URL:-sqlite+aiosqlite:///${PROJECT_ROOT}/.tmp/demo.db}"

mkdir -p "${PROJECT_ROOT}/.tmp"
LOG_FILE="${PROJECT_ROOT}/.tmp/demo-seed-reset.log"

START=$(date '+%Y-%m-%d %H:%M:%S')
echo "[${START}] Reset start (db=${DATABASE_URL} email=${DEMO_EMAIL})" >> "${LOG_FILE}"

export DATABASE_URL
export PYTHONPATH="${PROJECT_ROOT}/src"
export AGENTOS_DEMO_MODE="on"

cd "${PROJECT_ROOT}"

if python scripts/seed_prd10.py \
    --email "${DEMO_EMAIL}" \
    --password "${DEMO_PASSWORD}" \
    --reset >> "${LOG_FILE}" 2>&1; then
    END=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${END}] Reset OK" >> "${LOG_FILE}"
    exit 0
else
    rc=$?
    END=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${END}] Reset FAILED with exit code ${rc}" >> "${LOG_FILE}"
    exit "${rc}"
fi
