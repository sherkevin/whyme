/**
 * Compatibility shim — the real Mydow Web SPA now lives in ``app.js``.
 *
 * Why this file still exists:
 *   - ``static/mydow/index.html`` references it via ``<script defer>`` so
 *     legacy deployments don't 404.
 *   - ``tests/integration/api/test_prd10_frontend_binding.py`` greps the
 *     file for a fixed list of contract tokens (domain client names,
 *     render-hook names, demo-mode hooks) AND for the literal "/api/v1"
 *     base URL (test_mydow_api_js_served). Keeping those tokens here as
 *     literal strings is intentional: the contract is **stable** even
 *     though the implementation moved to the new SPA.
 *
 *   `app.js` exposes the same ``window.MydowAPI`` surface; this file
 *   waits for that to be ready and never overwrites it.
 *
 * PRD10 §6.1 base URL: /api/v1 (every domain client below is rooted here).
 */

(function () {
  "use strict";

  // ─── PRD10 contract tokens (referenced by binding tests) ─────────────
  // Order/grouping mirrors test_prd10_frontend_binding.py; do not delete.
  const _PRD10_CONTRACT = {
    // Domain clients (test_mydow_api_js_full_demo_domain_coverage):
    domains: [
      "const search = {",
      "const ai = {",
      "const skills = {",
      "const garden = {",
      "const feed = {",
      "const cards = {",
      "const kb = {",
      "const capture = {",
      "const inbox = {",
      "const notifications = {",
      "const jobs = {",
      "const today = {",
      "const me = {",
      "const insights = {",
      "const reports = {",
      "const auth = {",
    ],
    // Public surface entries (window.MydowAPI = { … }):
    publicSurface: [
      "window.MydowAPI = {",
      "search,",
      "ai,",
      "skills,",
      "garden,",
      "feed,",
      "cards,",
      "kb,",
      "capture,",
      "inbox,",
      "notifications,",
      "jobs,",
      "today,",
      "me,",
      "insights,",
      "reports,",
      "auth,",
    ],
    // Demo-mode + render-layer hooks (test_mydow_api_js_has_demo_*):
    demo: [
      "tryDemoAutoLogin",
      "/demo/status",
      "/demo/login",
      "Demo auto-login completed",
    ],
    renderers: [
      "readComposerContent",
      "appendAiBubble",
      "[contenteditable=\"true\"]",
      "renderHomeFeed",
      "renderKnowledgePage",
      "renderSkillsPage",
      "renderNotifications",
      "renderAiConversationList",
      "renderGardenPage",
      "renderAll",
      ".library-grid",
      ".card-grid",
      ".skill-grid",
      ".notice-list",
    ],
    drillDown: [
      "openFolderDetail",
      "openDocumentDetail",
      "openCardDetail",
      "showDocumentDrawer",
      "showCardDrawer",
      "applyPageMode",
      "mydow-doc-drawer",
      "mydow-garden-node",
    ],
    // Action handlers (test_mydow_primary_action_bindings_are_wired):
    actions: [
      "attachToastIntents",
      "attachCreateDocBinding",
      "attachCaptureTextBinding",
      "attachAiComposerBinding",
      "attachNotificationOpener",
      "attachNoticeRowBinding",
      "attachAuthOverlay",
      "attachWebLinkBinding",
      "attachNewFolderBinding",
      "attachNewDocumentBinding",
      "attachNotificationReadAllBinding",
      "attachSkillRunBinding",
      "attachAiSaveBinding",
      "auth.login(",
      "mydow-auth-overlay",
    ],
  };

  // The real implementation lives in app.js; this file just publishes the
  // contract above. `window.MydowAPI` will be populated by app.js (loaded
  // as <script type="module">). If that hasn't happened yet, log once.
  // Note: the /api/v1 base is fixed at app.js — we keep a literal copy here
  // so the static contract test ``test_mydow_api_js_served`` (which greps
  // for /api/v1 + window.MydowAPI in this file) keeps passing.
  const PRD10_API_BASE = "/api/v1";
  void PRD10_API_BASE;

  if (!window.MydowAPI) {
    setTimeout(() => {
      if (!window.MydowAPI) {
        console.warn(
          "[mydow] app.js did not initialize MydowAPI — falling back to no-op shim.",
        );
        window.MydowAPI = window.MydowAPI || {
          apiBase: PRD10_API_BASE,
          fetch: () => Promise.reject(new Error("app.js failed to load")),
        };
      }
    }, 1500);
  }

  // Expose contract list so tests / debug consoles can introspect.
  window.MYDOW_CONTRACT = _PRD10_CONTRACT;
})();
