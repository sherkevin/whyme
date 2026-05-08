# Agent 1 Todo - Coordinator And Backend Foundation

## Role Note

Agent 1 is the current coordinator and shared backend foundation owner. Main responsibility: keep the backend implementation coherent while Agent 2 and Agent 3 work in parallel. Own shared contracts, database/auth/session cleanup, integration decisions, and the final backend acceptance loop.

## Current Status

- `done` - V1 acceptance pass complete. PRD10 backend MVP is delivered
  end-to-end across Agent 1/2/3 ownership and bound to the Mydow Web
  frontend bundle. **123 PRD10 integration tests pass** across product-data,
  intelligence, frontend binding, app wiring, observability, and E2E smoke;
  `pytest --collect-only` exits 0 with 1377 tests collected. Frontend (`Mydow_Web_Frontend_Complete_
  Package.zip`) is deployed at `static/mydow/` and bound to the live API
  via `static/mydow/mydow-api.js`. Chrome MCP browser integration passed
  against a live uvicorn server in Milestone 12 after adding canonical
  `/api/v1/me`. Cleanup pass recorded in `agent-progress-report.md`
  Milestone 10.

## Progress Sync (read first)

- `open` - Read `agent-progress-report.md` before triaging tasks below.
  - It is the rolling change log written by the worker covering Agent 1 / 2 / 3 in parallel.
  - Newest milestone is at the top; check it before assuming a task is still pending.
  - When you (Engineer 1) sign off on a milestone, append an entry under that milestone or update its status to `accepted`.

## Mission

Build the foundation that lets PRD10 backend slices land without each engineer inventing separate conventions.

## Tasks

1. `done` - Freeze the PRD10 backend contract baseline.
   - Read `docs/01-prd/PRD10.md` sections 1-6, 20, 24-30.
   - Produced `agent-1-backend-contract.md`.
   - Confirm canonical API base is `/api/v1`.
   - Confirm response envelope, pagination, error format, auth, soft delete, and job-state conventions.

2. `done` - Decide the reusable backend architecture boundary.
   - Inspect `src/agent_os/server/app.py`, `src/agent_os/db/base.py`, `src/agent_os/db/session.py`, `src/agent_os/auth/*`, `src/agent_os/server/auth.py`.
   - Choose one DB/session path for PRD10 work: `src/agent_os/db/base.py`.
   - Choose one auth path for PRD10 work: `src/agent_os/auth/*`.
   - Deprecated for PRD10 APIs: `src/agent_os/db/session.py` and `src/agent_os/server/auth.py`.

3. `done` - Create the shared PRD10 API utility layer.
   - Candidate files:
     - `src/agent_os/common/response.py`
     - `src/agent_os/common/errors.py`
     - `src/agent_os/common/pagination.py`
   - Implement response helpers for success, paginated success, and typed errors.
   - Add request ID support usable by routers.
   - Add unit tests for envelope helpers.

4. `done` - Stabilize database imports and test collection blockers.
   - All 18 remaining collection errors resolved as of Milestone 2 in `agent-progress-report.md`.
   - Now: 1252 tests collected, 0 errors, exit 0 from `pytest --collect-only -q -p no:cacheprovider`.
   - Resolution summary:
     - `agent_os.agent.Agent` export mismatch — fixed (export `agent_os.agent_legacy.Agent`).
     - Missing `agent_os.search` package — added stub package (`keyword_search`, `hybrid_search`) raising NotImplementedError.
     - Missing `InboxItem` in `agent_os.knowledge.models` — added PRD10-shape ORM model.
     - Missing `UserSettings` in `agent_os.auth.models` — added ORM model (canonical settings still on `User.settings` JSON).
     - Missing `async_session_maker` in `agent_os.db.base` — fixed with lazy callable proxy.
     - FastAPI/Pydantic `FieldInfo.in_` compat — fixed earlier in auth router refactor.
     - Missing `agent_os.main` and `tests.test_app` — created shims re-exporting the canonical FastAPI app.
     - `tests/unit/auth/test_verification.py` missing `patch` import — added.
   - Note: Legacy tests are now collectable, not necessarily passing. New PRD10 tests under `tests/integration/api/test_prd10_*.py` remain the green-path contract.

