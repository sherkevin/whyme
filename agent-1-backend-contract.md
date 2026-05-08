# Agent 1 Backend Contract - PRD10

## Authority

`docs/01-prd/PRD10.md` is the only product authority for backend behavior. Existing AgentOS code can be reused, but it must not rename, narrow, or reshape PRD10 requirements.

## Canonical Backend Surface

All PRD10 product APIs converge on `/api/v1`.

P0 API groups:

- Auth/User: `/auth/*`, `/me`
- Today: `/today`
- Capture: `/capture/text`, `/capture/link`, `/capture/file/commit`
- Uploads: `/uploads/presign`
- Feed/Cards: `/feed`, `/cards/*`
- Knowledge Base: `/kb/overview`, `/kb/folders/*`, `/kb/documents/*`
- Jobs: `/jobs/{job_id}`
- Notifications: `/notifications/*`
- AI Chat: `/ai/conversations/*`
- Search: `/search`, `/search/suggestions`

P1 API groups:

- Insight/Reports
- Skills
- Garden
- Semantic index and richer embeddings

## Response Envelope

Every new PRD10 endpoint should use a consistent envelope.

Success:

```json
{
  "success": true,
  "data": {},
  "request_id": "req_xxx"
}
```

Paginated success:

```json
{
  "success": true,
  "data": {
    "items": [],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 0,
      "has_more": false
    }
  },
  "request_id": "req_xxx"
}
```

Error:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable message",
    "details": {}
  },
  "request_id": "req_xxx"
}
```

Canonical error codes:

- `UNAUTHORIZED`
- `FORBIDDEN`
- `NOT_FOUND`
- `VALIDATION_ERROR`
- `RATE_LIMITED`
- `INTERNAL_ERROR`
- `AI_PROVIDER_ERROR`
- `JOB_FAILED`

## Data And Identity Rules

- All `/api/v1/*` product APIs require authenticated identity unless explicitly public.
- All user-owned data must be filtered by `user_id`.
- All workspace-scoped data must include and filter by `workspace_id`.
- V1 defaults to personal workspace semantics. Keep `workspace_id` in storage and DTOs where PRD10 requires it, even if only one workspace is active.
- Deletion is soft delete by default.
- Empty list is a successful response with `items: []`, not an error.

## Chosen Backend Foundation

Use the async SQLAlchemy path as canonical:

- Keep: `src/agent_os/db/base.py`
- Keep: `src/agent_os/auth/*`
- Deprecate for PRD10 APIs: `src/agent_os/db/session.py`
- Deprecate for PRD10 APIs: `src/agent_os/server/auth.py`

Rationale:

- PRD10 requires real backend persistence, user isolation, async jobs, and scalable API behavior.
- Current `db/base.py` already matches FastAPI async dependency style used by most modern routers.
- Current `auth/*` already has DB-backed users, JWT utilities, schemas, email code flow, and garden stats integration.
- `server/auth.py` is file-backed and creates a separate user/token universe, which would cause identity drift.

## Router Boundary

New PRD10 endpoints should live in feature routers, not in the monolithic lower half of `src/agent_os/server/app.py`.

Preferred shape:

- `src/agent_os/common/*` for shared response/error/pagination helpers.
- `src/agent_os/capture/router.py`
- `src/agent_os/feed/router.py`
- `src/agent_os/kb/router.py`
- `src/agent_os/jobs/router.py`
- `src/agent_os/notifications/router.py`
- `src/agent_os/ai/router.py`
- `src/agent_os/search_engine/router.py` may be adapted if it can match PRD10.

`src/agent_os/server/app.py` should eventually only create the app, install middleware, initialize DB, include routers, keep existing WebSocket IDE routes if still needed, and serve legacy static pages.

## Persistence Strategy

Reuse with care:

- `auth.models.User`: canonical user model, but settings/preference may need a dedicated model or structured fields.
- `items.models.Workspace`: reusable personal workspace root.
- `items.models.Item`: reusable for generic captured/card-like content only if DTO mapping stays PRD10-compliant.
- `knowledge.models.Card`: reusable if extended to PRD10 card fields or wrapped by a DTO.
- `tasks.models.Task`: currently integer user IDs conflict with UUID user model; do not extend until reconciled.
- `search_engine.models.SearchIndex`: reusable as `SearchDocument` equivalent if object types and user/workspace fields are added or enforced through metadata.
- `search_engine.models.IngestionJob`: reusable for ingestion-specific jobs, but PRD10 probably needs a general `Job` abstraction.
- `garden.models.KnowledgeCardLink` and `DailyInsight`: reusable for Garden MVP.
- `stage3.models.Skill`: candidate for PRD10 Skills, pending Agent 3 mapping.

Likely missing canonical PRD10 models:

- `UserPreference`
- `Source`
- `Folder`
- `Document`
- `Chunk`
- `Notification`
- `Message` or PRD10-compatible conversation message
- `SkillRun`
- General `Job`

## Job Contract

Long-running operations must return a job immediately.

Allowed statuses:

- `queued`
- `running`
- `completed`
- `failed`
- `canceled`

Minimum job fields:

- `id`
- `user_id`
- `workspace_id`
- `job_type`
- `status`
- `progress`
- `input`
- `output`
- `error`
- `created_at`
- `updated_at`

Agent 2 owns Capture/KB jobs. Agent 3 owns AI/Skill jobs. Agent 1 owns the shared model decision.

## Test Strategy

Do not use broken legacy tests as the main acceptance path. Add PRD10-focused tests under new files:

- `tests/integration/api/test_prd10_auth_user_api.py`
- `tests/integration/api/test_prd10_capture_api.py`
- `tests/integration/api/test_prd10_feed_api.py`
- `tests/integration/api/test_prd10_kb_api.py`
- `tests/integration/api/test_prd10_jobs_notifications_api.py`
- `tests/integration/api/test_prd10_ai_api.py`
- `tests/integration/api/test_prd10_search_api.py`
- `tests/integration/api/test_prd10_skills_garden_api.py`

Acceptance requires:

- Targeted tests for the slice pass.
- `pytest --collect-only -q -p no:cacheprovider` improves or blockers are explicitly documented.
- New endpoints return PRD10 envelope format.
- User isolation and empty-state behavior are tested.

## Parallel Work Rules

- Agent 2 may start mapping product data models immediately.
- Agent 3 may start mapping intelligence models immediately.
- Agent 2/3 should wait for Agent 1's shared `common` helpers before finalizing public endpoint responses.
- If a model is shared between Agent 2 and Agent 3, record the proposed owner in the relevant todo before editing.

