# One-command Docker runbook

For Windows users, run from `cmd.exe` at the repository root:

```cmd
run-mydow.cmd
```

The launcher does the full local delivery path:

1. Checks Docker Desktop is running.
2. Generates `.env.docker.local` with local secrets when the file does not exist.
3. Copies LLM settings from process environment or `.env` when `API_KEY`,
   `API_BASE`, `MODEL`, or `MODEL_FALLBACK` are present.
4. Builds and starts `app`, `postgres`, and `redis` from
   `docker-compose.prd10.yml`.
5. Waits for `http://localhost:8000/health`.
6. Seeds demo data into the persisted app database.
7. Opens `http://localhost:8000/mydow/`.

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

Data is persisted in Docker volumes. The default app database is a real
persistent SQLite database at `/app/data/mydow.db`; Postgres and Redis are
started with the stack for deployment parity and services that need them.