5. `done` - Define PRD10 persistence model strategy.
   - Crosswalk and ownership table delivered in `agent-progress-report.md` (Milestone 3).
   - Reuse: `User`, `Workspace`, `UserSettings` (M2 add), `InboxItem` (M2 add), `Card` (extend), `Skill` (extend), `SearchIndex` (extend), `KnowledgeCardLink`, `DailyInsight` (daily/weekly).
   - New tables to be added in subsequent slices:
     - `Job` (general, Agent 1) → `src/agent_os/jobs/models.py`
     - `Notification` (Agent 2) → `src/agent_os/notifications/models.py`
     - `Source` (Agent 2) → `src/agent_os/sources/models.py`
     - `Folder`, `Document`, `Chunk` (Agent 2) → `src/agent_os/kb/models.py`
     - `AIConversation`, `AIMessage` (Agent 3) → `src/agent_os/ai/models.py`
     - `SkillRun` (Agent 3) → `src/agent_os/skills/models.py`
     - PRD10 Task (UUID user_id, alongside legacy `tasks.Task`) → `src/agent_os/tasks/models.py`

6. `done` - Own integration branch hygiene.
   - Keep unrelated generated files out of commits.
   - Watch for conflicts between Agent 2 and Agent 3 model/router additions.
   - Ensure routers included by `src/agent_os/server/app.py` do not duplicate paths.

7. `done` - Final backend acceptance pass (Milestones 6 and 10).
   - Targeted tests from all three agents:
    - Complete PRD10 matrix: product-data, intelligence, frontend binding,
      app wiring, observability, model tests, and E2E smoke.
    - Total 123/123 PRD10 integration tests green.
   - `pytest --collect-only -q -p no:cacheprovider` → 1377 tests
     collected, exit 0 (up from 1252 in Milestone 2).
   - Frontend bundle from `Mydow_Web_Frontend_Complete_Package.zip`
     deployed at `static/mydow/` and mounted at `/mydow` in
     `agent_os.server.app`. The bundled `mydow-api.js` covers every
     PRD10 path the handoff doc lists; binding tests assert literal
     presence of each path.
   - Remaining PRD10 gaps (carry-over to P1, not blockers for V1):
     - SSE streaming for AI messages (`/messages/{id}/stream`).
     - Background scheduler for worker execution; `process_job_once` exists
       and is covered for AI-output materialization jobs.
     - Richer AI context retrieval / citation ranking.
     - Legacy `tasks.models.Task.user_id` Integer→UUID reconciliation.
     - Legacy `tests/conftest.py` teardown hygiene
       (drop with `checkfirst=True`, swallow "no such table" on cleanup).

8. `done` - Coordinate Agent 4 frontend replacement acceptance.
   - Created `agent-4-todo.md`.
   - Created `agent-4-initialization.md` as the startup prompt/instructions
     for the engineer.
   - Agent 4 owns the Mydow UI replacement lane: audit old frontend/static
     entrypoints, bind real DOM actions to PRD10 APIs, and add UI-level
     acceptance tests.
   - Agent 3 keeps backend/frontend smoke binding and API liveness tests.
   - Agent 1 owns acceptance criteria and route/legacy UI decisions:
     older frontend/static entrypoints should either redirect to `/mydow`,
     remain legacy/dev-only, or be removed from user-facing navigation.
   - Initial Agent 1 route decision:
     - `/` redirects to `/mydow/` when the Mydow bundle exists.
     - `/legacy` preserves the previous AgentOS static index.
     - `/login.html`, `/project-wizard.html`, and `/static/*` remain
       legacy/dev-only until Agent 4 finishes the replacement map.
   - Accepted in Milestone 10:
     - `/mydow/` is canonical V1 UI.
     - Static DOM/API contract tests and ASGI backend liveness pass.
     - High-intent actions in `mydow-api.js` are bound to PRD10 APIs.
     - Browser-click persistence tests are a P1 hardening lane, not a V1 blocker.
   - Chrome MCP live-browser validation added in Milestone 12:
     - `/api/v1/me`, `/today`, `/capture/text`, `/feed`, `/kb/overview`,
       `/notifications/unread-count`, `/search`, `/ai/conversations`,
       `/messages`, `/skills`, and `/garden/overview` all returned 200/201
       through `window.MydowAPI`; console had no errors.

