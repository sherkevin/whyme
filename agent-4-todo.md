# Agent 4 Todo - Mydow Frontend Replacement And E2E Binding

## Role Note

Agent 4 owns the frontend acceptance lane for PRD10. The frontend source of truth is `Mydow_Web_Frontend_Complete_Package.zip` as deployed under `static/mydow/`; the product source of truth is `docs/01-prd/PRD10.md`. Agent 4 should replace or bypass older frontend surfaces when they conflict with the Mydow package, and verify that the deployed UI is bound to the PRD10 backend rather than only acting as a static prototype.

## Current Status

- `done` - Frontend package is deployed, backend binding smoke tests pass, and high-intent PRD10 actions are bound through `static/mydow/mydow-api.js`. Browser-level UI acceptance remains a P1 hardening track; V1 currently uses static DOM/API contract tests plus ASGI endpoint liveness.
  - Deployed bundle: `static/mydow/index.html`, `static/mydow/HANDOFF.md`, `static/mydow/mydow-api.js`.
  - Mounted app path: `/mydow`.
  - Existing binding test: `tests/integration/api/test_prd10_frontend_binding.py`.
  - Current Agent 4 binding test status: `python -m pytest tests/integration/api/test_prd10_frontend_binding.py -q -p no:cacheprovider` -> `14 passed`.
  - Chrome MCP live-browser validation status: PASS for authenticated `window.MydowAPI` calls to `/me`, Today, Capture, Feed, KB, Notifications, Search, AI, Skills, and Garden.

## Mission

Make `Mydow_Web_Frontend_Complete_Package.zip` the effective frontend standard for PRD10 V1 and prove that it works against the PRD10 backend contract. Do not redesign the UI unless the package itself is missing a critical PRD10 flow. Prefer binding, smoke tests, and compatibility shims over broad frontend rewrites.

## Task Map

1. `done` - Verify the package is deployed.
   - `static/mydow/index.html` is the package HTML prototype.
   - `static/mydow/HANDOFF.md` is present.
   - `static/mydow/mydow-api.js` is loaded by `index.html`.
   - `agent_os.server.app` mounts `/mydow` with `StaticFiles(html=True)`.

2. `done` - Audit current frontend replacement completeness.
   - Identify any older frontend/static entrypoints still presented as primary product UI.
   - Decide whether they should redirect to `/mydow`, remain legacy/dev-only, or be removed from navigation.
   - Output a short replacement map: old entrypoint -> action -> reason.
   - Initial Agent 1 decision already applied:
     - `/` redirects to `/mydow/` when the Mydow bundle exists.
     - `/legacy` serves the old AgentOS index.
     - `/login.html`, `/project-wizard.html`, and `/static/*` remain legacy/dev-only pending your full replacement map.
   - Replacement map after Agent 4 first pass:
     - `/` -> redirect to `/mydow/`; reason: Mydow is the V1 frontend standard; risk: none if bundle exists, current code falls back to legacy when absent.
     - `/mydow/` -> canonical V1 UI; reason: package lives under `static/mydow/` with `StaticFiles(html=True)`; risk: browser-only behavior is still mostly prototype state until more bindings land.
     - `/legacy` -> keep as legacy/dev-only; reason: old AgentOS UI may still be useful for debugging session/workspace tools; risk: user confusion if linked from product docs.
     - `/login.html` -> keep as legacy/dev-only for now; reason: `mydow-api.js` expects `localStorage["mydow_token"]`, while auth UX is not yet embedded in the package; risk: auth flow remains split.
     - `/project-wizard.html` -> keep as legacy/dev-only; reason: not part of PRD10 Mydow V1 acceptance; risk: stale product affordance if exposed publicly.
     - `/static/*` -> keep as asset/debug mount; reason: existing legacy pages may reference it; risk: no primary navigation should point users there.

3. `done` - Expand `mydow-api.js` from smoke binding to action binding.
   - Current JS exposes domain clients for search, AI, skills, garden, feed, KB, capture, notifications, jobs, today, and me.
   - Done in first Agent 4 slice:
     - Capture text submit -> `POST /api/v1/capture/text`.
     - Web clipping modal save -> `POST /api/v1/capture/link`.
     - New folder modal create -> `POST /api/v1/kb/folders`.
   - Verified in current takeover pass: selectors in `mydow-api.js` match the
     actual `index.html` modal names/buttons and the static contract test
     guards those exact hooks.
   - Done in later binding slice:
     - New document flow -> `POST /api/v1/cards`.
     - Notifications read-all -> `POST /api/v1/notifications/read-all`.
     - Skill run modal -> `POST /api/v1/skills/{id}/run`.
     - AI save modal -> `/api/v1/ai/messages/{id}/save-to-kb`.
   - Preserve the prototype's visual feedback while adding real API calls.

