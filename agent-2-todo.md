# Agent 2 Todo - Capture, Feed, Knowledge Base, Jobs, Notifications

## Initialization Instruction

You are Agent 2, owner of the PRD10 product data backend. Read `agent-collaboration.md` first. Then read `docs/01-prd/PRD10.md`, focusing on sections 4, 5.3-5.10, 7-10, 14-16, 20, 24-30.

Do not work on frontend. Your goal is to make the product data loop real: capture input, process it into cards/documents/searchable records, show feed and knowledge base data, expose job state, and generate notifications.

## Current Status

- `done` - Agent 2 PRD10 product-data backend MVP is shipped end-to-end. All
  routers (capture, feed, KB, jobs, notifications, today) are wired in
  `agent_os.server.app`. Both the dedicated test directory
  `tests/integration/api/prd10/` and the root-level
  `test_prd10_product_data_api.py` are green. Agent 4 has covered the first
  worker materialization slices (`ai_message_to_kb`, `ai_message_to_tasks`).
  This update adds PRD10 §8.5/§8.6 (`GET/PATCH /api/v1/inbox`) and §15 failure
  notifications (`upload_failed` / `job_failed` via the
  `simulate_failure` pipeline hook).

### Test status

| File | Result |
|---|---|
| `tests/integration/api/prd10/test_prd10_capture_api.py` | 7 passed |
| `tests/integration/api/prd10/test_prd10_kb_api.py` | passed |
| `tests/integration/api/prd10/test_prd10_jobs_notifications_api.py` | passed |
| `tests/integration/api/prd10/test_prd10_feed_api.py` | 7 passed |
| `tests/integration/api/prd10/test_prd10_today_api.py` | 4 passed |
| `tests/integration/api/prd10/test_prd10_inbox_api.py` (new) | 9 passed |
| `tests/integration/api/prd10/test_prd10_failure_paths_api.py` (new) | 7 passed |
| `tests/integration/api/test_prd10_product_data_api.py` | passed |

**Dual-engine green stamp** (latest, 2026-05-05):