9. `done` - Make local DeepSeek development config usable.
   - Stored the secret-bearing local values in gitignored `.env.local`.
   - Added non-secret notes in `docs/11-deployment/deepseek-local-env.md`.
   - Updated config loading so `.env.local` overrides `.env`.
   - Updated LLM provider env resolution for `DEEPSEEK_API_KEY`,
     `DEEPSEEK_OPENAI_BASE_URL`, and `DEEPSEEK_MODEL`.
   - Set default config model to `deepseek-v4-flash`.
   - Verification: `python -m pytest tests/unit/test_config.py tests/unit/test_llm_provider.py -q` -> `16 passed`.

9. `open` - Review Agent 4 progress report and acknowledge handoff.
   - Agent 4 has reported four cross-cutting milestones in
     `agent-progress-report.md`:
     - **Milestone 8 · Agent 4 first UI action-binding slice — DONE**
     - **Milestone 9 · Agent 2 worker slices for AI-output materialization — DONE**
     - **Milestone 10 · Worker scheduler entry + AI-output notification — DONE**
     - **Milestone 11 · PRD10 worker loop wired into FastAPI startup — DONE**
     - **Milestone 12 · PRD10 V1 acceptance walk-through — DONE**
     - **Milestone 13 · Real LLM provider + AI streaming SSE wired — DONE**
   - Please review:
     - `agent-progress-report.md` Milestones 8–10 for delivery/test evidence.
     - `agent-4-todo.md` for the frontend replacement map and remaining UI
       binding backlog.
     - `agent-2-todo.md` tasks 10–12 for the worker materialization slices
       Agent 4 has been covering.
   - Latest evidence from Agent 4:
     - `python -m pytest tests/integration/api/test_prd10_frontend_binding.py -q -p no:cacheprovider` -> `13 passed`.
     - `python -m pytest tests/integration/api/prd10/test_prd10_jobs_notifications_api.py -q -p no:cacheprovider` -> `13 passed`.
     - `python -m pytest tests/integration/api/prd10/test_prd10_worker_loop.py -q -p no:cacheprovider` -> `4 passed`.
     - `python -m pytest tests/integration/api/test_prd10_v1_acceptance.py -q -p no:cacheprovider` -> `12 passed`.
     - Full PRD10 acceptance matrix (12 suites) -> `159 passed`.
   - Outstanding to be fully PRD10-compliant (Milestone 13 verdict — 5 left):
     1. ~~AI streaming SSE~~ — done in Milestone 13
        (`POST /api/v1/ai/conversations/{id}/messages/stream`).
     2. ~~Real LLM provider~~ — done in Milestone 13 (`AGENTOS_AI_LLM=on`).
     3. Embedding + semantic search (B-13).
     4. `/insights/*` endpoints (PRD10 §12).
     5. Browser-level UI tests (Playwright runner choice).
     6. Mock data seed script (PRD10 §25.3) — `scripts/seed_prd10.py`
        exists in repo; needs an Agent 4 review pass to confirm coverage.
     7. Auth UX inside the Mydow bundle.
   - Agent 4 is now requesting an Agent 1 decision on whether
     `process_pending_jobs` should be invoked from a startup loop or an
     external scheduler, and whether to extend the worker to materialize
     `capture_text` jobs as well.

## Decisions

- `done` - PRD10 is the only product requirement source.
- `done` - Frontend implementation is out of scope for the backend team except API contract compatibility.
- `done` - Existing code may be reused only when it helps PRD10.
- `done` - Canonical API base is `/api/v1`.
- `done` - New PRD10 endpoints must return the PRD10 response envelope documented in `agent-1-backend-contract.md`.
- `done` - Canonical DB dependency path is async SQLAlchemy in `src/agent_os/db/base.py`.
- `done` - Canonical auth path is DB/JWT auth in `src/agent_os/auth/*`.
- `done` - File-backed `src/agent_os/server/auth.py` and sync `src/agent_os/db/session.py` are legacy for PRD10.

## Dependencies For Other Agents

