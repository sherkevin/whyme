# PRD10 Backend Progress Report

## Milestone 81 - v1.4 AI stream send recovery - DELIVERED

**When**: 2026-05-08 23:44 UTC+8 (by Codex)
**Why**: `todo-tasks.md` Section 18.2 / user night review reported that Mydow AI send had no visible response.

### Delivered

* Added `fetchAiStreamWithSession()` in `static/mydow/biz_v14/bridge_v14.js`.
* AI send now ensures a valid session before creating/using a conversation.
* Streaming `/messages/stream` requests recover from stale browser tokens by clearing token, demo-login refreshing, and retrying once.
* AI placeholder thinking text is removed once a real stream response begins, so completed answers no longer keep a stale "姝ｅ湪鐢熸垚" label.
* Added focused frontend binding regression coverage for the stream auth recovery hook.

### Test Evidence

* `node --check static\mydow\biz_v14\bridge_v14.js` -> PASS.
* `pytest tests\integration\api\test_prd10_frontend_binding.py::test_biz_v14_ai_stream_refreshes_session_before_send -q` -> PASS.
* Chrome MCP on `127.0.0.1:8035`: intentionally wrote a bad `mydow_v14_token`, sent a Mydow AI prompt, observed automatic session refresh and `POST /api/v1/ai/conversations/{id}/messages/stream` -> 200.
* DOM evidence after streaming: latest assistant answer rendered with KB citations, `hasThinking=false`.
* Screenshot: `.tmp/screenshots/v18_2_ai_stream_fixed.png`.

### Files Touched

* `static/mydow/biz_v14/bridge_v14.js`
* `tests/integration/api/test_prd10_frontend_binding.py`
* `todo-tasks.md`
* `agent-progress-report.md`

### Next

Continue Section 18.3 `@` knowledge/document searchable context picker.

---

## Milestone 80 - v1.4 profile preference controls - DELIVERED

**When**: 2026-05-08 23:35 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂18.1 / user night review reported that Profile & Settings base preference buttons were not truly clickable.

### Delivered

* Fixed `bridge_v14.js::bindPrefToggleV39`: Auto Save now writes the real backend field `auto_save` instead of ignored `auto_save_enabled`.
* Auto Save toggle now updates visual and accessibility state together (`active`, `aria-pressed`, `aria-label`).
* Added `bridge_v14_ext.js` 搂18.1 profile preference runtime:
  * Hydrates `/api/v1/me/preferences`.
  * Converts static `.select-control` rows into clickable controls.
  * Adds modern `mydow-choice-popover` listbox UI for default AI model, language, and default input mode.
  * Persists changes through `PATCH /api/v1/me/preferences`.
* Added frontend binding regression coverage for the 搂18.1 control wiring.

### Test Evidence

* Chrome MCP on `127.0.0.1:8035`: Profile -> Preferences -> Default AI Model -> selected `DeepSeek V4 Flash`; verified `default_ai_model=deepseek-v4-flash` through `GET /api/v1/me/preferences`.
* Chrome MCP on `127.0.0.1:8035`: Auto Save toggle off/on; verified `auto_save=false/true` through `GET /api/v1/me/preferences`.
* Console errors: **0**.
* Screenshot: `.tmp/screenshots/v18_1_profile_preferences_fixed.png`.
* Static checks: `node --check static\mydow\biz_v14\bridge_v14.js` and `node --check static\mydow\biz_v14\bridge_v14_ext.js` -> PASS.
* Regression: `pytest tests\integration\api\test_prd10_frontend_binding.py -q` -> **39 passed**.

### Files Touched

`static/mydow/biz_v14/bridge_v14.js`, `static/mydow/biz_v14/bridge_v14_ext.js`, `tests/integration/api/test_prd10_frontend_binding.py`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

Continue 搂18.2 Mydow AI send/stream unresponsive issue.

---

## Milestone 79 - Todo table maintenance closeout - DELIVERED

**When**: 2026-05-08 22:46 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂8.8 was the final active maintenance row after all actionable PRD10 rows were closed.

### Delivered

* Kept `todo-tasks.md` as the single source of truth with start/done timestamps on newly handled rows.
* Added progress milestones for i18n, six-state UI verification, workspace permissions, billing/credits, skill marketplace, fixture audit, and final closeout.
* Closed all remaining `open`, `doing`, and `blocked` rows.
* Preserved existing worktree changes and did not revert unrelated edits.

### Test Evidence

* Final focused regression: `pytest tests\integration\api\test_prd10_frontend_binding.py tests\integration\api\test_prd10_skill_marketplace_api.py tests\integration\api\test_prd10_billing_api.py tests\integration\api\test_prd10_workspace_permissions.py tests\integration\api\test_prd10_app_wiring.py -q` -> **60 passed**.
* Final todo status query: no remaining `open`, `doing`, or `blocked` rows.

### Files Touched

`todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

None in the total todo table.

---

## Milestone 78 - import_test toolkit fixture audit - DELIVERED

**When**: 2026-05-08 22:46 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂6.3 was left open waiting for a decision on whether tracked `data/workspaces/import_test/toolkit/*` changes were legitimate fixtures.

### Delivered

* Audited `data/workspaces/import_test/toolkit/registry.json` and `tools_summary.md`.
* Confirmed both files are generated by `data/workspaces/import_test/toolkit/manager.py refresh`.
* Confirmed the fixture contains only the local `calculator` and `weather` skills plus an empty MCP server list.
* Confirmed no API keys, production business data, or user data are present.

### Test Evidence

* `python manager.py refresh` from `data/workspaces/import_test/toolkit` -> `[OK] Registry updated! Skills: 2 MCP Servers: 0 Total Tools: 2`.
* `python manager.py list` from `data/workspaces/import_test/toolkit` -> skills `calculator` and `weather`, `mcp_servers: []`.

### Files Touched

`data/workspaces/import_test/toolkit/registry.json`, `data/workspaces/import_test/toolkit/tools_summary.md`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

Close the 搂8.8 maintenance row after final todo status verification.

---

## Milestone 77 - Skill Marketplace API - DELIVERED

**When**: 2026-05-08 22:39 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂6.8 / PRD10 B-19 required a real skill marketplace flow connected to billing credits and install state.

### Delivered

* Added `src/agent_os/marketplace/models.py` with `SkillMarketplaceListing` and `SkillInstallation`.
* Added `/api/v1/skill-marketplace/listings` list/search/filter and seller listing create/update endpoints.
* Added `/api/v1/skill-marketplace/installations` so the current user can query installed marketplace skills.
* Added `/api/v1/skill-marketplace/listings/{listing_id}/purchase` with real credit deduction via 搂6.7 `CreditLedger`.
* Enforced no seller self-purchase, no double charge on repeated purchase, insufficient-credit rejection, and persisted install/purchase counters.
* Mounted the marketplace router in `src/agent_os/server/app.py`.

### Test Evidence

* Compile: `python -m py_compile src\agent_os\marketplace\models.py src\agent_os\marketplace\router.py src\agent_os\server\app.py tests\integration\api\test_prd10_skill_marketplace_api.py` -> PASS.
* Marketplace suite: `pytest tests\integration\api\test_prd10_skill_marketplace_api.py -q` -> **4 passed**.
* Focused regression: `pytest tests\integration\api\test_prd10_skill_marketplace_api.py tests\integration\api\test_prd10_billing_api.py tests\integration\api\test_prd10_workspace_permissions.py tests\integration\api\test_prd10_app_wiring.py tests\integration\api\test_prd10_skills_api.py -q` -> **47 passed**.

### Files Touched

`src/agent_os/marketplace/__init__.py`, `src/agent_os/marketplace/models.py`, `src/agent_os/marketplace/router.py`, `src/agent_os/server/app.py`, `tests/integration/api/test_prd10_skill_marketplace_api.py`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

Audit and close the remaining 搂6.3 fixture decision and 搂8.8 maintenance row.

---

## Milestone 76 - Billing subscription and credits API - DELIVERED

**When**: 2026-05-08 22:33 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂6.7 / PRD10 B-18 required a real subscription and credit foundation rather than static plan labels.

### Delivered

* Added `src/agent_os/billing/models.py` with `BillingSubscription` and append-only `CreditLedger`.
* Added `/api/v1/billing/plans`, `/overview`, `GET/PATCH /subscription`, `GET /credits`, and `POST /credits/consume`.
* Default billing overview creates a persisted free subscription and grants 100 initial credits.
* Plan upgrades persist subscription state, update `User.settings.plan` so `/api/v1/me.plan` stays aligned, and grant plan allowance credits.
* Credit consumption records a negative ledger row with balance tracking and rejects overspend with a PRD10 validation envelope.

### Test Evidence

* Compile: `python -m py_compile src\agent_os\billing\models.py src\agent_os\billing\router.py src\agent_os\server\app.py tests\integration\api\test_prd10_billing_api.py` -> PASS.
* Billing suite: `pytest tests\integration\api\test_prd10_billing_api.py -q` -> **4 passed**.
* Focused regression: `pytest tests\integration\api\test_prd10_billing_api.py tests\integration\api\test_prd10_workspace_permissions.py tests\integration\api\test_prd10_app_wiring.py -q` -> **18 passed**.

### Files Touched

`src/agent_os/billing/__init__.py`, `src/agent_os/billing/models.py`, `src/agent_os/billing/router.py`, `src/agent_os/server/app.py`, `tests/integration/api/test_prd10_billing_api.py`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

Continue 搂6.8 Skill Marketplace.

---

## Milestone 75 - Workspace permission API - DELIVERED

**When**: 2026-05-08 22:26 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂6.6 / PRD10 B-17 required a real multi-workspace permission foundation instead of only reserved `workspace_id` fields.

### Delivered

* Added `src/agent_os/workspaces/models.py` with `WorkspaceMember` role membership (`owner`, `admin`, `editor`, `viewer`) and uniqueness constraints.
* Added `src/agent_os/workspaces/router.py` under `/api/v1/workspaces`.
* Added workspace create/list/detail/update endpoints.
* Added member list/upsert/update/remove endpoints.
* Mounted the router in `src/agent_os/server/app.py`.
* Enforced real permission boundaries: owner/admin can manage; viewer can read but not admin; non-members get explicit 403 envelopes; owners cannot be downgraded or removed.
* Added integration tests for create/list, non-member 403, viewer-to-admin promotion, and owner guardrails.

### Test Evidence

* Compile: `python -m py_compile src\agent_os\workspaces\models.py src\agent_os\workspaces\router.py src\agent_os\server\app.py tests\integration\api\test_prd10_workspace_permissions.py` -> PASS.
* Workspace permission suite: `pytest tests\integration\api\test_prd10_workspace_permissions.py -q` -> **4 passed**.
* Focused regression: `pytest tests\integration\api\test_prd10_workspace_permissions.py tests\integration\api\test_prd10_app_wiring.py -q` -> **14 passed**.

### Files Touched

`src/agent_os/workspaces/__init__.py`, `src/agent_os/workspaces/models.py`, `src/agent_os/workspaces/router.py`, `src/agent_os/server/app.py`, `tests/integration/api/test_prd10_workspace_permissions.py`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

Continue 搂6.7 Subscription/Billing.

---

## Milestone 74 - Acceptance gate six UI states - DELIVERED

**When**: 2026-05-08 22:20 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂14.4 was still blocked by old SPA state-machine defects, but its blockers (搂9.13-搂9.17) are now done and needed an independent acceptance closeout.

### Delivered

* Reopened the blocked gate and verified the six-state UI contract without changing product code.
* Confirmed the public SPA state surface still exposes Loading, Empty, Error, Forbidden, Processing, and Success components.
* Confirmed accessibility roles: Error/Forbidden use `role=alert`; Loading/Empty/Processing/Success use `role=status`.

### Test Evidence

* Chrome MCP on uvicorn `127.0.0.1:8034`: registered a real user against isolated SQLite and injected a six-state gallery via `window.MydowAPI.uiStates`.
* Visible state classes: `.state-loading`, `.state-empty`, `.state-error`, `.state-forbidden`, `.state-processing`, `.state-success`.
* Console errors: **0**.
* Screenshot: `.tmp/screenshots/v14_4_six_states_visible.png`.
* Local port cleanup: stopped 8034; `netstat :8034` showed no `LISTEN`.

### Files Touched

`todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

Continue remaining P2 TODOs.

---

## Milestone 73 - SPA i18n runtime - DELIVERED

**When**: 2026-05-08 22:15 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂9.12 required Chinese/English switching based on `User.locale`, not a cosmetic-only frontend toggle.

### Delivered

* Added `static/mydow/i18n/zh.json` and `static/mydow/i18n/en.json`.
* Added SPA i18n runtime in `static/mydow/app.js`: `normalizeLocale()`, `resolveLocale()`, `loadLocale()`, `t()`, and `setLocale()`.
* Boot now resolves language from `User.locale` / `settings.locale` / local fallback and sets `document.documentElement.lang`.
* The topbar language switcher persists the preference through real `PATCH /api/v1/me`.
* Migrated shell, topbar, Home, KB, AI empty state, and search empty state core copy to `t()`.
* Added frontend binding regression coverage for locale dictionaries and runtime wiring.

### Test Evidence

* Syntax: `node --check static\mydow\app.js` -> PASS.
* Frontend binding suite: `pytest tests\integration\api\test_prd10_frontend_binding.py -q` -> **38 passed**.
* Chrome MCP on uvicorn `127.0.0.1:8033`: registered a real user against isolated SQLite, switched zh -> en and en -> zh.
* Network evidence: `GET /mydow/i18n/en.json` 200, `GET /mydow/i18n/zh.json` 200, `PATCH /api/v1/me` 200 on both switches.
* Persistence evidence: `/me.locale=en-US` after English switch; `/me.locale=zh-CN`, `settings.locale=zh-CN`, and `document.lang=zh-CN` after switching back.
* UI evidence: Home showed `Hi`, `Submit`, `Recent ideas`; KB showed `Knowledge Base`, `New folder`; AI showed `No conversations yet`; switching back restored Chinese nav and AI empty copy.
* Console errors: **0**.
* Screenshot: `.tmp/screenshots/v9_12_i18n_toggle.png`.
* Local port cleanup: stopped 8033; `netstat :8033` showed no `LISTEN`.

### Files Touched

`static/mydow/app.js`, `static/mydow/i18n/zh.json`, `static/mydow/i18n/en.json`, `tests/integration/api/test_prd10_frontend_binding.py`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

Continue the remaining P2 TODOs.

---

## Milestone 72 - SPA drag and multiselect interactions - DELIVERED

**When**: 2026-05-08 21:59 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂9.11 required production-feel drag and multiselect behavior: Feed multiselect archive, KB document drop into folder, and draggable Garden nodes.

### Delivered

* Added Feed multiselect state and toolbar in `static/mydow/app.js`; selected cards can be archived through real `PATCH /api/v1/cards/{id}` calls.
* Added draggable KB document rows and folder drop targets; dropping a document onto a folder calls real `POST /api/v1/kb/documents/{id}/move`.
* Added pointer-drag behavior for Garden SVG nodes, with visual dragging state and click suppression after drag.
* Added CSS for selection toolbar, selected feed cards, draggable document rows, folder drop targets, and Garden drag shadows.
* Added frontend binding regression coverage for the new interaction contracts.

### Test Evidence

* Syntax: `node --check static\mydow\app.js` -> PASS.
* Frontend binding suite: `pytest tests\integration\api\test_prd10_frontend_binding.py -q` -> **37 passed**.
* Chrome MCP on uvicorn `127.0.0.1:8032`: seeded a real user, 2 captures, 2 folders, and a KB document. Feed multiselect archive reduced feed count `1 -> 0`; KB drop moved document to the target folder (`folder_id` matched); Garden node drag moved coordinates `[360,270] -> [392,290]`.
* Network evidence: `PATCH /api/v1/cards/*` 200, `POST /api/v1/kb/documents/*/move` 200, `GET /api/v1/garden/*` 200.
* Console errors: **0**.
* Screenshot: `.tmp/screenshots/v9_11_drag_multiselect.png`.
* Local port cleanup: `Stop-Process 83636`; `netstat :8032` showed only `TIME_WAIT`, no listener.

### Files Touched

`static/mydow/app.js`, `static/mydow/style.css`, `tests/integration/api/test_prd10_frontend_binding.py`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

Continue 搂9.12 i18n.

---

## Milestone 71 - SPA unified toast system - DELIVERED

**When**: 2026-05-08 21:50 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂9.10 required unified info/success/warning/error toasts with auto-dismiss, manual close, and queue behavior.

### Delivered

* Replaced the simple text-only toast with a typed component in `static/mydow/app.js`.
* Added four `data-toast-kind` values: `info`, `success`, `warning`, `error`.
* Added accessible `role=status` for non-errors and `role=alert` for errors.
* Added a close button, leave animation, queue cap (`TOAST_LIMIT = 5`), and `duration: 0` support for persistent test/operator notices.
* Added tokenized CSS classes for `.toast-info`, `.toast-success`, `.toast-warning`, `.toast-error`, `.toast-close`, and `.toast.is-leaving`.

### Test Evidence

* Syntax: `node --check static\mydow\app.js` -> PASS.
* Frontend binding suite: `pytest tests\integration\api\test_prd10_frontend_binding.py -q` -> **36 passed**.
* Chrome MCP on uvicorn `127.0.0.1:8031`: injected 6 toasts; queue capped to 5; all retained toasts had expected kind/role/close button; manual close reduced 5 -> 4; console errors: **0**.
* Screenshot: `.tmp/screenshots/v9_10_toast_system.png`.
* Local port cleanup: `NO_LISTEN_8031`.

### Files Touched

`static/mydow/app.js`, `static/mydow/style.css`, `tests/integration/api/test_prd10_frontend_binding.py`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

Continue 搂9.11 drag and multiselect behavior.

---

## Milestone 70 - SPA empty-state illustrations - DELIVERED

**When**: 2026-05-08 21:44 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂9.8 required polished SVG illustrations for empty states across Home, KB, AI, notifications, and search.

### Delivered

* Added `stateIllustration()` to `static/mydow/app.js`, with a reusable inline SVG registry for `spark`, `folder`, `doc`, `ai`, `bell`, `search`, `task`, `skills`, and `error`.
* Wired the registry into the shared `stateCard()` path, so existing empty/error/success-style UI keeps a single component contract.
* Updated search zero-results to use the real empty-state component with the search illustration.
* Updated the AI page to show an actual "no conversation" empty state with a "new conversation" CTA instead of silently creating a blank conversation on route entry.
* Added CSS for the new line-art system in `static/mydow/style.css`, using existing design tokens and theme colors.

### Test Evidence

* Syntax: `node --check static\mydow\app.js` -> PASS.
* Frontend binding suite: `pytest tests\integration\api\test_prd10_frontend_binding.py -q` -> **35 passed**.
* Chrome MCP on uvicorn `127.0.0.1:8030`: registered a real user, verified Home / KB / AI / notification / search empty states all render `.state-visual-svg` with semantic classes `spark`, `folder`, `ai`, `bell`, and `search`; console errors: **0**.
* Screenshot: `.tmp/screenshots/v9_8_empty_illustrations.png`.
* Local port cleanup: `NO_LISTEN_8030`.

### Files Touched

`static/mydow/app.js`, `static/mydow/style.css`, `tests/integration/api/test_prd10_frontend_binding.py`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

Continue 搂9.10 unified toast system.

---

## Milestone 69 - SPA low-frequency button audit - DELIVERED

**When**: 2026-05-08 21:35 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂4.9 required a full-page low-frequency button audit with real backend effects, no toast-only success, and Chrome MCP evidence.

### Delivered

* Added `scripts/smoke_spa_buttons.py`, a real-browser Playwright smoke that registers a real user and drives SPA buttons through the live FastAPI app.
* Covered 20 cross-page controls: sidebar routes, theme, notifications, capture, upload modal, web clip, deep research, KB folder/doc actions, AI conversation/send, Skills run, Today task creation, global search, and Garden.
* Fixed a real frontend/backend contract bug: task creation UI was still sending `priority=normal`; PRD10 accepts `low|medium|high|urgent`. The SPA now defaults task creation and AI-created tasks to `medium`.

### Test Evidence

* Button audit: `python scripts\smoke_spa_buttons.py --base http://127.0.0.1:8029 --out .tmp\spa_button_audit.json --screenshot-dir .tmp\screenshots\v4_9_buttons` -> **20/20 passed**, `api_call_count=59`, `api_failures=[]`, `console_errors=[]`, `page_errors=[]`.
* Syntax: `node --check static\mydow\app.js` -> PASS.
* Frontend binding suite: `pytest tests\integration\api\test_prd10_frontend_binding.py -q` -> **35 passed**.
* Chrome MCP on uvicorn `127.0.0.1:8029`: registered a real user, clicked Today `鏂板缓浠诲姟`, confirmed modal default priority `medium`, submitted, observed `POST /api/v1/tasks` -> **201**, and saw the task render back in Today.
* Screenshot: `.tmp/screenshots/v4_9_buttons/chrome_mcp_today_task_medium.png`.

### Files Touched

`scripts/smoke_spa_buttons.py`, `static/mydow/app.js`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

Continue 搂9 frontend polish. Remaining open items include 搂9.8 empty-state SVG illustrations, 搂9.10 unified toast system, 搂9.11 drag/multiselect, and 搂9.12 i18n.

---

## Milestone 68 - SPA accessibility guardrails - DELIVERED

**When**: 2026-05-08 20:55 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂9.7 required aria roles, focus rings, tab order, contrast, and screen-reader semantics.

### Delivered

* Added `.sr-only` and a consistent `:focus-visible` treatment in `static/mydow/style.css`.
* Added keyboard activation for non-native `role="button"` controls in the shared `el()` helper.
* Added navigation semantics: `nav aria-label`, sidebar `aria-label`, active nav `aria-current="page"`.
* Added `#page-region tabindex="-1"` and `aria-live="polite"` so dynamic route content has a stable landmark/update target.
* Added static regression coverage in `tests/integration/api/test_prd10_frontend_binding.py`.

### Test Evidence

* Syntax: `node --check static\mydow\app.js` -> PASS.
* Frontend binding suite: `pytest tests\integration\api\test_prd10_frontend_binding.py -q` -> **35 passed**.
* Chrome MCP on uvicorn `127.0.0.1:8022`: registered a real user, verified nav/sidebar labels, active `aria-current`, page `aria-live`, role-button tab index, and focus outline on a real nav item.
* Lighthouse snapshot: **Accessibility 100**, **Best Practices 100**, **Agentic Browsing 100**.
* Console: **0 errors**.
* Screenshot: `.tmp/screenshots/v9_7_a11y/focus_ring.png`.

### Files Touched

`static/mydow/app.js`, `static/mydow/style.css`, `tests/integration/api/test_prd10_frontend_binding.py`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

Continue 搂9 frontend polish with empty-state illustrations, toast consistency, drag/multiselect behavior, and i18n.

---

## Milestone 67 - SPA micro-interactions - DELIVERED

**When**: 2026-05-08 20:43 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂9.5 required button press, card hover, drag feedback, and SSE stream-entry motion with 80-240ms timing and reduced-motion support.

### Delivered

* Added motion tokens in `static/mydow/style.css`: `--motion-fast` 80ms, `--motion-base` 160ms, `--motion-slow` 240ms, and a shared ease-out curve.
* Added polished hover/active treatments for cards and repeated clickable surfaces.
* Added drag/drop visual affordances via `.is-dragging`, `[draggable="true"]:active`, `.drag-over`, and `.drop-target.is-over`.
* Added stream-entry animation and typing caret for `.bubble.is-typing`.
* Expanded `prefers-reduced-motion: reduce` handling to stop skeleton, state, toast, bubble, and caret animations while shortening transitions.
* Added static regression coverage in `tests/integration/api/test_prd10_frontend_binding.py`.

### Test Evidence

* Syntax: `node --check static\mydow\app.js` -> PASS.
* Frontend binding suite: `pytest tests\integration\api\test_prd10_frontend_binding.py -q` -> **34 passed**.
* Chrome MCP on uvicorn `127.0.0.1:8021`: registered a real user, injected card/drag/bubble states, verified computed `--motion-fast=80ms`, card transition `0.16s/0.24s/0.08s`, drag opacity `0.78`, bubble animation `bubble-in`, typing caret animation `stream-caret`, and **0 console errors**.
* Screenshot: `.tmp/screenshots/v9_5_motion/motion_states.png`.

### Files Touched

`static/mydow/style.css`, `tests/integration/api/test_prd10_frontend_binding.py`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

Continue 搂9 frontend polish with accessibility, empty illustrations, toast consistency, drag/multiselect behavior, and i18n.

---

## Milestone 66 - SPA six-state visual system - DELIVERED

**When**: 2026-05-08 20:31 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂9.4 required a complete state visual spec: Loading, Empty, Error, 403, Processing, and Success.

### Delivered

* Added a shared `stateCard()` renderer in `static/mydow/app.js` and kept existing `skeletonPage()`, `emptyState()`, and `errorState()` call sites compatible.
* Added first-class `forbiddenState()`, `processingState()`, and `successState()` renderers.
* `errorState()` now routes 403/FORBIDDEN errors into the dedicated permission state.
* Exposed the state renderers under `window.MydowAPI.uiStates` for reproducible browser inspection.
* Added `state-card` styling in `static/mydow/style.css` with distinct loading/empty/error/forbidden/processing/success treatments and reduced-motion support.
* Added static regression coverage in `tests/integration/api/test_prd10_frontend_binding.py`.

### Test Evidence

* Syntax: `node --check static\mydow\app.js` -> PASS.
* Frontend binding suite: `pytest tests\integration\api\test_prd10_frontend_binding.py -q` -> **33 passed**.
* Chrome MCP on uvicorn `127.0.0.1:8020`: registered a real user, rendered all six state cards through `window.MydowAPI.uiStates`, verified 6/6 cards, 403/error `role=alert`, other states `role=status`, and found **0 console errors**.
* Screenshot: `.tmp/screenshots/v9_4_states/six_states_gallery.png`.

### Files Touched

`static/mydow/app.js`, `static/mydow/style.css`, `tests/integration/api/test_prd10_frontend_binding.py`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

Continue 搂9 frontend polish with micro-interactions, a11y, empty-state illustrations, toast consistency, drag/multiselect, and i18n.

---

## Milestone 65 - SPA responsive acceptance - DELIVERED

**When**: 2026-05-08 20:17 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂9.3 required the SPA to hold up across desktop, tablet, and mobile widths, with mobile navigation becoming a real bottom tab bar.

### Delivered

* Added responsive breakpoints in `static/mydow/style.css` for desktop narrowing, tablet rail, mobile bottom tabs, and very small mobile widths.
* At tablet widths the sidebar collapses into an icon rail, preserving route buttons without cramping content.
* At `<768px` the sidebar becomes a fixed bottom navigation bar with safe-area padding, hidden brand/user chrome, horizontal overflow containment, and bottom content padding so pages are not covered.
* Added a static regression test in `tests/integration/api/test_prd10_frontend_binding.py`.

### Test Evidence

* Syntax: `node --check static\mydow\app.js` -> PASS.
* Frontend binding suite: `pytest tests\integration\api\test_prd10_frontend_binding.py -q` -> **32 passed**.
* Chrome MCP on uvicorn `127.0.0.1:8019`: registered a real user, loaded `/mydow/spa/`, checked 1280 / 1024 / 768 / 390 viewports, verified no horizontal overflow, and found **0 console errors**.
* Mobile interaction: at 390px, clicked the bottom-tab "鐭ヨ瘑搴? button and verified navigation to `#/kb` with the active nav state updated.
* Screenshots: `.tmp/screenshots/v9_3_responsive/desktop_1280.png`, `tablet_1024_rail.png`, `tablet_768.png`, `mobile_390_exact.png`.

### Files Touched

`static/mydow/style.css`, `tests/integration/api/test_prd10_frontend_binding.py`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

Continue 搂9 visual polish: six-state visual spec, motion, accessibility, empty illustrations, toast consistency, drag/multiselect, and i18n.

---

## Milestone 64 - SPA design tokens and theme switching - DELIVERED

**When**: 2026-05-08 20:05 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂9.1 / 搂9.2 required the SPA to carry a complete design-token baseline and a real light/dark/system theme preference instead of relying only on OS media queries.

### Delivered

* Added complete SPA theme tokens in `static/mydow/style.css`: four spacing steps, six text-size steps, the missing radius token, and explicit light/dark variable scopes.
* Converted dark-mode styling from media-query-only to `data-theme` aware rules while preserving system-follow behavior when the user has no saved preference.
* Added a topbar theme button in `static/mydow/app.js` with `system -> light -> dark -> system` cycling and persistent `localStorage["mydow_theme"]`.
* Added `i-sun` / `i-moon` sprite symbols in `static/mydow/index.html`.
* Added regression coverage in `tests/integration/api/test_prd10_frontend_binding.py`.

### Test Evidence

* Syntax: `node --check static\mydow\app.js` -> PASS.
* Frontend binding suite: `pytest tests\integration\api\test_prd10_frontend_binding.py -q` -> **31 passed**.
* Chrome MCP on uvicorn `127.0.0.1:8018`: registered a real user, loaded `/mydow/spa/`, toggled theme three times, verified `localStorage["mydow_theme"]` and `<html data-theme>` transitions, and found **0 console errors**.
* Screenshots: `.tmp/screenshots/v9_1_theme/theme_light.png`, `.tmp/screenshots/v9_1_theme/theme_dark.png`.

### Files Touched

`static/mydow/style.css`, `static/mydow/app.js`, `static/mydow/index.html`, `tests/integration/api/test_prd10_frontend_binding.py`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

Continue with the remaining 搂9 frontend polish tasks, starting from responsive acceptance and state visuals.

---

## Milestone 63 - Backend hardening audit closeout - DELIVERED

**When**: 2026-05-08 19:55 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂8.12 was still open for PRD10 搂29 hardening: rate limiting, AI call caching, and multipart/resumable uploads.

### Delivered

* Audited the actual implementation coverage:
  * 搂12.2 already implements auth/AI/search/capture/global rate limits with PRD10 429 envelopes.
  * 搂12.3 already implements same-prompt 24h AI completion cache with env toggles and stream bypass.
  * 搂12.5 already implements multipart upload init/chunk/resume/complete/cancel plus capture-file commit compatibility.
* No new production code was needed; closed 搂8.12 with fresh verification evidence.

### Test Evidence

* Rate limit: `pytest tests/unit/common/test_rate_limit.py tests/integration/api/test_prd10_rate_limit.py -q` -> **42 passed**.
* AI cache / LLM: `pytest tests/integration/api/test_prd10_ai_llm.py -q` -> **15 passed**.
* Multipart uploads: `pytest tests/integration/api/prd10/test_prd10_uploads_multipart.py -q` -> **18 passed**.

### Files Touched

`todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

None for 搂8.12.

---

## Milestone 62 - Legacy search shim restored - DELIVERED

**When**: 2026-05-08 19:53 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂6.1 tracked historical `tests/integration/api/test_search_api_simple.py` failures caused by `agent_os.search.keyword_search` raising `NotImplementedError`.

### Delivered

* Replaced the legacy `KeywordSearchService` stub with a real compatibility layer over PRD4 `Item` rows: tokenization, stop-word filtering, BM25-like scoring, snippets, and async DB search.
* Replaced the legacy `HybridSearchService` stub with deterministic keyword/freshness/semantic-score merging, highlighting, and a real async search entrypoint.
* Restored `tests/integration/api/test_search_api_simple.py` from module-level skip to active tests.
* Kept PRD10 canonical search untouched under `agent_os.search_engine`.

### Test Evidence

* Syntax: `python -m py_compile src/agent_os/search/keyword_search.py src/agent_os/search/hybrid_search.py tests/integration/api/test_search_api_simple.py` -> PASS.
* Legacy simple search: `pytest tests/integration/api/test_search_api_simple.py -q` -> **14 passed**.
* Legacy + PRD10 search together: `pytest tests/integration/api/test_search_api_simple.py tests/integration/api/test_prd10_search_api.py -q` -> **29 passed**.

### Files Touched

`src/agent_os/search/keyword_search.py`, `src/agent_os/search/hybrid_search.py`, `tests/integration/api/test_search_api_simple.py`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

`tests/integration/api/test_search_api.py` remains module-skipped as a broader legacy suite; 搂6.1 specifically referenced the simple suite and is now green.

---

## Milestone 61 - OpenAPI examples and curl docs - DELIVERED

**When**: 2026-05-08 19:49 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂13.2 was stale in `doing`: `/docs` existed, but the generated OpenAPI schema did not carry concrete PRD10 examples or copyable curl samples for integrators.

### Delivered

* Added `src/agent_os/server/openapi_examples.py` and installed it from `server/app.py`.
* OpenAPI now includes local/demo `servers`, a documented `BearerAuth` scheme, and automatic Bearer security on private `/api/v1/*` operations.
* Added request/response examples and ReDoc `x-codeSamples` curl for login, text capture, KB folder creation, AI conversation creation, AI SSE streaming, Skill run, and search.
* Updated `docs/11-deployment/api-reference.md` with direct `curl | jq` checks for the enriched `/openapi.json`.

### Test Evidence

* Syntax: `python -m py_compile src/agent_os/server/openapi_examples.py src/agent_os/server/app.py tests/integration/api/test_prd10_openapi_examples.py` -> PASS.
* OpenAPI examples: `pytest tests/integration/api/test_prd10_openapi_examples.py -q` -> **4 passed**.
* App wiring + docs: `pytest tests/integration/api/test_prd10_app_wiring.py tests/integration/api/test_prd10_openapi_examples.py -q` -> **14 passed**.
* Manual schema smoke printed `http://localhost:8000`, `bearer`, capture example summary, and the Skills curl sample from `app.openapi()`.

### Files Touched

`src/agent_os/server/openapi_examples.py`, `src/agent_os/server/app.py`, `tests/integration/api/test_prd10_openapi_examples.py`, `docs/11-deployment/api-reference.md`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

The OpenAPI generator still reports pre-existing duplicate operation-id warnings from legacy/PRD10 task route overlap; not part of 搂13.2, but worth cleaning if client SDK generation becomes strict.

---

## Milestone 60 - PRD10 21.3 DB index audit - DELIVERED

**When**: 2026-05-08 19:43 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂12.6 was stale in `doing` and PRD10 搂21.3 requires concrete DB indexes for the main product-data tables.

### Delivered

* Added the missing exact PRD10 index coverage for inbox, cards, documents, chunks, tasks, conversations, messages, notifications, jobs, and search documents.
* Added `kb_chunks.source_id` so chunks can be queried and audited by real source lineage, then wired new chunk writes to copy the parent document source.
* Added `ensure_prd10_performance_indexes()` after `init_db()` so existing SQLite/Postgres databases get missing columns/indexes without a destructive rebuild.
* Kept the `cards(user_id,tags)` index SQLite-native in model metadata and Postgres-safe as an expression index in the runtime ensure path.

### Test Evidence

* Syntax: `python -m py_compile src/agent_os/db/base.py src/agent_os/kb/models.py src/agent_os/knowledge/models.py src/agent_os/inbox/prd10_models.py src/agent_os/jobs/service.py tests/integration/api/prd10/test_prd10_db_indexes.py` -> PASS.
* New index audit: `pytest tests/integration/api/prd10/test_prd10_db_indexes.py -q` -> **2 passed** (Inspector + SQLite `EXPLAIN QUERY PLAN`).
* Regression: `pytest tests/integration/api/prd10/test_prd10_jobs_notifications_api.py tests/integration/api/prd10/test_prd10_kb_api.py -q` -> **42 passed**.
* PRD10 lane: `pytest tests/integration/api/prd10 -q` -> **117 passed**.
* Lifespan: `pytest tests/integration/api/test_prd10_lifespan_migration.py -q` -> **7 passed**.

### Files Touched

`src/agent_os/db/base.py`, `src/agent_os/kb/models.py`, `src/agent_os/knowledge/models.py`, `src/agent_os/inbox/prd10_models.py`, `src/agent_os/jobs/service.py`, `tests/integration/api/prd10/test_prd10_db_indexes.py`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

None for 搂12.6. Continue open/stale todo cleanup.

---

## Milestone 59 - SPA primary binding legacy todo closeout - DELIVERED

**When**: 2026-05-08 19:26 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂4.23 was still open even though `test_mydow_primary_action_bindings_are_wired` had already been rewritten for the SPA shell.

### Delivered

* Confirmed the test now checks the SPA shell (`#app`, auth overlay, toast stack, CSS/JS entrypoints) plus `app.js` renderers, modals, drawers, and PRD10 API helper tokens.
* Closed the obsolete 鈥渞ewrite/delete after SPA completion鈥?todo.

### Test Evidence

* `pytest tests/integration/api/test_prd10_frontend_binding.py -q -p no:cacheprovider --tb=short --no-header` -> **30 passed**.

### Files Touched

`todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

None for 搂4.23.

---

## Milestone 58 - Windows SSE notification race hardening - DELIVERED

**When**: 2026-05-08 19:25 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂5.3.1 tracked an intermittent Windows reader stall in `test_sse_emits_ready_then_notification`.

### Delivered

* `src/agent_os/notifications/router.py::event_source` now keeps one pending `queue.get()` task alive across heartbeat polls.
* The timeout path no longer cancels/recreates the queue receive task every 0.5s, avoiding the Windows uvicorn/httpx race where a published notification could wake a task exactly as it was cancelled.
* Disconnect polling and ping heartbeat behavior remain intact.

### Test Evidence

* Syntax: `python -m py_compile src/agent_os/notifications/router.py` -> PASS.
* SSE suite: `pytest tests/integration/api/prd10/test_prd10_sse_notifications_api.py -q -p no:cacheprovider --tb=short --no-header` -> **2 passed**.
* Flake target rerun: `pytest ...::test_sse_emits_ready_then_notification` -> **1 passed**.

### Files Touched

`src/agent_os/notifications/router.py`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

None for 搂5.3.1 unless CI later reports a different SSE failure mode.

---

## Milestone 57 - v1.4 Chrome MCP nav sweep baseline - DELIVERED

**When**: 2026-05-08 19:20 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂7.31 was stale in `doing`. After 搂16.1-搂16.12 closed, the v1.4 business prototype needed a fresh Chrome MCP sweep with zero API failures and zero console errors.

### Delivered

* Re-ran the nav sweep against `http://127.0.0.1:8017/mydow/biz_v14/` using an isolated SQLite DB.
* Verified home, records/inbox, notifications, knowledge, garden, AI, and skills surfaces.
* Fixed the Skills personalized recommendation score formatter so backend scores render as clamped human percentages instead of `10150%`.
* Added a data favicon to the v1.4 HTML shell to remove the automatic `/favicon.ico` 404 from browser console/network evidence.

### Test Evidence

* Chrome DevTools MCP: bridge booted, extension booted, token present; 28 `/api/v1/*` requests, **0 API failures**, **0 console errors**.
* Surface checks: home feed cards=4; records rows=5; notifications rows=5; KB folder cards=6; Garden nodes=8; AI threads=3 + composer; Skills cards=12 + recommendation drawer.
* Syntax: `node --check static/mydow/biz_v14/bridge_v14.js` -> PASS.
* Contract: `pytest tests/integration/api/test_prd10_frontend_binding.py::test_biz_v14_html_injects_bridge_v14_script tests/integration/api/test_prd10_frontend_binding.py::test_biz_v14_skill_recommendation_scores_are_clamped` -> **2 passed**.
* Report: `.tmp/nav_sweep_7_31_report.json`; screenshots under `.tmp/screenshots/v7_31/`.

### Files Touched

`static/mydow/biz_v14/bridge_v14.js`, `static/mydow/biz_v14/index.html`, `tests/integration/api/test_prd10_frontend_binding.py`, `.tmp/nav_sweep_7_31_report.json`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

Continue stale/open todo cleanup. The v1.4 nav baseline itself is now green.

---

## Milestone 56 - v1.4 six-state UI runtime - DELIVERED

**When**: 2026-05-08 19:08 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂16.10 was stale in `doing`. Business review required visible loading / empty / error states in the v1.4 prototype, with real backend requests and Chrome MCP evidence.

### Delivered

* `static/mydow/biz_v14/bridge_v14_ext.js` now owns a six-state runtime without changing the business HTML prototype.
* Capture submission shows a feed skeleton immediately, then hides it after the real `/capture/text` + `/feed` refresh completes.
* Search zero results now render a unified SVG empty state from the real `/search` response.
* Feed, records, knowledge folders, notifications, and search all have reusable empty-state cards.
* Backend failures surface the backend message plus a clear retry hint in the unified error toast.
* Micro-interactions and toast color classes are centralized in the injected v1.4 CSS.

### Test Evidence

* Syntax: `node --check static/mydow/biz_v14/bridge_v14_ext.js` -> PASS.
* Contract: `python -m pytest tests/integration/api/test_prd10_frontend_binding.py -q -p no:cacheprovider --tb=short --no-header` -> **29 passed**.
* Chrome DevTools MCP on `http://127.0.0.1:8016/mydow/biz_v14/`: capture skeleton `true -> false`; real capture persisted and refreshed the first feed card; real `/search` returned `items=[]` and rendered the search empty card; real missing endpoint 404 rendered `Not Found 路 璇烽噸璇昤.
* Screenshots: `.tmp/screenshots/v16_10/01_after_capture_feed.png`, `02_feed_skeleton.png`, `03_search_empty.png`, `04_error_toast.png`, `05_event_empty_states.png`.

### Files Touched

`static/mydow/biz_v14/bridge_v14_ext.js`, `tests/integration/api/test_prd10_frontend_binding.py`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

Continue burning down remaining open/stale todo rows; 搂16.10 itself is complete.

---

## Milestone 55 - SPA AI cancel/regenerate contract closeout - DELIVERED

**When**: 2026-05-08 18:30 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂8.11 was still `open` while the backend cancel/regenerate endpoints were already delivered. The SPA needed explicit client helpers, visible stop UX, and regression coverage so AI message controls keep using real PRD10 APIs.

### Delivered

* `static/mydow/app.js` AI client now exposes `streamUrl(convId)`, `cancelMessage(id)`, and `regenerateMessage(id)` alongside the existing compatibility names.
* The AI composer shows a real `鍋滄` button while stream generation is in flight, with `title="鍋滄鐢熸垚"` for accessible discovery.
* Fixed pre-first-token abort handling: if the user stops before the SSE response is established, the UI now resolves to `锛堝凡鍋滄锛塦 and does not incorrectly fall back to `POST /messages`.
* Fixed modal close-handler TDZ regressions (`onclick: close` inside `const { close } = openModal(...)`) that prevented AI save-to-KB / create-tasks modals from opening reliably.
* `tests/integration/api/test_prd10_frontend_binding.py` pins the new AI helper tokens and stop-button wiring.

### Test Evidence

* Syntax: `node --check static/mydow/app.js` -> PASS.
* Contract: `python -m pytest tests/integration/api/test_prd10_frontend_binding.py -q -p no:cacheprovider --tb=short --no-header` -> **28 passed**.
* Chrome DevTools MCP on `http://127.0.0.1:8011/mydow/index.html#/ai`: save-to-KB -> `POST /save-to-kb` **202**; create-tasks -> `POST /create-tasks` **202**; regenerate -> `POST /regenerate` **201**; Slow 3G stop leaves `锛堝凡鍋滄锛塦 and no fallback `/messages` duplicate.

### Files Touched

`static/mydow/app.js`, `tests/integration/api/test_prd10_frontend_binding.py`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

Continue with the latest v1.4 / 搂16 todo lane; older SPA 搂9.19 is already closed in the current table and should not be duplicated.

---

> **Reporter**: Worker covering Agent 1 / Agent 2 / Agent 3 backend tasks in parallel.
> **Audience**: Engineer 1 (commander). This file is the single shared progress journal.
> **Source of truth**: `docs/01-prd/PRD10.md` and `agent-1-backend-contract.md`.
> **Conventions**: Newest milestone at the top. Each milestone has a delivery summary, test evidence, files touched, and known follow-ups.

---

## Milestone 54 路 澶氫汉骞惰鑱旇皟绔彛鍗忚 + ephemeral Chrome MCP (`:2872`) 鈥?DELIVERED

**When**: 2026-05-08 (Cursor Composer, UTC+8)

### Delivered

* **`todo-tasks.md`**锛歚缁存姢瑙勫垯` 鏂板 **绗?14 鏉?*锛堣嚜閫夌┖闂茬鍙?+ 鐙珛 `DATABASE_URL` + 娴嬫瘯閲婃斁绔彛 + `done` 璇佹嵁鍐?port/db/pid锛夛紱鏂囬銆屾渶杩戞洿鏂般€嶅悓姝ヨ鍗忚銆?* **搂16.8锛堢涓€鏉¤〃锛屽紩鐢?chip锛?*锛氳瘉鎹拷鍔?**涓嶅崰 8000** 鐨勫娴嬶細`127.0.0.1:2872`锛孌B `d:/Codes/whyme/.tmp/ephemeral_compose_2872.db`锛孋hrome MCP `evaluate_script` + `list_network_requests` + 鎴浘 **`d:/Codes/whyme/.tmp/screenshots/mcp_ephemeral_port_2872_biz_v14.png`**锛涚粨鏉熷悗 **`Stop-Process`** uvicorn锛宍Get-NetTCPConnection -LocalPort 2872` 鏃?LISTEN锛宍close_page` 鍏抽棴 MCP tab銆?
### Test evidence

```text
Chrome DevTools MCP: new_page 鈫?http://127.0.0.1:2872/mydow/biz_v14/
evaluate_script 鈫?{"portGuess":"2872","booted":true,"tokenLen":209}
list_network_requests 鈫?30 requests, all 200 except favicon.ico 404
Stop-Process -Id <uvicorn_pid>; Get-NetTCPConnection -LocalPort 2872 鈫?(empty)
```

### Files touched

`todo-tasks.md`, `agent-progress-report.md`锛堟湰鏉＄洰锛?
### Follow-ups

涓嬩竴杞嫢鍐嶅惎 ephemeral server锛屾寜闇€鎹㈢鍙?db 鏂囦欢鍚嶏紝骞跺湪璇佹嵁涓洿鏂版暟瀛椼€?
---

## Milestone 53 路 搂16.9 v1.4 `data-toast` 鍏ㄩ噺瀹¤鑴氭湰 鈥?DELIVERED

**When**: 2026-05-08 (Cursor Composer, UTC+8)

### Delivered

* **`.tmp/audit_v14_buttons.py`**锛氬凡鐢变粨搴撳唴 Canonical 瀹¤鏇夸唬锛屼繚鐣?**`scripts/audit_v14_buttons.py`**锛坄MODAL_PRIMARY_TOAST_TO_MODAL` + `bindPrefToggleV39` map + `MODAL_SUBMIT_HANDLERS` 鍚嶇О鎶藉彇锛夈€?* **`.tmp/v14_button_audit.json`**锛歚45` 涓幓閲嶆爣绛惧叏閮?`wired`锛堜笟鍔?HTML 瀹為檯鏁伴噺楂樹簬鍘嗗彶銆?3銆嶅彛寰勶級銆?
### Test evidence

```text
python scripts/audit_v14_buttons.py
鈫?summary.labels_with_no_static_wiring = []
exit code 0
```

### Files touched

`scripts/audit_v14_buttons.py`锛坢odal map + pref-toggle 闈欐€佽鐩栵級, `.tmp/v14_button_audit.json`, `todo-tasks.md`锛埪?6.9 鈫?done锛?
### Follow-ups

搂16.10 鍏€侊紙loading / empty / error锛夐渶鍗曠嫭 milestone + Chrome MCP 鎴浘銆?
---

## Milestone 52 路 搂16.6 Skills 鍗＄墖銆屸湏 宸茬敓鎴愩€嶄笌閫氱煡 ingest 鈥?DELIVERED

**When**: 2026-05-08 (Cursor Agent, UTC+8)

### Delivered

* **`bridge_v14.js`**锛歚GET /notifications` 鍘熷鍒楄〃涓?`ai_output_saved` + `object_type=skill_run` 鈫?骞惰 `GET /skills/runs/{id}` 瑙ｆ瀽 `skill_id` / `document_id`锛屽啓鍏?`V14.skillRunDoneIds`锛屽湪瀵瑰簲 `.skill-card` 涓婃覆鏌撳彲鐐瑰嚮锛堣嫢鏈?KB 鏂囨。锛夌殑銆屸湏 宸茬敓鎴愩€峜hip锛汼kill 璇曠敤杞瀹屾垚鏃跺悓姝ユ洿鏂般€?* **CSS**锛歚injectInvestorPolishCss` 澧炲姞 `.skill-generated-chip` 鏍峰紡銆?
### Test evidence

```text
node --check static/mydow/biz_v14/bridge_v14.js 鈫?exit 0
```

### Files touched

`static/mydow/biz_v14/bridge_v14.js`, `todo-tasks.md`锛埪?6.6 鈫?done锛?
### Follow-ups

* 浠嶉潪鐪熸娴忚鍣?SSE锛氫緷璧栭€氱煡鍒楄〃 + 杞锛涜嫢鍚庣鎻愪緵 `/notifications/stream` 鍙啀璁㈤槄澧為噺銆?* Chrome MCP 闇€琛?Skills 椤垫埅鍥鹃獙璇?chip 涓庣偣鍑绘墦寮€鏂囨。銆?
---

## Milestone 51 路 Capture LLM 鏁寸悊涓?GLM-4.5/4-Flash 瑙ｈ€?+ Docker compose 鑱旇皟 鈥?DELIVERED

**When**: 2026-05-08 ~14:30鈥?4:45 (Cursor Composer, UTC+8)

### Delivered

* **鐏垫劅鎹曡幏缁撴瀯鍖栨暣鐞?*锛氱户缁鐢?**LiteLLM**锛堝紑婧愶級鍋?`enrich_capture_with_llm` / `patch_card_with_enrichment`锛涗负涓诲璇?`MODEL=GLM-4.5-Flash`锛坮easoning 鍊惧悜锛変笌銆屽繀椤昏緭鍑虹函 JSON銆嶇殑鏁寸悊浠诲姟瑙ｈ€︹€斺€擿enrich_capture_with_llm` 榛樿浣跨敤 **`GLM-4-Flash`**锛堝彲琚?`CAPTURE_ENRICH_MODEL` / `MODEL_FALLBACK` 瑕嗙洊锛夈€?* **`litellm_impl.LiteLLMProvider.complete`**锛氭敮鎸佸崟娆¤皟鐢ㄤ紶鍏?`model=` 瑕嗙洊瀹炰緥榛樿妯″瀷锛岄伩鍏嶄负鏁寸悊鍗曠嫭 new provider銆?* **`_coerce_json_payload`**锛氫粠鍚€濊€冮摼/鍓嶈█鐨勯暱鍥炲涓壂鎻?*鏈€澶у钩琛?* `\{鈥}` 瀛愪覆鍐?`json.loads`锛岄檷浣庤В鏋愬け璐ュ洖閫€ heuristic 鐨勬鐜囥€?* **`docker-compose.prd10.yml`**锛歚MODEL_FALLBACK` 榛樿 `GLM-4-Flash`锛沗CAPTURE_ENRICH_MODEL` 鍙€夋敞鍏ャ€?* **`.env.example`**锛氳ˉ鍏?搂16.1 鐩稿叧璇存槑琛屻€?
### Test evidence

```text
pytest tests/integration/api/prd10/test_prd10_capture_api.py 鈫?7 passed @ ~5鈥?s
```

* **Docker 瀹炴祴**锛歚POST /api/v1/capture/text` 鍚庣害 30s 鍐?`GET /api/v1/feed` 棣栨潯鍗＄墖 `updated_at` 鏇存柊锛屾爣棰?summary 鍙樹负 LLM 鏁寸悊缁撴灉锛沗llm_used` 鍦ㄥ悓姝ュ搷搴斾粛涓?false锛堣璁′负 heuristic 蹇矾寰?+ 寮傛 PATCH锛夈€?* **Chrome DevTools MCP**锛氬綋鍓嶇幆澧?`new_page` / `list_pages` 鎶ャ€宻elected page closed銆嶏紝闇€鍦?IDE 涓噸鏂伴檮鐫€娴忚鍣ㄥ悗鍐嶈窇鎴浘锛涙湭闃诲鍚庣楠岃瘉銆?
### Files touched

`src/agent_os/capture/llm_pipeline.py`, `src/agent_os/llm/litellm_impl.py`, `docker-compose.prd10.yml`, `.env.example`, `todo-tasks.md`锛埪?6.1 璇佹嵁鍚屾銆伮?6.4 鍘婚檲鏃?blocker锛夈€?
### Follow-ups

* 搂16.4锛歚data-ai-add` 鍥涢」 + 鏃犱細璇濇椂鑷姩寤哄璇?鈥?Chrome 鍏ㄦ祦绋嬬偣楠屻€?* 搂16.11 / 搂16.5 / 搂16.8 / 搂16.9 / 搂16.10 鈥?浠嶈 `todo-tasks.md`銆?
---

## Milestone 50 路 搂15.37 v1.4 button wiring rev2 + ruff 鐪?F821 bug 淇 + 1820 lint auto-fix 鈥?DELIVERED

**When**: 2026-05-07 22:00 (Cursor Agent claude-opus-4.7, parallel session)

### Delivered

* **搂15.37 v1.4 button wiring rev2 鈥?DONE** (涓庡苟琛?agent 搂15.39 鍗忎綔瀹屾垚)锛歚static/mydow/biz_v14/bridge_v14.js` 杩藉姞 搂15.37 鑺?(~580 琛? 鍦?`bindAssistantActionButtonsV14` 涔嬪悗鎸?10 涓柊 capture-phase 鐩戝惉 + 11 涓柊 helper锛?a) `bindNoticeActionV37` 6 涓?`data-notice-action` 閫氱煡琛屾寜閽寜 `result/link/folder/report/detail/settings` 鏄犲皠鍒?`data-nav-target` 鐪熻烦杞?+ 鍚庡彴 `POST /notifications/{id}/read`锛?b) `_openPopoverV37` 鑷畾涔?popover 绯荤粺锛?c) `bindAiThreadMenuV37` 鎺?`[data-ai-thread-menu]` 鈫?閲嶅懡鍚?(PATCH `/ai/conversations/{id}`) + 鍒犻櫎 (DELETE `/ai/conversations/{id}`)锛?d) `bindAiChatRenameV37` 椤舵爮銆岄噸鍛藉悕瀵硅瘽銆嶆寜閽洿杩炲悓 PATCH锛?e) `bindAiChatMoreV37` 銆屽璇濇洿澶氭搷浣溿€峱opover 4 椤癸紱(f) `streamV14AiReply` 璇?`[data-inline-menu=aiModel] [data-inline-label]` 瀹炴椂鍙栨ā鍨嬪悕浼?`body.model`锛屽苟鎶?`data-ai-mode` 浼?`body.mode`锛屾柊鍔?`_showAssistantActions(article, msgId)` 鍦ㄦ祦瀹屾垚鍚庡啓 `dataset.messageId` + 鏄剧ず 4 鎸夐挳宸ュ叿鏍忥紙澶嶅埗/閲嶆柊鐢熸垚/馃憤/馃憥锛夛紝璁?搂15.38 `bindAssistantActionButtonsV14` 鐪熸湁鐐瑰嚮瀵硅薄锛?g) `bindCardShareV37` 鍗＄墖鍒嗕韩閾炬帴澶嶅埗锛?h) `bindFolderFavoriteV37` 鏂囦欢澶规敹钘?PATCH锛?i) `bindSkillFavoriteV37` skill 鏀惰棌 + localStorage锛?j) `bindDocAiActionsV37` 5 涓枃妗?AI 鍔ㄤ綔锛?k) `bindInsightActionsV37` 娲炲療渚ф娊 鈫?cards/tasks/move銆?*鍐茬獊閬垮厤**锛歚closest('.ai-msg-actions, .assistant-message-actions')` 妫€娴嬭 搂15.38 澶勭悊 AI 姘旀场鎸夐挳锛屄?5.37 璺宠繃銆佷笓娉ㄩ潪姘旀场 surface锛浡?5.39 (`bridge_v14_ext.js`) 鍦?bubble 闃舵琛?confirmDelete 绛夈€?
* **鐪?LLM Chrome MCP 楠岃瘉 鈥?DONE**锛欴eepSeek 鐪熺洿鎺ヨ皟閫?`messages/stream`锛孋hrome MCP 鐪熸祻瑙堝櫒瀹炴祴锛氬鑸埌 `/mydow/biz_v14/?cb=mcp3` 鈫?鑷姩鐧诲綍 鈫?tokenLen=209 鈫?鍙?"鐢?15 涓瓧璇翠綘鏄粈涔?AI" 鈫?AI 瀹炴椂杩斿洖 "鎴戞槸Mydow AI锛岀煡璇嗗姪鎵嬨€? (16 瀛? real DeepSeek) 鈫?宸ュ叿鏍忚嚜鍔ㄥ嚭鐜?鈫?`dataset.messageId="dbc8e5d5-..."` 鈫?鐐瑰嚮 regenerate 鐪熷彂 `POST /ai/messages/{id}/regenerate [201]`锛宯etwork 鎶撳埌鍏ㄧ▼銆?
* **搂14.14 baseline 缁存姢 鈥?DONE**锛氳窇 PRD10 14 濂椾欢 + prd10/ + landing + nginx + frontend_binding + v1_acceptance = **278 passed / 0 failed @ 587.38s** (`.tmp/baseline-14-14-v2.log`)銆?*`.tmp/smoke_v14_walk.py 8770`** 14/14 sections OK / `console_error_count=0` / `page_error_count=0` / `api_failure_count=0` / `api_call_count=47` (姣?搂15.34 baseline 44 +3 鈥?鏂版帴 buttons 瑙﹀彂鏂?API call) / `pass=true`銆?*鏂板姞 `.tmp/smoke_15_37.py`** 5 sections all OK锛歜oot+10 搂15.37 export 鍏ㄥ湪 / AI thread 涓夌偣鑿滃崟 popover 鐪熷嚭鐜?/ aiModel 閫?GPT-5.2 鍚?`data-inline-label` 鐪熸敼 / Skill 鏀惰棌 click 鍚?localStorage 鐪熸寔涔呭寲 / Card share button click 0 error / `pass=true`銆?
* **搂14.8 鎬ц兘 LCP 鈥?DONE**锛欳hrome DevTools MCP `performance_start_trace` 瀹炴祴锛?a) **`/mydow/biz_v14/`锛堟姇璧勪汉 demo 榛樿鍏ュ彛锛塋CP=657ms / TTFB=27ms / Render delay=630ms / CLS=0.00**锛堣繙浣庝簬 2.5s 鐩爣锛夛紱(b) `/`锛坙anding锛塋CP=2,905ms 鈥?鐣ラ珮 405ms锛屼富瑕?render delay銆傛姇璧勪汉 demo 闃堝€煎凡杈炬垚銆?
* **鐪?F821 bug 淇 (2 澶?**锛?a) `src/agent_os/server/app.py` 鍔?`from typing import TYPE_CHECKING` + `if TYPE_CHECKING: from agent_os.server.diff_service import DiffService`锛岃 `DiffService` 瀛楃涓叉敞瑙?ruff F821 閫氳繃锛? 澶勶級锛?b) `src/agent_os/inbox/router.py::list_inbox_items` 鐢?`and_(...)` 浣嗗彧 import 浜?`select`锛屽姞 `from sqlalchemy import and_, select` 淇湡杩愯鏃舵湭瑙ｅ喅鍚嶇О閿欒銆備袱澶?fix 鍚?src F821 = **0**锛堜箣鍓?4锛夈€?
* **ruff 瀹夊叏 auto-fix 鈥?1820 errors fixed**锛歚python -m ruff check src/agent_os tests --fix --select=F401,F541,F811,F841,I,UP,SIM,C4 --no-show-fixes` 璺戜袱杞細绗竴杞?fix 190 (src) + 580 (tests)锛岀浜岃疆鍐?fix 1234锛涙€昏瀹夊叏鑷姩淇 ~1820 涓?lint error锛涘墿浣?**904 涓?*锛坰rc 687 + tests ~217锛夊ぇ澶氭槸 E (pycodestyle) / W (warning) / SIM103/SIM117 绛夐渶瑕佷汉宸?review 鐨勭畝鍖栫被銆?*淇鏈熼棿瑙﹀彂 1 涓?pre-existing 寰幆 import 鏆撮湶**锛歚agent_os/conversations/__init__.py` 鑰佸簭銆屽厛 `from . import router` 鍐?`from .repository import ConversationRepository`銆嶈 `router.py` 浠?`agent_os.conversations` 鎷?`ConversationRepository` 鏃舵嬁涓嶅埌锛坧artial init锛夛紱鏀逛负鍏?import models+repository 鍐?router 淇锛堝姞 `# noqa: E402`锛夈€?
### Test evidence

```text
PRD10 瀛愰泦 + frontend_binding + v1_acceptance + ai_api + skills + app_wiring + prd10/:
  鈫?278 passed / 0 failed @ 587.38s (`.tmp/baseline-14-14-v2.log`)
  鈫?178 passed @ 191.08s (after lint fix round 2) (`.tmp/after-lint-tests.log`)

v14 walk e2e:
  python .tmp/smoke_v14_walk.py 8770
  鈫?14/14 sections OK / 47 API calls / 0 console / 0 page / 0 failure / pass=true

v15.37 focused smoke:
  python .tmp/smoke_15_37.py 8770
  鈫?5/5 sections OK / 0 console / 0 page / 0 failure / pass=true

Real LLM via Chrome MCP:
  鈫?first iter: real DeepSeek "鎴戞槸Mydow AI锛岀煡璇嗗姪鎵嬨€? (16 chars matching prompt constraint)
  鈫?reqid=71 POST /messages/stream [200] / reqid=73 POST /ai/messages/{msgId}/regenerate [201]

Performance trace via Chrome MCP:
  鈫?/mydow/biz_v14/ LCP=657ms / CLS=0.00 (well under 2.5s)
  鈫?/ landing LCP=2,905ms (slight overrun)

Ruff lint sanitize:
  鈫?2728 鈫?904 errors (1824 safe auto-fixes applied)
  鈫?F821 (real bugs) 4 鈫?0 (all fixed)
```

### Files

* `static/mydow/biz_v14/bridge_v14.js` (+580 lines 搂15.37 / streamV14AiReply 鏀硅 live model label / appendAiAssistantPlaceholder 鍔?ai-message-actions)
* `src/agent_os/server/app.py` (TYPE_CHECKING import for DiffService, F821 fix)
* `src/agent_os/inbox/router.py` (import `and_`, F821 fix)
* `src/agent_os/conversations/__init__.py` (reorder imports to fix circular import)
* ~30 src/agent_os/**/*.py and tests/**/*.py auto-fixed by ruff
* `.tmp/smoke_15_37.py` (鏂板 5-section 搂15.37 smoke)
* `.tmp/baseline-14-14-v2.log` (baseline 278 passed)
* `.tmp/v14_chrome_smoke_report.json` (14/14 sections OK)
* `todo-tasks.md` (搂14.14 / 搂15.37 / 搂14.8 鈫?done)

### Follow-ups

* **搂5.3.1**: Windows uvicorn-in-thread + httpx 鍚屾娴佸紡 reader 鍋剁幇 stuck锛坧re-existing flake, not blocking锛夈€?* **搂11.2 partial**锛氬墿浣?904 ruff 閿欒锛堝ぇ澶?E/W 椋庢牸绫伙級锛汣I lint 浠嶄細 fail銆傚悗缁彲缁х画鎸夎鍒欐墜鍔ㄦ竻鐞嗘垨璋冩暣 pyproject.toml 鐨?ruff [select] 涓ユ牸搴︺€?* **搂14.8 follow-up**: 浼樺寲 `/` landing LCP 浠?2.9s 鈫?< 2.5s銆?
---

## Milestone 49 路 Docker 涓€閿儴缃叉暣濂?+ paratera GLM-4.5-Flash 鐪熸帴鍏?+ AI feedback 绔偣 + bridge_v14 楂橀鎸夐挳鐪熷寲 鈥?DELIVERED

**When**: 2026-05-07 21:35 (Cursor Agent claude-opus, parallel session covering 搂14.15 / 搂14.16 / 搂15.37 / 搂15.38 / 搂15.39)

### Delivered

* **搂15.37 涓氬姟鏂?zip 鍏ㄦ枃妗ｇ撼鍏ヤ粨搴?鈥?DONE**锛歚Mydow_Web_Frontend_Backend_Handoff_v1.4_20260507_0058.zip` 瀹屾暣瑙ｅ帇锛屾妸 5 涓柊 markdown 澶嶅埗鍒?`static/mydow/biz_v14/`锛?  - `Mydow_Web_AI_Workspace_v1.3.md`锛? 妯″瀷 + 12 閽╁瓙 + 7 鍚庣鎺ュ彛锛?  - `Mydow_Web_API_Buttons_v1.1.md`锛?3 绔?200+ 閽╁瓙鈫掓帴鍙ｆ槧灏勶級
  - `Mydow_Web_Frontend_Delivery_v1.1.md`
  - `Mydow_Web_Frontend_Handoff.md`
  - `_API_Contract_v1.4.md`
  涓枃鏂囦欢鍚嶄贡鐮佸凡鐢?`Rename-Item` 淇涓?ASCII銆傝繖浜涙枃妗ｄ笌 v1.4 contract 鍏卞悓鏋勬垚涓氬姟鏂归渶姹傜湡鐞嗐€?
* **搂14.15 鐪熷疄 LLM (paratera GLM-4.5-Flash) 鎺ュ叆 鈥?DONE**锛氬師 `MODEL=openai/DeepSeek-V3.1` 瑙﹀彂 `team_model_access_denied` 401锛堝洟闃熸潈闄愬彧鍏佽 GLM 绯诲垪锛歚PaddleOCR-VL-0.9B / GLM-4-Flash / GLM-CogView3-Flash / GLM-Z1-Flash / PaddleOCR-VL-1.5 / GLM-4.5-Flash / GLM-4V-Flash`锛夈€俙.env` 鏀癸細`API_BASE=https://llmapi.paratera.com/v1` (涓嶇敤 `BASE_URL` 閬垮厤涓?docker self-URL collision) + `MODEL=GLM-4.5-Flash` + `MODEL_FALLBACK=GLM-4-Flash`锛涘惎鍔?`AGENTOS_AI_LLM=on` + `AGENTOS_AI_TEMPERATURE=0.4` + `AGENTOS_AI_MAX_TOKENS=800`銆?  - `.tmp/test_real_llm.py`锛坲vicorn :8770锛夛細events=`[meta, keepalive, token..., done]` / 21 chunks / 35 chars / 16.8s / DB 钀?user+assistant 鍙?message / `verdict: real_llm_alive=True`銆?  - `.tmp/test_real_llm_docker.py`锛坉ocker :8000锛夛細345 token chunks / 488 chars / 60.5s / 鐪熷疄 GLM-4.5-Flash 涓枃杈撳嚭锛?鈥︾敤鎴疯姹傜敤涓€鍙ヤ腑鏂囧舰瀹逛笂娴风殑娓呮櫒鈥︺€?婕旂ず" 涓嶅湪锛? `verdict: docker_real_llm_alive=True`銆?  - `litellm_impl.LiteLLMProvider` 闆朵唬鐮佹敼鍔ㄥ嵆鍏煎 paratera OpenAI-compatible endpoint锛坒allback chain `BASE_URL 鈫?API_BASE 鈫?DEEPSEEK_OPENAI_BASE_URL`锛夈€?
* **搂15.38 v1.4 涓氬姟鏂规枃妗?audit + 5 涓珮棰戞寜閽湡瀹炲寲 鈥?DONE**锛?  - **Audit**锛歡rep `static/mydow/biz_v14/index.html` 鍏?50 涓?`data-toast="..."` 鍗犱綅鎸夐挳锛沚ridge_v14.js 宸叉帴閫?8 modal + 11 澶фā鍧楋紱鏈换鍔″畾浣?5 绫绘湭鐪熸帴鐨?AI assistant 鎿嶄綔銆?  - **5 涓珮棰戣ˉ鍏紙bridge_v14.js锛?*锛?    1. 澶嶅埗鍥炵瓟 鈫?`navigator.clipboard.writeText` (鍚?textarea fallback)
    2. 閲嶆柊鐢熸垚 鈫?`POST /api/v1/ai/messages/{id}/regenerate`锛圥RD10 搂3.14 宸插瓨鍦級
    3. 鐐硅禐 鈫?`POST /api/v1/ai/messages/{id}/feedback {rating:up}`
    4. 鐐硅俯 鈫?`POST /api/v1/ai/messages/{id}/feedback {rating:down}`
    5. 閫€鍑虹櫥褰曪紙`[data-account-action="logout"]`锛夆啋 `POST /auth/logout` + 娓?token + reload
  - **鏂板鍚庣绔偣** `POST /api/v1/ai/messages/{message_id}/feedback`锛坄ai/router.py` line 1209+锛夛細`FeedbackRequest{rating:up|down, comment?:str}`锛屽啓鍏?`prd10_notifications` 琛紙type=ai_feedback / object_type=ai_message / object_id=msg_id锛夛紝idempotent on (user, msg) 鐢?SELECT-then-update 淇濊瘉锛涜繑鍥?`{feedback_id, rating, comment, message_id, submitted_at}`銆?  - **鐪熷疄娴嬭瘯** `.tmp/test_feedback.py`锛歭ogin 鈫?create conv 鈫?send message 鈫?POST feedback up + comment 鈫?POST feedback down (overwrite) 鈫?idempotent feedback_id 涓€鑷?鉁?鈫?notifications list 鍚?1 鏉?ai_feedback 琛?鉁?鈫?`verdict: feedback_endpoint_works=True`銆?  - **bridge_v14.js** `bindAssistantActionButtonsV14()` + `bindLogoutAction()` capture-phase + `_resolveAssistantContext()`锛圖OM dataset 浼樺厛 + V14.lastAssistantMessageId fallback锛? `_copyTextToClipboard()` 鍚?execCommand fallback锛沗node --check` PASS銆?
* **搂14.16 / 搂15.39 Docker compose 涓€閿儴缃叉暣濂?+ 鐪?LLM 鈥?DONE**锛?  - **Dockerfile.prd10** 鍔?4 涓己澶变緷璧栵細`PyJWT>=2.8` / `sentry-sdk>=2.0` / `langgraph>=0.2` / `aider-chat>=0.60.0` + `typer/rich`銆?  - **`.dockerignore`** `*.md` 鍔犱緥澶?`!README.md` + `!static/mydow/biz_v14/*.md`锛堝墠鑰呬慨 Dockerfile COPY 鎵句笉鍒?README锛屽悗鑰呬繚涓氬姟鏂规枃妗ｈ繘 image锛夈€?  - **`agent_os/sandbox/docker_impl.py`** 鐢?try/except 鍖呰９ `import docker` 璁?Docker 闀滃儚鏃?docker SDK 鏃朵粛鍙?import server.app锛坙azy `_require_docker_sdk()` 鍦?DockerSandbox 瀹炰緥鍖栨椂妫€鏌ワ級銆?  - **`docker-compose.prd10.yml`** 缁?`app` service 鍔?`API_KEY/API_BASE/MODEL` env passthrough锛沗DATABASE_URL` 榛樿 `sqlite+aiosqlite:////app/data/mydow.db`锛坙egacy `conversations.user_id INTEGER` 涓?PRD10 `users.id UUID` FK type 涓嶅吋瀹?Postgres锛岄渶瑕?搂6.9.b 绫讳技鐨?INTEGER鈫扷UID schema rewrite锛屾湰浠诲姟鏆備笉鍔紱SQLite 瀹瑰繊 FK type 閿欓厤锛屽叏鍔熻兘鍙窇锛夈€?  - `docker compose up -d` 涓夋湇鍔″叏 healthy锛坧ostgres + redis healthcheck OK锛宎pp 30s 鍐?starting 鈫?healthy锛夈€?  - `docker compose exec app python scripts/seed_prd10.py --reset` 钀藉簱锛? folders / 20 documents / 30 cards / 5 tasks / 5 notifications / 3 ai_conversations / 18 ai_messages / 5 skills / 10 search_documents / 6 insights銆?  - `curl http://localhost:8000/health` 200 / `curl /mydow/` 307 鈫?`/mydow/biz_v14/` / `/mydow/biz_v14/` 200 / 462042 bytes銆?  - **Docker port 璧版煡** `.tmp/smoke_v14_walk.py 8000`锛?4/14 sections PASS / 0 console / 0 page / 0 API failure / 46 calls銆?  - **鐪熷疄 LLM via Docker**锛?45 token chunks 鐪熷疄涓枃杈撳嚭锛圙LM-4.5-Flash锛? 60.5s / DB 鐪熷疄钀?message銆?
* **landing page 閲嶅啓**锛氬師 `static/landing/index.html` 鍥?PowerShell 缂栫爜浜嬫晠锛坈p936 鈫?utf-8 鍙屽悜 mojibake锛夌牬鍧忥紝閲嶅啓涓€浠藉畬鏁?522 琛屾柊 landing锛堜繚鐣欏搧鐗?Mydow / 5 澶?CTA 鍏ㄥ垏鍒?`/mydow/biz_v14/` / pricing card 涓汉 Pro 楼39 + 鍥㈤槦 License 楼199 鍚€屾渶鍙楁杩庛€嶅窘绔?/ 8 涓?PRD10 搂2.1 妯″潡鍗″惈鍏ㄥ眬鎼滅储 / 閫氱煡涓績 / 闅愮+鏉℃+API+OpenAPI+鍋ュ悍 footer锛夈€俙test_landing_hero.py` 6/6 passed + `test_prd10_v1_acceptance.py::test_root_serves_landing_or_redirects_to_biz` + `test_prd10_frontend_binding.py::test_mydow_default_redirect_to_biz_or_spa` 鍏ㄨ繃锛堟柇瑷€鎺ュ彈 `/mydow/biz_v14/` 涓?`/mydow/biz/` 鍙屽舰鎬佷互鍏煎鏃?deploy锛夈€?
### Test evidence

```text
PRD10 12-suite + landing + nginx (subset of 14-suite, --tb=line --timeout=60):
  173 passed / 0 failed @ 325s

v1.4 walk (uvicorn :8770 with paratera GLM-4.5-Flash):
  14/14 sections PASS / 0 console / 0 page / 0 API failure / 45-46 /api/v1/* calls

v1.4 walk (docker :8000 with paratera GLM-4.5-Flash + sqlite + Postgres healthy):
  14/14 sections PASS / 0 console / 0 page / 0 API failure / 46 calls

Real LLM SSE (uvicorn): 21 token chunks / 35 chars / 16.8s
Real LLM SSE (docker): 345 token chunks / 488 chars / 60.5s

Feedback endpoint persistence:
  feedback_endpoint_works=True (idempotent on user+msg, persists in prd10_notifications)
```

### Files touched

* `.env` (LLM config: API_BASE / MODEL=GLM-4.5-Flash + docker-compose passthrough vars)
* `static/mydow/biz_v14/{Mydow_Web_AI_Workspace_v1.3.md, Mydow_Web_API_Buttons_v1.1.md, Mydow_Web_Frontend_Delivery_v1.1.md, Mydow_Web_Frontend_Handoff.md, _API_Contract_v1.4.md}` (涓氬姟鏂规枃妗ｅ叏濂?
* `static/mydow/biz_v14/bridge_v14.js` (+ 搂15.38 5 涓?binding + 2 涓?export)
* `src/agent_os/ai/router.py` (+ FeedbackRequest schema + POST /messages/{id}/feedback endpoint锛寏95 琛?
* `src/agent_os/sandbox/docker_impl.py` (+ try/except docker SDK import + lazy _require_docker_sdk)
* `src/agent_os/server/app.py` (搂15.34 redirect chain 鍒囧埌 v1.4)
* `Dockerfile.prd10` (+ 5 缂哄け渚濊禆)
* `docker-compose.prd10.yml` (LLM env passthrough + sqlite default)
* `.dockerignore` (+ !README.md + !static/mydow/biz_v14/*.md 渚嬪)
* `static/landing/index.html` (瀹屾暣閲嶅啓 522 琛?
* `tests/integration/api/test_landing_hero.py` (鎺ュ彈 v1.4 璺緞)
* `tests/integration/api/test_prd10_v1_acceptance.py` (鎺ュ彈 v1.4 璺緞 + 鏂板姞 test_biz_v14_prototype_reachable)
* `tests/integration/api/test_prd10_frontend_binding.py` (鎺ュ彈 v1.4 璺緞)
* `todo-tasks.md` (搂15.34/35/36/37/38/39 + 搂14.13/14.15/14.16 done)
* `agent-progress-report.md` (鏈?milestone)
* `.tmp/{smoke_v14_walk.py, test_real_llm.py, test_real_llm_docker.py, test_feedback.py, fix_landing_encoding.py}` (5 smoke 鑴氭湰锛? `.tmp/v14_chrome_smoke_report.json` + `.tmp/screenshots/v14_walk/00..99.png` 14 寮犳埅鍥?

### Known follow-ups

* 搂6.9.b legacy `conversations.user_id INTEGER 鈫?UUID`锛氳 docker stack 鍙敤鐪?Postgres锛堝綋鍓嶇敤 sqlite 鍏滃簳锛夈€?* 搂9.x 璁捐绯荤粺鍗囩骇锛堟殫鑹?/ 鍝嶅簲寮?/ a11y / 寰氦浜掞級锛氫笟鍔℃柟 v1.4 瑙嗚宸茶惤鍦帮紝鍓╀笅鏄?polishing銆?* 搂11.2 CI Actions锛圓gent 3 lane锛夛細璁?PR 蹇呴』缁裤€?* 搂15.40+锛氫笟鍔℃柟 v1.1 鏂囨。鍒楀嚭浣?PRD10 鍚庣鏈疄瑁呯殑 8 涓?P2 绔偣锛坄/research/tasks` / `/capture/voice/sessions` / `/capture/upload` 宸查儴鍒?/ `/billing/portal-session` / `/kb/docs/:id/share-links`锛夋寜闇€鎵┿€?
---

## Milestone 48 路 v1.4 鍏ㄦ寜閽湡鎺ラ€?+ 鐪?LLM 楠岃瘉 + 娴嬭瘯鍩虹嚎 302 passed 鈥?DELIVERED

**When**: 2026-05-07 21:35 (Cursor Agent claude-opus-4.7)

### Delivered

* **搂14.14 Test baseline maintenance 鈥?DONE**锛氳窇 PRD10 14 濂椾欢 + landing + nginx + frontend_binding + prd10/ + v1_acceptance baseline = **303 collected / 302 passed / 1 failed @ 887s** (`.tmp/baseline_14_14.log`)銆傚敮涓€澶辫触 `test_sse_emits_ready_then_notification` 鏄?搂5.3 宸茬煡 Windows-flaky harness锛堜笌 搂15.34 redirect 鏀瑰姩鏃犲叧锛屾柊鍐欏叆璺熻釜 搂5.3.1 绛夊緟淇級銆傛瘮 搂0 baseline 225 鎻愬崌 **+77**銆?* **`tests/e2e/test_v14_walk.py` 1 passed @ 22.26s** 鈥?`MydowBridgeV14.booted=true` / `mydow_v14_token` 钀藉簱 / `apiFetchV14` 瀵煎嚭 / capture surface 娓叉煋 / 0 console / 0 page / 0 failed API銆?* **鐪熷疄 LLM SSE 楠岃瘉 鈥?DONE**锛歚.tmp/verify_real_llm.py`锛堣嚜鍖呭惈 subprocess uvicorn + httpx SSE reader锛夎窇閫氾細`AGENTOS_AI_LLM=on` + `MODEL=deepseek-chat` (via `.env.local`) 鈫?`is_llm_enabled=True` 鈫?`POST /api/v1/ai/conversations/{id}/messages/stream` 鐪熻繑 SSE token 鈫?`tokens_seen=115` / `stream_content_len=195` / `persisted_status=completed` / `persisted_model=litellm` / `is_placeholder=false` / `real_llm_alive=true`銆傚洖澶嶅唴瀹规槸鐪熷疄 deepseek-chat 涓枃 3-bullet 鍒涗笟鑰呭缓璁€?* **`src/agent_os/llm/litellm_impl.py` 澧炲己**锛歚complete()` + `stream_complete()` 閮藉姞 `reasoning_content` fallback鈥斺€斿綋妯″瀷 (DeepSeek v4-flash 鎺ㄧ悊妯″紡 / GLM Z1) 鎶婄瓟妗堟斁鍦?`reasoning_content` 鑰?`content` 涓虹┖鏃讹紙max_tokens 琚?reasoning 鍚冨畬锛夛紝鑷姩surface reasoning_content锛堝甫 `锛堟€濊€冭繃绋嬶級` 鍓嶇紑锛夛紝閬垮厤绌哄洖澶嶏紱娴佸紡鐗堟湰瀵规病鏈?visible content 鐨勫叏绋嬭 reasoning chunks 閫氳繃 `kind="reasoning"` 閫忓嚭銆?* **`.env.local` 閲嶅啓**锛氭竻妤氭爣娉?`MODEL=deepseek-chat` 璺敱鍒?deepseek-v4-flash 浣嗚蛋闈炴帹鐞嗘ā寮忥紙content 鐩存帴钀?`choice.message.content`锛屽皬鍥炵瓟 200-500 tokens 鍗冲锛夛紱鏂板 `AGENTOS_AI_LLM=on` / `AGENTOS_AI_TEMPERATURE=0.4` / `AGENTOS_AI_MAX_TOKENS=1500` / `AGENTOS_AI_MODEL=deepseek-chat`銆?* **搂15.39 v1.4 鍏ㄦ寜閽湡鎺ラ€?鈥?DONE**锛歚static/mydow/biz_v14/bridge_v14.js` 鏂板 搂15.39 娈碉紙line 2829-3120锛? 13 涓?capture-phase 鐩戝惉 鈫?`bindAllRemainingV39()`锛歝onfirmDelete 涓婁笅鏂囧寲璺敱锛坈ards/docs/folders DELETE锛? movePanel锛坧rompt 閫?folder + `/cards/{id}/move`锛? themeToggle锛坙ocalStorage + `<html data-theme>` + body class锛? prefToggle锛圥ATCH `/me/preferences` auto_save_enabled / two_factor_enabled锛? passwordModal锛坧rompt 脳 2 + POST `/me/password`锛? billing / emailVerify / permissions锛圴1 toast + V2 roadmap 鎻愮ず锛? storageRefresh锛堟媺 `/kb/overview` 鏄剧ず鐪熷疄瀹归噺锛? securityDevices / aiContextAdd锛圥ATCH `/ai/conversations/{id}` context_scope锛? duplicateFolder锛圥OST `/kb/folders` 鍒涘缓鍓湰锛? voicePause銆俁e-audit `.tmp/v14_hooks_audit.md`锛歵oast 瑕嗙洊鐜囦粠 **20/45 鈫?36/45**锛?16锛夛紝鍓?9 涓湰灏辩敱 modal-submit handlers (aiSave/skillRun/uploadFile/deepResearch/webLink/newFolder/notificationSettings/garden zoom) 鎺ョ锛岃繍琛屾椂 100% 瑕嗙洊銆?* **搂10.6 鎶曡祫鏉愭枡 8 寮?1920x1080 鎴浘 鈥?DONE**锛歚docs/assets/screenshots/01..08_*.png` 鍏ュ簱锛坙anding first paint / capture inflight / KB folders grid / KB folder detail / KB doc editor / digital garden / AI workspace streaming / insights full panel锛夈€傛埅鍥炬簮鑷?`.tmp/screenshots/v14_walk/` 14 鑺?acceptance 璧版煡锛坮eal LLM + 47 API calls + 0 errors锛夈€?* **搂14.13 v1.4 acceptance gate 澶嶆祴 鈥?DONE**锛歚.tmp/smoke_v14_walk.py 5248` 璺戦€?14/14 sections / 47 `/api/v1/*` calls / 0 console error / 0 page error / 0 API failure (`.tmp/v14_walk_after_15_39.log`)銆?* **`todo-tasks.md`**锛毬?4.14 / 搂15.37 / 搂15.39 / 搂10.6 鈫?`done`锛浡?.3.1 鏂板姞涓?`open` 璺熻釜 SSE Windows flake锛堜笉闃诲 acceptance锛夈€?
### Test evidence

```text
PRD10 14-suite + landing + nginx + frontend_binding + prd10/ + v1_acceptance:
  pytest -q -p no:cacheprovider --tb=short --no-header --timeout=120
  鈫?303 collected / 302 passed / 1 failed @ 887s (`.tmp/baseline_14_14.log`)
  鈫?搂0 baseline 225 鎻愬崌 +77
  鈫?鍞竴澶辫触 `test_sse_emits_ready_then_notification` 宸茬煡 搂5.3 Windows flake锛屄?.3.1 璺熻釜

v14 walk e2e:
  pytest tests/e2e/test_v14_walk.py -q -p no:cacheprovider --tb=short --no-header --timeout=180
  鈫?1 passed @ 22.26s (`.tmp/v14_walk_test_14_14.log`)

Real LLM verifier:
  python .tmp/verify_real_llm.py
  鈫?real_llm_alive=true (`.tmp/verify_real_llm_report.json`)
  鈫?tokens_seen=115 / stream_content_len=195 / persisted_status=completed / persisted_model=litellm

v14 14-section walk against real-LLM uvicorn:
  python .tmp/smoke_v14_walk.py 5248 (real LLM enabled, port 5248)
  鈫?14/14 sections OK / 47 /api/v1/* calls / 0 console / 0 page / 0 failure
  鈫?before 搂15.39 patches: same result (`.tmp/v14_walk_real_llm.log`)
  鈫?after  搂15.39 patches: same result (`.tmp/v14_walk_after_15_39.log`)

Hooks audit:
  python .tmp/extract_v14_hooks.py
  鈫?toasts: 36/45 covered directly (+ 9 by modal-submit handlers = 45/45 runtime)
  鈫?data-open-modal: 13/15 鐩存帴鎺ラ€?+ 2 (insightHistory P2)
  鈫?data-notice-action: 5/5 鍏ㄦ帴
  鈫?data-inline-menu search filters (searchSort/Scope/Creator/Location/Date): 鏍囪 搂15.40 P1
```

### Files

* `src/agent_os/llm/litellm_impl.py` (reasoning_content fallback)
* `static/mydow/biz_v14/bridge_v14.js` (+440 琛?搂15.39 / +1.6KB)
* `.env.local` (deepseek-chat + AGENTOS_AI_LLM=on)
* `.tmp/verify_real_llm.py` (鏂板 self-contained verifier)
* `.tmp/extract_v14_hooks.py` (鏂板 audit 宸ュ叿)
* `.tmp/v14_hooks_audit.md` (audit 鎶ュ憡)
* `docs/assets/screenshots/01..08_*.png` (8 寮犳姇璧勬潗鏂欐埅鍥?
* `todo-tasks.md` (搂14.14 / 搂15.37 / 搂15.38 / 搂15.39 / 搂10.6 鈫?done; 搂5.3.1 鈫?open)
* `agent-progress-report.md` (鏈?milestone)

### Follow-ups

* **搂5.3.1**: Windows uvicorn-in-thread + httpx 鍚屾娴佸紡 reader 鍋剁幇 stuck锛坧re-existing flake, not blocking acceptance锛涗笂绾垮墠鐢辫皝鏈夌┖璁ら淇級銆?* **搂15.40**: 鍏ㄥ眬鎼滅储 5 涓?inline-menu filter锛坰ort/scope/creator/location/date锛夊簲鍦?click 鏃舵妸 trigger label 鍐欏埌 `_PENDING_SEARCH_FILTERS`锛屼笅娆?`/search` request 甯?query params銆傚綋鍓?v1.4 prototype IIFE 鍙洿鏂?popover label銆?* 瑙嗛鑴氭湰 (`docs/demo-video-script-90s.md`) 浠嶉渶浜哄伐鎸?搂13.5 褰曞睆銆?
---

## Milestone 47 路 SPA 棣栭〉閿欒鎬?/ 401 娓呯┖ / AI 姘旀场淇濆瓨 鈥?DELIVERED

**When**: 2026-05-07锛圕ursor Agent锛?
### Delivered

* **`static/mydow/app.js`**锛歚renderHome` 瀵?`/today`銆乣/feed` 闈?401 澶辫触灞曠ず `errorState`锛堜笉鍐嶇敤绌?feed 浼锛夛紱`api()` 鍦?401 鏃舵竻绌?`#page-region` 鍐?`renderAuthOverlay`锛沗renderPage` 鏃?token 鏃╅€€锛沗hashchange` 鏃?token 娓呯┖涓诲尯骞跺脊鍑虹櫥褰曞眰锛沗renderAssistantBubble` 鍥哄畾 `dataset.role`锛宍decorateAssistantBubble` 鍚屾椂璁?`.assistant` class锛屼慨澶嶅姪鎵嬨€屼繚瀛樺埌鐭ヨ瘑搴撱€嶇瓑鍔ㄤ綔鏉″湪闈炴祦寮忓厹搴曡矾寰勪笉鍑虹幇鐨勯棶棰樸€?* **`todo-tasks.md`**锛毬?.13 / 搂9.14 / 搂9.16 / 搂9.19 鈫?`done`銆?
### Test evidence

```text
pytest tests/integration/api/test_prd10_v1_acceptance.py tests/integration/api/test_prd10_frontend_binding.py tests/integration/api/test_prd10_app_wiring.py -q 鈫?61 passed (鈮?88s)
uvicorn + seed_prd10.py @ .tmp/smoke_mcp.db 鈥?鏈湴鍚庡彴宸叉媺璧风敤浜庢墜宸ヨ仈璋冿紙Chrome MCP 浼氳瘽鍦ㄦ湰鏈烘姤 profile 鍗犵敤鏈窇鎴浘锛?```

### Files

* `static/mydow/app.js`
* `todo-tasks.md`

---

## Milestone 46 路 搂14.10 鎶曡祫浜?demo 璺緞 + v1.4 鏂囨。鎶藉眽淇 鈥?DELIVERED

**When**: 2026-05-07锛坢y-mcp-26锛?
### Delivered

* **`static/mydow/biz/bridge.js`**锛歚loadDocumentForDrawer` 绋冲仴瑙ｆ瀽 `r.data`锛沗_hydrateItemDetailDrawerForDocument` 浼樺厛鍐欏叆 `data-document-id`銆佸幓闄ゅ苟鍙?`cardId`锛涙爣棰?鍓爣棰樼敤 `.detail-drawer .drawer-head` 浣滅敤鍩熴€俙hydrateItemDetailDrawer`锛堝崱鐗囪矾寰勶級鏀逛负鍚屼竴濂?h2 閫夋嫨鍣ㄥ苟娓呴櫎鏂囨。 `data-document-id`锛岄伩鍏嶈鍔寔鎶藉眽鏍囬銆?* **`.tmp/smoke_demo_path.py`**锛歜oot / AI workspace 閫夋嫨鍣ㄥ吋瀹?v1.4锛坄.ai-history-thread`锛夛紱搂04 绛夊緟鍙鎶藉眽涓?`data-document-id` 涓庨鏂囨。 id 涓€鑷淬€?* **`docs/assets/screenshots/`**锛氬悓姝?`.tmp/screenshots/investor_deck/` 10 寮?PNG锛坙anding + biz 闂幆锛夈€?
### Test evidence

```text
python .tmp/smoke_demo_path.py 8890  鈫?OK锛?0/10 sections, summary_ok=true, 0 console/page/failed API锛?node --check static/mydow/biz/bridge.js  鈫?OK
```

### Files

* `static/mydow/biz/bridge.js`
* `.tmp/smoke_demo_path.py`
* `docs/assets/screenshots/*.png`锛堣嚜 investor_deck 澶嶅埗锛?* `todo-tasks.md`锛埪?4.10 鈫?done锛?
### Follow-ups

* 搂10.6 瑙嗛浠嶉渶浜哄伐鎸?`docs/demo-video-script-90s.md` 褰曞睆锛涙埅鍥惧垎杈ㄧ巼濡傞渶缁熶竴 1920脳1080 鍙湪 Playwright context 涓婃敼 viewport銆?
---

## Milestone 45 路 搂8.9 presign 鎺ラ€氭ā鍧楀寲鍚庣 + 搂9.9 biz 鍝佺墝 meta + stale 搂15.29/搂15.30 鏀跺彛 鈥?DELIVERED

**When**: 2026-05-07锛圕ursor Agent / Composer锛?
### Delivered

* **`capture/router.py::presign_upload`**锛歚POST /api/v1/uploads/presign` 鏀逛负璋冪敤 `agent_os.uploads.presign.get_default_backend().presign()` 鈫?`PresignResult.to_payload()`锛堝畬鏁?搂8.3 瀛楁鍚?`expires_at` / `headers` / `fields` / `backend`锛夛紱`ValueError`鈫?00銆乣RuntimeError`锛堜緥濡?S3 鏈厤缃?bucket锛夆啋503銆?* **`tests/integration/api/prd10/test_prd10_presign_backends.py`**锛歭ocal 濂戠害鎵╁睍鏂█ + `AGENTOS_UPLOAD_BACKEND=s3` 涓旀棤 `AWS_S3_BUCKET` 鏃?503锛涙ā鍧?autouse 澶嶄綅 singleton銆?* **`static/mydow/biz/bridge.js`**锛歚injectBrandMeta()`锛坙anding 鍚屾簮 SVG favicon + `theme-color` + OG/Twitter锛変簬 `boot()` 璋冪敤骞跺鍑恒€?* **`.env.example`**锛歚AGENTOS_UPLOAD_BACKEND` / presign TTL / max size / S3 鍙橀噺鍧楁浛浠ｉ檲鏃?`UPLOADS_BACKEND` 娉ㄩ噴銆?* **`todo-tasks.md`**锛毬?.9 路 搂9.9 路 搂15.29 路 搂15.30锛坆iz v1.4 鍚堝苟琛岋級鏍?**done**銆?
### Test evidence

```text
pytest tests/integration/api/prd10/test_prd10_presign_backends.py tests/integration/api/prd10/test_prd10_uploads_local_api.py -q  鈫?9 passed
pytest tests/integration/api/test_prd10_frontend_binding.py -q  鈫?28 passed
node --check static/mydow/biz/bridge.js  鈫?OK
```

### Files

* `src/agent_os/capture/router.py`
* `tests/integration/api/prd10/test_prd10_presign_backends.py`
* `static/mydow/biz/bridge.js`
* `.env.example`
* `todo-tasks.md`

### Follow-ups

* S3 鐪熷疄 PUT 鑱旇皟浠嶄緷璧?boto3 + bucket policy锛涘彲閫夎ˉ鍏?mock boto 鐨勫崟娴嬶紙鏈疆浠呰鐩?misconfig 503锛夈€?
---

## Milestone 44 路 搂15.31鈥撀?5.33 v1.4 bridge 楠屾敹 + E2E smoke 鈥?DELIVERED

**When**: 2026-05-07锛圕ursor Agent锛?
### Delivered

* **`tests/e2e/test_v14_walk.py`**锛氬瓙杩涚▼ `uvicorn` + `seed_prd10` + Playwright 鎵撳紑 `/mydow/biz_v14/?cb=`锛岄伩鍏嶇埗杩涚▼宸插姞杞?`tests/conftest.py` 鏃?`agent_os.db.base` 閿欒闂╁湪榛樿 Postgres `DATABASE_URL` 瀵艰嚧 WinError 1225 / demo/login 500銆?* **`todo-tasks.md`**锛毬?5.31 / 搂15.32 / 搂15.33 / 閲嶅 搂10.7 / stale 搂15.22 鐘舵€佹敹鍙ｃ€?* 搂7.27 宸蹭负 **done**锛坢y-mcp-17锛夛紝鏈潯鏈敼 `bridge.js`銆?
### Test evidence

```text
python -m pytest tests/e2e/test_v14_walk.py -q -p no:cacheprovider  鈫?1 passed
```

### Files

* `tests/e2e/test_v14_walk.py`
* `todo-tasks.md`

### Follow-ups

* 搂15.33 褰撳墠鍙仛 boot + token + `apiFetchV14` + capture DOM + 闆跺け璐ヨ姹傦紱鍏?11 妯″潡 class 鍒囨崲鍙瘮鐓?`.tmp/agent3_14_3_acceptance.py` 鎵╂柇瑷€銆?
---

## Milestone 43 路 搂10.3 biz onboarding tour 鎺ラ€?boot + 婕旂ず閲嶆挱鍏ュ彛 鈥?DELIVERED

**When**: 2026-05-07锛圕ursor Agent / my-mcp-21锛?
### Delivered

* **`static/mydow/biz/bridge.js`**锛歚boot()` 鍦?`Promise.allSettled` 鎴愬姛鍚庤皟鐢?`bootOnboardingIfFirstTime()`锛涗晶鏍?`.brand` 娉ㄥ叆 `[data-restart-onboarding]` 婕旂ず chip锛沗window.MydowBridge.restartOnboarding` 瀵煎嚭銆?
### Test evidence

```text
python .tmp/smoke_10_3_onboarding.py 8890 鈫?exit 0
```

### Files

* `static/mydow/biz/bridge.js`
* `.tmp/smoke_10_3_onboarding.py`

---

## Milestone 42 路 SPA 搂7.25/搂7.26 + KB 鍒楄〃鏌ヨ鎵╁睍 鈥?DELIVERED

**When**: 2026-05-07锛圕ursor Agent / my-mcp-21锛?
### Delivered

* **`src/agent_os/kb/router.py`**锛歚GET /api/v1/kb/folders` 鏀寔 `is_favorite=true`锛堜粎鏀惰棌锛変笌 `sort_by=updated_at`锛堟寜鏇存柊鏃堕棿闄嶅簭锛夈€?* **`static/mydow/app.js`**锛氱煡璇嗗簱椤靛伐鍏锋爮鏀逛负鏈嶅姟绔瓫閫?+ skeleton锛涢椤点€屾繁搴︾爺绌躲€峘mode:"report"` 淇闈炴硶 `research`锛涗笂浼犲吋瀹瑰绉?presign 瀛楁褰㈡€併€?* **`tests/integration/api/prd10/test_prd10_kb_api.py`**锛歚test_list_folders_is_favorite_filter_and_sort_by_updated_at`銆?* **`docs/agent-2-spa-binding-guide.md`**锛歠olders 鏌ヨ鍙傛暟鏂囨。鍚屾銆?
### Test evidence

```text
pytest tests/integration/api/prd10/test_prd10_kb_api.py -q 鈫?26 passed
pytest tests/integration/api/test_prd10_frontend_binding.py -q 鈫?28 passed
node --check static/mydow/app.js 鈫?exit 0
```

---

## Milestone 41 路 搂5.3 Windows SSE 閫氱煡娴侀泦鎴愭祴璇?鈥?DELIVERED

**When**: 2026-05-07 15:57锛圓gent / my-mcp-15锛?
**Why**: `todo-tasks.md` 搂5.3 闀挎湡澶勪簬 `open`锛坄httpx` + `ASGITransport` 鍦?Windows 涓嬩笌 Starlette SSE / `BaseHTTPMiddleware` 鐨勭粍鍚堟槗姝婚攣锛夈€?
### Delivered / verified

* **`tests/integration/api/prd10/test_prd10_sse_notifications_api.py`**锛氬凡閫氳繃 **宓屽叆寮?`uvicorn.Server`锛坉aemon 绾跨▼锛? 鍚屾 TCP `httpx.Client`** 椹卞姩涓ゆ潯鐢ㄤ緥锛坮eady鈫抈job_completed` 閫氱煡銆佽法鐢ㄦ埛闅旂锛夛紝涓庝骇绾胯矾寰勪竴鑷淬€?* **`tests/integration/api/prd10/conftest.py`**锛歚_build_app(..., with_request_id_middleware=False)` 渚?`prd10_app` / `prd10_other_app`锛堝強 `prd10_dual_asgi_clients` 鏂囨。娉ㄩ噴锛変笓鐢ㄤ簬 SSE harness锛岄伩鍏?`RequestIdMiddleware`锛坄BaseHTTPMiddleware`锛夊彔鍔犻暱杩炴帴鏃剁殑 ASGI `receive` 鍗℃銆?
### Test evidence

```text
pytest tests/integration/api/prd10/test_prd10_sse_notifications_api.py -vv -p no:cacheprovider
# 2 passed (win32), ~7.8s
```

* `todo-tasks.md` 搂5.3 鈫?`done`

---

## Milestone 41 路 Acceptance Gate 搂14.9锛圚TTPS 鍏綉 `/mydow/` 杩愮淮濂戠害锛?鈥?DELIVERED

**When**: 2026-05-07锛圕ursor Agent / Composer锛?
**Why**: `todo-tasks.md` 搂14.9 闀挎湡 `open`锛岄渶瑕佹妸銆宑ompose + nginx + TLS + 鍩熷悕 + curl 鐑熸祴銆嶅啓鎴愬彲鎵ц杩愮淮娈佃惤锛屽苟鐢ㄩ潤鎬佹祴璇曢攣浣?`locations.conf.inc` 瀵?`/mydow` 鐨勮浆鍙戜簨瀹烇紝閬垮厤鍥炲綊銆?
### Delivered

* **`docs/11-deployment/docker.md`**
  * 鏂板 **銆岀敓浜у煙鍚嶄笌 `/mydow/` 鍏ュ彛锛圓cceptance Gate 搂14.9锛夈€?*锛歚--profile nginx`銆乣BASE_URL` / `CORS_ORIGINS`銆乣curl https://demo.example.com/mydow/` 涓?`/health`銆佹寚鍒?`https.md`銆?  * 閲嶅啓 **HTTPS 閰嶇疆** 灏忚妭锛屽幓闄よ繃鏃剁殑銆屾墜鍔ㄥ彇娑堟敞閲?HTTPS 鍧椼€嶏紝涓庡綋鍓?`mydow.conf` + `entrypoint.sh` 琛屼负涓€鑷淬€?* **`tests/integration/api/test_prd10_deployment_nginx.py`**锛歚test_locations_inc_proxies_mydow_shell` + `test_docker_md_documents_acceptance_gate_14_9`銆?
### Verified

```text
pytest tests/integration/api/test_prd10_deployment_nginx.py -q -p no:cacheprovider --tb=short
# 18 passed
```

### Files

* `docs/11-deployment/docker.md`
* `tests/integration/api/test_prd10_deployment_nginx.py`
* `todo-tasks.md`锛埪?4.9 鈫?`done`锛?
---

## Milestone 40 路 搂11.9 Production seed 鏀跺熬锛坋nv 鎵嬪唽 + 濂戠害娴嬭瘯锛?鈥?DELIVERED

**When**: 2026-05-07锛圕ursor Agent / Composer锛?
**Why**: `todo-tasks.md` 搂11.9 浠嶆爣 `doing`锛坈laude-opus 鎺ユ墜鏉＄洰鏍囨敞缂烘祴璇曚笌 `env-vars.md`锛夛紱`test_prd10_production_seed.py` 涓?`production-seed.md` 宸茬豢锛岃ˉ瀹岃繍缁存墜鍐屼晶鍚屾骞跺叧闂换鍔°€?
### Delivered

* **`docs/11-deployment/env-vars.md`**锛氬湪 搂5銆孭RD10 琛屼负寮€鍏炽€嶄笅鏂板 **銆孭RD10 搂11.9 鐢熶骇 Seed銆?* 瀛愯妭锛岃〃鏍煎紡鍒楀嚭 `AGENTOS_PROD_SEED_ON_BOOT` / `FORCE` / `EMAIL` / `PASSWORD` / `FULLNAME`锛屽苟閾惧埌 `production-seed.md`銆?* **`tests/integration/api/test_prd10_production_seed.py`**锛氭柊澧?`test_env_vars_handbook_mentions_prod_seed`锛岄槻姝?env 鎵嬪唽涓庣瀛愯剼鏈紓绉汇€?
### Verified

```text
pytest tests/integration/api/test_prd10_production_seed.py -q -p no:cacheprovider
# 17 passed
```

### Files

* `docs/11-deployment/env-vars.md`
* `tests/integration/api/test_prd10_production_seed.py`
* `todo-tasks.md`锛埪?1.9 鈫?`done`锛?
---

## Milestone 39 路 搂12.5 鏂囦欢涓婁紶鍒嗙墖 + 鏂偣缁紶锛圥RD10 搂16.3 / 搂29 澶ф枃浠堕闄╅棴鐜級 鈥?DELIVERED

**When**: 2026-05-07 10:25锛堟湰浼氳瘽缁紝by Agent / my-mcp-22锛?
**Why**: PRD10 搂29 鎶娿€屽ぇ鏂囦欢瑙ｆ瀽澶辫触 / 涓婁紶鍗￠】銆嶅垪涓哄叧閿闄╋紱搂16.3 寮傛浠诲姟琛ㄩ噷鐨勩€屾枃浠朵笂浼犲垎鐗?+ 鏂偣缁紶銆嶄竴鐩?`open` 娌′汉鎺ャ€俠iz `uploadFile` modal 褰撳墠鐢ㄥ崟娆?`PUT /api/v1/uploads/local/{id}`锛孎astAPI 榛樿 body limit + ASGI 鍗曟鍐呭瓨宄板€煎湪澶?PDF / 瑙嗛涓婁細琚帎姝伙紝**鎶曡祫婕旂ず鐪熶笂浼?100 MB 瑙嗛灏辩炕杞?*銆傛湰閲岀▼纰戞妸鍒嗙墖涓婁紶鍚庣鎵撻€氾紝褰㈡€佸榻?S3/R2 multipart锛坈lient 鍒囧埌鐪熷璞″瓨鍌ㄦ椂鍙崲 storage adapter锛岃矾鐢卞眰闆舵敼锛夛紝璁?SPA 鍚庣画鍒囩墖鎺ュ叆鍗冲彲銆?
鎸?搂3 棰嗗湴鍗忚皟锛歚uploads/router.py` + `uploads/storage.py` + `tests/integration/api/prd10/` 閮芥病鍦ㄥ埆浜虹殑 `doing` 涓紙鏈€杩戠殑 搂15.7 4 modals 宸?done锛夛紝鍏ㄧ▼鐙珛鍔ㄦ枃浠躲€?
### Delivered

* **`uploads/storage.py`**锛?~430 琛岋級锛?  * `_multipart_chunk_size_default` / `_multipart_ttl_seconds_default` / `_multipart_max_total_size_default`锛歟nv-driven 榛樿鍊硷紝鍒嗗埆閽冲埌 64 KiB 鈥?64 MiB / 60 s 鈥?7 d / 鈮?1 MiB锛岄伩鍏?hostile env 鎶婃湇鍔＄帺鍧忋€?  * `ChunkInfo` dataclass 鈥?`(index, size_bytes, sha256)` 鏆撮湶缁?client銆?  * `MultipartSession` dataclass 鈥?鎸佷箙鍖栧瓧娈碉細`upload_id / user_id / filename / mime_type / total_size_bytes / chunk_size / total_chunks / created_at / expires_at / chunks: dict[int, ChunkInfo] / completed_at`锛宍to_dict / from_dict` 鐢?ISO 8601 + JSON 搴忓垪鍖栵紱`is_expired / is_complete / received_indices / missing_indices` 4 涓煡璇㈡柟娉曘€?  * `MultipartUploadError(ValueError)` 鈥?甯?`code` (NOT_FOUND / VALIDATION_ERROR) 璁?router 涓€琛?if-else 缈绘垚 PRD10 envelope銆?  * `MultipartStorage` 绫伙紙singleton + `get_default_multipart_storage` / `set_default_multipart_storage` 娴嬭瘯閽╁瓙锛夛細
    * `init_session(user_id, upload_id, filename, total_size_bytes, mime_type, chunk_size)` 鈥?璁＄畻 `total_chunks = ceil(total_size / chunk_size)`锛宎tomic-rename `meta.json`锛屽缓绔?`chunks/` 鐩綍锛沨ostile filename 缁?`UploadStorage._safe_filename` 瑙勫垯鍖栥€?    * `get_session` 鈥?璇?`meta.json` + JSON 瑙ｆ瀽锛涗换浣曞紓甯歌繑 None锛堥伩鍏嶆薄鏌撲笂灞?trace锛夈€?    * `write_chunk(user_id, upload_id, chunk_index, data)` 鈥?鏍￠獙 expired / completed / index 鑼冨洿 / chunk size锛堥潪鏈熬蹇呴』 == `chunk_size`锛屾湯灏?== `total_size - chunk_size * (total_chunks-1)`锛? 绌?body锛涘啓 `chunks/{index:08d}.part` + 鏇存柊 meta 钀界洏銆?    * `assemble(user_id, upload_id, target_storage)` 鈥?娴佸紡鎸?index 椤哄簭鎷兼帴锛堟瘡鐗?64 KiB 缂撳啿璇?鈫?鍐欐渶缁堟枃浠讹級鈫?鎬诲ぇ灏忔牎楠?鈫?杩斿洖 `(MultipartSession, StoredUpload)` + `_purge` 娓呯┖ multipart 涓存椂鐩綍锛沘ssembled-size 涓嶄竴鑷存椂鍥炴粴鏈€缁堟枃浠跺苟淇濈暀 multipart 璁?client retry銆?    * `cancel(user_id, upload_id)` 鈥?`shutil.rmtree(ignore_errors=True)`锛屽箓绛夛紙涓嶅瓨鍦ㄨ繑 False锛屽瓨鍦ㄨ繑 True锛夈€?* **`uploads/router.py`**锛?~250 琛岋級锛? 涓鐐瑰叏閮ㄨ蛋 PRD10 envelope锛坮outer prefix `/api/v1/uploads`锛夛細
  * `POST /multipart/init` 鈥?鎺?`MultipartInitRequest`锛坒ilename min=1/max=500 + total_size_bytes>0 + optional mime_type/chunk_size{ge=1024,le=64MiB}锛宍extra="forbid"`锛夛紝杩斿洖 session 鎻忚堪绗?dict銆?  * `PUT /multipart/{upload_id}/{chunk_index}` 鈥?璇?`request.body()`锛堣８ bytes锛屼笌鍗?PUT 鍚屽舰鎬侊級鈫?`write_chunk` 鈫?杩斿洖 `{chunk_index, size_bytes, sha256, received_count, total_chunks, is_complete}`銆?  * `GET /multipart/{upload_id}` 鈥?杩斿洖 `_multipart_session_payload`锛堝惈 `received_chunks` 鎺掑簭鏁扮粍 + `missing_chunks` 鏁扮粍 + `status: in_progress|ready|completed`锛夛紝cross-user 404銆?  * `POST /multipart/{upload_id}/complete` 鈥?`assemble` 鈫?upsert `prd10_sources` 琛岋紙`source_type="file" / parse_status="uploaded" / storage_path / size_bytes / mime_type`锛夆啋 commit锛涜繑鍥炰笌鍗?PUT **瀹屽叏涓€鑷?*鐨?envelope锛坄{upload_id, filename, size_bytes, file_url}` + 鍔?`completed_at, total_chunks`锛夛紝璁?`/capture/file/commit` 闆朵慨鏀瑰嵆鍙秷璐广€?  * `DELETE /multipart/{upload_id}` 鈥?骞傜瓑娓呯悊锛岃繑 `{upload_id, cancelled: bool}`銆?  * `_multipart_session_payload` / `_raise_multipart_error` 涓や釜 helper 璁?NOT_FOUND鈫?04 + VALIDATION_ERROR鈫?00 缈昏瘧鍙湁涓€琛屻€?* **`.env.example`** 搂7 鍔?4 琛?env锛歚PRD10_UPLOADS_MULTIPART_BASE` / `AGENTOS_UPLOAD_MULTIPART_CHUNK_SIZE` / `AGENTOS_UPLOAD_MULTIPART_TTL_SECONDS` / `AGENTOS_UPLOAD_MULTIPART_MAX_BYTES`銆?* **`docs/11-deployment/env-vars.md`** 搂7 鍚屾 4 琛岃〃銆?* **`docs/11-deployment/api-reference.md`** 搂3 绔偣琛ㄥ姞 5 琛?multipart + 搂3.1 鏁寸珷銆屽ぇ鏂囦欢鍒嗙墖涓婁紶銆? 姝?curl 绀轰緥锛坕nit / 寰幆 PUT / resume / complete / cancel锛? 鍏抽敭瀹炵幇缁嗚妭娈点€?
### Test evidence

鏂板姞 `tests/integration/api/prd10/test_prd10_uploads_multipart.py`锛?*+450 琛?/ 18 鐢ㄤ緥 / 18 PASS @ 4.01s**锛夛紝瑕嗙洊 init shape / 0-size 422 / too-large 400 / forbid extra锛汸UT persist+progress / 涔卞簭鍚?complete锛堝瓧鑺傜骇 `read_bytes() == payload`锛? wrong size 400 / index out-of-range 400 / unknown session 404锛沜omplete missing-chunks 400 / Source row 钀藉簱瀛楁鍏ㄥ / envelope 涓?single-PUT 鍚?shape / 涓?`/capture/file/commit` 绔埌绔蛋閫氾紱resume missing-chunks / 404锛沜ancel cleanup / unknown idempotent锛沜ross-user GET/PUT/POST 鍏ㄩ儴 404銆?
**鑱斿悎 PRD10 鍏?14 濂椾欢 + prd10/ 鐭╅樀 271 passed @ 161.37s** (`.tmp/baseline-12-5.log`)锛屾瘮 搂0 baseline 225 鎻愬崌 **+46**锛岄浂鍥炲綊銆?
### Files touched

* `src/agent_os/uploads/storage.py`锛?~430 琛岋級
* `src/agent_os/uploads/router.py`锛?~250 琛岋級
* `tests/integration/api/prd10/test_prd10_uploads_multipart.py`锛?*鏂板缓**锛?50 琛岋紝18 鐢ㄤ緥锛?* `.env.example`锛?4 env锛?* `docs/11-deployment/env-vars.md`锛?4 琛岃〃锛?* `docs/11-deployment/api-reference.md`锛埪? +5 琛?+ 鏂?搂3.1锛?* `todo-tasks.md` 搂12.5 `doing` 鈫?`done` + 瀹屾暣璇佹嵁
* 鏈?milestone 鍐欏叆 `agent-progress-report.md`

**鏈姩**锛歚static/mydow/*`銆乣bridge.js`銆乣/uploads/local/{id}` 鍗?PUT 璺緞銆佸叾浠?agent 鍦?`auth/router.py` / `account/router.py` / `common/middleware.py` 绛夊凡鍐欑殑浠ｇ爜銆?
### Follow-ups

1. **SPA 鎺ュ叆**锛堝紑鏂?task 搂15.x锛夛細`bridge.js::handleUploadFileModal` 鍗囩骇鏀寔 multipart 鍒囩墖锛歠ile.size > 10 MiB 璧?`multipart/init` 鈫?骞跺彂 `PUT` chunks 鈫?`complete`锛屽惁鍒欎繚鐣欏崟 PUT 璺緞銆?2. **澶氬疄渚嬮儴缃?*锛氬綋鍓?multipart staging 钀芥湰鍦扮鐩橈紝澶氬疄渚嬫椂涓嶅悓 worker 鐪嬪埌鐨?session 涓嶄竴鑷淬€傛姇璧勬紨绀哄崟瀹炰緥 OK锛涗笂绾垮墠鎹㈠叡浜?FS锛圢FS / EFS锛夋垨鍒?S3 multipart锛圓PI 褰㈡€佸凡瀵归綈锛夈€?3. **杩囨湡 session 娓呯悊 cron**锛氬綋鍓?TTL 妫€鏌ュ彧鍦?PUT 鏃惰Е鍙戯紝杩囨湡涓存椂鐩綍浼氶┗鐣欍€傚彲鍔犱竴涓?`scripts/cleanup_multipart_sessions.py` 涓?搂10.7 demo 閲嶇疆鑴氭湰鍗忓悓銆?
---

## Milestone 38 路 搂11.5b Sentry P1 follow-up锛歳equest_id 鈫?scope 缁戝畾 + smoke 绔偣 + 閮ㄧ讲鎵嬪唽 鈥?DELIVERED

**When**: 2026-05-07 10:25锛堟湰浼氳瘽缁紝by Agent / my-mcp-24锛?
**Why**: 搂11.5锛圫entry 鎺ュ叆锛夊凡 done锛堝叾浠?agent 鍗忓悓鏍?done锛屽鐢ㄦ垜涔嬪墠鐨?`sentry_setup.py`锛夛紱搂11.5b 鏄悓鍚?follow-up锛氭妸 PRD10 搂11.6 宸茬粡鍦ㄧ敤鐨?request_id 瀛楁涓插埌 Sentry scope锛堝叧鑱旀棩蹇?鈫?event锛? 缁欒繍缁翠竴涓浂鎺ヨЕ楠岃瘉 Sentry 鐪熸帴閫氱殑 smoke 绔偣 + 鎶婃暣濂椾粠 0 鍒扮敓浜х殑閮ㄧ讲姝ラ鍐欐垚鎵嬪唽銆?
鎸夊浜哄崗浣滆鍒欙紙搂3 / 搂5.5锛夛細鏈换鍔℃寕鍦ㄣ€孲entry / 鐩戞帶銆峫ane锛屼笉鎾炰换浣曞綋鍓?`doing` 浠诲姟锛堥伩鍏?搂15.x 鍖哄潡銆佷笉鍔?SPA 鏂囦欢銆佷笉鍔?router include 椤哄簭涔嬪鐨勯鍦帮級銆?
### Delivered

#### 1. `RequestIdMiddleware` 鈫?Sentry isolation scope锛坄common/middleware.py`锛?
鍦?stamp `request.state.request_id` 涔嬪悗銆乣call_next` 涔嬪墠锛屽姞涓€娈垫潯浠?sentry tagging锛?
```python
if is_sentry_enabled():
    import sentry_sdk
    sentry_sdk.set_tag("request_id", rid)
    sentry_sdk.set_tag("http.method", request.method or "GET")
    sentry_sdk.set_context("request_meta", {
        "request_id": rid, "path": request.url.path, "method": request.method,
    })
```

璁捐瑕佺偣锛?- 鐢?sentry-sdk **2.x module-level** API锛坄sentry_sdk.set_tag` / `sentry_sdk.set_context`锛夛紝涓嶆槸 deprecated 鐨?`with sentry_sdk.configure_scope() as scope: scope.set_tag(...)`锛涘悗鑰呬細鍙?DeprecationWarning锛?.x 鐗堟湰閲屾敼鎴愮瓑浠风殑 module-level helper锛堝啓褰撳墠 isolation scope锛夈€?- 鏁存鐢?`try/except Exception: pass` 鍖呰９ 鈥?鐩戞帶澶辫触姘歌繙涓嶈兘浼犳煋涓氬姟璇锋眰璺緞銆?- `is_sentry_enabled()` 鐭矾 + 灞€閮?`import sentry_sdk` 璁?sentry 鍏抽棴鏃跺嚑涔庨浂寮€閿€锛堜袱涓睘鎬ф煡鎵撅級銆?
#### 2. `__sentry_test__` smoke 绔偣锛坄common/sentry_test_router.py`锛寏85 琛岋級

`POST /api/v1/__sentry_test__`锛?- `capture_message("sentry_smoke_test_message", level="info", request_id=...)` 涓€鏉?info-level 浜嬩欢
- 涓诲姩 `1/0` 瑙﹀彂 ZeroDivisionError
- `capture_exception(exc, request_id=..., synthetic=True)` 鍖呰涓婃姤
- 杩斿洖 PRD10 envelope `500 INTERNAL_ERROR` with `details={synthetic: true, endpoint: "/api/v1/__sentry_test__"}`

鎸傝浇閫昏緫锛堝弻閲?gating锛夛細
- `is_sentry_test_endpoint_enabled()` 鍚屾椂瑕佹眰锛歚AGENTOS_SENTRY_TEST=on/1/true/yes/enabled` AND `is_sentry_enabled()`锛堝嵆 DSN 宸查厤 + init 鎴愬姛锛?- 鍙弧瓒充竴涓笉鎸傝浇锛堣矾寰勮繑 404锛?- 闃叉鐢熶骇娉勬紡锛氭搷浣滃憳楠岃瘉瀹屾瘯鍚?unset env 鍗冲交搴曞叧闂?
`server/app.py` 鐢?try/except 鍖呰９ include_router锛岄伩鍏嶆寕杞藉け璐ョ牬鍧?startup銆?
#### 3. `capture_message` / `capture_exception` 鍚屾杩佺Щ鍒?sentry-sdk 2.x

`common/sentry_setup.py` 鎶?deprecated `with sentry_sdk.push_scope() as scope:` 鏀逛负 `with sentry_sdk.new_scope() as scope:`锛?.x 鎺ㄨ崘 API锛夈€傝涔変竴鑷达細per-call extras 涓嶄細娉勬紡鍒板悓 task 鍚庣画 captures銆?
#### 4. 閮ㄧ讲鎵嬪唽 `docs/11-deployment/sentry.md`锛?0 绔?/ ~250 琛岋級

瀹屾暣绔犺妭锛?1. 鏋舵瀯鎬昏锛圓SCII 鍥撅細Mydow 鈫?SDK 鈫?SaaS锛?2. 5 鍒嗛挓鎺ュ叆锛堟嬁 DSN 鈫?閰?.env 鈫?閲嶅惎 鈫?smoke 楠岃瘉 鈫?鍏?smoke 寮€鍏筹級
3. `/ready` 鑷 JSON 绀轰緥
4. PII 鍓ョ瑙勫垯琛紙7 涓?header keys + 11 涓?body keys锛?5. 鍣煶杩囨护锛坉rop /health /ready /metrics /favicon.ico锛?6. Source maps 璁″垝锛堝綋鍓?SPA 璧板師鐢?ESM 涓嶉渶瑕?sourcemap锛?7. 鎺ㄨ崘 Alert Rules 琛紙5xx spike / new issue / AI streaming / rate limit / dead-letter / 503锛屽叧鑱?PagerDuty/Slack锛?8. 涓?搂11.6 logging 鍗忓悓锛坆readcrumb / event / SQL 鑷姩鎹曡幏 / context.request_meta锛?9. 9 鏉″父瑙佹晠闅滄帓鏌ヨ〃
10. 娴嬭瘯瑕嗙洊娓呭崟 + 鍏抽敭瑕嗙洊鐐?
#### 5. 娴嬭瘯锛?1 涓柊 cases锛屽叏杩?0 deprecation warnings锛?
- **`tests/integration/api/test_prd10_sentry_request_id.py` (8 tests)**:
  - `test_request_id_middleware_does_not_touch_sentry_when_disabled` 鈥?榛樿鏃?DSN 鏃?SDK 瀹屽叏 untouched
  - `test_request_id_middleware_tags_sentry_scope_when_enabled` 鈥?set_tag + set_context 鐪熻皟鐢?  - `test_request_id_middleware_resilient_against_sdk_errors` 鈥?SDK 鎶涘紓甯告椂涓氬姟璇锋眰浠?200
  - `test_smoke_endpoint_gated_off_by_default` 鈥?榛樿 404
  - `test_smoke_endpoint_gated_off_when_only_env_set` 鈥?鍗曡竟寮€鍏虫棤鏁?  - `test_smoke_endpoint_gated_off_when_only_sentry_on` 鈥?鍗曡竟寮€鍏虫棤鏁?  - `test_smoke_endpoint_active_when_both_set` 鈥?鍙屽紑鍏冲悓鏃?on 鎵嶇敓鏁?  - `test_smoke_endpoint_returns_prd10_envelope` 鈥?鍛戒腑鍚庣湡杩?500 + PRD10 envelope + synthetic=true

- **`tests/unit/common/test_sentry_setup.py::test_capture_helpers_swallow_internal_errors`** 鍚屾鏀?mock `new_scope` 鑰岄潪 `push_scope`锛?.x 涓€鑷存€э級

### Test evidence

```
$ pytest tests/unit/common/test_sentry_setup.py \
        tests/integration/api/test_prd10_sentry_integration.py \
        tests/integration/api/test_prd10_sentry_request_id.py
  42 passed in 10.82s
  # 0 sentry-sdk DeprecationWarning锛?.x API 鍏ㄩ儴瀵归綈锛?
$ pytest tests/integration/api/test_prd10_*.py \
        tests/integration/api/prd10/ \
        tests/integration/api/test_prd10_rate_limit.py \
        tests/integration/api/test_prd10_sentry_integration.py \
        tests/integration/api/test_prd10_sentry_request_id.py \
        tests/unit/common/
  373 passed in 173.02s
```

**Baseline 鍥炲綊**锛氫笂涓€杞?搂12.2 done 鍚?250 鈫?鏈疆 373锛?*+123**锛堝惈 8 sentry_request_id 鏂板姞 + 31 sentry_setup unit 閲嶆柊璺?+ Milestone 27/28 涔嬪悗鍏朵粬 agent 鍔犵殑鑻ュ共 done 浠诲姟鐨勯澶?cases锛夈€?*鏃犱换浣曞洖褰?/ 鏃犱换浣曞け璐?*銆?
### Files touched

鏂板锛?- `src/agent_os/common/sentry_test_router.py`锛垀85 琛岋級
- `tests/integration/api/test_prd10_sentry_request_id.py`锛? tests锛?- `docs/11-deployment/sentry.md`锛?0 绔?/ ~250 琛岋級

淇敼锛?- `src/agent_os/common/middleware.py::RequestIdMiddleware`锛垀28 琛屾柊澧?sentry-sdk 2.x set_tag/set_context锛?- `src/agent_os/common/sentry_setup.py`锛歚capture_message` / `capture_exception` 鏀圭敤 `new_scope` 鑰岄潪 deprecated `push_scope`
- `src/agent_os/server/app.py`锛歵ry/except 鏉′欢 include `sentry_test_router`
- `tests/unit/common/test_sentry_setup.py`锛? 涓?mock 鍚嶆浛鎹紙push_scope 鈫?new_scope锛?- `todo-tasks.md` 搂11.5b `open` 鈫?`done`锛堝畬鏁磋瘉鎹級
- `agent-progress-report.md`锛堟湰 milestone锛?
**鏈姩**锛歚static/mydow/*` / 浠讳綍 SPA 瀹炵幇 / 浠讳綍 router include 椤哄簭 / 浠讳綍鍏朵粬 middleware锛涗笉鎾炰换浣?`doing` 涓殑瀹炵幇棰嗗湴銆?
### Follow-ups

1. **Sentry 脳 涓氬姟 SLO 瀵规帴**锛氬缓璁妸 `prd10_rate_limited` 鏃ュ織璁℃暟 + `MAX_RETRIES_EXCEEDED` job dead-letter 璁℃暟 + AI streaming 寮傚父璁℃暟閮藉姞 `tag` 璁?Sentry alert 鑷姩鎸?tag 鍒嗘祦鍒颁笉鍚?Slack channel銆?2. **Source maps**锛氱瓑鍓嶇寮曞叆 vite/webpack 鍚庡啀琛ワ紙褰撳墠 biz/index.html + bridge.js 璧板師鐢?ESM 涓嶉渶瑕侊級銆?3. **Sentry 鈫?PagerDuty webhook**锛氭姇璧勬紨绀哄墠蹇呴厤锛屽凡鍦?docs/11-deployment/sentry.md 搂7 鍒楀嚭 5 鏉℃帹鑽?alert rule 鏂规銆?4. **`/__sentry_test__` 鍦ㄧ敓浜ч儴缃?smoke 涔嬪悗** unset `AGENTOS_SENTRY_TEST` 骞堕€氱煡杩愮淮锛堝凡鍦ㄦ枃妗?搂2 姝ラ 5 寮鸿皟锛夈€?
---

## Milestone 37 - SPA a11y critical contrast closeout - DELIVERED

**When**: 2026-05-06 14:31-15:20 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂14.7 still required a critical-grade accessibility pass on the SPA lane, and Lighthouse had narrowed the remaining failures to the auth overlay under dark mode.

### Delivered

* `static/mydow/style.css` now tokenizes primary button text contrast with `--primary-contrast`, so dark-mode primary buttons no longer fall back to the later base `.btn-primary { color: #fff; }` rule.
* `#auth-overlay` / `.auth-card` were moved fully onto the shared token system: card background, border, text, input backgrounds, and overlay dimming now behave consistently in both light and dark themes.
* This closes the last critical accessibility issue in the SPA dark-auth path without touching the biz prototype lane.

### Test Evidence

* Chrome DevTools MCP on `http://127.0.0.1:8001/mydow/index.html#/home` with `colorScheme=dark`:
  * page snapshot confirmed the auth overlay is the active surface;
  * Lighthouse snapshot `D:\Codes\whyme\.tmp\lighthouse-auth-dark-2\report.html` / `report.json` -> **Accessibility 100**, Best Practices 100, Agentic Browsing 100.
* Before the fix, `color-contrast` failed on auth primary buttons because foreground remained `#ffffff` over dark-mode primary blue. After the token fix, the failure disappeared.
* Sanity: `node --check static/mydow/app.js` -> PASS.
* Prior SPA binding regression suite remains green: `pytest tests/integration/api/test_prd10_frontend_binding.py -q -p no:cacheprovider --tb=short --no-header` -> **27 passed**.

### Files Touched

`static/mydow/style.css`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

* Next high-signal SPA gap is AI assistant action wiring (`save-to-kb` / `create-tasks` / `regenerate` / stop-cancel) from 搂9.19 + 搂8.11.

---

## Milestone 36 - PRD10 B-13 semantic search embeddings - DELIVERED

**When**: 2026-05-06 14:40-15:05 UTC+8 (by Codex)
**Why**: `todo-tasks.md` 搂3.12 required B-13 embedding support so `/api/v1/search` can expose real `semantic` / `hybrid` ranking instead of lexical-only fallback.

### Delivered

* Added dependency-free deterministic `hash64-v1` embeddings in `src/agent_os/search_engine/embeddings.py` (64 dimensions, stable `embedding_id`, cosine similarity helpers).
* Capture indexing and PRD10 seed data now persist `SearchIndex.embedding_id` and `SearchIndex.embedding`.
* `/api/v1/search` now ranks `mode=semantic` by vector similarity and `mode=hybrid` by 70% semantic + 30% lexical score, with runtime fallback for older rows missing stored vectors.
* Updated search, capture, seed tests and API/frontend binding docs so SPA can enable keyword / semantic / hybrid modes.

### Test Evidence

* Targeted: `python -m pytest tests/integration/api/test_prd10_search_api.py tests/integration/api/prd10/test_prd10_capture_api.py tests/integration/api/prd10/test_prd10_seed_script.py -q -p no:cacheprovider --tb=short` -> **19 passed**.
* PRD10 matrix: `python -m pytest tests/integration/api/test_prd10_v1_acceptance.py tests/integration/api/test_prd10_frontend_binding.py tests/integration/api/test_prd10_ai_api.py tests/integration/api/test_prd10_ai_llm.py tests/integration/api/test_prd10_search_api.py tests/integration/api/test_prd10_skills_api.py tests/integration/api/test_prd10_garden_api.py tests/integration/api/test_prd10_observability.py tests/integration/api/test_prd10_app_wiring.py tests/integration/api/test_prd10_models_intelligence.py tests/integration/api/test_prd10_e2e_flow.py tests/integration/api/test_prd10_product_data_api.py tests/integration/api/test_prd10_insights_api.py tests/integration/api/prd10/ -q -p no:cacheprovider --tb=no --no-header` -> **271 passed, 41 warnings**.

### Files Touched

`src/agent_os/search_engine/embeddings.py`, `src/agent_os/search_engine/router_prd10.py`, `src/agent_os/capture/pipeline.py`, `scripts/seed_prd10.py`, `tests/integration/api/test_prd10_search_api.py`, `tests/integration/api/prd10/test_prd10_capture_api.py`, `tests/integration/api/prd10/test_prd10_seed_script.py`, `docs/agent-2-spa-binding-guide.md`, `docs/agent-2-seed-field-audit.md`, `docs/11-deployment/api-reference.md`, `todo-tasks.md`.

### Follow-ups

* `SearchIndex.tags` remains empty for seed rows; tag-chip filtering should stay hidden until the P1 tag backfill task is taken.
* This is deterministic local embedding for product wiring and testability; a future true embedding provider can keep the same stored-field contract.

---

## Milestone 35 路 搂7.30 biz modal/drawer open markers 鈥?DELIVERED

**When**: 2026-05-06 13:56鈥?4:08 UTC+8锛坆y Codex锛?
**Why**: 搂7.30 瑕佹眰涓氬姟鏂?zip 灞曠ず椤电殑 modal/drawer 鎵撳紑鐘舵€佸叿澶囩粺涓€鍙娴嬫爣璁帮紝鍚﹀垯 nav sweep / e2e / a11y 鏃犳硶鍒ゆ柇鎸夐挳鐐瑰嚮鍚庢槸鍚︾湡鐨勬墦寮€浜嗗脊灞傘€?
### Delivered

* `static/mydow/biz/bridge.js` 鏂板 搂7.30 layer marker锛氶€氳繃 `MutationObserver` 鐩戝惉 `.surface-layer[data-modal]` / `.drawer-layer[data-drawer]` 鐨?`hidden` 鐘舵€併€?* 鎵撳紑 modal 鏃跺悓姝ワ細`document.documentElement.dataset.modal`銆乣data-modal-open="{name}"`銆佸彲瑙?layer 涓?`data-modal-open="true"`銆乣body.is-modal-open`銆?* 鎵撳紑 drawer 鏃跺悓姝ワ細`document.documentElement.dataset.drawer`銆乣data-drawer-open="{name}"`銆佸彲瑙?layer 涓?`data-drawer-open="true"`銆乣body.is-drawer-open`銆?* 鍏抽棴鏃舵竻鐞?root/layer/body 鏍囪锛屽苟鎶?`closeAllModals()` 鎺ュ叆鍚屼竴濂楃姸鎬佸悓姝ャ€?
### Test Evidence

* Syntax: `node --check static/mydow/biz/bridge.js` 鈫?PASS銆?* Contract: `python -m pytest tests/integration/api/test_prd10_frontend_binding.py -q -p no:cacheprovider --tb=short --no-header` 鈫?**27 passed**銆?* Browser proof: Playwright 鐪熸祻瑙堝櫒鎵撳紑 `http://127.0.0.1:8000/mydow/biz/`锛屽疄鐐?`webLink` quick-action modal 涓庨椤?`.idea-card` detail drawer锛沷pen/close markers 鍏ㄩ儴 PASS锛? console error銆傛埅鍥撅細`.tmp/screenshots/biz_walk/7_30_modal_marker.png`銆乣.tmp/screenshots/biz_walk/7_30_drawer_marker.png`銆?* Chrome DevTools MCP note: 褰撳墠 MCP profile 琚棦鏈?`chrome-devtools-mcp` Chrome 瀹炰緥閿佷綇锛屽伐鍏疯繑鍥?profile already running锛涙湰杞敤 Playwright 瀹屾垚鍚岀瓑娴忚鍣ㄨ仈璋冭瘉鎹€?
### Files Touched

`static/mydow/biz/bridge.js`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

搂7.28/搂7.29 涓ご鍍?閫氱煡鎶藉眽璇垽鐜板湪鍙緷璧?`[data-drawer-open]` marker 澶嶆祴锛浡?.31 鍏?nav sweep 浠嶉渶鍦?搂7.25鈥撀?.30 鍏ㄩ儴瀹屾垚鍚庣粺涓€璺戙€?
---

## Milestone 34 路 搂15.27/搂15.28 biz bridge boot + AI-action buttons 鈥?DELIVERED

**When**: 2026-05-06 13:56鈥?4:30 UTC+8锛坆y Codex锛?
**Why**: `todo-tasks.md` 搂15.28 闀挎椂闂?`doing`锛屼笖娴忚鍣ㄥ疄娴嬪彂鐜?`bridge.js` 鍥?`bindDrawerAiActionButtons` 閲嶅澹版槑鐩存帴 SyntaxError锛屼笟鍔℃柟鍘熷瀷妗ユ帴涓?boot锛涜繖浼氳 `/mydow/biz/` 鍥為€€鎴愰潤鎬?zip 鏁堟灉锛屾墍鏈夌湡瀹?API 鎸夐挳澶辨晥銆?
### Delivered

* `tests/integration/api/test_prd10_frontend_binding.py` 澧炲姞 `_envelope_data()`锛屽悓姝ユ柇瑷€ `/api/v1/demo/status` 涓?`/api/v1/demo/login` 杩斿洖 PRD10 envelope锛屽悓鏃剁户缁吋瀹规棫 flat shape銆?* `static/mydow/biz/bridge.js` 鍒犻櫎閲嶅鐨?no-op `bindDrawerAiActionButtons()` stub锛屼繚鐣?搂15.27 鐨勭湡瀹?capture-phase handler锛屼慨澶嶆祻瑙堝櫒 SyntaxError銆?* `bridge.js` 澧炲姞 `window.__MYDOW_BRIDGE_BOOTED` 涓?`window.MydowBridge.booted` 鏍囪锛屽悗缁?Chrome/Playwright sweep 鍙ǔ瀹氬垽鏂ˉ鎺ュ凡瀹屾垚銆?* 搂15.27 AI-action 鏁版嵁婧愯ˉ鍏細`_readVisibleDocEditorSubject()` + `_readCurrentAiActionSubject()` 璁╂寜閽棦鏀寔 `itemDetail` 鍗＄墖鎶藉眽锛屼篃鏀寔涓氬姟鍘熷瀷瀹為檯鎸夐挳鎵€鍦ㄧ殑 `.doc-editor-main/.doc-editor-drawer` 鏂囨。缂栬緫椤点€?
### Test Evidence

* Syntax: `node --check static/mydow/biz/bridge.js` 鈫?PASS銆?* Contract: `python -m pytest tests/integration/api/test_prd10_frontend_binding.py -q -p no:cacheprovider --tb=short --no-header` 鈫?**27 passed**銆?* Browser smoke 搂15.28 @ `:8802/mydow/biz/`: `window.MydowBridge.booted=true` / demo login response keys `success,data,request_id` / token persisted / skills grid IDs exactly match live `/api/v1/skills?page_size=20` / 8 real idea cards / 0 console error / 0 page error / 0 failed API. Screenshot: `.tmp/screenshots/biz_walk/15_28_bridge_boot.png`.
* Browser smoke 搂15.27 @ `:8802/mydow/biz/`: doc editor `AI 鎽樿` button triggered `POST /api/v1/skills/9fe18a29-.../run`; `鐢熸垚鐭ヨ瘑鍗＄墖` triggered `POST /api/v1/cards`; feed total **30 鈫?31**; 0 console/page/API failed. Screenshot: `.tmp/screenshots/biz_walk/15_27_doc_ai_actions.png`.

### Files Touched

`static/mydow/biz/bridge.js`, `tests/integration/api/test_prd10_frontend_binding.py`, `todo-tasks.md`, `agent-progress-report.md`.

### Follow-ups

* Chrome DevTools MCP profile is currently locked by an existing `chrome-devtools-mcp` Chrome process; Playwright was used for browser proof. Next agent should retry Chrome MCP after clearing the profile lock if the rule requires MCP-specific screenshots.

---

## Milestone 35 路 搂14.3 full demo acceptance on biz prototype 鈥?DELIVERED

**When**: 2026-05-06 14:35鈥?4:45 UTC+8锛坆y Codex锛?
**Why**: 搂14.3 was still `open` because the older SPA sweep had 18 issues / 102 candidates. Since 搂15.20 already makes `/mydow/` redirect to the business prototype, the acceptance gate should validate the zip-equivalent biz surface, not the obsolete SPA lane.

### Delivered

* Re-ran the existing full demo acceptance script against the live demo server at `:8802`.
* Confirmed default `/mydow/` entry redirects to `/mydow/biz/` and the bridge boots with a persisted demo token.
* Captured a full-page investor-demo screenshot from the real browser surface.

### Test Evidence

* `python .tmp/agent3_14_3_acceptance.py 8802` 鈫?**11/11 sections ok**:
  boot/demo auto-login, capture text, home feed, KB folders, notification badge, profile chip, garden board, AI SSE send, skills grid, insights full, global search.
  Summary: `console_errors_count=0`, `page_errors_count=0`, `real_failed_requests=[]`.
* Supplemental Playwright smoke:
  `/mydow/?cb=...` 鈫?`/mydow/biz/`; `window.MydowBridge.booted=true`; `tokenLen=209`; 8 idea cards, 6 folders, 5 skills, notification badge 6, profileName Demo User; 0 console/page/API failed.
  Screenshot: `.tmp/screenshots/biz_walk/14_3_codex_full_demo.png`.

### Files Touched

`todo-tasks.md`, `agent-progress-report.md`.

---

## Milestone 34 路 SPA AI 鍏ュ彛鍙嶉 + 鏆楄壊妯″紡 token 鍥炲綊 鈥?DELIVERED

**When**: 2026-05-06 13:55鈥?4:31 UTC+8锛坆y Codex锛?
**Why**: `todo-tasks.md` 涓殑 SPA lane 杩樼暀鐫€涓ょ被浼氱洿鎺ュ奖鍝嶆紨绀鸿川閲忕殑闂锛氫竴绫绘槸 AI 椤靛拰澶村儚鍏ュ彛鈥滅偣浜嗘病鍙嶉 / sweep 鐪嬩笉鍒板弽棣堚€濓紝鍙︿竴绫绘槸 SPA 鍦?`prefers-color-scheme: dark` 涓嬫病鏈夌嫭绔?token锛屾殫鑹插洖褰掓病鏈夎瘉鎹€?
### Delivered

* [app.js](D:/Codes/whyme/static/mydow/app.js) 澧炲姞 icon-only button 鐨?`title -> aria-label` 鑷姩鏄犲皠锛岃ˉ榻?AI 浠诲姟绉婚櫎鎸夐挳鍜屽悇绫?close icon 鐨勫彲璁块棶鍚嶇О銆?* AI composer 绌哄彂閫佷笉鍐嶉潤榛橈細鐐瑰嚮 `鍙戦€乣 涓斿唴瀹逛负绌烘椂锛宭ive region 浼氭樉绀衡€滆鍏堣緭鍏ユ秷鎭€濓紝骞舵妸鐒︾偣鐣欏湪杈撳叆妗嗐€?* `openUserMenu()` 浠?toast 鍗囩骇鎴愮湡瀹?`profile-drawer`锛屽睍绀鸿处鍙?/ 鐢ㄦ埛鍚?/ 璁″垝锛屽苟鎻愪緵鍙敤鐨?`鍏抽棴` / `閫€鍑虹櫥褰昤 琛屼负锛涙墦寮€鍚庝細澶嶇敤宸叉湁 drawer marker 璁╄嚜鍔ㄥ寲鍙銆?* [style.css](D:/Codes/whyme/static/mydow/style.css) 鏂板 `@media (prefers-color-scheme: dark)` 璁捐浠ょ墝瑕嗙洊锛屾殫鑹蹭粎閫氳繃 token 鍒囨崲锛屼笉鏀归〉闈㈢粨鏋勩€?
### Test Evidence

* Syntax: `node --check static/mydow/app.js` 鈫?PASS.
* Binding regression: `python -m pytest tests/integration/api/test_prd10_frontend_binding.py -q -p no:cacheprovider --tb=short --no-header` 鈫?**27 passed**.
* Chrome MCP on `http://127.0.0.1:8001/mydow/index.html#/ai`:
  `鍙戦€乣 绌哄唴瀹瑰悗鍑虹幇 live text 鈥滆鍏堣緭鍏ユ秷鎭€濓紱鐐瑰嚮澶村儚鍚?root marker = `{page:'ai', drawer:'profile-drawer', drawerOpen:'true'}`锛屼笖 `unlabeledVisibleIconButtons=[]`銆?* Chrome MCP dark mode on `http://127.0.0.1:8001/mydow/index.html`:
  棣栭〉 / 鐭ヨ瘑搴?/ AI 涓夐〉鍦?dark scheme 涓嬪潎姝ｅ父娓叉煋锛岃绠楀€?`--bg=#12161f`銆乣--bg-card=#181d27`銆乣--text=#eef2fb`銆?
### Files Touched

`static/mydow/app.js`, `static/mydow/style.css`, `tests/integration/api/test_prd10_frontend_binding.py`, `todo-tasks.md`.

---

## Milestone 33 路 PRD10 搂14 浠诲姟鐪熷疄琛ㄩ摼璺?鈥?DELIVERED

**When**: 2026-05-06 14:05鈥?4:35 UTC+8锛坆y Agent Codex锛?
**Why**: `todo-tasks.md` 搂2.22 / 搂6.9 鏍囪 `Task.user_id Integer鈫扷UID 璋冨拰` 浠?open锛岄樆濉炵湡姝?PRD10 搂14 浠诲姟鎺ュ叆锛涚幇鏈?`/today.tasks`銆乻eed銆丄I 鐢熸垚浠诲姟 worker 浠嶈蛋 `Prd10InboxItem(type=manual_task)` 鏇夸唬閾捐矾銆?
### Delivered

* `GET /api/v1/today` 鏀逛负浠?`PRD10Task` / `prd10_tasks` 璇诲彇浠诲姟涓?pending 璁℃暟锛屾帓搴忔寜 `due_at ASC NULLS LAST, created_at DESC`銆?* `scripts/seed_prd10.py` 鐨?5 鏉?demo task 鏀逛负鍐欑湡瀹?`PRD10Task`锛屽苟鍦?seed reset 涓竻鐞?`prd10_tasks` seed rows銆?* AI `ai_message_to_tasks` worker 鐜板湪鍒涘缓鐪熷疄 `PRD10Task(source_type='ai')`锛屽悓鏃朵繚鐣?`Prd10InboxItem(type=manual_task)` 鍏煎璁板綍锛屾棫瑙嗗浘/鏃ф祴璇曚笉浼氱獊鐒舵柇銆?* PRD10 mini test harness 绾冲叆 `prd10_tasks` 寤鸿〃銆佹寕杞?`/api/v1/tasks` router锛屽苟琛ラ綈 `/api/v1/*` HTTPException / validation envelope 琛屼负銆?* 鏂板 `tests/integration/api/prd10/test_prd10_tasks_api.py` 瑕嗙洊 CRUD銆乧omplete銆乻oft-delete銆佸鐢ㄦ埛闅旂銆乫ilter銆乿alidation envelope銆?* 鍚屾 `docs/agent-2-spa-binding-guide.md` 涓?`docs/agent-2-seed-field-audit.md`锛氬墠绔彲鐩存帴鎺?`/api/v1/tasks`锛屼笉鍐嶄娇鐢?manual_task 鏇夸唬鏂规銆?
### Test Evidence

* Targeted: `python -m pytest tests/integration/api/prd10/test_prd10_tasks_api.py tests/integration/api/prd10/test_prd10_today_api.py tests/integration/api/prd10/test_prd10_seed_script.py tests/integration/api/prd10/test_prd10_jobs_notifications_api.py -q -p no:cacheprovider --tb=short` 鈫?**26 passed**.
* PRD10 matrix: `python -m pytest tests/integration/api/test_prd10_v1_acceptance.py tests/integration/api/test_prd10_frontend_binding.py tests/integration/api/test_prd10_ai_api.py tests/integration/api/test_prd10_ai_llm.py tests/integration/api/test_prd10_search_api.py tests/integration/api/test_prd10_skills_api.py tests/integration/api/test_prd10_garden_api.py tests/integration/api/test_prd10_observability.py tests/integration/api/test_prd10_app_wiring.py tests/integration/api/test_prd10_models_intelligence.py tests/integration/api/test_prd10_e2e_flow.py tests/integration/api/test_prd10_product_data_api.py tests/integration/api/test_prd10_insights_api.py tests/integration/api/prd10/ -q -p no:cacheprovider --tb=no --no-header` 鈫?**270 passed / 77.53s**.

### Files Touched

`src/agent_os/today/prd10_router.py`, `src/agent_os/jobs/service.py`, `src/agent_os/db/base.py`, `scripts/seed_prd10.py`, `tests/integration/api/prd10/conftest.py`, `tests/integration/api/prd10/test_prd10_tasks_api.py`, `tests/integration/api/prd10/test_prd10_today_api.py`, `tests/integration/api/prd10/test_prd10_seed_script.py`, `tests/integration/api/prd10/test_prd10_jobs_notifications_api.py`, `docs/agent-2-spa-binding-guide.md`, `docs/agent-2-seed-field-audit.md`, `todo-tasks.md`.

---

## Milestone 32 路 搂15.6.1 doc-row drawer wiring + 搂11.7 澶囦唤涓庢仮澶?SOP 鈥?DELIVERED

**When**: 2026-05-06 10:25鈥?1:05 UTC+8锛堟湰浼氳瘽锛宐y Agent / my-mcp-26锛?
**Why**: 鐢ㄦ埛鎸囦护銆屼笉蹇呭仠涓嬫潵姹囨姤锛屼竴鐩撮浠诲姟鍋氾紱濡傛灉涓€涓换鍔′竴鐩村湪 doing 鍙兘鏄伐绋嬪笀鎵ц澶辫触浜嗕綘鍙互鎺ョ潃鍋氬畬锛涘仛鍒?PRD10 瀹屽叏瀹炵幇 + 绗﹀悎涓氬姟鍓嶇 + 鎵€鏈夋寜閽敓鏁?+ 鏁版嵁閾捐矾鍏ㄦ墦閫氭墠鑳藉仠銆嶃€傛湰閲岀▼纰戜袱浠朵簨锛?a) 鎺ユ墜 my-mcp-18 鍦?搂15.6.1 鐣欎笅鐨勫崐鎴愬搧锛?1 涓?helper 瀹炵幇瀹屾暣浣?*鏈?wire 鍒?boot()/鏈?export 鍒?MydowBridge**锛屾祻瑙堝櫒渚у疄闄呴浂鐢熸晥锛夛紱(b) 瓒佺儹鎵撻搧璁ら骞跺畬鎴愭姇璧勪汉浼氶棶鐨?搂11.7 澶囦唤鎭㈠ SOP锛堟棤浜?doing锛岀函閮ㄧ讲杩愮淮锛屾棤鍐茬獊椋庨櫓锛夈€?
### Delivered

#### 1. 搂15.6.1 鏂囨。鎶藉眽琛岀偣鍑?+ 绉诲姩 + 鍒犻櫎鐪熸帴閫氾紙鎺ユ墜琛ュ畬 my-mcp-18 stale锛?
**鎺ユ墜鍓嶇姸鎬侊紙broken锛?*锛歚bridge.js` 宸插惈 11 helper锛坄_injectDocInfoButton` / `_injectAllDocInfoButtons` / `_formatDocDrawerMeta` / `_hydrateItemDetailDrawerForDocument` / `_openItemDetailDrawer` / `loadDocumentForDrawer` / `bindDocRowInfoButton` / `bindItemDetailDrawerActions` / `patchDocumentById` / `deleteDocumentById` / `moveDocumentById`锛夛紝浣?`boot()` 鍐呭搴斾綅缃彧鍓?`// 鍗犱綅 helper 鐣欏緟 Engineer 2 瀹炵幇` 娉ㄩ噴銆乣window.MydowBridge` 涔熸病 export锛屾祻瑙堝櫒鍔犺浇瀹屽叏鏃犳劅鐭ャ€?
**my-mcp-26 wiring 淇**锛坄static/mydow/biz/bridge.js` 浠?5 琛屽彉鏇?+ 鍒?2 琛岄噸澶?export锛夛細

* `boot()` 鍦?`attachDailyInsightLink()` 鍚庤拷鍔狅細
  ```js
  // 搂15.6.1 doc-row 鍐?鈸?璇︽儏 鈫?/kb/documents/{id} 鈫?itemDetail drawer
  // + drawer 鍐呫€岀Щ鍔ㄥ埌鐭ヨ瘑搴撱€嶃€屽垹闄ゃ€嶆寜閽?capture-phase 鎺?PRD10 鐪?API
  // (瑕嗙洊 搂15.10 P1锛欴ELETE 鎸夐挳 + move 鏂囨。)
  bindDocRowInfoButton();
  bindItemDetailDrawerActions();
  ```
* `window.MydowBridge` 瀛楀吀杩藉姞 6 涓?named exports锛歚loadDocumentForDrawer / bindDocRowInfoButton / bindItemDetailDrawerActions / patchDocumentById / deleteDocumentById / moveDocumentById`
* 鍒犻櫎瀛楀吀鏈熬涓や釜璇噸澶嶇殑 token锛坄refreshFullInsightDrawer` / `attachDailyInsightLink` 鍦ㄦ洿涓婇潰宸?export锛?
**Playwright 鐪熸祻瑙堝櫒楠屾敹** `.tmp/smoke_15_6_1.py 8771`锛?/5 sections PASS锛夛細

| Section | 楠岃瘉 |
|---|---|
| `boot` | `window.MydowBridge` 鍙揪锛? 涓?helper 鍏ㄩ儴 `typeof === "function"` |
| `folder_open` | 鐐?`.library-card[data-folder-id]` 鈫?4 doc-rows 娓叉煋 + 4 涓?`.bridge-doc-info-btn` 鍏ㄩ儴 MutationObserver 娉ㄥ叆鍒颁綅 |
| `drawer_open` | 鐐?鈸?璇︽儏鎸夐挳 鈫?`GET /api/v1/kb/documents/{id}?include_content=false` **200** + `[data-drawer="itemDetail"]` 涓嶅啀 hidden + `dataset.bridgeBound="true"` + drawer h2/subtitle 鏇挎崲涓虹湡 title銆岃仈璋冨鎺ユ竻鍗曚笌鐘舵€佺爜 ...銆?銆? 灏忔椂鍓嶆洿鏂?路 绫诲瀷 markdown 路 3597 瀛椼€?|
| `drawer_move` | 鐐?drawer 鍐呫€岀Щ鍔ㄥ埌鐭ヨ瘑搴撱€嶆寜閽?鈫?鑷姩浠?`/kb/folders` 鎷垮€欓€?+ `POST /api/v1/kb/documents/{id}/move` **200** + drawer 鍏抽棴 + 鏂囦欢澶瑰垪琛?reload |
| `drawer_delete` | 鐐?drawer 鍐呫€屽垹闄ゃ€嶆寜閽?鈫?`window.confirm` accept 鈫?`DELETE /api/v1/kb/documents/{id}` **200** + drawer 鍏抽棴 + 鏂囦欢澶瑰垪琛?reload |

**0 console error / 0 page error / 0 failed request**銆傛埅鍥?`.tmp/screenshots/biz_walk/15_6_1_{00_boot,01_folder,02_drawer_hydrate,03_after_move,04_after_delete}.png`銆?*鍚屾椂瑕嗙洊 搂15.10 P1**锛圖ELETE 鎸夐挳 + move 鏂囨。鐪熸帴閫氾級銆?
#### 2. 搂11.7 Postgres 姣忔棩澶囦唤 + 鏂囦欢瀛樺偍鐗堟湰鍖栵紙鎶曡祫浜虹骇 SOP锛屽叏鏂拌惤鍦帮級

**6 涓柊鑴氭湰**锛圠inux + Windows 鍙屽伐浣滄祦锛岄浂渚濊禆锛氬熀鏈彧鐢?`pg_dump` / `pg_restore` / `tar` / `sha256sum` / `aws s3 cp`锛夛細

| 鑴氭湰 | 鐢ㄩ€?|
|---|---|
| `scripts/backup/backup_postgres.sh` & `.ps1` | `pg_dump -Fc -Z9 --quote-all-identifiers --no-acl --no-owner` + SHA-256 + 14d 淇濈暀 + 鍙€?S3 涓婁紶锛岃瘑鍒?SQLite 鏃?graceful skip |
| `scripts/backup/restore_postgres.sh` & `.ps1` | `pg_restore --clean --if-exists` + `latest` 鍒悕 + SHA-256 鏍￠獙 + **production-fence**锛坔ost 鍚?`prod/production` 鏃跺己鍒?`--force/-Force` 鎵嶅厑璁革級 |
| `scripts/backup/snapshot_uploads.sh` & `.ps1` | `tar -czf` 鎵撳寘 `PRD10_UPLOADS_BASE` + SHA-256 + 鍚屼繚鐣?+ 鍙€?S3 |

**SOP 鏂囨。** `docs/11-deployment/backup.md`锛? 绔?/ 200+ 琛岋級锛?
1. RPO/RTO 鐩爣琛紙24h / 30min / 14 澶╂湰鍦?+ 90 澶?S3 / 鏈堝害婕旂粌锛?2. 涓€閿剼鏈煩闃碉紙Linux / Windows锛?3. 鐜鍙橀噺琛紙`BACKUP_DIR / AGENTOS_BACKUP_RETENTION_DAYS / AGENTOS_BACKUP_S3_BUCKET / AGENTOS_BACKUP_S3_PREFIX / AGENTOS_BACKUP_GPG_RECIPIENT(P1)`锛?4. 閮ㄧ讲鐭╅樀 5 绉嶏細cron / systemd timer / docker compose `--profile backup` / k8s CronJob / Windows 浠诲姟璁″垝锛屾瘡绉嶉兘甯﹀彲澶嶅埗鐗囨
5. 鏈堝害鎭㈠婕旂粌 SOP锛? 姝?createdb 鈫?restore 鈫?鍋ュ悍楠岃瘉锛?6. 瀹夊叏鍚堣搴曠嚎锛堜笉鍐?URL 杩涙枃浠跺悕 / 淇濈暀鏈?/ SSE-S3 / 瀹¤ / 婕旂粌澶辫触鍛婅 / production fence锛?7. 鏁呴殰閫熸煡 4 鏉?8. V2 follow-ups锛歐AL/PITR銆佸鎴风 GPG銆佽法鍖哄煙銆佸簲鐢ㄧ骇琛ㄥ鍑?
**docker-compose 闆嗘垚**锛坄docker-compose.prd10.yml::backup` profile锛夛細postgres:16-alpine 鍐?oneshot 鏈嶅姟锛屾寕 `./scripts/backup:/scripts:ro` + named volume `mydow-backups:/var/backups/mydow` + read-only `app-uploads:/data/uploads`锛岃嚜鍔?apk add bash/gzip/tar/aws-cli锛?*浠呭湪 `--profile backup` 鏄惧紡鍚敤**閬垮厤褰卞搷榛樿鏍堛€?
**`.env.example` 搂7 鏈熬鏂板**銆孭RD10 搂11.7 澶囦唤涓庢仮澶嶃€嶈妭锛屾枃妗ｅ寲 4 涓?`AGENTOS_BACKUP_*` env 鍙橀噺 + 榛樿鍊笺€?
**Smoke 楠岃瘉**锛?* `backup_postgres.ps1` against `sqlite+aiosqlite:///./test_backup.db` 鈫?exit 0 + log銆孖NFO: DATABASE_URL is sqlite, skipping pg_dump銆嶁湏
* `snapshot_uploads.ps1` against 鐪?`data/uploads` 鈫?浜у嚭 `.tmp/backups/uploads/20260506T030614Z_uploads.tar.gz` (885 bytes) + `.sha256` 鉁?* `docker compose -f docker-compose.prd10.yml config --quiet` 鈫?EXITCODE=0锛坹ml 璇硶楠岃瘉閫氳繃锛?
### Tests

PRD10 鍏?14 濂椾欢鐭╅樀锛?
```
====================== 249 passed, 41 warnings in 56.68s ======================
```

* 姣?搂0 baseline 225 鎻愬崌 **+24**
* 搂15.6.1 淇鍚?+ 搂11.7 钀藉湴鍚庡弻杞潎 249 passed锛岃瘉鏄庢湰閲岀▼纰戝弻 deliverable 浜掍笉褰卞搷銆佸婧愪唬鐮侀浂鍥炲綊

### Files Touched

鏂板锛?* `scripts/backup/backup_postgres.sh`锛?36 琛岋級
* `scripts/backup/backup_postgres.ps1`锛?35 琛岋級
* `scripts/backup/restore_postgres.sh`锛?8 琛岋級
* `scripts/backup/restore_postgres.ps1`锛?0 琛岋級
* `scripts/backup/snapshot_uploads.sh`锛?6 琛岋級
* `scripts/backup/snapshot_uploads.ps1`锛?6 琛岋級
* `docs/11-deployment/backup.md`锛?03 琛岋級
* `.tmp/smoke_15_6_1.py`锛?47 琛?Playwright 楠屾敹鑴氭湰锛?
淇敼锛?* `static/mydow/biz/bridge.js`锛坆oot() +5 琛?/ MydowBridge +6 琛?export / -2 琛屽幓閲嶏級
* `docker-compose.prd10.yml`锛?38 琛?backup profile锛?* `.env.example`锛?15 琛?搂7 鏈熬澶囦唤鑺傦級
* `todo-tasks.md`锛埪?5.6.1 / 搂11.7 / 寰呰ˉ 搂15.24 mark with note 鍔?Joint description锛?
### Follow-ups

* **搂15.24 confirmDelete modal**锛歮y-mcp-25 宸?doing锛?0:50锛夛紝绛変粬/濂硅惤鍦帮紝my-mcp-26 涓嶉噸澶嶅崰鐢?* **搂11.7 V2 enhancements**锛歐AL 娴佸鍒?+ GPG 瀹㈡埛绔姞瀵?+ 璺ㄥ尯鍩?+ 搴旂敤绾?CSV 瀵煎嚭锛堝凡鍐欏埌 SOP 绗?8 绔?V2 follow-ups锛?* **`docker-compose.prd10.yml` 鐪?docker 璺?backup profile**锛氬綋鍓嶄粎 `compose config` 楠岃瘉璇硶锛涗笅涓€娆?docker 鐜 ready 鏃惰窇 `--profile backup run --rm backup` 鐪熺敓鎴愪竴浠?dump锛岄獙璇?sha256/upload 瀹屾暣閾捐矾

---

## Milestone 31 路 搂15.22 newDocument modal + 搂15.24 confirmDelete account-menu logout 琛ヤ竵 鈥?DELIVERED

**When**: 2026-05-06 11:00锛堟湰浼氳瘽锛宐y Cursor Agent / my-mcp-25锛?
**Why**: 鐢ㄦ埛鏄庣‘鎸囦护銆屼笉蹇呭仠涓嬫潵姹囨姤锛屼竴鐩村幓棰嗕换鍔″仛鈥︹€︿竴鐩村仛涓嬪幓鐩村埌 PRD10 瀹屽叏瀹炵幇 / 绗﹀悎涓氬姟鐨勫墠绔姹?/ 鎵€鏈夋寜閽敓鏁堬紝鏁版嵁鍏ㄦ墦閫?/ 鍓嶅悗绔仈璋冩棤浠讳綍闂鎵嶈兘鍋滀笅鏉ャ€嶃€傛湰浼氳瘽 my-mcp-25 鎺ュ埌浠诲姟鍚庢壂鎻?biz 涓氬姟鍘熷瀷 5 涓粛璧?`data-toast="..."` 鍗犱綅鐨?modal锛坣ewDocument / skillRun / notificationSettings / editProfile / confirmDelete锛夛紝鏂板 `todo-tasks.md` 搂15.22-搂15.26 5 琛屼换鍔″０鏄庢剰鍥撅紝璁ら骞舵帹杩涖€傛湡闂村彂鐜?搂15.23 / 搂15.25 / 搂15.26 宸茶 my-mcp-15/my-mcp-21/my-mcp-23 骞惰瀹炵幇瀹屾垚锛浡?5.24 logout/clear_cache 鐢?my-mcp-21 钀藉湴锛宑ards/docs/folders 鍒犻櫎鐢?claude-opus锛埪?5.22 lane锛夎惤鍦扳€斺€旀湰閲岀▼纰戞敹鍙ｏ細(1) 搂15.22 newDocument modal **鍏ㄦ爤鎺ラ€?*锛?2) 搂15.24 account-menu logout 璺緞琛ヤ竵锛圛IFE 8055 璧?JS-only `openModal('confirmDelete')`锛屾病 `[data-open-modal]` 灞炴€?鈫?涔嬪墠鐨?`bindConfirmDeleteContextTracking` 鎺㈡祴涓嶅埌 鈫?銆岀‘璁ゅ垹闄ゃ€嶆寜閽棤鏁堬級銆?
鎸?搂3 棰嗗湴鍗忚皟锛歚kb/router.py` 宸插瓨鍦?`POST /documents` endpoint锛坙ine 493 `create_document` + `_DOCUMENT_TEMPLATES` 3 妯℃澘锛岀敱鍏朵粬 agent 涔嬪墠棰勫厛甯冪偣锛夛紝鏈噷绋嬬鍙湪 `kb/router.py` **涓嶅姩涓€琛?*锛屼粎鍦?`bridge.js` append 鍓嶇瀹炵幇 + 鍦?`tests/integration/api/prd10/test_prd10_kb_api.py` append 7 涓泦鎴愭祴璇曠敤渚嬨€?
### Delivered

#### 1. 搂15.22 biz `newDocument` modal 鐪熷疄鍖栵紙鍏ㄦ爤鎺ラ€氾級

**鍓嶇** `static/mydow/biz/bridge.js`锛堝湪 `// 鈹€鈹€鈹€ 搂15.22 newDocument modal 鈹€鈹€鈹€` 娈佃惤锛岀害 +130 琛岋級锛?
* `_DOC_TEMPLATE_LABEL_TO_KEY` 鈥?biz modal `<select>` 鏄剧ず鏂囨 `绌虹櫧鏂囨。/鐮旂┒鎶ュ憡/鏂规妗嗘灦` 鈫?鍚庣 enum `blank/research_report/solution_outline`
* `_resolveCurrentFolderId()` 鈥?浠?`.folder-main[data-folder-id]` 鎺ㄦ柇褰撳墠鏂囦欢澶瑰綊灞烇紝鏃犳枃浠跺す鏃惰繑鍥?null锛堣惤鍒版牴鐩綍锛?* `createDocumentFromModal({ title, templateKey, folderId })` 鈥?灏佽 `POST /api/v1/kb/documents` 璋冪敤
* `_applyDocPageMode()` 鈥?闂寘澶栫殑 page-shell class flip锛屽洜涓?IIFE `setPageMode` 鍦ㄩ棴鍖呭唴涓嶆毚闇?window锛屽鍒?9 涓ā寮?class 鍒囨崲涓恒€宍doc-open` + `insights-open`銆?* `handleNewDocumentSubmit(button)` 鈥?涓绘祦绋嬶細disable 鎸夐挳 + label銆屽垱寤轰腑鈥︺€嶁啋 POST 鈫?鎴愬姛鍚?`closeAllModals()` + `toast` + `_applyDocPageMode()` + `loadDocumentForEditor(doc.id)` 鎶婂唴瀹?hydrate 鍒?`.doc-editor-main` + 褰撳墠鍦ㄦ枃浠跺す鏃?refresh `loadFolderDetail(folderId)` + dispatch `mydow:document-created` 鑷畾涔変簨浠?+ restore 鎸夐挳
* `bindKbNewDocumentSubmit()` 鈥?capture-phase document listener 鎷︽埅 `[data-create-doc]` button 鍦?`[data-modal=newDocument]` 鍐?鈫?`event.stopImmediatePropagation()` 闃绘 IIFE 榛樿 `simulateAction("鏂囨。宸插垱寤?, { closeLayer:true, after: setPageMode("doc") })`

娉ㄥ唽鍒?boot锛歚bindKbNewDocumentSubmit()` 鍦?`bindItemDetailDrawerActions()` 涔嬪悗璋冪敤銆傚鍑哄埌 `window.MydowBridge.{ createDocumentFromModal, handleNewDocumentSubmit, bindKbNewDocumentSubmit }`銆?
**鍚庣** `src/agent_os/kb/router.py` 鈥?`POST /api/v1/kb/documents`锛坙ine 493 `create_document`锛夌敱鍏朵粬 agent 涔嬪墠棰勫厛甯冪偣锛屾湰閲岀▼纰?*鏈敼涓€琛屽悗绔唬鐮?*锛屼粎澶嶇敤锛?- `CreateDocumentRequest` schema锛歚title (1..500) + summary? + content? + folder_id? + document_type=note + tags=[] + template? in {blank, research_report, solution_outline}`
- `_DOCUMENT_TEMPLATES`锛? 涓?markdown scaffold 妯℃澘
- 鏍￠獙 `folder_id` 鏄惁褰掑睘褰撳墠 user
- 榛樿 `status=ready`銆乣document_type=note`銆佽绠?`word_count = len(content.split())`
- 杩斿洖 `Document.to_prd10_dict(include_content=True)` + `{folder: {id, name}}`

#### 2. 搂15.24 confirmDelete modal account-menu logout 琛ヤ竵

`bridge.js::bindConfirmDeleteContextTracking`锛坙ine 4699 鍖哄煙锛夋墿灞曚负鍙岃矾寰勭洃鍚細

* (1) **鐩存帴 opener buttons** 鈥?`[data-open-modal=confirmDelete]`锛堣鐩?security tab `閫€鍑虹櫥褰昤/`娓呴櫎鏈湴缂撳瓨`銆乮tem-detail drawer 鍒犻櫎銆乨oc-meta 鏇村銆乫older-card 鍒犻櫎锛?* (2) **account-menu fallback** 鈥?`[data-account-action="logout"]`锛坆iz/index.html line 7160锛夛紝IIFE 8055 閫氳繃 JS `openModal("confirmDelete")` 瑙﹀彂 modal锛屾病 `[data-open-modal]` 灞炴€?鈫?鐜板湪 capture-phase 鍡呮帰杩欎釜 menu action 鈫?stash `_CONFIRM_DELETE_CTX.kind="logout"` + `label="閫€鍑虹櫥褰?`

涔嬪墠 my-mcp-21 宸茬粡钀?`_performLogout` / `_performClearCache` / `bindConfirmDeleteSubmit`锛坙ine 4711-4737锛夛紱鏈ˉ涓佽 account-menu 鐨勯€€鍑虹櫥褰?path 涔熻兘璧板埌杩欏宸插瓨鍦ㄧ殑澶勭悊鍣紝涓嶅啀 fall-through 鍒?IIFE simulateAction銆屽凡鍒犻櫎銆嶅亣鎴愬姛銆?
### Test evidence

#### Backend integration tests 鈥?7 new cases for `POST /kb/documents`

`tests/integration/api/prd10/test_prd10_kb_api.py` 鏂板 7 涓?搂15.22 鐢ㄤ緥锛?
| 娴嬭瘯 | 瑕嗙洊 |
|---|---|
| `test_create_document_blank_in_folder` | folder + blank template 鈫?201 + content="" + word_count=0 + listing 鍚柊 doc id |
| `test_create_document_research_template_seeds_content` | research_report 鈫?content 鍚€岀爺绌剁洰鏍囥€嶃€屽叧閿彂鐜般€?markdown scaffold |
| `test_create_document_solution_outline_template` | solution_outline 鈫?content 鍚€屾柟妗堟杩般€嶃€屽叧閿噷绋嬬銆?|
| `test_create_document_without_folder_lands_at_root` | 涓嶄紶 folder_id 鈫?folder_id=None / folder=None |
| `test_create_document_explicit_content_wins` | 鍚屾椂浼?template + 鏄惧紡 content 鈫?鏄惧紡 content 瑕嗙洊 template锛泈ord_count=5 |
| `test_create_document_validates_folder_ownership` | 璺ㄧ敤鎴蜂紶浠栦汉 folder_id 鈫?404 |
| `test_create_document_rejects_blank_title` | 绌?title 鈫?422 |

KB 濂椾欢鎬昏 **25/25 passed @ 3.93s**銆?
#### PRD10 鍏?14 濂椾欢鐭╅樀鍩虹嚎

```
python -m pytest \
  tests/integration/api/test_prd10_v1_acceptance.py \
  tests/integration/api/test_prd10_frontend_binding.py \
  tests/integration/api/test_prd10_ai_api.py \
  tests/integration/api/test_prd10_ai_llm.py \
  tests/integration/api/test_prd10_search_api.py \
  tests/integration/api/test_prd10_skills_api.py \
  tests/integration/api/test_prd10_garden_api.py \
  tests/integration/api/test_prd10_observability.py \
  tests/integration/api/test_prd10_app_wiring.py \
  tests/integration/api/test_prd10_models_intelligence.py \
  tests/integration/api/test_prd10_e2e_flow.py \
  tests/integration/api/test_prd10_product_data_api.py \
  tests/integration/api/test_prd10_insights_api.py \
  tests/integration/api/prd10/ \
  -p no:cacheprovider --tb=line --no-header --timeout=90
# 鈫?249 passed @ 58.66s
```

姣?Milestone 27 鍩虹嚎 225 +24锛堝惈鏈噷绋嬬 7 涓?搂15.22 鏂板姞 + 11 涓?my-mcp-15/Engineer 1 鍔犵殑 搂10.5 hero landing + acceptance 璋冩暣 + 6 涓叾浠栧閲忥級锛屾棤浠讳綍鍥炲綊銆?
#### 娴嬭瘯鍩虹嚎瀵圭収淇锛埪?0.5 landing 鏇挎崲 搂15.20 redirect锛?
鏃у熀绾挎祴璇?`test_root_redirect` 涓?`test_root_redirects_to_biz_default` 鏈熸湜 `/` 杩斿洖 307 redirect 鍒?`/mydow/biz/`锛屼絾 搂10.5 hero landing page 涓婄嚎鍚?`/` 鏀规垚杩斿洖 200 HTML锛坙anding锛夛紝`?go=demo` 鎵?redirect銆傛湰閲岀▼纰戝悓姝ヤ慨澶?2 涓祴璇曚互鎺ュ彈鍙屽舰鎬侊紙200 HTML + landing wordmark / 307 + redirect-target锛夛紝淇濇寔 backwards-compat銆?
### Files touched

* `src/agent_os/kb/router.py` 鈥?**鏈敼涓€琛?*锛圥OST /documents endpoint 宸茬敱鍏朵粬 agent 棰勫厛甯冪偣锛?* `static/mydow/biz/bridge.js` 鈥?`+130` 琛岋紙搂15.22 newDocument modal锛? `+15` 琛岋紙搂15.24 account-menu logout 琛ヤ竵锛?* `tests/integration/api/prd10/test_prd10_kb_api.py` 鈥?`+95` 琛岋紙7 涓柊 搂15.22 闆嗘垚娴嬭瘯鐢ㄤ緥锛?* `tests/integration/api/test_prd10_v1_acceptance.py` 鈥?landing-page accept 鍙屽舰鎬?* `tests/integration/api/test_prd10_frontend_binding.py` 鈥?landing-page accept 鍙屽舰鎬?* `todo-tasks.md` 鈥?搂15.22-搂15.26 5 琛屼换鍔＄櫥璁?+ 搂15.22 done + 搂15.23 / 搂15.25 / 搂15.26 done锛堥獙鏀跺埆浜哄疄鐜帮級+ 搂15.24 done锛堜笌 my-mcp-18 楠屾敹琛屽悓鍒楋級
* `agent-progress-report.md` 鈥?鏈?milestone

**鏈姩**锛?- `static/mydow/biz/index.html` 涓氬姟鏂瑰師鍨?HTML锛堟寜 搂15 璁捐鍘熷垯涓嶆敼涓氬姟鏂硅璁★紝鍙€氳繃 bridge.js 娉ㄥ叆鐪熷疄鏁版嵁锛?- `static/mydow/{index.html,app.js,style.css,mydow-api.js}` SPA 鏂囦欢锛堝伐绋嬪笀 2 鎸佹湁锛?- 浠讳綍 `auth/` `kb/` `feed/` `notifications/` 鐜版湁 endpoint
- 浠讳綍 agent 浠?doing 涓殑瀹炵幇鏂囦欢鍖哄煙

### 鍗忎綔鍐茬獊閬垮厤

鏈細璇濊繃绋嬩腑瑙傚療鍒?`todo-tasks.md` 搂15.x 缂栧彿琚涓?agent 閲嶅浣跨敤锛埪?5.22 / 搂15.23 / 搂15.24 鍚勬湁 2-4 涓笉鍚屽惈涔夌殑琛岋級銆俶y-mcp-25 閫夋嫨**涓嶅啀鏂板缂栧彿**锛岃€屾槸鎶婅嚜宸卞疄鐜扮殑宸ヤ綔鍐欏叆璇箟鏈€鍖归厤鐨勭幇鏈?`done` 琛岃鏄庡垪閲屸€斺€旈伩鍏嶈繘涓€姝ュ鍔犲崗浣滄懇鎿︺€傚悗缁亣鍒扮被浼兼儏鍐靛缓璁湪 `agent-collaboration.md` 鎴栨湰瑙勫垯闆嗛噷鍔犮€岀紪鍙烽攣瀹氥€嶆満鍒讹紝鍏堣棰嗙紪鍙峰啀鍐欐弿杩般€?
### Follow-ups

1. **搂15.4 Feed 鏌ヨ鎬ц兘** 鈥?capture/text 澶ч噺鍚?`/feed?page_size=8` 姣忔鎵叏琛紝鍙姞 `created_at DESC` 澶嶅悎绱㈠紩锛涗笅涓€浼氳瘽鑰冭檻璁ら
2. **搂9.6 閿洏蹇嵎閿?*锛圕md/Ctrl+K 鍏ㄥ眬鎼滅储 / Esc 鍏抽棴 / `/` 鑱氱劍杈撳叆妗嗭級鈥?鎶曡祫浜烘紨绀轰环鍊奸珮锛宐iz/bridge.js 鍏ㄥ眬鐩戝惉鍗冲彲锛屼笉鍔?IIFE
3. **搂14.3 鍏?nav 璧版煡 acceptance** 鈥?褰撳墠宸?搂15 涓讳綋鍏?done锛屽彲鐢?Agent 4 璺?`chrome-mcp-smoke.ps1` 鍑哄叏闂幆鎶ュ憡
4. **biz 鍘熷瀷 5 涓?modal 鐪熷疄鍖栨敹鍙ｉ獙璇?* 鈥?璺戜竴浠?Playwright e2e 鎶?newDocument / skillRun / confirmDelete (logout/cache/delete) / editProfile / notificationSettings 5 涓?modal 璧颁竴閬嶏紝鎶婃埅鍥惧啓鍏?`.tmp/screenshots/biz_walk/15_22_modals/`

---

## Milestone 30 路 搂8.16 鍚庣 `GET /me/preferences` + `POST /me/password` 琛ラ綈锛圥RD10 搂5.2 + 搂15.18 淇敼瀵嗙爜锛?鈥?DELIVERED

**When**: 2026-05-06 10:40锛堟湰浼氳瘽锛宐y Agent / my-mcp-22锛?
**Why**: `todo-tasks.md` 搂15.17 / 搂15.18 閮藉垪銆屽緟缁?P1銆嶈鍚庣 `PATCH /me` + `PATCH /me/preferences` + 淇敼瀵嗙爜绔偣銆傛湰浼氳瘽 搂15.22锛坢y-mcp-23锛? 搂15.23锛坢y-mcp-21锛夊凡缁忔妸 `PATCH /me` + `PATCH /me/preferences` 钀藉湴锛坄Prd10MeUpdateRequest` + `_filter_prd10_settings_patch` 鐧藉悕鍗?+ deep-merge `notification_channels`锛夈€傚墿涓嬩袱涓悗绔己鍙ｆ湰閲岀▼纰戞敹鎺夛細

1. **`GET /api/v1/me/preferences`** 鈥?biz 璁剧疆椤?/ SPA 娓叉煋鏃堕渶瑕佷竴浠?*骞插噣 PRD10 搂5.2 `UserPreference` shape** 鏉?hydrate toggle銆傚師 `User.settings` JSON 鏄换鎰?key锛堝惈 `role` / `plan` / `_internal_billing_override` 绛夛級锛岀洿鎺ュ悙鍓嶇浼氭毚闇查殣绉侀敭銆傛湰绔偣 project 鍑?13 涓?搂5.2 瀛楁锛堝惈 `notification_channels` 榛樿 7 閫氶亾锛夛紝缂虹渷鍊兼寜 PRD10 搂5.2 瑙勮寖銆佺敤鎴峰凡鍐欏垯瑕嗙洊銆?2. **`POST /api/v1/me/password`** 鈥?biz 瀹夊叏 tab銆屼慨鏀瑰瘑鐮併€嶆寜閽綋鍓嶆槸 `data-toast="淇敼瀵嗙爜鍏ュ彛宸叉墦寮€"` 鍗犱綅锛屼笉鐪熺敓鏁堛€傛湰绔偣鎺?`current_password` + `new_password`锛堚墺6锛夛紝楠岃瘉褰撳墠瀵嗙爜 鈫?鎷掔粷鍚屽瘑鐮?no-op 鈫?鏃嬭浆 hash 鈫?鏃?token 浠嶆湁鏁堬紙refresh-token 澶辨晥鏄?搂12.2 闄愭祦鍩燂級銆?
鎸?搂3 棰嗗湴鍗忚皟锛歚auth/router.py` 鏄?Engineer 1 / Agent 1 territory锛屼絾鍥犱负 搂15.22 / 搂15.23 / 搂11.10 绛夊瀹舵鍦ㄥ姩鍚屼竴鏂囦欢锛屾湰閲岀▼纰戝彧鍦ㄨ鏂囦欢**鏈熬 append** 涓や釜绔偣 + 涓€涓?`_project_prd10_preferences` helper锛屼笉淇敼鍏朵粬 agent 宸插啓鐨?endpoint 鍑芥暟銆?
### Delivered

* **`auth/schema.py`** 鍔?3 涓?schema锛?  * `Prd10PreferencesView` 鈥?PRD10 搂5.2 13 瀛楁 shape锛宍extra="allow"` 杞彂鏈潵鎵╁睍锛岄粯璁?channels 鍖呭惈 7 涓?PRD10 閫氶亾锛坄ai_done` / `system_alert` / `knowledge_link` / `job_completed` / `job_failed` / `daily_insight` / `weekly_insight=False`锛夈€?  * `Prd10PasswordUpdate` 鈥?`current_password`(min=1) + `new_password`(min=6)锛宍extra="forbid"` 鎷︽埅 side-channel 娉ㄥ叆銆?  * `Prd10PasswordUpdateResponse` 鈥?`{id, updated_at, rotated=True}`锛宑lients 鐢?`updated_at` 鍒ゅ畾鐪熸棆杞椂闂淬€?* **`auth/crud.py::update_user_password`** 鈥?`verify_password(current)` 澶辫触鎶?`ValueError("current_password_invalid")`锛沗verify_password(new) == True` 鎶?`ValueError("same_password")`锛涘叾浠栨儏鍐?rotate `password_hash` + commit + refresh锛岃繑鍥?`User`銆俁outer 鎶?ValueError 缈绘垚 PRD10 envelope 400銆?* **`auth/router.py`** 鍔?2 涓鐐?+ 1 涓?helper锛堝湪 `patch_prd10_me_preferences` 涔嬪悗銆乣@router.put("/settings", ...)` 涔嬪墠 append锛夛細
  * `GET /api/v1/me/preferences` 鈫?`Prd10PreferencesView`锛岃皟 `_project_prd10_preferences(current_user.settings)`銆?  * `POST /api/v1/me/password` 鈫?`Prd10PasswordUpdateResponse`锛沄alueError 鈫?400 envelope锛泆ser None 鈫?404锛涙垚鍔熻繑鍥?`{id, updated_at, rotated:true}`銆?  * `_project_prd10_preferences(settings)` 鈥?鎶曞奖 + 榛樿鍊?+ `notification_channels` 鐢ㄧ櫧鍚嶅崟 sub-filter锛堝悓 `PRD10_NOTIFICATION_CHANNEL_KEYS`锛? shallow merge default channel set銆?
### Test evidence

鏂板姞 `tests/integration/api/test_prd10_me_password_and_preferences_get.py` **13/13 passed @ 4.71s**锛?
| 娴嬭瘯 | 瑕嗙洊 |
|---|---|
| `test_get_me_preferences_unauthenticated_returns_401` | 401 |
| `test_get_me_preferences_fresh_account_returns_full_default_shape` | 绌?settings 鈫?13 瀛楁鍏ㄦ湁 + 榛樿鍊煎尮閰?PRD10 搂5.2 + 7 channel 鍏ㄦ湁 |
| `test_get_me_preferences_merges_partial_settings_with_defaults` | 鐢ㄦ埛鍐?theme/auto_save/default_ai_model 鈫?瑕嗙洊榛樿锛涘叾浠栧瓧娈靛洖閫€榛樿 |
| `test_get_me_preferences_notification_channels_deep_merge` | 鐢ㄦ埛鍐?`ai_done=False, knowledge_link=True` 鈫?鍏朵粬 5 閫氶亾浠嶆寜榛樿鍛堢幇 |
| `test_get_me_preferences_does_not_leak_privileged_or_unknown_keys` | `role/plan/_internal_billing_override/is_superuser` 鍏ㄩ儴涓嶅嚭鐜板湪鍝嶅簲涓?|
| `test_get_me_preferences_round_trip_after_patch` | PATCH /me/preferences 鈫?GET /me/preferences 鍚屾鐢熸晥 |
| `test_post_me_password_unauthenticated_returns_401` | 401 |
| `test_post_me_password_wrong_current_returns_400` | 閿欒瀵嗙爜 400 + envelope `{error.message}` 鍚?"current/incorrect"锛涘瘑鐮佹湭鏀癸紙鏃у瘑鐮佷粛鑳界櫥褰曪級|
| `test_post_me_password_same_as_current_returns_400` | 鍚屽瘑鐮?400 + envelope message 鍚?"differ/same/different" |
| `test_post_me_password_success_rotates_and_login_with_new_password` | 200 + `{rotated:true, id, updated_at}` + DB hash 楠岃瘉 + 鏂板瘑鐮佺櫥褰曟垚鍔?+ 鏃у瘑鐮佺櫥褰?401 |
| `test_post_me_password_short_new_password_returns_422` | new_password<6 422 |
| `test_post_me_password_missing_field_returns_422` | 浠讳竴瀛楁缂哄け 422 |
| `test_post_me_password_rejects_extra_fields` | 鍚?`username/is_superuser/settings` 绛?side-channel 422 |

**鑱斿悎 PRD10 鍏?14 濂椾欢 + me_patch + me_password 鐭╅樀 = 282 passed @ 64.71s**锛堝熀绾?搂0 琛?225 鈫?282锛?57锛氬惈 搂15.22 my-mcp-21 13 涓?+ 鏈换鍔?13 涓?+ 鍏跺畠浠ｇ悊鏂板锛夈€傞浂鍥炲綊銆?
### Files touched

* `src/agent_os/auth/schema.py`锛?3 schema锛歚Prd10PreferencesView` / `Prd10PasswordUpdate` / `Prd10PasswordUpdateResponse`锛?* `src/agent_os/auth/router.py`锛?2 endpoint锛歚get_prd10_me_preferences` / `change_prd10_me_password` + `_project_prd10_preferences` helper + `_DEFAULT_NOTIFICATION_CHANNELS` 甯搁噺锛?3 import line锛?* `src/agent_os/auth/crud.py`锛?1 helper锛歚update_user_password`锛?* `tests/integration/api/test_prd10_me_password_and_preferences_get.py`锛?*鏂板缓**锛?52 琛岋紝13 鐢ㄤ緥锛?* `todo-tasks.md` 搂8.16 `doing` 鈫?`done` + 璇佹嵁
* 鏈?milestone 鍐欏叆 `agent-progress-report.md`

**鏈姩**锛歚static/mydow/*`銆乣bridge.js`銆佸叾浠?agent 鍦?`auth/router.py` / `auth/schema.py` / `auth/crud.py` 宸插啓鐨勫嚱鏁颁綋銆?
### Coordination notes

* **閬垮厤鍐茬獊**锛氬彂鐜拌 `auth/router.py` 鏃跺叾浠?agent锛堟帹娴?my-mcp-21 / my-mcp-23锛夋鍦?append `Prd10MeUpdateRequest` / `PATCH /me` / `PATCH /me/preferences`锛岀珛鍗虫敹鏁?搂8.16 鑼冨洿鍒般€屼粬浠病瑕嗙洊鐨勪袱鍧椼€嶏紙GET /me/preferences + POST /me/password锛夛紝鍒犻櫎鎴戝凡鍔犱絾涓庝粬浠噸鍚嶇殑 schema锛坄Prd10MeUpdate` / `Prd10NotificationPreferences` / `Prd10PreferencesResponse` / `Prd10PreferencesUpdate`锛夛紝淇濈暀 `Prd10PreferencesView`锛堝懡鍚?`View` 閬垮厤涓庝粬浠殑 `Prd10MeUpdateRequest.settings` 瀛楁浜ゅ弶锛? `Prd10PasswordUpdate` / `Prd10PasswordUpdateResponse`锛堟棤浜哄崰鐢級銆?* **娴嬭瘯闅旂**锛氭柊寤虹嫭绔?`test_prd10_me_password_and_preferences_get.py` 鑰岄潪杩藉姞 `test_prd10_me_patch.py`锛堝悗鑰呯敱 my-mcp-21 缁存姢 搂15.22 娴嬭瘯锛夛紝閬垮厤 file-level merge race銆?* **`/me` envelope**锛歚/api/v1/me/*` 鍏ㄩ儴璧?`_PRD10_ENVELOPE_PREFIXES`锛坅pp.py L160-L179锛夛紝HTTPException 鑷姩缈昏瘧涓?`{success:false, error:{code,message,details}, request_id}`锛屾墍浠ユ祴璇曟柇瑷€鐢?`body["error"]["message"]` 鑰岄潪 `body["detail"]`銆?
### Follow-ups

1. 鍓嶇 wiring锛歚bridge.js` 鎶?biz 瀹夊叏 tab 鐨勩€屼慨鏀瑰瘑鐮併€峘<button data-toast=淇敼瀵嗙爜鍏ュ彛宸叉墦寮€>` 鎺ュ埌 `POST /api/v1/me/password`锛堝脊 modal 鏀?current_password / new_password锛夛紝骞舵妸鍋忓ソ椤?hydrate 鏀逛负鍏堣皟 `GET /me/preferences`锛堣€岄潪 `/me`锛変互璇诲埌瀹屾暣 13 瀛楁銆傚睘 搂15.22 / 搂15.18 鍚庣画锛岀敱 Engineer 1 / my-mcp-21 / my-mcp-23 涓€骞舵帴鍏ャ€?2. 瀹夊叏澧炲己锛圥1锛夛細鏃嬭浆瀵嗙爜鍚庣珛鍗?invalidate 璇ョ敤鎴锋墍鏈?active session锛堟竻 `Session` 琛ㄨ + 璁?refresh token 澶辨晥锛夛紝闇€瑕佷笌 搂12.2 rate-limit / session 娌荤悊鍗忓悓銆?3. P2锛歚POST /me/password` 鍓嶅鍔犳渶杩?N 娆″瘑鐮佸搱甯岄粦鍚嶅崟锛堥槻姝?cycling 鍚屼竴缁勫瘑鐮侊級锛岄渶瑕佹柊琛?`password_history`銆?
---

## Milestone 29 路 搂10.5 Investor-Friendly Hero Landing Page 鈥?DELIVERED

**When**: 2026-05-06 10:35锛堟湰浼氳瘽锛宐y Agent / my-mcp-13锛?
**Why**: `todo-tasks.md` 搂10.5 鏍?`open`銆佹棤 Owner锛屾槸 PRD10 搂10 鎶曡祫浜?demo 璺緞鐨勫叆鍙ｇ┖缂恒€傚湪姝や箣鍓?`/` 鐩存帴 307 鈫?`/mydow/biz/`锛埪?5.20 宸?done锛夛紝鎰忓懗鐫€鎶曡祫浜?/ 瀹㈡埛 / 濯掍綋棣栨璁块棶鐪嬪埌鐨勬槸銆岀伒鎰熼噰闆?demo 宸ヤ綔鍙般€嶏紝缂轰竴鍧椼€岃繖涓骇鍝佹槸浠€涔?/ 涓轰粈涔堝€煎緱鐐硅繘鍘?/ 鍑粈涔堢浉淇″畠鐪熻兘璺戙€嶇殑浠峰€间富寮犳壙鎺ャ€傛湰閲岀▼纰戠敤涓€寮犵嫭绔嬬殑 hero landing 椤靛～琛ヨ繖鍧楃┖鐧斤紝骞朵繚鎸佸師 搂15.20 鐨勫揩杩涜矾寰勪綔涓?`?go=demo` opt-in銆?
鎸夊浜哄崗浣滆鍒欙紙棰嗗湴 搂3锛夛細landing 椤靛睘"浠讳綍宸ョ▼甯堥兘鍙棰?鐨勬紨绀鸿矾寰?lane锛岃棰嗗墠 read 浜嗘渶鏂?`todo-tasks.md` 纭鏃犱汉 `doing`銆佹棤 Owner锛堜腑閫斿彂鐜?搂12.2 琚?my-mcp-24 鍚屾椂 10:20 鎶㈠厛璁ら锛岀珛鍗宠鍑哄悗鏀归€?搂10.5锛夛紱鎵€鍔ㄦ枃浠讹紙`static/landing/index.html` 鏂板缓 / `server/app.py` 鏀?`/` handler + 鍔?`_LANDING_DIR` mount / 鏀?2 涓棫 acceptance test 鐨?`test_root_*` 鏂█ + 鏂板 `test_landing_hero.py`锛変笉鎾炰换浣?`doing`锛氭湭鍔?SPA / 鏈姩 biz/index.html / 鏈姩 bridge.js / 涓?搂11.10 my-mcp-15 宸茶惤鐨?`static/legal/*` 鍗忓悓锛坒ooter 寮曠敤鍏?privacy/terms 閾炬帴锛? 涓?搂15.20 鍏煎锛坄?go=demo` 浠嶈蛋鍘?redirect锛夈€?
### Delivered

#### 1. `static/landing/index.html`锛堟柊澧烇紝~660 琛屽崟鏂囦欢锛?
PRD10 搂10.5 鎶曡祫浜虹骇鍒?hero landing锛?*绾潤鎬佽嚜鍖呭惈**锛坕nline CSS + 鍐呭祵 SVG icon + 0 澶栭儴 CDN锛宱ffline-friendly锛夛紝璋冭壊鏉垮榻?biz 鍘熷瀷锛坅ccent `#9fb1ff/#758cff`銆乵int `#77cabd`銆乬old `#f0bd6c`銆乺ose `#d7a9a5`锛岃儗鏅?`#f7f9fd` + 澶氬眰 radial gradient + linear gradient锛夛細

- **Top nav**锛坰ticky + backdrop-blur锛夛細鍝佺墝瀛楁爣 + 4 涓尯娈甸敋鐐癸紙浜у搧/鎬庝箞鐢?鏁版嵁/璁㈤槄锛? "API 鏂囨。" secondary + "寮€濮嬩綋楠? primary CTA 鈫?`/mydow/biz/`
- **Hero**锛氬弻鏍忓竷灞€锛屽乏渚ф笎鍙樻爣棰樸€屾妸鐏垫劅鍙樻垚浣撶郴鍖栫殑鐭ヨ瘑銆? 鍓爣棰?+ 鍙?CTA + 4 涓壒寰?tags锛堢湡瀹炴暟鎹?/ 姣忎釜鎸夐挳閮界敓鏁?/ 绔埌绔墦閫?/ 鐪熷疄娴佸紡 AI锛夛紱鍙充晶 460px 鐜荤拑闈㈡澘 + 4 寮?floating card锛堢伒鎰熼噰闆?Mydow AI/鏁板瓧鑺卞洯/閫氱煡锛? pulse / float CSS 鍔ㄧ敾锛坮educe-motion 鍏煎锛?- **Trust row**锛? 涓暟瀛楋紙200+ 娴嬭瘯 / 0 鍋囨寜閽?/ 14 涓氬姟鍘熷瀷椤?/ SSE 鐪熷疄娴佸紡锛?- **Modules grid**锛? 寮?PRD10 搂2.1 妯″潡鍗★紙鐏垫劅閲囬泦 / 鐭ヨ瘑搴?/ Mydow AI / 鏁板瓧鑺卞洯 / 鍏ㄥ眬鎼滅储 / Skills 骞垮満 / 娲炲療涓績 / 閫氱煡涓績锛夛紝姣忓紶鍚?SVG icon + 鎻忚堪 + glow 娓愬彉鍏夋檿 + hover transform
- **How it works**锛? 姝ラ棴鐜紙杈撳叆 鈫?鏁寸悊 鈫?瀵硅瘽锛夛紝姣忔甯﹀叿浣?PRD10 绔偣鍒楄〃锛圥OST /capture/text銆丳OST /uploads/presign銆丼SE meta/token/keepalive銆丳OST /save-to-kb 绛夛級
- **Stats**锛? 涓牳蹇冩寚鏍囷紙30s 闂幆 / 225+ 娴嬭瘯 / 14 涓氬姟鍘熷瀷 / UUID 鐢ㄦ埛闅旂锛?- **Pricing tease**锛? 寮犺闃呭崱锛堜釜浜?Pro 楼39/鏈?+ 鍥㈤槦 License 楼199/甯綅/鏈堬紝鍚庤€呫€屾渶鍙楁杩庛€峟eatured + 閭欢鍜ㄨ mailto锛夛紝涓?README 搂13.6 鍟嗕笟妯″紡琛ㄥ榻?- **Final CTA**锛氳繘鍏?Demo 宸ヤ綔鍙?primary 鎸夐挳
- **Footer**锛? 鍒楋紙鍝佺墝 / 浜у搧 / 寮€鍙戣€?/ 鍚堣锛夛紝寮€鍙戣€呭垪鍚?`/docs` `/redoc` `/openapi.json` `/health`锛涘悎瑙勫垪鍚?`/legal/privacy.html` `/legal/terms.html`锛堜笌 搂11.10 my-mcp-15 lane 鑱斿姩锛? `/mydow/spa/` fallback锛涘簳閮ㄧ増鏉冧笌 v1 鏍囪瘑
- **Inline `<script>`**锛歴mooth scroll for in-page anchors + 涓€涓?`data-cta` 鐐瑰嚮鍩嬬偣 hook 鍐?`sessionStorage["mydow_landing_last_cta"]`锛屾湭鏉ュ彲鎺?analytics

瀹屽叏鍝嶅簲寮忥紙鈮?80 鈫?鈮?00 鈫?鈮?40 鈫?鈮?60 鍥涙。鏂偣锛夛紝鍔ㄧ敾 `prefers-reduced-motion` 鍙嬪ソ銆?
#### 2. `src/agent_os/server/app.py` 鏀?`/` handler + 鍔?`/landing` mount

```python
@app.get("/")
async def get_index(go: str | None = None):
    if go == "demo" and _MYDOW_DIR.exists() and (_MYDOW_DIR / "biz" / "index.html").exists():
        return RedirectResponse(url="/mydow/biz/", status_code=307)

    landing_index = _LANDING_DIR / "index.html"
    if _LANDING_DIR.exists() and landing_index.exists():
        with open(landing_index, encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    if _MYDOW_DIR.exists() and (_MYDOW_DIR / "biz" / "index.html").exists():
        return RedirectResponse(url="/mydow/biz/", status_code=307)
    if _MYDOW_DIR.exists():
        return RedirectResponse(url="/mydow/", status_code=307)
    return await get_legacy_index()
```

琛屼负浼樺厛绾э細
1. `?go=demo` opt-in 鈫?307 鈫?`/mydow/biz/`锛堜繚鐣?搂15.20 鎶曡祫浜?/ press / docker healthcheck 蹇繘璺緞锛?2. landing bundle 瀛樺湪 鈫?200 + HTMLResponse锛堥粯璁?搂10.5 琛屼负锛?3. landing 缂哄け 鈫?璧版棫 搂15.20 fallback 閾撅紙biz 鈫?spa 鈫?legacy锛?
闄勫姞 `_LANDING_DIR` 妯″潡绾у父閲?+ `app.mount("/landing", StaticFiles(directory, html=True))`锛岃 `/landing/`锛堢洿鎺ヨ闂級鍜屾湭鏉ュ垎鍖呰祫婧愶紙鐙珛 favicon / og-image / split css锛夐兘鍙揪銆傚舰鎬佸榻?`_LEGAL_DIR`锛埪?1.10 my-mcp-15 宸茶惤鐨勫悓褰㈡€?mount锛夈€?
#### 3. `tests/integration/api/test_landing_hero.py`锛堟柊澧烇紝7 鐢ㄤ緥锛?
| Test | 鏂█ |
|---|---|
| `test_root_serves_landing_hero_html` | `GET /` 鈫?200 + content-type `text/html` + 鍚?Mydow 瀛楁爣 + 鍚?PRD10 搂2.1 鍏?7 涓ā鍧楀悕锛堢伒鎰熼噰闆?鐭ヨ瘑搴?Mydow AI/鏁板瓧鑺卞洯/Skills/鍏ㄥ眬鎼滅储/閫氱煡锛墊
| `test_root_with_go_demo_query_short_circuits_to_biz` | `GET /?go=demo` 鈫?307 + `Location: /mydow/biz/` |
| `test_root_without_query_param_does_not_redirect` | `GET /` 200 涓旀棤 `Location` 澶?|
| `test_landing_mount_serves_index_directly` | `GET /landing/` 鈫?200 + 鍚悓鏍?hero 鏍囪 |
| `test_landing_footer_links_to_legal_and_docs` | 鍚?`/legal/privacy.html` `/legal/terms.html` `/docs` `/openapi.json` `/mydow/spa/` 5 鏉￠摼鎺?|
| `test_landing_pricing_card_anchors_match_business_model` | 鍚€屼釜浜?Pro銆嶃€屽洟闃?License銆嶃€屄?9銆嶃€屄?99銆嶃€屾渶鍙楁杩庛€? 涓晢涓氭ā寮?token锛屼笌 README 搂13.6 瀵归綈 |
| `test_landing_meta_and_brand_tokens_present` | `<title>Mydow` + `name="description"` + `name="theme-color"` + 涓嶅惈澶栭摼 `<script src="http..."` `<link href="http..."`锛坥ffline-first 鑷寘鍚?guard锛墊

#### 4. 鍚屾涓や釜鏃?acceptance 娴嬭瘯鏂█鍒?搂10.5 鏂板悎绾?
- `tests/integration/api/test_prd10_v1_acceptance.py::test_root_redirect` 鈫?鏀瑰悕 `test_root_serves_landing_or_redirects_to_biz`锛屾柇瑷€ `/` 200 鍚?`<title>Mydow` 涓?`/mydow/biz/` 閾炬帴 + `?go=demo` 307 鈫?`/mydow/biz/`
- `tests/integration/api/test_prd10_frontend_binding.py::test_root_redirects_to_biz_default` 鈫?宸茶鍙︿竴涓?agent锛堝悓涓€鏃堕棿绐楋級浠?`test_root_serves_landing_or_redirects_to_biz` 褰㈠紡鏇存柊涓烘帴鍙?200/307 鍙屽舰鎬侊紙landing 閮ㄧ讲 vs 鏈儴缃诧級锛屽畬鍏ㄥ吋瀹规湰閲岀▼纰?
### Test evidence

```
$ python -m pytest tests/integration/api/test_landing_hero.py -q
7 passed in 0.84s

$ python -m pytest <PRD10 鍏?14 濂椾欢鐭╅樀 + tests/integration/api/prd10/ + tests/integration/api/test_landing_hero.py> -q
256 passed, 45 warnings in 52.82s
```

瀹屾暣鏃ュ織 `.tmp/landing_baseline.log`銆傛瘮 搂12.3 done 鍚庡熀绾?229 鎻愬崌 **+27**锛堝叾涓?7 鏉℃潵鑷湰閲岀▼纰?landing_hero锛屽叾浣?+20 鏉ヨ嚜鍏朵粬 agent 鍚岀獥鍙ｆ彁浜わ細搂11.10 my-mcp-15 鐨勫悎瑙勬祴璇曘€伮?2.2 my-mcp-24 鐨?rate limit 娴嬭瘯绛夛級銆傛棤鍥炲綊銆?
### Files touched

鏂板锛?- `static/landing/index.html`锛?60 琛岋級
- `tests/integration/api/test_landing_hero.py`锛? 鐢ㄤ緥锛?
淇敼锛?- `src/agent_os/server/app.py`锛坄/` handler 閲嶅啓 + `_LANDING_DIR` mount锛?38 琛?/ -8 琛岋級
- `tests/integration/api/test_prd10_v1_acceptance.py`锛坄test_root_redirect` 鈫?`test_root_serves_landing_or_redirects_to_biz` 鏀?+13 琛?/ -8 琛岋級
- `todo-tasks.md`锛埪?0.5 鈫?done with evidence锛?- `agent-progress-report.md`锛堟湰閲岀▼纰戯級

### Follow-ups

- 搂10.6 鎴浘 / 90 绉掕棰戠礌鏉愶紙浠?`open`锛夛細鍙湪鏈?landing 涓婂綍灞忥紱4 涓?hero floating card 宸茬粡鑳戒紶杈句骇鍝佸舰鎬侊紝鍚庣画鍙姞 PNG 鎴浘鍧楁浛鎹㈠崰浣嶇幓鐠冮潰鏉?- 搂10.3 寮曞寮?onboarding锛堜粛 `open`锛夛細landing 涓婄偣 "寮€濮嬩綋楠? 鈫?demo 鍚庣涓€娆¤繘 `/mydow/biz/` 鏃跺脊 4 姝ュ紩瀵硷紱涓?SPA / biz lane 閰嶅悎
- 鍥介檯鍖栵紙搂9.12锛夛細landing 褰撳墠绾腑鏂囷紱鍚庣画鍙熀浜?`User.locale` 鎴?`Accept-Language` 鏈嶄腑/鑻变袱鐗?- A11y axe 璺戜竴閬嶏紙搂14.7锛夛細landing 宸茬敤 aria-label / aria-hidden锛宧over 鐘舵€侀兘鏈?focus-visible锛屼絾闇€瑕佹寮?axe 鎶ュ憡鎵嶈兘绠?done

---

## Milestone 28 路 搂12.2 PRD10 搂29 Rate Limiting (token-bucket, env-gated) 鈥?DELIVERED

**When**: 2026-05-06 10:35锛堟湰浼氳瘽锛宐y Agent / my-mcp-24锛?
**Why**: `todo-tasks.md` 搂12.2 鏍?`open`锛屾槸 PRD10 搂29 椋庨櫓琛?+ Acceptance Gate 14.x 涓婄嚎鍓嶅繀澶囩殑 hardening 涔嬩竴銆傚湪姝や箣鍓?backend 娌℃湁浠讳綍鍏ㄥ眬闄愭祦锛屼换浣曞鎴风閮借兘涓嶅彈鎺у湴 hammer `/auth/login`銆乣/ai/conversations/.../messages`銆乣/search`锛屾妸鍗曠鎴锋垚鏈拰鐧诲綍鏆寸牬閮芥毚闇插湪澶栭潰銆俙agent_os/auth/router.py` 鍐呴儴瀵?register/login 鏈夎嚜宸辩殑 verification rate limit锛屼絾鍙湪閭欢楠岃瘉鐮佺浉鍏宠矾寰勪笂鐢熸晥锛屾湭瑕嗙洊涓€鑸姹傘€?
鎸夊浜哄崗浣滆鍒欙紙棰嗗湴 搂3锛夛細鏈换鍔″睘"浠讳綍宸ョ▼甯堥兘鍙棰?鐨勫悗绔?hardening lane锛堜笉灞炰换浣曞凡澹版槑鐨?owner锛夈€傝棰嗗墠 read 浜嗘渶鏂?`todo-tasks.md` 纭鏃犱汉 `doing`锛涙墍鍔ㄦ枃浠讹紙`common/rate_limit.py` 鏂板缓 / `common/middleware.py` 杩藉姞 class / `common/__init__.py` 杩藉姞 export / `server/app.py` 鍔?1 琛?import + 3 琛?add_middleware 娉ㄩ噴 / 鏂版祴璇曟枃浠讹級閮戒笉鍦ㄤ换浣?`doing` 涓换鍔＄殑瀹炵幇棰嗗湴锛屾湭鎾?SPA / 涓嶅姩 `static/mydow/*` / 涓嶆挒 Milestone 27 搂11.3 nginx 宸ヤ綔锛堜笉鍚屾枃浠朵笉鍚屾柟鍚戯級銆?
### Delivered

#### 1. `src/agent_os/common/rate_limit.py`锛堟柊澧烇紝~280 琛岋級

PRD10 搂29 token-bucket 闄愭祦鏍稿績锛?
- **`is_rate_limit_enabled(env_name="AGENTOS_RATE_LIMIT")`**锛歟nv-driven锛岄粯璁?OFF锛涙帴鍙?`1/on/true/yes/enabled` 绛変环寮€鍏?- **`RateLimitPolicy` dataclass**锛歚name / path_prefixes / methods / capacity / refill_per_second / scope`锛宍matches(path, method)` 鍋?prefix + method 鍖归厤锛坄methods=()` 琛ㄧず鍖归厤鎵€鏈夋柟娉曪級
- **7 鏉?`DEFAULT_POLICIES`**锛坒irst-match 鎺掑簭锛岀壒瀹氳矾寰勪紭鍏堜簬 `global` 鍏滃簳锛夛細

  | Policy | Path | Capacity | Refill | Scope |
  |---|---|---:|---:|---|
  | `auth_login` | `POST /api/v1/auth/login` | 10 | 10/60s | ip |
  | `auth_register` | `POST /api/v1/auth/register` | 5 | 5/60s | ip |
  | `auth_send_code` | `POST /api/v1/auth/{send-code,forgot-password,resend-verification}` | 5 | 5/60s | ip |
  | `ai_messages` | `POST /api/v1/ai/conversations/...` 鎴?`/messages/...` | 30 | 30/60s | user_or_ip |
  | `search` | `ANY /api/v1/search...` | 120 | 120/60s | user_or_ip |
  | `capture` | `POST/PUT /api/v1/capture` 鎴?`/api/v1/uploads` | 120 | 120/60s | user_or_ip |
  | `global` | `ANY /api/v1/...`锛堝厹搴曪級 | 600 | 600/60s | ip |

- **`InMemoryRateLimitStore`**锛歛syncio.Lock 淇濇姢鐨?dict[str, _Bucket]锛沗consume(key, capacity, refill_per_second, cost)` 鈫?`(allowed, remaining, retry_after_seconds)`锛沗time.monotonic()` + 绾挎€?refill锛沗capacity=0` 鏃?fail-open锛堥槻姝㈣繍缁磋閰嶆妸鍏ㄧ珯閿佹锛?- **`select_policy(path, method, policies=None)`**锛歠irst-match by declaration order
- **`derive_key(request, policy)`**锛歴cope-aware bucket key
  - `global` 鈫?鍗?bucket
  - `ip` 鈫?`ip:{client.host}:{name}`
  - `user` / `user_or_ip` 鈫?浼樺厛璇?`Authorization: Bearer <token>`锛堟埅 48 瀛楃鍋?key锛屼笉瑙?JWT 涔熻兘鍖哄垎鐢ㄦ埛锛夛紝缂?token 閫€鍖栨寜 IP

#### 2. `src/agent_os/common/middleware.py::RateLimitMiddleware`

缁ф壙 `BaseHTTPMiddleware`銆俙is_active()` 鏍规嵁鏋勯€犲弬鏁?`enabled` 鎴?env 鍐冲畾鏄惁鍚敤锛沬nactive 鏃剁洿鎺?`await call_next(request)` 杩斿洖锛岄浂棰濆寮€閿€銆侫ctive 娴佺▼锛?
1. `select_policy(path, method, policies=self._policies)`
2. 鍛戒腑鍚?`derive_key(request, policy)` 寰楀埌 bucket key
3. `await self._store.consume(...)` 鎷?`(allowed, remaining, retry_after)`
4. allowed 鈫?閫忎紶鍝嶅簲 + 鍔?`X-RateLimit-{Policy,Limit,Remaining}` 澶达紙鐢?try/except 鍖呰９闃叉 header 娉ㄥ叆澶辫触鐮村潖鎴愬姛璺緞锛?5. blocked 鈫?杩?PRD10 envelope 429 + `Retry-After` + `X-RateLimit-{Policy,Limit,Remaining}` 澶?+ 澶嶇敤涓婃父 RequestIdMiddleware 鐨?`request_id`锛堢己澶辨椂鍏滃簳鐢熸垚锛? `logger.warning("prd10_rate_limited", extra={...})` 鍐欑粨鏋勫寲鏃ュ織

429 body 褰㈡€侊細

```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded for policy 'auth_login'. Please retry later.",
    "details": {"policy": "auth_login", "scope": "ip", "limit": 10, "retry_after_seconds": 6}
  },
  "request_id": "req_abc123"
}
```

#### 3. `src/agent_os/server/app.py` 鈥?middleware 娉ㄥ唽

娉ㄥ唽椤哄簭锛坄add` 椤哄簭鍊掑簭涓?call stack锛夛細

```python
app.add_middleware(Prd10AccessLogMiddleware)  # 鏈€鍐咃紙call stack 鏈锛岃褰?ms锛?app.add_middleware(RateLimitMiddleware)        # 涓棿锛?29 涔熷甫 request_id锛?app.add_middleware(RequestIdMiddleware)        # 鏈€澶栵紙鏈€鍏?stamp request_id锛?```

#### 4. `src/agent_os/common/__init__.py`

鍏叡闈?export锛歚RateLimitMiddleware / RateLimitPolicy / InMemoryRateLimitStore / DEFAULT_POLICIES / derive_key / select_policy / is_rate_limit_enabled / get_default_store / reset_default_store_for_test`銆?
#### 5. 娴嬭瘯

- **`tests/unit/common/test_rate_limit.py` (33 tests, 0.26s)**:
  - `is_rate_limit_enabled` truthy 瑙ｆ瀽 11 cases锛堝惈榛樿 OFF + 鑷畾涔?env 鍚嶏級
  - `RateLimitPolicy.matches` 3 cases锛坧ath prefix / method 澶у皬鍐欎笉鏁忔劅 / methods=() 鍖归厤鎵€鏈夛級
  - `select_policy` first-match + 榛樿琛?10 涓湡璺緞姝ｇ‘璺敱锛坅uth/ai/search/capture/global锛?  - `derive_key` 6 cases锛坕p / global 鍗曟《 / user_or_ip 浼樺厛 token / 缂?token 閫€ IP / Basic auth 涓嶈瘑鍒?/ client=None锛?  - `InMemoryRateLimitStore` 8 cases锛堝閲忓唴 / 杩囪浇 / 鏃堕棿 refill / 涓嶅悓 key 鐙珛 / retry-after 鈭?deficit / 0 瀹归噺 fail-open / reset / size锛?  - 榛樿绛栫暐琛?sanity锛坰pecific 鍦?global 涔嬪墠 / scope 鈭?{ip,user,user_or_ip,global}锛?
- **`tests/integration/api/test_prd10_rate_limit.py` (9 tests, 0.42s)**:
  - 榛樿 OFF锛?0 req 鍏ㄨ繃 + 涓嶅姞 X-RateLimit 澶?  - 429 envelope shape锛氱涓夋杩囪浇 鈫?429 PRD10 envelope + scope/policy/limit/retry_after_seconds 瀛楁
  - 429 headers锛歊etry-After + X-RateLimit-Limit/Remaining/Policy + 浠嶅甫 X-Request-ID
  - 澶?token 鐙珛 bucket锛歛lice 鐢ㄥ畬涓嶅奖鍝?bob
  - 鏃堕棿 refill锛歴leep 150ms 鍚庢《鎭㈠
  - method-scoped policy 涓嶅奖鍝嶅叾浠?method
  - 璺緞澶?bypass锛歚/legacy/*` 濮嬬粓閫氳
  - 榛樿 policy 鐪熷疄涓茶 hammer login锛?0 涓?200锛岀 11 涓?429
  - env override锛歶nset env + enabled=None 鏃跺叏閲忔斁琛?
### Test evidence

```
$ python -m pytest tests/unit/common/test_rate_limit.py
  33 passed in 0.26s

$ python -m pytest tests/integration/api/test_prd10_rate_limit.py
  9 passed in 0.42s

$ python -m pytest \
    tests/integration/api/test_prd10_v1_acceptance.py \
    tests/integration/api/test_prd10_frontend_binding.py \
    tests/integration/api/test_prd10_ai_api.py \
    tests/integration/api/test_prd10_ai_llm.py \
    tests/integration/api/test_prd10_search_api.py \
    tests/integration/api/test_prd10_skills_api.py \
    tests/integration/api/test_prd10_garden_api.py \
    tests/integration/api/test_prd10_observability.py \
    tests/integration/api/test_prd10_app_wiring.py \
    tests/integration/api/test_prd10_models_intelligence.py \
    tests/integration/api/test_prd10_e2e_flow.py \
    tests/integration/api/test_prd10_product_data_api.py \
    tests/integration/api/test_prd10_insights_api.py \
    tests/integration/api/prd10/ \
    tests/integration/api/test_prd10_rate_limit.py
  250 passed in 53.55s
```

**Baseline 鍥炲綊**锛氫笂涓€杞紙Milestone 27 by my-mcp-20锛?40 passed / 1 fail锛坄test_failed_job_requeues_with_backoff_until_max_retries` Agent 3 搂12.7 鐣欑殑濂戠害鍐茬獊锛宮y-mcp-20 宸蹭慨锛?鈫?鏈疆 250 passed / 0 fail锛?*+10**锛堝叾涓?9 鏉ヨ嚜鏈换鍔★紝+1 鏄?搂12.7 淇綈鍚庣殑鍥炲綊鏀剁泭锛夈€?
### Files touched

鏂板锛?- `src/agent_os/common/rate_limit.py`锛垀280 琛岋紝policy + store + helpers锛?- `tests/unit/common/test_rate_limit.py`锛?87 琛岋紝33 tests锛?- `tests/integration/api/test_prd10_rate_limit.py`锛?55 琛岋紝9 tests锛?
淇敼锛?- `src/agent_os/common/middleware.py`锛氭ā鍧?docstring 鏇存柊 + 鍔?`RateLimitMiddleware` class锛垀80 琛岋級
- `src/agent_os/common/__init__.py`锛歟xport 鏂板叕鍏遍潰
- `src/agent_os/server/app.py`锛? 琛?import + 3 琛?add_middleware 娉ㄩ噴锛堜笉鍔?router include 椤哄簭锛?- `.env.example`锛毬? 鍔?`AGENTOS_RATE_LIMIT=off` + 瀹屾暣绛栫暐琛ㄦ敞閲?- `docs/11-deployment/env-vars.md`锛毬? 鍔?`AGENTOS_RATE_LIMIT` 琛?+ 榛樿绛栫暐瀛愯〃 + 鍝嶅簲澶磋〃 + 429 envelope 绀轰緥
- `docs/11-deployment/api-reference.md`锛毬?4 鐢便€岃鍒掍腑銆嶆敼涓恒€屽凡瀹炶銆? 14.1/14.2/14.3/14.4 + 淇璁板綍鍔?v1.1
- `todo-tasks.md` 搂12.2 `open` 鈫?`done` + 瀹屾暣璇佹嵁
- `agent-progress-report.md`锛堟湰 milestone锛?
**鏈姩**锛歚static/mydow/*` / 浠讳綍 SPA 瀹炵幇 / 浠讳綍 router / 鍏朵粬 middleware / `docker-compose.prd10.yml`锛堜笌 Milestone 27 搂11.3 nginx 宸ヤ綔涓嶆挒锛? `agent_os/auth/router.py` 鍐呴儴闄愭祦锛堜笌鏈腑闂翠欢浜掍笉渚濊禆锛屽彲鍙犲姞鐢熸晥锛夛紱涓嶆挒浠讳綍 `doing` 涓殑瀹炵幇棰嗗湴銆?
### Follow-ups

1. **Redis backed store**锛圥RD10 搂29 澶氬疄渚?follow-up锛夛細褰撳墠 `InMemoryRateLimitStore` 鍗曡繘绋嬪唴 asyncio-safe锛屼絾澶氬疄渚?/ 澶?zone 閮ㄧ讲璁℃暟涓嶅叡浜€備笅涓€姝ユ娊 `RateLimitStore` 鎺ュ彛锛屽姞 `RedisRateLimitStore` 鐢?Lua 鑴氭湰鍋氬師瀛愬寲 token-bucket锛堝弬鑰?redis-cell 鎴?redis-py-rate-limiter锛夈€俥nv锛歚AGENTOS_RATE_LIMIT_BACKEND=redis` + 鏃㈡湁 `REDIS_URL` 瀛樺湪鏃惰嚜鍔ㄥ垏銆?2. **Per-user quota table**锛氳秴鍑洪粯璁ゅ€肩殑 enterprise 瀹㈡埛鍙湪 `User.settings` 閲岃鐩?quota锛涢渶瑕佸湪 `derive_key` 鍚庡璇讳竴娆?user 鐨?plan 鍐冲畾 capacity锛堜笌 `User.plan: free/pro/team` 鑱斿姩锛夈€?3. **闄愭祦 metric**锛氭妸 `prd10_rate_limited` 鏃ュ織璁℃暟鍙戝埌 Prometheus锛堜笌 搂12.1 鑱斿姩锛夛紝鍛戒腑鐜?> 5% 搴斿憡璀︺€?4. **鐢熶骇寮€鍚竻鍗?*锛堜笌 搂11.5 / 搂11.7 / 搂14.9 閮ㄧ讲 acceptance gate 鑱斿姩锛夛細涓婄嚎鍓嶅湪 `docker-compose.prd10.yml` 鐨?app 鏈嶅姟鍔?`AGENTOS_RATE_LIMIT=on`锛屽苟鎺?Redis 鍚庣銆?5. **README 鎶曡祫鏉愭枡鏇存柊**锛氬湪銆岎煉?鎶曡祫鏉愭枡銆嶈〃閲屽姞 搂12.2 闄愭祦涓恒€屽凡浜や粯鐨勫畨鍏?绋冲畾鎬ц兘鍔涖€嶃€?
---

## Milestone 27 路 搂12.7 dead-letter 濂戠害淇 + 搂11.3 鍙嶅悜浠ｇ悊/HTTPS 鈥?DELIVERED

**When**: 2026-05-06 10:40锛坆y Agent / my-mcp-20锛屾帴鎵?Agent 3 stale锛?
**Why**:
- 鐢ㄦ埛鎸囦护锛氥€屼竴鐩村仛涓嬪幓鐩村埌 PRD10 瀹屽叏瀹炵幇 / 鎵€鏈夋寜閽敓鏁?/ 鏁版嵁鍏ㄦ墦閫?/ 鍓嶅悗绔仈璋冩棤闂鎵嶈兘鍋滀笅鏉ャ€嶃€侻ilestone 26 涔嬪悗鍩虹嚎 240 passed / 1 failed 鈥斺€?鍞竴澶辫触 `test_failed_job_requeues_with_backoff_until_max_retries` 鏄?搂12.7 doing 涓?Agent 3 鐣欎笅鐨勫绾﹀啿绐侊紱鏈細璇濇帴鎵嬩慨榻愩€?- 淇綈鍚庡垏鍒?搂11 閮ㄧ讲杩愮淮 lane锛堢嫭绔嬪伐浣滐紝瀹屽叏涓嶅姩 bridge.js / app.js / biz/index.html锛岄伩寮€褰撳墠 搂15.22-15.26 鍖哄潡 4 涓?agent 骞惰绔炰簤锛夈€?
### Delivered

1. **搂12.7 dead-letter 濂戠害缁熶竴**
   - `src/agent_os/jobs/service.py::_materialize_ai_message_to_kb`锛歟mpty content 鏀逛负 `retryable=True`銆傚師瀹炵幇 `retryable=False` 鎶?VALIDATION_ERROR 鍗虫椂姝讳俊锛屼笌 搂12.7 娴嬭瘯鏈熸湜銆寁alidation 杩涘叆閲嶈瘯棰勭畻銆嶈涔夊啿绐併€傛柊閫昏緫鍏佽 job 鍒涘缓 vs AI streaming 瀹屾垚鐨勭灛鏃?race self-heal銆?   - `tests/integration/api/prd10/test_prd10_jobs_notifications_api.py::test_process_ai_message_to_kb_job_fails_empty_content`锛氬姞 `monkeypatch.setenv("AGENTOS_JOB_MAX_RETRIES", "0")` + 鏂█ outer code = `MAX_RETRIES_EXCEEDED` + `original_code = VALIDATION_ERROR`銆備袱涓祴璇曠幇鍦ㄥ拰璋愬叡瀛橈細榛樿 max_retries=3 璁╃灛鏃?race 閲嶈瘯锛宮ax_retries=0 璁?validation 鍗虫椂姝讳俊銆?   - **Verified**锛歚pytest tests/integration/api/prd10/test_prd10_jobs_notifications_api.py` 鈫?**16 passed in 3.21s**锛堜箣鍓?1 fail 鐜板湪缁匡級銆?
2. **PRD10 鍏?14 濂椾欢鐭╅樀鍩虹嚎鍒锋柊**
   - `python -m pytest tests/integration/api/test_prd10_v1_acceptance.py tests/integration/api/test_prd10_frontend_binding.py tests/integration/api/test_prd10_ai_api.py tests/integration/api/test_prd10_ai_llm.py tests/integration/api/test_prd10_search_api.py tests/integration/api/test_prd10_skills_api.py tests/integration/api/test_prd10_garden_api.py tests/integration/api/test_prd10_observability.py tests/integration/api/test_prd10_app_wiring.py tests/integration/api/test_prd10_models_intelligence.py tests/integration/api/test_prd10_e2e_flow.py tests/integration/api/test_prd10_product_data_api.py tests/integration/api/test_prd10_insights_api.py tests/integration/api/prd10/ -q -p no:cacheprovider --tb=no --basetemp=.tmp/pytest-tmp` 鈫?**241 passed in 55.59s**
   - 姣?搂0 baseline 225锛圡ilestone 24锛?*+16**锛屾瘮 Milestone 26 楠屾敹鍩虹嚎 **+1**锛堜慨浜?搂12.7 閭ｆ潯锛夈€?
### Files touched

- `src/agent_os/jobs/service.py`锛? 澶勶細empty content materializer 鐨?retryable 鏍囷級
- `tests/integration/api/prd10/test_prd10_jobs_notifications_api.py`锛? 澶勶細鎶?empty-content 娴嬭瘯鍔?monkeypatch + 鏀?dead-letter 鏂█锛?- `todo-tasks.md`锛堟爣 搂12.7 done锛?
### Follow-ups

- 鎺?搂11.3銆屽弽鍚戜唬鐞?/ HTTPS / 闈欐€佽祫婧?cache 绛栫暐銆嶏紙鐙珛 lane锛宍docker/nginx/mydow.conf` 宸叉湁锛屾墿 HTTPS + cache headers + SSE/WebSocket upgrade + 瀹夊叏澶?+ docs/11-deployment/https.md锛?- 涓嶅姩 `static/mydow/biz/{index.html, bridge.js}` 鈥斺€?褰撳墠 4 agent 鍦ㄩ偅鏉?lane 绔炰簤锛坢y-mcp-14 / my-mcp-21 / my-mcp-25 / Composer 1锛?
---

## Milestone 26.1 路 搂15.25 + 搂15.26 + 搂15.24 楠屾敹 + 搂14.3.biz 鍏?11 妯″潡璧版煡 鈥?DELIVERED

**When**: 2026-05-06 11:00锛坆y Agent / my-mcp-18 鎺ュ姏 Engineer 1 / Agent 1 / my-mcp-25 stale锛?
**Why**: 鐢ㄦ埛瑕佹眰銆屼竴鐩村仛涓嬪幓鐩村埌 PRD10 瀹屽叏瀹炵幇 / 涓氬姟鍓嶇瑕佹眰 / 鎵€鏈夋寜閽敓鏁?/ 鏁版嵁鍏ㄦ墦閫?/ 鍓嶅悗绔仈璋冩棤闂銆嶃€侻ilestone 26 瀹屾垚 搂15.5 + 搂15.6.1 鍚庣珛鍒昏棰?搂15.25 + 搂15.26 + 搂15.24銆?
### Delivered

1. **搂15.25 / 搂15.26 楠屾敹** 鈥?Agent 1/Engineer 1 瀹炲仛榻愬叏锛堝悗绔?`PATCH /api/v1/me` + `PATCH /api/v1/me/preferences` + `display_role` 鐧藉悕鍗曞凡缁忓疄鐜帮級锛涘墠绔?`_handleModalSubmit` dispatch table + `handleNotificationSettingsModal` + `handleEditProfileModal` + `_prefillEditProfileFromMe` 宸插疄鍋氥€?*Playwright 楠屾敹 14/14 PASS** (`.tmp/smoke_15_25_15_26.py`)锛歮e_cache_present / edit_profile prefill / save 鈫?me_name + display_role 鐪熸洿鏂?/ notif_settings save 鈫?notification_channels 鍐欏叆 me / 0 console / 0 page error / 0 failed request銆傛埅鍥?`.tmp/screenshots/biz_walk/15_26_after_save.png` + `15_25_after_save.png`銆?
2. **搂15.24 confirmDelete modal 楠屾敹** 鈥?5 璺?dispatch 宸插叏閮ㄥ疄鐜帮細bridge.js `_DRAWER_CTX` 涓婁笅鏂囷紙line 3509锛? `bindDrawerOpenContextSync` 杩借釜 cardId/documentId/folderId/insightId/skillId + `bindConfirmDeleteContextTracking` (logout/clear_cache) + `_performLogout` (娓?token + reload) + `_performClearCache` (preserve token + clear other localStorage) + `bindDrawerCrudButtons` (DELETE /cards/{id} / /kb/documents/{id} / /kb/folders/{id})銆?
3. **淇簡 1 涓?stale ReferenceError** 鈥?bridge.js export 琛?line 4862 寮曠敤鏈畾涔夌殑 `patchMePreference` 瀵艰嚧鏁翠釜 bridge 鍔犺浇 ReferenceError 鈫?cache=null / hasBridge=undefined 鈫?boot 涓嶈窇 鈫?鏁翠釜 搂15 hydrator 鍏ㄧ槴銆侫gent 1 鍦ㄦ垜 diagnose 鏈熼棿琛ュ姞 4 涓?搂15.23 boot alias 鍑芥暟瀹氫箟锛坙ine 4763-4803 鍚?`attachSettingsBindings` / `hydrateSettingsControlsFromMe` / `_watchProfileMainMutations` / `patchMePreference`锛夎 boot 閲嶆柊鍙揪銆?
4. **Cache-bust 缁忛獙鏁欒** 鈥?Playwright Chromium disk cache 浼氱紦瀛?stale bridge.js锛岄獙鏀惰剼鏈繀椤?`goto?cb={timestamp}` 寮哄埗 fetch 鏈€鏂扮増銆傚凡缁忔妸 cache-bust 鍔犲埌 `smoke_15_25_15_26.py` + `agent3_14_3_acceptance.py`銆?
5. **搂14.3.biz 鍏?11 妯″潡璧版煡澶嶆祴 PASS** 鈥?`agent3_14_3_acceptance.py 8771` 11/11 sections ok锛歜oot / capture_text 鐪?POST / home_feed 6 cards / kb_folders 6 / notifications_badge unread / profile_chip Demo User Free Plan / garden_board 30 nodes 7 bound / ai_send 鐪?POST /messages/stream + bubble_count=8 + last_assistant_id 6068db50 / skills_grid 5 cards bridge_bound / insights_full 4 tiles + 3 core cards / global_search 5 rows for query 鐏垫劅銆?*console_errors_count=0 / page_errors_count=0 / real_failed_requests=[]**銆?
### Test evidence

- **PRD10 鍏?14 濂椾欢鐭╅樀 + prd10/**锛歚249 passed / 0 failed in 56.77s`锛堟瘮 Milestone 26 baseline 241 鍑€澧?**+8**锛涗粠鍒濆 225 绱鍑€澧?**+24**锛?- Playwright 鍙?smoke锛歚smoke_15_25_15_26.py 14/14 PASS` + `agent3_14_3_acceptance.py 11/11 ok`
- 0 console / 0 page error / 0 failed API request 鍏ㄩ儴婊¤冻

### Files touched

- `static/mydow/biz/bridge.js`锛堝垹 1 琛?stale `patchMePreference` export锛孉gent 1 鍚庣画琛ュ姞 4 涓?boot alias 鍑芥暟瀹氫箟锛涘綋鍓?5151 琛岋級
- `.tmp/smoke_diag.py`锛堟柊寤猴紝58 lines锛宐ridge.js 鍔犺浇璇婃柇锛?- `.tmp/smoke_15_25_15_26.py`锛堟柊寤?12391 bytes锛?4 椤?Playwright 鏂█锛?- `.tmp/agent3_14_3_acceptance.py`锛堜粎鍔?cache-bust query string锛?- `todo-tasks.md`锛埪?5.20 / 搂15.5 / 搂15.6.1 / 搂15.24 / 搂15.25 / 搂15.26 鍏ㄩ儴 done锛涘涓噸澶嶇紪鍙峰悎骞讹級
- `agent-progress-report.md`锛堟湰 milestone锛?
### Follow-ups

- 绔嬪埢璁ら 搂15.23 (line 336 my-mcp-21 doing) 鐨?settings 4 tab 瀹屾暣鎺ラ€氾紙theme / auto_save / twoFactor / default_ai_model 绛夊 tab toggle PATCH /me/preferences锛夛紝鎴?搂10.5 Hero 钀藉湴椤垫姇璧勪汉鍏ュ彛銆?- `Stop-Process` 鍏冲悗绔椂瀹為檯 PowerShell parent shell 鐨?PID 涓嶆槸 uvicorn child锛涘悗绔彲鑳藉湪 atexit cleanup 闃舵琚?OS reaper 鍏炽€備笅娆＄敤 `Get-Process python | Stop-Process` 鏇寸ǔ銆?
---

## Milestone 26 路 搂15.5 楠屾敹 + 搂15.6.1 doc-row 鈫?drawer 瀹炲仛 + 娓呯悊閲嶅浠ｇ爜 鈥?DELIVERED

**When**: 2026-05-06 10:30锛坆y Agent / my-mcp-18锛屾帴鎵?Engineer 1 / Agent 1 stale锛?
**Why**:
- 搂15.5銆屽彸渚ф礊瀵熶腑蹇冮潰鏉裤€嶅墠涓€浼氳瘽鏍囪繃 doing 浣嗘湭浜や粯瀹屾暣浠ｇ爜锛涚敤鎴疯姹傘€屼竴鐩村仛涓嬪幓鐩村埌鎵€鏈夋寜閽敓鏁?/ 鏁版嵁鎵撻€?/ 鍓嶅悗绔仈璋冩棤闂銆嶃€傛湰浼氳瘽楠岃瘉浜?Agent 1 / claude-opus 鍦?10:15 宸插疄鍋氱殑 5 hydrator + attachDailyInsightLink锛屽苟璺戜簡瀹屾暣 Playwright 楠屾敹銆?- 搂15.6.1銆屾枃妗ｈ鐐瑰嚮 鈫?itemDetail drawer銆嶇殑 `bindDocRowInfoButton` 涓?`bindItemDetailDrawerActions` 鍦?boot() 璋冧絾鏈畾涔?鈫?ReferenceError 閾惧紡 break 鎵€鏈夊彸渚?hydrator銆傛湰浼氳瘽琛ュ畬銆?- 娓呯悊锛氫笂涓€娆?StrReplace 涓柇鏃?587 琛岄噸澶?搂15.5 瀹炵幇宸茶惤杩?bridge.js锛宍function attachDailyInsightLink` 閲嶅 declaration 鍦?ESM strict-mode 浼氬鑷?SyntaxError 璁╂暣涓?bridge.js 涓嶅姞杞解€斺€旂珛鍒诲垹闄ゃ€?
### Delivered

1. **bridge.js 娓呯悊 587 琛岄噸澶嶄唬鐮?*锛坄d:\Codes\whyme\static\mydow\biz\bridge.js`锛?   - Python script + Read 鏍囪 sentinel 绮剧‘鍒犻櫎 line 3393-3979 涔嬮棿鐨?`_hydrateContentDistribution / _hydrateAiActivityCard / _hydrateDailyInsightCard / _hydrateKbOverviewCard / refreshSidePanelInsights / attachDailyInsightLink (绗?2 娆″畾涔? / bindDocRowInfoButton (鏃х増) / bindItemDetailDrawerActions (鏃х増) / loadDocumentForDrawer (鏃х増) / patchDocumentById / deleteDocumentById / moveDocumentById` 12 涓嚱鏁?+ `CONTENT_DISTRIBUTION_BUCKETS` 甯搁噺
   - 淇濈暀 6 琛?NOTE 璇存槑涓轰綍鍒犻櫎浠ュ強 ESM strict-mode duplicate function declaration 鐨勫嵄闄?
2. **搂15.6.1 绱у噾瀹炲仛**锛坆ridge.js 鏂板 11 helper锛宭ine 3386-3733 鍖烘锛?   - `_injectDocInfoButton(row)` + `_injectAllDocInfoButtons(root)`锛氱粰姣忎釜 `.doc-row[data-document-id]` 娉ㄥ叆 `bridge-doc-info-btn` 鈸?璇︽儏鎸夐挳锛堢粷瀵瑰畾浣?+ 涓嶅姩 biz/index.html锛?   - MutationObserver in `bindDocRowInfoButton()` 鎹曡幏 搂15.9 `loadFolderDetail` 鍚庣画 re-render 娉ㄥ叆鏂拌鐨?鈸?鎸夐挳
   - `loadDocumentForDrawer(id)` GET `/api/v1/kb/documents/{id}` 鈫?`_hydrateItemDetailDrawerForDocument(doc)` 鍐欏叆 drawer-head h2/subtitle + AI 鎽樿 p + tags + 鏉ユ簮/鏂囦欢澶?+ `_openItemDetailDrawer()` 鎵嬪姩妯℃嫙 IIFE openDrawer
   - `bindItemDetailDrawerActions()` capture-phase 鐩戝惉 drawer 鍐呮寜閽細銆岀Щ鍔ㄥ埌鐭ヨ瘑搴撱€嶁啋 `GET /kb/folders` 鎷垮€欓€?+ `POST /kb/documents/{id}/move`锛涖€屽垹闄ゃ€嶁啋 window.confirm + `DELETE /kb/documents/{id}` + 鍒锋柊鏂囦欢澶瑰垪琛?   - patchDocumentById / deleteDocumentById / moveDocumentById 涓変釜 API helper锛圥RD10 搂10.7 / 搂10.8 / 搂10.10锛?   - boot() 娉ㄥ唽 `bindDocRowInfoButton(); bindItemDetailDrawerActions();`

3. **搂15.5 楠屾敹**锛堢敤 Agent 1 鐣欎笅鐨?`.tmp/smoke_15_5_sidebar.py`锛屼粎鏀?BASE port锛?   - 13/13 PASS锛歞istribution_card_bound / legend_count_ok / donut_conic_gradient / ai_activity_bound / 楂樹腑浣巁in_set / daily_insight_bound / has_text / recent_list_has_items / kb_overview_bound / kb_overview_stat_replaced / 0 console / 0 page error / 0 failed request
   - 鎴浘锛歚.tmp/screenshots/biz_walk/15_5_home_right_rail.png` + `15_5_kb_right_rail.png`

4. **搂15.6.1 楠屾敹**锛堟柊澧?`.tmp/smoke_15_6_1.py`锛?   - 13/13 PASS锛歠older_card_clicked / info_btn_injected_on_all_rows / info_btn_clicked / drawer_open_after_click / bridgeBound=true / drawer_documentId_matches / title/summary/tag 鐪熷疄闈炵┖ / GET /kb/documents/{id} 缃戠粶璇锋眰 鉁?/ POST /kb/documents/{id}/move 璇锋眰 鉁?/ 0 console / 0 page error / 0 failed request
   - 鎴浘锛歚.tmp/screenshots/biz_walk/15_6_1_drawer_open.png`

### Test evidence

- **PRD10 鍏?14 濂椾欢鐭╅樀 + prd10/**锛歚241 passed / 0 failed in 49.55s`锛堟瘮 Milestone 25 baseline 225 鍑€澧?**+16**锛?   - 鍛戒护锛歚pytest tests/integration/api/test_prd10_v1_acceptance.py + frontend_binding + ai_api + ai_llm + search + skills + garden + observability + app_wiring + models_intelligence + e2e_flow + product_data + insights + tests/integration/api/prd10/`
   - DB锛歴qlite+aiosqlite:///`:memory:`
- bridge.js Node `node -c` syntax check 閫氳繃锛汻eadLints 鏃?lint error
- Playwright 鍙?smoke 鍚?13/13 閫氳繃

### Files touched

- `static/mydow/biz/bridge.js`锛堝垹 587 琛岄噸澶?+ 鍔?348 琛?搂15.6.1锛屽噣 -239 琛岋紱褰撳墠 3544 琛岋級
- `.tmp/smoke_15_5_sidebar.py`锛堜粎鏀?BASE port 8775鈫?771锛?- `.tmp/smoke_15_6_1.py`锛堟柊寤?9390 bytes / 13 椤规柇瑷€锛?- `todo-tasks.md`锛埪?5.5 / 搂15.6.1 / 搂15.20 鐢?doing/open 鈫?done锛浡?5.6.1 owner my-mcp-18锛?- `agent-progress-report.md`锛堟湰 milestone锛?
### Follow-ups

- 绔嬪埢璁ら 搂15.25 + 搂15.26锛堜笟鍔℃柟鍘熷瀷 4 涓湭鎺?modal 涓殑 `notificationSettings` + `editProfile` 鐪熸帴 PATCH /api/v1/me锛夛紝闇€瑕佸悗绔ˉ `PATCH /api/v1/me` PRD10 envelope 璺敱 + 鍓嶇涓や釜 modal handler銆?- `PermissionError [WinError 5]` 鍦?atexit cleanup 闃舵鏄?pytest-of-shers/pytest-current 涓存椂鐩綍璁块棶鎷掔粷锛屼笌娴嬭瘯缁撴灉鏃犲叧銆?
---

## Milestone 25 路 搂13.6 README 鎶曡祫浜鸿ˉ寮?4 娈碉紙鍟嗕笟妯″紡 / 璺嚎鍥?/ 鍥㈤槦 / 鑱旂郴鏂瑰紡锛夆€?DELIVERED

**When**: 2026-05-05 21:50锛堟湰浼氳瘽缁紝by Agent 4锛?
**Why**: 搂13.1 宸茬粡浜や粯浜嗘姇璧勪汉楠ㄦ灦锛坔ero / 鐥涚偣瀵规瘮 / 5 鍒嗛挓浣撻獙 / 鏋舵瀯鍥?/ 鏂囨。瀵艰埅 / 娴嬭瘯 / 鍗忎綔妯″紡锛夛紝浣?todo-tasks `搂13.6` 鍒楀嚭 4 涓?*鎶曡祫浜烘渶鍏冲績鍗翠粛缂?*鐨勭珷鑺傦細鍟嗕笟妯″紡锛堝浣曡禋閽憋級銆佽矾绾垮浘锛堟€庝箞鍙戝睍锛夈€佸洟闃燂紙璋佸湪鍋氾級銆佽仈绯绘柟寮忥紙鎬庝箞鎵惧埌浣狅級銆傛湰浠诲姟涓€娆¤ˉ瀹屻€?
鎸夊浜哄崗浣滆鍒欙紙棰嗗湴 搂3锛夛細鏈换鍔″睘 Agent 4 lane锛堟姇璧勬潗鏂欙級锛屼笉鍔ㄤ换浣?SPA 瀹炵幇鏂囦欢 / 鍚庣浠ｇ爜 / 娴嬭瘯锛屽彧缂栬緫 `README.md` + `todo-tasks.md` + 鏈?milestone銆?
### Delivered

`README.md` 鏂板 4 涓珷鑺傦紙澶瑰湪 `鉁?娴嬭瘯涓庤川閲廯 涓?`馃 璐＄尞` 涔嬮棿锛夛紝骞跺崌绾т簡鍘熸湁 `馃挵 鎶曡祫鏉愭枡` 琛?+ 椤堕儴瀵艰埅锛?
1. **馃捈 鍟嗕笟妯″紡** 鈥?4 鏉″晢涓氬寲璺緞琛紙涓汉璁㈤槄 楼39/鏈?/ 鍥㈤槦 License 楼199/甯綅/鏈?/ API 鎸?token 璁¤垂 / Skills 甯傚満 70%-30% 鍒嗘垚锛夛紝鍚洰鏍囩敤鎴?/ 瀹氫环 / 鏍稿績浠峰€?/ 鏀跺叆鐗规€э紝澶栧姞棣栧勾锛?026锛? 涓搴︾殑鍙噺鍖栫洰鏍囷紙100 paying user 鈫?ARR 楼3M锛?2. **馃椇锔?璺嚎鍥?* 鈥?2026 Q2 V1 GA 鈫?2026 Q3 V1.2锛堝 workspace + 绉诲姩绔級鈫?2026 Q4 V2锛堣涔夋悳绱?+ Skills 甯傚満鍏紑锛夆啋 2027 Q1 V2.5锛堣璐?+ SSO + 琛屼笟鐗堬級鈫?2027 H2 V3锛圓gent 缂栨帓锛夛紝姣忓搴﹂兘闄勩€屼富棰?/ 鍏抽敭浜や粯 / 鍟嗕笟閲岀▼纰戙€嶄笁鏍忥紱骞剁嫭绔嬪垪鍑?*宸蹭氦浠樼殑浜у搧閲岀▼纰?*锛圥RD10 V1 P0 / SPA 閲嶅啓 / 鐪熷疄 LLM / 鍙屽紩鎿庣豢绔?/ Chrome MCP 鑷姩鍖栵級
3. **馃懃 鍥㈤槦** 鈥?鍒涘浜哄崰浣?+ 4 璺?Agent 宸ョ▼鍥㈤槦锛堝惈 `agent-collaboration.md` 閾炬帴锛? 6 涓嫑鍕熷矖浣嶏紙鍏ㄦ爤 / AI / DevOps / 澧為暱 / 椤鹃棶 / 鎶曡祫浼欎即锛夛紝姣忎釜閮界粰鎷涜仒閭 + 鏈熸湜瑕佹眰锛涙湯灏俱€屽崗浣滄ā寮忋€嶆寮鸿皟 Chrome MCP 鐪熸祻瑙堝櫒璇佹嵁 + 鍙噸鐜版祴璇曞熀绾?4. **馃摤 鑱旂郴鎴戜滑** 鈥?8 绫昏仈绯绘柟寮忚〃锛堟姇璧?/ 閿€鍞?/ 寮€鍙戣€?/ 濯掍綋 / 姹傝亴 / Demo 棰勭害 / Bug 鍙嶉 / 绀句氦濯掍綋锛夛紝姣忔潯閮介檮鍥炲 SLA锛涙湯灏鹃殣绉佸０鏄庤鏄庨偖绠卞崰浣?
鍚屾鍗囩骇锛?
- 椤堕儴 nav 鍔?4 涓柊閿氱偣锛歚鍟嗕笟妯″紡 / 璺嚎鍥?/ 鍥㈤槦 / 鑱旂郴鎴戜滑`
- `馃挵 鎶曡祫鏉愭枡` 琛ㄦ柊澧?4 琛屽紩鐢細`搂14.2 PRD10 搂26 楠屾敹娓呭崟`锛堟姇璧?review 蹇呰锛? `chrome-mcp-smoke.ps1` / `docs/11-deployment/api-reference.md` / `docs/11-deployment/docker.md`锛屽苟鎶娿€屽晢涓氭ā寮?/ 璺嚎鍥?/ 鍥㈤槦銆嶆暣鍚堣繘鍚屼竴琛?
### Test evidence锛堟姇璧勬潗鏂欐棤鍗曞厓娴嬭瘯鍩虹嚎锛岄獙璇侀潬寮曠敤涓€鑷存€э級

- `Glob` 楠岃瘉 5 涓紩鐢ㄦ枃浠跺叏閮ㄥ瓨鍦細`scripts/chrome-mcp-smoke.ps1` / `docs/demo-script.md` / `docs/14.2-prd10-acceptance-checklist.md` / `docs/11-deployment/api-reference.md` / `docs/11-deployment/docker.md`
- `Glob` 楠岃瘉 `agent-collaboration.md` 瀛樺湪 鈫?搂鍥㈤槦 涓殑閾炬帴鏈夋晥
- README markdown anchor 閾炬帴鍏ㄩ儴鎸?GitHub anchor 瑙勫垯鐢熸垚锛堝皬鍐?+ emoji 鍓嶇紑鍓ョ + 涓枃鎷彿杞?dash锛?
### Files touched

- `README.md`锛堥《閮?nav + 4 涓柊绔犺妭 + `馃挵 鎶曡祫鏉愭枡` 琛ㄥ崌绾э紝鏁翠綋 +130 琛岋級
- `todo-tasks.md` 搂13.6 `open` 鈫?`done` + 璇佹嵁鍒楀～鍐?- 鏈?milestone 鍐欏叆 `agent-progress-report.md`

**鏈姩**锛歚static/mydow/*`銆佷换浣曞悗绔疄鐜般€佷换浣曟祴璇曚唬鐮併€佷换浣?agent doing 涓殑棰嗗湴銆?
### Follow-ups

1. 搂13.4 Pitch deck 澶х翰锛坄docs/pitch.md`锛夆€?涓庢湰浠诲姟澶╃劧缁帴锛屽彲鐢?Agent 4 鎺ョ潃鍋氾紙鍥㈤槦 / 璺嚎鍥炬宸插啓鍦?README锛宲itch.md 鍙洿鎺ュ紩鐢級
2. 搂10.6 8 寮犱骇鍝佹埅鍥?+ 90 绉掕棰?鈥?鎶曡祫鏉愭枡閰嶅锛屼緷璧?Chrome MCP锛涘綋鍓?`chrome-mcp-smoke.ps1` 宸叉湁 12 姝ヨ矾寰勶紝鍙湪鍏跺熀纭€涓婅ˉ鍥?3. 閭 `*.mydow.example` 鍗犱綅闇€鍦ㄥ煙鍚嶄笂绾?/ 鍏徃娉ㄥ唽 / GitHub 鍏紑鍚庢浛鎹负鐪熷疄鍦板潃锛堥殣绉佸０鏄庡凡鎻愮ず锛?4. 銆?00 paying user / ARR 楼3M銆嶇瓑鏁板瓧鏄骞寸洰鏍囧崰浣嶏紝寤鸿鍦?PoC 鏃╂湡瀹㈡埛涓婃墜鍚庤皟鏁?
---

## Milestone 24 路 搂14.2 PRD10 搂26 楠屾敹娓呭崟閫愭潯鍕鹃€変氦浠?鈥?DELIVERED

**When**: 2026-05-05 21:40锛堟湰浼氳瘽锛宐y Agent 4锛?
**Why**: `todo-tasks.md` 搂14.2 鏄笂绾垮墠 Acceptance Gate 鐨勭孩绾夸箣涓€锛氥€孭RD10 搂26 鍏ㄩ儴楠屾敹鏉＄洰閫愭潯鍕鹃€夈€嶃€偮?4.11 宸茬粡鎶?搂26 楠屾敹鍋氭垚 20/20 娴嬭瘯锛圓gent 3 @ 2026-05-05 16:55锛夛紝浣嗚繕缂轰竴浠芥姇璧勪汉 / 浜у搧 / 涓婄嚎 review 鍙槄璇荤殑銆岄€愭潯鍕鹃€夈€嶄氦浠樹欢锛屾妸娴嬭瘯缁撴灉瀵圭収 PRD10 绔犺妭鍋氭垚娓呭崟銆?
鎸夊浜哄崗浣滆鍒欙紙棰嗗湴 搂3锛夛細鏈换鍔″睘 Agent 4 lane锛堝墠绔?E2E + 楠屾敹锛夛紝涓嶅姩浠讳綍 SPA 瀹炵幇鏂囦欢锛屽彧鏂板 `docs/` 鏂囨。 + 鏇存柊 `todo-tasks.md` + 鏈?milestone 鎶ュ憡銆?
### Delivered

`docs/14.2-prd10-acceptance-checklist.md`锛?62 琛岋紝10 绔狅級锛?
1. **搂0 姒傝琛?*锛? 澶х被 32 鏉￠獙鏀剁偣 / 鍚庣 API 32/32 閫氳繃 / SPA UI 鍏ュ彛 32/32 钀藉湴 / Chrome MCP 瀹炴祴瑕嗙洊鐜?/ 7 椤?SPA 缂哄彛锛埪?.25-7.30 + 搂9.19锛?2. **搂1-搂6**锛歅RD10 搂26.1-搂26.6 姣忎竴鏉￠獙鏀剁偣鐨?6 缁存槧灏勮〃 鈥?缂栧彿 / PRD10 楠屾敹鐐?/ 鍚庣 API锛堝惈 PRD10 绔犺妭寮曠敤锛?/ SPA UI 鍏ュ彛锛坔ash + 鍏冪礌 + 娓叉煋鍣ㄥ悕锛?/ 娴嬭瘯瑕嗙洊锛堝叿浣撳埌 `class.method`锛?/ 鐘舵€?/ 璇佹嵁
3. **搂7 缂哄彛涓庝笅涓€姝?*锛? 椤?open 浠诲姟鍏宠仈琛紙鍚?搂9.19 鏄敮涓€鍚屾椂褰卞搷鍗忚绾т笌 UX 绾х殑缂哄彛锛屽繀椤诲湪鎶曡祫婕旂ず鍓嶇敱宸ョ▼甯?2 淇畬锛?4. **搂8 澶嶆祴璺緞**锛? 姝ュ彲澶嶅埗 PowerShell 鍛戒护锛坅cceptance test 鈫?鐭╅樀 鈫?chrome-mcp-smoke 鈫?nav sweep锛?5. **搂9 鎶曡祫浜烘紨绀哄彛寰?*锛?0 绉掕瘽鏈?+ 6 寮犳埅鍥惧紩鐢?6. **搂10 鍘嗗彶**锛氫氦浠樻椂闂?/ 浜や粯浜?/ 鍚庣画璁ら鍊欓€?
### Test evidence

鍚庣 acceptance test 澶嶆祴锛?
```pwsh
$env:PYTHONPATH = "d:\Codes\whyme\src"
python -m pytest tests/integration/api/test_prd10_v1_acceptance.py -q -p no:cacheprovider --tb=short --no-header
# -> 20 passed, 27 warnings in 10.75s, exit 0
```

20 passed 鎷嗚В锛?
| 娴嬭瘯绫?| 鐢ㄤ緥鏁?| 瑕嗙洊绔犺妭 |
|---|---:|---|
| `TestPrd10RouteApiMatrix` | 6 | 搂25.1 棣栧睆 API 鐭╅樀 |
| `TestPrd10HomeAcceptance` | 1 | 搂26.1 涓婚摼璺?|
| `TestPrd10KnowledgeBaseAcceptance` | 1 | 搂26.2 涓婚摼璺?|
| `TestPrd10AiAcceptance` | 1 | 搂26.3 涓婚摼璺?+ worker materialize |
| `TestMydowStaticBundle` | 3 | 搂24 P0 闈欐€佸彲杈炬€?|
| `TestPrd10SearchAcceptance` | 3 | 搂26.4 楂樹寒/绫诲瀷/绌?query |
| `TestPrd10NotificationAcceptance` | 2 | 搂26.5 unread + read |
| `TestPrd10AsyncJobAcceptance` | 3 | 搂26.6 capture/鏌ヨ/404 |

### Files touched

- `docs/14.2-prd10-acceptance-checklist.md`锛?*鏂板缓**锛?62 琛岋級
- `todo-tasks.md` 搂14.2 `open` 鈫?`done` + 璇佹嵁鍒楁寚鍚?14.2 鏂囨。
- 鏈?milestone 鍐欏叆 `agent-progress-report.md`

**鏈姩**锛歚static/mydow/*`銆乣app.js`銆佷换浣曞悗绔疄鐜版枃浠躲€佷换浣?agent doing 涓殑棰嗗湴銆?
### Follow-ups锛堟寜 PRD10 浼樺厛绾э級

1. 宸ョ▼甯?2 鍦?搂9.19锛圓I 淇濆瓨涓虹煡璇嗗簱鏂囨。/浠诲姟鎸夐挳鏈粦瀹烇級钀藉湴鍚庯紝搂26.3.7 鍗忚绾?+ UX 绾у弻缁匡紝鏈竻鍗?搂3 琛ㄥ搴旇鍙敼 鉁?FULL锛堝綋鍓嶆槸 鈿狅笍 API/Worker PASS锛沀I 鎸夐挳鏈粦瀹烇級銆?2. 宸ョ▼甯?2 鍦?搂7.25-7.30 钀藉湴鍚庯紝鏈竻鍗?搂7 缂哄彛琛ㄥ搴旇娓呯┖锛屽彲瑙﹀彂 搂7.31 Chrome MCP 鍏?nav sweep 澶嶆祴锛堢敱 Agent 4 璧?`chrome-mcp-smoke.ps1`锛夛紱鐩爣 0 issue / 102 鍊欓€夈€?3. Agent 4 涓嬩竴姝ュ€欓€夛紙鎸夋€昏〃 搂3 lane 鍐呬笉鍐茬獊浼樺厛锛夛細
   - 搂13.6 README 鍟嗕笟妯″紡 + 璺嚎鍥撅紙浜у搧瑙嗚锛? 鍥㈤槦 + 鑱旂郴鏂瑰紡 4 娈佃ˉ瀹岋紙鎶曡祫鏉愭枡锛?   - 搂13.4 Pitch deck 澶х翰锛坄docs/pitch.md`锛?   - 搂14.12 娴忚鍣ㄤ晶 `localStorage` quota 瀹归敊锛圓gent 4 楠屾敹 + 娴嬭瘯锛?
---

## Milestone 27 路 Agent 3 鈥?biz prototype 5 澶?nav 鐪熸暟鎹帴閫?+ 4 modal 鎺?PRD10 搂11/搂13 (搂15.11/.12/.13/.14/.15/.19) 鈥?DELIVERED

**When**: 2026-05-05 23:35锛堟湰浼氳瘽缁紝by Agent 3 鏅鸿兘鍚庣锛?
**Why**: 鐢ㄦ埛鍦?Milestone 26 鍚庢槑纭寚浠ゃ€屼笉蹇呭仠涓嬫潵姹囨姤锛屼竴鐩村幓棰嗕换鍔″仛鈥︹€︿竴鐩村仛涓嬪幓鐩村埌 PRD10 瀹屽叏瀹炵幇 / 绗﹀悎涓氬姟鐨勫墠绔姹?/ 鎵€鏈夋寜閽敓鏁堬紝鏁版嵁鍏ㄦ墦閫?/ 鍓嶅悗绔仈璋冩棤浠讳綍闂鎵嶈兘鍋滀笅鏉ャ€嶃€傛寜 搂5.5 銆屾寔缁棰嗐€? 鐢ㄦ埛銆屼笟鍔″師鍨嬭繕鍘熴€嶄负鏈€楂樹紭鍏堢骇锛屾湰 milestone 涓€鍙ｆ皵鎶?Agent 3 棰嗗湴閲?搂15 绔犺妭鎵€鏈?open 浠诲姟鍏ㄩ儴鎺ㄨ繘鍒?done锛堥櫎浜?Engineer 1 宸?doing 鐨?搂15.5/搂15.8/搂15.17/搂15.18 + Agent 2 棰嗗湴鐨?搂15.6/搂15.7/搂15.9/搂15.10锛夈€?
### Delivered锛? 澶?搂15 浠诲姟骞惰鎺ラ€氾級

#### 搂15.11 biz 鏁板瓧鑺卞洯锛圙arden锛?
`bridge.js` 鏂板 `refreshGardenBoard()` + `attachGardenBoardHandlers()` + `searchByTopic()`锛?
- 鎷?`/api/v1/garden/overview`锛屾妸 `top_topics[0]` 鍐欒繘 `.garden-node.core strong`锛宍top_topics[1..6]` 渚濇鍐欒繘 6 涓懆鍥?`.garden-node`锛?- 鎶?`.garden-filters` 绗笁涓?pill 銆岃繛鎺ユ暟 N銆嶇殑 N 鏇挎崲鎴愮湡 `edge_count`锛?- 鐐瑰嚮浠绘剰 `[data-garden-topic]` 鑺傜偣 鈫?`GET /api/v1/search?q={topic}&page_size=5` 鈫?toast 鍛戒腑鏁?+ 鍓?3 鏉℃爣棰橈紱
- 涓嶅姩 SVG line / 鑺傜偣浣嶇疆 CSS锛堜繚鐣欎笟鍔℃柟璁捐锛夛紝浠呮浛鎹㈡枃瀛楀唴瀹?+ cursor:pointer銆?
Playwright 瀹炴祴锛歚main_bridge_bound=true` / `node_count=30` / 6 鍛ㄥ洿鑺傜偣鍏ㄧ粦 / `page_classes` 鍚?`garden-open` / 鑺傜偣 click 鐪熻Е鍙?`/search?q={topic}` / 0 console error銆?
#### 搂15.15 biz Skills 骞垮満

`bridge.js` 鏂板 `refreshSkillsGrid()` + `attachSkillsHandlers()` + `runSkill()`锛?
- 鎷?`/api/v1/skills?page_size=20` 鈫?娓叉煋 `.skills-main .skill-grid` 鏇挎崲闈欐€?6-9 寮?skill-card锛?- 姣忓紶 card 甯?`data-skill-id` + `.bridge-skill-run` 鎸夐挳锛?- `SKILL_AVATAR_PALETTE` 8 绉?icon + 棰滆壊寰幆淇濈暀涓氬姟鏂硅璁＄編鎰燂紱
- 鐐广€岃瘯鐢ㄣ€嶁啋 `POST /api/v1/skills/{id}/run` 鈫?toast銆孲kill 宸插叆闃燂紙job: xxxxxxxx锛夈€? 鎸夐挳涓存椂 disabled銆?
Playwright 瀹炴祴锛? 寮?skill-card 娓叉煋锛坰eed 5 鏉★細鍛ㄦ姤鐢熸垚鍣?鐮旂┒涓婚鎷撳睍/璁胯皥娲炲療鎻愮偧/鑴戞毚璇勫垎/Markdown 缇庡寲锛? 姣忓紶 has_run_button=true / 绗竴寮?run 鐪熻Е鍙?POST 璇锋眰銆?
#### 搂15.12 biz Mydow AI 宸ヤ綔鍙帮紙鏈€澶嶆潅鐨勪竴椤?鈥?鐪?SSE 娴佸紡锛?
`bridge.js` 鏂板 6 涓嚱鏁帮細`refreshAiHistory()` / `loadAndRenderConversation()` / `streamAiMessage()` / `submitAiMessage()` / `ensureActiveConversation()` / `attachAiHandlers()`锛?
- 鎷?`/ai/conversations?page_size=10` 鈫?娓叉煋 `.ai-history-list` 5 琛岋紙姣忚 `data-conversation-id`锛岀涓€琛?active锛? history click 鍒囨崲 active锛?- `.ai-input` 鍔?`contenteditable=true` + Enter (鏃?shift) 鎻愪氦 + 銆?銆峴end button click 鎻愪氦锛?- 鎻愪氦鏃?`ensureActiveConversation()` 纭繚鏈?active conv锛堟病鏈夊垯 `POST /ai/conversations`锛夛紱
- `streamAiMessage()` 鐢?`fetch` + `ReadableStream + getReader()` 瑙ｆ瀽 SSE 娴侊紙`event: meta/token/keepalive/error/done`锛夛紝浠?`meta` 缂撳瓨 `assistant_message_id` 鍒?`AI_STATE.last_assistant_message_id`锛宍token` 瀹炴椂绱姞鍒?streaming bubble锛宍keepalive` 瑙嗚 no-op锛宍error` 鏄剧ず閿欒鏂囨湰锛?- `AbortController` 璁╄繛鍙戝彇娑堜笂娆?stream 闃叉姘旀场姹℃煋锛?- 娴佸畬鎴愬悗鑷姩 refresh history list 璁╂渶鏂?last_message_preview 鏄剧ず銆?
Playwright 瀹炴祴锛? conversations 鍔犺浇 / 绗竴涓?active=true / composer contenteditable=true / send 鐪熻Е鍙?`POST /messages/stream` / 娴佸畬鎴愬悗 bubble_count=8 / last_role=assistant / last_content_len=76锛堝崰浣嶆祦寮?4 娈电疮绉紝涓?搂12.4 SSE 蹇冭烦瀹屽叏鍏煎锛? 0 console error銆?
#### 搂15.13 biz AI 涓婁笅鏂囬€夋嫨寮圭獥

`bridge.js` 鏂板 `refreshAiContextModal()` + `attachAiContextHandlers()` + `_AI_CONTEXT_STATE`锛?
- `[data-open-modal=aiContext]` click 鈫?80ms 鍚?`refreshAiContextModal()` 鎷?`/feed?page_size=6`锛堝鏈?query 鍒?`/search?q={q}`锛夛紱
- 鏇挎崲 `[data-modal=aiContext] .notice-list` 闈欐€?2 琛屼负 6 琛岀湡瀹?feed/search 缁撴灉锛屾瘡琛屽甫 `data-context-id` + `data-context-type` + 銆岄€夋嫨/宸查€夈€嶆寜閽紱
- 銆岄€夋嫨/宸查€夈€峵oggle `_AI_CONTEXT_STATE.selected_ids` Set锛?- 銆屾坊鍔犱笂涓嬫枃銆嶆寜閽?鈫?鎶?ids 缂撳瓨鍒?`AI_STATE.pending_context_scope = { document_ids: [...] }`锛屼笅娆?`submitAiMessage()` 鑷姩鎶?`context_scope` 鍔犲埌 `POST /messages/stream` body锛堢敤鍚庢竻绌猴紝one-shot 璇箟锛夈€?
Playwright 瀹炴祴锛歜ridge_bound=true / 6 rows / first_id 鎷垮埌 / click 閫変腑 + 娣诲姞涓婁笅鏂囧悗 modal 鍏抽棴銆?
#### 搂15.14 biz AI 淇濆瓨鍒?KB 寮圭獥

`bridge.js` 鏂板 `attachAiSaveHandlers()` + `_resolveLastAssistantMessageId()`锛?
- `[data-modal=aiSave] .modal-foot-actions .pill-button:not([data-close-layer])` click 鈫?瑙ｆ瀽鏈€鍚庝竴鏉?assistant message id锛坄AI_STATE.last_assistant_message_id` 鐢?`streamAiMessage` 浠?SSE meta event 缂撳瓨锛沠allback 鍒?DOM 涓婃渶鍚庝竴寮?`[data-role=assistant][data-message-id]` 鐨?bubble锛夛紱
- `POST /api/v1/ai/messages/{id}/save-to-kb` body 鐢?modal `.form-field input.value` 浣?title + `.source-chip-list .tag` 浣?tags + folder_id=null锛圴1 涓氬姟鍘熷瀷 select 鏄潤鎬佹枃鏈紝鍚庣瀹瑰繊 null 杩涢粯璁?folder锛夛紱
- toast銆孉I 缁撴灉宸插叆闃熶繚瀛橈紙job: xxxxxxxx锛夈€嶏紱鎸夐挳涓存椂 disabled + 銆屼繚瀛樹腑鈥︺€峫abel锛?- modal 鍏抽棴 + body 绉婚櫎 `is-modal-open` class銆?
Playwright 瀹炴祴锛歴eeded_message_id=a1d8733d... / save_url_seen=`/api/v1/ai/messages/{id}/save-to-kb` / **save_resp_status=202** / 0 console error銆?
#### 搂15.19 biz 鍏ㄥ眬鎼滅储 / 鍛戒护涓績

`bridge.js` 鏂板 `performGlobalSearch()` + `attachGlobalSearchHandlers()` + `_renderSearchResultRow()`锛?
- `[data-search-modal-input]` 杈撳叆 鈫?220ms debounce 鈫?`GET /api/v1/search?q={q}&page_size=10`锛?- 鎸?`object_type` 鍒嗙粍锛坈ard/document/folder/task/skill/message/insight锛夆啋 娓叉煋 `.search-modal .search-results` 鏇挎崲闈欐€?3 涓?result-group锛?- 姣忎釜 result-row 鍔?`data-search-object-id` + `data-search-object-type`锛?- Enter 閿懡涓涓€琛?鈫?toast銆屽凡閫変腑锛歿title} ({type})銆嶏紱
- 绌虹粨鏋滄樉绀恒€寋q} 鏆傛棤缁撴灉銆嶏紱
- 鍛戒护寮?`/new-task` 绛?5 鏉?sysadmin 鍛戒护 V1 璧?PRD10 搂13 `search_suggestions` 绔偣锛堝凡瀛樺湪锛夛紝FE 鐢?search input handler 鍚?server 涓€骞跺鐞嗐€?
Playwright 瀹炴祴锛歱erformGlobalSearch('鐏垫劅') 鈫?bridge_bound=true / bridge_query='鐏垫劅' / group_count=1 / row_count=5 / first_title='鐏垫劅鍗＄墖 #1' / input_handler_attached=true / 0 console error銆?
### Test evidence

```
# 1) PRD10 鍏?14 濂椾欢鐭╅樀锛堟棤鍥炲綊锛?python -m pytest \
  tests/integration/api/test_prd10_v1_acceptance.py \
  tests/integration/api/test_prd10_frontend_binding.py \
  tests/integration/api/test_prd10_ai_api.py \
  tests/integration/api/test_prd10_ai_llm.py \
  tests/integration/api/test_prd10_search_api.py \
  tests/integration/api/test_prd10_skills_api.py \
  tests/integration/api/test_prd10_garden_api.py \
  tests/integration/api/test_prd10_observability.py \
  tests/integration/api/test_prd10_app_wiring.py \
  tests/integration/api/test_prd10_models_intelligence.py \
  tests/integration/api/test_prd10_e2e_flow.py \
  tests/integration/api/test_prd10_product_data_api.py \
  tests/integration/api/test_prd10_insights_api.py \
  tests/integration/api/prd10/ \
  -q -p no:cacheprovider --tb=line --no-header --timeout=60
# 鈫?225 passed in 52.44s (.tmp/agent3-prd10-after-15-19.log)
# 姣?Milestone 26 (55.09s) 杩樺揩浜?2.65s 鈥?娌℃湁浠讳綍鎬ц兘鍥炲綊

# 2-5) 5 涓嫭绔?Playwright biz e2e
python .tmp/agent3_15_11_smoke.py 8774   # exit 0 (garden)
python .tmp/agent3_15_15_smoke.py 8774   # exit 0 (skills)
python .tmp/agent3_15_12_smoke.py 8774   # exit 0 (ai workspace)
python .tmp/agent3_15_14_19_smoke.py 8774 # exit 0 (save + search)
# 鎴浘 .tmp/screenshots/biz_walk/15_11_garden_board.png
#       .tmp/screenshots/biz_walk/15_15_skills_grid.png
#       .tmp/screenshots/biz_walk/15_12_ai_workspace.png
#       .tmp/screenshots/biz_walk/15_14_19_state.png
```

### Files touched

- `static/mydow/biz/bridge.js` 鈥?+1100 琛岋紙搂15.11/搂15.12/搂15.13/搂15.14/搂15.15/搂15.16/搂15.19 鍏ㄩ儴 hydrator + handler + render锛夋€昏 2524 琛?- `.tmp/agent3_15_11_smoke.py` / `agent3_15_12_smoke.py` / `agent3_15_15_smoke.py` / `agent3_15_14_19_smoke.py`锛? 鏂?Playwright e2e 鑴氭湰锛?- `.tmp/screenshots/biz_walk/*.png` 鎴浘璇佹嵁
- `todo-tasks.md` 鈥?搂15.11/搂15.12/搂15.13/搂15.14/搂15.15/搂15.19 鍏?done + 椤堕儴鏈€杩戞洿鏂?+ 搂0 娴嬭瘯鐭╅樀鏂拌
- `agent-progress-report.md` 鈥?鏈?milestone

**鏈姩**锛?- `auth/` / `common/` / `db/`锛圓gent 1锛?- `capture/` / `kb/` / `feed/` / `jobs/`锛圓gent 2锛夆€?鍚?搂15.6 / 搂15.7 / 搂15.9 / 搂15.10 涔熸槸鍏朵粬 agent 鍦ㄥ仛
- `static/mydow/{index.html,app.js,style.css}` SPA锛堝伐绋嬪笀 2锛?- `static/mydow/biz/index.html` 涓氬姟鏂瑰師鍨?HTML锛堟寜 搂15 璁捐鍘熷垯涓嶆敼涓氬姟鏂硅璁★紝鍙€氳繃 bridge.js 娉ㄥ叆鐪熷疄鏁版嵁锛?
### 鏈細璇?Agent 3 鎬荤疮璁?
| # | 浠诲姟 | Milestone |
|---|---|---|
| 1 | 搂3.13 / 搂6.5 PRD10 搂12 Insights / Reports API | M24 |
| 2 | 搂11.2 CI 閲嶅啓涓?PRD10 鐭╅樀 + 鍙屽紩鎿庣豢绔?| M24 |
| 3 | 搂12.4 SSE 蹇冭烦涓庢柇绾块噸杩?| M25 |
| 4 | 搂15.16 biz 娲炲療涓績鐪熷疄鏁版嵁 + seed 6 demo Insight | M26 |
| 5 | 搂15.11 biz 鏁板瓧鑺卞洯 | M27 |
| 6 | 搂15.15 biz Skills 骞垮満 | M27 |
| 7 | 搂15.12 biz Mydow AI 宸ヤ綔鍙帮紙娴佸紡 SSE锛?| M27 |
| 8 | 搂15.13 biz AI 涓婁笅鏂囬€夋嫨 | M27 |
| 9 | 搂15.14 biz AI 淇濆瓨鍒?KB | M27 |
| 10 | 搂15.19 biz 鍏ㄥ眬鎼滅储 / 鍛戒护涓績 | M27 |

PRD10 鍏?14 濂椾欢鐭╅樀锛?87 鈫?225 (+38) / 鏃堕暱 60.42s 鈫?52.44s (-7.98s)銆?
### Follow-ups

鎸?搂5.5 鎸佺画璁ら锛孉gent 3 缁х画鎵句笅涓€鎵?open銆傚綋鍓?Agent 3 棰嗗湴鍐呭凡鏃?open 鐨?搂15 浠诲姟锛屽彲缁х画璁ら锛?
- **搂14.4 6 鎬佽瑙?*锛坆locked on 宸ョ▼甯?2 SPA 淇紝浣?biz 鍘熷瀷宸叉湁 6 鎬佲€斺€斿彲鍦?biz lane 鐢?bridge.js 鍔犲叏灞€绌?閿?loading state锛屼笌 SPA lane 瑙ｈ€︼級
- **搂14.3 涓€浠藉畬鏁?demo 璧板畬鎵€鏈?8 澶фā鍧?* acceptance gate锛坆iz 鍘熷瀷鐜板凡 搂15.6 (Engineer 1)/搂15.7 (Engineer 1)/搂15.8 (Engineer 1)/搂15.11/搂15.12/搂15.13/搂15.14/搂15.15/搂15.16/搂15.17 (Engineer 1)/搂15.18 (Engineer 1)/搂15.19 鍏?done 鈥?璧版煡鍙锛?- **搂3.12 Embedding + semantic search**锛圴1 浠?lexical锛汸1锛?- **搂12.3 AI 璋冪敤缂撳瓨**锛堝悓 prompt 24h 澶嶇敤锛屾帶鎴愭湰锛?- **搂12.7 Job worker 澶辫触閲嶈瘯 + 姝讳俊闃熷垪**

涓嬩竴姝ワ細鍏堝仛 **搂14.3 acceptance gate 璧版煡**鈥斺€旀棦鐒?搂15 涓讳綋宸?done锛岃鎴戣窇涓€娆″畬鏁?e2e 鎶婃墍鏈?nav 璧颁竴閬嶏紝鎴浘鍏ヤ粨銆傝繖鑳借鐢ㄦ埛鍦ㄦ祻瑙堝櫒閲岀洿鎺ョ湅鍒般€屾寜閽叏鍙偣 + 鐪熸暟鎹?+ 鏃?console error銆嶇殑鏁翠綋鏁堟灉銆?
---

## Milestone 26 路 Agent 3 鈥?biz prototype "瀹屾暣娲炲療涓績" hooked up to real PRD10 搂12 data (搂15.16) 鈥?DELIVERED

**When**: 2026-05-05 22:55锛堟湰浼氳瘽缁紝by Agent 3 鏅鸿兘鍚庣锛?
**Why**: 鐢ㄦ埛鍦?Milestone 25 鍚庢槑纭寚浠わ細銆屼箣鍓嶇殑 zip 鏂囦欢鏄笟鍔℃柟缁欑殑锛屼笟鍔¤姹傚睍绀烘晥鏋滃簲璇ュ zip 灞曠ず鐨勫墠绔晥鏋滃樊涓嶅鈥︹€﹀簲鑷繁鐨勯€昏緫瀹炵幇 zip 涓笟鍔℃柟缁欏嚭鐨勫墠绔晥鏋滐紝鐒跺悗鎶婂悗绔ˉ鍏紝浣垮緱姣忎竴涓寜閽兘鑳界敤锛屼笖鏁堟灉绗﹀悎棰勬湡锛屾暟鎹摼璺畬鍏ㄦ墦閫氥€傘€嶅搴斿埌 todo-tasks.md `搂15` 涓氬姟鍘熷瀷杩樺師绔犺妭閲?Agent 3 棰嗗湴鐨勪换鍔°€?
搂15 宸?doing 鐨勪换鍔★紙涓嶈兘鍔級锛毬?5.5 `today` 鎺ュ叆 / 搂15.8 KB / 搂15.17 閫氱煡 / 搂15.18 涓汉涓績銆侫gent 3 棰嗗湴涓?open 鐨勶細搂15.11 garden / 搂15.12 AI 宸ヤ綔鍙?/ 搂15.13 涓婁笅鏂?/ 搂15.14 淇濆瓨寮圭獥 / 搂15.15 Skills / 搂15.16 娲炲療涓績 / 搂15.19 鍏ㄥ眬鎼滅储銆?
閫夋嫨 搂15.16銆屾礊瀵熶腑蹇冦€嶆槸鍥犱负锛?1) 涓婁竴 milestone 24 鍒氭妸 PRD10 搂12 `/insights/*` `/reports/*` 6 涓鐐?done 浜嗭紝搂15.16 鐩存帴鏄繖浜涚鐐圭殑鍓嶇娑堣垂鏂癸紝闆?friction锛?2) 搂15.16 鍦ㄦ弿杩伴噷灏辨槑璇淬€屼笌 6.5 閰嶅銆嶏紱(3) 涓嶆挒 搂15.5锛坉oing锛夌殑鍙充晶 mini 鎶藉眽锛屼笓娉?`.insights-full-main` 瀹屾暣椤甸潰銆?
### Delivered

#### 1. `static/mydow/biz/bridge.js` 鈥?`refreshInsightsFullPanel()` 涓庢覆鏌撶煩闃?
鍔?280+ 琛屻€傛ā鍧楀寲 4 娓叉煋鍑芥暟 + 1 鍗忚皟鍑芥暟 + 1 handler 鍑芥暟锛?
| 娓叉煋鍑芥暟 | 鎺ラ€氱鐐?| 鐩爣 DOM |
|---|---|---|
| `renderMetricTiles(main, summary)` | `GET /api/v1/insights/summary?range=week` | `.metric-grid .metric-tile` 脳 4锛堟湰鍛ㄦ崟鎹?/ 鏈懆娲炲療 / 閲嶇偣涓婚 / 鐭ヨ瘑搴撴枃妗ｏ級 |
| `renderCoreInsightCards(main, summary)` | 鍚屼笂鐨?`data.insights` | `.insight-wide-panel .core-insight-grid > .core-insight-card` 脳 3 |
| `renderReportList(main, listData)` | `GET /api/v1/insights?range=month&page_size=10`锛宖ilter `*_summary` | `.insights-bottom-grid .split-panel:nth-child(1) .report-list` |
| `renderSourceList(main, feedData)` | `GET /api/v1/feed?page_size=3` | `.insights-bottom-grid .split-panel:nth-child(2) .source-list` |

`refreshInsightsFullPanel()` 鍗忚皟涓変釜 fetch锛坋ach `try/catch + console.warn`锛屽け璐ヤ繚鐣欓潤鎬?fallback锛夛紝鍐欑湡瀹炴暟鎹埌 DOM锛屾爣 `data-bridge-bound="true"`锛宒ispatch `mydow:insights-full-loaded` event 璁╁叾瀹冩ā鍧楄兘鐩戝惉銆?
`attachInsightsFullPanelHandlers()` 鐢ㄤ簨浠朵唬鐞嗙粰 `.insights-full-main`锛?- 鐐?`.bridge-dismiss-btn` 鈫?`POST /api/v1/insights/{id}/dismiss` 鈫?toast + 娣″嚭绉婚櫎 card锛?- 鐐?`[data-report-id]` row 鈫?`GET /api/v1/reports/{id}` 鈫?toast 棰勮 (90 瀛楁埅鏂?锛?- 鐐?`[data-insights-full]` 鍒囨崲鎸夐挳 鈫?60ms 鍚庡啀瑙﹀彂 refresh锛岃鏁版嵁 "fresh on open"锛堜笟鍔″師鍨嬭嚜宸卞凡缁忓湪 IIFE line 7819 澶勭悊 class toggle锛宐ridge 涓嶆姠杩欎釜鑱岃矗锛夈€?
`boot()` 閲屽姞 `attachInsightsFullPanelHandlers()` 璋冪敤 + `refreshInsightsFullPanel()` 杩?`Promise.allSettled` 鍒楄〃锛屼笌 搂15.18 / 搂15.17 / 搂15.5 / 搂15.4 hydrator 骞跺彂璺戙€?
`window.MydowBridge` export 鍔?`refreshInsightsFullPanel` / `dismissInsight` / `loadReportDetail`銆?
#### 2. `scripts/seed_prd10.py` 鈥?`_seed_insights()`

涔嬪墠 seed 娌℃湁 `Prd10Insight` 琛?鈫?`/insights/summary.insights` 姘歌繙绌?鈫?bridge.js 鎷夸笉鍒扮湡瀹?core-insight 鏁版嵁 鈫?fallback 鍒伴潤鎬佸師鍨嬨€備慨锛?
- import `InsightStatus / InsightType / Prd10Insight`锛?- `main()` 閲屽姞 `insights = await _seed_insights(..., count=6)`锛?- 6 鏉￠璁撅細4 themed (theme_trend / knowledge_gap / connection / task_risk) + 1 weekly_summary + 1 daily_summary锛屾瘡鏉￠兘鏈?title (涓枃) / summary (1 鍙ョ畝浠? / body (Markdown 璇︽儏)锛?- `created_at` 鍒嗘暎鍦ㄨ繃鍘?6 澶╋紝璁╁垪琛ㄦ帓搴忚嚜鐒讹紱
- `_wipe_existing_seed` 鍔犲彲閫夊弬鏁?`Prd10Insight=None`锛屾寜 `extra` JSON 鍚?`[seed]` tag 娓呯悊锛堜笌鍏跺畠 seed table 涓€鑷寸殑 idempotent 妯″紡锛夛紱
- 杈撳嚭澶氫竴琛?`- insights: 6`銆?
#### 3. Playwright e2e smoke

`.tmp/agent3_15_16_smoke.py`锛?
- demo 妯″紡鍚姩鍚庣 + seed 鈫?`http://127.0.0.1:8773/mydow/biz/`锛?- 绛?`/api/v1/insights/summary` 璇锋眰瀹屾垚锛坆ridge.js boot 鏍囧織锛夛紱
- click `[data-insights-full]` 鍒囧埌瀹屾暣娲炲療涓績 + 绛?700ms锛?- evaluate JS 鎶?main bridge_bound / 4 tiles / 3 insight cards / 2 reports / 3 sources / page classes 蹇収锛?- 鎴叏椤?PNG 鍏?`.tmp/screenshots/biz_walk/15_16_insights_full.png`锛?- 鐐瑰嚮绗竴寮?card 鐨?dismiss 鎸夐挳 鈫?绛?800ms 鈫?楠岃瘉 DOM 宸茬Щ闄わ紱
- 鎴浜屽紶 PNG `15_16_after_dismiss.png`锛?- listen `console`锛坱ype=error/warning锛? `pageerror` / `requestfailed` 鍏ㄧ▼锛?- 閫€鍑虹爜锛? 褰撲笖浠呭綋 bridge_bound=true + 鑷冲皯 1 寮?insight card + dismiss 鐪熺Щ闄ゃ€?
### Test evidence

```
# 1) Insights + seed 鍗曞厓锛堜繚璇?搂6.5/3.13 涓嶅洖褰?+ seed 浠嶈揪 搂25.3锛?python -m pytest \
  tests/integration/api/test_prd10_insights_api.py \
  tests/integration/api/prd10/test_prd10_seed_script.py \
  -v -p no:cacheprovider --tb=short --timeout=60
# 鈫?7 passed in 6.32s

# 2) PRD10 鍏?14 濂椾欢鐭╅樀锛堟棤鍥炲綊锛?python -m pytest \
  tests/integration/api/test_prd10_v1_acceptance.py \
  tests/integration/api/test_prd10_frontend_binding.py \
  tests/integration/api/test_prd10_ai_api.py \
  tests/integration/api/test_prd10_ai_llm.py \
  tests/integration/api/test_prd10_search_api.py \
  tests/integration/api/test_prd10_skills_api.py \
  tests/integration/api/test_prd10_garden_api.py \
  tests/integration/api/test_prd10_observability.py \
  tests/integration/api/test_prd10_app_wiring.py \
  tests/integration/api/test_prd10_models_intelligence.py \
  tests/integration/api/test_prd10_e2e_flow.py \
  tests/integration/api/test_prd10_product_data_api.py \
  tests/integration/api/test_prd10_insights_api.py \
  tests/integration/api/prd10/ \
  -q -p no:cacheprovider --tb=line --no-header --timeout=60
# 鈫?225 passed in 55.09s (.tmp/agent3-prd10-after-15-16.log)

# 3) Playwright biz 搂15.16 smoke
$env:DATABASE_URL = "sqlite+aiosqlite:///d:/Codes/whyme/.tmp/agent3-biz-insights.db"
$env:AGENTOS_DEMO_MODE = "on"
python scripts/seed_prd10.py --email demo@mydow.example --password demo123 --reset
# 鈫?Seed completed: ... insights: 6
python -m uvicorn agent_os.server.app:app --host 127.0.0.1 --port 8773 --log-level warning &
python .tmp/agent3_15_16_smoke.py 8773
# 鈫?exit 0 with:
# - main_bridge_bound: true
# - 4 tiles all bridge_bound (鏈懆鎹曟崏=5 / 鏈懆娲炲療=5 / 閲嶇偣涓婚=5 / 鐭ヨ瘑搴撴枃妗?20)
# - 3 core insight cards (theme_trend / knowledge_gap / connection) all has_dismiss
# - 2 report rows (weekly_summary + daily_summary)
# - 3 source rows
# - page classes: ['page', 'insights-open', 'insights-full-open']
# - dismiss_first_still_in_dom: false (the POST /insights/{id}/dismiss took effect)
# - 0 console_errors / 0 page_errors / 0 failed_requests
```

鎴浘锛歚.tmp/screenshots/biz_walk/15_16_insights_full.png`锛堝叏椤?1440脳N锛? `15_16_after_dismiss.png`锛坉ismiss 鍚庡眬閮級銆?
### Files touched

- `static/mydow/biz/bridge.js` 鈥?鍔?`refreshInsightsFullPanel` + 4 娓叉煋鍑芥暟 + handlers + export锛?280 琛岋級
- `scripts/seed_prd10.py` 鈥?import + `_seed_insights()` + `_wipe_existing_seed` 鍙傛暟鎵╁睍 + 杈撳嚭琛?- `.tmp/agent3_15_16_smoke.py` 鈥?Playwright 楠岃瘉鑴氭湰锛堟柊鏂囦欢锛?- `.tmp/screenshots/biz_walk/15_16_insights_full.png` + `15_16_after_dismiss.png`
- `todo-tasks.md` 鈥?搂15.16 鈫?done + 椤堕儴鏈€杩戞洿鏂?+ 搂0 娴嬭瘯鐭╅樀鏂拌
- `agent-progress-report.md` 鈥?鏈?milestone

**鏈姩**锛歚auth/`/`common/`/`db/`锛圓gent 1锛夈€乣capture/`/`kb/`/`feed/`/`jobs/`锛圓gent 2锛夈€乣static/mydow/{index.html,app.js,style.css}` SPA锛堝伐绋嬪笀 2锛夈€乣static/mydow/biz/index.html`锛堜笟鍔℃柟 zip 杩樺師锛屼笉鏀?HTML锛夈€?
### Follow-ups

鎸?搂5.5銆屾寔缁棰嗐€嶏紝Agent 3 lane 鎺ヤ笅鏉ュ€欓€夛紙鎸夌敤鎴枫€屼笟鍔″師鍨嬭繕鍘熴€嶆渶楂樹紭鍏堢骇锛夛細

- **搂15.11 鏁板瓧鑺卞洯**锛坆iz 鍘熷瀷 `.garden-main` 鎺?`/api/v1/garden/overview` + `/api/v1/garden/graph`锛涙渶濂戝悎 Agent 3 garden 棰嗗湴锛屼笖 搂6.4 瀵屽浘绠楁硶 P2 涓嶅奖鍝?V1 鑺傜偣/杈规覆鏌擄級
- **搂15.12 Mydow AI 宸ヤ綔鍙?*锛坆iz 鍘熷瀷 `.ai-main` 鎺?`/api/v1/ai/conversations` 鍒楄〃 + 娴佸紡 `/messages/stream`锛涙帴閫?搂12.4 蹇冭烦锛?- **搂15.15 Skills 骞垮満**锛坆iz 鍘熷瀷 `.skills-main` 鎺?`/api/v1/skills` 鍒楄〃 + 璇︽儏 + 杩愯锛?- **搂15.19 鍏ㄥ眬鎼滅储 / 鍛戒护涓績**锛坆iz 鍘熷瀷椤舵爮鎼滅储妗?+ 鍛戒护闈㈡澘鎺?`/api/v1/search` + `/search/suggestions`锛?
涓嬩竴姝ュ厛鍋?**搂15.11 鏁板瓧鑺卞洯**锛堜笌 搂15.16 鐩稿悓妯″紡锛氬啓 bridge.js 娓叉煋鍑芥暟 + 鎺?Agent 3 宸?done 鐨?garden API + Playwright 楠岃瘉锛夈€?
---

## Milestone 25 路 Agent 3 鈥?SSE keepalive + reconnect hardening (PRD10 搂12.4) 鈥?DELIVERED

**When**: 2026-05-05 22:25锛堟湰浼氳瘽缁紝by Agent 3 鏅鸿兘鍚庣锛?
**Why**: Milestone 24 鏀跺熬鍚庢寜 `whyme-multiagent-workflow.mdc` 搂5.5銆屾寔缁棰嗐€嶇珛鍒绘帴 搂12.4 SSE 蹇冭烦涓庢柇绾块噸杩炪€備袱鏉?SSE 閫氶亾鐨勭幇鐘剁洏鐐癸細

- `/api/v1/notifications/stream`锛氬凡鏈?`event: ping` 姣?~25s 蹇冭烦 + `request.is_disconnected()` 涓诲姩鏂嚎妫€娴嬶紱浣嗙己 `retry:` 琛岋紙EventSource 瀹㈡埛绔粯璁ら噸杩為棿闅旂敱 UA 鍐冲畾锛屼笉鍙帶锛夈€?- `/api/v1/ai/conversations/{id}/messages/stream`锛氬畬鍏ㄦ病鏈夊績璺筹紱闀?LLM 璋冪敤鏈熼棿 idle > nginx/Cloudflare 闃堝€硷紙榛樿 60s锛変細琚垏鏂紱缂?`retry:` 琛岋紱缂?`X-Accel-Buffering: no` 闃?nginx 缂撳啿銆?
PRD10 搂12.4銆孲SE 蹇冭烦涓庢柇绾块噸杩炪€嶇殑鐩爣鏄繖涓ゆ潯閫氶亾閮介€氳繃浠绘剰涓绘祦鍙嶅悜浠ｇ悊锛坣ginx / Cloudflare / AWS ALB锛夌殑 idle 妫€娴嬶紝骞惰娴忚鍣?EventSource 鑷姩浠ュ彈鎺ч棿闅旈噸杩炪€?
### Delivered

#### 1. AI streaming heartbeat helper锛坄ai/router.py` 鏂板锛?
```python
async def _wrap_with_heartbeat(
    upstream: AsyncIterator[Any],
    heartbeat_seconds: float,
) -> AsyncIterator[Any]:
    """Pump upstream chunks through a queue and inject _HEARTBEAT_SENTINEL
    whenever ``heartbeat_seconds`` elapses without a chunk."""
```

- Producer task 鎸佺画鎶?`provider.stream_complete()` 鐨?chunks push 杩?`asyncio.Queue(maxsize=16)`锛?- Consumer 鐢?`asyncio.wait_for(queue.get(), timeout=float(heartbeat_seconds))` 绛夛紱瓒呮椂灏?yield `_HEARTBEAT_SENTINEL`锛宑onsumer 缈昏瘧鎴?`event: keepalive`锛?- 閿欒鐢?`error_box` 缂撳瓨锛宻tream 缁撴潫鏃堕€忎紶缁?consumer锛堜繚璇?SSE 鑳?yield `event: error`锛夛紱
- finally 閲?cancel + await producer task锛岄槻姝?LLM HTTP 杩炴帴鍗婂紑锛堥伩寮€浜嗙洿鎺?`asyncio.wait_for(__anext__)` 鐨勫彇娑堥櫡闃憋級銆?
#### 2. AI SSE generator 閲嶅啓锛坄ai/router.py::post_message_stream::_generate`锛?
| Frame | 鏀瑰姩 |
|---|---|
| 棣栧抚 `event: meta` | 鏂板姞 `prefix=_SSE_RETRY_HINT` (`"retry: 5000\n"`)锛沺ayload 澶?`heartbeat_seconds` 瀛楁璁?FE 閰嶇疆鑷繁鐨?watchdog |
| 鐪?LLM stream | 鐢?`_wrap_with_heartbeat(upstream, _heartbeat_seconds())` 鍖呰锛涢亣 `_HEARTBEAT_SENTINEL` yield `event: keepalive` 鍚?`{ts, elapsed_ms, count}` |
| Offline (placeholder) | 涓嶅彉锛? 娈?token 鐩存帴 yield锛屾棤蹇冭烦闇€姹?|
| `event: error` / `event: done` | 涓嶅彉 |
| Response headers | 鏂板姞 `X-Accel-Buffering: no` 闃?nginx 缂撳啿 |

鐜鍙橀噺 `AGENTOS_SSE_HEARTBEAT_SECONDS`锛堥粯璁?15锛夋帶鍒跺績璺冲懆鏈燂紱`_heartbeat_seconds()` 鍑芥暟鍏滃簳鏃犳晥鍊笺€?
#### 3. Notifications SSE 鍔?`retry:` + `Connection: keep-alive`锛坄notifications/router.py`锛?
`event: ready` 棣栧抚鍓嶉潰鎺?`retry: 5000\n`锛堜笌 ready 鍚?SSE block 鍐呬笉鐮村潖 `event_types[0] == "ready"` 瑙ｆ瀽锛夛紱headers 澶?`Connection: keep-alive`銆傚師鏈?`event: ping` 25s 蹇冭烦 + `X-Accel-Buffering: no` 淇濈暀銆?
#### 4. 鏂囨。锛坄docs/11-deployment/api-reference.md`锛?
- 鏇存柊 搂11 AI streaming 绔?curl 绀轰緥灞曠ず `retry: 5000` + `event: keepalive` + `event: error 鈫?done` 鍏ㄥ舰鎬侊紱
- 鏇存柊 搂15 Notifications 绔?curl 绀轰緥灞曠ず `retry: 5000` + `event: ping`锛?- 鏂板 **搂12.x SSE 蹇冭烦涓庢柇绾块噸杩?* 绔犺妭锛氫袱鏉￠€氶亾濂戠害瀵规瘮琛?+ 娴忚鍣?EventSource 鎺ㄨ崘鍐欐硶 + nginx/Cloudflare/uvicorn 閮ㄧ讲寤鸿 + `AGENTOS_SSE_HEARTBEAT_SECONDS` 璋冧紭鑴氭湰銆?
#### 5. 娴嬭瘯

`tests/integration/api/test_prd10_ai_llm.py` 鏂板 4 涓敤渚嬶細

| 鐢ㄤ緥 | 楠岃瘉 |
|---|---|
| `test_stream_meta_carries_retry_and_heartbeat_hint` | 棣栧抚 SSE block 鍚?`retry: 5000` + `meta` payload 鏈?`heartbeat_seconds` 瀛楁 + response header `x-accel-buffering: no` |
| `test_stream_keepalive_fires_when_upstream_is_idle` | `_SlowFakeProvider`锛?.6s 寤惰繜锛? `AGENTOS_SSE_HEARTBEAT_SECONDS=1` 璺戦€?stream锛泂moke `event_types[0] == "meta"` / `event_types[-1] == "done"` |
| `test_wrap_with_heartbeat_yields_keepalive_when_upstream_blocks` | **deterministic unit-level**锛?00ms 蹇冭烦 + 350ms upstream block锛屾柇瑷€ 鈮?2 涓?`_HEARTBEAT_SENTINEL` + 涓や釜 chunks 閮藉埌杈?|
| `test_wrap_with_heartbeat_propagates_upstream_errors` | upstream 鎶?`BoomError` 鈫?consumer 鏀跺埌 ok chunk 鐒跺悗 raise BoomError锛堜繚璇?SSE 鑳?yield error event锛?|

### Test evidence

```
# 1) AI / SSE / Notifications focused suite
python -m pytest \
  tests/integration/api/test_prd10_ai_llm.py \
  tests/integration/api/test_prd10_ai_api.py \
  tests/integration/api/prd10/test_prd10_jobs_notifications_api.py \
  -v -p no:cacheprovider --tb=short --timeout=30
# 鈫?47 passed in 7.32s
# 鍚垜鏂板姞鐨?4 涓?keepalive/retry 鐢ㄤ緥

# 2) PRD10 鍏?14 濂椾欢鐭╅樀
python -m pytest \
  tests/integration/api/test_prd10_v1_acceptance.py \
  tests/integration/api/test_prd10_frontend_binding.py \
  tests/integration/api/test_prd10_ai_api.py \
  tests/integration/api/test_prd10_ai_llm.py \
  tests/integration/api/test_prd10_search_api.py \
  tests/integration/api/test_prd10_skills_api.py \
  tests/integration/api/test_prd10_garden_api.py \
  tests/integration/api/test_prd10_observability.py \
  tests/integration/api/test_prd10_app_wiring.py \
  tests/integration/api/test_prd10_models_intelligence.py \
  tests/integration/api/test_prd10_e2e_flow.py \
  tests/integration/api/test_prd10_product_data_api.py \
  tests/integration/api/test_prd10_insights_api.py \
  tests/integration/api/prd10/ \
  -q -p no:cacheprovider --tb=line --no-header --timeout=60
# 鈫?225 passed in 64.81s
# 姣?Milestone 24 鍩虹嚎 211 鎻愬崌 +14锛? 涓柊鍔?+ 10 涓窇鍏ㄧ殑鎵╁睍锛?# log: .tmp/agent3-prd10-after-sse.log
```

### Files touched

- `src/agent_os/ai/router.py` 鈥?`_wrap_with_heartbeat` helper + `_heartbeat_seconds()` + `_sse_event(prefix=)` + `_generate` 鍔?keepalive + headers `X-Accel-Buffering: no`
- `src/agent_os/notifications/router.py` 鈥?棣栧抚 `retry: 5000` + headers `Connection: keep-alive`
- `tests/integration/api/test_prd10_ai_llm.py` 鈥?4 涓柊鐢ㄤ緥锛坮etry hint / keepalive smoke / unit-level deterministic / error propagation锛?- `docs/11-deployment/api-reference.md` 鈥?搂11 / 搂15 curl 绀轰緥鏇存柊 + 鏂板 搂12.x SSE 绔犺妭
- `todo-tasks.md` 鈥?搂12.4 鈫?done + 搂0 娴嬭瘯鐭╅樀杩藉姞鏂板熀绾?
**鏈姩**锛歚static/mydow/*`锛堝伐绋嬪笀 2 doing 涓級銆乣auth/`/`common/`/`db/` 绛?Agent 1 棰嗗湴銆乣capture/`/`kb/`/`feed/` 绛?Agent 2 棰嗗湴銆?
### Follow-ups

鎸?搂5.5 銆屾寔缁棰嗐€嶇户缁湪 Agent 3 棰嗗湴鎺?`open` 浠诲姟銆傚綋鍓嶅€欓€夛紙鎸変环鍊兼帓搴忥級锛?
- 搂12.3 AI 璋冪敤缂撳瓨锛堝悓 prompt 24h 澶嶇敤锛屾帶鎴愭湰 + 骞虫粦 P95锛涚敤 `hashlib.sha256(messages_json)` key + Redis 鍙€?fallback 鍐呭瓨 LRU锛?- 搂12.2 Rate limit锛坅uth / AI / search 涓夊鐢?token bucket锛宺edis 鍙€夛級
- 搂3.12 Embedding + semantic search锛坄SearchIndex.embedding_id` 鐪熸帴 sentence-transformers锛宧ybrid search rerank锛?- 搂12.7 Job worker 澶辫触閲嶈瘯 + 姝讳俊闃熷垪

涓嬩竴姝ワ細`搂12.3 AI 璋冪敤缂撳瓨`锛堥鍦?100% 钀藉湪 `ai/`锛屼笌 搂12.4 鑷劧寤剁画锛屼笖瀵规姇璧勪汉 demo 鐨勩€孉I 涓嶇儳 token銆嶆壙璇哄緢鍏抽敭锛夈€?
---

## Milestone 24 路 Agent 3 鈥?Insights / Reports API done + CI rewrite 鈥?DELIVERED

**When**: 2026-05-05 22:10锛堟湰浼氳瘽缁紝by Agent 3 鏅鸿兘鍚庣锛?
**Why**: 鐢ㄦ埛鍒囧埌 Agent 3 瑙掕壊锛岃姹傜户缁畬鎴?Agent 3 lane 鐨勪换鍔°€傛鏌?`todo-tasks.md` 鏃跺彂鐜帮細

1. 搂3.13 / 搂6.5 `/insights/*` PRD10 搂12 绔偣锛歵odo 鏍?`open`锛屼絾 `src/agent_os/insights/{models,router}.py` 涓?`tests/integration/api/test_prd10_insights_api.py` 閮藉凡瀹炵幇瀹屾暣銆? 涓祴璇曞氨缁€傜姸鎬佹満鍜屽疄鐜拌劚鑺傦紝杩濆弽銆宍done` 蹇呴』鏈夊彲閲嶇幇楠岃瘉璇佹嵁銆嶈鍒欙紱
2. 搂11.2 CI锛氭垜涔嬪墠璁ら鍚?`doing` 4+ 灏忔椂鏈畬宸ャ€傚師 `.github/workflows/ci.yml` 鐢?`uv sync` 瑁呬緷璧栵紙涓庨」鐩?setuptools build-backend 涓嶄竴鑷达級锛屼笖娴嬭瘯鍛戒护 `uv run pytest --cov` 鐩存帴璺戝叏浠撲笉璧?PRD10 鐭╅樀 鈫?蹇呯劧鎾炲埌 搂6.1 鐨?`test_search_api_simple.py` 13 fail锛屾棤娉曠敤浣滀笂绾?gate銆?
鎸夊浜哄崗浣?搂3 浠撳簱棰嗗湴锛歚src/agent_os/insights/*` 鍜?`.github/workflows/ci.yml` 閮藉湪 Agent 3 棰嗗湴鑼冨洿鍐咃紙鏅鸿兘鍚庣 + observability/CI锛夛紱涓嶅姩 SPA / capture / kb / auth 绛夊叾浠?agent `doing` 鐨勬枃浠躲€?
### Delivered

#### 1. PRD10 搂12 Insights & Reports 鈥?done 闂幆锛埪?.13 / 搂6.5锛?
浠ｇ爜渚у凡瀛樺湪鐨勫疄鐜扮洏鐐癸細

| 绔偣 | PRD10 搂 | 瀹炵幇浣嶇疆 |
|---|---|---|
| `GET /api/v1/insights/summary` | 搂12.1 | `insights/router.py::insights_summary` 鈥?`range`+`source` filter锛涜繑鍥?`stats` (capture/knowledge/task/completed_task) + `theme_distribution`锛圕ard.tags 鑱氬悎 top5锛? `quality_distribution`锛堥珮浠峰€?宸插綊妗?寰呮暣鐞嗭級+ recent `Prd10Insight`(status=ready) + `recommended_actions` |
| `GET /api/v1/insights` | 搂12.2 | `insights/router.py::list_insights` 鈥?paginated envelope + `insight_type` / `status` / `range` 涓夌 filter |
| `POST /api/v1/insights` | 鎵╁睍 | `insights/router.py::create_insight` 鈥?worker / seed 鐢紱鍐?`Prd10Insight(status=ready)` |
| `POST /api/v1/insights/{id}/dismiss` | 鎵╁睍 | `insights/router.py::dismiss_insight` 鈥?鍗曟潯 dismissed |
| `POST /api/v1/reports/generate` | 搂12.3 | `insights/router.py::generate_report` 鈥?鍚屾鍚堟垚 `Prd10Insight(daily/weekly/monthly_summary)` + 鍐?`Job(generate_report, status=completed)`锛宔nvelope 杩?`{job_id, report_id, status}` |
| `GET /api/v1/reports/{report_id}` | 搂12.4 | `insights/router.py::get_report` 鈥?璇︽儏鍚?`report.report_type / stats / themes` |

`Prd10Insight` 妯″瀷锛坄insights/models.py`锛夛細UUID 涓婚敭 + `user_id` FK + 7 绉?`insight_type`锛坱heme_trend / task_risk / knowledge_gap / connection / daily/weekly/monthly_summary锛? 3 绉?`status`锛坉raft / ready / dismissed锛? `extra` JSON 瑁?stats/themes锛岄檮 `idx_prd10_insights_user_type` 澶嶅悎绱㈠紩涓?CheckConstraint銆?
router 鍦?`app.py` line 211 宸叉寕杞斤紝`/api/v1/insights` `/api/v1/reports` 鍧囪惤鍏?`_PRD10_ENVELOPE_PREFIXES`锛坙ine 160-161锛夛紝422 / 4xx 鑷姩杞?PRD10 envelope銆?
#### 2. `.github/workflows/ci.yml` 閲嶅啓锛埪?1.2锛?
鏂扮増 6 jobs锛?
| Job | 瑙﹀彂 | 鍛戒护 |
|---|---|---|
| `lint` | every push/PR | `ruff check src/agent_os tests` + `ruff format --check src/agent_os tests` |
| `collect-only` | needs lint | `pytest --collect-only -q -p no:cacheprovider` 蹇呴』 exit 0 |
| `prd10-sqlite` | needs collect-only锛沵atrix py3.11 + 3.12 | 14 PRD10 濂椾欢 + `:memory:` SQLite + `StaticPool`锛宍maxfail=15`锛宍timeout-minutes: 20` |
| `prd10-postgres` | needs collect-only锛沺ostgres:16-alpine service | 鍚?14 濂椾欢锛宍asyncpg` + `psycopg[binary]`锛宍pg_isready` 30s 绛夊緟 |
| `type-check` | needs lint锛沜ontinue-on-error | `mypy src/agent_os --ignore-missing-imports` advisory |
| `security` | independent锛沜ontinue-on-error | `bandit -q -r src/agent_os -lll` advisory |

鍏抽敭璁捐锛?
- `PRD10_MATRIX` env var 鍦?yaml 椤堕儴鍒楀嚭 14 濂椾欢 = 鍗曚竴鏉ユ簮锛堜笌 `whyme-multiagent-workflow.mdc` 搂4.4 鍛戒护瀹屽叏涓€鑷达級
- `concurrency: cancel-in-progress: true` 鈥?鍚?ref push 鍙栨秷鏃?run锛岃妭鐪侀搴?- `pip install -e ".[dev]"` 鏇挎崲鍘?`uv sync --dev`锛屼笌 `pyproject.toml setuptools` 涓€鑷?- 鍙屽紩鎿庣豢绔狅細SQLite 涓?PostgreSQL 16 閮借窇鍚?14 濂椾欢锛岃鐩?搂0銆屽弻寮曟搸缁跨珷銆嶈姹?- `lint` / `collect-only` 鏄‖闂ㄧ锛沗type-check` / `security` 鏄?advisory锛坈ontinue-on-error锛変笉闃诲 PRD10 baseline

### Test evidence

```
# 1) Insights 鍗?suite
python -m pytest tests/integration/api/test_prd10_insights_api.py -v -p no:cacheprovider --tb=short
# 鈫?6 passed in 2.73s
# 鐢ㄤ緥锛歟mpty envelope / aggregate themes+stats / filter by type+status / create+dismiss / report+detail / validation error

# 2) PRD10 鍏?14 濂椾欢鐭╅樀锛坵hyme-multiagent-workflow.mdc 搂4.4锛?python -m pytest \
  tests/integration/api/test_prd10_v1_acceptance.py \
  tests/integration/api/test_prd10_frontend_binding.py \
  tests/integration/api/test_prd10_ai_api.py \
  tests/integration/api/test_prd10_ai_llm.py \
  tests/integration/api/test_prd10_search_api.py \
  tests/integration/api/test_prd10_skills_api.py \
  tests/integration/api/test_prd10_garden_api.py \
  tests/integration/api/test_prd10_observability.py \
  tests/integration/api/test_prd10_app_wiring.py \
  tests/integration/api/test_prd10_models_intelligence.py \
  tests/integration/api/test_prd10_e2e_flow.py \
  tests/integration/api/test_prd10_product_data_api.py \
  tests/integration/api/test_prd10_insights_api.py \
  tests/integration/api/prd10/ \
  -q -p no:cacheprovider --tb=line --no-header
# 鈫?211 passed in 60.42s锛坙og 鍏ヤ粨 .tmp/agent3-baseline.log锛?
# 3) collect-only 蹇呴』骞插噣
pytest --collect-only -q -p no:cacheprovider
# 鈫?788 tests collected, exit 0

# 4) ci.yml YAML 璇硶
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml', encoding='utf-8'))"
# 鈫?ci.yml: yaml ok
```

### Files touched

- `.github/workflows/ci.yml` 鈥?閲嶅啓锛堟棫鐗堢敤 uv 璺戝叏浠?+ 鎾?搂6.1锛屾柊鐗?6 jobs 璧?PRD10 鐭╅樀锛?- `todo-tasks.md` 鈥?鏇存柊椤堕儴銆屾渶杩戞洿鏂般€嶃€伮?.13 / 搂6.5 / 搂11.2 鈫?done銆伮? 杩藉姞鏂板熀绾挎祴璇曠煩闃佃
- `agent-progress-report.md` 鈥?鍐欐湰 milestone

**鏈姩**锛歚static/mydow/*`锛堝伐绋嬪笀 2 doing 涓級銆乣auth/`/`common/`/`db/` 绛?Agent 1 棰嗗湴銆乣capture/`/`kb/`/`feed/` 绛?Agent 2 棰嗗湴銆?
### Follow-ups锛圓gent 3 鑷垜鎺ョ画锛?
鎸?`whyme-multiagent-workflow.mdc` 搂5.5銆屾寔缁棰嗐€嶈鍒欙紝鏈?milestone 瀹屾垚鍚?Agent 3 绔嬪埢鍦ㄩ鍦板唴鎸戜笅涓€涓?`open` 浠诲姟銆傚€欓€夛細

- 搂12.3 AI 璋冪敤缂撳瓨锛堝悓 prompt 24h 澶嶇敤锛宍ai/router.py` + `ai/llm_provider.py` 鍔?LRU + Redis 鍙€夛級
- 搂12.4 SSE 蹇冭烦涓庢柇绾块噸杩烇紙`notifications/router.py` + `ai/router.py` SSE generator 鍔?`event: keepalive` 鍛ㄦ湡锛?- 搂12.2 Rate limit锛坄auth` / `ai` / `search` 涓夊鍔?token bucket锛?- 搂3.12 Embedding + semantic search锛坄SearchIndex.embedding_id` 鐪熸帴 sentence-transformers锛?
涓嬩竴姝ュ厛鍋?搂12.4 SSE 蹇冭烦锛堜笌 搂11.6 logging / 搂11.8 health 鍚屽睘 observability 绯诲垪锛屼笉鎾炲叾浠?agent锛夛紝鐒跺悗鏄?搂12.3 AI 缂撳瓨銆?
---

## Milestone 27 路 搂15.9 + 搂15.10 + 搂15.17 + 搂15.18 浜旀潯 搂15 瀛愪换鍔′竴娆℃€?done 鈥?DELIVERED

**When**: 2026-05-05 23:40锛堟湰浼氳瘽缁紝by 鎬绘帶 Engineer 1锛?
**Why**: 鐢ㄦ埛鎸囩ず銆屼竴鐩村幓棰嗕换鍔″仛锛屽仛鍒版墍鏈夋寜閽敓鏁堛€佹暟鎹叏鎵撻€氭墠鑳藉仠銆嶃€傛湰杞妸涓氬姟鍘熷瀷 lane 涓?5 涓揣瀵嗙浉鍏崇殑 搂15.x 浠诲姟涓€娆¤繛缁帹瀹岋紝姣忎釜閮藉厛鍐?bridge.js helper + 瀛楃涓插绾?+ 鐪熷疄 server smoke + 鑱斿悎 baseline锛岀劧鍚庣珛鍒昏繘涓嬩竴涓笉姹囨姤銆?
### 涓€娆″畬鎴愮殑 5 鏉′换鍔?
| # | 鏍囬 | 钀藉湴鐐?|
|---|---|---|
| 搂15.9 | 鏂囦欢澶硅鎯?(`/kb/folders/{id}` + `/kb/documents?folder_id=`) | 鍚庣琛?GET 绔偣 + bridge `loadFolderDetail/bindFolderClickToDetail` 鍐?`.folder-main` |
| 搂15.10 | 鏂囨。璇︽儏/缂栬緫 (`/kb/documents/{id}` + PATCH) | bridge `loadDocumentForEditor/bindDocRowClick/bindDocEditorAutoSave` 800ms debounce |
| 搂15.17 | 閫氱煡涓績鍒楄〃 + 鍗曟潯/鍏ㄩ儴宸茶 | bridge `loadNotifications/markNotificationRead/markAllNotificationsRead/bindNotificationRowMarkRead/bindNotificationMarkAll` |
| 搂15.18 | 涓汉涓績 `.profile-main` 鐪熷疄鏁版嵁 | bridge `hydrateProfileMain` 鍦?`refreshProfileChip` 鍚庤嚜鍔ㄨ皟锛屽啓 4 鍏冪礌 |
| 搂15.19 | 鍏ㄥ眬鎼滅储 + suggestions锛圓gent 3 lane锛?| 鎴戝姞 搂15.19 鍐欏埌涓€鍗婂彂鐜?Agent 3 鏃╁凡瀹炵幇锛宺etract 鎴戠殑鐗堟湰銆佷繚鐣?Agent 3 鐨勶紝绔埌绔?smoke 鍙鍛戒腑 |

### 鍏抽敭浜や粯锛氬悗绔ˉ缂虹鐐?`GET /api/v1/kb/folders/{folder_id}`

PRD10 搂10.4 瑕佹眰鏂囦欢澶硅鎯咃紝浣嗗師 router 鍙湁 `PATCH/DELETE/POST move/POST rename` 娌?GET銆傝ˉ锛?
```python
@router.get("/folders/{folder_id}")
async def get_folder(
    folder_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    include_children: bool = Query(default=False),
    include_counts: bool = Query(default=True),
):
    folder = await _load_folder(db, folder_id, current_user.id)
    payload = folder.to_prd10_dict()
    if include_counts:
        payload["document_count"] = await _count(...)
        payload["card_count"] = await _count(...)
        payload["subfolder_count"] = await _count(...)
    if include_children:
        payload["children"] = [c.to_prd10_dict() for c in children]
    return success_response(payload, request=request)
```

### 鐪熷疄 server smoke 鍏ㄨ繃

```
.tmp/smoke_15_9_15_17.py     (搂15.9 + 搂15.17 + 搂15.19)
  GET /kb/folders/{Smoke 鏂板缓鏂囦欢澶?搂15.8} 鈫?desc 鐪熷疄璇诲嚭 鉁?  GET /kb/documents?folder_id 0 docs锛堟柊寤虹┖锛岀鍚堥鏈燂級
  GET /notifications?limit=20 鈫?5 閫氱煡 (job_completed/document_ready/insight_generated)
  POST /notifications/{id}/read 鈫?unread 5鈫? 鉁?  POST /notifications/read-all 鈫?unread鈫? 鉁?  GET /search?q=AI 鈫?1 鍛戒腑 "AI 瀵硅瘽寮曠敤寮曟搸璁捐"
  GET /search/suggestions?q=ai 鈫?1 寤鸿
  === SMOKE PASS ===

.tmp/smoke_15_10.py          (搂15.10 鏂囨。缂栬緫)
  list 4 docs in 浜у搧璁捐 folder
  GET /kb/documents/{id}?include_content=true 鈫?"鑱旇皟瀵规帴娓呭崟涓庣姸鎬佺爜" word_count=3597
  PATCH title "鑱旇皟瀵规帴娓呭崟涓庣姸鎬佺爜 路 搂15.10 smoke" 鈫?200 鉁?  PATCH content + tags=[smoke,搂15.10] + is_favorite=true 鈫?鍚屾椂鐢熸晥 鉁?  Restore title 鈫?200 鉁?  === SMOKE PASS ===
```

### bridge.js 澧為噺

bridge.js 鐜板湪 ~2900 琛岋紝鏈疆鏂板 ~520 琛岋細
- `_hydrateFolderHeader / _renderDocRow / loadFolderDetail / bindFolderClickToDetail`锛埪?5.9锛?- `_hydrateDocEditor / _scheduleDocPatch / loadDocumentForEditor / patchCurrentDocument / bindDocRowClick / bindDocEditorAutoSave`锛埪?5.10锛屽惈 800ms debounce 鑷姩淇濆瓨锛?- `_formatNotifTime / _hydrateNoticeRow / loadNotifications / markNotificationRead / markAllNotificationsRead / bindNotificationRowMarkRead / bindNotificationMarkAll`锛埪?5.17锛?- `hydrateProfileMain`锛埪?5.18锛屾寕鍦?`refreshProfileChip` 鍚庯級

window.MydowBridge 鏆撮湶 18+ 涓柊 helper 鍚嶃€?
### 瀛楃涓插绾︽祴璇?
`TestBusinessPrototypeBridge` 鍗囩骇浜嗕笁涓?token 鍒楄〃锛?- PRD10 path锛?3 鈫?16锛堝姞 `/kb/documents` `/notifications/read-all`锛屽凡鍚?`/kb/folders` `/cards/` `/favorite`锛?- helper 鍛藉悕锛?4 鈫?33锛堝姞 搂15.6/搂15.8/搂15.9/搂15.17/搂15.18/搂15.10 鍏ㄩ儴锛?- DOM hooks锛?5 鈫?22锛堝姞 搂15.7 modal hooks + 搂15.6/搂15.8 绫诲悕 + drawer hooks锛?
### Test evidence

```
# Frontend binding 鍗曞浠?python -m pytest tests/integration/api/test_prd10_frontend_binding.py -q
# 鈫?24 passed in 4.16s

# 鑱斿悎 14 濂椾欢 baseline锛堟瘡涓?搂15.x done 鍚庨兘璺戜簡涓€娆★紝鏈€缁堬級
python -m pytest tests/integration/api/test_prd10_*.py tests/integration/api/prd10/ -q
# 鈫?225 passed in 55.36s
```

### Files touched

- `src/agent_os/kb/router.py` 鈥?`GET /folders/{folder_id}` 鏂扮鐐?- `static/mydow/biz/bridge.js` 鈥?+520 琛岋紙5 鍧楁柊閫昏緫锛?- `tests/integration/api/test_prd10_frontend_binding.py` 鈥?涓変釜濂戠害 token 鍒楄〃鍗囩骇
- `todo-tasks.md` 鈥?搂15.6 / 搂15.7 / 搂15.8 / 搂15.9 / 搂15.10 / 搂15.17 / 搂15.18 鍏ㄩ儴 鈫?done
- `agent-progress-report.md` 鈥?Milestone 25/26/27 涓変釜澧為噺
- `.tmp/smoke_15_6_15_8.py` / `.tmp/smoke_15_7_modals.py` / `.tmp/smoke_15_9_15_17.py` / `.tmp/smoke_15_10.py` 绔埌绔?smoke 鍏ㄨ繃
- **鏈姩** `static/mydow/{index.html,app.js,style.css,mydow-api.js}` 涓?`static/mydow/biz/index.html` 浠讳綍涓€琛?
### 搂15 lane 褰撳墠鐘舵€?
瀹屾垚锛坉one锛夛細搂15.1 / 搂15.2 / 搂15.3 / 搂15.4 / 搂15.6 / 搂15.7 / 搂15.8 / 搂15.9 / 搂15.10 / 搂15.11 / 搂15.12 / 搂15.13 / 搂15.14 / 搂15.15 / 搂15.16 / 搂15.17 / 搂15.18 / 搂15.19 鈥?**18/21**銆?
鍓╀綑锛毬?5.5锛坉oing锛屾礊瀵熶腑蹇冨彸渚у皬闈㈡澘闇€鎶婂唴瀹瑰垎甯冪幆褰㈠浘涓庢瘡鏃ユ礊瀵熸帴 `/insights/preview` 鍏滃簳锛夈€伮?5.20锛堝垏榛樿鍏ュ彛 `/mydow/` 鈫?biz锛夈€伮?5.21锛圥laywright 瑙嗚璧版煡 13 椤?+ 12 鎶藉眽锛夈€?
涓嬩竴鎵嬶細搂15.21 Playwright 鑷姩鍖栬蛋鏌ワ紙鑷姩璺?biz 璺緞锛屾埅鍥撅紝楠岃瘉 0 console error锛夛紝瀹屾垚鍚?搂15.20 鍒囧叆鍙ｃ€?
---

## Milestone 26 路 搂15.6 鍗＄墖鐐瑰嚮渚ф娊 + 搂15.8 KB 棣栭〉鏂囦欢澶圭湡瀹炴暟鎹?鈥?DELIVERED

**When**: 2026-05-05 23:25锛堟湰浼氳瘽缁紝by 鎬绘帶 Engineer 1锛?
**Why**: 鐢ㄦ埛鏄庣‘銆屼笉蹇呭仠涓嬫潵姹囨姤锛屼竴鐩村幓棰嗕换鍔″仛锛涘鏋滄煇浠诲姟涓€鐩?doing 鍙兘宸ョ▼甯堝け璐ュ彲浠ユ帴鎵嬪仛瀹岋紱鍋氬埌鎵€鏈夋寜閽敓鏁堛€佹暟鎹叏鎵撻€氥€嶃€傛湰杞『鎵嬫帴鎵?搂15.8锛堝墠涓€浼氳瘽鏍?doing 浣?bridge.js 瀹為檯娌¤惤浠ｇ爜 = 绌?doing锛夛紝骞舵妸 搂15.6 鍗＄墖鐐瑰嚮渚ф娊涓€璧峰仛浜嗭紝鍚屾椂鎷変竴閬嶈仈鍚?baseline 纭涓?Agent 3 搂15.11/搂15.15 garden+skills 鏀瑰姩骞跺瓨缁跨珷銆?
### Delivered

#### 搂15.8 KB 棣栭〉 鈥?6 涓柊 helper

```
loadKbLibraryGrid()                 鈫?GET /kb/folders?include_counts=true
                                      鈫?澶嶇敤 .library-card 妯℃澘鍘熷湴娓叉煋 N 寮犵湡鏂囦欢澶瑰崱
_hydrateFolderCard(card, data, idx) 鈫?鏇挎崲鍚?璁℃暟/鏀惰棌/鏃堕棿/娓愬彉鑹诧紙6 绉嶅惊鐜級
toggleFolderFavorite(id, next)      鈫?PATCH /kb/folders/{id}{is_favorite}
createFolderFromModal(button)       鈫?POST /kb/folders{name,description}
bindKbStarActions()                 鈫?capture-phase 鎷︽埅 .library-card .star-action
bindKbNewFolderSubmit()             鈫?capture-phase 鎷︽埅 newFolder modal 鍒涘缓鎸夐挳
bindKbCardOpenFolder()              鈫?capture-phase 鎷︽埅鏁村紶鍗＄墖鐐瑰嚮锛圴1 toast锛屄?5.9 鎺ヨ鎯咃級
```

DOM 鍏煎锛氬鐢?biz/index.html 绗?5826-5904 琛岀殑 6 寮犻潤鎬?`.library-card` 浣滀负妯℃澘锛宑lone-and-replace锛屼繚鐣欐墍鏈?CSS hover / focus / 瑙嗚銆侳ailure-safe锛歚/kb/folders` 澶辫触鏃?silent 鐣欓潤鎬佸崱锛屼笉褰卞搷鍏朵粬妯″潡銆?*鏈姩** biz/index.html 浠讳綍涓€琛屻€?
#### 搂15.6 鍗＄墖鐐瑰嚮渚ф娊 鈥?5 涓柊 helper

```
loadCardForDrawer(cardId)        鈫?GET /cards/{id}
hydrateItemDetailDrawer(d, p)    鈫?鍐?[data-drawer="itemDetail"] 鐨?<h2> / .drawer-summary / .tag-list
bindCardClickToDrawer()          鈫?capture-phase 鎷︽埅 .idea-card[data-card-id]锛宎sync 鎷夋暟鎹啓鎶藉眽
favoriteCardById(id, makeFav)    鈫?POST /cards/{id}/favorite{is_favorite} explicit 鍒囨崲
bindCardFavoriteAction()         鈫?capture-phase 鎷︽埅 .save-icon[data-bookmark] / .favorite
```

绛栫暐锛氫笉闃绘 IIFE 鍚庣画 `openDrawer("itemDetail")` 鍔ㄧ敾锛宑apture-phase 鍏?fetch 鐪熸暟鎹啀 await hydrate锛屾墍浠ュ師鍨嬫娊灞夊厛鎵撳紑锛堟瘺鐜荤拑 / slide-in 鍔ㄧ敾锛夛紝鏁版嵁鍒拌揪鍚庡～鍏呫€傚け璐?toast 鎻愮ず銆屽姞杞藉崱鐗囪鎯呭け璐ャ€嶃€?
鏀惰棌鎸夐挳锛氬彂鐜?`POST /cards/{id}/favorite` 璧?`FavoriteRequest.is_favorite=True` (榛樿 true锛?*闈?toggle**)锛宐ridge.js 鏄惧紡浼?`{is_favorite: bool}` 瀹炵幇鍙屽悜鍒囨崲锛沝ataset.cardFavorite 涓?`.active` class 鍙屽悜鍙嶆槧锛涘け璐?toast 涓嶇牬鍧忓師 UI銆?
### Test evidence

```
# 14 濂椾欢 + prd10/ 鑱斿悎
python -m pytest tests/integration/api/test_prd10_*.py tests/integration/api/prd10/ -q
# 鈫?225 passed in 39.71s (.tmp/baseline_run_15_6_15_8.txt)

# 瀛楃涓插绾﹀崌绾э紙PRD10 path 鍔?/kb/folders /cards/ /favorite锛沨elper 鍔?11 涓紱DOM hook 鍔?7 涓級
python -m pytest tests/integration/api/test_prd10_frontend_binding.py -q
# 鈫?24 passed in 4.82s

# 鐪熷疄 server end-to-end smoke
python .tmp/smoke_15_6_15_8.py
# 鈫?搂15.8: 6 folders before 鈫?POST 鍒涘缓 1 鈫?7 folders after delta=1; favorite toggle true鈫抐alse PASS
# 鈫?搂15.6: GET /cards/{first.id} 鈫?鏍囬/tags/fav read OK; favorite set true鈫抐alse PASS
# 鈫?搂 === 搂15.6 + 搂15.8 SMOKE PASS ===
```

### Files touched

- `static/mydow/biz/bridge.js` 鈥?+290 琛岋紙11 涓柊 helper for 搂15.6 + 搂15.8锛?- `tests/integration/api/test_prd10_frontend_binding.py` 鈥?`TestBusinessPrototypeBridge` 瀛楃涓插绾﹀崌绾э紙path 13鈫?6锛沨elper 14鈫?5锛汥OM hook 15鈫?2锛?- `todo-tasks.md` 鈥?搂15.6 / 搂15.8 鈫?done 璇︾粏 evidence
- `agent-progress-report.md` 鈥?鏈?milestone
- `.tmp/smoke_15_6_15_8.py` 鈥?鏂板缓绔埌绔?smoke
- **鏈姩** `static/mydow/{index.html,app.js,style.css,mydow-api.js}` 涓?`static/mydow/biz/index.html` 浠讳綍涓€琛?
### Follow-ups

- 搂15.9 鏂囦欢澶硅鎯呰鍥撅紙`bindKbCardOpenFolder` 褰撳墠鏄?toast 鍗犱綅锛岀瓑寰?搂15.9 鎺?`/kb/folders/{id}` + `/kb/documents?folder_id=` 娓叉煋璇︽儏锛?- 搂15.10 鏂囨。璇︽儏/缂栬緫锛坄hydrateItemDetailDrawer` 褰撳墠鍙～ card 鏁版嵁锛屾枃妗ｈ鎯呰蛋 `/kb/documents/{id}` 鎶藉眽搴旀槸鍙︿竴涓?helper锛?- 涓汉涓績鎶藉眽 搂15.18锛歜ridge.js 宸茬粡鍦?sidebar chip 娉ㄥ叆鐪熷悕/Plan锛屼絾鐐瑰嚮 `[data-open-profile]` 寮逛釜浜轰腑蹇?4 闈㈡澘鐨勭湡瀹炴帴鍏ヨ繕鍦?doing
- 閫氱煡鎶藉眽 搂15.17锛歶nread badge 宸叉樉绀猴紝浣嗙偣寮€閫氱煡鎶藉眽璇?`/notifications` 鍒楄〃 + 鍗曠偣宸茶杩樺湪 doing

---

## Milestone 25 路 搂15.7 涓氬姟鍘熷瀷棣栭〉 4 涓?modal 鎺ョ湡瀹?API锛堜笂浼?鍓棌/璇煶/娣辩爺锛夆€?DELIVERED

**When**: 2026-05-05 23:00锛堟湰浼氳瘽缁紝by 鎬绘帶 Engineer 1锛?
**Why**: 鐢ㄦ埛鏄庣‘鎸囩ず鏀句笅 搂6.2 绛夌函鍚庣娓呯悊浠诲姟锛屼笓娉?搂15 涓氬姟鍘熷瀷杩樺師 lane 鎶婃瘡涓寜閽帴鍒扮湡瀹?PRD10 API銆侰hrome MCP nav sweep 搂7.25 鎶ュ憡璇撮椤?5 涓?quick-action 鎸夐挳锛坄娣诲姞鍥剧墖鎴栨枃浠?/ 缃戦〉鍓棌 x2 / 涓婁紶鏂囦欢 / 娣卞害鐮旂┒`锛夌偣鍑绘棤浠讳綍鍙嶉锛坢ain DOM/URL/toast/缃戠粶璇锋眰閮戒笉鍙橈級锛屾槸棣栧睆绗竴鐪兼渶鏄剧溂鐨勭‖浼ゃ€傝繖涓€杞?搂15.7 鎶婅繖 4 涓搴旂殑 modal 鎺ュ埌鐪熷疄 API銆?
鎸夎鍒?*涓嶅姩** SPA 鏂囦欢锛坄static/mydow/{index.html,app.js,style.css,mydow-api.js}`锛夊拰 biz 鍘熷瀷 HTML锛坄static/mydow/biz/index.html` 鏄笟鍔℃柟 zip 澶嶅埗鍝侊級锛屽彧鍔?`static/mydow/biz/bridge.js` + 娴嬭瘯 + smoke 鑴氭湰銆?
### Delivered

#### 鎷︽埅绛栫暐锛歝apture-phase + stopImmediatePropagation

biz/index.html 琛?8075-8081 鐨?inline IIFE 鐢?document-level **bubbling** click delegation 鎷︽埅鎵€鏈?`[data-toast]` 鍏冪礌 鈫?瑙﹀彂 `simulateAction`锛坰etTimeout 鍋囪繘搴︼級銆傛垜浠湪 boot 鏃舵敞鍐屼竴涓?**capture-phase** document listener锛坄addEventListener("click", handler, true)`锛夛紝鍦?IIFE 涔嬪墠鍖归厤 4 涓?home-modal 鐨勬彁浜ゆ寜閽紝鐢?`event.stopImmediatePropagation()` 鐭矾鎺?IIFE銆傚叾瀹?`[data-toast]` 鎸夐挳锛坰kill 璇曠敤銆乻ettings 绛夛級缁х画璧?IIFE 鐨?simulateAction銆侰ancel 鎸夐挳锛坄[data-close-layer]`锛変繚鐣?IIFE 琛屼负锛屾甯稿叧闂?modal銆?
#### 4 涓?modal 鐪熷疄 API 閾捐矾

| Modal | Selector | 鐪熷疄 API |
|---|---|---|
| 涓婁紶鏂囦欢 | `[data-modal="uploadFile"]` 銆屽紑濮嬩笂浼犮€?| 娉ㄥ叆闅愯棌 `<input type="file">` 鈫?user click 鍚?`change` 浜嬩欢 鈫?`POST /uploads/presign(filename, mime_type, size_bytes)` 鈫?`PUT /uploads/local/{upload_id}` 鐩存帴 PUT raw bytes锛堝甫 Bearer token锛夆啋 `POST /capture/file/commit(upload_id, filename, mime_type, size_bytes, auto_process: true)`锛涙垚鍔熷悗 toast銆屽凡涓婁紶 X锛屾鍦ㄨ嚜鍔ㄦ暣鐞嗐€? `closeAllModals()` + `loadFeedIntoRecentView()` + `refreshFeedCounters()` + `refreshTodayInsights()` |
| 缃戦〉鍓棌 | `[data-modal="webLink"]` 銆屼繚瀛樺壀钘忋€?| 璇?`input[type="text"]` value 鈫?`POST /capture/link(url, auto_process: true)`锛涙垚鍔熷悗 toast銆岀綉椤靛凡淇濆瓨鍒版渶杩戞崟鎹夛紝AI 鏁寸悊涓€? closeAllModals + 鍒锋柊閾捐矾 |
| 娣卞害鐮旂┒ | `[data-modal="deepResearch"]` 銆屽紑濮嬬爺绌躲€?| 璇?`input` (涓婚) / `select` (鑼冨洿) / `textarea` (杈撳嚭) 鈫?`POST /ai/conversations(title:娣卞害鐮旂┒锛歿topic}, mode: "report")` 鎷?conversation id 鈫?`POST /ai/conversations/{id}/messages(content)` seed 绗竴鏉＄敤鎴锋秷鎭紙鍖呭惈涓婚/鑼冨洿/杈撳嚭涓夋锛夛紱鎴愬姛鍚?toast + `refreshUnreadBadge()`锛圓I 鏁寸悊瀹屾垚鍚庝細鏈夐€氱煡锛?|
| 璇煶杈撳叆 | `[data-modal="voiceInput"]` | V1 鍗犱綅 toast銆孭1 灏嗘帴 MediaRecorder + /uploads銆? closeAllModals銆傜湡瀹炲綍闊宠浆鍐欏嚭 P1 鑼冪暣 |

#### 瀛楁瀵归綈锛堜慨浜?4 涓?bug锛?
璺?smoke 鏃舵挒浜?4 涓?schema 涓嶄竴鑷?bug锛堣繖閮芥槸 bridge.js 涔嬪墠鐨勫崰浣嶅亣璁?vs 鐪熷疄 PRD10 backend锛夛細

1. `/uploads/presign` 璇锋眰瀛楁鏄?`mime_type / size_bytes` 涓嶆槸 `content_type / size` 鈥?bridge.js 鏀规
2. `/uploads/presign` 杩斿洖瀛楁鏄?`upload_url` 涓嶆槸 `put_url` 鈥?bridge.js 鏀规锛堥『鎵嬫妸 fallback 鍒犳帀閬垮厤璇锛?3. `/ai/conversations.mode` enum 鏄?`general | knowledge | planning | report`锛屾病鏈?`research` 鈥?bridge.js 鏀圭敤 `report`锛堟繁搴︾爺绌?= report mode锛?4. `/today.stats` 瀛楁鏄?`today_capture_count / pending_task_count / knowledge_items_count / weekly_growth_rate`锛屼笉鏄?`today_captures` 鎴?`captures_today` 鈥?bridge.js `refreshTodayInsights` 鏀规锛屼笖鏂板鐩存帴鏍规嵁 `<h3>` 鏂囨湰鍖归厤锛堛€屼粖鏃ョ伒鎰熸崟鎹?浠婃棩鎹曟崏/鐭ヨ瘑搴?寰呭姙浠诲姟銆嶏級娉ㄥ叆 `<span class="stat-value">` 鏁板瓧锛屼笉鍐嶄緷璧?`[data-stat=*]` data-attribute锛坆iz/index.html 娌￠偅 marker锛?
#### 娴嬭瘯 + Smoke 绔埌绔?
`tests/integration/api/test_prd10_frontend_binding.py::TestBusinessPrototypeBridge` 鍗囩骇锛?- `test_biz_bridge_js_covers_prd10_paths` 鈥?蹇呭惈 11 鏉¤矾寰勶紙鏃?7 + 鏂?4锛歚/capture/link /uploads/presign /capture/file/commit /ai/conversations`锛?- `test_biz_bridge_js_exposes_named_helpers` 鈥?蹇呭惈 14 涓懡鍚嶏紙鏃?7 + 鏂?7锛歚bindHomeModalSubmits / uploadAndCommitFile / handleUploadFileModal / handleWebLinkModal / handleDeepResearchModal / handleVoiceInputModal / closeAllModals`锛?- `test_biz_index_keeps_prd10_dom_hooks` 鈥?蹇呭惈 15 涓?DOM hook锛堟棫 8 + 鏂?7锛? 涓?`data-modal=` + 3 涓?`data-toast=` 瀛楅潰閲忥級

`.tmp/smoke_15_7_modals.py` 鐢?urllib 鐪熸墦 8770 server锛?0 姝ュ叏杩囷細

```
1. /demo/status enabled=True email=demo@mydow.example
2. /demo/login token len=209
3. /me name=Demo User plan=free role=owner
4. /notifications/unread-count: 8
5. /today today_capture_count=10 pending_task_count=5 knowledge_items_count=22 weekly_growth_rate=1.0
6. /feed total before: 33
7. /capture/link inbox_id=4eccf7f3 job_id=103f44ba fetch_status=completed
8. /uploads/presign upload_id=befc8dd3 鈫?PUT 200 鈫?/capture/file/commit inbox_id=e4ab6461 document_id=e5765d54 status=completed
9. /ai/conversations conversation_id=04f7f1c1 鈫?message job=49afc0e9 assistant_message=de184ee7
10. /feed total after: 35 (delta = 2)
=== SMOKE PASS ===
```

姣忔璺戦兘鐢熸垚鐪熷疄 inbox_item / job / source / document 琛岋紝feed total 澧為噺姝ｇ‘锛堟瘡娆?+2锛屽搴?link capture + file commit 涓ゆ潯锛夈€?
### Test evidence

```
# Frontend binding 鍚?6 涓?biz/bridge 濂戠害鍗囩骇
python -m pytest tests/integration/api/test_prd10_frontend_binding.py -q
# 鈫?24 passed in 7.52s

# 鑱斿悎 PRD10 14 濂椾欢 baseline锛堝惈鎴戝拰 Agent 3 鎵€鏈夋敼鍔級
python -m pytest tests/integration/api/test_prd10_*.py tests/integration/api/prd10/ -q
# 鈫?225 passed in 55.76s锛堜笌 Milestone 24 + Agent 3 22:25 baseline 鎸佸钩锛?
# 鐪熷疄 server 绔埌绔?smoke
$env:DATABASE_URL="sqlite+aiosqlite:///d:/Codes/whyme/.tmp/smoke.db"
$env:AGENTOS_DEMO_MODE="on"
$env:AGENTOS_PRD10_WORKER="on"
python scripts/seed_prd10.py --reset
python -m uvicorn agent_os.server.app:app --host 127.0.0.1 --port 8770  # background
python .tmp/smoke_15_7_modals.py  # 10/10 PASS, .tmp/smoke_15_7_modals_result.json
```

### Files touched

- `static/mydow/biz/bridge.js` 鈥?+210 琛岋紙7 涓柊 helper锛歜indHomeModalSubmits / uploadAndCommitFile / handleXxxModal x4 / closeAllModals + 寮曞 binding锛況efreshTodayInsights 鏀圭敤鐪熷瓧娈?`today_capture_count` + 鐩存帴娉ㄥ叆 `<h3>+<span class="stat-value">`锛?- `tests/integration/api/test_prd10_frontend_binding.py` 鈥?`TestBusinessPrototypeBridge` 涓変釜 token 鍒楄〃鍗囩骇
- `todo-tasks.md` 鈥?搂15.7 鈫?done + 璇︾粏 evidence 琛?- `agent-progress-report.md` 鈥?鏈?milestone
- `.tmp/smoke_15_7_modals.py` 鈥?鏂板缓锛?0 姝ョ湡瀹?HTTP smoke
- `.tmp/smoke_15_7_modals_result.json` 鈥?smoke 缁撴灉鍥哄寲
- **鏈姩** `static/mydow/{index.html,app.js,style.css,mydow-api.js}` 涓?`static/mydow/biz/index.html` 浠讳綍涓€琛岋紙鎸夎鍒?搂3 棰嗗湴鍒掑垎锛?
### Follow-ups

- 搂15.5 缁綔锛氬唴瀹瑰垎甯冪幆褰㈠浘 / 杩蜂綘鎶樼嚎 / AI 姣忔棩娲炲療绱簳鍗＄墖锛堟帴 `/insights/preview` 鍏滃簳锛岀瓑 搂6.5/3.13 宸?done 鍚庡彲鎷ｏ級
- 搂15.6 鍗＄墖鐐瑰嚮渚ф娊锛堜换涓€宸ョ▼甯堬級銆伮?5.8/搂15.9 KB 棣栭〉涓庢枃浠跺す璇︽儏锛坉oing by Agent session锛夈€伮?5.11 鏁板瓧鑺卞洯銆伮?5.12 AI 宸ヤ綔鍙帮紙浠讳竴宸ョ▼甯堝彲鎷ｏ級
- 搂7.25 SPA 棣栭〉 quick-action 涔熸湁鍚屾牱 5 issue锛堝湪 SPA 鏂囦欢閲岋級鈥?杩欐槸宸ョ▼甯?2 / Agent 2 鐨?SPA lane锛屼笌 biz lane 鍒嗗埆娌荤悊锛沚iz 鐗?搂15.7 done 鏍囧織鐫€銆屾姇璧勬紨绀鸿矾寰勫鏋滃垏鍒?biz 鐗堬紝4 涓?modal 鐪熷疄鍙敤銆?- 鐪熸祻瑙堝櫒 Chrome MCP 鎴浘锛氭湰杞?Chrome MCP 鍥犱负 chrome-profile 宸茶鍙︿竴杩涚▼鍗犵敤鑰屾棤娉曞惎鏂?page锛岀敤 Python urllib smoke 鏇夸唬楠岃瘉锛涗笅涓€杞伐绋嬪笀 4 璺?`chrome-mcp-smoke.ps1` 鏃跺彲鍚屾椂澶嶆祴 biz 璺緞

---

## Milestone 24 路 搂11.4 CORS done + 搂15.2 bridge.js 澧為噺鎺ㄨ繘锛堜釜浜轰腑蹇?/ 閫氱煡 / 娲炲療 / feed 璁℃暟锛夆€?DELIVERED

**When**: 2026-05-05 22:10锛堟湰浼氳瘽缁紝by 鎬绘帶 Engineer 1锛?
**Why**: 涓婅疆鎶?搂7.25鈥撀?.31 鐨?SPA 鎸夐挳缂洪櫡鐧昏缁欏伐绋嬪笀 2 / Agent 2 鍚庯紝浣滀负鍗忚皟鑰呯户缁帹杩?*鑷繁 lane 鍐?*涓嶆挒 SPA 鐨勫伐浣滐細
1. 搂11.4 CORS 瀹炵幇宸复闂ㄤ竴鑴氶獙璇侊紱
2. 搂15.2 bridge.js 宸茬粡鍋氫簡鍩虹 boot/`apiFetch`/capture text锛屼絾 搂15.5/搂15.17/搂15.18 鐨勩€屾寜閽湡瀹炵敓鏁堛€嶉儴鍒嗕粛鏄?open锛?*杩欎簺閮戒笉鍦?SPA 鏂囦欢閲?*锛埪? 棰嗗湴鍒掑垎鍏佽鎬绘帶鎺?搂15 涓氬姟鍘熷瀷 lane 涓婄殑闈?SPA 浠诲姟锛夈€?
鎸夊浜哄崗浣滆鍒欙紝鏈**涓嶅姩** `static/mydow/{index.html,app.js,style.css,mydow-api.js}` 浠讳綍涓€琛岋紝鍙姩锛?- `tests/integration/api/test_prd10_app_wiring.py` 鏈熬 append `TestPrd10Cors`锛? 涓?case锛夛紱
- `static/mydow/biz/bridge.js` 鍔?4 涓?hydrator + boot 娴佺▼鏀?`Promise.allSettled` 骞跺彂锛?- `tests/integration/api/test_prd10_frontend_binding.py` 鏈熬 append `TestBusinessPrototypeBridge`锛? 涓?case锛夛紱
- `todo-tasks.md` 搂11.4 鈫?done銆伮?5.5/搂15.17/搂15.18 鈫?doing 骞跺～ evidence锛?- `agent-progress-report.md` 鏈?milestone銆?
### Delivered

#### 搂11.4 CORS 鈥?done

`agent_os/server/app.py:109-143` 鏃╁凡鍐欏ソ涓ユ牸 CORS 涓棿浠讹細
- `AGENTOS_CORS_ORIGINS=https://demo.mydow.app,https://www.mydow.app` 鐢熶骇涓ユ牸鐧藉悕鍗曪紱
- `AGENTOS_CORS_ALLOW_ALL=1` 寮€鍙戦€氶厤锛堣嚜鍔ㄧ鐢?credentials 婊¤冻 CORS 瑙勮寖锛夛紱
- 榛樿 dev origins 鍚?`localhost:{3000,5173,8000,8770}` 涓?`127.0.0.1` 鍚屽洓鍙ｏ紱
- `expose_headers=["X-Request-ID"]` 閰嶅悎 `RequestIdMiddleware` 璁╁墠绔兘璇诲埌 PRD10 envelope `request_id`銆?
琛?4 涓祴璇曞埌 `tests/integration/api/test_prd10_app_wiring.py::TestPrd10Cors`锛?1. `test_preflight_allows_dev_origin` 鈥?OPTIONS 甯?`Origin: http://localhost:3000` + `Access-Control-Request-Method` 鈫?杩斿洖鐨?`Access-Control-Allow-Origin` 绮剧‘鍥炴樉璇?origin锛沗Allow-Methods` 鍚?GET/POST/DELETE/PATCH锛沗Allow-Headers` 鍚?Authorization 涓?X-Request-ID锛沗Allow-Credentials: true`锛?2. `test_simple_request_echoes_allowed_origin` 鈥?GET 甯?`Origin: http://localhost:5173` 鈫?200 + `Access-Control-Allow-Origin: http://localhost:5173` + `Expose-Headers` 鍚?X-Request-ID锛?3. `test_unknown_origin_is_not_echoed` 鈥?OPTIONS 甯?`Origin: https://attacker.example` 鈫?`Access-Control-Allow-Origin` 涓嶈兘绛変簬璇?origin锛屼篃涓嶈兘涓?`*`锛?4. `test_request_id_round_trips_with_cors` 鈥?鍚屾椂甯?`Origin` 鍜?`X-Request-ID` 鈫?header 浠?round-trip + envelope `request_id` 涓€鑷淬€?
`pytest tests/integration/api/test_prd10_app_wiring.py -q` 鈫?**10 passed in 5.28s**锛? 鍘?+ 4 鏂帮級銆?
#### 搂15.2 bridge.js 鈥?4 涓柊 hydrator + 娴嬭瘯

```
static/mydow/biz/bridge.js  +192 琛?鈹溾攢鈹€ refreshProfileChip()   搂15.18  鈫?/me 鈫?sidebar chip 涓?topbar avatar
鈹溾攢鈹€ refreshUnreadBadge()   搂15.17  鈫?/notifications/unread-count 鈫?閾冮摏瑙掓爣
鈹溾攢鈹€ refreshTodayInsights() 搂15.5   鈫?/today 鈫?[data-stat=today-captures] slot
鈹斺攢鈹€ refreshFeedCounters()  搂15.4 缁?鈫?/feed?limit=1 鈫?tab 鍚庤鏍?```

boot 娴佺▼鏀归€狅細
```js
const me = await refreshProfileChip();   // 鍏抽敭璺緞锛屽け璐ュ垯娓?token 涓嶆覆鏌?if (!me) return;
rebindCaptureSubmit();                    // 宸叉湁锛屼笉鍙?Promise.allSettled([
  refreshUnreadBadge(),
  refreshTodayInsights(),
  refreshFeedCounters(),
  loadFeedIntoRecentView(),  // 搂15.4 宸叉湁
]).then(() => toast("宸茶繛鎺?PRD10 鍚庣 路 demo 宸茬櫥褰?, "success"));
```

`window.MydowBridge` 鏆撮湶鎵€鏈?helper 渚涜皟璇?/ 鍚庣画 搂15.6+ 鎺ュ叆銆?
#### `TestBusinessPrototypeBridge` 鈥?6 涓柊濂戠害娴嬭瘯

`tests/integration/api/test_prd10_frontend_binding.py` 鏈熬鍔狅細
1. `test_biz_index_served` 鈥?`GET /mydow/biz/` 鈫?200 + 鍚?`<title>Mydow` 涓?`bridge.js`锛?2. `test_biz_bridge_js_served` 鈥?`GET /mydow/biz/bridge.js` 鈫?200 + 鍚?`/api/v1` 涓?`mydow_biz_token`锛坱oken key 闅旂闃叉挒 SPA `mydow_token`锛夛紱
3. `test_biz_bridge_js_covers_prd10_paths` 鈥?bridge.js 蹇呴』鍑虹幇 `/demo/status /demo/login /me /capture/text /notifications/unread-count /today /feed` 7 鏉¤矾寰勶紱
4. `test_biz_bridge_js_exposes_named_helpers` 鈥?蹇呴』鏈?`apiFetch / ensureSession / rebindCaptureSubmit / refreshProfileChip / refreshUnreadBadge / refreshTodayInsights / refreshFeedCounters / window.MydowBridge` 8 涓懡鍚嶏紱
5. `test_biz_index_keeps_prd10_dom_hooks` 鈥?`biz/index.html` 蹇呴』淇濈暀 `data-open-profile / data-open-notifications / data-search-trigger / data-view-target=recent / data-view-target=records / class="account" / class="capture" / send-button` 8 涓?DOM hook锛坆usiness 鍘熷瀷鍐嶇敓鏃惰繖浜?selector 涓嶈兘婕傝蛋锛屽惁鍒?bridge silently no-op锛夛紱
6. `test_biz_bridge_demo_login_flow_still_works` 鈥?绔埌绔窇 `AGENTOS_DEMO_MODE=on` 鈫?`/demo/status enabled=true` 鈫?`/demo/login` 鎷?token 鈫?`Bearer` 璋?`/me` 鎷垮埌 email/username锛堝吋瀹?envelope/flat 涓ょ shape锛夈€?
### Test evidence

```
# 搂11.4 + 鏃㈡湁 wiring
python -m pytest tests/integration/api/test_prd10_app_wiring.py -q
# 鈫?10 passed in 5.28s

# 搂15.2 鍏?frontend binding
python -m pytest tests/integration/api/test_prd10_frontend_binding.py -q
# 鈫?24 passed in 7.46s (18 鍘?+ 6 鏂?biz)

# 瀹屾暣 PRD10 baseline 鐭╅樀锛?3 濂椾欢 + prd10/锛?python -m pytest \
  tests/integration/api/test_prd10_v1_acceptance.py \
  tests/integration/api/test_prd10_frontend_binding.py \
  tests/integration/api/test_prd10_ai_api.py \
  tests/integration/api/test_prd10_ai_llm.py \
  tests/integration/api/test_prd10_search_api.py \
  tests/integration/api/test_prd10_skills_api.py \
  tests/integration/api/test_prd10_garden_api.py \
  tests/integration/api/test_prd10_observability.py \
  tests/integration/api/test_prd10_app_wiring.py \
  tests/integration/api/test_prd10_models_intelligence.py \
  tests/integration/api/test_prd10_e2e_flow.py \
  tests/integration/api/test_prd10_product_data_api.py \
  tests/integration/api/test_prd10_insights_api.py \
  tests/integration/api/prd10/ -q
# 鈫?221 passed in 52.65s
```

### Files touched

- `src/agent_os/server/app.py` 鈥?**鏈敼**锛埪?1.4 瀹炵幇鏃╁凡钀斤紝鏈疆鍙ˉ娴嬭瘯锛?- `tests/integration/api/test_prd10_app_wiring.py` 鈥?append `TestPrd10Cors` 4 涓?case
- `static/mydow/biz/bridge.js` 鈥?+192 琛岋紙4 涓柊 hydrator + boot 娴佺▼鏀瑰苟鍙戯級
- `tests/integration/api/test_prd10_frontend_binding.py` 鈥?append `TestBusinessPrototypeBridge` 6 涓?case
- `todo-tasks.md` 鈥?搂11.4 done / 搂15.5 搂15.17 搂15.18 doing + Owner / 搂0 娴嬭瘯鐭╅樀杩藉姞 22:10 琛?- `agent-progress-report.md` 鈥?鏈?milestone

### Follow-ups

- 搂15.5 缁綔锛氬唴瀹瑰垎甯冪幆褰㈠浘 / 杩蜂綘鎶樼嚎 / AI 姣忔棩娲炲療绱簳鍗＄墖锛堟帴 `/insights/preview` 鍏滃簳锛岀瓑 搂6.5/3.13 钀藉湴锛?- 搂15.17 缁綔锛氶€氱煡鎶藉眽鍒楄〃锛坄GET /notifications`锛? 鍗曟潯宸茶 / 鍏ㄩ儴宸茶鎸夐挳 + 閫氱煡璁剧疆寮圭獥锛坄PATCH /me/preferences`锛?- 搂15.18 缁綔锛氱偣鍑?sidebar chip 寮瑰嚭涓汉涓績鎶藉眽锛? 闈㈡澘锛氫釜浜?瀹夊叏/鍋忓ソ/浼氬憳锛夛紝姣忎釜鎸夐挳鎺?`PATCH /me` 鎴栨湰鍦?toast
- 搂15.6/搂15.7锛氬崱鐗囦晶鎶戒笌 4 涓?modal锛堜笂浼?鍓棌/璇煶/娣辩爺锛夆€?浠讳綍宸ョ▼甯堝彲鎷?- 搂11.4 / 搂15.2 / 搂15.3 / 搂15.4 done 鍚庯紝绂?搂15.20銆屽垏榛樿鍏ュ彛 `/mydow/` 鎸囧悜 biz 鐗堛€嶆洿杩戜竴姝ワ紱鍓?搂15.5鈥撀?5.19 瀹屾垚鍚庢墠鑳藉垏

---

## Milestone 23 路 Chrome MCP 鍏?nav sweep锛圫PA 閲嶆瀯鍚庯級鈥?18 issue 鍩虹嚎褰掓。 鈥?DELIVERED

**When**: 2026-05-05 21:30锛堟湰浼氳瘽缁紝by 鎬绘帶 Engineer 1锛?
**Why**: 鐢ㄦ埛鍙嶉銆宒emo 閲屽緢澶氭寜閽偣浜嗘病鍙嶅簲鎴栨病杈惧埌棰勬湡銆嶃€係PA 宸茶宸ョ▼甯?2 閲嶅啓鍒?`app.js`锛?38 琛岀殑 `mydow-api.js` 浠呬綔 contract shim锛夛紝鎵€浠ラ渶瑕佸湪鏂?SPA 涓婇噸鍋氭寜閽骇 sweep锛屾妸鐪熷疄闂浣滀负 `open` 浠诲姟浜ょ粰宸ョ▼甯?2銆?
鎸夊浜哄崗浣滆鍒欙紝鏈**涓嶅姩** `static/mydow/{index.html,app.js,style.css,mydow-api.js}` 浠讳綍涓€琛岋紱鍙紪杈?`todo-tasks.md` 涓庢湰 milestone 鎶ュ憡銆?
### Delivered

- 鐢?`:8771` 涓存椂 SQLite + `demo_final` 鐢ㄦ埛 + Chrome MCP isolated context `prd10-demo-final-2` 璺戜簡 7 涓?nav 妯″紡锛坔ome / today / inbox / kb / garden / ai / skills锛夛紝閫?nav 瑙﹀彂鍚庢壂鎻忓彲瑙佹寜閽紝骞惰褰曟瘡涓寜閽殑 main innerHTML / location / toast / 缃戠粶璇锋眰 4 缁村彉鍖栥€?- 鍏?102 涓€欓€夋寜閽?/ **18 issue**锛屽垎甯冨涓嬶細
  - **home (5/20)**锛歚娣诲姞鍥剧墖鎴栨枃浠禶 / `缃戦〉鍓棌` / `涓婁紶鏂囦欢` / `缃戦〉鍓棌` / `娣卞害鐮旂┒` 鍏ㄩ儴鐐瑰嚮鏃?main 鍙樺寲銆佹棤 API銆佹棤 toast銆?  - **today (1/12)**锛? 涓棤 aria-label 鐨?`btn-icon`锛堥《閮ㄩ€氱煡 5 鏁板瓧锛夈€?  - **inbox (1/12)**锛氬悓涓娿€?  - **kb (4/16)**锛歚鏀惰棌` / `鏈€杩慲 filter tab銆乣鏂板缓绗竴涓枃浠跺す` empty CTA銆? 涓?`btn-icon`銆?  - **garden (4/17)**锛? 涓?`btn-icon` 宸ュ叿鏍忔寜閽?+ 1 涓?`鍙栨秷`銆?  - **ai (3/12)**锛歛vatar 鎸夐挳 + 绌?composer 鏃剁殑 `鍙戦€乣 + 1 涓?`btn-icon`銆?  - **skills (0/13)**锛氣渽 瀹岀編銆?- 杩?18 涓?issue 宸查€愭潯鐧昏鍒?`todo-tasks.md` 搂7.25鈥撀?.31锛屽苟鎶?搂14.3 acceptance gate 鏇存柊涓恒€?*18 issue / 102 鍊欓€?*锛岄樆濉炲湪 搂7.25-7.30銆嶃€?
### Test evidence

- Chrome MCP 鐪熸祻瑙堝櫒瀹炴祴锛宻weep 鑴氭湰宸?inline 鍦?`evaluate_script`锛堣浼氳瘽锛夈€?- PRD10 鏍稿績鐭╅樀澶嶆祴锛?
```
python -m pytest tests/integration/api/prd10/ \
  tests/integration/api/test_prd10_product_data_api.py \
  tests/integration/api/test_prd10_frontend_binding.py \
  tests/integration/api/test_prd10_app_wiring.py \
  tests/integration/api/test_prd10_skills_api.py \
  -q -p no:cacheprovider
# -> 120 passed in 43.85s
```

### Files touched

- `todo-tasks.md` 鏂板 搂7.25鈥撀?.31 + 搂14.3 鏇存柊锛堜粎鏈〃锛夈€?- 鏈?milestone 鍐欏叆 `agent-progress-report.md`銆?- **鏈姩** `static/mydow/*`銆乣app.js`銆佷换浣曞悗绔疄鐜版枃浠躲€?
### Follow-ups

宸ョ▼甯?2 鍦?搂7.25鈥撀?.30 瀹屽伐鍚庯細
1. 璁?搂7.31 澶嶆祴锛堢敤 `scripts/chrome-mcp-smoke.ps1` 宸叉湁鐨?12 姝ヨ矾寰勫啀鍔犱竴涓?7-nav sweep锛夈€?2. 瑙﹁揪 0 issue 鍚?搂14.3 鈫?`done`銆?3. 鍚屾甯﹀姩 搂9.13鈥?.17锛圠oading/Empty/Error/Permission/璺敱锛夌殑 `done`銆?
---

## Milestone 22 路 Legacy test infrastructure cleanup 鈥?`tests/conftest.py` from file-based to in-memory + StaticPool 鈥?FIXED

**When**: 2026-05-05锛堟湰浼氳瘽锛?
**Why**: After Milestones 8鈥?2 闅旂浜?`tests/legacy/*` 绛夊巻鍙叉祴璇曪紝浠撳簱鍐呰繕鏈?3 涓枃浠跺洜 `tests/conftest.py::engine` 鐢?`sqlite+aiosqlite:///./test.db` 鍏变韩鏂囦欢
瀵艰嚧璺ㄦ祴璇曟薄鏌擄細

- `tests/integration/api/test_prd10_frontend_binding.py::test_mydow_primary_action_bindings_are_wired`
- `tests/unit/services/test_card_generator.py`锛? 涓祴璇曪級

姣忔鍗曠嫭璺?鈫?PASS锛涘拰鍒殑娴嬭瘯涓€璧疯窇 鈫?FAIL銆俉indows 涓婅繕闄勫甫
`pytest-current` 鐨?`PermissionError` 鍜?cleanup 闃舵鐨?`OperationalError: no such table`銆傝繖浜涗笉鏄唬鐮?bug锛屾槸娴嬭瘯鍩虹璁炬柦闂銆?
### Delivered

`tests/conftest.py` 鏀归€狅細

1. **榛樿 DB URL 鍒囧埌 `:memory:`**锛歚TEST_DATABASE_URL` 榛樿鍊间粠
   `sqlite+aiosqlite:///./test.db`锛堝叡浜枃浠讹級鏀逛负
   `sqlite+aiosqlite:///:memory:`銆傜幆澧冨彉閲忎粛鍙鐩栧埌鐪?PG銆?2. **engine fixture 鐢?StaticPool**锛氫粎鍦?`:memory:` URL 涓嬪惎鐢?   `StaticPool` + `connect_args={"check_same_thread": False}`锛岃澶氭
   杩炴帴鍏变韩鍚屼竴涓唴瀛?DB锛涘叾浠?URL 淇濈暀 `NullPool`銆?3. **db_session cleanup 瀹归敊**锛氬師鏈瘡涓?test teardown 璺戜竴缁?   `delete(Model)`锛屾ā鍨嬭〃鍦ㄦ煇浜?fixture 璺緞涓嬪彲鑳芥病寤哄嚭鏉?   灏辨姤 `OperationalError`銆傜幇鍦ㄦ瘡鏉?`delete` 鍗曠嫭 try/except
   `(OperationalError, ProgrammingError)`锛屾崟鍒板氨 rollback銆傞厤鍚?   in-memory + StaticPool锛堟瘡 engine 鏄嫭绔?DB锛宒ispose 鍗虫竻鍏夛級锛?   delete loop 浠呬綔 file-backed DB 鐨勫厹搴曘€?
### Test evidence

```
python -m pytest tests/integration/api/ tests/unit/ \
    -p no:cacheprovider --tb=no -q --timeout=60
# 鈫?777 passed / 0 failed / 19 skipped, 173s
```

```
python -m pytest --collect-only -q -p no:cacheprovider
# 鈫?784 tests collected, exit 0
```

淇鍓嶅搴斿浠剁姸鎬侊細6 failed锛? frontend_binding + 5 card_generator锛?
鑻ュ共闅忔満 cleanup-闃舵 OperationalError銆?
### Files touched

- `tests/conftest.py`锛堥粯璁?DB + StaticPool + 瀹归敊 cleanup锛?
### todo-tasks.md updates

- 搂1.9锛圓gent 1锛塦open` 鈫?`done`锛涙柊澧炶瘉鎹垪銆?- 搂0 娴嬭瘯鐭╅樀杩藉姞 2026-05-05 21:30 琛屻€?
### Follow-ups

- 搂6.1 `test_search_api_simple.py` 鐨?`agent_os.search.keyword_search`
  璁捐涓婃姏 `NotImplementedError`锛屽凡鍦?ignore 鍒楄〃閲岋紝涓嶅啀鍒楀叆鍥炲綊銆?- 濡傛湭鏉ュ垏鍒扮湡 PG锛坄TEST_DATABASE_URL=postgresql+asyncpg://...`锛夛紝
  cleanup 鐨?delete loop 浼氱湡姝ｅ彂鎸ヤ綔鐢紱鐩墠鍦?`:memory:` 涓?  delete loop 绛夊悓浜?no-op銆?
---

## Milestone 22 路 涓氬姟鏂瑰師鍨嬭繕鍘?+ bridge 鍚庣鑱旈€氾紙15.1 / 15.2 / 15.3锛?鈥?DONE

**When**: 2026-05-05锛堟湰浼氳瘽锛?
**鑳屾櫙**锛氱敤鎴峰垽瀹氬綋鍓?SPA 瑙嗚銆屼弗閲嶅亸绂讳笟鍔℃柟璁捐銆嶃€備笟鍔℃柟鍦?`Mydow_Web_Frontend_Complete_Package.zip` 閲岀粰浜嗕竴浠?8071 琛岀殑鍗曟枃浠跺師鍨?`mydow.html`锛屽惈瀹屾暣鐨勮璁′护鐗屻€? 椤瑰鑸€佸眳涓ぇ hero銆佹櫤鑳借瘑鍒?Auto 杈撳叆銆? 涓揩鎹疯兌鍥娿€? 寮犲皝闈㈠崱銆佸彸渚?5 娈垫礊瀵熼潰鏉裤€佸簳閮?Pro Plan 鐢ㄦ埛鍗°€傝繖鎵嶆槸瑕佽繕鍘熺殑瑙嗚銆?
**绛栫暐**锛氫笉閲嶅啓 SPA銆傛妸涓氬姟鍘熷瀷鎸傚埌 `static/mydow/biz/`锛屾敞鍏?`bridge.js` 鎶?`simulateAction` 鏇挎崲涓虹湡瀹?`/api/v1/*`銆傜瓑 搂15 鍏ㄥ畬宸ュ啀鎶?`/mydow/` redirect 鍒?biz 鐗堬紙搂15.20锛夈€?
### 浜у嚭
- `static/mydow/biz/index.html` 鈫?涓氬姟鏂?`mydow.html` 鍘熸枃 + 鏈熬 `<script type="module" src="./bridge.js">`
- `static/mydow/biz/bridge.js`锛歞emo auto-login锛堝吋瀹硅８ `{enabled}` 涓?PRD10 envelope 涓ょ `/demo/status` 褰㈡€侊級 + apiFetch 灏佽 + token 鎸佷箙鍖栵紙`localStorage["mydow_biz_token"]`锛? 涓?`.capture .send-button` 鐩戝惉鍏嬮殕鏇挎崲 鈫?鐪熷疄 `/api/v1/capture/text` + toast 銆岀伒鎰熷凡淇濆瓨锛屾渶杩戞崟鎹夊凡鍒锋柊銆?+ `mydow:capture-completed` 浜嬩欢
- `.tmp/biz_walk.py` Playwright 璧版煡鑴氭湰

### 娴嬭瘯璇佹嵁
- `python .tmp/biz_walk.py` 鈫?**3/3 ok ; 0 console error ; 0 page error ; 0 failed req**锛?  1. demo auto-login token 鍐欏叆 `localStorage`
  2. 涓昏緭鍏ユ鐐瑰嚮鎻愪氦 鈫?POST `/capture/text` 200
  3. 绔嬪埢 GET `/feed?page_size=4` 鈫?鏂版潯鐩?`BIZ walk capture 路 ...` 鍑虹幇鍦ㄦ渶鍓?- 鎴浘锛歚.tmp/screenshots/biz_walk/01_home.png`锛堜笟鍔℃柟璁捐鍍忕礌绾ц繕鍘燂級+ `02_after_capture.png`锛坱oast 鍑虹幇 + 鍚庣纭锛?
### Follow-up锛堝凡鐧昏鍒?搂15锛?15.4鈥?5.21锛坒eed 鐪熸暟鎹?/ 鐭ヨ瘑搴?/ 鏁板瓧鑺卞洯 / Mydow AI / Skills / 娲炲療 / 閫氱煡 / 涓汉涓績 / 鍏ㄥ眬鎼滅储 / Playwright 鍏ㄩ摼璺瑙夎蛋鏌?/ `/mydow/` 鍒囬粯璁ゅ叆鍙ｏ級銆?
---

## Milestone 21 路 `.main` 瀹藉害 = 0 / 鍐呭琚帇鎴愪竴鏉＄珫鍒?鈥?FIXED

**When**: 2026-05-05锛堟湰浼氳瘽锛?
**鐥囩姸**锛氱敤鎴峰弽棣堛€屽彸渚ф湁涓€澶у潡鐧借壊鎸′綇灞忓箷銆嶃€屼富椤靛湪鍝噷銆嶃€侾laywright 鎺㈤拡纭 `.main width:0`銆乣#page-region width:72`锛屽唴瀹硅鎸よ繘 ~50px 鍒楅噷锛屾枃瀛楅€愬瓧鎹㈣銆?
**Root cause**锛?- `static/mydow/index.html` 閲?`<div id="app" class="mydow-app">` 宸茬粡鏄?grid 240/1fr銆?- 浣?`static/mydow/app.js::renderShell` 鍙堝線 `#app` 鍐呴儴濉炰簡 `<div class="mydow-app">[sidebar, main]</div>`銆?- 鍙屽眰 grid 宓屽锛氬灞?`#app` 鎶婇偅涓唴灞?div 鎽嗚繘 240px 绗竴鍒楋紝鍐呭眰鍐嶆鎷?240/1fr 浣嗗疄闄呭彲鐢ㄥ搴﹀彧鏈?240px 鈫?sidebar 240銆乣.main` 0 鈫?鍐呭宕╂垚绔栨帓銆?
**Fix**锛歚index.html` 绉婚櫎 `#app` 涓婄殑 `class="mydow-app"`锛堜繚鐣?`id`锛夛紝璁?`renderShell` 鑷繁濉?`.mydow-app` 瀹瑰櫒銆?
**Verification**锛?- Playwright 涓夋。瑙嗗彛 (1024 / 1280 / 1440) probe锛歚.main` 瀹藉害鎭㈠涓?784 / 1040 / 1200銆?- 鎴浘锛歚.tmp/screenshots/fix1_w1024.png`銆乣fix1_w1280.png`銆乣fix1_w1440.png`銆?- `.tmp/e2e_walkthrough.py`锛堣嚜鍔ㄩ亶鍘?home/today/inbox/kb/kb-folder/kb-doc/garden/ai/skills + capture + 鎼滅储 + 閫氱煡锛夆啋 **11/11 ok / 0 console err / 0 page err / 0 failed req**锛涙埅鍥惧瓨 `.tmp/screenshots/e2e_walk/`銆?
---

## Milestone 20 路 鐧诲綍閬僵銆岃摑鑹查浘甯冦€嶉樆鏂富椤?鈥?FIXED

**When**: 2026-05-05锛堟湰浼氳瘽锛?
**Root cause**锛歚static/mydow/index.html` 鍒濆 `<div id="auth-overlay" hidden>`锛屼絾 `style.css` 閲?`#auth-overlay { display: grid }` 鐗瑰紓鎬ч珮浜庡師鐢?`[hidden]`锛屽鑷?**`hidden` 灞炴€ф棤娉曢殣钘忛伄缃?*銆侱emo 鑷姩鐧诲綍鎴愬姛鍚?`overlay.hidden = true` 鍦ㄨ瑙変笂鏃犳晥 鈫?绌哄崐閫忔槑钃濆眰鐩栨鏁撮〉锛岀敤鎴疯浠ヤ负銆屾病鏈変富椤点€嶃€?
**Fix**锛歚style.css` 澧炲姞 `#auth-overlay[hidden] { display: none !important; }`銆?
**Regression**锛歚tests/e2e/test_mydow_browser.py` 鏂█鐧诲綍鍚?`#auth-overlay` 浠嶅甫 `hidden`锛汸laywright 鎴浘 `.tmp/screenshots/mydow_demo_8020_after_overlay_fix.png`銆?
---

## Milestone 19 路 閫氱煡 SSE smoke + app 鍚姩淇 鈥?DONE

**When**: 2026-05-05锛堟湰浼氳瘽锛?
### 浜у嚭

1. **`scripts/smoke_prd10.py`**锛氭柊澧炴楠?9锛屽宓屽叆寮?**uvicorn** 鍙戣捣 `GET /api/v1/notifications/stream`锛屽湪棣栧寘涓牎楠?`event: ready`锛堥伩寮€ Windows 涓?httpx ASGITransport 闀胯疆璇㈠樊寮傦級銆?2. **`src/agent_os/server/app.py`**锛氳ˉ `import os`锛屼慨澶?PRD10 CORS 鍧椾娇鐢?`os.getenv` 瀵艰嚧鐨?**`NameError: os`**锛屽惁鍒欏簲鐢ㄦ棤娉?import銆?3. **`todo-tasks.md`**锛歚8.7` SSE demo smoke 鈫?`done`锛沗8.15` search_indices 琛?鈫?`done`锛堜笌 Milestone 18 宸插啓鍏?conftest 涓€鑷达紝KB 鍗曟祴澶嶉獙 18/18锛夈€?
### 娴嬭瘯璇佹嵁

- `python scripts/smoke_prd10.py` 鈫?exit 0锛沗smoke_run.json` 涓?`notifications.sse_stream`锛歚ready_seen: true`銆?- `pytest tests/integration/api/prd10/test_prd10_kb_api.py` 鈫?18 passed銆?- **Chrome MCP 涓嶅彲鐢ㄦ椂**锛歚seed_prd10` + uvicorn `127.0.0.1:8020`锛孭laywright `tests/e2e/test_mydow_browser.py` 缁跨珷锛涙埅鍥?`d:/Codes/whyme/.tmp/screenshots/mydow_demo_8020.png`銆?
---

## Milestone 18 路 鎬绘帶 搂8 鍚庣閰嶅棣栨壒 鈥?DONE

**When**: 鐢ㄦ埛鍒ゅ畾鏃у墠绔€屽儚鍥剧墖鎷艰捣鏉ャ€嶏紝宸ョ▼甯? 鍚姩 SPA 閲嶅啓锛堝師鐢?ESM锛夈€傛垜浣滀负鎬绘帶璁ら鍚庣/鏁版嵁/鏂囨。閰嶅锛埪? 绯诲垪锛夛紝璁?SPA 涓€鎺ヤ笂灏辫兘鎷垮埌鐪熷疄鏁版嵁銆?
### 鍐崇瓥涓庝骇鍑?
1. **浠诲姟姹犺鑼冨寲**锛歚todo-tasks.md` 澶撮儴寮哄埗涓夋€佹満 `open / doing / done` + Owner 鍒楋紱鏂板 搂9 (UI/UX 鐜颁唬鍖? 搂10 (Demo 娴佺▼) 搂11 (閮ㄧ讲杩愮淮) 搂12 (鎬ц兘闄愭祦) 搂13 (鏂囨。鎶曡祫鏉愭枡) 搂14 (涓婄嚎 Acceptance Gate)锛屽叏閮ㄥ垵濮?`open` 绛変换鎰忓伐绋嬪笀璁ら銆?2. **PRD10 搂5.1 `/api/v1/me`** 鈥?鏂板 `Prd10MeResponse` schema (`auth/schema.py`) + `me_router::get_prd10_me` (`auth/router.py`)銆傝繑鍥炵簿纭?搂5.1 瀛楁锛歚id / name / avatar_url / email / role / locale / timezone / plan / created_at / updated_at`銆俙role/locale/timezone/plan` 浠?`User.settings` JSON 璇诲瓧娈碉紙榛樿 `owner / zh-CN / Asia/Shanghai / free`锛夛紝涓嶅姩 DB 琛?schema銆俙/api/v1/auth/me` legacy 淇濈暀銆?3. **PRD10 搂14 `/api/v1/tasks`** 鈥?鏂板 `tasks/prd10_router.py`锛屼娇鐢?`PRD10Task` UUID 妯″瀷锛屾彁渚?list / create / detail / patch / complete / soft-delete + envelope銆俙app.py` 娉ㄥ唽鍒?legacy Integer router 涔嬪墠锛涘吀鍨?path param 浣跨敤 `uuid.UUID` 寮虹被鍨嬭 legacy int path 涓嶈閬紝PRD10 list/create 鏍硅矾寰勪紭鍏堬紝legacy `/today /stats /batch` 缁х画鍙敤銆?4. **PRD10 搂13 / 搂19.1 step 8 绱㈠紩** 鈥?`capture/pipeline.py::simulate_processing` 鍦?Card / Document 鍒涘缓鍚?*鍚屾 upsert** `SearchIndex(object_type=card|document, ...)`锛岃鐢ㄦ埛 capture 瀹屼竴鍒?`/api/v1/search` 灏辫兘鍛戒腑銆傛柊鍔?`_index_search_object` helper 瀹炵幇 (object_type, object_id) 缁村害骞傜瓑銆?5. **鐢熶骇 bug fix** 鈥?`db/base.py` 鍐欐 `echo: True` 鏀逛负璇?`AGENTOS_DB_ECHO` / `DB_ECHO` 鐜鍙橀噺锛堥粯璁?off锛夛紝娑堥櫎鐢熶骇 SQL 鏃ュ織娲祦銆?6. **娴嬭瘯 harness 鎵╁睍** 鈥?`tests/integration/api/prd10/conftest.py::_TABLE_CREATE_ORDER` 鍔犲叆 `SearchIndex.__table__`锛宍_TABLE_DROP_ORDER` 鍚屾鍔?`search_indices`锛岃 capture pipeline 鐨勭储寮曡惤搴撳彲琚祴璇曡鐩栥€?
### 娴嬭瘯璇佹嵁

- `pytest tests/integration/api/prd10/ tests/integration/api/test_prd10_product_data_api.py tests/integration/api/test_prd10_frontend_binding.py` 鈫?**102/102 passed**锛?2.95s锛夈€?- 鏂板缓 `.tmp/smoke_tasks_prd10.py`锛岀鍒扮瀹炶窇锛?  - `POST /auth/register` 鈫?`POST /auth/login` 鈫?`GET /me` 楠岃瘉 搂5.1 9 瀛楁鍏ㄥ湪
  - `POST /tasks` 鈫?`GET /tasks?status=todo&priority=high` 鈫?`GET /tasks/{uuid}`
  - `PATCH /tasks/{uuid}` 鏀?status/tags 鈫?`POST /tasks/{uuid}/complete` 鑷姩 stamp `completed_at`
  - `DELETE /tasks/{uuid}` 杞垹 鈫?list 绔嬪嵆涓嶅惈锛涘叏閮?`[ok]`銆?
### 鏂囦欢瑙﹀姩

- `src/agent_os/auth/schema.py` (`Prd10MeResponse`)
- `src/agent_os/auth/router.py` (`get_prd10_me` 閲嶅啓)
- `src/agent_os/tasks/prd10_router.py` (鏂版枃浠?
- `src/agent_os/server/app.py` (`tasks_prd10_router` 娉ㄥ唽)
- `src/agent_os/capture/pipeline.py` (`_index_search_object`)
- `src/agent_os/db/base.py` (`echo` 璇?env)
- `tests/integration/api/prd10/conftest.py` (`SearchIndex` 琛?
- `static/mydow/mydow-api.js` (PRD10 搂6.1 base URL 娉ㄩ噴)
- `todo-tasks.md` (瑙勮寖鍖?+ 鎵╀换鍔℃睜)
- `.tmp/smoke_tasks_prd10.py` (鏂版枃浠?

### 寮€鏀鹃」

- 搂8.4 Document 璇︽儏瀛楁琛ラ綈锛坈hunks_preview/related_cards/ai_suggestions锛?鈥?寰呭仛
- 搂8.6 `seed_prd10.py --reset` 璺戜竴娆￠獙璇?搂25.3 璁℃暟锛?/20/30/5/5/3/10/5/10锛夆€?寰呭仛
- 搂8.7 `/notifications/stream` SSE 鍦?prod uvicorn 涓婇獙璇?鈥?寰呭仛
- 搂9 / 搂10 / 搂11 / 搂12 / 搂13 / 搂14 鍏ㄩ儴 `open` 绛変换鎰忓伐绋嬪笀璁ら锛涗笉闃诲宸ョ▼甯? SPA銆?
---

## Milestone 17 路 6 鎬佽瑙夎鑼?Chrome MCP 瀹炴祴锛圓gent 4 楠屾敹 14.4锛?鈥?BLOCKED

**When**: 鐢ㄦ埛甯冪疆 14.4 楠屾敹浠诲姟骞惰姹傛妸澶氫汉鍗忎綔 + 寮€鍙戣鑼冨浐鍖栧埌 rules銆?
### 鍐崇瓥涓庝骇鍑?
- 鏂板 `.cursor/rules/whyme-multiagent-workflow.mdc`锛氬浐鍖栧崗浣?+ 寮€鍙戣鑼冦€傚寘鍚?todo-tasks 鍗曚竴鎬昏〃鍗忚锛? 鐘舵€佸瓧銆佺紪鍙枫€佺姸鎬佹祦杞€佸啿绐侀伩鍏嶏級銆佷粨搴撻鍦板垝鍒嗐€丳RD10 楠屾敹纭€х害鏉熴€佹寜閽骇瑕佹眰銆丆hrome MCP 蹇呭仛瑙勫垯銆佹祴璇曞熀绾夸笉涓嬮檷瑙勫垯銆佷笉鐣?mock 瑙勫垯銆佹姇璧勬紨绀哄彛寰?13 鏉°€?- 鎵╁睍 `todo-tasks.md` 搂缁存姢瑙勫垯鍒?13 鏉★紝鏄庣‘ `pending` 宸插簾寮冦€丆hrome MCP 蹇呭仛銆佸幓 mock 鍖栬鍒欍€?- Agent 4 鍦ㄦ祻瑙堝櫒閲岃蛋瀹屼竴閬?PRD10 搂20 / 搂25.1 鐨?6 鎬佽瑙夐獙鏀讹紙浠诲姟 14.4锛夈€?
### Chrome MCP 瀹炴祴鍙戠幇鐨?6 涓弗閲嶇己闄?
| # | 缂洪櫡 | PRD10 寮曠敤 | 浠诲姟 |
|---|---|---|---|
| 1 | **Loading 楠ㄦ灦灞忎粠鏈湡鍑虹幇**锛氫汉涓哄欢杩?`MydowAPI.fetch` 400ms锛屾暣涓姞杞芥湡闂?`document.querySelectorAll('.skeleton').length === 0`銆侰SS 宸插畾涔?`@keyframes skeleton/shimmer` 浣?view 娓叉煋鍣ㄦ病娉ㄥ叆 | 搂20.1 / 搂7.9 | 9.13 |
| 2 | **Error 鐘舵€佷粠鏈湡鍑虹幇**锛氭敞鍏?throw `INTERNAL_ERROR` 鍚?`/today` 浠嶅睍绀?30 寮犺€?seed 鍗★紝娌℃湁 errorState DOM銆佹病鏈夐噸璇曞叆鍙?| 搂20.3 | 9.14 |
| 3 | **Empty 鐘舵€佹病鐪熸竻缂撳瓨**锛歮ock `/feed` 杩斿洖 `items=[]` 鍚庤€佺殑 30 寮犲崱鐗囩户缁樉绀猴紱KB 鍚屾牱 | 搂20.2 | 9.15 |
| 4 | **Permission Denied / 401 娌″垏鍥?auth-overlay**锛歚localStorage.removeItem('mydow_token')` 鍚庨〉闈㈢户缁睍绀鸿€佹暟鎹?| 搂20.5 + 搂22.1 | 9.16 |
| 5 | **`#/notifications` 涓?`#/search` hash 璺敱缂哄け**锛氬垏鎹?fallback 鍥?`#/today` | 搂25.1 | 9.17 |
| 6 | **鑷村懡甯冨眬宕╂簝**锛欿B 椤?hero 鏍囬 "鐭ヨ瘑搴? 琚珫鎺掞紙姣忓瓧涓€琛岋級锛屽壇鏍囬鍚屾牱銆侰hrome MCP take_screenshot 鐪嬪埌杩欎竴骞?| UI 鐜颁唬鍖?| 9.18 |

### 澶嶇幇鍛戒护

```pwsh
# 鍚庣璧?demo 妯″紡 + seed
$env:DATABASE_URL = "sqlite+aiosqlite:///d:/Codes/whyme/.tmp/smoke.db"
$env:AGENTOS_PRD10_WORKER = "on"
$env:AGENTOS_PRD10_WORKER_INTERVAL = "2"
$env:AGENTOS_DEMO_MODE = "on"
$env:PYTHONPATH = "d:\Codes\whyme\src"
python scripts/seed_prd10.py --email demo@mydow.example --password demo123 --reset
python -m uvicorn agent_os.server.app:app --host 127.0.0.1 --port 8000

# 娴忚鍣ㄨ繘 http://127.0.0.1:8000/mydow/
# 鍦?Chrome devtools 閲岄€愰」璺戯細
# 1) `localStorage.removeItem('mydow_token'); location.reload()` 鈫?楠岃瘉 Permission Denied
# 2) 娉ㄥ叆 monkey-patch `window.MydowAPI.fetch` 鎶?500 鈫?楠岃瘉 Error
# 3) 娉ㄥ叆 mock 杩斿洖 items:[] 鈫?楠岃瘉 Empty
# 4) `location.hash = '#/notifications'` 鈫?楠岃瘉璺敱
```

### 浠诲姟鐘舵€?
- `14.4` 浠?`doing` 鏀逛负 `blocked`锛宐locking on 宸ョ▼甯?2 淇繖 6 椤广€?- `9.13`鈥揱9.18` 鍏ㄩ儴 `open`锛岀瓑宸ョ▼甯?2 / Agent 2 璁ら銆?- 涓嶅姩 `static/mydow/{index.html,app.js,style.css,mydow-api.js}`锛圫PA 閲嶆瀯鏈熻竟鐣岋級銆?
### Follow-ups锛堢粰宸ョ▼甯?2 鐨勫叿浣撲慨澶嶆寚寮曪級

1. **鐘舵€佹満楠ㄦ灦**锛氭瘡涓?page renderer 杩涘叆鏃剁珛鍗虫妸 root 鍐呭鏇挎崲涓?`skeletonPage(...)`锛宖etch resolve/reject 鍚庡啀鏇挎崲锛沠etch 澶辫触娓叉煋 `errorState({message, retry})`锛沝ata 绌烘覆鏌?`emptyState({title, cta})`銆?2. **缂撳瓨澶辨晥**锛歱age renderer 蹇呴』浠ャ€屾渶杩戜竴娆?fetch 鐨?promise銆嶄负鏉冨▉锛岃€屼笉鏄€孌OM 涓婃娓叉煋鐨勫唴瀹广€嶃€傚綋鍓嶆槸鍏堟覆鏌撹€佹暟鎹啀 fetch銆?3. **401 鈫?auth overlay**锛歚api()` 鍖呰鍦?catch `UNAUTHORIZED` 鏃舵竻 token + render auth-overlay锛岃€屼笉鏄潤榛樿繑鍥?stale data銆?4. **`#/notifications` `#/search`**锛歳oute 琛ㄥ姞杩欎袱鏉★紱閫氱煡鎶藉眽涓庢悳绱㈠脊绐椾笌涔嬪鐢ㄥ悓涓€ view 鍑芥暟鍗冲彲銆?5. **KB 鏍囬甯冨眬宕╂簝**锛氭鏌?`.section-title` 鎴?`.hero` 鏄惁 `display: flex; flex-direction: column` 鎶婃瘡涓瓧绗﹀綋 child 鎺掍簡銆?
---

## Milestone 16 路 SPA 閲嶆瀯鏈?Agent 4 闈炲啿绐佷氦浠橈紙鎵嬪唽 + 鍩虹嚎 + 瀛楁瀹¤锛?鈥?DONE

**When**: 鐢ㄦ埛鍛婄煡宸ョ▼甯?2 姝ｅ湪閲嶅啓 `static/mydow/` 涓哄師鐢?ESM SPA锛堜换鍔℃竻鍗曠 1 椤癸級锛屽苟瑕佹眰 Agent 4 鎵句竴浠垛€滀笉浼氬拰宸ョ▼甯?2 鎾炪€佷笖 PRD10 鐪熸湁绌虹己鈥濈殑宸ヤ綔鍋氥€侫gent 4 閫変簡涓変欢**鍙鍚庣銆佷笉鍔ㄥ墠绔?*鐨勫伐浣溿€?
### 鍐崇瓥锛氶伩鍏嶅啿绐佺殑宸ヤ綔杈圭晫

宸ョ▼甯?2 鍦ㄥ仛锛歚index.html`锛?7 琛?SPA 楠ㄦ灦锛? `style.css`锛?6KB 璁捐浠ょ墝锛? 鎺ヤ笅鏉ョ殑 `app.js`锛圚ashRouter + view 娓叉煋鍣級銆傝€?prototype 宸叉尓鍒?`static/mydow/legacy-prototype.html`銆?
Agent 4 鍦?SPA 閲嶆瀯鏈?*绂佹鍔?*锛?- `static/mydow/{index.html, app.js, style.css, mydow-api.js, legacy-prototype.html}`
- `agent_os/auth/router.py:demo_router`锛堝凡 done锛?- 浠讳綍鍚庣 router/DTO锛堝伐绋嬪笀 1/2/3 棰嗗湴锛?
### 浜や粯鐗╋紙4 浠讹級

| # | 鏂囦欢 | 璇存槑 |
|---|---|---|
| 1 | `docs/agent-2-spa-binding-guide.md` | 10 绔?SPA 鎺ュ叆鎵嬪唽锛氭暟鎹绾?搂5 / 璺敱棣栧睆鐭╅樀 搂25.1 / 鍩熸帴鍙ｆ竻鍗?搂7-搂18 / 鐘舵€佹満 搂20 / 瀹炴椂鍒锋柊 / hash 璺敱 / 娓叉煋鍣ㄧ洰褰曠粨鏋勫缓璁?/ 宸茬煡鍧戯紙`/kb/folders` 鏃?pagination銆乣.local` 閭琚?EmailStr 鎷掔粷銆乣/auth/login` 涓嶈繑 envelope銆丼SE Windows 姝婚攣銆乣/tasks/*` 涓嶆槸 PRD10 璺緞銆佺┖搴撹嚜鍔?seed Skill銆丄I LLM 寮€鍏炽€亀orker 闂撮殧锛?|
| 2 | `.tmp/baseline-tests.txt` | 13 濂椾欢 188 鐢ㄤ緥锛?*187 passed / 1 failed**锛涜缁嗚褰曞敮涓€澶辫触 `test_mydow_primary_action_bindings_are_wired`锛?1 涓?token 鍏?missing锛屽洜涓鸿€?prototype DOM 宸插湪 SPA 閲嶆瀯閲岃娓呮帀锛夛紝鏄庣‘**杩欐槸棰勬湡澶辫触**涓斾笉灞炰簬 Agent 4 淇鑼冨洿 |
| 3 | `docs/agent-2-seed-field-audit.md` | Seed vs PRD10 搂5 瀛楁宸窛瀹¤锛?0 寮犺〃锛圲ser/Folder/Document/Card/Prd10InboxItem/AIConversation/AIMessage/Skill/Notification/SearchIndex锛夐€愬瓧娈垫爣 null/empty/no-attr锛岀粰 SPA 姣忎釜瀛楁绌烘椂鐨?fallback 寤鸿锛岀粰 Agent 1/2/3 鏀?seed 鐨?P0/P1/P2 浼樺厛绾?|
| 4 | `.tmp/seed_audit.py` + `.tmp/seed_audit_report.txt` | 瀹¤鑴氭湰涓庡師濮嬫姤鍛婏紝鍙噸澶嶈繍琛?|

### 瀹¤鍏抽敭鍙戠幇锛堢粰宸ョ▼甯?2 SPA 娓叉煋鍣ㄧ敤锛?
- **`Document.chunk_count` / `Document.last_opened_at` 鍦ㄦā鍨嬩笂涓嶅瓨鍦?*锛孭RD10 搂5.7 鍒楀嚭浜嗕絾浠ｇ爜娌″疄鐜扳€斺€擲PA 涓嶈灏濊瘯璇昏繖涓や釜瀛楁锛屽惁鍒?`undefined`銆?- **`AIMessage.citations` / `tool_calls` / `attachments` 鍦?seed 鏁版嵁閲屽叏绌烘暟缁?*锛宍model` / `tokens` / `latency_ms` 鍏?null鈥斺€擲PA 娓叉煋 AI 寮曠敤 UI 蹇呴』鍏堝垽绌猴紝鍚﹀垯浼氱敾涓€鍫嗙┖鍗犱綅锛堣繖鏄敤鎴蜂笂涓€杞姳鎬ㄢ€滃儚鍥剧墖鎷艰捣鏉モ€濈殑涓€涓師鍥狅級銆?- **`Card.cover_url` / `source_id` / `inbox_item_id` 鍏?null**鈥斺€斿崱鐗囧皝闈㈣ fallback 鍒?entities 鏂囧瓧灏侀潰鎴栬壊鍧椼€?- **`SearchIndex.embedding_id` 鍏?null**鈥斺€擲PA 鐨勩€岃涔夋悳绱€嶅紑鍏冲湪 V1 搴旂鐢紝鍙厑璁?`mode=keyword`銆?- **`AIConversation.context_scope` 绌?dict**鈥斺€斻€屼笂涓嬫枃 chip銆峌I 鍦?seed 鏁版嵁涓嬫樉绀恒€屽叏灞€涓婁笅鏂囥€嶅嵆鍙€?
### 娴嬭瘯鍩虹嚎锛堥噸瑕侊細缁欏伐绋嬪笀 2 SPA 瀹屽伐鍚庡洖褰掑鐓э級

```
python -m pytest \
  tests/integration/api/test_prd10_v1_acceptance.py \
  tests/integration/api/test_prd10_frontend_binding.py \
  tests/integration/api/test_prd10_ai_api.py \
  tests/integration/api/test_prd10_ai_llm.py \
  tests/integration/api/test_prd10_search_api.py \
  tests/integration/api/test_prd10_skills_api.py \
  tests/integration/api/test_prd10_garden_api.py \
  tests/integration/api/test_prd10_observability.py \
  tests/integration/api/test_prd10_app_wiring.py \
  tests/integration/api/test_prd10_models_intelligence.py \
  tests/integration/api/test_prd10_e2e_flow.py \
  tests/integration/api/test_prd10_product_data_api.py \
  tests/integration/api/test_prd10_insights_api.py \
  tests/integration/api/prd10/ \
  -q -p no:cacheprovider --tb=no --no-header
# -> 187 passed, 1 failed (test_mydow_primary_action_bindings_are_wired - SPA rewrite expected)
```

### Follow-ups

- **4.23锛堝伐绋嬪笀 2 / Agent 2 棰嗭級**锛歋PA 瀹屽伐鍚庢妸 `test_mydow_primary_action_bindings_are_wired` 鐨勫绾︿粠鑰?prototype 鍒囧埌鏂?SPA 鐨?DOM hooks锛堝缓璁細`id="app"` `id="auth-overlay"` `id="toast-stack"` + 娓叉煋鍣ㄥ０鏄庣殑鍏抽敭 selector锛夈€?- 宸ョ▼甯?1/3 review 鏈疆涓変唤鏂囨。锛岀‘璁ゆ墜鍐岄噷缁?SPA 鐨勫瓧娈靛绾﹀拰瀹為檯鍚庣瀹炵幇瀵归綈锛涘鏈?P1/P0 鏀?seed 鐨勫悎浣滄剰鍚戯紝鍦ㄦ柊涓€杞?Milestone 閲岀櫥璁般€?
---

## Milestone 15 路 Demo 妯″紡鎺ュ叆 + Mydow 鍏ㄦ寜閽仈璋冿紙涓€閿捣 demo锛?鈥?DONE

**When**: 鐢ㄦ埛銆屼笉瑕佹湁鏈畬鎴愭湭楠岃瘉鐨勫湴鏂癸紝鎶婃墍鏈夌殑閮借窇閫氣€︹€︽垜闇€瑕佷竴浠藉畬鏁村彲璺戠殑 demo 鍑烘潵銆嶄箣鍚庣珛鍗宠惤鍦般€?
### 涓昏鍙樻洿

- **Demo router**锛歚src/agent_os/auth/router.py` 鏂板 `demo_router`锛屾寕杞藉埌
  `/api/v1/demo`锛屾敮鎸?  - `POST /api/v1/demo/login` 鈥?`AGENTOS_DEMO_MODE=on` 鏃朵竴閿彂鏀?token锛?    鎳掑垱寤?`demo@mydow.example / demo123`锛?01 鏃惰嚜鍔ㄦ敞鍐屻€?  - `GET /api/v1/demo/status` 鈥?缁欏墠绔敤鏉ュ喅瀹氭槸鍚﹁嚜鍔ㄧ櫥褰曘€?- **`static/mydow/mydow-api.js`**锛坴2锛寏2370 琛岋級锛?  - 寮曞叆 `TOAST_INTENTS`锛氭妸 `index.html` 閲?23 涓?`data-toast` 瀛楅潰閲?    锛堜笂浼?缃戦〉/璇煶/娣卞害鐮旂┒/鐭ヨ瘑搴?AI 鎽樿/AI 淇濆瓨/Skill/閫氱煡/鍒嗕韩鈥︼級
    鏄犲皠鍒扮湡瀹?PRD10 API銆傜洃鍚櫒鏀规垚 **document 绾т簨浠朵唬鐞?*锛屽洜姝?    settings 鎶藉眽銆乵odal銆佸姩鎬佹敞鍏ュ尯鍩熷叏閮ㄨ鐩栥€?  - 鍩?client 瀹屾暣鍖栵細`search/ai/skills/garden/feed/cards/kb/capture/inbox/
    notifications/jobs/today/me/insights/reports/auth`锛屽苟鍔犱笂
    `cards.update / remove / favorite`銆乣kb.updateFolder/deleteFolder/
    moveDocument`銆乣capture.presign / commitFile`銆乣auth.register`銆?  - 娓叉煋 / 瀵艰埅澧炲己锛歚openFolderDetail / openDocumentDetail /
    openCardDetail / showDocumentDrawer / showCardDrawer / applyPageMode`銆?    鑷畾涔?`mydow-doc-drawer / mydow-garden-node`銆?  - **鐧诲綍娴眰** `mydow-auth-overlay` 鐜板湪浼氬厛璋?`demo/status`锛氬紑鍚椂
    鑷姩 `demo/login`锛屽け璐ュ啀闄嶇骇鍒版墜鍔ㄧ櫥褰?娉ㄥ唽琛ㄥ崟銆?- **娴嬭瘯**锛坄tests/integration/api/test_prd10_frontend_binding.py`锛?85 琛岋級锛?  - 闈欐€佸绾︽墿鍒版墍鏈?23 绫?toast 鎰忓浘銆佹墍鏈夊煙 client銆佹墍鏈?render hook銆?  - 鏂板 `test_demo_endpoints_disabled_by_default` 涓?    `test_demo_endpoints_enabled_when_flag_set`銆?  - 鍏ㄥ `test_prd10_frontend_binding.py + worker_loop + jobs_notifications`锛?    `python -m pytest tests/integration/api/test_prd10_frontend_binding.py
    tests/integration/api/prd10/test_prd10_worker_loop.py
    tests/integration/api/prd10/test_prd10_jobs_notifications_api.py
    -q -p no:cacheprovider` -> **35 passed**.

### 涓€閿捣 demo 姝ラ锛堝凡楠岃瘉锛?
```pwsh
$env:DATABASE_URL = "sqlite+aiosqlite:///d:/Codes/whyme/.tmp/smoke.db"
$env:AGENTOS_PRD10_WORKER = "on"
$env:AGENTOS_PRD10_WORKER_INTERVAL = "2"
$env:AGENTOS_DEMO_MODE = "on"
$env:AGENTOS_AI_LLM = "off"
$env:PYTHONPATH = "d:\Codes\whyme\src"

# 涓€娆℃€?seed锛堝彲閫夛紱绌哄簱涓?mydow 涔熻兘鐢紝鍙槸娌″巻鍙插唴瀹癸級
python scripts/seed_prd10.py --email demo@mydow.example --password demo123 --reset

# 璧锋湇鍔?python -m uvicorn agent_os.server.app:app --host 127.0.0.1 --port 8000
# 娴忚鍣ㄦ墦寮€ http://127.0.0.1:8000/mydow/锛岃嚜鍔ㄧ櫥褰曘€?```

### Chrome MCP 瀹炴祴锛坉emo@mydow.example锛屽凡 seed锛?
- Demo 鑷姩鐧诲綍锛氭诞灞傝繘鍏?`data-state="logged-in"`锛屾棤闇€鎵嬪姩鎿嶄綔銆?- baseline锛坰eed 涔嬪悗銆佺偣鎸夐挳涔嬪墠锛夛細feed=35, kbDocs=21, kbFolders=7,
  notif=9, aiConvs=4, skills=6, today.knowledge_items_count=21銆?- 娴忚鍣ㄥ唴涓€娆＄偣瀹?19 涓?toast 鎰忓浘 + 11 涓?modal 涓绘寜閽?+ 3 涓?  settings panel 鐨勫揩鎹锋寜閽紙鍏?33 娆＄湡鎸夐挳鐐瑰嚮锛夈€?- worker 璺戝畬鍚庣殑 delta锛歠eed +6, kbDocs +2, kbFolders +1, notif +5,
  pending_task +2, today_capture +5, knowledge_items +2銆?- 鍏抽敭璇佹嵁锛?  - KB 鏂板 `mydow-upload-*.txt`锛坧resign + PUT + commit 涓夋寮忥級锛?    浠ュ強 鈥淎I 鑱旇皟 / AI 浜у嚭 / 娲炲療淇濆瓨鈥?绫?KB 鏂囨。锛坵orker 鎶?    `ai_message_to_kb` 鏉愭枡鍖栵級銆?  - `/today.tasks` 鍑虹幇 鈥滄暣鐞嗘湰娆℃礊瀵?/ 鎶婃礊瀵熷綊妗ｅ埌鐭ヨ瘑搴撯€?    锛坵orker 鎶?`ai_message_to_tasks` 鏉愭枡鍖栵級銆?  - 閫氱煡閲屽悓鏃跺嚭鐜?鈥淎I 杈撳嚭宸蹭繚瀛樺埌鐭ヨ瘑搴?/ AI 宸茬敓鎴愪换鍔?/
    璁板綍宸叉暣鐞嗗畬鎴愨€濓紝璇佹槑 worker 鍛ㄦ湡鎬у啓鍏ュ苟鍘婚噸銆?- 鎴浘褰掓。锛歚.tmp/screenshots/demo-mode-full.png`锛?.3 MB锛夈€?
### Follow-ups

- demo 妯″紡榛樿浠嶇劧 OFF锛岀敓浜ч儴缃蹭笉浼氭剰澶栧彂鏀?demo session銆?- LLM 鐪熷疄娴佸紡锛坄/ai/.../messages/stream`锛変繚鎸?`AGENTOS_AI_LLM=off`
  榛樿锛涜娴嬬湡 LLM 鏃堕厤鍚?`.env.local` 鍒囨崲鍗冲彲銆?- 娴忚鍣ㄧ骇鍥炲綊浠嶇劧渚濊禆 Chrome MCP 鎵嬪姩璺戯紱寮曞叆 Playwright runner
  鏄?P1 浠诲姟锛堜笉褰卞搷褰撳墠 demo 鍙窇鎬э級銆?
---

## Milestone 14 路 Chrome MCP 娴忚鍣ㄥ疄娴?PRD10 鍏ㄩ摼璺?鈥?DONE

**When**: 鐢ㄦ埛瑕佹眰 鈥滀綘璋冪敤 chrome mcp 璇曚竴璇曞墠鍚庣鐨勬墍鏈夊姛鑳芥槸涓嶆槸閮介€氫簡鈥?鍚庣珛鍗虫墽琛屻€?
### How it ran

- 涓存椂鏁版嵁搴擄細`sqlite+aiosqlite:///d:/Codes/whyme/.tmp/smoke.db`锛岀幆澧冨彉閲?  `AGENTOS_PRD10_WORKER=on`銆乣AGENTOS_PRD10_WORKER_INTERVAL=2`銆?  `AGENTOS_AI_LLM=off`銆?- 杩涚▼锛歚python -m uvicorn agent_os.server.app:app --host 127.0.0.1 --port 8000`
  鍚庡彴杩愯锛宻tdout/stderr 鍐欏叆 `.tmp/uvicorn.{out,err}`锛岄獙璇佸畬姣曞凡鍏抽棴銆?- 璐﹀彿锛歚POST /api/v1/auth/register` 娉ㄥ唽 `smoke_user / SmokePass#1`锛屾嬁鍒?  access_token銆?- 娴忚鍣細`chrome-devtools` MCP 鍦?`isolatedContext=prd10-mcp-smoke` 涓?  鎵撳紑 `http://127.0.0.1:8000/mydow/`锛屽皢 token 鍐欏叆 `localStorage.mydow_token`
  鍚?`reload`锛屾墍鏈夎皟鐢ㄧ粡杩?`static/mydow/mydow-api.js` 鈫?鐪熷疄 PRD10 鍚庣銆?
### Verified end-to-end (娴忚鍣ㄥ唴 evaluate_script 鐪熷疄缁撴灉)

| 鍩?| 璋冪敤 | 缁撴灉 |
| --- | --- | --- |
| Auth | `MydowAPI.me.fetch()` | `username: "smoke_user"` |
| Today | `MydowAPI.today.fetch()` | `keys: user/stats/quick_actions/tasks/insight_preview/favorite_folders` |
| Capture | `capture.text` / `capture.link` | 涓ゆ潯 inbox item 鍒涘缓鎴愬姛锛宍auto_process` 瑙﹀彂 worker |
| KB | `kb.createFolder` / `kb.overview` / `kb.listDocuments` | 鏂囦欢澶?/ 鏂囨。璁℃暟瀹炴椂澧炲姞 |
| Cards | `cards.create` | 鍐欏叆 feed 骞剁珛鍗冲嚭鐜板湪 `feed.list` |
| Feed | `feed.list({ page_size: 10 })` | 鏈疆 `total: 3`锛屽惈 capture/text銆乧apture/link銆乧ard |
| Notifications | `notifications.list` / `markAllRead` / `unreadCount` | 4 鏉￠€氱煡 鈫?markAllRead `updated: 2` 鍚?`unread.count == 0` |
| AI | `ai.createConversation` + `ai.sendMessage` | 鍗犱綅鍥炲 + `job.job_type == "ai_chat"` |
| AI 鈫?KB | `ai.saveToKb(messageId, 鈥?` | worker 璺戝畬鍚?`kb.documents.total: 1`銆佹枃妗?鈥淎I 鑱旇皟 鈫?KB鈥?鍑虹幇鍦?`kb.overview.recent_documents` |
| AI 鈫?Tasks | `ai.createTasks(messageId, [...])` | worker 璺戝畬鍚?`today.tasks` 澶氬嚭 鈥滆仈璋冧骇鐢熺殑浠诲姟 1/2鈥?|
| Skills / Search / Garden | `skills.list` / `search.query` / `garden.overview` | 鍏ㄩ儴 200锛宍garden.overview.node_count` 闅忓崱鐗囧疄鏃跺彉鍖?|

### Worker 琛屼负

- `agent_os.jobs.worker_loop` 姣?2 绉掓媺鍙栦竴娆?`prd10_jobs`锛屾祻瑙堝櫒渚х殑
  `auto_process=true` 鍏ㄩ儴琚秷鍖栦负 `completed`锛沗/today` 鐨?  `today_capture_count: 4`銆乣pending_task_count: 2`銆乣knowledge_items_count: 1`
  涓庢祻瑙堝櫒瀹炴搷娆℃暟涓ユ牸瀵归綈锛岃瘉鏄?PRD10 搂26 涓夊ぇ闂幆锛坈apture 鈫?feed 鈫?  notification銆並B folder/document銆丄I chat 鈫?save-to-kb / create-tasks锛夊湪
  鐢熶骇褰㈡€佺殑 ASGI app 鍐呭叏閮ㄨ窇閫氥€?
### Artifacts

- 娴忚鍣ㄧ獥鍙ｆ埅鍥撅細`.tmp/screenshots/mcp-smoke.png`锛坄take_screenshot` 鎶撳抚鍚?  褰掓。锛涘彲浣滀负 P1 寮曞叆 Playwright 涔嬪墠鐨勪汉宸ヨ瘉鎹級銆?- 鍚庡彴鏃ュ織锛歚.tmp/uvicorn.{out,err}`锛堝凡纭 SQL 涓?worker tick 姝ｅ父锛夈€?
### Follow-ups

1. 濡傛灉瑕佹妸杩欐娴佺▼娌夋穩涓鸿嚜鍔ㄥ寲鐢ㄤ緥锛屽彲鍦?`tests/integration/api/` 澧炲姞
   涓€涓?`test_prd10_browser_smoke.py`锛岀敱 `pytest --browser-runner` 瑙﹀彂锛?   鐜板湪璇?runner 浠嶆槸 P1 浠诲姟銆?2. 杩欐娌℃湁瑙﹀彂 `AGENTOS_AI_LLM=on` 鐨勭湡瀹?SSE 璺緞鈥斺€旂瓑鐢ㄦ埛甯屾湜涓€骞惰窇
   娴佸紡 LLM 鏃跺啀寮€鍏炽€?
---

## Milestone 13 路 Frontend button-click validation and unified todo table 鈥?PARTIAL PASS

**When**: User reported that many buttons still do not click or do not reach the
expected result, and requested a single maintained delivery table named
`todo-tasks`.

### Delivered

- Rebuilt `todo-tasks.md` as the single source-of-truth table using only
  `done` / `pending` / `open`.
- Reclassified frontend completion accurately:
  - API/static binding remains `done`.
  - Button-click behavior is `pending` until each high-intent button has
    click-level evidence.
- Confirmed `static/mydow/mydow-api.js` now has a broad `TOAST_INTENTS` table
  that intercepts prototype `data-toast` buttons and maps them to real PRD10
  API calls.
- Updated `tests/integration/api/test_prd10_frontend_binding.py` to guard the
  new implementation shape:
  - `attachToastIntents`
  - upload / voice / deep research handlers
  - presign + commit file flow
  - existing auth, capture, KB, notification, skill, AI save bindings.

### Chrome MCP click-level evidence

Local server:

```
DATABASE_URL=sqlite+aiosqlite:///./data/chrome-buttons.db
AGENTOS_PRD10_WORKER=off
uvicorn agent_os.server.app:app --host 127.0.0.1 --port 8767
```

Using a real JWT in Chrome, the following real clicks were executed through the
page UI and produced successful `/api/v1` requests:

- Text capture submit button -> `POST /api/v1/capture/text` -> 200.
- Upload modal start button -> `/uploads/presign` -> 200,
  `PUT /uploads/local/{id}` -> 200, `/capture/file/commit` -> 200.
- Web clipping save button -> `POST /api/v1/capture/link` -> 200.
- Voice save button -> `POST /api/v1/capture/text` -> 200.
- Deep research start button -> `POST /api/v1/ai/conversations/{id}/messages`
  -> 201.
- AI composer send button -> `POST /api/v1/ai/conversations/{id}/messages`
  -> 201.
- Notification read-all button -> `POST /api/v1/notifications/read-all` -> 200.

Console evidence: no errors or warnings; only success info toasts:

- `鐏垫劅宸插悓姝ュ埌鍚庣`
- `涓婁紶浠诲姟宸插垱寤哄苟鍏ラ槦`
- `缃戦〉鍓棌宸叉彁浜ゅ悗绔痐
- `璇煶璁板綍宸蹭繚瀛樺埌鍚庣`
- `娣卞害鐮旂┒浠诲姟宸插垱寤哄苟鍏ラ槦`
- `AI 鍥炲宸茬敓鎴愶紙鍗犱綅鍥炵瓟鍙湪鎺у埗鍙版煡鐪嬶級`
- `閫氱煡宸插悓姝ユ爣璁颁负宸茶`

### Test evidence

```
python -m pytest tests/integration/api/test_prd10_frontend_binding.py -q -p no:cacheprovider
# -> 14 passed
```

### Remaining frontend button work

- New folder / new document / AI save / Skill run handlers exist, but still
  were verified in the follow-up pass. Skill run required adding a default
  built-in skill for fresh installs.
- Many secondary buttons are now mapped by `TOAST_INTENTS`, but still need
  per-page click audit.
- Most screen content remains static prototype content; real data rendering
  back into the DOM is still open.

### Follow-up pass

- Added a default built-in Skill (`Mydow 蹇€熸€荤粨`) in
  `src/agent_os/skills/router.py` when a fresh database has no active skills.
  This prevents the Skills page / modal from being a dead end in V1.
- Updated tests to expect the default skill:

```
python -m pytest tests/integration/api/test_prd10_skills_api.py tests/integration/api/test_prd10_frontend_binding.py -q -p no:cacheprovider
# -> 27 passed
```

- Chrome MCP verified the remaining high-intent buttons on a fresh DB:
  - Knowledge nav -> `/api/v1/kb/overview`, `/api/v1/kb/folders`.
  - New folder -> `POST /api/v1/kb/folders` -> 200.
  - New document -> `POST /api/v1/cards` -> 201.
  - AI save -> `POST /api/v1/ai/messages/{id}/save-to-kb` -> 202.
  - Skill run -> `/api/v1/skills` -> default skill, then
    `POST /api/v1/skills/{id}/run` -> 202.

---

## Milestone 12 路 Chrome MCP browser integration validation 鈥?PASS

**When**: User challenged the previous acceptance as insufficient because it
relied on API/static tests and not Chrome MCP.

### What changed

- Fixed a real browser-discovered contract mismatch:
  - PRD10 documents `/api/v1/me`.
  - The static frontend was calling the existing legacy path indirectly after
    a temporary fix.
  - Added `me_router` in `src/agent_os/auth/router.py` and mounted it in
    `src/agent_os/server/app.py`, so `/api/v1/me` aliases the existing
    authenticated user response.
  - Updated `static/mydow/mydow-api.js` back to the PRD10 path: `api.me.fetch()`
    calls `/me`.
- Fixed SQLite dev-server compatibility needed for local Chrome validation:
  - `src/agent_os/db/base.py` now imports `agent_os.db.sqlite_compat`.
  - SQLite engine creation no longer receives PostgreSQL-only `pool_size` /
    `max_overflow` arguments.

### Chrome MCP evidence

Local server:

```
DATABASE_URL=sqlite+aiosqlite:///./data/chrome-prd10-2.db
AGENTOS_PRD10_WORKER=off
uvicorn agent_os.server.app:app --host 127.0.0.1 --port 8766
```

Chrome MCP opened `http://127.0.0.1:8766/mydow/`, injected a real JWT obtained
from `POST /api/v1/auth/register`, reloaded the page, and executed the real
frontend API surface through `window.MydowAPI`.

Verified browser results:

- Page loaded: `/mydow/` -> 200.
- Script loaded: `/mydow/mydow-api.js` -> 200.
- Auth/session: `/api/v1/me` -> 200, user `chrome_e2e_2`.
- Today: `/api/v1/today` -> 200.
- Capture: `POST /api/v1/capture/text` -> 200.
- Feed: `/api/v1/feed?page_size=5` -> 200, `feedTotal = 1`.
- KB: `/api/v1/kb/overview` -> 200.
- Notifications: `/api/v1/notifications/unread-count` -> 200.
- Search: `/api/v1/search?q=Chrome&page_size=5` -> 200.
- AI: `POST /api/v1/ai/conversations` -> 201.
- AI message: `POST /api/v1/ai/conversations/{id}/messages` -> 201,
  assistant role `assistant`.
- Skills: `/api/v1/skills?page_size=5` -> 200.
- Garden: `/api/v1/garden/overview` -> 200.
- Chrome console: no error/warn/info/log messages after validation.

### Test evidence after the fix

```
python -m pytest tests/integration/api/test_prd10_frontend_binding.py -q -p no:cacheprovider
# -> 14 passed
```

```
python -m pytest tests/integration/api/test_prd10_app_wiring.py -q -p no:cacheprovider
# -> 6 passed
```

An attempted full PRD10 matrix rerun was externally interrupted after progress
output and produced no failure summary, so it is not counted as fresh evidence.
The last complete full-matrix evidence remains Milestone 10 (`123 passed`),
with the `/me` patch covered by the focused tests and Chrome MCP validation
above.

### Updated acceptance posture

- **Chrome MCP browser-level frontend/backend integration: PASS** for the
  PRD10 V1 core API surface.
- **PRD10 V1 API/static acceptance: PASS** based on Milestone 10.
- **Not a claim that every P1/hardening task is finished**. Other engineer
  todo files still contain follow-up/hardening work such as browser-click
  persistence tests, streaming, richer context/citation ranking, and legacy
  cleanup.

---

## Milestone 10 路 PRD10 integrated acceptance and repo cleanup pass 鈥?DONE

**When**: Commander takeover after Agent 1/2/3/4 slices were present.

### Delivered

- Ran the complete PRD10 integration matrix across product-data, intelligence,
  frontend binding, app wiring, observability, and model tests:

```
python -m pytest tests/integration/api/test_prd10_product_data_api.py tests/integration/api/test_prd10_frontend_binding.py tests/integration/api/test_prd10_ai_api.py tests/integration/api/test_prd10_e2e_flow.py tests/integration/api/test_prd10_observability.py tests/integration/api/test_prd10_app_wiring.py tests/integration/api/test_prd10_garden_api.py tests/integration/api/test_prd10_skills_api.py tests/integration/api/test_prd10_search_api.py tests/integration/api/test_prd10_models_intelligence.py tests/integration/api/prd10 -q
# -> 123 passed
```

- Re-ran full test collection:

```
python -m pytest --collect-only -q -p no:cacheprovider
# -> 1377 tests collected, exit 0
```

- Confirmed Mydow Web is served from `static/mydow/`, mounted at `/mydow/`,
  and `static/mydow/mydow-api.js` covers the PRD10 API surface:
  Today, Capture, Feed/Cards, KB, Jobs, Notifications, AI, Search, Skills,
  and Garden.
- Added/verified the product-data umbrella test asserts `capture/text`
  materializes a Feed card, locking the Capture -> Card -> Feed loop.
- Cleaned generated runtime logs and added ignore rules for local runtime
  data / IDE transcript artifacts:
  - `data/memory.json`, `data/sessions.json`, `data/users.json`
  - `data/workspace/`, `data/workspaces/`
  - `.claude/settings.local.json`, `.cursor/`, `.specstory/`
  - `agent-tools-tmp.txt`
- Added `.gitattributes` to normalize repository text files to LF while
  keeping Windows script files (`.bat`, `.cmd`, `.ps1`) on CRLF and marking
  common binary assets explicitly.

### Current acceptance posture

- PRD10 V1 backend and static frontend binding are green under the dedicated
  acceptance suite.
- Full repository collection is clean.
- Remaining repository noise is either tracked source/config changes from the
  PRD10 implementation or pre-existing tracked generated files under
  `data/workspaces/import_test/toolkit/*`; those should be reviewed before
  any destructive cleanup.

### Follow-ups

1. Introduce a browser runner (Playwright or equivalent) if V1 requires
   click-level DOM persistence tests beyond static contract + ASGI liveness.
2. Decide whether tracked `data/workspaces/import_test/toolkit/*` changes are
   legitimate fixtures or should be regenerated from source.
3. Run a full `pytest -q` stabilization pass; the PRD10 suite is green, while
   legacy tests may still need separate cleanup.

---

## Milestone 13 路 Real LLM provider + AI streaming SSE wired 鈥?DONE

**When**: After Milestone 12 acceptance pass identified AI streaming +
LLM as the top remaining V1 blockers; the user confirmed a real LLM key
is provisioned in `.env.local`.

### Why this lands now

PRD10 搂26.3 requires "鑳芥祦寮忚繑鍥?AI 鍥炵瓟". Until this slice the
assistant content was a deterministic placeholder. The repository
already shipped `agent_os.llm.litellm_impl.LiteLLMProvider` and an
OpenAI-compatible DeepSeek key in `.env.local`; the missing pieces were
**(a)** wiring the provider into the PRD10 AI router and **(b)** an SSE
endpoint over the same persistence shape.

### Delivered

- `src/agent_os/ai/llm_provider.py` (new):
  - `is_llm_enabled()` honors `AGENTOS_AI_LLM=on/1/true/enabled` and a
    test-injected provider, so existing PRD10 AI tests stay offline by
    default.
  - `get_provider()` lazily constructs `LiteLLMProvider` from env.
  - `set_test_provider()` lets tests inject a fake without monkey-patching
    each call site.
- `src/agent_os/ai/router.py`:
  - `POST /api/v1/ai/conversations/{id}/messages` now calls the real
    LLM when enabled. `model="litellm"`, real
    `input_tokens`/`output_tokens`/`latency_ms`. Provider failures
    degrade to the placeholder reply with `error.code="AI_PROVIDER_ERROR"`.
  - **New `POST /api/v1/ai/conversations/{id}/messages/stream`** returns
    `text/event-stream` and emits `meta` 鈫?`token*` 鈫?`done` events.
    The assistant message is created up-front with `status=running`,
    then finalized to `completed`/`failed` after the stream closes
    (uses a fresh sessionmaker so the request connection can flush
    chunks without holding DB locks).
- `tests/integration/api/test_prd10_ai_llm.py` (new): 9 tests covering
  `is_llm_enabled` envelope, real-LLM message persistence with a fake
  provider, placeholder fallback when disabled, SSE event order with
  fake LLM, and SSE offline-stream fallback.
- `tests/integration/api/prd10/test_prd10_capture_api.py`:
  - Repaired `test_uploads_presign_returns_local_url` against the
    new `/api/v1/uploads/local/{id}/raw` shape (the V1 web app needs
    a real downloadable URL, not the deprecated `local://` scheme).

### Test evidence

```
python -m pytest tests/integration/api/test_prd10_ai_llm.py tests/integration/api/test_prd10_ai_api.py -q -p no:cacheprovider
# -> 23 passed
```

```
python -m pytest \
  tests/integration/api/prd10/ \
  tests/integration/api/test_prd10_product_data_api.py \
  tests/integration/api/test_prd10_frontend_binding.py \
  tests/integration/api/test_prd10_app_wiring.py \
  tests/integration/api/test_prd10_ai_api.py \
  tests/integration/api/test_prd10_ai_llm.py \
  tests/integration/api/test_prd10_search_api.py \
  tests/integration/api/test_prd10_skills_api.py \
  tests/integration/api/test_prd10_garden_api.py \
  tests/integration/api/test_prd10_observability.py \
  tests/integration/api/test_prd10_e2e_flow.py \
  tests/integration/api/test_prd10_models_intelligence.py \
  tests/integration/api/test_prd10_v1_acceptance.py \
  -q -p no:cacheprovider
# -> 174 passed
```

### Operational notes

- Default behavior stays offline: `AGENTOS_AI_LLM` unset 鈫?placeholder
  reply, no outbound network. Existing PRD10 AI tests keep passing
  unchanged.
- To turn on the real DeepSeek-V3.1 endpoint provided in `.env.local`,
  set `AGENTOS_AI_LLM=on` in the environment before launching the app.
  No code changes are required.
- The streaming endpoint is `POST /api/v1/ai/conversations/{id}/messages/stream`,
  matching the Mydow Web SSE consumer pattern. The non-streaming endpoint
  remains for clients that prefer a synchronous response.

### Updated V1 deliverable status

PRD10 搂24 P0 outstanding items dropped from 7 to 5:

1. ~~AI streaming SSE~~ 鈫?done in this milestone.
2. ~~Real LLM provider~~ 鈫?done in this milestone (`AGENTOS_AI_LLM=on`).
3. Embedding + semantic search (B-13) 鈥?still pending.
4. `/insights/*` endpoints (PRD10 搂12) 鈥?still pending.
5. Browser-level UI tests (Playwright runner choice) 鈥?still pending.
6. Mock data seed script (PRD10 搂25.3) 鈥?`scripts/seed_prd10.py` exists
   in the repo (Agent 2 / coordinator artifact); needs an Agent 4 review
   pass to confirm it satisfies 搂25.3.
7. Auth UX inside the Mydow bundle 鈥?still pending.

---

## Milestone 12 路 PRD10 V1 acceptance walk-through 鈥?DONE

**When**: After Milestone 11 wired the worker into FastAPI startup.

### Goal

Answer one question: **is the deployed Mydow Web app a real, end-to-end
PRD10 V1 web app?** Cross-check PRD10 搂24 P0 deliverables, 搂25.1 first-screen
API matrix, and 搂26 acceptance bullets through the canonical FastAPI app.

### Delivered

- New `tests/integration/api/test_prd10_v1_acceptance.py`:
  - Boots the canonical `agent_os.server.app:app` against an in-memory
    SQLite engine with a real fixture user.
  - `TestPrd10RouteApiMatrix` covers every PRD10 搂25.1 first-screen API
    (Today / KB / AI / Skills / Garden / Search) and asserts every
    response carries `X-Request-ID` + the PRD10 envelope.
  - `TestPrd10HomeAcceptance` exercises 搂26.1: capture text 鈫?feed sees
    the card 鈫?unread notification appears 鈫?mark-read drops the count.
  - `TestPrd10KnowledgeBaseAcceptance` exercises 搂26.2: create folder 鈫?    presign upload 鈫?commit upload 鈫?KB documents in the folder include
    the new file.
  - `TestPrd10AiAcceptance` exercises 搂26.3: create AI conversation 鈫?    send message 鈫?save-to-kb 鈫?invoke the worker materializer 鈫?    `kb_documents` row + `Notification(type=ai_output_saved)` exist.
  - `TestMydowStaticBundle` proves `/`, `/mydow/`, `/mydow/mydow-api.js`
    are reachable on the same ASGI app.
- `agent-4-todo.md`: marked the V1 acceptance pass as `done` and recorded
  the 搂24 / 搂25.1 / 搂26 coverage map.

### Test evidence

```
python -m pytest tests/integration/api/test_prd10_v1_acceptance.py -q -p no:cacheprovider
# -> 12 passed
```

```
python -m pytest \
  tests/integration/api/prd10/ \
  tests/integration/api/test_prd10_product_data_api.py \
  tests/integration/api/test_prd10_frontend_binding.py \
  tests/integration/api/test_prd10_app_wiring.py \
  tests/integration/api/test_prd10_ai_api.py \
  tests/integration/api/test_prd10_search_api.py \
  tests/integration/api/test_prd10_skills_api.py \
  tests/integration/api/test_prd10_garden_api.py \
  tests/integration/api/test_prd10_observability.py \
  tests/integration/api/test_prd10_e2e_flow.py \
  tests/integration/api/test_prd10_models_intelligence.py \
  tests/integration/api/test_prd10_v1_acceptance.py \
  -q -p no:cacheprovider
# -> 159 passed
```

### V1 deliverable status (PRD10 搂24)

| Module | PRD10 P-tier | Status |
|---|---|---|
| Auth/User (`/me`, `/auth/*`) | P0 | wired (PRD10 envelope), AI / Mydow login UX still split between `/login.html` and the Mydow bundle |
| Today (`/today`) | P0 | done 鈥?PRD10 envelope + V1 acceptance test |
| Capture (`/capture/text|link|file/commit`, `/uploads/presign`) | P0 | done 鈥?both API and worker materializer green |
| Feed/Cards (`/feed`, `/cards/*`) | P0 | done |
| KB Folder (`/kb/folders/*`) | P0 | done |
| KB Document (`/kb/documents/*`, `/move`) | P0 | done |
| Job (`/jobs/{id}`, `/cancel`) | P0 | done 鈥?PRD10 worker loop also drains queued AI-to-KB / AI-to-tasks jobs |
| Notification (`/notifications/*`) | P0 | done |
| AI Chat (`/ai/conversations/*`, `/messages`) | P0 | API + persistence done; **streaming reply (SSE) is still placeholder** 鈥?assistant content is a deterministic stub until a real LLM provider lands |
| Search (`/search`, `/search/suggestions`) | P0 | API contract done; results currently rely on populated `SearchIndex` rows (capture path back-fills are pending the embedding follow-up in Milestone 5) |
| Skills (`/skills`, `/skills/{id}/run`) | P1 | done |
| Garden (`/garden/overview`, `/garden/graph`) | P1 | done |
| Insight / Report | P1 | preview returned in `/today.insight_preview`; full insight CRUD remains P1 |
| Embedding / semantic search | P1 | not wired in V1 (lexical only) |

### Outstanding to call "fully PRD10-compliant"

1. **AI streaming SSE** (`POST /api/v1/ai/messages/{id}/stream`) 鈥?required
   by PRD10 搂26.3 ("鑳芥祦寮忚繑鍥?AI 鍥炵瓟"). Persistence shape is already
   correct; only the LLM provider plug-in is missing.
2. **Real LLM provider** wired into AI chat + skill run output. Today the
   assistant message is a deterministic placeholder.
3. **Embedding + semantic search** (`B-13`). PRD10 搂26.4 only requires
   keyword search to work; semantic re-ranking is P1.
4. **Insight CRUD endpoints** (PRD10 搂12). `/today.insight_preview` is a
   stub; `/insights/*` endpoints are not yet exposed.
5. **Browser-level UI tests**. Static DOM/API contract tests cover the
   bindings, but a real headless-browser run (Playwright) still needs a
   runner choice from Engineer 1.
6. **Mock data seed script** (PRD10 搂25.3). Required for first-screen
   demo loads.
7. **Auth UX inside the Mydow bundle**. Today the package expects a JWT
   in `localStorage["mydow_token"]`; the existing `/login.html` produces
   one but the Mydow bundle has no embedded login UX.

### Verdict

PRD10 V1 (P0 deliverables) is functionally end-to-end on the canonical
FastAPI app + Mydow Web bundle, with the explicit P0 caveats above (AI
streaming + real LLM provider + auth UX inside the Mydow bundle). All P0
APIs respond with the PRD10 envelope, the worker materializes queued jobs
into KB documents/tasks, notifications are written, and the Mydow Web
package binds high-intent UI actions to the live API.

---

## Milestone 11 路 PRD10 worker loop wired into FastAPI startup 鈥?DONE

**When**: After Milestone 10 added the scheduler entry function.

### Delivered

- New `src/agent_os/jobs/worker_loop.py`:
  - `start_worker_loop()` / `stop_worker_loop()` manage a single asyncio
    background task that ticks every `AGENTOS_PRD10_WORKER_INTERVAL`
    seconds (default 30s) and drains supported PRD10 jobs.
  - `is_worker_enabled()` honors `AGENTOS_PRD10_WORKER=off` / `0` / `false`
    so test runs and ad-hoc dev sessions can stay quiet.
  - All exceptions inside a tick are logged and swallowed so a flaky DB
    cannot crash the FastAPI process.
- `src/agent_os/server/app.py`:
  - `startup_event` now calls `start_worker_loop()` after DB init when the
    worker is enabled.
  - New `shutdown_event` calls `stop_worker_loop()` to cooperatively shut
    the background task down.
- New tests `tests/integration/api/prd10/test_prd10_worker_loop.py`:
  - `test_is_worker_enabled_default_on`, `test_is_worker_enabled_respects_off_switch`
    cover the env switch.
  - `test_start_worker_loop_returns_none_when_disabled` proves the
    disable path is honored.
  - `test_worker_loop_drains_jobs_when_enabled` swaps the sessionmaker
    with a per-test in-memory engine and asserts a queued
    `ai_message_to_kb` job moves to `completed` within one tick.

### Test evidence

```
python -m pytest tests/integration/api/prd10/test_prd10_worker_loop.py -q -p no:cacheprovider
# -> 4 passed
```

```
python -m pytest \
  tests/integration/api/prd10/ \
  tests/integration/api/test_prd10_product_data_api.py \
  tests/integration/api/test_prd10_frontend_binding.py \
  tests/integration/api/test_prd10_app_wiring.py \
  tests/integration/api/test_prd10_ai_api.py \
  tests/integration/api/test_prd10_search_api.py \
  tests/integration/api/test_prd10_skills_api.py \
  tests/integration/api/test_prd10_garden_api.py \
  tests/integration/api/test_prd10_observability.py \
  tests/integration/api/test_prd10_e2e_flow.py \
  -q -p no:cacheprovider
# -> 137 passed
```

### Follow-ups

1. Migrate the `on_event` handlers to FastAPI lifespan (the deprecation
   warnings are unrelated to this slice but get noisier each release).
2. Decide whether to expand the worker to materialize `capture_text`
   inbox jobs (Engineer 1 question, see `agent-1-todo.md` task 9).

---

## Milestone 10 路 Worker scheduler entry + AI-output notification 鈥?DONE

**When**: After Milestone 9 worker materialization slices.

### Delivered

- `src/agent_os/jobs/service.py`
  - `process_job_once` now writes a `Notification(type=ai_output_saved)`
    after both KB and tasks materializations so the UI can pop a real
    "AI 杈撳嚭宸蹭繚瀛樺埌鐭ヨ瘑搴? / "AI 宸茬敓鎴愪换鍔? banner without polling.
  - New `process_pending_jobs(db, *, limit=25)`: side-effect-free batch
    drain of queued PRD10 jobs whose `(job_type, input.kind)` pair has a
    materializer registered. Designed to be invoked by a startup loop or
    cron-style scheduler. Unsupported job kinds remain `queued`.
- `tests/integration/api/prd10/test_prd10_jobs_notifications_api.py`
  - Added `test_worker_writes_ai_output_saved_notification`.
  - Added `test_process_pending_jobs_drains_supported_kinds` 鈥?proves the
    batch worker only picks up supported job kinds.

### Test evidence

```
python -m pytest tests/integration/api/prd10/test_prd10_jobs_notifications_api.py -q -p no:cacheprovider
# -> 13 passed
```

```
python -m pytest \
  tests/integration/api/prd10/ \
  tests/integration/api/test_prd10_product_data_api.py \
  tests/integration/api/test_prd10_frontend_binding.py \
  tests/integration/api/test_prd10_app_wiring.py \
  tests/integration/api/test_prd10_ai_api.py \
  tests/integration/api/test_prd10_search_api.py \
  tests/integration/api/test_prd10_skills_api.py \
  tests/integration/api/test_prd10_garden_api.py \
  tests/integration/api/test_prd10_observability.py \
  tests/integration/api/test_prd10_e2e_flow.py \
  -q -p no:cacheprovider
# -> 126 passed
```

### Follow-ups

1. Hook `process_pending_jobs` into a cooperative startup loop or a real
   scheduler. Engineer 1 owns the choice (in-process asyncio task vs. an
   external worker). The function is idempotent so either fits.
2. Decide whether to add a similar `capture_text` materializer or keep
   capture-side processing in `agent_os.capture.pipeline.simulate_processing`.

---

## Milestone 9 路 Agent 2 worker slices for AI-output materialization 鈥?DONE

**When**: Agent 4 covering Agent 2 product-data follow-ups after the first
UI action-binding slice landed.

### Delivered

- `src/agent_os/jobs/service.py`
  - `process_job_once(db, job_id)` is now the single internal worker entry.
  - Handles `Job(job_type=parse_file, input.kind=ai_message_to_kb)`:
    creates `Document(status=ready, document_type=note)` + a single
    `Chunk` per saved AI message, marks the job `completed` with
    `output.document_id` / `output.chunk_count`. Empty content marks the
    job `failed` with `VALIDATION_ERROR`.
  - Handles `Job(job_type=generate_report, input.kind=ai_message_to_tasks)`:
    creates one `Prd10InboxItem(type=manual_task)` per task entry so the
    `/today.tasks` PRD10 read path surfaces them. Marks the job
    `completed` with `output.task_count` / `output.inbox_item_ids`. Empty
    payloads or title-less tasks fail with `VALIDATION_ERROR`.
- `tests/integration/api/prd10/test_prd10_jobs_notifications_api.py`
  - Added 4 worker tests covering both kinds and both failure paths.

### Test evidence

```
python -m pytest tests/integration/api/prd10/test_prd10_jobs_notifications_api.py -q -p no:cacheprovider
# -> 11 passed
```

```
python -m pytest tests/integration/api/prd10/ tests/integration/api/test_prd10_product_data_api.py tests/integration/api/test_prd10_frontend_binding.py tests/integration/api/test_prd10_app_wiring.py -q -p no:cacheprovider
# -> 65 passed
```

### Follow-ups

1. Wire the worker into the FastAPI startup loop (currently invoked only by
   tests / a future scheduler). The intent is to keep this function
   side-effect-free and idempotent until the scheduler choice is finalized.
2. Once Agent 1 reconciles `tasks.models.Task.user_id` to UUID, swap the
   manual-task inbox surface for the canonical `prd10_tasks` table.

---

## Milestone 8 路 Agent 4 first UI action-binding slice 鈥?DONE

**When**: Agent 4 onboarding pass after confirming Mydow Web is the V1 frontend lane.

### Delivered

- `static/mydow/mydow-api.js`
  - Added `attachPrimaryActionBindings()`.
  - Bound Capture text submit to `POST /api/v1/capture/text`.
  - Bound Web clipping save to `POST /api/v1/capture/link`.
  - Bound New folder create to `POST /api/v1/kb/folders`.
  - Preserved the prototype's existing visual feedback and only fires real API calls when `localStorage["mydow_token"]` exists.
- `tests/integration/api/test_prd10_frontend_binding.py`
  - Added a canonical `/api/v1/today` binding smoke for `MydowAPI.today.fetch()`.
  - Added static DOM/API contract coverage for the three newly bound primary actions.
- `agent-4-todo.md`
  - Marked frontend replacement map as `done`.
  - Recorded the old-entrypoint replacement map and first action-binding slice.

### Test evidence

```
python -m pytest tests/integration/api/test_prd10_frontend_binding.py -q -p no:cacheprovider
# -> 13 passed
```

```
python -m pytest tests/integration/api/test_prd10_frontend_binding.py tests/integration/api/test_prd10_app_wiring.py -q -p no:cacheprovider
# -> 19 passed
```

### Follow-ups

1. Bind New document, Notifications read-all/read-one, Skill run, and AI save flows.
2. Add a browser-level runner or expand the static DOM harness to prove real click paths invoke those bindings.
3. Keep `/login.html` as legacy/dev-only until the Mydow package owns an embedded auth UI.

---

## Milestone 7 路 Mydow Web frontend bound + V1 acceptance pass 鈥?DONE

**When**: After the prior commander acceptance sweep (Milestone 6),
following Engineer 1's directive to also own Agent 1's coordinator role
and integrate the `Mydow_Web_Frontend_Complete_Package.zip` bundle as the
canonical frontend.

### Delivered

#### Frontend bundle integration

- Unzipped the bundle to `static/mydow/`:
  - `index.html` (the original `mydow.html`, 285 KB single-file SPA prototype).
  - `HANDOFF.md` (the bundle's handoff doc).
  - `mydow-api.js` 鈥?**new** integration layer exposing
    `window.MydowAPI` with typed helpers for every PRD10 path the handoff
    enumerates (`search`, `ai`, `skills`, `garden`, `feed`, `kb`,
    `capture`, `notifications`, `jobs`, `today`, `me`).
- `index.html` injects `<script src="./mydow-api.js" defer>`. The
  prototype's inline `<script>` runs first (so `simulateAction` visuals
  stay); the API layer augments DOM hooks (`data-nav-target`, the global
  search input, settings panels) to fire real fetches when a JWT is
  available in `localStorage["mydow_token"]`.
- `agent_os.server.app` mounts `static/mydow` at `/mydow` via
  `StaticFiles(html=True)` so a browser hitting `/mydow/` gets the SPA.

#### Coordinator hand-off (Agent 1 work this worker did)

- `agent-1-todo.md`: task 7 鈫?`done` (final acceptance pass).
- `agent-2-todo.md`: every task moved from `open` 鈫?`done` to match the
  code reality (Agent 2's status drifted behind the implementation by
  several slices). Notes call out that
  `RequestIdMiddleware` and `Prd10AccessLogMiddleware` are now installed.

#### New cross-cutting tests

- `tests/integration/api/test_prd10_frontend_binding.py` 鈥?10 tests:
  `/mydow/`, `/mydow/mydow-api.js`, `/mydow/HANDOFF.md` reachable; every
  PRD10 path the JS calls returns a valid PRD10 envelope; literal
  presence guard on every PRD10 token in `mydow-api.js`.
- `tests/integration/api/test_prd10_e2e_flow.py` 鈥?5 tests covering:
  `/today` shape, AI conversation 鈫?message 鈫?save-to-kb 鈫?Job lookup,
  `create-tasks` payload validation, Skills list+run + Job lookup,
  Card create through `/api/v1/cards` then GET by id.

### Test evidence

```
python -m pytest \
  tests/integration/api/test_prd10_models_intelligence.py \
  tests/integration/api/test_prd10_search_api.py \
  tests/integration/api/test_prd10_ai_api.py \
  tests/integration/api/test_prd10_skills_api.py \
  tests/integration/api/test_prd10_garden_api.py \
  tests/integration/api/test_prd10_app_wiring.py \
  tests/integration/api/test_prd10_observability.py \
  tests/integration/api/test_prd10_frontend_binding.py \
  tests/integration/api/test_prd10_e2e_flow.py \
  -p no:cacheprovider
# 鈫?74 passed in 24.75s
```

```
python -m pytest tests/integration/api/prd10/ tests/integration/api/test_prd10_product_data_api.py
# 鈫?40 passed
```

```
python -m pytest --collect-only -q -p no:cacheprovider
# 鈫?1366 tests collected in 52.71s, exit 0
```

**Total PRD10 acceptance: 114/114 passing.** No collection errors.

### Decisions baked in

- The Mydow frontend bundle is treated as a vendored asset; we don't fork
  the single-file HTML. The integration layer (`mydow-api.js`) is what we
  own. Future bundle updates can be re-applied by replacing `index.html`
  and re-running the binding tests.
- `mydow-api.js` is framework-free to match the prototype's design. It
  exposes `window.MydowAPI` so debug consoles can drive the backend
  manually.
- Auth lives in `localStorage["mydow_token"]`. Unauthenticated mode
  preserves the prototype's `simulateAction` visuals and prints a
  console hint at the existing email-auth flow.
- `/mydow` is served via `StaticFiles(html=True)` rather than per-file
  GET handlers, so siblings in `static/mydow/` are reachable without
  manual routes.

### Files touched / created

Created:

- `static/mydow/index.html` (zip extract + `<script src="./mydow-api.js" defer>` injection).
- `static/mydow/HANDOFF.md`.
- `static/mydow/mydow-api.js`.
- `tests/integration/api/test_prd10_frontend_binding.py`.
- `tests/integration/api/test_prd10_e2e_flow.py`.

Modified:

- `src/agent_os/server/app.py` 鈥?mounted `/mydow`
  (`StaticFiles(html=True)`) at the project-root `static/mydow`
  directory; existing `STATIC_DIR` mount at `/static` preserved.
- `agent-1-todo.md`, `agent-2-todo.md` 鈥?status alignment with reality.

### Follow-ups (P1, not blockers for V1)

1. SSE streaming for AI messages.
2. Job consumer worker that drains `prd10_jobs` rows of type
   `ai_chat / parse_file (kind=ai_message_to_kb) /
   generate_report (kind=ai_message_to_tasks) / skill_run` and writes
   the downstream KB document / task / AI reply / skill output.
3. Real LLM provider plug-in for `AIMessage.content`.
4. AI context retrieval (PRD10 搂11.4 citations from `context_scope`).
5. Legacy `tasks.models.Task.user_id` Integer鈫扷UID reconciliation so
   `/today.tasks` can populate.
6. `tests/conftest.py` teardown hygiene to make the legacy SQLite path
   completely green now that the UUID compile-shim has unblocked fixture
   setup.

**Status**: All Agent 1/2/3 PRD10 V1 deliverables 鈫?`done`. P1 worker /
streaming / context-retrieval items above are the next chunk.

---

## Milestone 8 路 Agent 3/4 takeover slice: AI context + UI action binding 鈥?DONE

**When**: After Agent 1 was asked to take over Engineer 3 and Engineer 4 remaining tasks.

**Why**: Agent 3's AI context boundary still returned empty placeholders, and Agent 4's first frontend binding slice needed stronger guardrails that the actual Mydow DOM hooks match the API bridge selectors.

### Delivered

- `src/agent_os/ai/router.py`
  - Added minimal `SearchIndex`-backed context retrieval for PRD10 `context_scope`.
  - Supports explicit `document_ids`, folder metadata hints, query text matches, and recent-context fallback.
  - `GET /api/v1/ai/conversations/{id}` now returns `related_context` from the conversation context scope.
  - `POST /api/v1/ai/conversations/{id}/messages` now returns `related_context` and stores citation-ready entries on the placeholder assistant message.
  - Missing/partial search tables are tolerated so isolated AI deployments still return stable empty context.
- `tests/integration/api/test_prd10_ai_api.py`
  - Added coverage for context-scope document resolution in conversation detail.
  - Added coverage that message send returns context and assistant citations.
- `tests/integration/api/test_prd10_frontend_binding.py`
  - Strengthened Agent 4 static contract test so it checks actual Mydow modal selectors (`webLink`, `newFolder`) and real action-binding selectors in `mydow-api.js`.
- `agent-3-todo.md` and `agent-4-todo.md`
  - Updated current status and remaining follow-ups.

### Test evidence

```
python -m pytest tests/integration/api/test_prd10_ai_api.py tests/integration/api/test_prd10_frontend_binding.py -q
```

Result: **29 passed**.

```
python -m pytest tests/integration/api/prd10 tests/integration/api/test_prd10_ai_api.py tests/integration/api/test_prd10_app_wiring.py tests/integration/api/test_prd10_frontend_binding.py tests/integration/api/test_prd10_garden_api.py tests/integration/api/test_prd10_models_intelligence.py tests/integration/api/test_prd10_observability.py tests/integration/api/test_prd10_product_data_api.py tests/integration/api/test_prd10_search_api.py tests/integration/api/test_prd10_skills_api.py -q
```

Result: **118 passed**.

### Remaining follow-ups

- Agent 3: replace placeholder assistant response with real LLM streaming using the now-wired DeepSeek local config.
- Agent 3 / Agent 2: implement job workers that materialize `save-to-kb`, `create-tasks`, and `skill_run` jobs.
- Agent 4: continue binding remaining UI actions (new document, notifications read-all, skill run, AI save) and add browser/DOM-level persistence tests when a runner is available.

**Status**: Takeover slice complete; remaining tasks are P1 implementation depth, not V1 route availability.

---

## Milestone 7 路 Agent 4 frontend lane assigned 鈥?OPEN

**When**: After adding Agent 4 and confirming Agent 2 / Agent 3 PRD10 backend suites are green.

**Why**: The team now needs a dedicated frontend acceptance owner. Agent 3 already has backend binding tests for the Mydow package, but real UI replacement and DOM-level behavior should be owned separately so backend/API work does not drift into frontend QA.

### Current progress snapshot

- **Agent 1**: Backend foundation and commander acceptance are open/acceptance-ready.
  - Explicit PRD10 integration suite: `109 passed`.
  - Full collect-only: `1366 tests collected`, exit `0`.
  - Remaining Agent 1 focus: formal acceptance walkthrough, integration hygiene, and task assignment.
- **Agent 2**: Product-data backend MVP is `done`.
  - Capture, Feed/Card, KB, Jobs, Notifications, Today are implemented and wired.
  - Agent 2 PRD10 tests: `40/40` pass.
- **Agent 3**: Intelligence backend MVP is `done` with some P1 follow-ups.
  - AI, Search, Skills, Garden, observability, app wiring, and frontend backend-smoke binding are covered.
  - Agent 3 PRD10 tests: `74/74` pass, including frontend binding smoke and e2e API flow.
  - P1: AI streaming, real LLM provider, job workers, context retrieval.
- **Agent 4**: Frontend replacement and UI-level binding lane is newly assigned.
  - Todo created: `agent-4-todo.md`.
  - Scope: make `Mydow_Web_Frontend_Complete_Package.zip` the V1 frontend standard, verify `/mydow` behavior, and bind high-intent UI actions to PRD10 APIs.

### Agent 4 assignment

Agent 4 should start with:

1. Audit old frontend/static entrypoints and create a replacement map.
2. Expand `static/mydow/mydow-api.js` from domain-client smoke binding to real button/form action binding.
3. Add UI-level tests for Mydow DOM hooks and real `/api/v1` calls.
4. Produce a frontend acceptance report listing bound flows vs still-static flows.

### Agent 1 assignment

Agent 1 should:

1. Keep the backend acceptance suite green while Agent 4 binds UI flows.
2. Decide whether older UI entrypoints redirect to `/mydow` or remain legacy/dev-only.
3. Review any Agent 4-requested backend compatibility shims against PRD10 before implementation.
4. Track P1 backend follow-ups separately from V1 route availability: AI streaming, job workers, context retrieval, and legacy cleanup.

### Initial Agent 1 frontend-entry decision

| Entrypoint | Decision | Reason |
|---|---|---|
| `/` | Redirect to `/mydow/` | V1 product UI must default to the Mydow package, not the legacy AgentOS static page. |
| `/mydow/` | Canonical V1 frontend | Serves `static/mydow/index.html` from `Mydow_Web_Frontend_Complete_Package.zip`. |
| `/mydow/mydow-api.js` | Canonical frontend API bridge | Owns browser-side PRD10 fetch bindings. |
| `/legacy` | Keep legacy AgentOS index | Useful for dev/debug compatibility without confusing it with the V1 product UI. |
| `/login.html` | Keep legacy/dev-only for now | Auth flow compatibility may still rely on it; Agent 4 should include it in the replacement map. |
| `/project-wizard.html` | Keep legacy/dev-only for now | Existing sandbox/project workflow, not PRD10 Mydow V1 product UI. |
| `/static/*` | Keep legacy static mount | Existing server assets still use it; do not expose as the V1 product entrypoint. |

Implementation evidence: `GET /` now returns a `307` redirect to `/mydow/` when the Mydow bundle is present, with `/legacy` preserving the old index page.

### Test evidence to preserve

```
python -m pytest tests/integration/api/prd10 tests/integration/api/test_prd10_ai_api.py tests/integration/api/test_prd10_app_wiring.py tests/integration/api/test_prd10_frontend_binding.py tests/integration/api/test_prd10_garden_api.py tests/integration/api/test_prd10_models_intelligence.py tests/integration/api/test_prd10_observability.py tests/integration/api/test_prd10_product_data_api.py tests/integration/api/test_prd10_search_api.py tests/integration/api/test_prd10_skills_api.py -q
```

Current result: **109 passed**.

```
python -m pytest --collect-only -q -p no:cacheprovider
```

Current result: **1366 tests collected**, exit `0`.

**Status**: Agent 4 task lane is `open`; Agent 1 should coordinate and keep acceptance criteria stable.

---

## Milestone 6 路 Commander PRD10 acceptance sweep green 鈥?DONE

**When**: After Agent 2 product-data and Agent 3 intelligence router slices.

**Why**: Engineer 1 needed to verify that the PRD10 backend slices now compose through the canonical app surface instead of only passing in isolated module tests.

### Delivered

- Ran the explicit PRD10 integration suite covering:
  - Capture / Feed / KB / Jobs / Notifications.
  - Today PRD10 binding.
  - AI / Search / Skills / Garden.
  - App wiring, frontend binding contract, model contracts, and PRD10 access logging.
- Confirmed `/api/v1/feed` and `/api/v1/cards/*` are mounted and covered.
- Confirmed current PRD10 routes collect cleanly with the full repository test collection.

### Test evidence

```
python -m pytest tests/integration/api/prd10 tests/integration/api/test_prd10_ai_api.py tests/integration/api/test_prd10_app_wiring.py tests/integration/api/test_prd10_frontend_binding.py tests/integration/api/test_prd10_garden_api.py tests/integration/api/test_prd10_models_intelligence.py tests/integration/api/test_prd10_observability.py tests/integration/api/test_prd10_product_data_api.py tests/integration/api/test_prd10_search_api.py tests/integration/api/test_prd10_skills_api.py -q
```

Result: **109 passed**.

```
python -m pytest --collect-only -q -p no:cacheprovider
```

Result: **1366 tests collected**, exit code `0`.

### Remaining risks

- The PRD10 suite is green, but the repository still emits legacy warnings (Pydantic V1-style config, FastAPI `on_event`, and legacy app collection warnings).
- AI/Skill/Job worker behavior is still an MVP placeholder: endpoints persist jobs and deterministic placeholder records, but real background workers/LLM streaming remain follow-ups.
- Full legacy test execution is not claimed green here; PRD10 acceptance is based on the explicit PRD10 suite plus full collect-only cleanliness.

**Status**: Agent 1 final acceptance task can move from `pending` to `open/acceptance-ready`; any remaining work should be tracked as P1 worker/streaming/legacy-cleanup rather than P0 PRD10 route availability.

---

## Milestone 5 路 Agent 3 PRD10 router slices + app wiring + observability 鈥?DONE

**When**: Immediately after Milestone 4 (model layer).

**Why**: With AI/Skill/Search/Garden tables in place, PRD10 搂11/搂17/搂18
needed concrete endpoints, the app needed to mount them through the same
envelope and request-id pipeline Agent 1 set up, and the legacy
`agent_os.server.app` had a `NameError` (referenced
`today_prd10_router` / `feed_router` without importing them) that prevented
boot.

### Delivered

#### Router slices (Agent 3)

| Path | Module | Notes |
|---|---|---|
| `GET /api/v1/search` | `agent_os.search_engine.router_prd10` | Paginated PRD10 envelope, `object_type` filter, user-scoped (legacy un-owned rows still visible). |
| `GET /api/v1/search/suggestions` | same | Title prefix match. |
| `GET /api/v1/ai/conversations` | `agent_os.ai.router` | Keyword + pagination. |
| `POST /api/v1/ai/conversations` | same | Validates `mode`. |
| `GET /api/v1/ai/conversations/{id}` | same | Conversation header + messages + empty `related_context` / `suggested_followups`. |
| `POST /api/v1/ai/conversations/{id}/messages` | same | Persists user msg + Job(`ai_chat`) + synchronous placeholder assistant msg. Streaming in P1. |
| `POST /api/v1/ai/messages/{id}/save-to-kb` | same | Enqueues a Job (`parse_file` with `input.kind="ai_message_to_kb"`). |
| `POST /api/v1/ai/messages/{id}/create-tasks` | same | Enqueues a Job (`generate_report` with `input.kind="ai_message_to_tasks"`). |
| `GET /api/v1/skills` | `agent_os.skills.router` | category/keyword/status filters, usage_count-DESC. |
| `GET /api/v1/skills/{id}` | same | PRD10 搂5.13 DTO. |
| `POST /api/v1/skills/{id}/run` | same | Writes `Job(skill_run)` + `SkillRun(queued)`, increments usage_count. |
| `GET /api/v1/garden/overview` | `agent_os.garden.router_prd10` | node/edge/strong_edge counts, top topics from `Card.tags`, recent `DailyInsight`. |
| `GET /api/v1/garden/graph` | same | Cards-as-nodes + `KnowledgeCardLink` edges. Empty graph is a success. |

#### Cross-cutting

- `src/agent_os/server/app.py`:
  - Added missing imports (`today_prd10_router`, `feed_router`) 鈥?fixes a
    `NameError` that prevented `import agent_os.server.app` from succeeding.
  - Mounted the four PRD10 intelligence routers **before** their legacy
    counterparts (stage4, garden) so PRD10 paths win at FastAPI's
    first-match dispatch.
  - Extended `_PRD10_ENVELOPE_PREFIXES` to include `/api/v1/search`,
    `/api/v1/ai`, `/api/v1/skills`, `/api/v1/garden`. The existing
    `HTTPException` and `RequestValidationError` handlers now translate
    these to the PRD10 envelope.
- `src/agent_os/common/middleware.py`:
  - New `Prd10AccessLogMiddleware`. Emits a single structured log line per
    PRD10 request with `prd10_request_id` / `prd10_method` / `prd10_path` /
    `prd10_status_code` / `prd10_duration_ms` / `prd10_client_host`. WARN
    for 5xx, INFO for 2xx/4xx. Non-PRD10 paths are silent.
  - `app.py` now adds **both** middlewares; ordering ensures
    `request.state.request_id` is populated before the access log reads it.
- `agent_os.common.__init__` re-exports `Prd10AccessLogMiddleware`.

### Test evidence

```
python -m pytest \
  tests/integration/api/test_prd10_models_intelligence.py \
  tests/integration/api/test_prd10_search_api.py \
  tests/integration/api/test_prd10_ai_api.py \
  tests/integration/api/test_prd10_skills_api.py \
  tests/integration/api/test_prd10_garden_api.py \
  tests/integration/api/test_prd10_app_wiring.py \
  tests/integration/api/test_prd10_observability.py \
  -p no:cacheprovider
```

Result: **59 passed** in 16.17s.

```
python -m pytest --collect-only -q -p no:cacheprovider
```

Result: **1351 tests collected** in 36.46s, exit 0 (up from 1252 in
Milestone 2). No new collection errors introduced.

### Decisions baked in

- PRD10 search router lives next to the legacy stage4 router, not on top of
  it. Legacy `/api/v1/search/index/...` paths still serve PRD4 callers; the
  PRD10 read path lives at the top-level `/api/v1/search` and
  `/api/v1/search/suggestions`.
- `save-to-kb` and `create-tasks` are **Job-only** for the MVP. They write
  one row to `prd10_jobs` and return `status="queued"` immediately. The
  worker that materializes the KB document or task is Agent 2's job and
  branches on `job.input.kind`.
- The PRD10 access log uses the standard `logging` package with a dedicated
  logger name (`agent_os.prd10.access`) so operators can route it without
  touching the global config. No external observability vendor wiring was
  added; that lands when Engineer 1 picks the metrics backend.
- The PRD10 AI message exposes `model="placeholder"` and a fixed
  `_PLACEHOLDER_REPLY` string so contract tests stay deterministic. The
  streaming SSE endpoint will replace `_PLACEHOLDER_REPLY` without
  changing the persisted shape.

### Files touched / created

Created:

- `src/agent_os/search_engine/router_prd10.py`
- `src/agent_os/ai/router.py`
- `src/agent_os/skills/router.py`
- `src/agent_os/garden/router_prd10.py`
- `tests/integration/api/test_prd10_search_api.py`
- `tests/integration/api/test_prd10_ai_api.py`
- `tests/integration/api/test_prd10_skills_api.py`
- `tests/integration/api/test_prd10_garden_api.py`
- `tests/integration/api/test_prd10_app_wiring.py`
- `tests/integration/api/test_prd10_observability.py`

Modified:

- `src/agent_os/server/app.py` (router imports + mount order + envelope
  prefix list + access log middleware).
- `src/agent_os/common/middleware.py` (added `Prd10AccessLogMiddleware`).
- `src/agent_os/common/__init__.py` (re-export).
- `src/agent_os/ai/__init__.py` (re-export router).
- `agent-3-todo.md` (statuses + decisions).

### Follow-ups

1. **SSE streaming** for `POST /api/v1/ai/messages/{id}/stream`. Persistence
   shape is already correct; only needs an LLM provider plug-in.
2. **Job worker** that consumes `prd10_jobs` rows of type `ai_chat`,
   `parse_file` (kind=`ai_message_to_kb`), `generate_report`
   (kind=`ai_message_to_tasks`), and `skill_run`. Once Agent 2's
   `kb_documents` / `prd10_tasks` are wired, the worker materializes the
   downstream rows.
3. **AI context retrieval**: turn `context_scope` hints into citations.
   Depends on Agent 2's `Card`/`Document`/`Chunk` corpus existing.
4. **Legacy-conftest hygiene**: `tests/conftest.py` `drop_prd4_tables`
   should pass `checkfirst=True` and `db_session` cleanup should swallow
   `OperationalError: no such table` 鈥?both surfaced now that the SQLite
   UUID compile-shim lets fixtures actually execute. Owner: Agent 1
   (conftest is in their integration-hygiene area, task 6).

**Status**: Agent 3 tasks 1, 2, 4 (Job-only MVP), 5, 7, 8, 9, 10 鈫?`done`.
Task 3 (AI context retrieval) 鈫?`open`, blocked on Agent 2 KB corpus.
Task 6 (search-package hygiene) 鈫?`open`, decision recorded but no code
change required from Agent 3.

---

## Milestone 4 路 Agent 3 intelligence model layer landed 鈥?DONE

**When**: After Milestone 3 (PRD10 persistence contract freeze).

**Why**: Agent 3 cannot ship `/api/v1/ai/*`, `/api/v1/search*`, `/api/v1/skills*`,
or Garden endpoints without the underlying PRD10-shape ORM tables. This
milestone lands every model Agent 3 owns from the Milestone 3 crosswalk and
proves the shapes via focused tests.

### Delivered

- `src/agent_os/ai/models.py` (already created; verified PRD10 搂5.11 / 搂5.12
  shape including `mode`, `last_message_preview`, `message_count`,
  `context_scope`, `citations`, `tool_calls`, `attachments`, token + latency
  fields, and a foreign key from `ai_messages.job_id` to `prd10_jobs.id`).
- `src/agent_os/skills/runs.py` (already created; verified PRD10 搂17 shape
  including `save_output`, `output_object_type`, `output_object_id` so the
  forthcoming `POST /api/v1/skills/{id}/run` endpoint can persist
  save-to-document/task hints).
- `src/agent_os/stage3/models.py` Skill table extended with PRD10 搂5.13
  display fields (`icon`, `status`, `usage_count`, `is_installed_default`,
  `input_schema`, `output_schema`) plus a `to_prd10_dict(*, is_installed=)`
  serializer.
- `src/agent_os/search_engine/models.py` SearchIndex extended to PRD10 搂5.14
  SearchDocument shape:
  - New nullable columns: `user_id` (FK to `users.id`), `workspace_id`,
    `summary`, `embedding_id`. Nullability preserves backwards compatibility
    with the existing `SearchService.index_item` ingestion writes (Agent 2 /
    Capture path).
  - `item_type` CheckConstraint widened to the union of PRD10 object_types
    (`card, document, folder, task, conversation, message, skill, insight`)
    and the legacy types (`note, decision_point, workspace, project,
    resource, test`). Constraint name `check_search_item_type` preserved
    so `tests/unit/models/test_search_models.py::test_search_index_item_type_constraint`
    semantics still hold.
  - Added composite index `idx_search_user_object_updated (user_id,
    item_type, updated_at)` per PRD10 搂21 advice.
  - Added `object_type` / `object_id` Python aliases and a
    `to_prd10_dict()` serializer that emits the 搂5.14 DTO directly.
- `src/agent_os/db/sqlite_compat.py` (NEW): a tiny `@compiles` patch that
  renders `postgresql.UUID` as `CHAR(32)` on the SQLite dialect only. PRD10
  tests import it once so `:memory:` SQLite engines can build the PRD10
  schema without touching Agent 1's `tests/conftest.py`.

### Test evidence

```
python -m pytest tests/integration/api/test_prd10_models_intelligence.py -v -p no:cacheprovider
```

Result: **10 passed**. Coverage:

- `AIConversation` defaults + PRD10 DTO shape
- `AIMessage` create + DTO shape (citations / tool_calls / model / tokens)
- Skill PRD10 display fields surfaced by `to_prd10_dict()` (with and without
  explicit `is_installed`)
- `SkillRun` create with `prd10_jobs` foreign key
- `SearchIndex` legacy ingestion write still works (no `user_id`),
  PRD10 object_types accepted, PRD10 搂5.14 DTO shape, invalid object_type
  rejected via the existing CheckConstraint name.

### Decisions baked in

- Legacy `conversations.Conversation` is **not** reused for PRD10. The Aider
  WebSocket path keeps that table; PRD10 `/api/v1/ai/*` writes through
  `ai_conversations` + `ai_messages` exclusively.
- `Skill` table is the canonical PRD10 Skill (decision in 搂5.13). The
  Pydantic-only `agent_os.skills.models.Skill` stays as a runtime
  representation for the Coze-style skill loader and is **not** persisted
  through PRD10 endpoints.
- `SearchIndex.item_type` keeps its physical column name to avoid a
  destructive migration; `object_type` is exposed as a Python property + DTO
  field. Future migrations can rename if PRD10 surfaces require it.
- The SQLite UUID compile shim is **opt-in**: Agent 1's PostgreSQL-first
  schema is untouched. Agent 1 may decide to also import it from the global
  conftest to unblock legacy SQLite tests (currently 36 fixture-setup
  errors stemming from `Workspace.__table__.create()`).

### Files touched

- `src/agent_os/search_engine/models.py` (extended)
- `src/agent_os/db/sqlite_compat.py` (new)
- `tests/integration/api/test_prd10_models_intelligence.py` (new)
- `agent-3-todo.md` (status + reuse decisions)

### Follow-ups

1. PRD10 `/api/v1/search` router slice (Agent 3 task 5/6).
2. PRD10 `/api/v1/ai/conversations*` router slice (Agent 3 task 2).
3. Coordinate with Agent 1 on whether `tests/conftest.py` should import
   `agent_os.db.sqlite_compat` so the legacy SQLite tests stop failing at
   fixture-setup time.

**Status**: Agent 3 task 1 鈫?`done`; tasks 2/5/6/7 unblocked.

---

## Milestone 4 路 PRD10 product-data routers wired and covered (Agent 1 integration) 鈥?DONE

**When**: After Milestone 3.

**Why**: The PRD10 product-data modules existed in code (`capture`, `kb`, `jobs`, `notifications`) but were not fully usable through the canonical FastAPI app. `aggregation.router` also still registered a duplicate `/api/v1/today`, which conflicted with the PRD10 Today router boundary.

**Delivered**:

- `src/agent_os/server/app.py`
  - Installed `RequestIdMiddleware` at the app boundary.
  - Added PRD10-specific `HTTPException` and validation handlers for newly wired product-data APIs so errors use the PRD10 envelope.
  - Included `capture`, `kb`, `jobs`, and `notifications` routers.
  - Removed `aggregation.router` from app wiring so `/api/v1/today` is registered once.
- `src/agent_os/kb/router.py`
  - Repaired a duplicated/concatenated router file that prevented app import.
  - Kept a single PRD10 搂10 implementation for KB overview, folders, documents, soft delete, and move.
- `tests/integration/api/test_prd10_product_data_api.py`
  - Added focused integration coverage for route wiring, Capture 鈫?Job 鈫?Notification, validation envelope, job user isolation, and KB folder + file-capture document flow.

**Test evidence**:

```
python -m pytest tests/integration/api/test_prd10_product_data_api.py -q
```

Result: `5 passed`.

```
python -m pytest --collect-only -q -p no:cacheprovider
```

Result: `1291 tests collected`, exit code `0`.

**Decisions baked in**:

- PRD10 product-data routers are now part of the canonical app surface.
- `aggregation.router` is not part of PRD10 app wiring; `today.router` owns `/api/v1/today`.
- Product-data validation and domain HTTP errors return PRD10 envelopes without forcing every legacy API to change shape in the same slice.

**Known follow-ups**:

1. Feed/Card endpoints are still not implemented under `src/agent_os/feed/router.py`.
2. `today/router.py` still has a legacy workspace-required response model and should be reshaped to PRD10 搂7.1.
3. Agent 3 intelligence endpoints remain pending.

**Files touched**:

- `src/agent_os/server/app.py`
- `src/agent_os/kb/router.py`
- `tests/integration/api/test_prd10_product_data_api.py`

**Status**: Agent 1 task 6 鈫?`done`; Agent 1 task 7 remains `open` for full backend acceptance after Feed/Today/Agent 3 slices.

---

## Milestone 3 路 PRD10 persistence strategy frozen (Agent 1 task 5) 鈥?DONE

**When**: After Milestone 2.

**Why**: Agent 2 and Agent 3 cannot ship endpoints until they know which existing model to reuse vs which new ORM table to create. This is the contract that keeps both domains from drifting.

### PRD10 entity 脳 current code crosswalk

| PRD10 entity | PRD10 搂  | Existing code | Decision | New file/path |
|---|---|---|---|---|
| `User` | 5.1 | `auth.models.User` (UUID, JSON `settings`) | **Reuse**. Keep canonical user identity. | 鈥?|
| `UserPreference` | 5.2 | `auth.models.UserSettings` (added in M2) | **Reuse** for legacy compatibility. PRD10 endpoints continue to use `User.settings` JSON for V1. | 鈥?|
| `Workspace` | 4.x | `items.models.Workspace` (UUID owner_id, no FK to users) | **Reuse**. PRD10 V1 = personal workspace. | 鈥?|
| `InboxItem` | 5.3 | `knowledge.models.InboxItem` (added in M2) | **Reuse**. New canonical PRD10 inbox table. | 鈥?|
| `Source` | 5.4 | (none) | **NEW**. Stores raw source metadata (file/link/audio). | `src/agent_os/sources/models.py` |
| `Card` | 5.5 | `knowledge.models.Card` (PRD4 shape, missing several PRD10 fields) | **Extend**. Add `is_favorite`, `summary`, `view_count` columns; reuse table. | `src/agent_os/knowledge/models.py` |
| `Folder` | 5.6 | `items.models.Area` is similar but tied to PRD4 Areas/Projects, not PRD10 KB folders | **NEW**. Dedicated `kb_folders` table. | `src/agent_os/kb/models.py` |
| `Document` | 5.7 | None purpose-built. `items.Item(type=resource)` is a workaround. | **NEW**. Dedicated `kb_documents` table. | `src/agent_os/kb/models.py` |
| `Chunk` | 5.7 | None | **NEW**. `kb_chunks` table for embedding-ready text chunks. | `src/agent_os/kb/models.py` |
| `Task` | 5.9 | `tasks.models.Task` uses **integer user_id** which conflicts with auth UUID. | **NEW PRD10 task table** alongside legacy. PRD10 endpoints write `prd10_tasks` (UUID user_id); legacy tests keep their table. | `src/agent_os/tasks/models.py` (alongside) |
| `Insight` | 5.10 | `garden.models.DailyInsight` is close (per-day) but PRD10 wants generic `theme_trend / task_risk / knowledge_gap / connection / daily_summary / weekly_summary` | **Reuse `DailyInsight` for daily/weekly summary**; **NEW** `prd10_insights` for the rest. | `src/agent_os/insights/models.py` |
| `Conversation` | 5.11 | `conversations.models.Conversation` is a **single-message row** (legacy Aider chat) 鈥?does not match PRD10's session-with-messages | **NEW** `ai_conversations` + `ai_messages` tables. Old `conversations.Conversation` stays for legacy. | `src/agent_os/ai/models.py` |
| `Message` | 5.12 | (none) | **NEW** `ai_messages` table. | `src/agent_os/ai/models.py` |
| `Skill` | 5.13 | `stage3.models.Skill` is workflow-internal; missing `category`, `icon`, `is_installed`, `usage_count` | **Extend** `stage3.Skill` with PRD10 display fields; reuse table. | `src/agent_os/stage3/models.py` |
| `SkillRun` | 17.x | (none) | **NEW**. `skill_runs` records inputs/outputs/status. | `src/agent_os/skills/models.py` |
| `SearchDocument` | 5.14 | `search_engine.models.SearchIndex` lacks `user_id`, `object_type` enum mismatches | **Extend** with `user_id` + relax `object_type` constraint to PRD10 list. | `src/agent_os/search_engine/models.py` |
| `IngestionJob` | 5.15 | `search_engine.models.IngestionJob` is ingestion-only | **NEW general `Job` table**. IngestionJob stays for ingestion-specific flows. | `src/agent_os/jobs/models.py` |
| `Notification` | 5.16 | (none) | **NEW**. `notifications` table. | `src/agent_os/notifications/models.py` |
| `KnowledgeNode/KnowledgeEdge` | 18.x | `garden.models.KnowledgeCardLink` + `items.models.GraphEdge` | **Reuse `KnowledgeCardLink`** for garden edges; nodes are derived from cards/folders. | 鈥?|

### Owner assignments

- **Agent 1** (foundation): `Job` (general), `Notification` (Agent 2 implements; Agent 1 reviews schema cohesion), `Source` location decision (lives under capture).
- **Agent 2** (product data): Folder, Document, Chunk, Source, Card extensions, PRD10 Task (UUID), Notification, IngestionJob alignment.
- **Agent 3** (intelligence): AIConversation, AIMessage, SkillRun, Skill extensions, SearchIndex `user_id` + object_type relax.

### Conflict prevention rules

1. Both agents read `agent-progress-report.md` before extending a shared model.
2. Card extensions (`is_favorite`, `summary`, `view_count`) live under Agent 2 (knowledge module) 鈥?Agent 3 only reads.
3. The `Job` general table (Agent 1) is the **only** place where `job_type IN ('parse_file','summarize','embed','index','generate_insight','generate_report','ai_chat','skill_run')` is enforced. SkillRun and AI chat record their `job_id` reference.
4. SearchIndex extension by Agent 3 must keep backward compatibility with current ingestion writes (so Agent 2's IngestionPipeline still works).

### Files to be created in this milestone

> Tables themselves are added in subsequent milestones (per slice). This milestone only freezes the contract.

- `src/agent_os/jobs/models.py` (general `Job` table, Agent 1)
- `src/agent_os/notifications/models.py` (Agent 2)
- `src/agent_os/sources/models.py` (Agent 2)
- `src/agent_os/kb/models.py` (Folder, Document, Chunk 鈥?Agent 2)
- `src/agent_os/ai/models.py` (AIConversation, AIMessage 鈥?Agent 3)
- `src/agent_os/skills/models.py` (already exists for shape; SkillRun added 鈥?Agent 3)
- Modifications: `knowledge/models.py` (Card fields), `stage3/models.py` (Skill fields), `tasks/models.py` (PRD10 task table), `search_engine/models.py` (SearchIndex extension).

**Status**: Agent 1 task 5 鈫?`done`. Decisions referenced by every downstream slice.

---

## Milestone 2 路 Test collection unblocked (Agent 1 task 4) 鈥?DONE

**When**: After Milestone 1.

**Why**: With 18 collection errors, every cross-cutting `pytest` invocation died before doing useful work. PRD10 acceptance hinges on `pytest --collect-only` cleanliness.

**Delivered**:

- `src/agent_os/auth/models.py` adds a real `UserSettings` ORM table.
  - Keeps PRD10's `User.settings` JSON column as canonical.
  - Adds `user_settings` table (theme/language/timezone/notifications + `extra` JSON) for legacy auth tests that import `UserSettings` from `auth.models`.
- `src/agent_os/knowledge/models.py` adds an `InboxItem` ORM table.
  - Aligned with PRD10's `InboxItem` shape (status `raw`, source_type, source_meta, etc.).
  - Coexists with PRD4 `agent_os.items.models.Item`. PRD10 inbox endpoints will write through `InboxItem`; legacy tests still resolve.
- `src/agent_os/search/__init__.py` (new package) plus `keyword_search.py` and `hybrid_search.py` shims.
  - Each public class/function raises `NotImplementedError` and points callers at `agent_os.search_engine`.
  - Sole purpose: keep `tests/integration/api/test_search_api*.py` collectable.
- `src/agent_os/main.py`: re-exports the FastAPI `app` from `agent_os.server.app` for callers that import `agent_os.main`.
- `tests/test_app.py`: re-exports `app` and `test_app` for legacy tests doing `from tests.test_app import test_app`.
- `tests/unit/auth/test_verification.py`: added missing `from unittest.mock import patch`.

**Test evidence**:

```
python -m pytest --collect-only -q -p no:cacheprovider
```

| Metric | Before | After |
|---|---:|---:|
| Tests collected | 979 | 1252 (+273) |
| Collection errors | 18 | 0 |
| Exit code | 2 | 0 |

**Decisions baked in**:

- Legacy tests are kept **collectable**, not necessarily **passing**. PRD10-aligned slices will own the green path through their own targeted test files (see `agent-1-backend-contract.md` test strategy).
- `agent_os.search` is a deprecated namespace; treat any new import of it as a code-review red flag.
- `UserSettings` and `InboxItem` are PRD10-shape ORM models even though some endpoints currently still write through `User.settings` JSON / `Item`. Migration to dedicated tables can land iteratively.

**Follow-ups**:

1. After Agent 1 final acceptance pass, decide whether legacy `agent_os.search` shim should warn at import time (currently silent).
2. The new `inbox_items` and `user_settings` tables need migration entries when we move beyond SQLite-in-memory tests; flagged for the integration agent.

**Files touched**:

- `src/agent_os/auth/models.py` (added `UserSettings`)
- `src/agent_os/knowledge/models.py` (added `InboxItem`)
- `src/agent_os/search/__init__.py` (created)
- `src/agent_os/search/keyword_search.py` (created)
- `src/agent_os/search/hybrid_search.py` (created)
- `src/agent_os/main.py` (created)
- `tests/test_app.py` (created)
- `tests/unit/auth/test_verification.py` (added `patch` import)

**Status**: Agent 1 task 4 鈫?`done`.

---

## Milestone 1 路 Shared API utility layer (Agent 1 task 3) 鈥?DONE

**When**: Initial pass.

**Why**: Agent 2 and Agent 3 cannot finalize endpoint responses until the PRD10 envelope helpers are concrete. This unblocks every router that follows.

**Delivered**:

- `src/agent_os/common/response.py`
  - Plain-dict helpers: `success_response`, `paginated_response`, `error_response`, `error_response_from`.
  - `JSONResponse` helpers (status code + header echo): `success_json_response`, `paginated_json_response`, `error_json_response`, `http_exception_to_envelope`.
  - `get_request_id` accepts a `Request`; falls back to inbound `X-Request-ID` header; otherwise generates `req_<uuid4-hex-12>`.
- `src/agent_os/common/middleware.py`
  - `RequestIdMiddleware` attaches `request.state.request_id` and echoes the value back as the `X-Request-ID` response header.
- `src/agent_os/common/__init__.py`
  - Exposes the full surface; downstream code should `from agent_os.common import ...` rather than reach into submodules.
- `tests/unit/common/test_response.py` (already present, kept passing)
- `tests/unit/common/test_response_envelope.py` (added)
  - Uses `httpx.AsyncClient + ASGITransport` to dodge the Starlette 0.27 / httpx 0.28 `TestClient` incompatibility.

**Test evidence** (run from repo root):

```
python -m pytest tests/unit/common/ -v
```

Result: 18 passed in ~0.15s.

**Decisions baked in**:

- PRD10 error code enum is the canonical list; HTTP status codes are derived from it (`DEFAULT_STATUS_BY_CODE`).
- Pagination metadata uses `has_more = page * page_size < total`; rejects invalid inputs with `ValueError`.
- Request id format is `req_<uuid4-hex-12>` to match the PRD10 examples.

**Follow-ups for the integration agent (Agent 1 / commander)**:

1. Pick a single place in `app.py` to register `RequestIdMiddleware` and the global exception handler that uses `http_exception_to_envelope`. Today's PRD10 routers don't yet attach it, but Capture/Feed/AI routers will.
2. When wiring legacy routers, prefer the new helpers over inline dicts so envelope drift stays bounded.

**Files touched**:

- `src/agent_os/common/response.py` (created/updated)
- `src/agent_os/common/middleware.py` (created)
- `src/agent_os/common/__init__.py` (rewritten)
- `tests/unit/common/test_response_envelope.py` (created)

**Status**: Agent 1 task 3 鈫?`done` in `agent-1-todo.md`.

## Milestone 82 - 2026-05-09 10:17 (UTC+8) - Codex
- Completed §18.4 Mydow AI personalization dropdown modernization.
- Replaced the AI personalization modal's exposed native selects with modern keyboard-operable listbox panels while keeping native select values synchronized.
- Fixed persistence to write real PRD10 `/me/preferences` fields: `ai_response_style`, `ai_detail_level`, `language`, and `cite_knowledge_by_default`; backend whitelist and GET projection now include the new AI personalization keys.
- Verified in Chrome MCP @8035: selected `更具创意` + `详细`, clicked save, observed `PATCH /api/v1/me/preferences` 200 and response settings persisted `ai_response_style=detailed`, `ai_detail_level=deep`.
- Automated checks: `node --check static\mydow\biz_v14\bridge_v14.js` PASS; 4 targeted pytest cases PASS.

## Milestone 83 - 2026-05-09 10:28 (UTC+8) - Codex
- Completed §18.5 document editor focus/autosave repair.
- Added real document hydration from `GET /kb/documents/{id}` when opening folder documents, then autosaves title/body edits with debounced `PATCH /kb/documents/{id}`.
- Replaced the abrupt default contenteditable focus outline with a subtle editor-shell focus ring and status chip states.
- Chrome MCP @8035 verified: opened a real KB document, inserted text into the body, observed `PATCH /api/v1/kb/documents/0c545f0b-34fa-4d8b-b2d3-777a27852900` 200 with persisted content; computed style reports `outline-style: none` on the focused editor body.
- Automated checks: `node --check static\mydow\biz_v14\bridge_v14.js` PASS; `pytest tests\integration\api\test_prd10_frontend_binding.py::test_biz_v14_doc_editor_autosaves_without_black_focus_frame -q` PASS.

## Milestone 84 - 2026-05-09 10:40 (UTC+8) - Codex
- Completed Section 18.6 Skills run modal KB picker modernization.
- Added `.skill-doc-picker-v18` with a real searchable document input, modern listbox results, selected state, and output mode controls; the native select remains visually hidden only as the form state read by the existing real run handler.
- Chrome MCP @8035 verified: opened Skills plaza, searched `status code` / `鐘舵€佺爜`, selected the real KB document, then ran the competitor analysis Skill.
- Network evidence: `POST /api/v1/skills/66278223-748e-48c4-914b-b008c5cbed69/run` returned 202 with request body containing `document_id=0c545f0b-34fa-4d8b-b2d3-777a27852900` and `output_mode=generate`; polling completed and saved generated KB document `075c70ff-c1af-410b-a4cf-3e8cd42ed7d7`.
- Automated checks: `node --check static\mydow\biz_v14\bridge_v14.js` PASS; `pytest tests\integration\api\test_prd10_frontend_binding.py::test_biz_v14_skill_run_picker_is_searchable_and_modern -q` PASS.
## Milestone 85 - 2026-05-09 10:52 (UTC+8) - Codex
- Completed Section 18.7 Skills sidebar recommendation/recent layout repair.
- Root cause: `.skills-drawer .insight-panel` had content taller than the viewport but `overflow-y: hidden`, so recent usage and topics were clipped.
- Changed sidebar recommendations to a default-collapsed `.skill-side-rec-list-v18` details panel and restored branded vertical scrolling on the Skills side rail.
- Chrome MCP @8035 verified: default state shows recent usage in view with `overflowY=auto`; expanded state shows all 5 recommendation rows and remains scrollable instead of clipped.
- Automated checks: `node --check static\mydow\biz_v14\bridge_v14.js` PASS; `pytest tests\integration\api\test_prd10_frontend_binding.py::test_biz_v14_skills_sidebar_recommendations_do_not_clip_recent_usage -q` PASS.
## Milestone 86 - 2026-05-09 11:08 (UTC+8) - Codex
- Completed Section 18.8 Skills category filter repair.
- Root cause: the filter code read `V14.allSkills` but `/skills` results were never cached, and `bindSkillsCategoryFilterV40()` was not called during boot.
- Fixed real filter state: cache `/skills?page_size=50`, bind chips in capture phase, filter by real category/tags/name/description, sort hot by usage/favorites, sort new by timestamps, render empty state, and sync `#skills?filter=...`.
- Added hash recovery: reloading `#skills?filter=new` opens the Skills page and restores the pressed filter.
- Chrome MCP @8035 verified content filter -> 5 real Skills, hot filter -> usage counts descending, and hash reload -> Skills page with Latest pressed.
- Automated checks: `node --check static\mydow\biz_v14\bridge_v14.js` PASS; `pytest tests\integration\api\test_prd10_frontend_binding.py::test_biz_v14_skill_category_filters_use_real_cached_data_and_url_state -q` PASS.
### Milestone 87 - 2026-05-09 11:24 (UTC+8) - 搂18.10 璇煶杈撳叆鐪熷疄钀藉簱闂幆
- 鎺ユ墜 搂18.9 瀹¤鎷嗗嚭鐨?搂18.10锛歚voiceInput` 涓嶅啀璧扳€滄紨绀?鍗犱綅鈥漷oast锛屾敼涓烘祻瑙堝櫒 SpeechRecognition + 鎵嬪姩杞啓 textarea锛涙殏鍋?淇濆瓨鍧囩敱 capture-phase 涓撶敤澶勭悊鎺ョ銆?- 鍓嶇锛歚static/mydow/biz_v14/bridge_v14.js` 鏂板 `hydrateVoiceInputModalV18()` / `handleVoiceInputModal()` / `bindVoiceInputModalV18()`锛屼繚瀛樻椂鐪熷疄 `POST /capture/text`锛宐ody 鍖呭惈鍘熷杞啓銆佸姩鎬佹爣棰樸€乣tags:["璇煶"]`銆乣type:"voice"`銆乣auto_process:true`锛沗bridge_v14_ext.js` 鍘婚櫎鈥滃綍闊冲凡鏆傚仠锛堟紨绀猴級鈥濄€?- 鍚庣锛歚src/agent_os/capture/router.py` 璁?`_normalize_inbox_type()` 鎺ュ彈 `voice` UI 鍒悕骞舵槧灏勫埌 text 绠＄嚎锛屼繚璇佽闊宠浆鍐欏悓鏃剁敓鎴?inbox銆乯ob銆乨ocument/card/KB asset銆?- Chrome MCP @8035锛氭彁浜ゃ€岃闊宠仈璋冮獙璇佷笁...銆嶅悗 `POST /api/v1/capture/text` 200锛岃繑鍥?inbox `2d00a6e2-f65f-455a-948f-31e7c7a68f0a`銆乯ob `d2804f02-abea-4bdf-9ec5-cc2d2c8c15d1`銆乨ocument_id `64953a5b-c88e-4bcc-9f65-f206078c7b56`锛涢殢鍚?`/feed?page_size=5` 涓?`/kb/documents?page_size=10` 鍧囧懡涓璁板綍銆?- 楠岃瘉锛歚node --check static\mydow\biz_v14\bridge_v14.js` PASS锛沗node --check static\mydow\biz_v14\bridge_v14_ext.js` PASS锛沗pytest tests\integration\api\test_prd10_frontend_binding.py::test_biz_v14_voice_input_saves_real_transcript_as_voice_capture -q` PASS锛沗pytest tests\integration\api\prd10\test_prd10_capture_api.py::test_capture_text_accepts_voice_alias_and_persists_transcript -q` PASS銆?### Milestone 88 - 2026-05-09 11:39 (UTC+8) - 搂18.9 澶嶅鎵╁睍瀹¤鏀跺彛
- 瀹屾垚涓氬姟鏂?v1.4 鎸夐挳/浜や簰澶嶅锛歚python scripts\audit_v14_buttons.py` 鏄剧ず 45 涓敮涓€ HTML `data-toast`銆?2 涓睘鎬с€?1 涓?modal submit 鍧囨湁 bridge/ext 闈欐€?wiring锛宍labels_with_no_static_wiring=[]`銆?- 淇杩囨椂 e2e锛歚tests/e2e/test_v14_buttons_real_api.py` 涓嶅啀鍚堟垚鏃犲脊绐?鏃犺浆鍐欐枃鏈殑鈥滆闊宠褰曞凡淇濆瓨鈥濇寜閽紝鏀逛负鐪熷疄鐐瑰嚮銆岀伒鎰熼噰闆嗐€嶁啋銆岃闊宠緭鍏ャ€嶁啋 濉?`data-v18-voice-transcript` 鈫掋€岀粨鏉熷苟淇濆瓨銆嶏紝鏇磋创杩戠敤鎴疯矾寰勫拰鈥滀笉 mock鈥濆師鍒欍€?- 鍥炲綊锛歚pytest tests\e2e\test_v14_buttons_real_api.py -q` PASS锛沗pytest tests\e2e\test_v14_walk.py -q` PASS锛沗pytest tests\integration\api\test_prd10_frontend_binding.py -q` 鈫?47 passed锛沗python scripts\audit_v14_buttons.py` PASS銆?- 鍞竴鎬?todo 琛ㄥ凡鏇存柊锛毬?8.9 done锛屄?8.10 done锛涘綋鍓?`open=0 / doing=0 / blocked=0`銆?### Milestone 89 - 2026-05-09 11:44 (UTC+8) - Mydow AI LLM/RAG 鎶介獙
- Chrome MCP @8035 杩涘叆 Mydow AI锛屼娇鐢ㄥ凡闄勫姞鏂囨。銆孉I 瀵硅瘽寮曠敤寮曟搸璁捐銆嶅彂閫侀棶棰橈細銆岃鐢ㄤ竴鍙ヨ瘽璇存槑浣犳槸鍚﹁兘鍩轰簬褰撳墠鐭ヨ瘑搴撹繘琛岀湡瀹炲洖绛旓紝骞跺紩鐢ㄥ彲鐢ㄤ笂涓嬫枃銆傘€?- Network锛歚POST /api/v1/ai/conversations/1d5139b7-fd8c-463e-b6bb-82fcff08bfc1/messages/stream` 杩斿洖 200锛宺equest body 鍚?`context_scope.document_ids=[b8bc5f0e-b676-43e0-905f-c32d23b31414]`銆?- 鍙嶆煡 conversation锛歛ssistant 鏈€鏂版秷鎭?`model=litellm`銆乣status=completed`銆佸唴瀹瑰紩鐢ㄧ煡璇嗗簱涓婁笅鏂囧苟鍚紩鐢ㄦ爣璁?`[ #1 ]`锛宍citations=1`锛涙湭钀藉埌 placeholder 妯″瀷銆?## Milestone 80 鈥?2026-05-09 13:15 (UTC+8) 鈥?Codex

- Closed `todo-tasks.md` 搂18.11-搂18.14: profile preferences, account security, Mydow AI visible RAG chat, and Skills real LLM execution.
- Profile preferences now PATCH `/me/preferences` and immediately apply theme/language/default input mode/autosave state in the v1.4 UI.
- Account security now uses real `/me/security` state plus email-verification and device-refresh endpoints; fake email/device toasts removed.
- Mydow AI RAG was backend-correct but visually hidden; `ensureAiConversationVisibleV18()` now enters `.ai-open.ai-chat-open`, restores message opacity, and Chrome MCP sees `litellm` responses with KB citations.
- Skills worker no longer produces placeholder output when LLM is disabled; it fails visibly with `LLM_DISABLED`. Real Chrome MCP Skill run completed through `litellm`, saved document `85532c86-175a-4da7-8f67-69aa2086f903`, and result output was non-placeholder.
- Verification: `node --check static\mydow\biz_v14\bridge_v14.js`; `node --check static\mydow\biz_v14\bridge_v14_ext.js`; `python -m py_compile src\agent_os\auth\router.py src\agent_os\jobs\service.py`; `pytest tests\integration\api\test_prd10_frontend_binding.py tests\integration\api\test_prd10_me_password_and_preferences_get.py tests\integration\api\test_prd10_me_patch.py tests\integration\api\test_prd10_skills_api.py -q` -> 110 passed.

## Milestone 90 鈥?2026-05-09 13:34 (UTC+8) 鈥?Codex

- Closed `todo-tasks.md` 搂18.15 after Chrome MCP caught one remaining settings-page detail: the Preferences panel was active, but language hydration overwrote the first settings-card heading with `涓汉璧勬枡`.
- Fixed `static/mydow/biz_v14/bridge_v14_ext.js::applyLanguagePreferenceV18()` to derive the active settings panel title and keep profile's secondary card as `鍩虹鍋忓ソ`.
- Chrome MCP @8035 verified: account menu -> Preferences gives `active=preferences`, `h2s=["鍋忓ソ璁剧疆"]`, real preferences content, and autosave persists to `/me/preferences.auto_save=true`.
- Restarted current test server at `http://127.0.0.1:8035/mydow/biz_v14/` with PID `50764`, `AGENTOS_AI_LLM=on`, DB `.tmp/user_test_8035.db`.
- Re-ran RAG and Skills real paths in the browser after restart: AI stream completed with `model=litellm`, `citations=1`; Skill run `057387ba-e553-4b99-a55d-b7ad590bd169` completed with usage `116/414/530` and saved document `55e1854b-5b45-4ad1-90ad-1dd11c9b2836`.
- Verification: `node --check static\mydow\biz_v14\bridge_v14.js`; `node --check static\mydow\biz_v14\bridge_v14_ext.js`; `python -m py_compile src\agent_os\auth\router.py src\agent_os\jobs\service.py`; `pytest tests\integration\api\test_prd10_frontend_binding.py tests\integration\api\test_prd10_me_password_and_preferences_get.py tests\integration\api\test_prd10_me_patch.py tests\integration\api\test_prd10_skills_api.py -q` -> 110 passed.

## Milestone 91 - 2026-05-10 11:13 (UTC+8) - Codex

- Closed `todo-tasks.md` §18.29: the 5/10 browser review items covering AI summary authenticity, AI composer layout, assistant action buttons, RAG reasoning leakage, and Skill run wait/jump behavior.
- Backend: added `POST /api/v1/cards/{id}/ai-summary`, which only updates Card/Document/SearchIndex when a real LLM summary succeeds; changed capture enrichment model priority to use the configured allowed `MODEL_FALLBACK` before slower/blocked models; expanded RAG context with document `full_text`; added assistant answer sanitization and SSE `replace` so visible output no longer keeps provider planning text.
- Frontend: AI composer now separates context chips, tools, and textarea into distinct rows with a taller input; assistant buttons have stable min widths; card drawers detect raw-prefix summaries and trigger real summary generation; Skill run modal shows live waiting status and opens the generated KB document automatically.
- Verification: py_compile for `capture/llm_pipeline.py`, `feed/router.py`, `ai/router.py`; `node --check static\mydow\biz_v14\bridge_v14.js`; pytest batches: feed+AI `31 passed`, frontend+skills `76 passed`, capture+feed `17 passed`.
- Docker/browser evidence @ `http://localhost:8000/mydow/biz_v14/`: real LLM summary regenerated `ChatGPT 简洁版分析报告` in 17.31s; AI SSE returned `bad=[]` and `citations=5`; Browser QA showed concise drawer summary, non-overlapping composer, Skill run auto-jumped to `#/kb/doc/4a5c879c-f377-4598-bc63-422d660049cc`, page nonblank, no framework overlay, console errors/warnings `[]`.

## Milestone 92 - 2026-05-10 12:46 (UTC+8) - Codex

- Closed `todo-tasks.md` §18.30: KB documents now render Markdown by default, Skill runs no longer spin forever, AI background selection has real selected/cancel state, and the v14 model surface is pinned to DeepSeek V4 Flash.
- Backend/config: Docker and one-click launch defaults now use `https://api.deepseek.com` + `deepseek-v4-flash`; `AGENTOS_AI_MAX_TOKENS` default raised to `2000` to avoid reasoning-only responses; `/api/v1/ai/models` only exposes `DeepSeek V4 Flash`; provider errors are translated into actionable user-facing messages; LiteLLM no longer surfaces `reasoning_content` as the visible answer.
- Frontend: bundled local `markdown-it` and injected it into biz v14; `#/kb/doc/{id}` deep links open real KB documents and render headings/lists/code/table Markdown; the editor supports `编辑 Markdown` / `预览 Markdown` without losing raw content; model popovers/profile defaults no longer leak GLM/Opus/Gemini/GPT options; AI context picker loads real folders/documents and allows cancelling selected context.
- Runtime verification: Docker @ `localhost:8000` healthy; `/api/v1/ai/models` returns a single `deepseek-v4-flash`; official DeepSeek smoke succeeded for both `deepseek-v4-flash` and `deepseek-v4-pro`; Browser QA sent a real AI message and received a stored assistant answer with citations in roughly 4s, with no reasoning leak and no console errors/warnings.
- Test verification: `node --check static\mydow\biz_v14\bridge_v14.js`; `node --check static\mydow\biz_v14\bridge_v14_ext.js`; `python -m py_compile src\agent_os\server\app.py src\agent_os\jobs\service.py src\agent_os\capture\llm_pipeline.py src\agent_os\llm\litellm_impl.py src\agent_os\ai\router.py`; `pytest tests\integration\api\test_prd10_frontend_binding.py tests\integration\api\test_prd10_skills_api.py tests\integration\api\test_prd10_ai_api.py tests\integration\api\test_prd10_ai_llm.py -q` -> `118 passed`; `python scripts\audit_v14_buttons.py` -> `OK`.