| Engine | Tests | Result | Time |
|---|---|---|---|
| SQLite (in-memory) | 71 (excludes Agent 1/3's `test_prd10_sse_notifications_api.py` long-poll) | **71 passed** | 21.96s |
| Postgres 16 (`postgres:16-alpine`, Docker `whyme-prd10-pg:5433`) | 71 (same exclusion) | **71 passed** | 125.52s |

The single excluded file (`test_prd10_sse_notifications_api.py`) is owned by
Agent 1/3 and exercises an SSE `httpx` long-poll path that hangs on Windows;
that issue is independent of the Agent 2 product-data domain.

**End-to-end smoke (real uvicorn) green stamp**:
`scripts/smoke_prd10.py` boots a real FastAPI server, walks the V1 critical
path (auth.register → capture.text → today → feed → uploads.presign+PUT+raw
→ capture.file.commit → kb.overview/folders/documents → inbox.list/patch →
notifications.unread_count/list/read_all). Latest run: **16/16 ok**, report
at `tests/integration/api/prd10/smoke_run.json`.

Zero failures, zero skips, zero regressions across both engines or in the
end-to-end smoke.

Pre-existing failures in `tests/integration/api/test_search_api_simple.py`
are unrelated (the legacy `agent_os.search.keyword_search` raises
`NotImplementedError` by design).

### Frontend handoff

- Delivery doc: `docs/agent-2-delivery.md` (env vars, request/response
  envelope, critical-path API recipes, error-code table).
- Demo data: `python scripts/seed_prd10.py` materializes 6 folders / 20
  documents / 30 cards / 5 manual tasks / 5 notifications under
  `demo@whyme.local`.
- Local upload storage backs PRD10 §22.2; production swaps the
  ``UploadStorage`` class for an S3 / R2 / OSS adapter without API change.

### How to run against Docker Postgres 16

```powershell
docker run -d --name whyme-prd10-pg `
    -e POSTGRES_USER=agentos -e POSTGRES_PASSWORD=agentos `
    -e POSTGRES_DB=agentos_db `
    -p 5433:5432 postgres:16-alpine

# Reset schema between runs (FK ordering means create_all needs a clean slate):
docker exec whyme-prd10-pg psql -U agentos -d agentos_db -c `
    "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO agentos;"

$env:PYTHONPATH = (Resolve-Path .\src).Path
$env:TEST_DATABASE_URL = "postgresql+asyncpg://agentos:agentos@localhost:5433/agentos_db"
pytest tests/integration/api/prd10/ -q -p no:cacheprovider
```

## Mission

Implement PRD10's non-AI product data backbone while reusing current `items`, `knowledge`, `tasks`, and `search_engine` assets where they fit.

## Decisions Recorded (V1)

- Workspace: PRD10 DTOs only expose `user_id`. DB tables keep `workspace_id` (nullable) for future multi-workspace, populated from `user.default_workspace_id` when available. Backend filters always include `user_id`. PRD10 endpoints never require `workspace_id` query parameter.
- `InboxItem`: PRD10 §5.3 needs `processing_status / priority / source_id / target_folder_id / auto_process` etc., which the legacy `Item` model does not support cleanly. New dedicated table `prd10_inbox_items` lives in `agent_os/inbox/prd10_models.py`; legacy `inbox/router.py` (Item-based) stays untouched for back-compat but is **not** the V1 PRD10 path.
- `Source`: use `agent_os/sources/models.py::Source` (`prd10_sources`). All Capture endpoints write through it.
- `Card`: continue using `agent_os/knowledge/models.py::Card` extended via DTO mapping. Required PRD10 fields not on the table (`summary`, `content_type`, `cover_url`, `is_favorite`, `is_archived`, `entities`, `visibility`, `inbox_item_id`, `folder_id`) will be added in a later slice; for V1 they default in DTO. **Action**: extend the table once Feed slice ships (separate todo `t8b-card-fields`).
- `Folder/Document/Chunk`: use Agent 1's new `agent_os/kb/models.py` tables (`kb_folders`, `kb_documents`, `kb_chunks`).
- `Task`: integer-`user_id` legacy table conflicts with UUID `User`. Out of Agent 2 V1 scope; PRD10 `/today` will treat tasks as empty list until Agent 1 reconciles.
- `Insight`: Agent 3 owns model and DTO; Agent 2 will only echo `insight_preview` in `/today` once Agent 3 publishes it. Until then, return the empty preview block.
- `IngestionJob` / `Job`: PRD10 `/api/v1/jobs/{id}` always reads `agent_os/jobs/models.py::Job` (`prd10_jobs`). `search_engine.IngestionJob` is internal to crawler/parsers and stays private.
- `Notification`: use `agent_os/notifications/models.py::Notification` (`prd10_notifications`). Capture and Job state changes write rows here.

## Task Map

1. `done` - Map PRD10 product data models to existing code. (See "Decisions Recorded" above. Source/Folder/Document/Chunk/Job/Notification tables registered in `db.base.init_db`.)

2. `done` - Add PRD10 `InboxItem` model + minimal CRUD. Implemented in
   `src/agent_os/inbox/prd10_models.py` (table `prd10_inbox_items`),
   registered in `db.base.init_db`.

3. `done` - Implement Capture endpoints (`/api/v1/capture/text`, `/link`,
   `/uploads/presign`, `/capture/file/commit`) under
   `src/agent_os/capture/router.py`. Long-running parsing writes through
   `prd10_jobs`. Tests: `prd10/test_prd10_capture_api.py` 7/7.

4. `done` - Implement Feed/Card endpoints under `src/agent_os/feed/router.py`
   (GET /feed with view/type/tag/date_range/sort/pagination, GET/POST/PATCH/
   DELETE /cards/{id}, POST /cards/{id}/favorite). The Card model now
   carries the §5.5 fields PRD10 needs (summary, content_type, cover_url,
   is_favorite, is_archived, entities, visibility, folder_id, inbox_item_id,
   source_id, deleted_at). Tests: `prd10/test_prd10_feed_api.py` passing.

5. `done` - Implement Knowledge Base endpoints under
   `src/agent_os/kb/router.py` (overview, folders CRUD, documents CRUD,
   move). Tests: `prd10/test_prd10_kb_api.py` 10/10.

6. `done` - Implement Jobs API under `src/agent_os/jobs/router.py`
   (`GET /api/v1/jobs/{id}`, `POST /api/v1/jobs/{id}/cancel`). Tests:
   `prd10/test_prd10_jobs_notifications_api.py` passing.

7. `done` - Implement Notifications API under
   `src/agent_os/notifications/router.py` (unread-count, list,
   `/{id}/read`, `/read-all`). Tests passing in the same file as 6.

8. `done` - Reshape `GET /api/v1/today` per PRD10 §7.1. Implemented in
   `src/agent_os/today/prd10_router.py`, mounted before the legacy
   `today_router` so PRD10 wins. Tests:
   `prd10/test_prd10_today_api.py` passing.

9. `done` - Add focused integration tests under
   `tests/integration/api/prd10/` (5 files) plus the umbrella
   `tests/integration/api/test_prd10_product_data_api.py`. Total: 40/40
   Agent 2 PRD10 tests pass.

10. `done` - First queued job materialization slice (Agent 4 covering Agent 2 follow-up).
   - Implemented `agent_os.jobs.service.process_job_once`.
   - Supported `Job(job_type=parse_file, input.kind=ai_message_to_kb)`.
   - Materializes queued AI assistant output into:
     - `kb_documents` (`Document(status=ready, document_type=note)`)
     - `kb_chunks` (single chunk for the saved AI output)
   - Marks the job `completed` with `output.document_id` / `output.chunk_count`.
   - Empty content marks the job `failed` with `VALIDATION_ERROR`.
   - Tests added in `tests/integration/api/prd10/test_prd10_jobs_notifications_api.py`.

13. `done` - PRD10 worker loop wired into FastAPI startup (Agent 4 covering Agent 2 follow-up).
   - New `agent_os.jobs.worker_loop` module owns the asyncio scheduler.
   - `agent_os.server.app` `startup_event` starts the loop when
     `AGENTOS_PRD10_WORKER` is not `off` / `0` / `false`; new
     `shutdown_event` stops it cooperatively.
   - Tests added in `tests/integration/api/prd10/test_prd10_worker_loop.py`.

12. `done` - AI output notifications + scheduler entry (Agent 4 covering Agent 2 follow-up).
   - `agent_os.jobs.service.process_job_once` now writes a
     `Notification(type=ai_output_saved)` after both worker kinds finish.
   - New `agent_os.jobs.service.process_pending_jobs(db, *, limit=25)`
     drains a small batch of queued PRD10 jobs (only ones with a
     registered materializer). Side-effect-free; safe to invoke from a
     startup loop or external scheduler.
   - Tests added in `tests/integration/api/prd10/test_prd10_jobs_notifications_api.py`:
     - `test_worker_writes_ai_output_saved_notification`
     - `test_process_pending_jobs_drains_supported_kinds`

11. `done` - Second queued job materialization slice (Agent 4 covering Agent 2 follow-up).
   - Extended `agent_os.jobs.service.process_job_once` with
     `Job(job_type=generate_report, input.kind=ai_message_to_tasks)` handling.
   - Materializes the AI-suggested task list into multiple
     `Prd10InboxItem(type=manual_task)` rows so that PRD10 §7.1 `/today.tasks`
     surfaces them via the existing manual-task read path. This avoids
     touching the legacy `tasks.models.Task` table while we wait on the
     UUID migration.
   - Marks the job `completed` with
     `output.task_count` / `output.inbox_item_ids`. Empty / title-less
     payloads mark the job `failed` with `VALIDATION_ERROR`.
   - Tests added in `tests/integration/api/prd10/test_prd10_jobs_notifications_api.py`
     (`test_process_ai_message_to_tasks_creates_manual_task_inbox_items`,
     `test_process_ai_message_to_tasks_fails_empty_payload`).

13. `done` - PRD10 §8.5/§8.6 Inbox listing and patching.
   - `GET /api/v1/inbox` (filter by `type` / `status` / `keyword`,
     paginated, ordered by `created_at desc`).
   - `PATCH /api/v1/inbox/{id}` (status / tags / priority / title /
     target_folder_id; per-user isolation; 404 for cross-user).
   - Implementation lives next to the capture endpoints in
     `agent_os/capture/router.py`; legacy `inbox/router.py` remains
     unchanged on its `/items` sub-paths.
   - Tests: `prd10/test_prd10_inbox_api.py` 9/9.

14. `done` - PRD10 §15 failure-path notifications.
   - `agent_os.capture.pipeline.simulate_failure` flips the V1 pseudo-worker
     to a `failed` outcome (Job.status=failed, Source.parse_status=failed,
     Document.status=failed) and writes the matching notification:
     `upload_failed` for file/image/audio/video, `job_failed` otherwise.
   - All three capture endpoints (`text` / `link` / `file/commit`) accept a
     test-only private payload field `_simulate_failure: <message>` so
     contract-level failure tests exist without a real worker.
   - Tests: `prd10/test_prd10_failure_paths_api.py` 7/7. Coverage includes
     job failure inspection via `GET /api/v1/jobs/{id}` and the
     `VALIDATION_ERROR` returned by `cancel` on a terminal job.

## Dependencies

- Agent 1: `common/response`, `common/middleware`, `common/errors` (already shipped). DB session conventions already adopted.
- Agent 3: `insight_preview` DTO for `/today` and `SearchDocument` writeback contract.

## Notes / Blockers

- `aggregation/router.py` declares a placeholder `/api/v1/today` that
  comments now point at `today/router.py` as the single source of truth.
  PRD10 traffic hits `today_prd10_router` first because it's mounted
  before `today_router` in `app.py`.
- `tasks.models.Task.user_id` is `Integer`, while PRD10 expects UUID.
  **V1 read path resolved**: `/today.tasks` now derives from
  `Prd10InboxItem(type=manual_task)` and `pending_task_count` counts
  non-archived/non-processed manual tasks. The legacy `tasks.models.Task`
  table is left untouched; reconciliation (UUID column migration vs. fully
  retiring it) remains an Agent 1 follow-up.
- `POST /api/v1/capture/text` accepts an optional `type` field. Defaults to
  `text`; `manual_task` (and any other §5.3 enum) is also accepted. This is
  the V1 way to create a task without a separate `/api/v1/tasks` endpoint.
- `RequestIdMiddleware` from `agent_os.common.middleware` is now installed
  in `app.py` (Milestone 5). `Prd10AccessLogMiddleware` was added by
  Agent 3 in the same milestone for structured access logging.
- PRD10 §5.5 Card fields are now persisted on `knowledge.models.Card`
  (`summary`, `cover_url`, `content_type`, `entities`, `is_favorite`,
  `is_archived`, `visibility`, `folder_id`, `inbox_item_id`, plus
  `deleted_at` for soft delete and `source_id`).
- `save-to-kb` and `create-tasks` from Agent 3's AI router enqueue
  `prd10_jobs` rows of type `parse_file` (kind=`ai_message_to_kb`) and
  `generate_report` (kind=`ai_message_to_tasks`) respectively. Both worker
  slices have now landed in `agent_os.jobs.service.process_job_once`:
  - `ai_message_to_kb` writes `kb_documents` + `kb_chunks`.
  - `ai_message_to_tasks` writes `Prd10InboxItem(type=manual_task)` rows.
  Once Agent 1 reconciles `tasks.models.Task` to UUID `user_id`, the
  task path can switch to the canonical `prd10_tasks` table.

### Inbox table merge proposal (needs Agent 1 arbitration)

Two inbox tables coexist:

- `inbox_items` (Agent 1, `agent_os/knowledge/models.py::InboxItem`) —
  minimal fields for legacy/test code only.
- `prd10_inbox_items` (Agent 2, `agent_os/inbox/prd10_models.py::Prd10InboxItem`)
  — full PRD10 §5.3 schema; the table all PRD10 capture/feed/today writes
  flow through.

Proposal:

1. Promote `prd10_inbox_items` to the canonical PRD10 inbox table.
2. Demote `inbox_items` to legacy. Either drop the model (preferred since
   no production data lives there yet) or keep it as a read-only mirror
   maintained by an adapter for back-compat.
3. Update `agent-1-backend-contract.md` to call out `prd10_inbox_items` as
   the canonical table.

Action: Agent 2 will not drop or alter `inbox_items` unilaterally. The
decision is reserved for Agent 1 / coordination.

### Search ownership

`/api/v1/search` and `/api/v1/search/suggestions` remain owned by Agent 3
(intelligence domain). Agent 2 will not implement these unless explicitly
delegated.