- Agent 2 can start model mapping immediately and should use `agent-1-backend-contract.md` for API/DB/auth rules.
- Agent 3 can start model mapping immediately and should use `agent-1-backend-contract.md` for API/DB/auth rules.
- Agent 2 and Agent 3 should wait for shared `src/agent_os/common/*` helpers before finalizing endpoint response formatting.
- Agent 4 should use `static/mydow/HANDOFF.md`, `static/mydow/mydow-api.js`, and
  `tests/integration/api/test_prd10_frontend_binding.py` as the starting point
  for UI-level frontend replacement acceptance.

## Notes / Blockers

- Product-data app wiring completed in Milestone 4 of `agent-progress-report.md`.
  - `src/agent_os/server/app.py` now includes PRD10 `capture`, `kb`, `jobs`, and `notifications` routers.
  - `RequestIdMiddleware` is installed.
  - PRD10 product-data HTTP/validation errors are enveloped without reshaping legacy APIs globally.
  - Duplicate `/api/v1/today` registration was removed by excluding `aggregation.router` from the canonical app.
  - Verification: `python -m pytest tests/integration/api/test_prd10_product_data_api.py -q` -> `5 passed`.
  - Verification: `python -m pytest --collect-only -q -p no:cacheprovider` -> `1291 tests collected`, exit `0`.
- Commander acceptance sweep completed in Milestone 6 of `agent-progress-report.md`.
  - Explicit PRD10 integration suite: `109 passed`.
  - Full collection: `1366 tests collected`, exit `0`.
- Remaining acceptance risks:
  - Real AI streaming / LLM provider wiring remains P1; current AI reply path is deterministic placeholder persistence.
  - Job worker materialization remains P1; endpoints create and expose `prd10_jobs`, while background execution is not yet implemented.
  - Legacy warnings remain (Pydantic V1-style config, FastAPI `on_event`, old app collection warnings).
  - Full legacy test execution is not claimed green; PRD10 acceptance currently rests on explicit PRD10 suite + full collect-only.
- Agent 4 lane opened in Milestone 7 of `agent-progress-report.md`.
  - Frontend standard: `Mydow_Web_Frontend_Complete_Package.zip`.
  - Deployed standard path: `/mydow`.
  - Agent 4 should expand from static/API smoke binding to real UI action binding.
  - Agent 1 implemented the first route decision: root `/` now points users
    to `/mydow/`, while `/legacy` serves the old AgentOS index.
- Local DeepSeek config is now wired:
  - `.env.local` is ignored by git and holds the actual API key.
  - `config.yaml` defaults to `deepseek-v4-flash`.
  - `LiteLLMProvider` can call DeepSeek's OpenAI-compatible endpoint with
    new model names.

- Historical: `pytest --collect-only -q -p no:cacheprovider` originally collected 913 tests and stopped with 26 collection errors before Milestones 2-4.
- The repository contains large old/test/generated areas: `src/aider`, `data/workspaces`, `tests/legacy`, and archived docs. Treat them as context, not PRD10 implementation boundaries.
- General job statuses are frozen as `queued`, `running`, `completed`, `failed`, `canceled`.
- New PRD10 endpoints should live in feature routers rather than adding more route logic to the monolithic body of `src/agent_os/server/app.py`.
- Added shared helpers under `src/agent_os/common/`.
- Verification: `python -m pytest "tests/unit/common/test_response.py" -q` -> `9 passed`.
- Import stabilization changed:
  - `src/agent_os/agent/__init__.py`
  - `src/agent_os/db/base.py`
  - `src/agent_os/auth/router.py`
- Historical Milestone 1 intermediate state: `pytest --collect-only -q -p no:cacheprovider` improved from 913 tests / 26 collection errors to 979 tests / 18 collection errors.
- Historical remaining collection errors at that point were mostly obsolete test references:
  - `tests.test_app` missing (old test app path).
  - `agent_os.main` missing (old app path).
  - `UserSettings` ORM model expected by old auth tests, while current canonical user settings are JSON on `auth.models.User`.
  - `InboxItem` expected in `knowledge.models`, while current inbox uses `items.Item`.
  - `agent_os.search.*` expected by old search tests, while current implementation is `agent_os.search_engine.*`.
  - `tests/unit/auth/test_verification.py` misses `patch` import.

