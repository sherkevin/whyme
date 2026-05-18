# One-Click Local Docker Runbook

> Goal: let another person run the full Mydow frontend + backend stack on
> their own computer with one command, without committing any private key,
> DeepSeek key, SMTP password, database password, or local runtime data.

## What This Starts

The one-click launcher starts the real local stack:

```text
nginx -> FastAPI app -> Postgres 16
                   \-> Redis 7
```

The frontend is served by the FastAPI app and nginx. The default browser entry
is:

```text
http://localhost:8080/
```

The root path redirects straight to the current product UI:

```text
/mydow/biz_v14/
```

## Prerequisites

Required:

- Git
- Docker Desktop on Windows/macOS, or Docker Engine + Docker Compose plugin on Linux
- Project source code cloned locally
- A DeepSeek API key for complete AI functionality

Optional:

- SMTP settings if email sending must work from the local machine

## Windows

From the repository root:

```cmd
run-mydow.cmd
```

The script will:

1. Check that Docker is running.
2. Generate `.env.docker.local` if it does not exist.
3. Copy the LLM API URL from `LLM_BASE_URL`, `DEEPSEEK_OPENAI_BASE_URL`,
   `API_BASE`, `.env.local`, or `.env`.
4. Prompt for the LLM API URL if no URL is found. Press Enter to use
   `https://api.deepseek.com`.
5. Copy `DEEPSEEK_API_KEY` from the process environment, `.env.local`, or `.env`.
6. Prompt for a DeepSeek key if no key is found.
7. Generate local-only `SECRET_KEY`, `JWT_SECRET_KEY`, Postgres password, and Redis password.
8. Start `app`, `postgres`, `redis`, and `nginx` with Docker Compose.
9. Wait for `/health` and the database schema.
10. Open `http://localhost:8080/`.

Useful variants:

```cmd
run-mydow.cmd -NoOpen
run-mydow.cmd -NoBuild
run-mydow.cmd -RequireDeepSeek
run-mydow.cmd -SeedDemoData
run-mydow.cmd -NoNginx -Port 8000
run-mydow.cmd -HttpPort 8081
```

## macOS / Linux

From the repository root:

```bash
chmod +x run-mydow.sh scripts/run_mydow_docker.sh
./run-mydow.sh
```

Useful variants:

```bash
./run-mydow.sh --no-open
./run-mydow.sh --no-build
./run-mydow.sh --require-deepseek
./run-mydow.sh --seed-demo-data
./run-mydow.sh --no-nginx --port 8000
./run-mydow.sh --http-port 8081
```

## Recommended DeepSeek Setup

Best option before running:

Windows PowerShell:

```powershell
$env:LLM_BASE_URL = "https://api.deepseek.com"
$env:DEEPSEEK_API_KEY = "sk-..."
.\run-mydow.cmd
```

macOS / Linux:

```bash
export LLM_BASE_URL="https://api.deepseek.com"
export DEEPSEEK_API_KEY="sk-..."
./run-mydow.sh
```

Alternatively, create a local `.env.local` file:

```env
LLM_BASE_URL=https://api.deepseek.com
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_OPENAI_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

`.env.local` and `.env.docker.local` are ignored by git.

## SMTP

The stack can run without SMTP. In that mode, security email verification writes
a real local-outbox request instead of pretending that an email was sent.

If local email sending must work, edit `.env.docker.local` after first launch:

```env
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your-user
SMTP_PASS=your-password
SMTP_FROM=noreply@example.com
SMTP_USE_TLS=true
```

Then restart:

```bash
docker compose --env-file .env.docker.local -f docker-compose.prd10.yml --profile nginx up -d app nginx
```

## Stop / Reset

Stop containers but keep local data:

```bash
docker compose --env-file .env.docker.local -f docker-compose.prd10.yml --profile nginx down
```

Delete local database/uploads/Redis volumes:

```bash
docker compose --env-file .env.docker.local -f docker-compose.prd10.yml --profile nginx down -v
```

## Data And Accounts

Default mode does not enable demo login and does not seed demo content:

```env
AGENTOS_DEMO_MODE=off
AGENTOS_AI_OFFLINE_PLACEHOLDER=off
MYDOW_ROOT_REDIRECT=on
```

Users should register a real local account through the UI. If you need demo
data for training or screenshots, run with `-SeedDemoData` on Windows or
`--seed-demo-data` on macOS/Linux.

## Troubleshooting

Docker is not running:

```text
Start Docker Desktop, wait until it says Docker is running, then rerun.
```

Port conflict on `8080`:

```bash
./run-mydow.sh --http-port 8081
```

or on Windows:

```cmd
run-mydow.cmd -HttpPort 8081
```

AI calls fail:

```text
Set LLM_BASE_URL and DEEPSEEK_API_KEY in the environment or .env.local, then rerun.
```

Database gets into a bad local state:

```bash
docker compose --env-file .env.docker.local -f docker-compose.prd10.yml --profile nginx down -v
./run-mydow.sh
```

## Evidence Boundary

This runbook is for local one-command delivery. It does not replace the
production VPS runbook for `mydow.club`, ICP filing, HTTPS certificates,
backup, or production SMTP hardening.