4. `done` - Add UI-level contract tests for the Mydow package.
   - Existing test only verifies static reachability and backend endpoint liveness via `httpx`.
   - Added first static DOM/API contract guard:
     - `test_today_home_binding` verifies the canonical app responds to `MydowAPI.today.fetch()`'s `/api/v1/today` path with PRD10 shape.
     - `test_mydow_primary_action_bindings_are_wired` verifies the prototype DOM still exposes Capture/WebLink/NewFolder hooks and `mydow-api.js` binds them to PRD10 API helpers.
   - P1 browser/DOM-level coverage when the repo test stack supports it:
     - Load `/mydow/`.
     - Confirm primary navigation pages switch correctly.
     - Seed or mock auth token.
     - Trigger capture/search/AI/skills/garden flows and assert network calls hit `/api/v1`.
   - If no browser runner is available, add a JS/HTML static contract test that parses the DOM hooks and verifies `mydow-api.js` binds them.

5. `done` - Coordinate with Agent 3 on frontend binding tests.
   - Agent 3 already owns backend path liveness and API contract binding tests.
   - Agent 4 owns real UI behavior: DOM hooks, user-visible state, and frontend replacement completeness.
   - Avoid duplicating Agent 3's `httpx` backend smoke tests unless a frontend hook requires a new backend endpoint.

6. `done` - Frontend acceptance report.
   - Current evidence is recorded in `agent-progress-report.md`
     Milestones 8 / 10 / 12.
   - Acceptance command: full PRD10 integration matrix +
     `tests/integration/api/test_prd10_v1_acceptance.py` -> `159 passed`.
   - Static package reachability and backend path liveness are covered by
     `tests/integration/api/test_prd10_frontend_binding.py`.
   - Chrome MCP browser validation evidence is recorded in
     `agent-progress-report.md` Milestone 12.

8. `done` - Real LLM provider + AI streaming SSE.
   - New `agent_os.ai.llm_provider` module owns `is_llm_enabled()` /
     `get_provider()` / `set_test_provider()`. Default-off so PRD10 AI
     tests stay offline; honor `AGENTOS_AI_LLM=on/1/true/enabled`.
   - `POST /api/v1/ai/conversations/{id}/messages` now persists real LLM
     content + token / latency metrics when the switch is on; falls back
     to the placeholder with `AI_PROVIDER_ERROR` on failure.
   - **New** `POST /api/v1/ai/conversations/{id}/messages/stream` returns
     `text/event-stream` and emits `meta` → `token*` → `done` events,
     binding to `LiteLLMProvider.stream_complete`.
   - Tests: `tests/integration/api/test_prd10_ai_llm.py` (9 tests),
     plus existing AI suite (14) all green; full PRD10 matrix 174 passed.
   - Side fix: `tests/integration/api/prd10/test_prd10_capture_api.py`
     was asserting the deprecated `local://` scheme; rewritten against
     the real `/api/v1/uploads/local/{id}/raw` URL the V1 frontend can
     actually `GET` / `<img>`-render.

7. `done` - PRD10 V1 acceptance walk-through.
   - New `tests/integration/api/test_prd10_v1_acceptance.py` boots
     `agent_os.server.app:app` and runs:
     - PRD10 §25.1 first-screen API matrix for Today / KB / AI / Skills /
       Garden / Search.
     - PRD10 §26.1 capture → feed → notification chain.
     - PRD10 §26.2 KB folder + presign + commit + listing chain.
     - PRD10 §26.3 AI conversation + message + save-to-kb + worker
       materialization + notification.
     - Mydow static bundle reachability (`/`, `/mydow/`, `/mydow/mydow-api.js`).
   - Outstanding to be fully PRD10-compliant (recorded in
     `agent-progress-report.md` Milestone 12):
     - AI streaming SSE (`POST /api/v1/ai/messages/{id}/stream`).
     - Real LLM provider plug-in.
     - Embedding + semantic search.
     - `/insights/*` endpoints.
     - Browser-level UI tests (Playwright runner choice pending Engineer 1).
     - Mock data seed script (PRD10 §25.3).
     - Auth UX embedded in the Mydow bundle.

## Decisions

- `done` - `Mydow_Web_Frontend_Complete_Package.zip` is the V1 frontend standard.
- `done` - PRD10 remains the product/API requirement standard.
- `done` - `/mydow` is the canonical mounted frontend path for V1 acceptance.
- `done` - Older primary root redirects to `/mydow`; old surfaces remain legacy/dev-only.
- `done` - V1 keeps Agent 4 tests as static DOM/API contract checks until a browser runner is selected.

## Dependencies

- Agent 1: final integration decision, app routing, acceptance criteria, and avoiding route conflicts.
- Agent 2: product-data endpoints used by capture/feed/KB/notifications/jobs/today.
- Agent 3: AI/search/skills/garden endpoints and backend binding tests.

## Notes / Blockers

- The package is currently a single-file static prototype plus an API augmentation script. It is not a React/Vue app.
- Unauthenticated browser sessions intentionally degrade to friendly toast messages because PRD10 APIs require Bearer auth.
- Current tests prove `/mydow/`, `/mydow/mydow-api.js`, high-intent DOM hooks, and backend endpoints are live in the same ASGI app; they do not yet prove a real browser click creates persisted data through the UI.
- Startup instructions for this role live in `agent-4-initialization.md`.
- First UI action-binding slice is guarded by static contract tests. Browser
  click-level persistence tests still need a runner or a DOM harness.
