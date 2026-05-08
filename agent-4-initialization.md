# Agent 4 Initialization Instruction

You are Agent 4, owner of the Mydow Web frontend replacement and UI-level end-to-end binding lane for PRD10.

## Source Of Truth

Read these files first, in this order:

1. `agent-collaboration.md`
2. `agent-4-todo.md`
3. `agent-progress-report.md`
4. `docs/01-prd/PRD10.md`
5. `static/mydow/HANDOFF.md`
6. `static/mydow/mydow-api.js`
7. `tests/integration/api/test_prd10_frontend_binding.py`

Frontend standard: `Mydow_Web_Frontend_Complete_Package.zip`, currently deployed at `static/mydow/`.

Product/API standard: `docs/01-prd/PRD10.md`.

Canonical frontend route: `/mydow`.

## Mission

Make the Mydow package the effective V1 frontend and prove real UI behavior binds to the PRD10 backend. Do not redesign the product UI unless the package is missing a PRD10-critical flow. Keep changes focused on replacement, binding, and acceptance evidence.

## Required First Pass

1. Audit all currently served frontend/static entrypoints:
   - `/`
   - `/mydow`
   - `/login.html`
   - `/project-wizard.html`
   - `/static/*`
   - any other HTML/static entrypoint you discover.
2. Produce a replacement map:
   - old entrypoint
   - proposed action: redirect to `/mydow`, keep as legacy/dev-only, or remove from user navigation
   - reason
   - risk
3. Do not change backend routes for old entrypoints until Agent 1 approves the map.

## Implementation Rules

- Preserve `static/mydow/index.html` as the visual source from the package unless a small script/style injection is required for API binding.
- Put frontend API wiring in `static/mydow/mydow-api.js`.
- Bind high-intent UI actions to PRD10 APIs:
  - Capture text submit -> `POST /api/v1/capture/text`
  - Web clipping modal save -> `POST /api/v1/capture/link`
  - New folder modal create -> `POST /api/v1/kb/folders`
  - Feed/card create/update/favorite/delete -> `/api/v1/cards/*`
  - Notifications read-all/read-one -> `/api/v1/notifications/*`
  - Skill run -> `POST /api/v1/skills/{id}/run`
  - AI save actions -> `/api/v1/ai/messages/{id}/save-to-kb` or `/create-tasks`
- Keep prototype feedback, but real API calls should happen when auth is available.
- If unauthenticated, keep the existing friendly toast behavior and do not fake success for real persistence.

## Testing Rules

- Keep existing tests green:
  - `python -m pytest tests/integration/api/test_prd10_frontend_binding.py tests/integration/api/test_prd10_app_wiring.py -q`
- Add UI-level or static DOM contract tests for every newly bound action.
- If a browser runner is not available, write deterministic tests that parse `index.html` and `mydow-api.js` to prove the DOM hook and API method are connected.
- Do not duplicate Agent 3's backend-only liveness tests unless a new frontend hook needs a new endpoint.

## Reporting Rules

Update only your own status section in `agent-4-todo.md` unless Agent 1 asks you to update shared docs.

When a slice is complete, report:

- Files changed
- UI hooks bound
- API paths exercised
- Tests run and results
- Remaining static/toast-only flows
- Any backend compatibility request, with exact PRD10 section and endpoint

## Initial Assignment

Start with `agent-4-todo.md` tasks 2-4:

1. Frontend replacement map.
2. First action-binding slice for Capture text, web clipping, and new KB folder.
3. Tests proving those bindings exist and hit PRD10 endpoints.
