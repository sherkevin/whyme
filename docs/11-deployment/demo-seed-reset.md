# Demo Seed Periodic Reset (PRD10 §10.7)

> **Purpose**: keep the public investor-facing demo at `https://demo.mydow.example/`
> in a known-good state so each new visitor sees the same well-curated data
> and the previous visitor's noise (random captures, half-deleted folders,
> dangling AI conversations) is wiped on a predictable cadence.
>
> **Non-goal**: this is **not** a backup/restore mechanism. For that, see
> [`docs/11-deployment/backup.md`](./backup.md). This script blows away
> demo seed rows and re-creates them; production tenants are untouched
> because the demo user is identified by a configurable email
> (`--email demo@mydow.example` by default).

## Contents

1. [Quick start](#1-quick-start)
2. [How it decides whether to reseed](#2-how-it-decides-whether-to-reseed)
3. [Exit codes & structured log](#3-exit-codes--structured-log)
4. [Deployment recipes](#4-deployment-recipes)
   * 4.1 [Linux cron](#41-linux-cron)
   * 4.2 [systemd timer](#42-systemd-timer)
   * 4.3 [Docker compose oneshot](#43-docker-compose-oneshot)
   * 4.4 [Kubernetes CronJob](#44-kubernetes-cronjob)
   * 4.5 [Windows Task Scheduler](#45-windows-task-scheduler)
5. [Health verification](#5-health-verification)
6. [Failure rollback](#6-failure-rollback)
7. [PRD10 cross-references](#7-prd10-cross-references)

---

## 1. Quick start

```bash
# One-shot reseed, default threshold (60 captures)
python scripts/demo_seed_reset.py

# Health probe, no writes — exit 10 means "you should reseed"
python scripts/demo_seed_reset.py --check-only

# Cron mode: reseed only when today's captures > 80
python scripts/demo_seed_reset.py --threshold 80

# Force unconditional reseed (use for nightly fresh-start jobs)
python scripts/demo_seed_reset.py --force
```

All of the above print exactly one JSON record per run to stdout (see
[§3](#3-exit-codes--structured-log)). Exit code drives cron alerting.

Pre-requisite environment:

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | — (must be set) | e.g. `postgresql+asyncpg://user:pw@host/db` |
| `AGENTOS_DEMO_EMAIL` | `demo@mydow.example` | Override the demo user identity |
| `AGENTOS_DEMO_PASSWORD` | `demo123` | Used only on first-run create |
| `AGENTOS_DEMO_FULL_NAME` | `Demo User` | Display name in seeded data |
| `AGENTOS_DEMO_RESET_THRESHOLD` | `60` | Default `--threshold` value |

## 2. How it decides whether to reseed

The script always probes the demo account first (read-only) and reads
three numbers:

| Metric | Source | Used for |
|---|---|---|
| `today_captures` | `COUNT(prd10_inbox_items WHERE user_id=demo AND created_at>=today_utc AND type=text)` | Drift detector |
| `seed_card_count` | `COUNT(cards WHERE user_id=demo)` | Sanity check |
| `seed_folder_count` | `COUNT(folders WHERE user_id=demo)` | Sanity check |

The reseed decision logic:

```
needs_reset = (
    args.force                               # nightly mode
    or not before["user_found"]              # first run / dropped DB
    or before["today_captures"] > threshold  # visitor-induced noise
)
```

This means:

* On a quiet day with no investor visits, the cron job is a no-op
  (`decision=skipped`, exit 0).
* Right after a heavy demo, `today_captures` likely shoots past 60-80
  and the job reseeds.
* If the demo user table got wiped (DB restore, etc.) the job
  always reseeds.

`--check-only` runs the same probe and returns exit 10 instead of writing,
so a Prometheus blackbox-style health check can alert on stale demos
without taking the lock.

## 3. Exit codes & structured log

Each run prints exactly one JSON line to stdout:

```json
{
  "event": "demo_seed_reset",
  "decision": "reseed",
  "threshold": 60,
  "today_captures_before": 73,
  "today_captures_after": 16,
  "seed_card_count_before": 87,
  "seed_card_count_after": 30,
  "seed_folder_count_before": 9,
  "seed_folder_count_after": 6,
  "duration_ms": 4823,
  "email": "demo@mydow.example",
  "ts": "2026-05-07T02:14:55+00:00"
}
```

| Exit code | Meaning | Cron action |
|---:|---|---|
| **0** | Success or "no action needed" | continue |
| **10** | `--check-only` says reseed recommended | trigger separate reseed job |
| **11** | Another reset is already running (lock contention) | warn, no retry |
| **20** | Reseed failed (see `error` key) | page on-call |
| **30** | Environment misconfigured (e.g. `DATABASE_URL` missing) | page on-call |

The `decision` enum is `reseed | skipped | reseed_recommended | error | lock_busy`.
Logging tooling should key off `event=demo_seed_reset` and route by
`decision`.

## 4. Deployment recipes

### 4.1 Linux cron

```bash
# /etc/cron.d/mydow-demo-reset
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
DATABASE_URL=postgresql+asyncpg://mydow:CHANGEME@db.internal/mydow_prod

# Every day at 02:00 UTC, threshold 80; force on Sunday
0 2 * * * mydow cd /opt/mydow && /opt/mydow/.venv/bin/python scripts/demo_seed_reset.py --threshold 80 >> /var/log/mydow/demo-reset.log 2>&1
0 2 * * 0 mydow cd /opt/mydow && /opt/mydow/.venv/bin/python scripts/demo_seed_reset.py --force >> /var/log/mydow/demo-reset.log 2>&1
```

Then add log rotation:

```
/var/log/mydow/demo-reset.log {
  daily
  rotate 14
  compress
  missingok
  notifempty
  copytruncate
}
```

### 4.2 systemd timer

```ini
# /etc/systemd/system/mydow-demo-reset.service
[Unit]
Description=Mydow demo seed periodic reset
After=postgresql.service network-online.target

[Service]
Type=oneshot
User=mydow
WorkingDirectory=/opt/mydow
EnvironmentFile=/etc/mydow/demo-reset.env
ExecStart=/opt/mydow/.venv/bin/python scripts/demo_seed_reset.py --threshold 80
StandardOutput=append:/var/log/mydow/demo-reset.log
StandardError=append:/var/log/mydow/demo-reset.log
```

```ini
# /etc/systemd/system/mydow-demo-reset.timer
[Unit]
Description=Run Mydow demo reset every 24h

[Timer]
OnCalendar=*-*-* 02:00:00 UTC
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
```

`/etc/mydow/demo-reset.env`:

```
DATABASE_URL=postgresql+asyncpg://mydow:CHANGEME@db.internal/mydow_prod
AGENTOS_DEMO_EMAIL=demo@mydow.example
AGENTOS_DEMO_RESET_THRESHOLD=80
```

Enable & verify:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mydow-demo-reset.timer
sudo systemctl list-timers mydow-demo-reset.timer
sudo journalctl -u mydow-demo-reset.service -n 50
```

### 4.3 Docker compose oneshot

Add a profile to `docker-compose.prd10.yml`:

```yaml
services:
  demo-reset:
    profiles: ["maintenance"]
    image: mydow-app:latest
    depends_on:
      postgres:
        condition: service_healthy
    env_file: [".env"]
    entrypoint: ["python", "scripts/demo_seed_reset.py"]
    command: ["--threshold", "80"]
```

Then schedule from the host crontab:

```bash
0 2 * * * docker compose -f /opt/mydow/docker-compose.prd10.yml --profile maintenance run --rm demo-reset
```

### 4.4 Kubernetes CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: mydow-demo-reset
  namespace: mydow
spec:
  schedule: "0 2 * * *"          # daily 02:00 UTC
  concurrencyPolicy: Forbid       # extra safety on top of advisory lock
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 5
  jobTemplate:
    spec:
      backoffLimit: 1
      template:
        spec:
          restartPolicy: Never
          containers:
            - name: demo-reset
              image: registry.example.com/mydow-app:latest
              imagePullPolicy: IfNotPresent
              args:
                - python
                - scripts/demo_seed_reset.py
                - --threshold
                - "80"
              envFrom:
                - secretRef: { name: mydow-database }
              env:
                - { name: AGENTOS_DEMO_EMAIL, value: "demo@mydow.example" }
              resources:
                requests: { cpu: "200m", memory: "256Mi" }
                limits:   { cpu: "1",    memory: "512Mi" }
```

### 4.5 Windows Task Scheduler

PowerShell installer script:

```powershell
$action  = New-ScheduledTaskAction `
            -Execute "D:\Codes\whyme\.venv\Scripts\python.exe" `
            -Argument "scripts\demo_seed_reset.py --threshold 80" `
            -WorkingDirectory "D:\Codes\whyme"

$trigger = New-ScheduledTaskTrigger -Daily -At 02:00

$settings = New-ScheduledTaskSettingsSet `
              -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
              -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5)

Register-ScheduledTask `
  -TaskName "MydowDemoReset" `
  -Action $action -Trigger $trigger -Settings $settings `
  -RunLevel Highest `
  -Description "PRD10 §10.7 — daily demo seed reset"
```

DATABASE_URL should be set as a system environment variable so the
scheduled task inherits it (`Set-ItemProperty -Path
'HKLM:\System\CurrentControlSet\Control\Session Manager\Environment'
-Name DATABASE_URL -Value '...'`).

## 5. Health verification

After deployment, run these three probes:

```bash
# 1) Dry-run probe — should print "decision":"skipped" or "reseed_recommended"
python scripts/demo_seed_reset.py --check-only

# 2) Force one round of reset, then verify counters return to baseline
python scripts/demo_seed_reset.py --force | tee /tmp/last-reset.json

# 3) Verify the demo account is logged-in-able right after reset
curl -X POST $APP_BASE/api/v1/demo/login -i | head -n 1   # expect 200
curl -X GET  $APP_BASE/api/v1/today \
     -H "Authorization: Bearer $(jq -r .access_token /tmp/demo-login.json)" \
     | jq .data.stats.today_capture_count   # expect a small number (≤ 30)
```

The reset is good when:

* `decision == "reseed"` in the JSON log
* `today_captures_after <= today_captures_before` (always true after
  reset because seeded captures use back-dated timestamps)
* `seed_card_count_after == 30` (PRD10 §25.3 baseline)
* `seed_folder_count_after == 6` (PRD10 §25.3 baseline)

If any of those fail, treat it as exit-code-30 and page on-call.

## 6. Failure rollback

The script is **destructive** for the demo user only — it wipes seed
rows tagged with `[seed]` and re-inserts them. Failure modes and
recovery:

| Failure | Symptom | Recovery |
|---|---|---|
| Seeder crashes mid-run | `decision=error`, `seed_card_count_after` differs from baseline | Re-run with `--force`; the `--reset` semantics are idempotent |
| DB unreachable | exit 30, `error=probe_failed:...` | Don't auto-retry; page on-call (likely an infra incident, not a demo issue) |
| Lock file orphaned | exit 11 forever | `rm .tmp/demo_seed_reset.lock` and re-run |
| Wrong `--email` | exit 0 but `seed_card_count_before == 0` | Set `AGENTOS_DEMO_EMAIL` correctly and re-run with `--force` |
| Production DB targeted by mistake | catastrophic data loss | **Use the production `--email` audit**: this script only ever touches rows owned by the configured demo email. If you ran it against prod with a real user's email, restore via [`docs/11-deployment/backup.md`](./backup.md). For ops safety, **always** set `--email demo@...` explicitly in cron jobs, never rely on defaults. |

## 7. PRD10 cross-references

* §10.1 — Demo auto-login (`AGENTOS_DEMO_MODE=on` + `POST /api/v1/demo/login`)
* §10.2 — Demo seed default account & data shape
* §25.3 — Authoritative seed counts (6 folders / 20 docs / 30 cards / 5 tasks / 5 notifs / 3 conv / 18 msgs / 5 skills / 10 search docs / 6 insights)
* §11.7 — Backups (this is **not** a backup; reset only restores demo
  rows, not user data)
* §14.10 — Acceptance gate "investor demo path doesn't error" — this
  script is what keeps that path stable across days.
