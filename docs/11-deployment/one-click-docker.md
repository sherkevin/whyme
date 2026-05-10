# One-command Docker runbook

For Windows users, run from `cmd.exe` at the repository root:

```cmd
run-mydow.cmd
```

The launcher does the full local delivery path:

1. Checks Docker Desktop is running.
2. Generates `.env.docker.local` with local secrets when the file does not exist.
3. Copies LLM settings from process environment or `.env`, preferring
   `DEEPSEEK_API_KEY` / `DEEPSEEK_OPENAI_BASE_URL` and defaulting the model to
   `deepseek-v4-flash`.
4. Builds and starts `app`, `postgres`, and `redis` from
   `docker-compose.prd10.yml`.
5. Waits for `http://localhost:8000/health`.
6. Seeds demo data into the persisted app database.
7. Opens `http://localhost:8000/mydow/biz_v14/`.

Useful variants:

```cmd
run-mydow.cmd -NoOpen
run-mydow.cmd -NoBuild
run-mydow.cmd -NoSeed
run-mydow.cmd -Port 8010
```

Stop the stack:

```cmd
docker compose --env-file .env.docker.local -f docker-compose.prd10.yml down
```

Data is persisted in Docker volumes. The default app database is the real
Postgres service in the stack
(`postgresql+asyncpg://agentos:agentos@postgres:5432/agentos_db`), and Redis is
used by the backend services that need it. SQLite is now only a deliberate
local-development override when `DATABASE_URL` is explicitly set to a sqlite
URL.

Before a 50-user internal beta, run the capacity gate in
[`internal-beta-50.md`](internal-beta-50.md), especially
`python scripts\prd10_beta_load_check.py --users 50 --concurrency 10 --include-ai --include-skills`.
