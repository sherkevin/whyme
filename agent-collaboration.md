# PRD10 Backend Collaboration Protocol

## Source Of Truth

- `docs/01-prd/PRD10.md` is the product source of truth.
- Existing code is reusable asset only. If current code conflicts with PRD10, PRD10 wins.
- Frontend is owned by another engineer outside this backend split. Do not change frontend files unless a backend contract requires a small compatibility note.

## Team Roles

- `agent-1`: coordinator and backend foundation owner. Owns architecture decisions, API contract, shared DB/auth/session conventions, and final integration.
- `agent-2`: product data domain owner. Owns Capture, Feed, Knowledge Base, Jobs, and Notifications backend.
- `agent-3`: intelligence domain owner. Owns AI Chat, Search, Skills, Garden, observability, and cross-module test strategy.
- `agent-4`: frontend replacement and end-to-end binding owner. Owns making `Mydow_Web_Frontend_Complete_Package.zip` the effective V1 frontend standard, deployed under `static/mydow/`, and proving real UI flows bind to PRD10 backend APIs.

## Todo Status Values

- `pending`: not started or waiting for a dependency.
- `open`: actively being worked or needs discussion.
- `done`: completed with code/tests/docs updated.

Do not invent other statuses.

## Communication Rules

- Each engineer updates only their own `agent-*-todo.md` status section unless explicitly coordinating a dependency.
- Use `Notes / Decisions / Blockers` in your own todo file to record findings.
- If a task needs another engineer, add a short dependency note with exact file/API names.
- Prefer small vertical slices that pass tests over broad rewrites.
- Preserve useful existing modules, but delete or bypass old paths when they conflict with PRD10 and are not part of the selected implementation.
- Frontend work should treat `Mydow_Web_Frontend_Complete_Package.zip` as the V1 UI standard. Older frontend/static surfaces are legacy unless Agent 1 explicitly keeps them as debug/dev views.

## Implementation Conventions

- API base should converge on `/api/v1`.
- All business APIs should use authenticated `user_id` isolation and `workspace_id` where PRD10 requires it.
- Responses should converge toward PRD10 envelopes:
  - Success: `{ "success": true, "data": ..., "request_id": "..." }`
  - Error: `{ "success": false, "error": { "code": "...", "message": "...", "details": ... }, "request_id": "..." }`
- Long-running work should return a job object and be queryable.
- Add focused tests with every backend slice. If a legacy test is obsolete, mark the replacement path in notes before changing it.

## Files To Read First

- `docs/01-prd/PRD10.md`
- `README.md`
- `pyproject.toml`
- `config.yaml`
- `src/agent_os/server/app.py`
- `src/agent_os/db/base.py`
- `src/agent_os/auth/router.py`
- `src/agent_os/items/models.py`
- `src/agent_os/search_engine/models.py`
- `static/mydow/HANDOFF.md`
- `static/mydow/mydow-api.js`
- `tests/integration/api/test_prd10_frontend_binding.py`
- `tests/README.md`

