# Agent 3 Todo - AI Chat, Search, Skills, Garden, Observability

## Initialization Instruction

You are Agent 3, owner of the PRD10 intelligence backend. Read `agent-collaboration.md` first. Then read `docs/01-prd/PRD10.md`, focusing on sections 4.5, 5.11-5.15, 11-13, 17-19, 20, 23-30.

Do not work on frontend. Your goal is to make AI/search/skills/garden capabilities usable through PRD10-aligned backend APIs, while reusing existing `AiderAgent`, `search_engine`, `stage3`, `garden`, and `skills` assets only where they fit.

## Current Status

- `done` - Agent 3 PRD10 intelligence backend MVP shipped. All routers wired
  into `agent_os.server.app`, observability + RequestId middleware in place.
  Focused tests cover model layer, every router, app wiring, and access logs;
  total **59/59** PRD10 tests pass and `pytest --collect-only` still exits 0
  (1351 tests collected). See `agent-progress-report.md` Milestones 4–5.

## Mission

Build the intelligence layer that supports Mydow AI conversation, global search, skills execution, garden overview, and observability for backend experiments.

## Tasks

1. `done` - Map PRD10 intelligence models to existing code.
   - Reuse decisions implemented (see `agent-progress-report.md` Milestones 3–4):
     - `Conversation` / `Message` → **NEW** `agent_os.ai.models.AIConversation` /
       `AIMessage` (`ai_conversations`, `ai_messages`). Legacy
       `conversations.Conversation` is left in place for the Aider WebSocket
       path; PRD10 endpoints will not write through it.
     - `ToolCall` / `Citation` → JSON columns on `AIMessage.tool_calls`,
       `AIMessage.citations` (PRD10 §5.12).
     - `Skill` → reuse `stage3.models.Skill`, **extended** with PRD10 §5.13
       display fields (`icon`, `status`, `usage_count`, `is_installed_default`,
       `input_schema`, `output_schema`) plus a `to_prd10_dict()` serializer.
     - `SkillRun` → **NEW** `agent_os.skills.runs.SkillRun` (table
       `skill_runs`) referencing `prd10_jobs.id` (Agent 1's general `Job`).
     - `SearchDocument` → reuse `search_engine.models.SearchIndex`, **extended**
       to PRD10 §5.14 shape: nullable `user_id` / `workspace_id` / `summary` /
       `embedding_id`, relaxed `item_type` constraint to accept the PRD10
       object_type set (`card, document, folder, task, conversation, message,
       skill, insight`) plus the legacy ingestion types, added composite
       index `(user_id, item_type, updated_at)` per PRD10 §21, and
       `object_type` / `object_id` properties + `to_prd10_dict()`.
     - `IngestionJob` → kept ingestion-specific in `search_engine.models`;
       general PRD10 jobs use `agent_os.jobs.models.Job` (Agent 1).
     - `GardenNode` / `GardenEdge` → reuse `garden.models.KnowledgeCardLink`
       for edges; nodes are derived from cards/folders (not yet wired into a
       router slice).

2. `done` - Implement PRD10 AI conversation APIs.
   - Delivered: `GET/POST /api/v1/ai/conversations`,
     `GET /api/v1/ai/conversations/{id}`,
     `POST /api/v1/ai/conversations/{id}/messages` (synchronous placeholder
     assistant reply for the MVP; streaming is P1).
   - Persists user message, assistant message, and a `Job(job_type=ai_chat)`
     so the §16 long-running-operation contract is honored.
   - `citations` / `tool_calls` / `attachments` are first-class fields on
     `AIMessage`, even when empty in the MVP.
   - Tests: `tests/integration/api/test_prd10_ai_api.py` 14/14 passing.

3. `done` - Define AI context retrieval boundary.
   - Implemented minimal DB-backed retrieval in `agent_os.ai.router`.
   - `AIConversation.context_scope` and message-level
     `MessageSend.context_scope` now resolve explicit `document_ids`, folder
     metadata hints, query matches, or recent rows from `SearchIndex`.
   - Conversation detail returns `related_context`.
   - `POST /messages` echoes `related_context` and stores citation-ready
     entries on the placeholder assistant message.
   - Tests added in `tests/integration/api/test_prd10_ai_api.py`.

4. `done` (Job-only MVP) - Implement save-AI-output endpoints.
   - Delivered: `POST /api/v1/ai/messages/{id}/save-to-kb` and
     `POST /api/v1/ai/messages/{id}/create-tasks` enqueue a `Job` row
     (`parse_file` and `generate_report` job_types; the consumer worker
     branches on `input.kind`).
   - Real ``kb_documents`` / ``prd10_tasks`` writes still live in Agent 2's
     pipeline. The Job contract is testable end-to-end today.

5. `done` - Implement Global Search API.
   - Delivered: `GET /api/v1/search` (paginated PRD10 envelope, object_type
     filter, user-scoped with legacy un-owned rows still visible) and
     `GET /api/v1/search/suggestions` (title prefix match).
   - Reuses `SearchIndex.to_prd10_dict()` for the result item shape.
   - Tests: `tests/integration/api/test_prd10_search_api.py` 7/7 passing.

6. `open` - Repair current search package confusion.
   - Current tests reference missing `agent_os.search.*`. Agent 1 already added
     a `NotImplementedError`-raising shim package (`src/agent_os/search/`)
     during Milestone 2 to keep `pytest --collect-only` clean.
   - Next decision (Agent 3 owns): the PRD10 `/api/v1/search` router should
     live in a fresh `agent_os.search_engine.router` slice and **not**
     resurrect a second implementation under `agent_os.search`.
   - Do not create a second real search implementation.

7. `done` - Implement Skills list/run MVP.
   - Delivered: `GET /api/v1/skills` (category/keyword/status filters,
     usage_count-DESC ordering), `GET /api/v1/skills/{id}` (PRD10 §5.13 DTO),
     and `POST /api/v1/skills/{id}/run` (writes `Job(job_type=skill_run)` +
     `SkillRun(status=queued)`, increments `Skill.usage_count`).
   - Tests: `tests/integration/api/test_prd10_skills_api.py` 12/12 passing.

8. `done` - Implement Garden overview/graph MVP.
   - Delivered: `GET /api/v1/garden/overview` (node/edge/strong-edge counts
     scoped to the user's cards, top topics from `Card.tags`, recent
     `DailyInsight`) and `GET /api/v1/garden/graph` (cards-as-nodes with
     `KnowledgeCardLink` edges, range/topic/depth/limit query params).
   - Empty graph is a successful empty payload.
   - Tests: `tests/integration/api/test_prd10_garden_api.py` 7/7 passing.

9. `done` - Add observability for PRD10 APIs.
   - Delivered: `agent_os.common.middleware.Prd10AccessLogMiddleware`
     emits a single structured log record per PRD10 request with
     `request_id` / `method` / `path` / `status_code` / `duration_ms` /
     `client_host`. WARN for 5xx, INFO for 2xx/4xx.
   - Mounted in `agent_os.server.app` together with `RequestIdMiddleware`.
   - Tests: `tests/integration/api/test_prd10_observability.py` 3/3 passing.

10. `done` - Add focused tests.
    - All under `tests/integration/api/test_prd10_*.py`:
      - `test_prd10_models_intelligence.py` — 10/10
      - `test_prd10_search_api.py` — 7/7
      - `test_prd10_ai_api.py` — 14/14
      - `test_prd10_skills_api.py` — 12/12
      - `test_prd10_garden_api.py` — 7/7
      - `test_prd10_app_wiring.py` — 6/6 (router mounting, X-Request-ID
        round-trip, PRD10 envelope on 404 for the intelligence surface)
      - `test_prd10_observability.py` — 3/3
    - Total: Agent 3 PRD10 tests pass; after context-boundary tests and
      frontend binding updates, the expanded PRD10 suite is **118 passed**.
    - `pytest --collect-only -q -p no:cacheprovider` exits 0 with 1351 tests
      collected (up from 1252 before this slice).

## Decisions To Record

- `done` - PRD10 AI Chat is a **separate** persistence path through
  `agent_os.ai` (`ai_conversations` + `ai_messages`). The legacy
  `conversations.Conversation` (Aider WebSocket) is preserved but not used by
  PRD10 endpoints. Streaming will be added on the same persistence layer.
- `done` - `stage3.Skill` is the canonical PRD10 Skill model (extended with
  PRD10 display fields). The Pydantic `agent_os.skills.models.Skill`
  remains a runtime representation for the Coze-style skill loader and is
  not persisted by PRD10 endpoints.
- `done` - Garden graph in V1 is derived from
  `garden.models.KnowledgeCardLink`. `items.models.GraphEdge` continues to
  serve PRD4 Item graphs but is not exposed through PRD10 `/garden/*`.

## Dependencies

- Agent 1: shared response helpers, auth, DB/session convention.
- Agent 2: KB document/card/chunk models and job/notification model.

## Notes / Blockers

- Current `AiderAgent` is optimized for coding workspaces. PRD10 Mydow AI uses
  a separate persistence path and now has a minimal `SearchIndex`-backed
  context boundary; real LLM streaming remains P1.
- Current `search_engine.IngestionJob` is source-ingestion specific. If Agent 2 generalizes jobs, align SkillRun and AI jobs to that model.
- `tests/conftest.py` (Agent 1 owned) creates PRD4 tables on
  `sqlite+aiosqlite:///./test.db`. The existing `postgresql.UUID(as_uuid=True)`
  columns can't render on SQLite by default, so any fixture that touches
  `Workspace.__table__.create()` raises `sqlalchemy.exc.CompileError: ... can't
  render element of type UUID`. Agent 3 sidesteps this by adding
  `src/agent_os/db/sqlite_compat.py` (a `@compiles` rule that renders
  `postgresql.UUID` as `CHAR(32)` only on the SQLite dialect) and importing
  it from PRD10-focused tests. This patch is opt-in and does **not** change
  the canonical PostgreSQL schema. Coordinate with Agent 1 if the global
  conftest should also import it to unblock the legacy SQLite tests.

