// =============================================================================
// Mydow business-prototype <→> PRD10 backend bridge.
//
// The single-file static prototype in ``index.html`` wires every button to a
// local ``simulateAction(...)`` stub so the UI looks alive while staying
// API-free. This bridge re-attaches the high-intent buttons to real
// ``/api/v1/*`` endpoints (auth, capture, feed, ...). Other widgets keep their
// inline simulation until the corresponding §15 task lands.
//
// Loaded as ``<script type="module" src="./bridge.js"></script>`` from
// ``static/mydow/biz/index.html`` AFTER the inline IIFE block, so we can clone
// elements to detach the simulation handlers, then attach real ones.
// =============================================================================

const API_BASE = "/api/v1";
const TOKEN_KEY = "mydow_biz_token";

// ─────────────────────────────────────────────  Tiny toast (independent) ───
function makeToaster() {
  const stack =
    document.querySelector("[data-toast-stack]") ||
    document.querySelector(".toast-stack");
  return (message, kind = "info") => {
    if (!stack) {
      console.info("[Mydow]", message);
      return;
    }
    // Match the prototype's ``.toast`` two-column grid (26px icon / text) so the
    // message stays on a single line. Without an explicit icon child the text
    // falls into the 26px column and wraps vertically (the original bug seen in
    // the screenshot from §15.3).
    const node = document.createElement("div");
    node.className = `toast toast-${kind}`;
    const icon = document.createElement("span");
    icon.style.cssText =
      "display:inline-grid;place-items:center;width:26px;height:26px;border-radius:9px;background:rgba(112,140,255,0.12);color:#5b78ff;font-weight:700;font-size:12px;";
    icon.textContent =
      kind === "error" ? "!" : kind === "warning" ? "△" : "✓";
    const text = document.createElement("span");
    text.textContent = message;
    node.append(icon, text);
    stack.appendChild(node);
    window.setTimeout(() => {
      node.animate(
        [
          { opacity: 1, transform: "translateY(0)" },
          { opacity: 0, transform: "translateY(8px)" },
        ],
        { duration: 220, easing: "ease-out" },
      ).onfinish = () => node.remove();
    }, 2200);
  };
}

const toast = makeToaster();

// ─────────────────────────────────────────────  §7.30 layer markers  ─────
//
// The business prototype opens modals/drawers inside its inline IIFE by
// toggling the native ``hidden`` property. Chrome sweeps and a11y checks need a
// stable marker that says which layer is currently visible, so mirror that
// state onto ``document.documentElement`` and the visible layer itself.
const _LAYER_MARKERS = {
  observer: null,
  raf: 0,
};

function _visibleLayer(selector) {
  return Array.from(document.querySelectorAll(selector)).find(
    (layer) => !layer.hidden && !layer.hasAttribute("hidden"),
  );
}

function _currentPageMode() {
  const shell = document.querySelector(".page");
  if (!shell) return "";
  const modes = [
    ["knowledge", "knowledge-open"],
    ["folder", "folder-open"],
    ["ai", "ai-open"],
    ["garden", "garden-open"],
    ["skills", "skills-open"],
    ["notifications", "notifications-open"],
    ["insightsFull", "insights-full-open"],
    ["profile", "profile-open"],
    ["doc", "doc-open"],
  ];
  const active = modes.find(([, className]) => shell.classList.contains(className));
  return active ? active[0] : "home";
}

function syncLayerStateMarkers() {
  const root = document.documentElement;
  const pageMode = _currentPageMode();
  const modal = _visibleLayer(".surface-layer[data-modal]");
  const drawer = _visibleLayer(".drawer-layer[data-drawer]");

  if (pageMode) {
    root.dataset.page = pageMode;
    root.setAttribute("data-page-open", pageMode);
  } else {
    delete root.dataset.page;
    root.removeAttribute("data-page-open");
  }

  document.querySelectorAll(".surface-layer[data-modal-open]").forEach((layer) => {
    if (layer !== modal) layer.removeAttribute("data-modal-open");
  });
  document.querySelectorAll(".drawer-layer[data-drawer-open]").forEach((layer) => {
    if (layer !== drawer) layer.removeAttribute("data-drawer-open");
  });

  if (modal) {
    const name = modal.dataset.modal || "open";
    root.dataset.modal = name;
    root.setAttribute("data-modal-open", name);
    modal.setAttribute("data-modal-open", "true");
    document.body.classList.add("is-modal-open");
  } else {
    delete root.dataset.modal;
    root.removeAttribute("data-modal-open");
    document.body.classList.remove("is-modal-open");
  }

  if (drawer) {
    const name = drawer.dataset.drawer || "open";
    root.dataset.drawer = name;
    root.setAttribute("data-drawer-open", name);
    drawer.setAttribute("data-drawer-open", "true");
    document.body.classList.add("is-drawer-open");
  } else {
    delete root.dataset.drawer;
    root.removeAttribute("data-drawer-open");
    document.body.classList.remove("is-drawer-open");
  }
}

function scheduleLayerStateSync() {
  if (_LAYER_MARKERS.raf) return;
  _LAYER_MARKERS.raf = window.requestAnimationFrame(() => {
    _LAYER_MARKERS.raf = 0;
    syncLayerStateMarkers();
  });
}

function attachLayerStateMarkers() {
  if (_LAYER_MARKERS.observer) {
    syncLayerStateMarkers();
    return;
  }

  _LAYER_MARKERS.observer = new MutationObserver((mutations) => {
    if (
      mutations.some((mutation) => {
        const target = mutation.target;
        return (
          (mutation.type === "attributes" &&
            mutation.attributeName === "hidden" &&
            target instanceof Element &&
            target.matches(".surface-layer[data-modal], .drawer-layer[data-drawer]")) ||
          mutation.type === "childList"
        );
      })
    ) {
      scheduleLayerStateSync();
    }
  });

  _LAYER_MARKERS.observer.observe(document.body, {
    attributes: true,
    attributeFilter: ["hidden"],
    childList: true,
    subtree: true,
  });

  document.addEventListener("click", scheduleLayerStateSync, true);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") scheduleLayerStateSync();
  }, true);
  syncLayerStateMarkers();
}

// ─────────────────────────────────────────────  §14.12 storage helpers  ───
//
// Wrap every ``localStorage`` access in a try/catch with an in-memory
// ``_MEMORY_STORAGE`` fallback. Browsers may throw on:
//   * Safari Private Browsing (storage quota = 0)
//   * Quota exceeded (QuotaExceededError / NS_ERROR_DOM_QUOTA_REACHED)
//   * User-disabled storage (cookie blockers, enterprise policies)
//   * Cross-origin iframe sandboxes
//
// When localStorage is unavailable the helpers transparently keep state
// in the in-memory Map for the lifetime of the page so that demo
// auto-login + favourite-skills + bridge boot still work for a single
// session, just without persistence across reloads.

const _MEMORY_STORAGE = new Map();

function _getMemoryFallback(key) {
  return _MEMORY_STORAGE.has(key) ? _MEMORY_STORAGE.get(key) : null;
}

function safeLocalStorageGet(key) {
  try {
    const v = window.localStorage.getItem(key);
    if (v !== null && v !== undefined) return v;
    return _getMemoryFallback(key);
  } catch (e) {
    return _getMemoryFallback(key);
  }
}

function safeLocalStorageSet(key, value) {
  // Always update the in-memory mirror so the next ``get`` returns the
  // fresh value even if persistence fails.
  _MEMORY_STORAGE.set(key, String(value));
  try {
    window.localStorage.setItem(key, value);
    return true;
  } catch (e) {
    if (
      e &&
      (e.name === "QuotaExceededError" ||
        e.name === "NS_ERROR_DOM_QUOTA_REACHED" ||
        e.code === 22)
    ) {
      console.warn(
        `[Mydow] localStorage quota exceeded for key="${key}"; in-memory fallback active`,
      );
    } else {
      console.warn(`[Mydow] localStorage.setItem("${key}") failed`, e);
    }
    return false;
  }
}

function safeLocalStorageRemove(key) {
  _MEMORY_STORAGE.delete(key);
  try {
    window.localStorage.removeItem(key);
    return true;
  } catch (e) {
    return false;
  }
}

// ─────────────────────────────────────────────  apiFetch / token  ──────────
function token() {
  return safeLocalStorageGet(TOKEN_KEY) || "";
}

function setToken(value) {
  if (value) safeLocalStorageSet(TOKEN_KEY, value);
  else safeLocalStorageRemove(TOKEN_KEY);
}

async function apiFetch(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    "X-Client-Platform": "web",
    "X-Client-Version": "1.0.0",
  };
  const tok = token();
  if (tok) headers.Authorization = `Bearer ${tok}`;

  // §15.28 (b) — Browser HTTP cache was returning stale GET responses
  // across reseed / user switch flows (e.g. /skills boot rendered cards
  // with skill_ids from a previous demo session, then POST /skills/{id}/run
  // hit "Skill not found"). PRD10 envelopes are not idempotent across
  // reseed; opt every API request out of HTTP cache. POST/PUT/DELETE are
  // already non-cacheable but keep the same store policy for symmetry.
  const cacheMode = options.cache || "no-store";

  const resp = await fetch(`${API_BASE}${path}`, {
    ...options,
    cache: cacheMode,
    headers: { ...headers, ...(options.headers || {}) },
    body:
      options.body && typeof options.body === "object"
        ? JSON.stringify(options.body)
        : options.body,
  });

  let payload = null;
  try {
    payload = await resp.json();
  } catch {
    payload = null;
  }

  if (!resp.ok) {
    const msg =
      (payload && payload.error && payload.error.message) ||
      (payload && payload.message) ||
      `${resp.status} ${resp.statusText}`;
    const err = new Error(msg);
    err.status = resp.status;
    err.payload = payload;
    throw err;
  }
  return payload;
}

// ─────────────────────────────────────────────  Demo auto-login  ───────────
async function ensureSession() {
  if (token()) return true;
  try {
    // /demo/status returns the bare ``{enabled, email}`` shape today (it predates
    // the PRD10 envelope rollout). Accept both shapes so it keeps working when
    // the route migrates to ``success_response``.
    const status = await apiFetch("/demo/status");
    const enabled = !!(
      (status && status.data && status.data.enabled) ||
      (status && status.enabled)
    );
    if (!enabled) {
      console.info("[Mydow] demo mode off; skipping auto-login");
      return false;
    }
    const login = await apiFetch("/demo/login", { method: "POST" });
    const accessToken =
      (login && (login.access_token || (login.data && login.data.access_token))) ||
      "";
    if (!accessToken) throw new Error("demo login returned no access_token");
    setToken(accessToken);
    return true;
  } catch (e) {
    console.error("[Mydow] auto-login failed", e);
    toast(`自动登录失败: ${e.message}`, "error");
    return false;
  }
}

// ─────────────────────────────────────────────  Capture helpers  ───────────
function clearComposer(el) {
  if (!el) return;
  if ("value" in el) el.value = "";
  else el.textContent = "";
}

async function submitCaptureText(content) {
  const trimmed = (content || "").trim();
  if (!trimmed) {
    toast("请先输入想法或选择输入方式", "warning");
    return null;
  }
  const r = await apiFetch("/capture/text", {
    method: "POST",
    body: { content: trimmed, auto_process: true },
  });
  return r;
}

// ─────────────────────────────────────────────  Feed renderer (§15.4)  ─────
//
// Replace the prototype's 4 hardcoded ``article.idea-card`` items with real
// data from ``/api/v1/feed``. We snapshot the prototype's hand-crafted thumb
// SVGs once and reuse them as a rotation pool so cards still look polished
// (cover-image upload is §15.7 and not part of V1).

const FEED_PAGE_SIZE = 8;
let _thumbPool = null;

function thumbPool() {
  if (_thumbPool) return _thumbPool;
  const grid = document.querySelector(".recent-view .card-grid");
  if (!grid) {
    _thumbPool = [];
    return _thumbPool;
  }
  _thumbPool = [...grid.querySelectorAll(".thumb-svg")].map((svg) =>
    svg.outerHTML,
  );
  if (_thumbPool.length === 0) _thumbPool = [""];
  return _thumbPool;
}

function pickThumb(idx) {
  const pool = thumbPool();
  return pool[idx % pool.length] || "";
}

function relTime(ts) {
  if (!ts) return "";
  const t = typeof ts === "string" ? new Date(ts) : ts;
  if (Number.isNaN(t.getTime())) return "";
  const delta = (Date.now() - t.getTime()) / 1000;
  if (delta < 60) return "刚刚";
  if (delta < 3600) return `${Math.floor(delta / 60)} 分钟前`;
  if (delta < 86400) return `${Math.floor(delta / 3600)} 小时前`;
  if (delta < 86400 * 7) return `${Math.floor(delta / 86400)} 天前`;
  return t.toLocaleDateString("zh-CN", { month: "long", day: "numeric" });
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value == null ? "" : String(value);
  return div.innerHTML;
}

function renderCardArticle(item, idx) {
  const article = document.createElement("article");
  article.className = "idea-card";
  article.dataset.cardId = item.id || "";
  const tags = (item.tags || []).slice(0, 3);
  article.innerHTML = `
    <div class="thumb">
      ${
        item.is_favorite
          ? '<span class="favorite"><svg class="icon" style="width:15px;height:15px"><use href="#icon-star" /></svg></span>'
          : ""
      }
      ${pickThumb(idx)}
    </div>
    <div class="card-body">
      <h2 class="card-title">${escapeHtml(item.title || "未命名")}</h2>
      <div class="tags">
        ${tags
          .map((t) => `<span class="tag">${escapeHtml(t)}</span>`)
          .join("")}
      </div>
      <div class="card-meta">
        <span>${escapeHtml(relTime(item.created_at))}</span>
        <svg class="icon save-icon" style="width:17px;height:17px" data-bookmark="${item.id}"><use href="#icon-bookmark" /></svg>
      </div>
    </div>
  `;
  return article;
}

async function loadFeedIntoRecentView() {
  const grid = document.querySelector(".recent-view .card-grid");
  if (!grid) return;
  // Prime the thumb pool from the prototype's static cards before we wipe them.
  thumbPool();
  try {
    const r = await apiFetch(`/feed?page_size=${FEED_PAGE_SIZE}`);
    const items = (r && r.data && r.data.items) || [];
    grid.innerHTML = "";
    if (items.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty-feed-msg";
      empty.style.cssText =
        "grid-column: 1 / -1; padding: 24px; text-align: center; color: rgba(108,124,153,0.85); font-size: 13px;";
      empty.textContent = "还没有灵感，先在上面输入框写一条吧。";
      grid.appendChild(empty);
      return;
    }
    items.forEach((item, idx) => grid.appendChild(renderCardArticle(item, idx)));
  } catch (e) {
    console.error("[Mydow] feed load failed", e);
    toast(`加载灵感失败: ${e.message}`, "error");
  }
}

function listenForFeedRefresh() {
  window.addEventListener("mydow:capture-completed", () => {
    loadFeedIntoRecentView();
    // §15.5: capture changes today_capture_count + content distribution +
    // recent list; re-hydrate the right-side cards so the panels stay
    // consistent with the freshly-saved item.
    refreshTodayInsights().catch(() => {});
    refreshHomeContentDistribution().catch(() => {});
    refreshHomeRecentList().catch(() => {});
    refreshHomeAiActivity().catch(() => {});
    // §15.5j: capture also bumps today/month totals on the right-rail
    // top stat cards (今日新增灵感 / 本月灵感捕捉 / AI 周报总结).
    refreshHomeRightRailStatCards().catch(() => {});
    refreshKbOverviewCard().catch(() => {});
  });
}

// ─────────────────────────────────────────────  Wire .capture send  ────────
//
// The inline IIFE at the bottom of index.html attaches a click handler to
// every ``.send-button`` that calls ``simulateAction``. Cloning the node
// drops those listeners before we re-attach the real handler.
function rebindCaptureSubmit() {
  const captureSection = document.querySelector(".capture");
  if (!captureSection) return;
  const textarea = captureSection.querySelector("textarea");
  const submit = captureSection.querySelector(".send-button");
  if (!submit || !textarea) return;

  const fresh = submit.cloneNode(true);
  submit.replaceWith(fresh);

  fresh.addEventListener("click", async () => {
    const content = (textarea.value || "").trim();
    if (!content) {
      toast("请先输入想法或选择输入方式", "warning");
      return;
    }
    fresh.disabled = true;
    fresh.classList.add("is-loading");
    try {
      const resp = await submitCaptureText(content);
      clearComposer(textarea);
      const inboxId =
        (resp && resp.data && (resp.data.inbox_item_id || resp.data.id)) || "";
      toast("灵感已保存，最近捕捉已刷新", "success");
      window.dispatchEvent(
        new CustomEvent("mydow:capture-completed", {
          detail: { inboxItemId: inboxId, content },
        }),
      );
      // §15.4: refresh feed counts after capture completes.
      refreshFeedCounters().catch(() => {});
      refreshTodayInsights().catch(() => {});
      // §15.5: real-time refresh the right-side insight drawers so the
      // 今日捕捉 stat-value bumps, AI 助理活跃度 re-derives, content
      // distribution re-balances, and 最近使用 list shows the new card.
      refreshHomeContentDistribution().catch(() => {});
      refreshHomeAiActivity().catch(() => {});
      refreshHomeRecentList().catch(() => {});
    } catch (e) {
      toast(`保存失败: ${e.message}`, "error");
    } finally {
      fresh.disabled = false;
      fresh.classList.remove("is-loading");
    }
  });
}

// ─────────────────────────────────────────────  §15.18 profile chip  ───────
//
// Replace the sidebar user-chip ("你好，Allison" / "Pro Plan") with the
// PRD10 §5.1 ``/me`` payload so the demo account's actual name and plan
// show up. This is the smallest visible win for §15.18 ("个人中心").
async function refreshProfileChip() {
  let me;
  try {
    me = await apiFetch("/me");
  } catch (e) {
    console.warn("[Mydow] /me lookup failed", e);
    return null;
  }
  const data = (me && me.data) || me || {};
  // §15.23 — cache the resolved /me payload so the settings page can
  // hydrate toggle/segmented-control states from real settings JSON
  // every time the user switches between the 4 tabs.
  window._BIZ_ME_CACHE = data;
  const name =
    data.name ||
    (data.email && String(data.email).split("@")[0]) ||
    "demo";
  const plan = data.plan || "free";
  const avatar = data.avatar_url || "";

  const chip = document.querySelector(".account[data-open-profile]");
  if (chip) {
    const strong = chip.querySelector(".account-info strong");
    const span = chip.querySelector(".account-info span");
    if (strong) strong.textContent = `你好，${name}`;
    const planLabel = plan === "pro" ? "Pro Plan" : plan === "team" ? "Team Plan" : "Free Plan";
    if (span) span.textContent = planLabel;
    chip.dataset.userPlan = plan;
    chip.dataset.userName = name;
    if (avatar) {
      const av = chip.querySelector(".avatar");
      if (av) {
        av.style.backgroundImage = `url("${avatar}")`;
        av.style.backgroundSize = "cover";
      }
    }
  }
  // Topbar avatar mirrors the same data.
  const topAvatar = document.querySelector("[data-top-profile]");
  if (topAvatar) {
    topAvatar.setAttribute("aria-label", `${name} 个人头像`);
    if (avatar) {
      topAvatar.style.backgroundImage = `url("${avatar}")`;
      topAvatar.style.backgroundSize = "cover";
    }
  }
  // §15.18 — also rewrite the .profile-main section so opening the
  // 个人中心 page shows the demo account's real identity.
  hydrateProfileMain(data);
  return data;
}

function hydrateProfileMain(me) {
  const main = document.querySelector(".profile-main");
  if (!main || !me) return;
  const name = me.name || (me.email ? String(me.email).split("@")[0] : "demo");
  const planRaw = me.plan || "free";
  const planLabel =
    planRaw === "pro" ? "Pro Plan 用户"
      : planRaw === "team" ? "Team Plan 用户"
        : "Free Plan 用户";

  const h3 = main.querySelector(".profile-info h3");
  if (h3) h3.textContent = name;
  const p = main.querySelector(".profile-info p");
  if (p) p.textContent = me.email || "";
  const tag = main.querySelector(".profile-info .tag");
  if (tag) tag.textContent = planLabel;
  const avatar = main.querySelector(".profile-info .avatar.large");
  if (avatar && me.avatar_url) {
    avatar.style.backgroundImage = `url("${me.avatar_url}")`;
    avatar.style.backgroundSize = "cover";
    avatar.setAttribute("aria-label", `${name} 头像`);
  }
  main.dataset.userId = me.id || "";
  main.dataset.userPlan = planRaw;
}

// ─────────────────────────────────────────────  §15.17 unread badge  ───────
//
// Render an unread count badge on the topbar bell so the static prototype
// shows live data instead of a hard-coded "5". Uses the same selector the
// inline IIFE uses for the icon button.
async function refreshUnreadBadge() {
  let payload;
  try {
    payload = await apiFetch("/notifications/unread-count");
  } catch (e) {
    console.warn("[Mydow] unread-count failed", e);
    return null;
  }
  const data = (payload && payload.data) || payload || {};
  const count = Number(
    data.count != null ? data.count : data.unread_count != null ? data.unread_count : 0,
  );
  const bell = document.querySelector("[data-open-notifications]");
  if (!bell) return count;
  let badge = bell.querySelector(".bridge-unread-badge");
  if (count > 0) {
    if (!badge) {
      badge = document.createElement("span");
      badge.className = "bridge-unread-badge";
      // Inline minimal styling so we don't fight the prototype's CSS.
      badge.style.cssText = [
        "position:absolute",
        "top:-2px",
        "right:-2px",
        "min-width:16px",
        "height:16px",
        "padding:0 4px",
        "border-radius:8px",
        "background:#ff5775",
        "color:#fff",
        "font-size:10px",
        "line-height:16px",
        "font-weight:700",
        "text-align:center",
        "pointer-events:none",
      ].join(";");
      bell.style.position = bell.style.position || "relative";
      bell.appendChild(badge);
    }
    badge.textContent = count > 99 ? "99+" : String(count);
  } else if (badge) {
    badge.remove();
  }
  bell.dataset.unreadCount = String(count);
  return count;
}

// ─────────────────────────────────────────────  §15.5 today insights  ─────
//
// Pull `/today` once on boot to surface the demo account's real "今日捕捉"
// counter on the right insight column (replacing the prototype's
// hard-coded number when the matching DOM is found). Keeps the failure
// silent — the prototype's static markup is the safe fallback.
async function refreshTodayInsights() {
  let payload;
  try {
    payload = await apiFetch("/today");
  } catch (e) {
    console.warn("[Mydow] /today failed", e);
    return null;
  }
  const data = (payload && payload.data) || payload || {};
  const stats = data.stats || {};
  // PRD10 §7.1 stats schema: today_capture_count / pending_task_count /
  // knowledge_items_count / weekly_growth_rate. Older clients used
  // ``today_captures`` / ``captures_today``; we keep them as fallback so
  // that future schema-rename doesn't break the bridge.
  const captureToday = Number(
    stats.today_capture_count != null
      ? stats.today_capture_count
      : stats.today_captures != null
        ? stats.today_captures
        : stats.captures_today != null
          ? stats.captures_today
          : 0,
  );
  const pendingTasks = Number(stats.pending_task_count || 0);
  const kbItems = Number(stats.knowledge_items_count || 0);

  // 1) Generic ``[data-stat=*]`` slots (forward-compat marker).
  document.querySelectorAll('[data-stat="today-captures"]').forEach((n) => {
    n.textContent = String(captureToday);
    n.dataset.bridgeBound = "true";
  });
  document.querySelectorAll('[data-stat="pending-tasks"]').forEach((n) => {
    n.textContent = String(pendingTasks);
    n.dataset.bridgeBound = "true";
  });
  document.querySelectorAll('[data-stat="kb-items"]').forEach((n) => {
    n.textContent = String(kbItems);
    n.dataset.bridgeBound = "true";
  });

  // 2) Direct DOM rewrite of the prototype's static stat cards. The biz
  //    HTML hard-codes ``<h3>今日灵感捕捉</h3><span class="stat-value">16</span>``
  //    in 2-3 places (insight panels). We scan all .insight-card with an
  //    h3 + stat-value pair and update by heading text.
  const STAT_HEADINGS = {
    "今日灵感捕捉": String(captureToday),
    "今日捕捉": String(captureToday),
    "知识库": String(kbItems),
    "待办任务": String(pendingTasks),
  };
  document
    .querySelectorAll(".insight-card .stat-value, .stat-value")
    .forEach((statNode) => {
      const card = statNode.closest("article, .insight-card, .insights-bottom-grid > *");
      const h3 = card && card.querySelector("h3");
      const heading = h3 ? h3.textContent.trim() : "";
      const next = STAT_HEADINGS[heading];
      if (next != null) {
        statNode.textContent = next;
        statNode.dataset.bridgeBound = "true";
      }
    });

  window.dispatchEvent(
    new CustomEvent("mydow:today-loaded", { detail: { stats, raw: data } }),
  );
  return data;
}

// ─────────────────────────────────────────────  §15.5 [续] right-side panel  ─
//
// The biz prototype's right-side ``.insight-drawer .insight-panel`` (visible
// on home page) has 4 hard-coded cards:
//   1. 今日灵感捕捉 (covered by refreshTodayInsights above)
//   2. AI 助理活跃度 — stat-value=高 + stat-note="帮助你梳理了 12 条灵感"
//   3. 内容分布 (.distribution-card) — 4 legend rows + .donut SVG
//   4. AI 每日洞察 (.daily-insight) — <p> body text + 「查看洞察详情」link
//   5. 最近使用 (.recent-list) — 3 .recent-item rows
//
// The KB drawer (``.knowledge-drawer .insight-panel``) ships:
//   1. 今日灵感捕捉 + AI 助理活跃度 (same as home, hydrated by shared selectors)
//   2. 知识库概览 (.kb-overview) — stat-value="735 条记录" + legend 我的记录 / 自动捕获 / 协作共享
//   3. 小贴士 (.tip-card) — static, no hydration needed
//
// All hydrators are silent on failure (the prototype's static fallback shows).

// ── Internal: select all visible distribution cards (home + duplicates) ──
function _findCards(selector) {
  return Array.from(document.querySelectorAll(selector));
}

// §15.5b ─ 内容分布饼图（接 /feed facets.types -> 笔记/链接/文件/语音 4 桶）
async function refreshHomeContentDistribution() {
  const cards = _findCards(".insight-card.distribution-card");
  if (cards.length === 0) return null;

  let payload;
  try {
    payload = await apiFetch("/feed?page_size=1");
  } catch (e) {
    console.warn("[Mydow] /feed (distribution) failed", e);
    return null;
  }
  const data = (payload && payload.data) || payload || {};
  const types = (data.facets && data.facets.types) || [];

  // Map PRD10 §5.5 content_type values into the prototype's 4 visual buckets.
  const buckets = { note: 0, link: 0, file: 0, voice: 0 };
  for (const item of types) {
    const v = String(item.value || "").toLowerCase();
    const c = Number(item.count || 0);
    if (v === "note" || v === "task" || v === "ai_output") buckets.note += c;
    else if (v === "article" || v === "link") buckets.link += c;
    else if (v === "file" || v === "image" || v === "report") buckets.file += c;
    else if (v === "audio") buckets.voice += c;
    else buckets.note += c; // unknown → notes bucket
  }
  const total = buckets.note + buckets.link + buckets.file + buckets.voice;
  const pct = (n) => (total === 0 ? 0 : Math.round((n / total) * 100));

  const segs = [
    pct(buckets.note),
    pct(buckets.link),
    pct(buckets.file),
    pct(buckets.voice),
  ];
  const colors = ["#7d8cff", "#67c2c4", "#f0bd6c", "#d7a9a5"];

  cards.forEach((card) => {
    const rows = card.querySelectorAll(".legend-row strong");
    if (rows.length >= 4) {
      rows[0].textContent = `${segs[0]}%`;
      rows[1].textContent = `${segs[1]}%`;
      rows[2].textContent = `${segs[2]}%`;
      rows[3].textContent = `${segs[3]}%`;
    }
    const donut = card.querySelector(".donut");
    if (donut) {
      let acc = 0;
      const stops = [];
      for (let i = 0; i < 4; i += 1) {
        const next = acc + segs[i];
        stops.push(`${colors[i]} ${acc}% ${next}%`);
        acc = next;
      }
      if (acc < 100) stops.push(`${colors[0]} ${acc}% 100%`);
      donut.style.background = `conic-gradient(${stops.join(", ")})`;
      donut.setAttribute(
        "aria-label",
        `内容分布图：笔记 ${segs[0]}% / 链接 ${segs[1]}% / 文件 ${segs[2]}% / 语音 ${segs[3]}%`,
      );
    }
    card.dataset.bridgeBound = "true";
  });

  window.dispatchEvent(
    new CustomEvent("mydow:content-distribution-loaded", {
      detail: { buckets, total, percentages: { note: segs[0], link: segs[1], file: segs[2], voice: segs[3] } },
    }),
  );
  return { buckets, total };
}

// §15.5c ─ AI 助理活跃度（用 /ai/conversations 真 message_count + /today
// weekly_growth_rate 派生 高/中/低）
async function refreshHomeAiActivity() {
  // Find the second .insight-card.insight-graph (the one with .mood-orb).
  const candidates = _findCards(".insight-card.insight-graph");
  const cards = candidates.filter((c) => c.querySelector(".mood-orb"));
  if (cards.length === 0) return null;

  let totalMessages = 0;
  let conversationCount = 0;
  try {
    const payload = await apiFetch("/ai/conversations?page_size=20");
    const data = (payload && payload.data) || payload || {};
    const items = data.items || [];
    conversationCount = items.length;
    for (const c of items) totalMessages += Number(c.message_count || 0);
  } catch (e) {
    console.warn("[Mydow] /ai/conversations failed", e);
  }

  let growthRate = 0;
  try {
    const payload = await apiFetch("/today");
    const data = (payload && payload.data) || payload || {};
    growthRate = Number((data.stats && data.stats.weekly_growth_rate) || 0);
  } catch (e) {
    /* ignore — already fetched in refreshTodayInsights, this is fallback */
  }

  // Activity tier: 高 if growth >= 0.2 OR messages >= 10; 中 if >= 0; 低 otherwise.
  let tier = "中";
  if (growthRate >= 0.2 || totalMessages >= 10) tier = "高";
  else if (totalMessages === 0 && growthRate < 0) tier = "低";

  const noteText = totalMessages > 0
    ? `帮助你梳理了 ${totalMessages} 条对话消息`
    : conversationCount > 0
      ? `已开始 ${conversationCount} 个对话`
      : "记录第一条想法即可开启";

  cards.forEach((card) => {
    const stat = card.querySelector(".stat-value");
    const note = card.querySelector(".stat-note");
    if (stat) {
      stat.textContent = tier;
      stat.dataset.bridgeBound = "true";
    }
    if (note) {
      note.textContent = noteText;
      note.dataset.bridgeBound = "true";
    }
  });
  return { tier, totalMessages, conversationCount, growthRate };
}

// §15.5d ─ AI 每日洞察文案（接 /insights/summary 第一条 + /today.insight_preview 兜底）
async function refreshHomeDailyInsightCard() {
  const cards = _findCards(".insight-card.daily-insight");
  if (cards.length === 0) return null;

  let title = "";
  let body = "";
  let insightId = null;

  try {
    const payload = await apiFetch("/insights/summary?range=week");
    const data = (payload && payload.data) || payload || {};
    const insights = data.insights || [];
    if (insights.length > 0) {
      const first = insights[0];
      title = first.title || "";
      body = first.summary || first.body || "";
      insightId = first.id || null;
    }
  } catch (e) {
    console.warn("[Mydow] /insights/summary failed", e);
  }

  if (!body) {
    try {
      const payload = await apiFetch("/today");
      const data = (payload && payload.data) || payload || {};
      const preview = data.insight_preview || {};
      title = preview.title || title;
      body = preview.summary || "";
    } catch (e) {
      /* keep prototype fallback */
    }
  }

  if (!body) {
    body = "继续记录，Mydow AI 将基于你的灵感与文档自动生成洞察。";
  }

  cards.forEach((card) => {
    const para = card.querySelector("p");
    if (para) {
      // Preserve title prefix (e.g. "你最近...") — replace whole paragraph
      // with a real summary; if title exists, prepend a `<strong>` for context.
      if (title) {
        para.innerHTML = `<strong>${escapeHtml(title)}</strong> · ${escapeHtml(body)}`;
      } else {
        para.textContent = body;
      }
      para.dataset.bridgeBound = "true";
    }
    if (insightId) card.dataset.insightId = insightId;
    card.dataset.bridgeBound = "true";
  });
  return { title, body, insightId };
}

// §15.5e ─ 最近使用列表（.recent-list 3 行）接 /feed?page_size=3
async function refreshHomeRecentList() {
  const lists = _findCards(".insight-drawer .recent-list");
  if (lists.length === 0) return null;

  let payload;
  try {
    payload = await apiFetch("/feed?page_size=3");
  } catch (e) {
    console.warn("[Mydow] /feed (recent-list) failed", e);
    return null;
  }
  const data = (payload && payload.data) || payload || {};
  const items = data.items || [];
  if (items.length === 0) return null;

  const TYPE_TO_ICON = {
    note: { iconId: "icon-file-text", cls: "" },
    article: { iconId: "icon-link", cls: "link" },
    link: { iconId: "icon-link", cls: "link" },
    file: { iconId: "icon-file-text", cls: "file" },
    image: { iconId: "icon-file-text", cls: "file" },
    audio: { iconId: "icon-mic", cls: "voice" },
    task: { iconId: "icon-file-text", cls: "" },
    ai_output: { iconId: "icon-sparkles", cls: "" },
    report: { iconId: "icon-file-text", cls: "file" },
  };

  lists.forEach((list) => {
    list.innerHTML = "";
    items.forEach((it) => {
      const ct = String(it.content_type || "note").toLowerCase();
      const meta = TYPE_TO_ICON[ct] || TYPE_TO_ICON.note;
      const article = document.createElement("article");
      article.className = "recent-item";
      article.dataset.cardId = it.id || "";
      const iconSpan = document.createElement("span");
      iconSpan.className = `recent-item-icon ${meta.cls}`.trim();
      iconSpan.innerHTML = `<svg class="icon" style="width: 17px; height: 17px"><use href="#${meta.iconId}" /></svg>`;
      const textWrap = document.createElement("div");
      const strong = document.createElement("strong");
      strong.textContent = it.title || "未命名";
      const span = document.createElement("span");
      span.textContent = relTime(it.updated_at || it.created_at);
      textWrap.append(strong, span);
      article.append(iconSpan, textWrap);
      list.appendChild(article);
    });
    list.dataset.bridgeBound = "true";
  });
  return items;
}

// §15.5g ─ 通知抽屉 mini-stat 三件套（今日未读 / 已完成任务 / AI 通知占比）
async function refreshNotificationMiniStats() {
  const list = document.querySelector(".notification-drawer .mini-stat-list");
  if (!list) return null;
  const cards = list.querySelectorAll(".mini-stat");
  if (cards.length === 0) return null;

  const [unreadResp, notifResp, todayResp] = await Promise.all([
    apiFetch("/notifications/unread-count").catch(() => null),
    apiFetch("/notifications?page_size=100").catch(() => null),
    apiFetch("/today").catch(() => null),
  ]);

  const unread = Number(
    (unreadResp && unreadResp.data && (unreadResp.data.count != null
      ? unreadResp.data.count
      : unreadResp.data.unread_count)) || 0,
  );
  const items = (notifResp && notifResp.data && notifResp.data.items) || [];
  const total = items.length;
  const aiCount = items.filter((n) => /^ai[_-]/i.test(String(n.type || ""))).length;
  const aiPct = total > 0 ? Math.round((aiCount / total) * 100) : 0;
  const stats = (todayResp && todayResp.data && todayResp.data.stats) || {};
  const completed = Number(stats.completed_task_count || 0);

  const labels = [
    {
      heading: "今日未读",
      value: String(unread),
      note: total > 0 ? `共 ${total} 条通知` : `暂无通知`,
    },
    {
      heading: "已完成任务",
      value: String(completed),
      note:
        completed > 0
          ? `本周共完成 ${completed} 项`
          : `开始处理任务以查看进度`,
    },
    {
      heading: "AI 通知占比",
      value: `${aiPct}%`,
      note: aiCount > 0 ? `AI 推送 ${aiCount} / ${total}` : `AI 暂无新推送`,
    },
  ];

  cards.forEach((card, idx) => {
    if (idx >= labels.length) return;
    const it = labels[idx];
    const h3 = card.querySelector("h3");
    const strong = card.querySelector("strong");
    const span = card.querySelector("div > span");
    if (h3) h3.textContent = it.heading;
    if (strong) strong.textContent = it.value;
    if (span) span.textContent = it.note;
    card.dataset.bridgeBound = "true";
  });
  return { unread, total, aiCount, aiPct, completed };
}

// §15.5h ─ 完整洞察侧栏 topic-donut + 内容来源 bar-list（驱动
//          .insights-full-drawer 内 5 主题环形 + 5 类来源百分比）
async function refreshFullInsightDrawer() {
  const panel = document.querySelector(".insights-full-drawer");
  if (!panel) return null;

  const [summaryResp, feedResp] = await Promise.all([
    apiFetch("/insights/summary?range=week").catch(() => null),
    apiFetch("/feed?page_size=100").catch(() => null),
  ]);

  const summary = (summaryResp && summaryResp.data) || {};
  const themes = summary.theme_distribution || [];
  const feedItems = (feedResp && feedResp.data && feedResp.data.items) || [];

  // ── topic-donut（重点主题数 + legend 5 行）──
  const donut = panel.querySelector(".topic-donut-card .topic-donut strong");
  if (donut) {
    while (donut.firstChild) donut.removeChild(donut.firstChild);
    donut.append(document.createTextNode(String(themes.length || 0)));
    const sub = document.createElement("span");
    sub.textContent = "重点主题";
    donut.appendChild(sub);
  }
  const themeRows = panel.querySelectorAll(".topic-donut-card .legend .legend-row");
  if (themeRows.length > 0 && themes.length > 0) {
    const grand = themes.reduce((a, t) => a + Number(t.value || 0), 0) || 1;
    themeRows.forEach((row, idx) => {
      if (idx >= themes.length) {
        row.style.display = "none";
        return;
      }
      row.style.display = "";
      const t = themes[idx];
      const labelSpan = row.querySelectorAll("span")[1];
      const strong = row.querySelector("strong");
      const pct = Math.round((Number(t.value || 0) / grand) * 100);
      if (labelSpan) labelSpan.textContent = String(t.name || "未命名");
      if (strong) strong.textContent = `${pct}%`;
    });
    panel.querySelector(".topic-donut-card").dataset.bridgeBound = "true";
  }

  // ── 内容来源 bar-list ──
  const buckets = { note: 0, link: 0, file: 0, voice: 0, ai: 0 };
  let bucketTotal = 0;
  for (const it of feedItems) {
    const t = String(it.content_type || "note").toLowerCase();
    if (t === "note" || t === "task") buckets.note += 1;
    else if (t === "article" || t === "link") buckets.link += 1;
    else if (t === "file" || t === "image" || t === "report") buckets.file += 1;
    else if (t === "audio") buckets.voice += 1;
    else if (t === "ai_output") buckets.ai += 1;
    else buckets.note += 1;
    bucketTotal += 1;
  }
  const pctOf = (n) =>
    bucketTotal > 0 ? Math.round((n / bucketTotal) * 100) : 0;
  const barLabels = [
    { label: "笔记", pct: pctOf(buckets.note) },
    { label: "网页链接", pct: pctOf(buckets.link) },
    { label: "图片 / 文件", pct: pctOf(buckets.file) },
    { label: "语音输入", pct: pctOf(buckets.voice) },
    { label: "AI 生成", pct: pctOf(buckets.ai) },
  ];
  const barRows = panel.querySelectorAll(".bar-list .bar-row");
  barRows.forEach((row, idx) => {
    if (idx >= barLabels.length) return;
    const it = barLabels[idx];
    const labelSpan = row.querySelector("span:first-child");
    const strong = row.querySelector("strong");
    const track = row.querySelector(".bar-track > span");
    if (labelSpan) labelSpan.textContent = it.label;
    if (strong) strong.textContent = `${it.pct}%`;
    if (track) track.style.width = `${it.pct}%`;
    row.dataset.bridgeBound = "true";
  });

  return { themeCount: themes.length, bucketTotal };
}

// §15.5j ─ home page 右上 .right-rail .stats 顶部 3 张 stat-card
//          （业务方原型 line 6471-6502）：
//            1) 今日新增灵感      → today_capture_count + 周相对趋势
//            2) AI 周报总结        → 高/中/低 + 「梳理 N 条灵感」
//            3) 本月灵感捕捉      → /feed?date_range=month total
//          这 3 张是 ``.right-rail .stats > .stat-card``，与
//          ``.insight-drawer .insight-card`` 不在同一作用域，所以
//          ``refreshTodayInsights`` 的 .insight-card 选择器不会命中。
//          失败时静默保留原型静态值（PRD10 §20 的 fallback 语义）。
async function refreshHomeRightRailStatCards() {
  const stats = document.querySelectorAll(".right-rail .stats .stat-card");
  if (stats.length === 0) return null;

  // /today + /feed?date_range=month + /ai/conversations 并行；任一失败
  // 都只跳过对应那张卡，不阻塞其余。
  const [todayResp, monthResp, aiResp] = await Promise.all([
    apiFetch("/today").catch(() => null),
    apiFetch("/feed?date_range=month&page_size=1").catch(() => null),
    apiFetch("/ai/conversations?page_size=20").catch(() => null),
  ]);

  const todayStats =
    (todayResp && todayResp.data && todayResp.data.stats) || {};
  const todayCaptureCount = Number(
    todayStats.today_capture_count != null
      ? todayStats.today_capture_count
      : todayStats.today_captures != null
        ? todayStats.today_captures
        : 0,
  );
  const weeklyGrowth = Number(todayStats.weekly_growth_rate || 0);

  // /feed pagination.total when date_range=month
  const monthTotal = Number(
    (monthResp && monthResp.data && monthResp.data.pagination &&
      monthResp.data.pagination.total) || 0,
  );

  // AI 总消息数 + 会话数
  let totalMessages = 0;
  let conversationCount = 0;
  if (aiResp && aiResp.data && Array.isArray(aiResp.data.items)) {
    conversationCount = aiResp.data.items.length;
    for (const c of aiResp.data.items) {
      totalMessages += Number(c.message_count || 0);
    }
  }
  let aiTier = "中";
  if (weeklyGrowth >= 0.2 || totalMessages >= 10) aiTier = "高";
  else if (totalMessages === 0 && weeklyGrowth < 0) aiTier = "低";
  const aiNote =
    totalMessages > 0
      ? `帮助你梳理了 ${totalMessages} 条对话消息`
      : conversationCount > 0
        ? `已开始 ${conversationCount} 个对话`
        : "记录第一条想法即可开启";

  const trendNote = (() => {
    if (weeklyGrowth > 0.001) {
      return `较上周\u00a0\u00a0+${Math.round(weeklyGrowth * 100)}%`;
    }
    if (weeklyGrowth < -0.001) {
      return `较上周\u00a0\u00a0${Math.round(weeklyGrowth * 100)}%`;
    }
    return todayCaptureCount > 0 ? "今日仍在记录中" : "记录第一条灵感";
  })();

  // 顺序匹配业务方原型的 3 张卡（h3 文字精确）
  const SLOTS = {
    "今日新增灵感": { value: String(todayCaptureCount), note: trendNote },
    "AI 周报总结": { value: aiTier, note: aiNote },
    "本月灵感捕捉": {
      value: String(monthTotal),
      note:
        monthTotal === 0
          ? "本月暂无灵感"
          : conversationCount > 0
            ? `已记录 ${monthTotal} 条`
            : `本月共 ${monthTotal} 条`,
    },
  };

  stats.forEach((card) => {
    const h3 = card.querySelector("h3");
    const heading = h3 ? h3.textContent.trim() : "";
    const slot = SLOTS[heading];
    if (!slot) return;
    const valueEl = card.querySelector(".stat-value");
    const noteEl = card.querySelector(".stat-note");
    if (valueEl) {
      valueEl.textContent = slot.value;
      valueEl.dataset.bridgeBound = "true";
    }
    if (noteEl) {
      noteEl.textContent = slot.note;
      noteEl.dataset.bridgeBound = "true";
    }
    card.dataset.bridgeBound = "true";
  });

  window.dispatchEvent(
    new CustomEvent("mydow:right-rail-stats-loaded", {
      detail: { todayCaptureCount, monthTotal, aiTier, weeklyGrowth },
    }),
  );

  return {
    todayCaptureCount,
    monthTotal,
    aiTier,
    aiNote,
    weeklyGrowth,
  };
}

// §15.5i ─ 把「查看洞察详情」 .text-link 接到 [data-insights-full] 触发器
let _attachedDailyInsightLink = false;
function attachDailyInsightLink() {
  if (_attachedDailyInsightLink) return;
  document.addEventListener(
    "click",
    (event) => {
      const link = event.target.closest(
        ".insight-card.daily-insight .text-link",
      );
      if (!link) return;
      event.preventDefault();
      event.stopPropagation();
      const opener = document.querySelector("[data-insights-full]");
      if (opener) {
        opener.click();
        window.setTimeout(() => {
          if (typeof refreshInsightsFullPanel === "function") {
            refreshInsightsFullPanel().catch(() => {});
          }
        }, 60);
      }
    },
    true,
  );
  _attachedDailyInsightLink = true;
}

// §15.5f ─ 知识库概览面板（.kb-overview）接 /kb/overview
async function refreshKbOverviewCard() {
  const cards = _findCards(".insight-card.kb-overview");
  if (cards.length === 0) return null;

  let payload;
  try {
    payload = await apiFetch("/kb/overview");
  } catch (e) {
    console.warn("[Mydow] /kb/overview failed", e);
    return null;
  }
  const data = (payload && payload.data) || payload || {};
  // PRD10 §10.1 returns either flat stats or a stats sub-object; tolerate both.
  const stats = data.stats || data;
  const docCount = Number(
    stats.document_count != null ? stats.document_count : stats.documents || 0,
  );
  const folderCount = Number(
    stats.folder_count != null ? stats.folder_count : stats.folders || 0,
  );
  const favoriteCount = Number(
    stats.favorite_count != null ? stats.favorite_count : stats.favorites || 0,
  );
  const recentUpdated = Number(
    stats.recent_updated_count != null ? stats.recent_updated_count : 0,
  );

  // 3-bucket synthesis matching the prototype legend:
  //   我的记录 = docCount - favoriteCount - recentUpdated（剩余）
  //   自动捕获 = recentUpdated（近期由 capture pipeline 生成的）
  //   协作共享 = favoriteCount（V1 用收藏数充当"协作"占位；P1 接真实 share API）
  const myShare = Math.max(0, docCount - favoriteCount - recentUpdated);
  const total = myShare + recentUpdated + favoriteCount;
  const pct = (n) => (total === 0 ? 0 : Math.round((n / total) * 100));

  cards.forEach((card) => {
    const stat = card.querySelector(".stat-value");
    if (stat) {
      // Preserve the inner <span>条记录</span> styling.
      const inner = stat.querySelector("span") || document.createElement("span");
      inner.style.cssText = "font-size: 13px; color: #718098";
      inner.textContent = " 条记录";
      stat.textContent = String(docCount);
      stat.appendChild(inner);
      stat.dataset.bridgeBound = "true";
    }
    const rows = card.querySelectorAll(".legend-row strong");
    if (rows.length >= 3) {
      rows[0].textContent = `${pct(myShare)}%`;
      rows[1].textContent = `${pct(recentUpdated)}%`;
      rows[2].textContent = `${pct(favoriteCount)}%`;
    }
    card.dataset.bridgeBound = "true";
  });
  return { docCount, folderCount, favoriteCount, recentUpdated };
}

// ─────────────────────────────────────────────  §15.4 feed counters  ──────
//
// Hit `/feed?type=*` for the prototype's three tabs and surface a small
// counter beside each tab label so the user can see real numbers driven
// by the seed data. The prototype keeps the existing tab-switching
// behaviour; we layer real counts on top without removing the static
// listeners.
async function refreshFeedCounters() {
  const tabs = [
    { selector: '[data-view-target="recent"]', type: null },
    { selector: '[data-view-target="records"]', type: null },
  ];
  let payload;
  try {
    payload = await apiFetch("/feed?limit=1");
  } catch (e) {
    console.warn("[Mydow] /feed failed", e);
    return null;
  }
  const data = (payload && payload.data) || payload || {};
  const facets = data.facets || {};
  const total =
    (data.pagination && data.pagination.total) ||
    facets.all ||
    facets.total ||
    (data.items && data.items.length) ||
    0;
  // Surface counts on each tab as a sup-style suffix.
  tabs.forEach((spec) => {
    const tab = document.querySelector(spec.selector);
    if (!tab) return;
    let counter = tab.querySelector(".bridge-tab-counter");
    if (!counter) {
      counter = document.createElement("span");
      counter.className = "bridge-tab-counter";
      counter.style.cssText =
        "margin-left:6px;padding:1px 6px;border-radius:8px;background:rgba(106,122,148,.12);color:#5a6b86;font-size:10px;font-weight:600";
      tab.appendChild(counter);
    }
    counter.textContent = String(total);
  });
  window.dispatchEvent(
    new CustomEvent("mydow:feed-loaded", { detail: { total, facets } }),
  );
  return data;
}

// ─────────────────────────────────────────────  §15.7 modals  ─────────────
//
// The biz prototype's 4 home modals (uploadFile / webLink / voiceInput /
// deepResearch) currently submit via ``data-toast="..."`` which the inline
// IIFE intercepts to fire ``simulateAction`` (a fake setTimeout-based
// progress UI). To keep the prototype's visual flow intact while making
// the buttons real, we attach a **capture-phase** document listener that
// recognises the 4 modal submit buttons and short-circuits the IIFE with
// ``stopImmediatePropagation``. Other ``data-toast`` buttons (skill run,
// settings, etc.) still go through the IIFE's simulateAction path.

function closeAllModals() {
  document.querySelectorAll(".surface-layer[data-modal]").forEach((layer) => {
    layer.hidden = true;
  });
  syncLayerStateMarkers();
}

function injectMobileUsabilityFixes() {
  if (document.getElementById("mydow-mobile-usability-fixes")) return;
  const style = document.createElement("style");
  style.id = "mydow-mobile-usability-fixes";
  style.textContent = `
@media (max-width: 680px) {
  .workspace { overflow-x: hidden; }
  .content-grid,
  .page.insights-open .content-grid,
  .page.knowledge-open .content-grid,
  .page.folder-open .content-grid,
  .page.ai-open .content-grid,
  .page.garden-open .content-grid,
  .page.skills-open .content-grid,
  .page.notifications-open .content-grid,
  .page.insights-full-open .content-grid,
  .page.profile-open .content-grid,
  .page.doc-open .content-grid {
    width: 100% !important;
    max-width: 100% !important;
    grid-template-columns: minmax(0, 1fr) !important;
    gap: 18px !important;
  }
  .main-column,
  .main-column > .hero,
  .capture,
  .quick-actions,
  .section-bar,
  .content-view,
  .knowledge-main,
  .folder-main,
  .ai-main,
  .garden-main,
  .skills-main,
  .notification-main,
  .insights-full-main,
  .profile-main,
  .doc-editor-main {
    width: 100% !important;
    min-width: 0 !important;
    max-width: 100% !important;
  }
  .capture-footer {
    display: flex !important;
    flex-wrap: wrap;
    gap: 10px;
  }
  .capture-footer .submit-row {
    margin-left: auto;
    display: inline-flex;
    flex: 0 0 auto;
  }
  .capture-footer .circle-button { flex: 0 0 auto; }
  .quick-actions,
  .card-grid,
  .library-grid,
  .skills-main .skill-grid,
  .insights-full-main .metric-grid,
  .profile-layout {
    grid-template-columns: minmax(0, 1fr) !important;
  }
  .doc-editor-surface { padding: 24px 18px 20px !important; }
  .doc-title-input { font-size: 28px !important; }
}
`;
  document.head.appendChild(style);
}

const MYDOW_FAVICON_DATA_URI =
  "data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop offset='0' stop-color='%239fb1ff'/%3E%3Cstop offset='1' stop-color='%23758cff'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='100' height='100' rx='22' fill='url(%23g)'/%3E%3Cpath d='M28 64 L42 36 L50 56 L58 36 L72 64' stroke='white' stroke-width='8' stroke-linecap='round' stroke-linejoin='round' fill='none'/%3E%3C/svg%3E";

/** §9.9 — favicon + theme-color + Open Graph / Twitter meta (no biz HTML edits). */
function injectBrandMeta() {
  if (document.documentElement.dataset.mydowBrandMeta === "1") return;
  document.documentElement.dataset.mydowBrandMeta = "1";
  const head = document.head;
  if (!head) return;

  const upsertMeta = (selector, factory) => {
    let el = head.querySelector(selector);
    if (!el) {
      el = factory();
      head.appendChild(el);
    }
    return el;
  };

  let icon = head.querySelector("link[rel='icon']");
  if (!icon) {
    icon = document.createElement("link");
    icon.rel = "icon";
    head.appendChild(icon);
  }
  icon.type = "image/svg+xml";
  icon.href = MYDOW_FAVICON_DATA_URI;

  const origin = window.location.origin || "";
  const path = window.location.pathname || "/mydow/biz/";
  upsertMeta("meta[name='theme-color']", () => {
    const m = document.createElement("meta");
    m.setAttribute("name", "theme-color");
    return m;
  }).content = "#758cff";

  upsertMeta("meta[property='og:title']", () => {
    const m = document.createElement("meta");
    m.setAttribute("property", "og:title");
    return m;
  }).content = "Mydow";

  upsertMeta("meta[property='og:description']", () => {
    const m = document.createElement("meta");
    m.setAttribute("property", "og:description");
    return m;
  }).content = "把灵感变成体系化的知识 · PRD10 演示";

  upsertMeta("meta[property='og:type']", () => {
    const m = document.createElement("meta");
    m.setAttribute("property", "og:type");
    return m;
  }).content = "website";

  upsertMeta("meta[property='og:url']", () => {
    const m = document.createElement("meta");
    m.setAttribute("property", "og:url");
    return m;
  }).content = `${origin}${path}`;

  upsertMeta("meta[name='twitter:card']", () => {
    const m = document.createElement("meta");
    m.setAttribute("name", "twitter:card");
    return m;
  }).content = "summary_large_image";
}

async function uploadAndCommitFile(file) {
  // 1) Ask the API for an upload "presign" record. PRD10 §8.3 schema:
  //    request {filename, mime_type, size_bytes} → response
  //    {upload_id, upload_url, upload_method:"PUT", file_url, expires_in}.
  const mimeType = file.type || "application/octet-stream";
  const presign = await apiFetch("/uploads/presign", {
    method: "POST",
    body: {
      filename: file.name,
      mime_type: mimeType,
      size_bytes: file.size,
    },
  });
  const presignData = (presign && presign.data) || presign || {};
  const uploadId = presignData.upload_id;
  const uploadUrl = presignData.upload_url;
  if (!uploadId || !uploadUrl) {
    throw new Error("presign 未返回 upload_id / upload_url");
  }
  // 2) PUT the bytes. apiFetch JSON-stringifies, so use raw fetch for
  //    binary. The local /uploads/local/{id} endpoint accepts the auth
  //    bearer token, so propagate it.
  const tok = token();
  const putResp = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      ...(tok ? { Authorization: `Bearer ${tok}` } : {}),
      "Content-Type": mimeType,
    },
    body: file,
  });
  if (!putResp.ok) {
    throw new Error(`上传失败：${putResp.status} ${putResp.statusText}`);
  }
  // 3) Commit so the backend records metadata + queues parsing/index jobs.
  const commit = await apiFetch("/capture/file/commit", {
    method: "POST",
    body: {
      upload_id: uploadId,
      filename: file.name,
      mime_type: mimeType,
      size_bytes: file.size,
      auto_process: true,
    },
  });
  return commit;
}

async function handleUploadFileModal(button) {
  const modal = button.closest('[data-modal="uploadFile"]');
  if (!modal) return;
  let input = modal.querySelector('input[type="file"][data-bridge-input]');
  if (!input) {
    input = document.createElement("input");
    input.type = "file";
    input.setAttribute("data-bridge-input", "true");
    input.style.display = "none";
    modal.appendChild(input);
  }
  return new Promise((resolve) => {
    input.value = "";
    const onChange = async () => {
      input.removeEventListener("change", onChange);
      const file = input.files && input.files[0];
      if (!file) {
        toast("没有选择文件", "warning");
        resolve();
        return;
      }
      button.disabled = true;
      button.classList.add("is-loading");
      try {
        await uploadAndCommitFile(file);
        toast(`已上传 ${file.name}，正在自动整理`, "success");
        closeAllModals();
        loadFeedIntoRecentView();
        refreshFeedCounters();
        refreshTodayInsights();
      } catch (e) {
        console.error("[Mydow] upload failed", e);
        toast(`上传失败: ${e.message}`, "error");
      } finally {
        button.disabled = false;
        button.classList.remove("is-loading");
        resolve();
      }
    };
    input.addEventListener("change", onChange, { once: true });
    input.click();
  });
}

async function handleWebLinkModal(button) {
  const modal = button.closest('[data-modal="webLink"]');
  if (!modal) return;
  const urlInput = modal.querySelector('input[type="text"], input:not([type])');
  const url = (urlInput && urlInput.value.trim()) || "";
  if (!url) {
    toast("请先填入网页 URL", "warning");
    return;
  }
  button.disabled = true;
  button.classList.add("is-loading");
  try {
    await apiFetch("/capture/link", {
      method: "POST",
      body: { url, auto_process: true },
    });
    toast("网页已保存到最近捕捉，AI 整理中", "success");
    closeAllModals();
    loadFeedIntoRecentView();
    refreshFeedCounters();
    refreshTodayInsights();
  } catch (e) {
    console.error("[Mydow] capture link failed", e);
    toast(`剪藏失败: ${e.message}`, "error");
  } finally {
    button.disabled = false;
    button.classList.remove("is-loading");
  }
}

async function handleDeepResearchModal(button) {
  const modal = button.closest('[data-modal="deepResearch"]');
  if (!modal) return;
  const topic = modal.querySelector("input")?.value.trim() || "";
  const scope = modal.querySelector("select")?.value || "";
  const output = modal.querySelector("textarea")?.value.trim() || "";
  if (!topic) {
    toast("请先填写研究主题", "warning");
    return;
  }
  button.disabled = true;
  button.classList.add("is-loading");
  try {
    const conv = await apiFetch("/ai/conversations", {
      method: "POST",
      body: { title: `深度研究：${topic}`, mode: "report" },
    });
    const cid = (conv && conv.data && conv.data.id) || conv?.id;
    if (!cid) throw new Error("会话创建失败");
    const seedMessage = [
      `主题: ${topic}`,
      scope ? `范围: ${scope}` : "",
      output ? `输出要求: ${output}` : "",
    ]
      .filter(Boolean)
      .join("\n");
    await apiFetch(`/ai/conversations/${cid}/messages`, {
      method: "POST",
      body: { content: seedMessage },
    });
    toast(`深度研究已创建，正在 AI 整理`, "success");
    closeAllModals();
    refreshUnreadBadge();
  } catch (e) {
    console.error("[Mydow] deep research failed", e);
    toast(`研究任务创建失败: ${e.message}`, "error");
  } finally {
    button.disabled = false;
    button.classList.remove("is-loading");
  }
}

async function handleVoiceInputModal(_button) {
  // V1: real Web Speech transcription is out of scope. We acknowledge the
  // intent and surface a toast so the prototype's UX still flows; once
  // §15.7 voice slice lands in P1 we'll wire MediaRecorder + a /uploads
  // path here.
  toast("语音输入：V1 占位 — P1 将接 MediaRecorder + /uploads", "info");
  closeAllModals();
}

function bindHomeModalSubmits() {
  // The inline IIFE registers a *bubbling* document listener that closes
  // a layer + fires simulateAction whenever a [data-toast] in a
  // .surface-layer is clicked. We register a *capture* listener that
  // runs first and short-circuits with stopImmediatePropagation, so only
  // our home-modal + biz-prototype-modal submits get rerouted to real
  // PRD10 calls.
  document.addEventListener(
    "click",
    (event) => {
      const button = event.target.closest("button[data-toast]");
      if (!button) return;
      const layer = button.closest(".surface-layer[data-modal]");
      if (!layer) return;
      const modalName = layer.dataset.modal;
      const handlers = {
        uploadFile: handleUploadFileModal,
        webLink: handleWebLinkModal,
        deepResearch: handleDeepResearchModal,
        voiceInput: handleVoiceInputModal,
        // §15.24 / §15.25 / §15.26 — biz prototype modals whose submit
        // button uses [data-toast] (so they cleanly reuse this capture
        // listener); the actual logic lives in the §15 helpers below.
        skillRun: handleSkillRunModal,
        notificationSettings: handleNotificationSettingsModal,
        editProfile: handleEditProfileModal,
        // §15.30 v1.4 sync — Mydow AI 个性化 modal
        aiPersonalize: handleAiPersonalizeModal,
        // §15.30 v1.4 sync — 自定义洞察 modal (生成洞察)
        customInsight: handleCustomInsightModal,
      };
      const fn = handlers[modalName];
      if (!fn) return;
      // Cancel buttons keep falling through to data-close-layer.
      if (button.matches("[data-close-layer]")) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      fn(button, layer).catch((e) => console.error("[Mydow] modal handler", e));
    },
    true /* capture */,
  );
}

// §15.23 newDocument modal binding lives further down (search for
// `bindKbNewDocumentSubmit` / `handleNewDocumentSubmit`) — it predates this
// block by a different agent and is wired into boot already. The backend
// `POST /api/v1/kb/documents` endpoint that those helpers call is added in
// `agent_os/kb/router.py` (this same change set).

// ─────────────────────────────────────────────  §15.24 skillRun modal  ────
//
// `[data-modal="skillRun"]` opens with input <textarea>, output <select>
// and a "运行 Skill" button (data-toast="Skill 正在运行"). It is
// triggered by `[data-open-modal="skillRun"]` from a skill card's
// "立即试用" button — but the click event hands no skill_id to the modal.
// We track the most-recently-opened skill id via a capture-phase listener
// on `[data-open-modal="skillRun"]` so submitting the modal posts to the
// right /skills/{id}/run.

const _SKILL_RUN_STATE = {
  activeSkillId: null,
  activeSkillName: null,
  // PRD10 §15.24 idempotency guard — boot path may run more than once
  // (DOMContentLoaded race, hot reload during dev) so we never want to
  // register the global capture listener twice.
  attached: false,
};

function _stashSkillRunContext() {
  if (_SKILL_RUN_STATE.attached) return;
  _SKILL_RUN_STATE.attached = true;

  // §15.24 — Three entry points to the [data-modal="skillRun"] modal:
  //
  //   (A) User clicks a `.skill-card[data-skill-id]` body — IIFE opens
  //       `[data-drawer="skillDetail"]` (line 8123 of biz/index.html).
  //       Then user clicks "立即试用" inside the drawer
  //       `[data-open-modal="skillRun"]` (line 7272) to open the modal.
  //   (B) Some legacy markup may put `[data-open-modal="skillRun"]`
  //       directly inside a `[data-skill-id]` wrapper.
  //   (C) The drawer's "立即试用" button is outside any [data-skill-id]
  //       — in that case (A) has already stashed the right id from the
  //       most recent card click, and we only refresh the displayed name
  //       from the drawer's heading so toasts stay accurate.
  //
  // We attach two capture-phase listeners so all three paths converge on
  // the same `_SKILL_RUN_STATE` before the modal's submit handler runs.

  // Path (A) — capture-phase BEFORE IIFE's bubble openDrawer fires, so by
  // the time skillDetail drawer is visible, skillId is already stashed.
  document.addEventListener(
    "click",
    (event) => {
      const card = event.target.closest(".skill-card[data-skill-id]");
      if (!card) return;
      const skillId = (card.dataset.skillId || "").trim();
      if (!skillId) return;
      _SKILL_RUN_STATE.activeSkillId = skillId;
      const nameEl = card.querySelector("h3, h2");
      _SKILL_RUN_STATE.activeSkillName = nameEl
        ? nameEl.textContent.trim()
        : _SKILL_RUN_STATE.activeSkillName || null;
    },
    true /* capture */,
  );

  // Paths (B) + (C) — when the user clicks any [data-open-modal=skillRun]
  // we either confirm the skillId from a wrapping [data-skill-id] (B), or
  // refresh the name from the visible skillDetail drawer (C).
  document.addEventListener(
    "click",
    (event) => {
      const opener = event.target.closest('[data-open-modal="skillRun"]');
      if (!opener) return;
      const card = opener.closest("[data-skill-id]");
      if (card) {
        _SKILL_RUN_STATE.activeSkillId = card.dataset.skillId || null;
        const nameEl = card.querySelector(".skill-card h3, h3, h2");
        _SKILL_RUN_STATE.activeSkillName = nameEl
          ? nameEl.textContent.trim()
          : null;
        return;
      }
      const drawer = opener.closest('[data-drawer="skillDetail"]');
      if (drawer) {
        const headEl = drawer.querySelector(".drawer-head h2, h2, h1, .drawer-title");
        if (headEl) {
          _SKILL_RUN_STATE.activeSkillName = headEl.textContent.trim();
        }
        // skillId comes from path (A) — the card click that triggered
        // the drawer to open. handleSkillRunModal still has a final
        // first-card fallback if A never fired.
      }
    },
    true /* capture */,
  );
}

async function handleSkillRunModal(button, layer) {
  const textarea = layer.querySelector("textarea");
  const select = layer.querySelector("select");
  const instruction = (textarea && textarea.value ? textarea.value : "").trim();
  let outputFormat = null;
  if (select) {
    const selected = select.options[select.selectedIndex];
    outputFormat = selected ? (selected.value || selected.textContent || "").trim() : null;
  }
  let skillId = _SKILL_RUN_STATE.activeSkillId;
  if (!skillId) {
    // V1 fallback: pick the first skill in the grid so the modal is never
    // a dead end. P1 we can refuse and toast "请先选择一个 Skill".
    const firstCard = document.querySelector(".skill-card[data-skill-id]");
    if (firstCard) skillId = firstCard.dataset.skillId;
  }
  if (!skillId) {
    toast("没有可用的 Skill，请稍后再试", "warning");
    return null;
  }
  const original = button.innerHTML;
  const disabled = button.disabled;
  button.disabled = true;
  button.innerHTML = "运行中…";
  let result;
  try {
    const inputs = {};
    if (instruction) inputs.instruction = instruction;
    if (outputFormat) inputs.output_format = outputFormat;
    const r = await apiFetch(`/skills/${skillId}/run`, {
      method: "POST",
      body: { input: inputs, save_output: true },
    });
    result = (r && r.data) || r || null;
    closeAllModals();
    const jobId = result && (result.job_id || result.skill_run_id);
    const skillName = _SKILL_RUN_STATE.activeSkillName || "Skill";
    toast(
      jobId
        ? `${skillName} 已入队（job: ${String(jobId).slice(0, 8)}）`
        : `${skillName} 已入队`,
      "success",
    );
    window.dispatchEvent(
      new CustomEvent("mydow:skill-run-queued", {
        detail: { skillId, result, inputs },
      }),
    );
  } catch (e) {
    toast(`Skill 运行失败: ${e.message}`, "error");
  } finally {
    button.disabled = disabled;
    button.innerHTML = original;
  }
  return result;
}

// ─────────────────────────────────────────────  §15.25 / §15.26 PATCH /me  ─
//
// `[data-modal="notificationSettings"]` and `[data-modal="editProfile"]`
// both write back to PRD10 PATCH /api/v1/me. Helper below collects the
// 3 toggle states / form fields and merges them into User.settings JSONB.
//
// Toggle state is read from `.toggle-switch.active` (the IIFE flips this
// class on click). We don't try to be cleverer than the prototype here:
// "active" = on; default = off.

function _readToggleSwitches(layer) {
  const switches = Array.from(layer.querySelectorAll(".toggle-switch"));
  return switches.map((sw) => {
    const isActive =
      sw.classList.contains("active") ||
      sw.getAttribute("aria-checked") === "true";
    const article = sw.closest("article.quick-setting");
    const label = article
      ? (article.querySelector("strong")?.textContent || "").trim()
      : "";
    return { label, active: isActive };
  });
}

// Visible toggle labels in the biz prototype's notificationSettings modal
// → keys recognised by the PRD10 §5.2 settings schema. The backend
// whitelists `notification_enabled` (top-level boolean) plus the keys
// inside `notification_channels` (PRD10_NOTIFICATION_CHANNEL_KEYS — see
// `agent_os/auth/schema.py`). Anything else is silently dropped.
const _NOTIFICATION_TOGGLE_LABEL_TO_PRD10 = {
  "浏览器通知": { kind: "top", key: "notification_enabled" },
  "AI 任务结果": { kind: "channel", key: "ai_done" },
  "知识连接提醒": { kind: "channel", key: "knowledge_link" },
};

async function handleNotificationSettingsModal(button, layer) {
  const toggles = _readToggleSwitches(layer);
  const settings = {};
  const channels = {};
  toggles.forEach((entry) => {
    const mapping = _NOTIFICATION_TOGGLE_LABEL_TO_PRD10[entry.label];
    if (!mapping) return;
    if (mapping.kind === "top") {
      settings[mapping.key] = entry.active;
    } else if (mapping.kind === "channel") {
      channels[mapping.key] = entry.active;
    }
  });
  if (Object.keys(channels).length > 0) {
    settings.notification_channels = channels;
  }
  const payload = { settings };
  const original = button.innerHTML;
  const disabled = button.disabled;
  button.disabled = true;
  button.innerHTML = "保存中…";
  let result;
  try {
    const r = await apiFetch("/me", { method: "PATCH", body: payload });
    result = (r && r.data) || r || null;
    closeAllModals();
    toast("通知偏好已保存", "success");
    window.dispatchEvent(
      new CustomEvent("mydow:me-updated", { detail: { me: result, payload } }),
    );
    refreshProfileChip().catch(() => {});
  } catch (e) {
    toast(`保存失败: ${e.message}`, "error");
  } finally {
    button.disabled = disabled;
    button.innerHTML = original;
  }
  return result;
}

function _editProfileInputs(layer) {
  // The modal's 3 form-field inputs are 姓名 / 邮箱(disabled) / 角色.
  const inputs = layer.querySelectorAll(".form-field input");
  let name = null;
  let displayRole = null;
  inputs.forEach((el) => {
    const labelEl = el.closest(".form-field")?.querySelector("label");
    const label = labelEl ? labelEl.textContent.trim() : "";
    const value = (el.value || "").trim();
    if (el.disabled) return;
    if (label.startsWith("姓名") || label === "Name") name = value;
    else if (label.startsWith("角色") || label.startsWith("Display"))
      displayRole = value;
  });
  return { name, displayRole };
}

async function handleEditProfileModal(button, layer) {
  const { name, displayRole } = _editProfileInputs(layer);
  if (!name) {
    toast("姓名不能为空", "warning");
    return null;
  }
  const payload = { name };
  if (displayRole) {
    payload.settings = { display_role: displayRole };
  }
  const original = button.innerHTML;
  const disabled = button.disabled;
  button.disabled = true;
  button.innerHTML = "保存中…";
  let result;
  try {
    const r = await apiFetch("/me", { method: "PATCH", body: payload });
    result = (r && r.data) || r || null;
    closeAllModals();
    toast("个人资料已更新", "success");
    window.dispatchEvent(
      new CustomEvent("mydow:me-updated", { detail: { me: result, payload } }),
    );
    // Push the new name/plan back into the sidebar chip + topbar avatar +
    // settings page main panel.
    refreshProfileChip().catch(() => {});
    if (result) hydrateProfileMain(result);
  } catch (e) {
    toast(`更新失败: ${e.message}`, "error");
  } finally {
    button.disabled = disabled;
    button.innerHTML = original;
  }
  return result;
}

// ─────────────────────────────────────────────  §15.30 v1.4 sync  ─────────
//
// Three new modals from business prototype v1.4
// (Mydow_Web_Frontend_Backend_Handoff_v1.4_20260507_0058.zip):
//
//   1. aiPersonalize  — 4 select/toggle preferences for Mydow AI workspace.
//      Wired to PATCH /api/v1/me/preferences with {ai_response_style,
//      ai_verbosity, locale, default_kb_context}.
//   2. customInsight  — "+ 新建洞察" creates a Prd10Insight via
//      POST /api/v1/insights with {title, related_card_ids[]}.
//   3. insightHistory — read-only browser of past insights (drawer-style),
//      wired by §15.30b loader (loadInsightHistoryModal) below.
//
// Pre-fill listeners + submit handlers below; bindings into
// `bindHomeModalSubmits` happen in the dispatch table edit a few lines up.

const _AI_PERSONALIZE_FIELD_MAP = {
  response_style: { label: "默认回答风格", scope: "ai_response_style" },
  verbosity: { label: "输出详细程度", scope: "ai_verbosity" },
  language: { label: "常用语言", scope: "locale" },
};

function _readAiPersonalizeForm(layer) {
  const out = {};
  layer.querySelectorAll("select[data-ai-personalize]").forEach((el) => {
    const key = el.dataset.aiPersonalize;
    const map = _AI_PERSONALIZE_FIELD_MAP[key];
    if (!map) return;
    const opt = el.options[el.selectedIndex];
    const text = opt ? (opt.textContent || "").trim() : "";
    if (text) out[map.scope] = text;
  });
  layer
    .querySelectorAll('[data-ai-personalize-toggle="default_kb_context"]')
    .forEach((el) => {
      out.default_kb_context = el.classList.contains("active");
    });
  return out;
}

async function handleAiPersonalizeModal(button, layer) {
  const patch = _readAiPersonalizeForm(layer);
  if (Object.keys(patch).length === 0) {
    toast("没有偏好可保存", "warning");
    return null;
  }
  const original = button.innerHTML;
  const disabled = button.disabled;
  button.disabled = true;
  button.innerHTML = "保存中…";
  let result;
  try {
    const r = await apiFetch("/me/preferences", {
      method: "PATCH",
      body: patch,
    });
    result = (r && r.data) || r || null;
    if (result) {
      window._BIZ_ME_CACHE = result;
      window.dispatchEvent(
        new CustomEvent("mydow:me-updated", {
          detail: { me: result, payload: patch },
        }),
      );
    }
    closeAllModals();
    toast("AI 个性化设置已保存", "success");
  } catch (e) {
    toast(`保存失败: ${e.message}`, "error");
  } finally {
    button.disabled = disabled;
    button.innerHTML = original;
  }
  return result;
}

function _prefillAiPersonalizeFromMe() {
  document.addEventListener(
    "click",
    async (event) => {
      const opener = event.target.closest('[data-open-modal="aiPersonalize"]');
      if (!opener) return;
      const layer = document.querySelector(
        '.surface-layer[data-modal="aiPersonalize"]',
      );
      if (!layer) return;
      const me =
        window._BIZ_ME_CACHE ||
        (await apiFetch("/me").catch(() => null)) ||
        {};
      const settings =
        (me && (me.data ? me.data.settings : me.settings)) || {};
      // Apply persisted values to the selects + toggle.
      layer.querySelectorAll("select[data-ai-personalize]").forEach((el) => {
        const key = el.dataset.aiPersonalize;
        const map = _AI_PERSONALIZE_FIELD_MAP[key];
        if (!map) return;
        const persisted = settings[map.scope];
        if (!persisted) return;
        for (const opt of el.options) {
          if ((opt.textContent || "").trim() === String(persisted).trim()) {
            el.value = opt.value;
            break;
          }
        }
      });
      layer
        .querySelectorAll('[data-ai-personalize-toggle="default_kb_context"]')
        .forEach((el) => {
          if (settings.default_kb_context) el.classList.add("active");
          else el.classList.remove("active");
        });
    },
    true /* capture */,
  );
}

// §15.30b ─ customInsight modal: collects topic + selected related notes,
// then POST /api/v1/insights to create a Prd10Insight (status=draft).
function _readCustomInsightForm(layer) {
  const topicEl = layer.querySelector("[data-new-insight-topic]");
  const title = topicEl ? (topicEl.value || "").trim() : "";
  const noteRows = layer.querySelectorAll(
    ".note-picker-row[data-note-option][data-selected]",
  );
  const related_card_ids = [];
  noteRows.forEach((row) => {
    const id = row.dataset.noteId;
    if (id) related_card_ids.push(id);
  });
  return { title, related_card_ids };
}

async function handleCustomInsightModal(button, layer) {
  const { title, related_card_ids } = _readCustomInsightForm(layer);
  if (!title) {
    toast("请先输入洞察主题", "warning");
    return null;
  }
  const body = {
    title,
    insight_type: "theme_trend",
    summary: `用户自定义洞察：${title}`,
    related_card_ids,
    status: "draft",
  };
  const original = button.innerHTML;
  const disabled = button.disabled;
  button.disabled = true;
  button.innerHTML = "生成中…";
  let result;
  try {
    const r = await apiFetch("/insights", { method: "POST", body });
    result = (r && r.data) || r || null;
    if (result) {
      const insightId =
        (result.insight && result.insight.id) || result.id || "";
      toast(
        insightId
          ? `已创建洞察（${String(insightId).slice(0, 8)}）`
          : "已创建洞察",
        "success",
      );
      closeAllModals();
      // Refresh the insights centre so the new draft shows up.
      try {
        if (typeof refreshInsightsFullPanel === "function") {
          refreshInsightsFullPanel().catch(() => {});
        }
      } catch (_e) {
        /* non-fatal */
      }
    }
  } catch (e) {
    toast(`生成失败: ${e.message}`, "error");
  } finally {
    button.disabled = disabled;
    button.innerHTML = original;
  }
  return result;
}

// Toggle visual state when user picks a note inside the customInsight modal.
function _bindCustomInsightNotePicker() {
  document.addEventListener(
    "click",
    (event) => {
      const row = event.target.closest(
        '[data-modal="customInsight"] .note-picker-row[data-note-option]',
      );
      if (!row) return;
      // Toggle [data-selected] flag + visual state of "选择 / 已选".
      const wasSelected = row.dataset.selected === "1";
      if (wasSelected) {
        delete row.dataset.selected;
      } else {
        row.dataset.selected = "1";
      }
      const checkEl = row.querySelector("[data-note-check]");
      if (checkEl) {
        checkEl.textContent = wasSelected ? "选择" : "已选";
        checkEl.classList.toggle("active", !wasSelected);
      }
      // Enable the "生成洞察" button only if at least topic is non-empty
      // (related notes are optional but recommended).
      const layer = row.closest('[data-modal="customInsight"]');
      const topicEl = layer.querySelector("[data-new-insight-topic]");
      const submitBtn = layer.querySelector("[data-generate-insight]");
      if (topicEl && submitBtn) {
        submitBtn.disabled = !(topicEl.value || "").trim();
      }
      // Update the selected-notes summary line.
      const selected = layer.querySelectorAll(
        ".note-picker-row[data-selected]",
      );
      const target = layer.querySelector("[data-selected-notes]");
      if (target) {
        if (selected.length === 0) {
          target.innerHTML =
            '<span style="color:#8b97aa;font-size:12px;font-weight:650" data-selected-empty>暂未选择关联笔记</span>';
        } else {
          const titles = [...selected]
            .map((r) => r.dataset.noteTitle || "")
            .filter(Boolean);
          target.textContent = `已选 ${selected.length} 篇：${titles.join("、")}`;
        }
      }
    },
    false,
  );
  // Toggle picker visibility.
  document.addEventListener(
    "click",
    (event) => {
      const trigger = event.target.closest(
        '[data-modal="customInsight"] [data-toggle-note-picker]',
      );
      if (!trigger) return;
      const picker = trigger
        .closest('[data-modal="customInsight"]')
        .querySelector("[data-note-picker]");
      if (picker) picker.hidden = !picker.hidden;
    },
    false,
  );
  // Topic-input listener: enable the submit button as user types.
  document.addEventListener(
    "input",
    (event) => {
      const topicEl = event.target.closest(
        '[data-modal="customInsight"] [data-new-insight-topic]',
      );
      if (!topicEl) return;
      const layer = topicEl.closest('[data-modal="customInsight"]');
      const submitBtn = layer.querySelector("[data-generate-insight]");
      if (submitBtn) submitBtn.disabled = !(topicEl.value || "").trim();
    },
    false,
  );
}

// §15.30c ─ insightHistory modal: when opener is clicked, lazy-load real
// /insights data and replace the 3 hard-coded sample cards with the
// authenticated user's last 10 insights. Search input filters by title /
// summary / type prefix.
async function loadInsightHistoryModal() {
  const layer = document.querySelector(
    '.surface-layer[data-modal="insightHistory"]',
  );
  if (!layer) return null;
  const list = layer.querySelector("[data-insight-history-list]");
  if (!list) return null;

  let payload;
  try {
    payload = await apiFetch("/insights?range=month&page_size=10");
  } catch (e) {
    console.warn("[Mydow] /insights for history modal failed", e);
    return null;
  }
  const data = (payload && payload.data) || payload || {};
  const items = data.items || [];
  if (items.length === 0) {
    // Keep the static sample cards as a non-empty fallback so the demo
    // still looks alive on a fresh DB.
    return null;
  }

  const palette = ["color-yellow", "color-green", "color-blue", "color-purple"];
  list.innerHTML = "";
  items.forEach((insight, idx) => {
    const article = document.createElement("article");
    article.className = `history-insight-card ${palette[idx % palette.length]}`;
    article.setAttribute("role", "button");
    article.setAttribute("tabindex", "0");
    article.dataset.openDrawer = "insightDetail";
    article.dataset.historyInsightCard = "1";
    article.dataset.insightId = insight.id || "";
    const meta = insight.created_at
      ? new Date(insight.created_at).toLocaleDateString("zh-CN", {
          month: "long",
          day: "numeric",
        })
      : "";
    const tagLabel = insight.insight_type
      ? String(insight.insight_type).replace("_", " ")
      : "洞察";
    const related = insight.related_card_ids || [];
    article.innerHTML = `
      <div class="insight-title-row">
        <span class="insight-bulb" aria-hidden="true">💡</span>
        <h3>${escapeHtml(insight.title || "未命名洞察")}</h3>
      </div>
      <p class="insight-card-meta">${escapeHtml(tagLabel)} · ${escapeHtml(meta)}</p>
      <p class="insight-summary">${escapeHtml(insight.summary || "")}</p>
      <div class="connected-notes-title"><span>关联笔记 · ${related.length}</span></div>
      <div class="insight-actions"><button class="pill-button small" type="button" data-jump-knowledge="auto">查看来源</button></div>
    `;
    list.appendChild(article);
  });
  return items;
}

function _bindInsightHistoryOpener() {
  document.addEventListener(
    "click",
    (event) => {
      const opener = event.target.closest(
        '[data-open-modal="insightHistory"]',
      );
      if (!opener) return;
      // Don't preventDefault — let the IIFE actually open the modal; we just
      // populate it after a microtask.
      window.setTimeout(() => {
        loadInsightHistoryModal().catch(() => {});
      }, 60);
    },
    false,
  );
  // Search filter inside the modal.
  document.addEventListener(
    "input",
    (event) => {
      const inputEl = event.target.closest("[data-insight-history-search]");
      if (!inputEl) return;
      const layer = inputEl.closest('[data-modal="insightHistory"]');
      if (!layer) return;
      const q = (inputEl.value || "").trim().toLowerCase();
      const cards = layer.querySelectorAll(".history-insight-card");
      let visible = 0;
      cards.forEach((card) => {
        const text = (card.textContent || "").toLowerCase();
        const match = q === "" || text.includes(q);
        card.style.display = match ? "" : "none";
        if (match) visible += 1;
      });
      const empty = layer.querySelector("[data-insight-history-empty]");
      if (empty) empty.hidden = visible !== 0;
    },
    false,
  );
}

function _prefillEditProfileFromMe() {
  // Capture-phase listener on [data-open-modal="editProfile"] — pre-fill
  // the form with the current /me payload before the IIFE opens it.
  document.addEventListener(
    "click",
    async (event) => {
      const opener = event.target.closest('[data-open-modal="editProfile"]');
      if (!opener) return;
      const layer = document.querySelector(
        '.surface-layer[data-modal="editProfile"]',
      );
      if (!layer) return;
      let me;
      try {
        const r = await apiFetch("/me");
        me = (r && r.data) || r || null;
      } catch {
        return;
      }
      if (!me) return;
      const inputs = layer.querySelectorAll(".form-field input");
      inputs.forEach((el) => {
        const labelEl = el.closest(".form-field")?.querySelector("label");
        const label = labelEl ? labelEl.textContent.trim() : "";
        if (label.startsWith("姓名")) {
          el.value = me.name || (me.email ? String(me.email).split("@")[0] : "");
        } else if (label.startsWith("邮箱")) {
          el.value = me.email || "";
        } else if (label.startsWith("角色")) {
          const planRaw = me.plan || "free";
          const planLabel =
            planRaw === "pro"
              ? "Pro Plan 用户"
              : planRaw === "team"
                ? "Team Plan 用户"
                : "Free Plan 用户";
          // Allow user-customised display_role to win over plan-derived label.
          const custom =
            me.settings && me.settings.display_role
              ? me.settings.display_role
              : null;
          el.value = custom || planLabel;
        }
      });
    },
    true /* capture */,
  );
}

// ─────────────────────────────────────────────  §15.16 insights centre  ───
//
// The biz prototype's "完整洞察中心" panel (.insights-full-main) is full of
// hand-crafted static cards. PRD10 §12 (Insights / Reports) is now backed by
// real endpoints (Milestone 24), so this section hydrates:
//
//   * 4 metric tiles  ← /api/v1/insights/summary?range=week
//   * 3 core-insight cards (with dismiss button) ← summary.insights
//   * "最近洞察报告" list ← /api/v1/insights?range=month, *_summary types
//   * "可追溯来源" list  ← /api/v1/feed?page_size=3
//
// Click handlers live in attachInsightsFullPanelHandlers():
//   * .bridge-dismiss-btn → POST /api/v1/insights/{id}/dismiss
//   * .report-row[data-report-id] → GET /api/v1/reports/{id} (toast preview)
//   * [data-insights-full] (the existing prototype toggle) → re-refresh
//     after the panel becomes visible so the data feels "fresh on open".

const INSIGHT_TAG_LABELS = {
  theme_trend: "趋势洞察",
  task_risk: "风险洞察",
  knowledge_gap: "缺口洞察",
  connection: "关联洞察",
  daily_summary: "日报",
  weekly_summary: "周报",
  monthly_summary: "月报",
};

const INSIGHT_ICON_HREFS = {
  theme_trend: "#icon-user",
  task_risk: "#icon-bookmark",
  knowledge_gap: "#icon-book",
  connection: "#icon-link",
  daily_summary: "#icon-cube",
  weekly_summary: "#icon-cube",
  monthly_summary: "#icon-cube",
};

function _formatReportDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("zh-CN", { month: "long", day: "numeric" });
}

function renderMetricTiles(main, summary) {
  const tiles = main.querySelectorAll(".metric-grid .metric-tile");
  if (tiles.length === 0) return;
  const data = (summary && summary.data) || {};
  const stats = data.stats || {};
  const themeDist = data.theme_distribution || [];
  const insights = data.insights || [];

  const spec = [
    {
      label: "本周捕捉",
      value: Number(stats.capture_count || 0),
      note: `较上周 ${stats.capture_count > 0 ? "+" + stats.capture_count : "持平"}`,
    },
    {
      label: "本周洞察",
      value: insights.length,
      note: insights.length > 0 ? `较上周 +${insights.length}` : "持平",
    },
    {
      label: "重点主题",
      value: themeDist.length,
      note: themeDist.length > 0 ? `共 ${themeDist.length} 个` : "暂无",
    },
    {
      label: "知识库文档",
      value: Number(stats.knowledge_count || 0),
      note: `${stats.task_count || 0} 个任务`,
    },
  ];

  tiles.forEach((tile, idx) => {
    if (idx >= spec.length) return;
    const item = spec[idx];
    const h3 = tile.querySelector("h3");
    const strong = tile.querySelector("strong");
    const note = [...tile.children].find(
      (n) => n.tagName === "SPAN" && !n.classList.contains("tag"),
    );
    if (h3) h3.textContent = item.label;
    if (strong) strong.textContent = String(item.value);
    if (note) note.textContent = item.note;
    tile.dataset.bridgeBound = "true";
  });
}

function renderCoreInsightCards(main, summary) {
  const grid = main.querySelector(".insight-wide-panel .core-insight-grid");
  if (!grid) return;
  const data = (summary && summary.data) || {};
  const insights = (data.insights || []).slice(0, 3);
  if (insights.length === 0) {
    return;
  }
  grid.innerHTML = "";
  insights.forEach((it, idx) => {
    const card = document.createElement("article");
    card.className = "core-insight-card";
    card.dataset.insightId = it.id || "";
    card.dataset.insightType = it.insight_type || "";
    card.style.position = "relative";
    const tagLabel = INSIGHT_TAG_LABELS[it.insight_type] || "洞察";
    const iconHref = INSIGHT_ICON_HREFS[it.insight_type] || "#icon-sparkles";
    const iconClass = idx === 1 ? "green" : "";
    card.innerHTML = `
      <span class="notice-icon ${iconClass}"><svg class="icon"><use href="${iconHref}" /></svg></span>
      <h3>${escapeHtml(it.title || "未命名洞察")}</h3>
      <p>${escapeHtml(it.summary || it.body || "AI 基于近期记录生成的洞察")}</p>
      <span class="tag">${escapeHtml(tagLabel)}</span>
      <button class="bridge-dismiss-btn" type="button" aria-label="忽略此洞察"
        style="position:absolute;top:14px;right:14px;padding:4px 9px;border-radius:8px;
        border:1px solid rgba(108,124,153,0.18);background:rgba(255,255,255,0.6);
        color:#5a6b86;font-size:11px;font-weight:600;cursor:pointer;line-height:1">忽略</button>
    `;
    grid.appendChild(card);
  });
  grid.dataset.bridgeBound = "true";
}

function renderReportList(main, listData) {
  const reportList = main.querySelector(
    ".insights-bottom-grid .split-panel:nth-child(1) .report-list",
  );
  if (!reportList) return;
  const items = ((listData && listData.data && listData.data.items) || [])
    .filter((it) =>
      ["daily_summary", "weekly_summary", "monthly_summary"].includes(
        it.insight_type,
      ),
    )
    .slice(0, 3);
  if (items.length === 0) return;
  const iconColors = ["", "purple", "file"];
  reportList.innerHTML = "";
  items.forEach((it, idx) => {
    const row = document.createElement("article");
    row.className = "report-row";
    row.dataset.reportId = it.id || "";
    row.dataset.insightType = it.insight_type || "";
    row.style.cursor = "pointer";
    row.tabIndex = 0;
    const tagLabel = INSIGHT_TAG_LABELS[it.insight_type] || "报告";
    const iconClass = iconColors[idx % iconColors.length];
    const iconHref = INSIGHT_ICON_HREFS[it.insight_type] || "#icon-cube";
    row.innerHTML = `
      <span class="recent-item-icon ${iconClass}"><svg class="icon"><use href="${iconHref}" /></svg></span>
      <div><strong>${escapeHtml(it.title || "未命名")}</strong><span>${escapeHtml(tagLabel)}</span></div>
      <span>${escapeHtml(_formatReportDate(it.created_at))}</span>
    `;
    reportList.appendChild(row);
  });
  reportList.dataset.bridgeBound = "true";
}

function renderSourceList(main, feedData) {
  const sourceList = main.querySelector(
    ".insights-bottom-grid .split-panel:nth-child(2) .source-list",
  );
  if (!sourceList) return;
  const items = ((feedData && feedData.data && feedData.data.items) || []).slice(
    0,
    3,
  );
  if (items.length === 0) return;
  sourceList.innerHTML = "";
  items.forEach((it) => {
    const row = document.createElement("article");
    row.className = "source-row";
    row.dataset.cardId = it.id || "";
    const tag = (it.tags && it.tags[0]) || "灵感";
    row.innerHTML = `
      <span class="source-thumb"></span>
      <div><strong>${escapeHtml(it.title || "未命名")}</strong><span>笔记 · ${escapeHtml(tag)}</span></div>
      <span>${escapeHtml(relTime(it.created_at))}</span>
    `;
    sourceList.appendChild(row);
  });
  sourceList.dataset.bridgeBound = "true";
}

async function refreshInsightsFullPanel() {
  const main = document.querySelector(".insights-full-main");
  if (!main) return null;

  let summary = null;
  let listData = null;
  let feedData = null;

  try {
    summary = await apiFetch("/insights/summary?range=week");
  } catch (e) {
    console.warn("[Mydow] /insights/summary failed", e);
  }
  try {
    listData = await apiFetch("/insights?range=month&page_size=10");
  } catch (e) {
    console.warn("[Mydow] /insights list failed", e);
  }
  try {
    feedData = await apiFetch("/feed?page_size=3");
  } catch (e) {
    console.warn("[Mydow] /feed (insights source) failed", e);
  }

  renderMetricTiles(main, summary);
  renderCoreInsightCards(main, summary);
  renderReportList(main, listData);
  renderSourceList(main, feedData);

  main.dataset.bridgeBound = "true";
  window.dispatchEvent(
    new CustomEvent("mydow:insights-full-loaded", {
      detail: {
        summary: summary && summary.data,
        list: listData && listData.data,
        sources: feedData && feedData.data,
      },
    }),
  );
  return { summary, listData, feedData };
}

async function dismissInsight(insightId) {
  if (!insightId) return;
  return apiFetch(`/insights/${insightId}/dismiss`, { method: "POST" });
}

// ─────────────────────────────────────────────  §15.11 garden board  ──────
//
// The biz prototype's `.garden-main` ships a hand-crafted SVG-on-top-of-DOM
// constellation: 1 ``.garden-node.core`` + 6 surrounding ``.garden-node`` and
// a "连接数 9" pill in `.garden-filters`. This bridge:
//
//   * pulls /api/v1/garden/overview for the real edge count + top topics;
//   * uses the user's most-used tag as the core node label and the next 6
//     tags as the surrounding nodes (preserves the existing visual layout
//     and color coding);
//   * makes every node click run /api/v1/search?q={topic} and surface the
//     hit count in a toast — the V1 contract per §15.11 ("V1 用 search by
//     topic 兜底" because there's no /garden/nodes/:id GET yet).
//
// Falls back silently when /garden/overview fails or returns empty topics
// — the static prototype's seven hand-crafted cards stay visible so the
// page never looks broken.

const GARDEN_NODE_SELECTORS = [
  ".garden-node.top",
  ".garden-node.left-top",
  ".garden-node.left-bottom",
  ".garden-node.bottom",
  ".garden-node.right-top",
  ".garden-node.right-bottom",
];

function _setGardenNodeTopicTitle(nodeEl, topic) {
  if (!nodeEl || !topic) return;
  const strong = nodeEl.querySelector(".node-copy strong");
  if (strong) {
    strong.textContent = topic;
    return;
  }
  _setNodeLabel(nodeEl, topic);
}

function _setNodeLabel(nodeEl, label) {
  if (!nodeEl || !label) return;
  // .garden-node has [bubble svg, text node, ...]; we replace just the text
  // node so the icon stays. Fall back to setting textContent on the last
  // text-bearing child.
  const textNodes = [...nodeEl.childNodes].filter(
    (n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim().length > 0,
  );
  if (textNodes.length > 0) {
    textNodes[textNodes.length - 1].textContent = label;
  } else {
    // Append a new text node next to the bubble when the prototype HTML
    // has trimmed whitespace away (rare, but defensive).
    nodeEl.appendChild(document.createTextNode(label));
  }
}

async function refreshGardenBoard() {
  const main = document.querySelector(".garden-main");
  if (!main) return null;
  let overview = null;
  try {
    overview = await apiFetch("/garden/overview");
  } catch (e) {
    console.warn("[Mydow] /garden/overview failed", e);
    return null;
  }
  const data = (overview && overview.data) || {};
  const topTopics = Array.isArray(data.top_topics) ? data.top_topics : [];
  const edgeCount = Number(data.edge_count || 0);
  const nodeCount = Number(data.node_count || 0);

  // Filter pill: "连接数 N" → live edge_count.
  const filters = main.querySelectorAll(".garden-filters .pill-button");
  const edgeFilter = [...filters].find((b) =>
    /连接数/.test(b.textContent || ""),
  );
  if (edgeFilter) {
    // Wipe existing trailing text node (which holds "连接数 9") while keeping
    // the leading <svg class="icon"> child.
    [...edgeFilter.childNodes]
      .filter((n) => n.nodeType === Node.TEXT_NODE)
      .forEach((n) => n.remove());
    edgeFilter.appendChild(document.createTextNode(`连接数 ${edgeCount}`));
    edgeFilter.dataset.bridgeBound = "true";
    edgeFilter.dataset.edgeCount = String(edgeCount);
  }

  if (topTopics.length > 0) {
    // Core node label = top topic.
    const core = main.querySelector(".garden-node.core strong");
    if (core) {
      core.textContent = topTopics[0];
    }
    const coreNode = main.querySelector(".garden-node.core");
    if (coreNode) {
      coreNode.dataset.gardenTopic = topTopics[0];
      coreNode.dataset.bridgeBound = "true";
      coreNode.style.cursor = "pointer";
    }

    // Surrounding nodes: legacy v13 used positional classes (.top / .left-top…);
    // v1.4+ uses semantic classes (research/note/link…) — hydrate up to 6
    // satellites inside `.garden-map`.
    const legacyHits = [];
    GARDEN_NODE_SELECTORS.forEach((sel) => {
      const node = main.querySelector(sel);
      if (node) legacyHits.push(node);
    });

    const satellites =
      legacyHits.length >= 6
        ? legacyHits.slice(0, 6)
        : [
            ...main.querySelectorAll(".garden-map .garden-node:not(.core)"),
          ].slice(0, 6);
    satellites.forEach((node, idx) => {
      const topic = topTopics[idx + 1];
      if (!topic) return;
      _setGardenNodeTopicTitle(node, topic);
      node.dataset.gardenTopic = topic;
      node.dataset.bridgeBound = "true";
      node.style.cursor = "pointer";
    });
  }

  main.dataset.bridgeBound = "true";
  main.dataset.bridgeNodeCount = String(nodeCount);
  main.dataset.bridgeEdgeCount = String(edgeCount);

  window.dispatchEvent(
    new CustomEvent("mydow:garden-loaded", {
      detail: { overview: data },
    }),
  );
  return data;
}

async function searchByTopic(topic) {
  if (!topic) return null;
  const q = encodeURIComponent(topic);
  return apiFetch(`/search?q=${q}&page_size=5`);
}

// ─────────────────────────────────────────────  §15.15 skills marketplace
//
// The biz prototype's `.skills-main` ships ~6 hand-crafted skill-card
// articles. PRD10 §17 (`/api/v1/skills`) has the real list (5 demo
// rows from seed_prd10.py) and a real run endpoint. The bridge
// replaces the static grid with real cards and wires the "试用" / "查看"
// buttons to ``POST /api/v1/skills/{id}/run``.

const SKILL_AVATAR_PALETTE = [
  { class: "", iconHref: "#icon-message" },
  { class: "purple", iconHref: "#icon-chart" },
  { class: "green", iconHref: "#icon-file-text" },
  { class: "yellow", iconHref: "#icon-box" },
  { class: "", iconHref: "#icon-ai" },
  { class: "purple", iconHref: "#icon-calendar" },
  { class: "green", iconHref: "#icon-link" },
  { class: "yellow", iconHref: "#icon-bookmark" },
];

function _formatUsageCount(n) {
  if (typeof n !== "number") return "0";
  if (n >= 1000) {
    const k = (n / 1000).toFixed(1).replace(/\.0$/, "");
    return `${k}k`;
  }
  return String(n);
}

function renderSkillCard(skill, idx) {
  const avatar = SKILL_AVATAR_PALETTE[idx % SKILL_AVATAR_PALETTE.length];
  const tags = (skill.tags || skill.tag_list || []).slice(0, 3);
  const tagsHtml =
    tags.length > 0
      ? tags
          .map((t) => `<span class="tag">${escapeHtml(t)}</span>`)
          .join("")
      : "";
  const desc = skill.description || skill.summary || "";
  const author =
    skill.author ||
    (skill.metadata && skill.metadata.author) ||
    skill.created_by ||
    "Mydow";
  const rating = skill.rating || (skill.metadata && skill.metadata.rating) || "4.8";
  const usage = _formatUsageCount(
    Number(skill.usage_count != null ? skill.usage_count : 0),
  );
  const article = document.createElement("article");
  article.className = "skill-card";
  article.dataset.skillId = skill.id || "";
  article.innerHTML = `
    <div class="skill-card-head">
      <span class="skill-icon ${avatar.class}"><svg class="icon"><use href="${avatar.iconHref}" /></svg></span>
      <h3>${escapeHtml(skill.name || skill.title || "未命名 Skill")}</h3>
    </div>
    <p>${escapeHtml(desc)}</p>
    <div class="tags">${tagsHtml}</div>
    <div class="skill-meta">
      <span>by ${escapeHtml(author)}</span>
      <span>★ ${escapeHtml(String(rating))}</span>
      <span>${escapeHtml(usage)}</span>
      <button class="pill-button small bridge-skill-run" type="button" data-skill-id="${skill.id || ""}">试用</button>
    </div>
  `;
  return article;
}

async function refreshSkillsGrid() {
  const grid = document.querySelector(".skills-main .skill-grid");
  if (!grid) return null;
  let payload;
  try {
    payload = await apiFetch("/skills?page_size=20");
  } catch (e) {
    console.warn("[Mydow] /skills failed", e);
    return null;
  }
  const items = ((payload && payload.data && payload.data.items) || []).slice(
    0,
    12,
  );
  if (items.length === 0) {
    return payload;
  }
  grid.innerHTML = "";
  items.forEach((skill, idx) => grid.appendChild(renderSkillCard(skill, idx)));
  grid.dataset.bridgeBound = "true";
  grid.dataset.bridgeCount = String(items.length);
  window.dispatchEvent(
    new CustomEvent("mydow:skills-loaded", { detail: { items } }),
  );
  return payload;
}

async function runSkill(skillId, inputs = {}) {
  if (!skillId) return null;
  return apiFetch(`/skills/${skillId}/run`, {
    method: "POST",
    body: { inputs },
  });
}

// ─────────────────────────────────────────────  §15.12 Mydow AI workspace
//
// The biz prototype's `.ai-main` ships a static composer + 5-row history
// list + a hand-crafted "AI 产品设计方案" answer card. PRD10 §11 has real
// conversations + streaming SSE (the same endpoint Milestone 25 hardened
// with retry/keepalive). The bridge:
//
//   * /api/v1/ai/conversations?page_size=10 → repopulate `.ai-history-list`
//     with real conversation rows (data-conversation-id);
//   * .send-button click + .ai-input keypress (Enter without shift) →
//     /api/v1/ai/conversations (lazy create if none active) →
//     POST /messages/stream + read SSE stream + append tokens into a
//     single growing assistant bubble in `.ai-answer`;
//   * history item click → swap active conversation + re-render the
//     answer area from the conversation detail.
//
// Falls back silently when /ai/* fails — the static prototype's
// hand-crafted card stays visible so the page never looks broken.

const AI_STATE = {
  active_conversation_id: null,
  conversations: [],
  // Track the per-stream EventSource-style abort controller so a second
  // submission cancels the previous in-flight stream.
  current_stream_controller: null,
};

function _formatConvDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const today = new Date();
  if (d.toDateString() === today.toDateString()) {
    return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  }
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (d.toDateString() === yesterday.toDateString()) {
    return `昨天 ${d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`;
  }
  return d.toLocaleDateString("zh-CN", { month: "long", day: "numeric" });
}

/** v1.4 HTML: GPT-style thread + `.ai-message-list` (no `.ai-history-list` / `.ai-answer`). */
function _isAiV14Layout() {
  return Boolean(document.querySelector(".ai-main .ai-message-list"));
}

function _aiPageShell() {
  return document.querySelector(".page");
}

function _ensureV14ChatOpen() {
  const shell = _aiPageShell();
  if (shell && _isAiV14Layout() && !shell.classList.contains("ai-chat-open")) {
    shell.classList.add("ai-chat-open");
  }
}

function aiMessageMount() {
  return (
    document.querySelector(".ai-main .ai-message-list") ||
    document.querySelector(".ai-main .ai-answer")
  );
}

async function refreshAiHistory() {
  const listLegacy = document.querySelector(".ai-main .ai-history-list");
  const sidebar = document.querySelector(".ai-main .ai-history-sidebar");

  let payload;
  try {
    payload = await apiFetch("/ai/conversations?page_size=10");
  } catch (e) {
    console.warn("[Mydow] /ai/conversations failed", e);
    return null;
  }
  const items = (payload && payload.data && payload.data.items) || [];

  AI_STATE.conversations = items;
  if (!AI_STATE.active_conversation_id && items[0]) {
    AI_STATE.active_conversation_id = items[0].id;
  }

  if (listLegacy) {
    if (items.length === 0) {
      if (AI_STATE.active_conversation_id) {
        loadAndRenderConversation(AI_STATE.active_conversation_id).catch((e) =>
          console.warn("[Mydow] load conversation failed", e),
        );
      }
      return payload;
    }
    listLegacy.innerHTML = "";
    items.forEach((conv) => {
      const btn = document.createElement("button");
      btn.className = "ai-history-item";
      btn.type = "button";
      btn.dataset.conversationId = conv.id || "";
      if (conv.id === AI_STATE.active_conversation_id) {
        btn.classList.add("active");
      }
      const title =
        conv.title ||
        (conv.last_message_preview && conv.last_message_preview.slice(0, 30)) ||
        "新的对话";
      btn.innerHTML = `
      <strong>${escapeHtml(title)}</strong>
      <span>${escapeHtml(_formatConvDate(conv.updated_at || conv.created_at))}</span>
    `;
      listLegacy.appendChild(btn);
    });
    listLegacy.dataset.bridgeBound = "true";
    listLegacy.dataset.bridgeCount = String(items.length);
  } else if (sidebar) {
    sidebar.querySelectorAll(".ai-history-group").forEach((g) => g.remove());
    if (items.length > 0) {
      const group = document.createElement("div");
      group.className = "ai-history-group";
      const label = document.createElement("span");
      label.textContent = "对话";
      group.appendChild(label);
      items.forEach((conv) => {
        const btn = document.createElement("button");
        btn.className = "ai-history-thread";
        btn.type = "button";
        btn.dataset.conversationId = conv.id || "";
        btn.setAttribute("data-ai-chat-open", "");
        if (conv.id === AI_STATE.active_conversation_id) {
          btn.classList.add("active");
        }
        const title =
          conv.title ||
          (conv.last_message_preview &&
            conv.last_message_preview.slice(0, 36)) ||
          "新的对话";
        const when = _formatConvDate(conv.updated_at || conv.created_at);
        btn.innerHTML = `
          <svg class="icon"><use href="#icon-message" /></svg>
          <strong>${escapeHtml(title)}</strong>
          <small>${escapeHtml(when)}</small>
        `;
        group.appendChild(btn);
      });
      const search = sidebar.querySelector(".ai-history-search");
      if (search) {
        search.insertAdjacentElement("afterend", group);
      } else {
        sidebar.appendChild(group);
      }
      sidebar.dataset.bridgeCount = String(items.length);
    }
  }

  if (AI_STATE.active_conversation_id) {
    loadAndRenderConversation(AI_STATE.active_conversation_id).catch((e) =>
      console.warn("[Mydow] load conversation failed", e),
    );
  }
  return payload;
}

async function loadAndRenderConversation(conversationId) {
  if (!conversationId) return null;
  let detail;
  try {
    detail = await apiFetch(`/ai/conversations/${conversationId}`);
  } catch (e) {
    console.warn("[Mydow] /ai/conversations/{id} failed", e);
    return null;
  }
  const data = (detail && detail.data) || {};
  const conv = data.conversation || {};
  const messages = data.messages || [];
  const v14 = _isAiV14Layout();
  const titleLabel = document.querySelector(
    ".ai-main .ai-chat-title [data-inline-label]",
  );
  if (titleLabel) {
    titleLabel.textContent = conv.title || "新的对话";
  }
  const answerMain = aiMessageMount();
  const answerTitle = answerMain?.querySelector(".ai-answer-title h2");
  if (answerTitle && !v14) {
    // Preserve the leading <svg> icon, replace only the trailing text.
    [...answerTitle.childNodes]
      .filter((n) => n.nodeType === Node.TEXT_NODE)
      .forEach((n) => n.remove());
    answerTitle.appendChild(
      document.createTextNode(" " + (conv.title || "新的对话")),
    );
  }
  if (!answerMain) return data;

  if (v14) {
    answerMain.innerHTML = "";
  } else {
    // Replace everything below `.ai-answer-title` with rendered messages.
    const title = answerMain.querySelector(".ai-answer-title");
    while (answerMain.lastChild && answerMain.lastChild !== title) {
      answerMain.removeChild(answerMain.lastChild);
    }
  }

  if (messages.length === 0) {
    const empty = document.createElement("p");
    empty.className = "bridge-ai-empty";
    empty.style.cssText = "padding:24px;text-align:center;color:#7a8aa6";
    empty.textContent =
      "新会话已就绪。在上方输入框写一句你想问 AI 的内容。";
    answerMain.appendChild(empty);
    answerMain.dataset.bridgeBound = "true";
    return data;
  }

  messages.forEach((msg) => {
    const bubble = renderAiBubble(msg);
    answerMain.appendChild(bubble);
  });
  answerMain.dataset.bridgeBound = "true";
  return data;
}

function renderAiBubble(msg) {
  const wrap = document.createElement("div");
  wrap.className = `bridge-ai-bubble bridge-ai-${msg.role || "assistant"}`;
  wrap.dataset.messageId = msg.id || "";
  wrap.dataset.role = msg.role || "assistant";
  wrap.style.cssText = [
    "padding:14px 18px",
    "border-radius:14px",
    "margin-top:14px",
    msg.role === "user"
      ? "background:rgba(99,135,232,0.10);border:1px solid rgba(99,135,232,0.18)"
      : "background:rgba(255,255,255,0.55);border:1px solid rgba(108,124,153,0.16)",
    "white-space:pre-wrap",
    "line-height:1.6",
    "color:#28344c",
    "font-size:14px",
  ].join(";");
  const role = document.createElement("div");
  role.style.cssText =
    "font-size:11px;font-weight:600;color:#7a8aa6;margin-bottom:6px;letter-spacing:.04em;";
  role.textContent = msg.role === "user" ? "你" : "Mydow AI";
  wrap.appendChild(role);
  const body = document.createElement("div");
  body.className = "bridge-ai-body";
  body.textContent = msg.content || "";
  wrap.appendChild(body);
  return wrap;
}

function aiInputElement() {
  if (_isAiV14Layout()) {
    const shell = _aiPageShell();
    const chatOpen = shell && shell.classList.contains("ai-chat-open");
    if (chatOpen) {
      return document.querySelector(
        ".ai-main .ai-chat-composer textarea.ai-input",
      );
    }
    return document.querySelector(
      '.ai-main .ai-composer[data-ai-composer="home"] textarea.ai-input',
    );
  }
  return document.querySelector(".ai-main .ai-composer .ai-input");
}

function aiInputContent() {
  const el = aiInputElement();
  if (!el) return "";
  if (el.tagName === "TEXTAREA" || el.tagName === "INPUT") {
    const v = (el.value || "").trim();
    const ph = (el.getAttribute("placeholder") || "").trim();
    if (ph && v === ph) return "";
    return v;
  }
  const raw = el.textContent || "";
  // The static prototype's div has no placeholder attribute; instead it
  // ships the placeholder text verbatim. Treat that exact string as
  // "empty" so the user has to type something to fire a request.
  const placeholder = "询问、搜索或创作任何内容...";
  return raw.trim() === placeholder ? "" : raw.trim();
}

function clearAiInput() {
  const el = aiInputElement();
  if (!el) return;
  if (el.tagName === "TEXTAREA" || el.tagName === "INPUT") {
    el.value = "";
  } else {
    el.textContent = "";
  }
}

async function ensureActiveConversation() {
  if (AI_STATE.active_conversation_id) return AI_STATE.active_conversation_id;
  // Try the most recent conversation first.
  if (AI_STATE.conversations[0]) {
    AI_STATE.active_conversation_id = AI_STATE.conversations[0].id;
    return AI_STATE.active_conversation_id;
  }
  // Otherwise create one.
  const created = await apiFetch("/ai/conversations", {
    method: "POST",
    body: { title: "新的对话", mode: "general" },
  });
  const conv = (created && created.data) || {};
  AI_STATE.active_conversation_id = conv.id;
  AI_STATE.conversations.unshift(conv);
  return conv.id;
}

function _uiAiModelLabelToPreference(label) {
  const m = {
    "Opus 4.6": "opus-4.6",
    "Gemini 2.5 Flash": "gemini-2.5-flash",
    "GPT-5.2": "gpt-5.2",
    "Mydow Auto": "auto",
  };
  return m[label] || "auto";
}

function _preferenceSlugToUiAiModel(slug) {
  const s = String(slug || "auto");
  const m = {
    "opus-4.6": "Opus 4.6",
    "gemini-2.5-flash": "Gemini 2.5 Flash",
    "gpt-5.2": "GPT-5.2",
    auto: "Mydow Auto",
  };
  return m[s] || "Mydow Auto";
}

function _readAiModelSlugForStream() {
  const labelEl = document.querySelector(
    '[data-inline-menu="aiModel"] [data-inline-label]',
  );
  const label = labelEl?.textContent?.trim();
  const fromDom =
    label && label.length ? _uiAiModelLabelToPreference(label) : null;
  if (fromDom && fromDom !== "auto") return fromDom;
  const meSlug = window._BIZ_ME_CACHE?.settings?.default_ai_model;
  if (meSlug && String(meSlug) !== "auto") return String(meSlug);
  return null;
}

function hydrateAiModelControlFromPreferences(me) {
  if (!me || !me.settings) return;
  const slug = me.settings.default_ai_model || "auto";
  const label = _preferenceSlugToUiAiModel(slug);
  document
    .querySelectorAll('[data-inline-menu="aiModel"] [data-inline-label]')
    .forEach((el) => {
      el.textContent = label;
    });
}

let _aiModelPrefBound = false;
function bindAiModelPreferenceSync() {
  if (_aiModelPrefBound) return;
  _aiModelPrefBound = true;
  document.addEventListener(
    "click",
    (event) => {
      const btn = event.target.closest(
        ".inline-popover.ai-model-popover button[data-menu-value]",
      );
      if (!btn) return;
      const label = btn.dataset.menuValue || "";
      window.setTimeout(async () => {
        const slug = _uiAiModelLabelToPreference(label);
        try {
          await patchMePreference({ default_ai_model: slug });
          window._BIZ_ME_CACHE = window._BIZ_ME_CACHE || {};
          window._BIZ_ME_CACHE.settings =
            window._BIZ_ME_CACHE.settings || {};
          window._BIZ_ME_CACHE.settings.default_ai_model = slug;
        } catch (e) {
          toast(`保存默认模型失败: ${e.message}`, "error");
        }
      }, 0);
    },
    true,
  );
}

async function streamAiMessage(conversationId, content) {
  if (!conversationId || !content) return;

  // Cancel any previous in-flight stream to keep a single bubble pair.
  if (AI_STATE.current_stream_controller) {
    try {
      AI_STATE.current_stream_controller.abort();
    } catch {}
  }
  const ctrl = new AbortController();
  AI_STATE.current_stream_controller = ctrl;

  // Append user bubble + placeholder assistant bubble immediately.
  const answerMain = aiMessageMount();
  let assistantBody = null;
  if (answerMain) {
    const userBubble = renderAiBubble({ role: "user", content });
    answerMain.appendChild(userBubble);
    const assistantBubble = renderAiBubble({
      role: "assistant",
      content: "",
    });
    assistantBody = assistantBubble.querySelector(".bridge-ai-body");
    if (assistantBody) assistantBody.textContent = "（生成中…）";
    answerMain.appendChild(assistantBubble);
    answerMain.scrollTop = answerMain.scrollHeight;
  }

  const url = `${API_BASE}/ai/conversations/${conversationId}/messages/stream`;
  const body = { content, attachments: [] };
  const aiSlug = _readAiModelSlugForStream();
  if (aiSlug) body.ai_model = aiSlug;
  if (AI_STATE.pending_context_scope) {
    body.context_scope = AI_STATE.pending_context_scope;
  }
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token()}`,
      Accept: "text/event-stream",
    },
    body: JSON.stringify(body),
    signal: ctrl.signal,
  });
  // Context is one-shot per message — clear after consumption.
  AI_STATE.pending_context_scope = null;

  if (!resp.ok || !resp.body) {
    if (assistantBody) {
      assistantBody.textContent = `（生成失败：${resp.status} ${resp.statusText}）`;
    }
    toast(`AI 生成失败：${resp.status}`, "error");
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let firstToken = true;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() || "";
    for (const block of blocks) {
      const line = block.trim();
      if (!line) continue;
      const eventLine = line
        .split(/\r?\n/)
        .find((l) => l.startsWith("event:"));
      const dataLine = line.split(/\r?\n/).find((l) => l.startsWith("data:"));
      if (!eventLine || !dataLine) continue;
      const eventType = eventLine.split(":", 1)[0]
        ? eventLine.slice(eventLine.indexOf(":") + 1).trim()
        : "";
      const dataRaw = dataLine.slice(dataLine.indexOf(":") + 1).trim();
      let payload = null;
      try {
        payload = JSON.parse(dataRaw);
      } catch {
        payload = { _raw: dataRaw };
      }
      if (eventType === "meta" && payload) {
        // Capture the assistant message id so §15.14 (save-to-kb) knows
        // which message to send to the backend.
        if (payload.assistant_message_id) {
          AI_STATE.last_assistant_message_id = payload.assistant_message_id;
        }
        continue;
      }
      if (eventType === "token" && payload && payload.delta && assistantBody) {
        if (firstToken) {
          assistantBody.textContent = "";
          firstToken = false;
        }
        assistantBody.textContent += payload.delta;
        if (answerMain) answerMain.scrollTop = answerMain.scrollHeight;
      } else if (eventType === "keepalive") {
        // Visual no-op; the heartbeat is for the proxy, not the user.
      } else if (eventType === "error") {
        if (assistantBody) {
          assistantBody.textContent = `（错误：${(payload && payload.message) || "未知错误"}）`;
        }
      } else if (eventType === "done") {
        // Final assertion: if we never got a token but got `done`, surface
        // the placeholder so the user knows we landed.
        if (firstToken && assistantBody) {
          assistantBody.textContent =
            "（已收到回答，但流式输出为空——离线占位模式。）";
        }
      }
    }
  }
  AI_STATE.current_stream_controller = null;
}

async function submitAiMessage(content) {
  const trimmed = (content || "").trim();
  if (!trimmed) {
    toast("请先输入消息", "warning");
    return;
  }
  let conversationId;
  try {
    conversationId = await ensureActiveConversation();
  } catch (e) {
    toast(`无法创建会话: ${e.message}`, "error");
    return;
  }
  _ensureV14ChatOpen();
  clearAiInput();
  try {
    await streamAiMessage(conversationId, trimmed);
    // After stream finishes, refresh history list so the new last_message
    // preview shows up.
    refreshAiHistory().catch(() => {});
  } catch (e) {
    if (e.name !== "AbortError") {
      toast(`AI 生成失败: ${e.message}`, "error");
    }
  }
}

// ─────────────────────────────────────────────  §15.13 AI context  ───────
//
// The biz prototype's `[data-modal="aiContext"]` ships 2 hand-crafted
// suggestion rows. Bridge lazily replaces them with real /search hits
// the moment the modal becomes visible, then caches the selected ids
// on AI_STATE.pending_context_scope so the next ``submitAiMessage()``
// payload carries them into the assistant request.

const _AI_CONTEXT_STATE = { selected_ids: new Set() };

function _renderContextRow(item) {
  const row = document.createElement("article");
  row.className = "notice-row";
  row.dataset.contextId = item.object_id || item.id || "";
  row.dataset.contextType = item.object_type || item.item_type || "card";
  row.style.gridTemplateColumns = "48px minmax(0,1fr) 80px";
  const title = escapeHtml(item.title || "未命名");
  const summary = escapeHtml(
    item.summary || item.snippet || item.content || "",
  ).slice(0, 80);
  const iconCls =
    item.object_type === "document"
      ? ""
      : item.object_type === "folder"
        ? "purple"
        : item.object_type === "skill"
          ? "yellow"
          : "green";
  const iconHref =
    item.object_type === "document"
      ? "#icon-file-text"
      : item.object_type === "folder"
        ? "#icon-folder"
        : item.object_type === "skill"
          ? "#icon-grid"
          : "#icon-network";
  const sel = _AI_CONTEXT_STATE.selected_ids.has(row.dataset.contextId);
  row.innerHTML = `
    <span class="notice-icon ${iconCls}"><svg class="icon"><use href="${iconHref}" /></svg></span>
    <div class="notice-body"><h2>${title}</h2><p>${summary}</p></div>
    <button class="notice-action bridge-context-toggle" type="button">${sel ? "已选" : "选择"}</button>
  `;
  return row;
}

async function refreshAiContextModal(query = "") {
  const layer = document.querySelector('.surface-layer[data-modal="aiContext"]');
  if (!layer) return null;
  const list = layer.querySelector(".notice-list");
  if (!list) return null;
  let payload;
  try {
    const q = (query || "").trim();
    const url = q
      ? `/search?q=${encodeURIComponent(q)}&page_size=8`
      : "/feed?page_size=6";
    payload = await apiFetch(url);
  } catch (e) {
    console.warn("[Mydow] context modal refresh failed", e);
    return null;
  }
  const items = (payload && payload.data && payload.data.items) || [];
  if (items.length === 0) return payload;
  list.innerHTML = "";
  items.forEach((item) => list.appendChild(_renderContextRow(item)));
  list.dataset.bridgeBound = "true";
  return payload;
}

function attachAiContextHandlers() {
  const layer = document.querySelector('.surface-layer[data-modal="aiContext"]');
  if (!layer || layer.dataset.bridgeHandlers === "true") return;

  document.querySelectorAll('[data-open-modal="aiContext"]').forEach((btn) => {
    btn.addEventListener("click", () => {
      window.setTimeout(() => refreshAiContextModal().catch(() => {}), 80);
    });
  });

  layer.addEventListener("click", (ev) => {
    const toggle = ev.target.closest(".bridge-context-toggle");
    if (toggle) {
      const row = toggle.closest("[data-context-id]");
      if (!row) return;
      const id = row.dataset.contextId;
      if (_AI_CONTEXT_STATE.selected_ids.has(id)) {
        _AI_CONTEXT_STATE.selected_ids.delete(id);
        toggle.textContent = "选择";
      } else {
        _AI_CONTEXT_STATE.selected_ids.add(id);
        toggle.textContent = "已选";
      }
      return;
    }

    const footBtn = ev.target.closest(
      ".modal-foot-actions .pill-button:not([data-close-layer])",
    );
    if (footBtn && layer.contains(footBtn)) {
      const ids = [..._AI_CONTEXT_STATE.selected_ids];
      AI_STATE.pending_context_scope =
        ids.length > 0 ? { document_ids: ids } : null;
      toast(
        ids.length > 0
          ? `已选 ${ids.length} 条作为下次 AI 对话上下文`
          : "未选中任何上下文",
        ids.length > 0 ? "success" : "info",
      );
      layer.setAttribute("hidden", "");
      document.body.classList.remove("is-modal-open");
    }
  });

  layer.dataset.bridgeHandlers = "true";
}

// ─────────────────────────────────────────────  §15.14 AI save-to-KB  ────
//
// The biz prototype's `[data-modal="aiSave"]` lets the user save the
// current AI answer to the knowledge base. PRD10 §11.7 has a real
// endpoint (``POST /api/v1/ai/messages/{id}/save-to-kb``) that enqueues
// a ``Job`` so Agent 2's worker materializes a ``Document`` row.

function _resolveLastAssistantMessageId() {
  if (AI_STATE.last_assistant_message_id) {
    return AI_STATE.last_assistant_message_id;
  }
  const last = [
    ...document.querySelectorAll(
      '.ai-main .bridge-ai-bubble[data-role="assistant"][data-message-id]',
    ),
  ].pop();
  return last ? last.dataset.messageId : "";
}

function attachAiSaveHandlers() {
  const layer = document.querySelector('.surface-layer[data-modal="aiSave"]');
  if (!layer || layer.dataset.bridgeHandlers === "true") return;

  layer.addEventListener("click", async (ev) => {
    if (ev.target.closest("[data-close-layer]")) return;
    const saveBtn = ev.target.closest(
      ".modal-foot-actions .pill-button:not([data-close-layer])",
    );
    if (!saveBtn || !layer.contains(saveBtn)) return;
    ev.preventDefault();
    ev.stopPropagation();

    const id = _resolveLastAssistantMessageId();
    if (!id) {
      toast("未找到可保存的 AI 回答，请先发送一条消息", "warning");
      return;
    }

    const titleInput = layer.querySelector(".form-field input");
    const tagEls = layer.querySelectorAll(".source-chip-list .tag");
    const title = titleInput ? titleInput.value.trim() : "";
    const tags = [...tagEls]
      .map((t) => (t.textContent || "").trim())
      .filter(Boolean);

    saveBtn.disabled = true;
    saveBtn.style.opacity = "0.6";
    const originalLabel = saveBtn.textContent;
    saveBtn.textContent = "保存中…";
    try {
      const r = await apiFetch(`/ai/messages/${id}/save-to-kb`, {
        method: "POST",
        body: { folder_id: null, title: title || null, tags },
      });
      const data = (r && r.data) || {};
      const jobId = data.job_id || (data.job && data.job.id) || "";
      toast(
        `AI 结果已入队保存${jobId ? `（job: ${jobId.slice(0, 8)}）` : ""}`,
        "success",
      );
      layer.setAttribute("hidden", "");
      document.body.classList.remove("is-modal-open");
    } catch (e) {
      toast(`保存失败：${e.message}`, "error");
    } finally {
      saveBtn.disabled = false;
      saveBtn.style.opacity = "1";
      saveBtn.textContent = originalLabel || "保存";
    }
  });

  layer.dataset.bridgeHandlers = "true";
}

// ─────────────────────────────────────────────  §15.19 global search  ───
//
// The biz prototype's `.search-modal` has hand-crafted result rows.
// Bridge replaces them with real /search hits as the user types.
// PRD10 §13: GET /search.

let _searchDebounceTimer = null;

function _renderSearchResultRow(item) {
  const btn = document.createElement("button");
  btn.className = "result-row";
  btn.type = "button";
  btn.dataset.searchObjectId = item.object_id || "";
  btn.dataset.searchObjectType = item.object_type || "card";
  const iconHref =
    item.object_type === "document"
      ? "#icon-file-text"
      : item.object_type === "folder"
        ? "#icon-folder"
        : item.object_type === "task"
          ? "#icon-list"
          : item.object_type === "skill"
            ? "#icon-grid"
            : "#icon-cube";
  btn.innerHTML = `
    <svg class="icon"><use href="${iconHref}" /></svg>
    <span>${escapeHtml(item.title || "未命名")}</span>
    <svg class="icon" style="width: 16px; height: 16px"><use href="#icon-chevron-right" /></svg>
  `;
  return btn;
}

function _searchOptsFromFilterBar() {
  const sortLabel =
    document
      .querySelector('[data-inline-menu="searchSort"] [data-inline-label]')
      ?.textContent?.trim() || "";
  const locLabel =
    document
      .querySelector('[data-inline-menu="searchLocation"] [data-inline-label]')
      ?.textContent?.trim() || "";
  let mode = "keyword";
  if (sortLabel.includes("相关度")) mode = "semantic";
  const object_types = [];
  if (locLabel.includes("知识库")) {
    object_types.push("folder", "document", "card");
  }
  if (locLabel.includes("数字花园")) {
    object_types.push("card", "insight");
  }
  return { mode, object_types };
}

async function performGlobalSearch(query, opts = {}) {
  const modal = document.querySelector(".search-modal");
  if (!modal) return null;
  const resultsHost = modal.querySelector(".search-results");
  if (!resultsHost) return null;
  const q = (query || "").trim();
  if (!q) {
    resultsHost.dataset.bridgeBound = "false";
    return null;
  }
  const params = new URLSearchParams();
  params.set("q", q);
  params.set("page_size", "10");
  params.set("mode", opts.mode || "keyword");
  for (const t of opts.object_types || []) {
    if (t) params.append("object_type", t);
  }
  let payload;
  try {
    payload = await apiFetch(`/search?${params.toString()}`);
  } catch (e) {
    console.warn("[Mydow] /search failed", e);
    return null;
  }
  const items = (payload && payload.data && payload.data.items) || [];
  const groups = new Map();
  items.forEach((it) => {
    const t = it.object_type || "card";
    if (!groups.has(t)) groups.set(t, []);
    groups.get(t).push(it);
  });
  const groupLabel = {
    card: "灵感卡片",
    document: "文档",
    folder: "文件夹",
    task: "任务",
    skill: "Skill",
    message: "AI 消息",
    insight: "洞察",
  };
  resultsHost.innerHTML = "";
  if (items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "result-empty";
    empty.style.cssText =
      "padding:24px;text-align:center;color:#7a8aa6;font-size:13px";
    empty.textContent = `「${q}」暂无结果`;
    resultsHost.appendChild(empty);
  } else {
    for (const [type, rows] of groups) {
      const grp = document.createElement("div");
      grp.className = "result-group";
      grp.dataset.searchGroup = type;
      const h3 = document.createElement("h3");
      h3.textContent = `${groupLabel[type] || type}（${rows.length}）`;
      grp.appendChild(h3);
      rows.forEach((it) => grp.appendChild(_renderSearchResultRow(it)));
      resultsHost.appendChild(grp);
    }
  }
  resultsHost.dataset.bridgeBound = "true";
  resultsHost.dataset.bridgeQuery = q;
  return payload;
}

function attachGlobalSearchHandlers() {
  const input = document.querySelector("[data-search-modal-input]");
  if (!input || input.dataset.bridgeHandlers === "true") return;

  input.addEventListener("input", (ev) => {
    const q = ev.target.value || "";
    if (_searchDebounceTimer) {
      window.clearTimeout(_searchDebounceTimer);
    }
    _searchDebounceTimer = window.setTimeout(() => {
      performGlobalSearch(q, _searchOptsFromFilterBar()).catch(() => {});
    }, 220);
  });

  input.addEventListener("keydown", (ev) => {
    if (ev.key !== "Enter") return;
    const first = document.querySelector(".search-modal .result-row");
    if (!first) return;
    ev.preventDefault();
    const title = first.querySelector("span")?.textContent || "(未命名)";
    const type = first.dataset.searchObjectType || "card";
    toast(`已选中：${title} (${type})`, "info");
  });

  input.dataset.bridgeHandlers = "true";
}

let _searchInlineMenuLinked = false;
function bindSearchInlineMenuRefresh() {
  if (_searchInlineMenuLinked) return;
  _searchInlineMenuLinked = true;
  document.addEventListener(
    "click",
    (event) => {
      const btn = event.target.closest(
        ".inline-popover button[data-menu-value]",
      );
      if (!btn || btn.closest(".ai-model-popover")) return;
      window.setTimeout(() => {
        const input = document.querySelector("[data-search-modal-input]");
        const q = (input && input.value && input.value.trim()) || "";
        if (!q) return;
        performGlobalSearch(q, _searchOptsFromFilterBar()).catch(() => {});
      }, 0);
    },
    true,
  );
}

function attachAiHandlers() {
  const main = document.querySelector(".ai-main");
  if (!main || main.dataset.bridgeHandlers === "true") return;

  main.querySelectorAll(".ai-composer .send-button").forEach((sendBtn) => {
    const fresh = sendBtn.cloneNode(true);
    sendBtn.replaceWith(fresh);
    fresh.addEventListener("click", () => {
      submitAiMessage(aiInputContent()).catch(() => {});
    });
  });

  main.querySelectorAll("textarea.ai-input").forEach((input) => {
    input.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && !ev.shiftKey) {
        ev.preventDefault();
        const v = (input.value || "").trim();
        const ph = (input.getAttribute("placeholder") || "").trim();
        const content = ph && v === ph ? "" : v;
        submitAiMessage(content).catch(() => {});
      }
    });
  });

  if (!_isAiV14Layout()) {
    const input = main.querySelector(".ai-composer .ai-input");
    if (input && input.tagName !== "TEXTAREA") {
      input.setAttribute("contenteditable", "true");
      input.setAttribute("role", "textbox");
      input.addEventListener("focus", () => {
        if (aiInputContent() === "") input.textContent = "";
      });
      input.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" && !ev.shiftKey) {
          ev.preventDefault();
          submitAiMessage(aiInputContent()).catch(() => {});
        }
      });
    }
  }

  const list = main.querySelector(".ai-history-list");
  if (list) {
    list.addEventListener("click", (ev) => {
      const item = ev.target.closest(".ai-history-item[data-conversation-id]");
      if (!item) return;
      const id = item.dataset.conversationId;
      if (!id || id === AI_STATE.active_conversation_id) return;
      AI_STATE.active_conversation_id = id;
      list
        .querySelectorAll(".ai-history-item.active")
        .forEach((b) => b.classList.remove("active"));
      item.classList.add("active");
      loadAndRenderConversation(id).catch(() => {});
    });
  }

  const sidebar = main.querySelector(".ai-history-sidebar");
  if (sidebar) {
    sidebar.addEventListener("click", (ev) => {
      const item = ev.target.closest(
        ".ai-history-thread[data-conversation-id]",
      );
      if (!item) return;
      const id = item.dataset.conversationId;
      if (!id || id === AI_STATE.active_conversation_id) return;
      AI_STATE.active_conversation_id = id;
      sidebar
        .querySelectorAll(".ai-history-thread.active")
        .forEach((b) => b.classList.remove("active"));
      item.classList.add("active");
      _ensureV14ChatOpen();
      loadAndRenderConversation(id).catch(() => {});
    });
  }

  main.dataset.bridgeHandlers = "true";
}

function attachSkillsHandlers() {
  const main = document.querySelector(".skills-main");
  if (!main || main.dataset.bridgeHandlers === "true") return;
  main.addEventListener("click", async (ev) => {
    const runBtn = ev.target.closest(".bridge-skill-run");
    if (!runBtn) return;
    ev.preventDefault();
    ev.stopPropagation();
    const id = runBtn.dataset.skillId;
    if (!id) {
      toast("Skill 未就绪，请稍后", "warning");
      return;
    }
    runBtn.disabled = true;
    runBtn.style.opacity = "0.6";
    const originalLabel = runBtn.textContent;
    runBtn.textContent = "运行中…";
    try {
      const r = await runSkill(id, {});
      const data = (r && r.data) || {};
      const jobId =
        data.job_id ||
        (data.job && data.job.id) ||
        (data.run && data.run.id) ||
        "";
      const status = data.status || (data.job && data.job.status) || "queued";
      toast(
        `Skill 已${status === "queued" ? "入队" : "启动"}${jobId ? `（job: ${jobId.slice(0, 8)}）` : ""}`,
        "success",
      );
    } catch (e) {
      toast(`运行失败：${e.message}`, "error");
    } finally {
      runBtn.disabled = false;
      runBtn.style.opacity = "1";
      runBtn.textContent = originalLabel || "试用";
    }
  });
  main.dataset.bridgeHandlers = "true";
}

function attachGardenBoardHandlers() {
  const main = document.querySelector(".garden-main");
  if (!main || main.dataset.bridgeHandlers === "true") return;

  main.addEventListener("click", async (ev) => {
    const node = ev.target.closest(".garden-node[data-garden-topic]");
    if (!node) return;
    const topic = node.dataset.gardenTopic;
    if (!topic) return;
    ev.preventDefault();
    ev.stopPropagation();
    node.classList.add("bridge-clicked");
    setTimeout(() => node.classList.remove("bridge-clicked"), 220);
    try {
      const r = await searchByTopic(topic);
      const items = (r && r.data && r.data.items) || [];
      if (items.length === 0) {
        toast(`「${topic}」暂无相关内容`, "info");
        return;
      }
      const titles = items.map((it) => it.title || "未命名").slice(0, 3);
      toast(
        `「${topic}」相关 ${items.length} 条：${titles.join(" / ")}`,
        "success",
      );
    } catch (e) {
      toast(`搜索 ${topic} 失败：${e.message}`, "error");
    }
  });
  main.dataset.bridgeHandlers = "true";
}

const GARDEN_VIEW_STATE = {
  zoom: 1,
  fullscreen: false,
};

let GARDEN_LAYOUT_MODE = 0;

function _ensureGardenControlStyles() {
  if (document.getElementById("mydow-garden-control-styles")) return;
  const style = document.createElement("style");
  style.id = "mydow-garden-control-styles";
  style.textContent = `
    .garden-board.bridge-fullscreen {
      position: fixed !important;
      inset: 24px !important;
      z-index: 80 !important;
      height: auto !important;
      background: rgba(255,255,255,.96) !important;
      box-shadow: 0 24px 80px rgba(35,48,76,.24) !important;
    }
    .garden-board.bridge-garden-layout-0 .garden-network-svg { opacity: 1; }
    .garden-board.bridge-garden-layout-1 .garden-network-svg {
      transform: rotate(-5deg);
      transform-origin: 50% 50%;
      transition: transform 220ms ease-out;
    }
    .garden-board.bridge-garden-layout-2 .garden-network-svg {
      transform: rotate(6deg);
      opacity: 0.92;
      transition: transform 220ms ease-out, opacity 220ms ease-out;
    }
    .garden-board .zoom-control [data-garden-zoom] {
      border: 0;
      background: transparent;
      color: inherit;
      font: inherit;
      min-width: 28px;
      height: 28px;
      border-radius: 8px;
      cursor: pointer;
    }
    .garden-board .zoom-control [data-garden-zoom]:hover,
    .garden-board .zoom-control [data-garden-zoom]:focus-visible {
      background: rgba(112,140,255,.12);
      outline: none;
    }
    .garden-map.bridge-zooming {
      transform-origin: center center;
      transition: transform 180ms ease-out;
    }
  `;
  document.head.appendChild(style);
}

function _ensureGardenFullscreenButton(controls) {
  if (!controls || controls.querySelector("[data-garden-fullscreen]")) return;
  const layoutBtn = controls.querySelector(".square-tool");
  if (!layoutBtn || layoutBtn.dataset.gardenFullscreen) return;
  const fs = document.createElement("button");
  fs.type = "button";
  fs.className = "square-tool";
  fs.dataset.gardenFullscreen = "true";
  fs.setAttribute("aria-label", "切换全屏图谱");
  fs.title = "切换全屏图谱";
  fs.setAttribute("aria-pressed", "false");
  fs.innerHTML =
    '<svg class="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3m10-5h3a2 2 0 0 0 2-2v-3"/></svg>';
  layoutBtn.insertAdjacentElement("afterend", fs);
}

function _cycleGardenLayout(board) {
  if (!board) return;
  GARDEN_LAYOUT_MODE = (GARDEN_LAYOUT_MODE + 1) % 3;
  board.classList.remove(
    "bridge-garden-layout-0",
    "bridge-garden-layout-1",
    "bridge-garden-layout-2",
  );
  board.classList.add(`bridge-garden-layout-${GARDEN_LAYOUT_MODE}`);
  toast("已切换图谱布局", "success");
}

function _setGardenZoom(value, announce = true) {
  const map = document.querySelector(".garden-map");
  const controls = document.querySelector(".garden-controls");
  if (!map || !controls) return;
  GARDEN_VIEW_STATE.zoom = Math.min(1.4, Math.max(0.7, value));
  map.classList.add("bridge-zooming");
  map.style.transform = `scale(${GARDEN_VIEW_STATE.zoom.toFixed(2)})`;
  const pct = Math.round(GARDEN_VIEW_STATE.zoom * 100);
  const reset = controls.querySelector('[data-garden-zoom="reset"]');
  if (reset) reset.textContent = `${pct}%`;
  if (announce) toast(`图谱缩放 ${pct}%`, "info");
}

function _wireGardenZoomControl() {
  const control = document.querySelector(".garden-controls .zoom-control");
  if (!control || control.dataset.bridgeBound === "true") return;

  const labels = {
    out: "缩小图谱",
    reset: "重置图谱缩放",
    in: "放大图谱",
  };

  const wired = [...control.querySelectorAll("[data-garden-zoom]")];
  if (wired.length >= 3) {
    wired.forEach((btn) => {
      const action = btn.dataset.gardenZoom;
      if (!action || !labels[action]) return;
      if (!btn.getAttribute("aria-label")) btn.setAttribute("aria-label", labels[action]);
      if (!btn.title) btn.title = labels[action];
    });
    control.dataset.bridgeBound = "true";
    return;
  }

  const spans = [...control.querySelectorAll("span")];
  const buttons = [...control.querySelectorAll("button")];

  if (buttons.length === 2 && spans.length === 1) {
    const [outBtn, inBtn] = buttons;
    const midSpan = spans[0];
    outBtn.dataset.gardenZoom = "out";
    outBtn.setAttribute("aria-label", labels.out);
    outBtn.title = labels.out;

    const resetBtn = document.createElement("button");
    resetBtn.type = "button";
    resetBtn.dataset.gardenZoom = "reset";
    resetBtn.setAttribute("aria-label", labels.reset);
    resetBtn.title = labels.reset;
    resetBtn.textContent = (midSpan.textContent || "100%").trim();
    midSpan.replaceWith(resetBtn);

    inBtn.dataset.gardenZoom = "in";
    inBtn.setAttribute("aria-label", labels.in);
    inBtn.title = labels.in;
    control.dataset.bridgeBound = "true";
    return;
  }

  if (spans.length >= 3) {
    const actions = [
      { action: "out", label: labels.out, text: "-" },
      { action: "reset", label: labels.reset, text: "100%" },
      { action: "in", label: labels.in, text: "+" },
    ];
    spans.slice(0, 3).forEach((span, index) => {
      const cfg = actions[index];
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.gardenZoom = cfg.action;
      button.setAttribute("aria-label", cfg.label);
      button.title = cfg.label;
      button.textContent = cfg.text;
      span.replaceWith(button);
    });
    control.dataset.bridgeBound = "true";
  }
}

function attachGardenControlHandlers() {
  const controls = document.querySelector(".garden-controls");
  const board = document.querySelector(".garden-board");
  if (!controls || !board || controls.dataset.bridgeHandlers === "true") return;
  _ensureGardenControlStyles();
  _ensureGardenFullscreenButton(controls);
  _wireGardenZoomControl();

  controls.setAttribute("role", "toolbar");
  controls.setAttribute("aria-label", "数字花园图谱工具栏");
  const zc = controls.querySelector(".zoom-control");
  if (zc && !zc.getAttribute("role")) {
    zc.setAttribute("role", "group");
    zc.setAttribute("aria-label", "图谱缩放");
  }

  board.classList.add("bridge-garden-layout-0");

  const layoutToggle = controls.querySelector(
    ".square-tool:not([data-garden-fullscreen])",
  );
  if (layoutToggle) {
    if (!layoutToggle.getAttribute("aria-label")) {
      layoutToggle.setAttribute("aria-label", "切换图谱布局");
    }
    if (!layoutToggle.title) layoutToggle.title = "切换图谱布局";
    layoutToggle.addEventListener(
      "click",
      (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        _cycleGardenLayout(board);
      },
      true,
    );
  }

  const fullscreenBtn = controls.querySelector("[data-garden-fullscreen]");
  if (fullscreenBtn) {
    fullscreenBtn.addEventListener(
      "click",
      (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        GARDEN_VIEW_STATE.fullscreen = !GARDEN_VIEW_STATE.fullscreen;
        board.classList.toggle("bridge-fullscreen", GARDEN_VIEW_STATE.fullscreen);
        fullscreenBtn.setAttribute(
          "aria-pressed",
          String(GARDEN_VIEW_STATE.fullscreen),
        );
        toast(
          GARDEN_VIEW_STATE.fullscreen ? "已展开全屏图谱" : "已退出全屏图谱",
          "info",
        );
      },
      true,
    );
  }

  controls.addEventListener(
    "click",
    (event) => {
      const button = event.target.closest("[data-garden-zoom]");
      if (!button || !controls.contains(button)) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      const action = button.dataset.gardenZoom;
      if (action === "out") _setGardenZoom(GARDEN_VIEW_STATE.zoom - 0.1);
      if (action === "in") _setGardenZoom(GARDEN_VIEW_STATE.zoom + 0.1);
      if (action === "reset") _setGardenZoom(1);
    },
    true,
  );

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !GARDEN_VIEW_STATE.fullscreen) return;
    GARDEN_VIEW_STATE.fullscreen = false;
    board.classList.remove("bridge-fullscreen");
    if (fullscreenBtn) fullscreenBtn.setAttribute("aria-pressed", "false");
    toast("已退出全屏图谱", "info");
  });

  _setGardenZoom(1, false);
  controls.dataset.bridgeHandlers = "true";
}

async function loadReportDetail(reportId) {
  if (!reportId) return null;
  return apiFetch(`/reports/${reportId}`);
}

function attachInsightsFullPanelHandlers() {
  const main = document.querySelector(".insights-full-main");
  if (!main || main.dataset.bridgeHandlers === "true") return;

  main.addEventListener("click", async (ev) => {
    // Dismiss core insight
    const dismissBtn = ev.target.closest(".bridge-dismiss-btn");
    if (dismissBtn) {
      ev.preventDefault();
      ev.stopPropagation();
      const card = dismissBtn.closest("[data-insight-id]");
      if (!card) return;
      const id = card.dataset.insightId;
      dismissBtn.disabled = true;
      dismissBtn.style.opacity = "0.6";
      try {
        await dismissInsight(id);
        toast("已忽略此洞察", "success");
        card.style.transition = "opacity 200ms ease, transform 200ms ease";
        card.style.opacity = "0";
        card.style.transform = "scale(0.96)";
        setTimeout(() => card.remove(), 220);
      } catch (e) {
        dismissBtn.disabled = false;
        dismissBtn.style.opacity = "1";
        toast(`忽略失败: ${e.message}`, "error");
      }
      return;
    }

    // Report row click → fetch report detail and toast a preview
    const reportRow = ev.target.closest("[data-report-id]");
    if (reportRow) {
      const id = reportRow.dataset.reportId;
      try {
        const detail = await loadReportDetail(id);
        const data = (detail && detail.data) || {};
        const summary = (data.summary || data.body || "").trim();
        const preview = summary
          ? summary.length > 90
            ? summary.slice(0, 90) + "…"
            : summary
          : "暂无摘要";
        toast(`${data.title || "报告"}：${preview}`, "info");
      } catch (e) {
        toast(`获取报告详情失败: ${e.message}`, "error");
      }
    }
  });

  // Refresh again whenever the user opens the full insights centre, so the
  // numbers feel "fresh on open" (e.g. after a capture has just landed).
  document.querySelectorAll("[data-insights-full]").forEach((btn) => {
    btn.addEventListener("click", () => {
      window.setTimeout(() => {
        refreshInsightsFullPanel().catch((err) =>
          console.warn("[Mydow] refresh on toggle failed", err),
        );
      }, 60);
    });
  });

  main.dataset.bridgeHandlers = "true";
}

// ─────────────────────────────────────────────  §15.8 knowledge base  ─────
//
// Replace the prototype's 6 hard-coded ``.library-card`` folders with real
// data from ``/api/v1/kb/folders?include_counts=true``. Bind the per-card
// star (favorite) action to ``PATCH /kb/folders/{id}`` and intercept the
// ``[data-modal="newFolder"]`` submit to ``POST /kb/folders``.
//
// We don't wipe the static DOM — instead we replace each card's textual
// content + dataset + click handlers in place so the existing CSS / hover
// states continue to work without us re-implementing them.

const FOLDER_COLOR_GRADIENTS = [
  "linear-gradient(135deg, #ffd9a8, #ffb56a)",
  "linear-gradient(135deg, #c1d5ff, #8aa9ff)",
  "linear-gradient(135deg, #b9f2c8, #6ad6a4)",
  "linear-gradient(135deg, #f3c4ec, #d394c8)",
  "linear-gradient(135deg, #ffd6d6, #f08a9b)",
  "linear-gradient(135deg, #ffe9b3, #ffc56b)",
];

function _formatFolderUpdated(iso) {
  if (!iso) return "刚刚更新";
  try {
    const d = new Date(iso);
    const ms = Date.now() - d.getTime();
    if (ms < 60_000) return "刚刚更新";
    if (ms < 3600_000) return `${Math.round(ms / 60_000)} 分钟前更新`;
    if (ms < 86_400_000) return `${Math.round(ms / 3600_000)} 小时前更新`;
    return `${Math.round(ms / 86_400_000)} 天前更新`;
  } catch {
    return "刚刚更新";
  }
}

function _hydrateFolderCard(card, folder, idx) {
  // Mark the card so subsequent loads can update in place.
  card.dataset.folderId = folder.id || "";
  card.dataset.folderFavorite = String(Boolean(folder.is_favorite));
  card.setAttribute("role", "button");
  card.setAttribute("tabindex", "0");
  card.setAttribute(
    "aria-label",
    `打开 ${folder.name || "未命名"} 文件夹`,
  );
  // Replace the static folder-name + counts.
  const heading = card.querySelector("h2");
  if (heading) heading.textContent = folder.name || "未命名文件夹";
  const meta = card.querySelector(".library-meta");
  if (meta) {
    const docs = folder.document_count != null ? folder.document_count : 0;
    const cards = folder.card_count != null ? folder.card_count : 0;
    const total = docs + cards;
    const sub = folder.subfolder_count != null
      ? folder.subfolder_count
      : null;
    meta.textContent = sub != null
      ? `${total} 条记录 · ${sub} 个子文件夹`
      : `${total} 条记录`;
  }
  // Owner + relative time.
  const owner = card.querySelector(".library-owner");
  if (owner) {
    const name = (window.MydowBridge && window.MydowBridge.lastMe) || "你";
    const initial = (typeof name === "string" && name[0]) || "M";
    owner.innerHTML =
      `<span class="creator-mark">${escapeHtml(initial)}</span> ` +
      escapeHtml(_formatFolderUpdated(folder.updated_at));
  }
  // Folder visual gradient (rotates by index for variety).
  const visual = card.querySelector(".folder-visual");
  if (visual) {
    visual.style.background = FOLDER_COLOR_GRADIENTS[idx % FOLDER_COLOR_GRADIENTS.length];
  }
  // Star action: reflect favorite state and dataset.
  const star = card.querySelector(".star-action");
  if (star) {
    star.dataset.folderId = folder.id || "";
    star.classList.toggle("active", Boolean(folder.is_favorite));
    star.setAttribute(
      "aria-label",
      folder.is_favorite ? "取消收藏" : `收藏 ${folder.name}`,
    );
  }
}

async function loadKbLibraryGrid() {
  // biz prototype renames the section from .knowledge-page to
  // .knowledge-main; tolerate either to keep the bridge resilient when
  // the prototype HTML is regenerated.
  const grid =
    document.querySelector(".knowledge-main .library-grid") ||
    document.querySelector(".knowledge-page .library-grid") ||
    document.querySelector(".library-grid");
  if (!grid) return null;
  let payload;
  try {
    payload = await apiFetch("/kb/folders?include_counts=true");
  } catch (e) {
    console.warn("[Mydow] /kb/folders failed", e);
    return null;
  }
  const items = (payload && payload.data && payload.data.items) || [];
  // Reuse the prototype's existing static cards — clone the first one
  // and rebuild grid contents so the CSS-styled markup stays intact.
  const template = grid.querySelector(".library-card");
  if (!template) return null;
  const stash = template.cloneNode(true);
  // Wipe stash dataset to ensure each render starts clean.
  stash.removeAttribute("data-open-folder");
  // Remove all current cards.
  Array.from(grid.querySelectorAll(".library-card")).forEach((node) =>
    node.remove(),
  );
  if (items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "library-empty";
    empty.style.cssText =
      "grid-column: 1 / -1; padding: 24px; text-align: center; color: rgba(108,124,153,.85); font-size: 13px;";
    empty.textContent = "还没有文件夹，先点右上方「新建」创建一个吧。";
    grid.appendChild(empty);
    return items;
  }
  items.forEach((folder, idx) => {
    const card = stash.cloneNode(true);
    _hydrateFolderCard(card, folder, idx);
    grid.appendChild(card);
  });
  window.dispatchEvent(
    new CustomEvent("mydow:kb-folders-loaded", { detail: { items } }),
  );
  return items;
}

async function toggleFolderFavorite(folderId, nextFavorite) {
  const r = await apiFetch(`/kb/folders/${folderId}`, {
    method: "PATCH",
    body: { is_favorite: Boolean(nextFavorite) },
  });
  return r;
}

async function createFolderFromModal(button) {
  const modal = button.closest('[data-modal="newFolder"]');
  if (!modal) return;
  const name = modal.querySelector('input')?.value.trim() || "";
  const description = modal.querySelector('textarea')?.value.trim() || "";
  if (!name) {
    toast("请先填入文件夹名称", "warning");
    return;
  }
  button.disabled = true;
  button.classList.add("is-loading");
  try {
    await apiFetch("/kb/folders", {
      method: "POST",
      body: { name, description, is_favorite: false },
    });
    toast(`已创建文件夹「${name}」`, "success");
    closeAllModals();
    await loadKbLibraryGrid();
  } catch (e) {
    console.error("[Mydow] create folder failed", e);
    toast(`创建失败: ${e.message}`, "error");
  } finally {
    button.disabled = false;
    button.classList.remove("is-loading");
  }
}

function bindKbStarActions() {
  // Capture-phase listener so the prototype's IIFE bubbling handler
  // ("收藏状态已更新" generic toast) fires AFTER us — and we toast the
  // final real result. We do not stop propagation, so the IIFE's static
  // toast still appears as transient feedback while our PATCH lands.
  document.addEventListener(
    "click",
    async (event) => {
      const star = event.target.closest(".library-card .star-action");
      if (!star) return;
      const card = star.closest(".library-card");
      const folderId = (card && card.dataset.folderId) || star.dataset.folderId;
      if (!folderId) return; // static prototype card — skip
      event.preventDefault();
      event.stopImmediatePropagation();
      const nowFav = card.dataset.folderFavorite === "true";
      const next = !nowFav;
      // Optimistic UI: flip immediately.
      card.dataset.folderFavorite = String(next);
      star.classList.toggle("active", next);
      try {
        await toggleFolderFavorite(folderId, next);
        toast(next ? "已加入收藏" : "已取消收藏", "success");
      } catch (e) {
        // Rollback.
        card.dataset.folderFavorite = String(nowFav);
        star.classList.toggle("active", nowFav);
        toast(`收藏失败: ${e.message}`, "error");
      }
    },
    true,
  );
}

function bindKbNewFolderSubmit() {
  // Capture-phase intercept of the [data-modal="newFolder"] primary
  // action. The prototype's data-toast="知识库文件夹已创建" ships as
  // the bubble-phase IIFE handler; we short-circuit that.
  document.addEventListener(
    "click",
    (event) => {
      const button = event.target.closest('button[data-toast="知识库文件夹已创建"]');
      if (!button) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      createFolderFromModal(button).catch((e) =>
        console.error("[Mydow] new folder", e),
      );
    },
    true,
  );
}

function bindKbCardOpenFolder() {
  // Card click → for now log + toast (folder-detail rendering belongs
  // to §15.9). We still set the data-folder-id so future bindings can
  // pick the row up from the same hook.
  document.addEventListener(
    "click",
    (event) => {
      const card = event.target.closest(".library-card[data-folder-id]");
      if (!card) return;
      const action = event.target.closest(
        ".star-action, .dots-action, button, a",
      );
      if (action) return; // let other handlers (favorite, more) take over
      const folderId = card.dataset.folderId;
      if (!folderId) return;
      const name = card.querySelector("h2")?.textContent.trim() || "文件夹";
      // §15.9 will replace this toast with a real folder-detail view.
      toast(`已选中「${name}」（详情视图待 §15.9 接入）`, "info");
      window.dispatchEvent(
        new CustomEvent("mydow:kb-folder-clicked", {
          detail: { folderId, name },
        }),
      );
    },
    true,
  );
}

// ─────────────────────────────────────────────  §15.6 card drawer  ────────
//
// The home feed's idea-cards (.idea-card[data-card-id]) currently open the
// prototype's static "itemDetail" drawer. We hijack the click to fetch
// real card data via /cards/:id and inject it into the drawer panel
// before the IIFE shows it.

async function loadCardForDrawer(cardId) {
  let card;
  try {
    card = await apiFetch(`/cards/${cardId}`);
  } catch (e) {
    console.warn("[Mydow] /cards/{id} failed", e);
    return null;
  }
  return (card && card.data) || card;
}

function _findItemDetailDrawer() {
  // The prototype defines drawerLayers via [data-drawer]; find by name.
  return document.querySelector('[data-drawer="itemDetail"]');
}

function hydrateItemDetailDrawer(drawer, payload) {
  if (!drawer || !payload) return;
  delete drawer.dataset.documentId;
  drawer.removeAttribute("data-document-id");
  const title =
    drawer.querySelector(".detail-drawer .drawer-head h2") ||
    drawer.querySelector(".drawer-head h2");
  if (title) {
    title.textContent =
      payload.title || payload.summary?.slice(0, 60) || "未命名";
  }
  const summary =
    drawer.querySelector(".drawer-summary") ||
    drawer.querySelector(".drawer-section p") ||
    drawer.querySelector("article p, .panel-text");
  if (summary && payload.summary) {
    summary.textContent = payload.summary;
  }
  // Tags. Inject a small fresh row at the top of any existing .tag-list.
  const tags = drawer.querySelector(".tag-list, .source-chip-list");
  if (tags && Array.isArray(payload.tags)) {
    tags.innerHTML = payload.tags
      .slice(0, 8)
      .map((t) => `<span class="tag">${escapeHtml(String(t))}</span>`)
      .join("");
  }
  drawer.dataset.cardId = payload.id || "";
  drawer.dataset.cardFavorite = String(Boolean(payload.is_favorite));
  // Surface raw payload for any downstream handler.
  drawer.__bridgeCard = payload;
}

function bindCardClickToDrawer() {
  document.addEventListener(
    "click",
    async (event) => {
      const card = event.target.closest(".idea-card[data-card-id]");
      if (!card) return;
      const cardId = card.dataset.cardId;
      if (!cardId) return;
      // Don't hijack inner action elements (favorite icon, bookmark).
      if (event.target.closest(".save-icon, .favorite, button, a")) return;
      const drawer = _findItemDetailDrawer();
      if (!drawer) return;
      // Fetch real card data; the IIFE will open the drawer immediately
      // after this handler returns (we don't stop propagation), so we
      // run async hydration in parallel and update the drawer in place
      // when it lands. Loading-state toast keeps the UI responsive.
      const payload = await loadCardForDrawer(cardId);
      if (payload) {
        hydrateItemDetailDrawer(drawer, payload);
      } else {
        toast("加载卡片详情失败", "error");
      }
    },
    true,
  );
}

async function favoriteCardById(cardId, makeFavorite) {
  // ``POST /cards/{id}/favorite`` accepts an explicit ``is_favorite``
  // flag (default ``true``). We always pass an explicit boolean so the
  // bridge can flip in either direction.
  return apiFetch(`/cards/${cardId}/favorite`, {
    method: "POST",
    body: { is_favorite: Boolean(makeFavorite) },
  });
}

function bindCardFavoriteAction() {
  document.addEventListener(
    "click",
    async (event) => {
      const star = event.target.closest(
        ".idea-card .save-icon[data-bookmark], .idea-card .favorite",
      );
      if (!star) return;
      const card = star.closest(".idea-card[data-card-id]");
      if (!card) return;
      const cardId = card.dataset.cardId;
      if (!cardId) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      const wasFav = card.dataset.cardFavorite === "true";
      const next = !wasFav;
      try {
        const res = await favoriteCardById(cardId, next);
        const newFav = !!(res && (res.data?.is_favorite ?? res.is_favorite));
        card.dataset.cardFavorite = String(newFav);
        star.classList.toggle("active", newFav);
        toast(newFav ? "已加入收藏" : "已取消收藏", "success");
      } catch (e) {
        toast(`收藏失败: ${e.message}`, "error");
      }
    },
    true,
  );
}

// ─────────────────────────────────────────────  §15.9 folder detail  ─────
//
// When a user clicks a .library-card[data-folder-id] (handled by §15.8
// bindKbCardOpenFolder which dispatches "mydow:kb-folder-clicked"), we
// fetch /kb/folders/{id} + /kb/documents?folder_id={id} and rewrite the
// prototype's static .folder-main panel.

function _hydrateFolderHeader(folder, docCount) {
  const main = document.querySelector(".folder-main");
  if (!main) return;
  const breadcrumb = main.querySelector(".folder-breadcrumb strong");
  if (breadcrumb) breadcrumb.textContent = folder.name || "未命名";
  const titleH1 = main.querySelector(".folder-title h1");
  if (titleH1) titleH1.textContent = folder.name || "未命名";
  const desc = main.querySelector(".folder-title > p");
  if (desc) desc.textContent = folder.description || "暂无描述。点击右上角更多按钮可编辑文件夹信息。";
  // Update the meta row spans (文档 X 篇 / 协作成员 / 更新时间).
  const metaSpans = main.querySelectorAll(".folder-meta-row > span");
  if (metaSpans[0]) {
    metaSpans[0].innerHTML =
      '<svg class="icon"><use href="#icon-file-text" /></svg> 文档 ' +
      String(docCount) +
      " 篇";
  }
  if (metaSpans[4]) {
    metaSpans[4].innerHTML =
      '<svg class="icon"><use href="#icon-clock" /></svg> 更新 ' +
      escapeHtml(_formatFolderUpdated(folder.updated_at));
  }
  main.dataset.folderId = folder.id || "";
}

function _renderDocRow(template, doc) {
  const row = template.cloneNode(true);
  row.dataset.documentId = doc.id || "";
  const titleH2 = row.querySelector(".doc-title h2");
  if (titleH2) titleH2.textContent = doc.title || "未命名文档";
  const tagsBox = row.querySelector(".doc-tags");
  if (tagsBox) {
    tagsBox.innerHTML = (doc.tags || [])
      .slice(0, 4)
      .map((t) => `<span class="tag">${escapeHtml(String(t))}</span>`)
      .join("");
  }
  const update = row.querySelector(".doc-update");
  if (update) {
    const when = _formatFolderUpdated(doc.updated_at);
    const summary = doc.summary || (doc.document_type === "manual" ? "手动文档" : "自动摘要");
    update.innerHTML =
      `<strong>更新于 ${escapeHtml(when)}</strong>` +
      `来自 ${escapeHtml(summary.slice(0, 18) + (summary.length > 18 ? "…" : ""))}`;
  }
  return row;
}

async function loadFolderDetail(folderId) {
  if (!folderId) return null;
  const main = document.querySelector(".folder-main");
  if (!main) return null;
  // Fetch folder meta + its documents.
  let folder, docs;
  try {
    [folder, docs] = await Promise.all([
      apiFetch(`/kb/folders/${folderId}`),
      apiFetch(`/kb/documents?folder_id=${folderId}&limit=50`),
    ]);
  } catch (e) {
    console.error("[Mydow] load folder detail failed", e);
    toast(`打开文件夹失败: ${e.message}`, "error");
    return null;
  }
  const folderData = (folder && folder.data) || folder || {};
  const docList = (docs && docs.data && docs.data.items) || [];
  _hydrateFolderHeader(folderData, docList.length);

  // Replace .doc-list rows in place.
  const list = main.querySelector(".doc-list");
  if (!list) return folderData;
  const template = list.querySelector(".doc-row");
  if (!template) return folderData;
  const stash = template.cloneNode(true);
  Array.from(list.querySelectorAll(".doc-row")).forEach((n) => n.remove());
  if (docList.length === 0) {
    const empty = document.createElement("div");
    empty.className = "doc-empty";
    empty.style.cssText =
      "padding: 24px; text-align: center; color: rgba(108,124,153,.85); font-size: 13px;";
    empty.textContent = "这个文件夹还没有文档，点右上角「+ 新建文档」添加。";
    list.appendChild(empty);
  } else {
    docList.forEach((doc) => list.appendChild(_renderDocRow(stash, doc)));
  }
  window.dispatchEvent(
    new CustomEvent("mydow:folder-detail-loaded", {
      detail: { folder: folderData, documents: docList },
    }),
  );
  return folderData;
}

function bindFolderClickToDetail() {
  // §15.8 already dispatches mydow:kb-folder-clicked when a card is
  // clicked; we listen and load the real detail panel.
  window.addEventListener("mydow:kb-folder-clicked", (event) => {
    const id = event.detail && event.detail.folderId;
    if (id) loadFolderDetail(id);
  });
}

// ─────────────────────────────────────────────  §15.22 drawer CRUD  ────
//
// The biz prototype's IIFE wires every `data-toast="..."` button to a
// fake simulateAction toast. That makes 5 high-intent buttons silently
// inert from the demo's perspective:
//
//   1. itemDetail drawer 「移动到知识库」 (data-toast="已移动到知识库")
//   2. confirmDelete modal 「确认删除」 (data-toast="已删除，仍可在回收站恢复")
//   3. insightDetail drawer 「已创建整理任务」 (data-toast="已创建整理任务")
//   4. itemDetail card share button 「已复制分享链接」 (data-toast="已复制分享链接")
//   5. skillDetail drawer 「已收藏 Skill」 (data-toast="已收藏 Skill")
//
// We attach a capture-phase listener at the document level to short-
// circuit the IIFE's generic [data-toast] fallback for these specific
// buttons and route them to real PRD10 endpoints instead. Other
// data-toast buttons (settings toggles, etc.) keep going through the
// IIFE's simulateAction path.

const _DRAWER_CTX = {
  cardId: null,
  documentId: null,
  folderId: null,
  insightId: null,
  insightTitle: null,
  insightSummary: null,
  skillId: null,
  skillName: null,
};

const FAVORITE_SKILLS_KEY = "mydow_biz_favorite_skills";

function _readFavoriteSkills() {
  try {
    const raw = safeLocalStorageGet(FAVORITE_SKILLS_KEY) || "[]";
    return new Set(JSON.parse(raw));
  } catch {
    return new Set();
  }
}

function _writeFavoriteSkills(set) {
  try {
    safeLocalStorageSet(FAVORITE_SKILLS_KEY, JSON.stringify([...set]));
  } catch {
    /* JSON.stringify error — silently degrade */
  }
}

// Sync the active drawer ↔ context so subsequent button clicks know
// which object they target. Triggered by §15.6 (idea-card click stores
// cardId on [data-drawer="itemDetail"]) and the new dataset-write
// callbacks below for skill / insight / node drawers.
function _syncDrawerCtxFromVisibleDrawers() {
  const drawers = document.querySelectorAll(".drawer-layer[data-drawer]");
  drawers.forEach((layer) => {
    if (layer.hidden) return;
    const kind = layer.dataset.drawer;
    if (kind === "itemDetail") {
      const aside = layer.querySelector("aside");
      _DRAWER_CTX.cardId =
        (aside && (aside.dataset.cardId || aside.dataset.itemId)) ||
        layer.dataset.cardId ||
        _DRAWER_CTX.cardId;
    }
    if (kind === "insightDetail") {
      const head = layer.querySelector(".drawer-head");
      _DRAWER_CTX.insightId =
        layer.dataset.insightId ||
        (head && head.dataset.insightId) ||
        _DRAWER_CTX.insightId;
      const titleEl = layer.querySelector(".drawer-head h2");
      const subEl = layer.querySelector(".drawer-section p");
      if (titleEl) _DRAWER_CTX.insightTitle = titleEl.textContent.trim();
      if (subEl) _DRAWER_CTX.insightSummary = subEl.textContent.trim();
    }
    if (kind === "skillDetail") {
      _DRAWER_CTX.skillId = layer.dataset.skillId || _DRAWER_CTX.skillId;
      const titleEl = layer.querySelector(".drawer-head h2");
      if (titleEl) _DRAWER_CTX.skillName = titleEl.textContent.trim();
    }
  });
}

// §15.22a ─ 「移动到知识库」（itemDetail drawer 卡片移动）
async function moveCardToKb(cardId) {
  if (!cardId) return null;
  // V1 fallback: target_folder_id = null = move out of any folder
  // (semantically "待整理收件"). P1 will add a folder-picker modal.
  try {
    const resp = await apiFetch(`/cards/${cardId}/move`, {
      method: "POST",
      body: { target_folder_id: null },
    });
    return resp;
  } catch (e) {
    toast(`移动失败：${e.message}`, "error");
    throw e;
  }
}

// §15.22b ─ confirmDelete modal「确认删除」: dispatches by current
// drawer context. card / document / folder all soft-delete via the
// PRD10 DELETE endpoints.
async function deleteCurrentSubject() {
  _syncDrawerCtxFromVisibleDrawers();
  if (_DRAWER_CTX.cardId) {
    try {
      await apiFetch(`/cards/${_DRAWER_CTX.cardId}`, { method: "DELETE" });
      window.dispatchEvent(
        new CustomEvent("mydow:card-deleted", {
          detail: { cardId: _DRAWER_CTX.cardId },
        }),
      );
      _DRAWER_CTX.cardId = null;
      return { kind: "card" };
    } catch (e) {
      toast(`删除卡片失败：${e.message}`, "error");
      throw e;
    }
  }
  if (_DRAWER_CTX.documentId) {
    try {
      await apiFetch(`/kb/documents/${_DRAWER_CTX.documentId}`, {
        method: "DELETE",
      });
      _DRAWER_CTX.documentId = null;
      return { kind: "document" };
    } catch (e) {
      toast(`删除文档失败：${e.message}`, "error");
      throw e;
    }
  }
  if (_DRAWER_CTX.folderId) {
    try {
      await apiFetch(`/kb/folders/${_DRAWER_CTX.folderId}`, {
        method: "DELETE",
        body: { strategy: "move_to_root" },
      });
      _DRAWER_CTX.folderId = null;
      return { kind: "folder" };
    } catch (e) {
      toast(`删除文件夹失败：${e.message}`, "error");
      throw e;
    }
  }
  return null;
}

// §15.22c ─ insightDetail drawer 「已创建整理任务」: POST /tasks
async function createTaskFromInsight() {
  _syncDrawerCtxFromVisibleDrawers();
  const title = _DRAWER_CTX.insightTitle
    ? `整理：${_DRAWER_CTX.insightTitle}`
    : "整理本周洞察";
  const description = _DRAWER_CTX.insightSummary || "由 AI 洞察生成的整理任务";
  try {
    const resp = await apiFetch("/tasks", {
      method: "POST",
      body: {
        title: title.slice(0, 250),
        description: description.slice(0, 2000),
        priority: "medium",
        status: "todo",
        source_type: "insight",
        source_id: _DRAWER_CTX.insightId || null,
        tags: ["AI 洞察", "整理"],
      },
    });
    return resp;
  } catch (e) {
    toast(`创建任务失败：${e.message}`, "error");
    throw e;
  }
}

// §15.22d ─ 已复制分享链接 (itemDetail drawer .soft-filter)
async function copyCardShareLink(cardId) {
  if (!cardId) return false;
  const url = `${window.location.origin}/mydow/biz/#card/${cardId}`;
  try {
    await navigator.clipboard.writeText(url);
    return true;
  } catch {
    // Fallback: inert input + execCommand for older browsers.
    const input = document.createElement("input");
    input.value = url;
    document.body.appendChild(input);
    input.select();
    try {
      document.execCommand("copy");
    } catch {
      /* ignore */
    }
    input.remove();
    return true;
  }
}

// §15.22e ─ skillDetail drawer 「已收藏 Skill」: localStorage persist
function toggleSkillFavorite(skillId) {
  if (!skillId) return false;
  const set = _readFavoriteSkills();
  const wasFav = set.has(skillId);
  if (wasFav) set.delete(skillId);
  else set.add(skillId);
  _writeFavoriteSkills(set);
  return !wasFav;
}

// When the user clicks a card / skill / insight that opens a drawer
// (data-open-drawer="..."), stamp the parent's id on both the drawer
// layer and the global context so subsequent button clicks know what
// to operate on. This is the single point that wires §15.6/§15.15/
// §15.16 row-clicks into the §15.22 button handlers without modifying
// those modules.
function bindDrawerOpenContextSync() {
  document.addEventListener(
    "click",
    (event) => {
      const opener = event.target.closest("[data-open-drawer]");
      if (!opener) return;
      const drawerName = opener.getAttribute("data-open-drawer");
      const layer = document.querySelector(
        `.drawer-layer[data-drawer="${drawerName}"]`,
      );
      if (!layer) return;
      // Find the closest object id on the opener (skill-card, insight
      // card, idea-card etc.) and forward it to the layer.
      const cardId =
        opener.dataset.cardId ||
        (opener.closest("[data-card-id]") &&
          opener.closest("[data-card-id]").dataset.cardId);
      const skillId =
        opener.dataset.skillId ||
        (opener.closest("[data-skill-id]") &&
          opener.closest("[data-skill-id]").dataset.skillId);
      const insightId =
        opener.dataset.insightId ||
        (opener.closest("[data-insight-id]") &&
          opener.closest("[data-insight-id]").dataset.insightId);
      if (cardId) {
        layer.dataset.cardId = cardId;
        _DRAWER_CTX.cardId = cardId;
      }
      if (skillId) {
        layer.dataset.skillId = skillId;
        _DRAWER_CTX.skillId = skillId;
      }
      if (insightId) {
        layer.dataset.insightId = insightId;
        _DRAWER_CTX.insightId = insightId;
      }
    },
    true,
  );
}

// ─────────────────────────────────────────────  §15.27 AI-action buttons  ─
//
// 5 `data-toast` buttons on item-detail / insightDetail drawers that the
// prototype leaves as simulateAction stubs:
//   * `AI 已开始生成摘要` / `摘要已重新生成`  → enqueue Skill run
//   * `已提取推荐标签`                       → enqueue Skill run
//   * `已生成知识卡片`                       → POST /cards
//   * `已关联数字花园`                       → V1 toast (PRD10 §18 P2)
//   * `洞察已保存到知识库`                    → POST /cards from insight
//
// All five share `_DRAWER_CTX` and run through a single capture-phase
// document listener distinct from §15.22's CRUD listener (matched by
// different `data-toast` intent strings).

let _CACHED_FIRST_SKILL_ID = null;

async function _resolveFirstSkillId() {
  if (_CACHED_FIRST_SKILL_ID) return _CACHED_FIRST_SKILL_ID;
  try {
    const resp = await apiFetch("/skills?page_size=1");
    const items = (resp && resp.data && resp.data.items) || [];
    if (items[0] && items[0].id) {
      _CACHED_FIRST_SKILL_ID = items[0].id;
      return _CACHED_FIRST_SKILL_ID;
    }
  } catch (e) {
    console.warn("[Mydow] /skills probe failed", e);
  }
  return null;
}

function _readVisibleItemDetailDrawer() {
  const layer = document.querySelector(
    '.drawer-layer[data-drawer="itemDetail"]:not([hidden])',
  );
  if (!layer) return null;
  const head = layer.querySelector(".drawer-head h2");
  const summary = layer.querySelector(".drawer-summary, .drawer-section p");
  const tags = [
    ...layer.querySelectorAll(".tag-list .tag, .source-chip-list .tag"),
  ]
    .map((el) => (el.textContent || "").trim())
    .filter(Boolean);
  return {
    cardId: layer.dataset.cardId || _DRAWER_CTX.cardId,
    title: (head && head.textContent.trim()) || "",
    summary: (summary && summary.textContent.trim()) || "",
    tags,
  };
}

function _readVisibleDocEditorSubject() {
  const shell = document.querySelector(".page");
  const main = document.querySelector(".doc-editor-main");
  if (!shell || !main || !shell.classList.contains("doc-open")) return null;
  const titleInput = main.querySelector(".doc-title-input");
  const body = main.querySelector(".doc-body");
  const tags = [
    ...document.querySelectorAll(
      ".doc-editor-drawer .source-chip-list .tag",
    ),
  ]
    .map((el) => (el.textContent || "").trim())
    .filter(Boolean);
  const title = (titleInput && titleInput.value.trim()) || "未命名文档";
  const content = (body && body.innerText.trim()) || title;
  return {
    cardId: null,
    documentId: main.dataset.documentId || _docEditorState.documentId || null,
    sourceObjectType: "document",
    sourceObjectId: main.dataset.documentId || _docEditorState.documentId || null,
    title,
    summary: content.slice(0, 1000),
    content,
    tags,
  };
}

function _readCurrentAiActionSubject() {
  const card = _readVisibleItemDetailDrawer();
  if (card && (card.cardId || card.title)) {
    return {
      ...card,
      sourceObjectType: "card",
      sourceObjectId: card.cardId || null,
      content: card.summary || card.title,
    };
  }
  return _readVisibleDocEditorSubject();
}

function _readVisibleInsightDetailDrawer() {
  const layer = document.querySelector(
    '.drawer-layer[data-drawer="insightDetail"]:not([hidden])',
  );
  if (!layer) return null;
  const head = layer.querySelector(".drawer-head h2");
  const subtitle = layer.querySelector(".drawer-head p");
  const body = layer.querySelector(".drawer-section p");
  return {
    insightId: layer.dataset.insightId || _DRAWER_CTX.insightId,
    title: (head && head.textContent.trim()) || "",
    subtitle: (subtitle && subtitle.textContent.trim()) || "",
    body: (body && body.textContent.trim()) || "",
  };
}

async function runSkillForCard(intent, instruction) {
  const subject = _readCurrentAiActionSubject();
  if (!subject || !subject.title) {
    toast("当前页面未识别到可处理内容", "warning");
    return null;
  }
  const skillId = await _resolveFirstSkillId();
  if (!skillId) {
    toast("没有可用的 Skill", "warning");
    return null;
  }
  try {
    const resp = await apiFetch(`/skills/${skillId}/run`, {
      method: "POST",
      body: {
        input: {
          instruction,
          intent,
          source_object_type: subject.sourceObjectType || "card",
          source_object_id: subject.sourceObjectId || subject.cardId || null,
          source_title: subject.title,
        },
        save_output: true,
      },
    });
    return resp;
  } catch (e) {
    toast(`${intent} 失败：${e.message}`, "error");
    throw e;
  }
}

async function generateCardFromCurrentDrawer() {
  const subject = _readCurrentAiActionSubject();
  if (!subject || !subject.title) {
    toast("当前页面未识别到可生成卡片的内容", "warning");
    return null;
  }
  const summary = subject.summary || subject.content || subject.title;
  try {
    const resp = await apiFetch("/cards", {
      method: "POST",
      body: {
        title: `知识卡片 · ${subject.title}`.slice(0, 200),
        summary: summary.slice(0, 1000),
        content: (subject.content || summary || subject.title).slice(0, 10000),
        content_type: "note",
        tags: [...(subject.tags || []), "AI 生成"].slice(0, 10),
      },
    });
    return resp;
  } catch (e) {
    toast(`生成知识卡片失败：${e.message}`, "error");
    throw e;
  }
}

async function saveInsightToKb() {
  const drawer = _readVisibleInsightDetailDrawer();
  if (!drawer || !drawer.title) {
    toast("当前抽屉未识别到洞察", "warning");
    return null;
  }
  const summary = drawer.body || drawer.subtitle || drawer.title;
  try {
    const resp = await apiFetch("/cards", {
      method: "POST",
      body: {
        title: `洞察 · ${drawer.title}`.slice(0, 250),
        summary: summary.slice(0, 1000),
        content: summary,
        content_type: "note",
        tags: ["AI 洞察"],
      },
    });
    return resp;
  } catch (e) {
    toast(`保存洞察失败：${e.message}`, "error");
    throw e;
  }
}

function bindDrawerAiActionButtons() {
  document.addEventListener(
    "click",
    async (event) => {
      const button = event.target.closest("button[data-toast]");
      if (!button) return;
      const intent = button.getAttribute("data-toast");
      _syncDrawerCtxFromVisibleDrawers();

      const skillIntents = {
        "AI 已开始生成摘要": "为这张卡生成 AI 摘要",
        "摘要已重新生成": "重新生成 AI 摘要",
        "已提取推荐标签": "为这张卡提取推荐标签",
      };

      if (intent in skillIntents) {
        event.preventDefault();
        event.stopImmediatePropagation();
        const original = button.textContent;
        button.disabled = true;
        button.textContent = "排队中…";
        try {
          const resp = await runSkillForCard(intent, skillIntents[intent]);
          if (resp) {
            const jobId =
              (resp.data && resp.data.job_id) ||
              (resp.data && resp.data.skill_run_id) ||
              "";
            toast(
              `${intent.replace(/^已|^AI 已/, "")} 已入队${jobId ? `（${jobId.slice(0, 8)}…）` : ""}`,
              "success",
            );
          }
        } finally {
          button.disabled = false;
          button.textContent = original;
        }
        return;
      }

      if (intent === "已生成知识卡片") {
        event.preventDefault();
        event.stopImmediatePropagation();
        const original = button.textContent;
        button.disabled = true;
        button.textContent = "生成中…";
        try {
          const resp = await generateCardFromCurrentDrawer();
          if (resp) {
            const cardId =
              (resp.data && (resp.data.id || resp.data.card_id)) || "";
            toast(
              cardId
                ? `已生成知识卡片（${cardId.slice(0, 8)}…）`
                : "已生成知识卡片",
              "success",
            );
            loadFeedIntoRecentView().catch(() => {});
            refreshHomeContentDistribution().catch(() => {});
            refreshHomeRecentList().catch(() => {});
          }
        } finally {
          button.disabled = false;
          button.textContent = original;
        }
        return;
      }

      if (intent === "已关联数字花园") {
        event.preventDefault();
        event.stopImmediatePropagation();
        const subject = _readCurrentAiActionSubject();
        toast(
          subject && subject.title
            ? `已请求关联到数字花园：「${subject.title}」（V1 异步入队，P2 上线后真合入边）`
            : "已请求关联到数字花园（V1 异步入队）",
          "info",
        );
        window.dispatchEvent(
          new CustomEvent("mydow:garden-link-requested", {
            detail: subject || {},
          }),
        );
        refreshGardenBoard().catch(() => {});
        return;
      }

      if (intent === "洞察已保存到知识库") {
        event.preventDefault();
        event.stopImmediatePropagation();
        const original = button.textContent;
        button.disabled = true;
        button.textContent = "保存中…";
        try {
          const resp = await saveInsightToKb();
          if (resp) {
            const cardId =
              (resp.data && (resp.data.id || resp.data.card_id)) || "";
            toast(
              cardId
                ? `洞察已保存到知识库（${cardId.slice(0, 8)}…）`
                : "洞察已保存到知识库",
              "success",
            );
            loadFeedIntoRecentView().catch(() => {});
            refreshHomeRecentList().catch(() => {});
          }
        } finally {
          button.disabled = false;
          button.textContent = original;
        }
        return;
      }
    },
    true,
  );
}

// Single capture-phase document listener that intercepts the 5 §15.22
// buttons. Other [data-toast] buttons (settings toggles, etc.) keep
// flowing to the prototype IIFE's simulateAction.
function bindDrawerCrudButtons() {
  document.addEventListener(
    "click",
    async (event) => {
      const button = event.target.closest("button[data-toast]");
      if (!button) return;
      const intent = button.getAttribute("data-toast");
      // Sync drawer state on every click so we know what's open.
      _syncDrawerCtxFromVisibleDrawers();

      if (intent === "已移动到知识库") {
        event.preventDefault();
        event.stopImmediatePropagation();
        if (!_DRAWER_CTX.cardId) {
          toast("当前抽屉未识别到卡片", "warning");
          return;
        }
        const original = button.textContent;
        button.disabled = true;
        button.textContent = "移动中…";
        try {
          await moveCardToKb(_DRAWER_CTX.cardId);
          toast("已移动到 待整理收件", "success");
          window.dispatchEvent(
            new CustomEvent("mydow:card-moved", {
              detail: { cardId: _DRAWER_CTX.cardId },
            }),
          );
        } finally {
          button.disabled = false;
          button.textContent = original;
        }
        return;
      }

      if (intent === "已删除，仍可在回收站恢复") {
        // §15.22 settings-page wiring claims this same modal for logout
        // / clear-cache flows. Yield to ``bindConfirmDeleteSubmit`` when
        // the most recent ``[data-open-modal="confirmDelete"]`` opener
        // was the security-tab "退出登录" / "清除本地缓存" button (or the
        // account-menu logout item). That handler is registered later in
        // boot and would otherwise be starved by ``stopImmediatePropagation``.
        if (
          _CONFIRM_DELETE_CTX.kind === "logout" ||
          _CONFIRM_DELETE_CTX.kind === "clear_cache"
        ) {
          return; // let bindConfirmDeleteSubmit handle this click.
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        const original = button.textContent;
        button.disabled = true;
        button.textContent = "删除中…";
        try {
          const result = await deleteCurrentSubject();
          if (result) {
            toast(
              result.kind === "card"
                ? "已删除卡片，可在回收站恢复"
                : result.kind === "document"
                  ? "已删除文档"
                  : "已删除文件夹",
              "success",
            );
            // Refresh list views so the deleted row disappears.
            if (result.kind === "card" || result.kind === "document") {
              loadFeedIntoRecentView().catch(() => {});
              loadKbLibraryGrid().catch(() => {});
            }
            // Close any open modal/drawer layers.
            closeAllModals();
            document
              .querySelectorAll(".drawer-layer[data-drawer]:not([hidden])")
              .forEach((layer) => {
                layer.hidden = true;
              });
          } else {
            toast("当前没有可删除的对象", "warning");
          }
        } finally {
          button.disabled = false;
          button.textContent = original;
        }
        return;
      }

      if (intent === "已创建整理任务") {
        event.preventDefault();
        event.stopImmediatePropagation();
        const original = button.textContent;
        button.disabled = true;
        button.textContent = "创建中…";
        try {
          const resp = await createTaskFromInsight();
          const taskId =
            (resp && resp.data && resp.data.id) || (resp && resp.id) || "";
          toast(
            taskId
              ? `已创建整理任务（${taskId.slice(0, 8)}）`
              : "已创建整理任务",
            "success",
          );
          refreshTodayInsights().catch(() => {});
        } finally {
          button.disabled = false;
          button.textContent = original;
        }
        return;
      }

      if (intent === "已复制分享链接") {
        event.preventDefault();
        event.stopImmediatePropagation();
        if (!_DRAWER_CTX.cardId) {
          toast("当前抽屉未识别到卡片", "warning");
          return;
        }
        const ok = await copyCardShareLink(_DRAWER_CTX.cardId);
        toast(ok ? "已复制分享链接到剪贴板" : "复制失败", ok ? "success" : "error");
        return;
      }

      if (intent === "已收藏 Skill") {
        event.preventDefault();
        event.stopImmediatePropagation();
        if (!_DRAWER_CTX.skillId) {
          toast("当前抽屉未识别到 Skill", "warning");
          return;
        }
        const isFav = toggleSkillFavorite(_DRAWER_CTX.skillId);
        const skillLabel = _DRAWER_CTX.skillName || "Skill";
        toast(
          isFav ? `已收藏 ${skillLabel}` : `已取消收藏 ${skillLabel}`,
          "success",
        );
        // Reflect state in the button label.
        button.textContent = isFav ? "已收藏" : "收藏";
        return;
      }
    },
    true, // capture phase — intercept BEFORE the IIFE listener
  );
}

// ─────────────────────────────────────────────  §15.17 notifications  ────
//
// Replace the static .notice-list rows with /notifications data; bind
// each row's [click] to mark-read; bind [全部已读] (if present) and
// [data-modal=notificationSettings].

const NOTIFICATION_TYPE_TAGS = {
  ai_output_saved: "AI 任务",
  ai_chat: "AI 任务",
  job_completed: "AI 任务",
  skill_run_completed: "AI 任务",
  job_failed: "系统提醒",
  upload_failed: "系统提醒",
  garden_connection: "数字花园",
  kb_update: "知识库",
  daily_insight: "AI 任务",
  insight_generated: "AI 任务",
  document_ready: "系统提醒",
  system: "系统提醒",
};

/** Maps row id → latest /notifications item (for capture-phase action routing). */
const _NOTIFICATION_ROW_CACHE = new Map();

function _noticeFilterBucket(ntype) {
  const tag =
    NOTIFICATION_TYPE_TAGS[String(ntype || "").trim()] || "系统提醒";
  if (tag === "AI 任务") return "ai";
  if (tag === "数字花园" || tag === "知识库") return "collab";
  return "system";
}

function _noticeRowDatasetType(notif) {
  const parts = [_noticeFilterBucket(notif.type)];
  if (!notif.is_read) parts.push("unread");
  return parts.join(" ");
}

function _deriveNoticeActionKey(notif) {
  const ot = String(notif.object_type || "").toLowerCase();
  const ty = String(notif.type || "");
  if (ot === "insight" || ty === "insight_generated" || ty === "daily_insight") {
    return "report";
  }
  if (ot === "folder") return "folder";
  if (
    ot === "document" ||
    ty === "document_ready" ||
    ty === "ai_output_saved"
  ) {
    return "detail";
  }
  if (
    ot === "garden_node" ||
    ot === "garden" ||
    ty === "garden_connection"
  ) {
    return "link";
  }
  if (ty === "job_completed" || ty === "skill_run_completed") {
    return "result";
  }
  return "detail";
}

function _applyNoticeFilterClient(filter = "all") {
  const tabs = [...document.querySelectorAll("[data-notice-filter]")];
  tabs.forEach((tab) => {
    const isActive = tab.dataset.noticeFilter === filter;
    tab.classList.toggle("active", isActive);
    tab.setAttribute("aria-pressed", String(isActive));
  });
  let visibleCount = 0;
  document.querySelectorAll(".notice-row[data-notice-type]").forEach((row) => {
    const types = (row.dataset.noticeType || "").split(/\s+/).filter(Boolean);
    const isVisible = filter === "all" || types.includes(filter);
    row.hidden = !isVisible;
    if (isVisible) visibleCount += 1;
  });
  const emptyNote = document.querySelector(".notification-main .page-empty-note");
  if (emptyNote) {
    emptyNote.textContent = visibleCount
      ? "没有更多通知了"
      : "当前筛选没有通知";
  }
}

function _reapplyNoticeFilterAfterLoad() {
  const active = document.querySelector("[data-notice-filter].active");
  const f = (active && active.dataset.noticeFilter) || "all";
  _applyNoticeFilterClient(f);
}

function _updateNoticeTabCounts(items) {
  const buckets = {
    all: items.length,
    ai: 0,
    system: 0,
    collab: 0,
    unread: 0,
  };
  for (const n of items) {
    const b = _noticeFilterBucket(n.type);
    if (b === "ai") buckets.ai += 1;
    else if (b === "collab") buckets.collab += 1;
    else buckets.system += 1;
    if (!n.is_read) buckets.unread += 1;
  }
  for (const k of ["all", "ai", "system", "collab", "unread"]) {
    const tab = document.querySelector(`[data-notice-filter="${k}"] span`);
    if (tab) tab.textContent = String(buckets[k] ?? 0);
  }
}

function _formatNotifTime(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    const ms = Date.now() - d.getTime();
    if (ms < 60_000) return "刚刚";
    if (ms < 3600_000) return `${Math.round(ms / 60_000)} 分钟前`;
    if (ms < 86_400_000) return `${Math.round(ms / 3600_000)} 小时前`;
    return d.toLocaleString("zh-CN", { hour12: false });
  } catch {
    return "";
  }
}

function _hydrateNoticeRow(row, notif) {
  row.dataset.notificationId = notif.id || "";
  row.dataset.notificationRead = String(Boolean(notif.is_read));
  row.dataset.noticeType = _noticeRowDatasetType(notif);
  // .notice-dot — solid for unread, muted for read.
  const dot = row.querySelector(".notice-dot");
  if (dot) {
    dot.classList.toggle("muted", Boolean(notif.is_read));
  }
  const heading = row.querySelector(".notice-body h2");
  if (heading) {
    const tag = NOTIFICATION_TYPE_TAGS[notif.type] || "系统提醒";
    const title = notif.title || "新通知";
    heading.innerHTML = `${escapeHtml(title)} <span class="tag">${escapeHtml(tag)}</span>`;
  }
  const body = row.querySelector(".notice-body p");
  if (body) {
    const text = (notif.content || notif.body || notif.message || "").trim();
    body.textContent = text;
  }
  const time = row.querySelector(".notice-time");
  if (time) time.textContent = _formatNotifTime(notif.created_at);
  const action = row.querySelector(".notice-action");
  if (action) {
    action.dataset.notificationId = notif.id || "";
    action.dataset.noticeAction = _deriveNoticeActionKey(notif);
    action.textContent = notif.action_label || "查看详情";
  }
}

async function loadNotifications() {
  let payload;
  try {
    payload = await apiFetch("/notifications?page_size=100");
  } catch (e) {
    console.warn("[Mydow] /notifications failed", e);
    return null;
  }
  const data = (payload && payload.data) || payload || {};
  const items = data.items || [];
  const list = document.querySelector(".notice-list");
  if (!list) return items;
  _NOTIFICATION_ROW_CACHE.clear();
  list.querySelectorAll(".notice-empty").forEach((n) => n.remove());
  const template = list.querySelector(".notice-row");
  if (!template) return items;
  const stash = template.cloneNode(true);
  Array.from(list.querySelectorAll(".notice-row")).forEach((n) => n.remove());
  if (items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "notice-empty";
    empty.style.cssText =
      "padding: 24px; text-align: center; color: rgba(108,124,153,.85); font-size: 13px;";
    empty.textContent = "暂无通知";
    list.appendChild(empty);
    _updateNoticeTabCounts([]);
    _reapplyNoticeFilterAfterLoad();
    return items;
  }
  for (const notif of items) {
    if (notif && notif.id != null) {
      _NOTIFICATION_ROW_CACHE.set(String(notif.id), notif);
    }
  }
  items.forEach((notif) => {
    const row = stash.cloneNode(true);
    _hydrateNoticeRow(row, notif);
    list.appendChild(row);
  });
  _updateNoticeTabCounts(items);
  _reapplyNoticeFilterAfterLoad();
  window.dispatchEvent(
    new CustomEvent("mydow:notifications-loaded", { detail: { items } }),
  );
  return items;
}

async function markNotificationRead(notifId) {
  return apiFetch(`/notifications/${notifId}/read`, { method: "POST" });
}

async function markAllNotificationsRead() {
  return apiFetch("/notifications/read-all", { method: "POST" });
}

function _bizEnterFolderPageLayout(folderTitle) {
  const pageShell = document.querySelector(".page");
  if (!pageShell) return;
  const strip = [
    "doc-open",
    "folder-open",
    "knowledge-open",
    "ai-open",
    "garden-open",
    "skills-open",
    "notifications-open",
    "profile-open",
    "insights-full-open",
  ];
  strip.forEach((c) => pageShell.classList.remove(c));
  pageShell.classList.add("folder-open");
  document
    .querySelectorAll(
      ".folder-breadcrumb strong, .folder-title h1, .folder-side-hero h2",
    )
    .forEach((el) => {
      el.textContent = folderTitle || "文件夹";
    });
  const desc = document.querySelector(".folder-title p");
  if (desc) {
    desc.textContent = `${folderTitle || "文件夹"}相关的文档、记录与知识连接`;
  }
}

async function _openInsightDetailForNotification(insightId) {
  let payload;
  try {
    payload = await apiFetch("/insights?page_size=100&range=all");
  } catch (e) {
    toast("加载洞察失败", "error");
    return;
  }
  const items = (payload && payload.data && payload.data.items) || [];
  const ins = items.find((x) => String(x.id) === String(insightId));
  const drawer = document.querySelector('[data-drawer="insightDetail"]');
  if (!drawer) return;
  if (!ins) {
    document.querySelector("[data-insights-full]")?.click();
    toast("未找到洞察详情（可能已归档）", "warning");
    return;
  }
  drawer.dataset.insightId = ins.id;
  _DRAWER_CTX.insightId = ins.id;
  _DRAWER_CTX.insightTitle = ins.title;
  _DRAWER_CTX.insightSummary = ins.summary;
  const h2 = drawer.querySelector(".drawer-head h2");
  if (h2) h2.textContent = ins.title || "洞察";
  const sub = drawer.querySelector(".drawer-head > div > p");
  if (sub) {
    sub.textContent = `${INSIGHT_TAG_LABELS[ins.insight_type] || "洞察"} · PRD10`;
  }
  const sections = drawer.querySelectorAll(".drawer-section");
  const coreP = sections[0] && sections[0].querySelector("p");
  if (coreP) coreP.textContent = ins.summary || ins.body || "";
  document.querySelectorAll(".drawer-layer").forEach((l) => {
    l.hidden = true;
  });
  drawer.hidden = false;
  toast("已打开洞察详情", "success");
}

async function _routeNotificationAction(notif, actionHint) {
  const oid = notif.object_id;
  const ot = String(notif.object_type || "").toLowerCase();
  const hint = actionHint || _deriveNoticeActionKey(notif);

  if (ot === "document" && oid) {
    document.querySelector('[data-nav-target="knowledge"]')?.click();
    await loadDocumentForDrawer(oid);
    toast("已打开文档详情", "success");
    return;
  }
  if (ot === "folder" && oid) {
    document.querySelector('[data-nav-target="knowledge"]')?.click();
    let name = "文件夹";
    try {
      const r = await apiFetch(`/kb/folders/${oid}`);
      const fd = (r && r.data) || r;
      name = fd.name || name;
    } catch {
      /* keep default */
    }
    _bizEnterFolderPageLayout(name);
    await loadFolderDetail(oid);
    toast(`已打开文件夹：${name}`, "success");
    return;
  }
  if (ot === "insight" && oid) {
    await _openInsightDetailForNotification(oid);
    return;
  }
  if ((ot === "conversation" || ot === "ai_conversation") && oid) {
    document.querySelector('[data-nav-target="ai"]')?.click();
    AI_STATE.active_conversation_id = oid;
    await loadAndRenderConversation(oid);
    toast("已打开关联对话", "success");
    return;
  }
  if (ot === "card" && oid) {
    document.querySelector('[data-nav-target="home"]')?.click();
    const drawer = _findItemDetailDrawer();
    const payload = await loadCardForDrawer(oid);
    if (drawer && payload) {
      hydrateItemDetailDrawer(drawer, payload);
      _openItemDetailDrawer();
      toast("已打开灵感卡片", "success");
    }
    return;
  }
  if (ot === "skill" && oid) {
    document.querySelector('[data-nav-target="skills"]')?.click();
    toast("已打开 Skills 广场，请从列表选择对应 Skill", "info");
    return;
  }

  if (hint === "link" || ot === "garden_node" || ot === "garden") {
    document.querySelector('[data-nav-target="garden"]')?.click();
    toast("已在数字花园，可在画布上查看相关话题节点", "success");
    return;
  }
  if (hint === "report") {
    document.querySelector("[data-insights-full]")?.click();
    if (oid) await _openInsightDetailForNotification(oid);
    else toast("已打开洞察中心", "info");
    return;
  }
  if (hint === "result") {
    document.querySelector('[data-nav-target="ai"]')?.click();
    toast("已打开 AI 工作台", "info");
    return;
  }
  if (hint === "folder" && oid) {
    document.querySelector('[data-nav-target="knowledge"]')?.click();
    let name = "文件夹";
    try {
      const r = await apiFetch(`/kb/folders/${oid}`);
      const fd = (r && r.data) || r;
      name = fd.name || name;
    } catch {
      /* keep */
    }
    _bizEnterFolderPageLayout(name);
    await loadFolderDetail(oid);
    return;
  }
  if (hint === "detail" && oid) {
    document.querySelector('[data-nav-target="knowledge"]')?.click();
    await loadDocumentForDrawer(oid);
    return;
  }
  toast("该通知暂无可用跳转目标", "warning");
}

let _noticeQuickMarkReadBound = false;
function bindNoticeQuickMarkRead() {
  if (_noticeQuickMarkReadBound) return;
  _noticeQuickMarkReadBound = true;
  document.addEventListener(
    "click",
    async (event) => {
      const quick = event.target.closest("[data-notice-quick]");
      if (!quick || quick.dataset.noticeQuick !== "markRead") return;
      event.preventDefault();
      event.stopImmediatePropagation();
      try {
        await markAllNotificationsRead();
        toast("已将全部通知标为已读", "success");
        await loadNotifications();
        refreshUnreadBadge();
      } catch (e) {
        toast(`操作失败: ${e.message}`, "error");
      }
    },
    true,
  );
}

let _noticeActionBridgeBound = false;
function bindNoticeActionBridge() {
  if (_noticeActionBridgeBound) return;
  _noticeActionBridgeBound = true;
  document.addEventListener(
    "click",
    async (event) => {
      const btn = event.target.closest(
        ".notice-list .notice-action[data-notice-action]",
      );
      if (!btn) return;
      const row = btn.closest(".notice-row[data-notification-id]");
      if (!row) return;
      const id = row.dataset.notificationId;
      const notif = _NOTIFICATION_ROW_CACHE.get(String(id));
      if (!notif) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      try {
        await _routeNotificationAction(notif, btn.dataset.noticeAction);
      } catch (e) {
        console.error("[Mydow] notice action", e);
        toast(`无法打开目标: ${e.message}`, "error");
      }
    },
    true,
  );
}

function bindNotificationRowMarkRead() {
  // Capture-phase: clicking a .notice-row (or its .notice-action button)
  // should mark it read on the server; let the IIFE handle visual drawer
  // logic if any.
  document.addEventListener(
    "click",
    async (event) => {
      const row = event.target.closest(".notice-row[data-notification-id]");
      if (!row) return;
      // We don't stop propagation so the prototype's "已读" UI can show
      // first; we just background-mark on the server.
      const notifId = row.dataset.notificationId;
      const wasRead = row.dataset.notificationRead === "true";
      if (!notifId || wasRead) return;
      try {
        await markNotificationRead(notifId);
        row.dataset.notificationRead = "true";
        const dot = row.querySelector(".notice-dot");
        if (dot) dot.classList.add("muted");
        // Refresh badge count after a small delay so visual transition is
        // not interrupted.
        refreshUnreadBadge();
      } catch (e) {
        console.error("[Mydow] mark read failed", e);
      }
    },
    true,
  );
}

function bindNotificationMarkAll() {
  // The prototype has a small "全部已读" hint button (we look for it by
  // text + section context). Add a small click delegation: any button in
  // .notification-main whose text starts with "全部已读" is rerouted.
  document.addEventListener(
    "click",
    async (event) => {
      const btn = event.target.closest(".notification-main button, .notification-drawer button");
      if (!btn) return;
      const txt = (btn.textContent || "").trim();
      if (!/全部已读|标为已读全部|清空通知/.test(txt)) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      try {
        await markAllNotificationsRead();
        toast("已将全部通知标为已读", "success");
        await loadNotifications();
        refreshUnreadBadge();
      } catch (e) {
        toast(`操作失败: ${e.message}`, "error");
      }
    },
    true,
  );
}

// ─────────────────────────────────────────────  §15.10 doc detail/edit  ──
//
// Click on a .doc-row[data-document-id] (rendered by §15.9
// loadFolderDetail) → fetch /kb/documents/{id} → write into the
// .doc-editor-main section (title input, contenteditable body, footer
// word count + updated time). Edits debounce-PATCH back to the API.

let _docEditorState = {
  documentId: null,
  pending: null,
};

function _hydrateDocEditor(doc) {
  const main = document.querySelector(".doc-editor-main");
  if (!main || !doc) return;
  main.dataset.documentId = doc.id || "";
  const titleInput = main.querySelector(".doc-title-input");
  if (titleInput) titleInput.value = doc.title || "未命名文档";
  const body = main.querySelector(".doc-body");
  if (body) {
    // Render the document content as plain paragraphs. We keep the
    // existing AI-callout block from the prototype only when the
    // backend has no real content (so empty docs still look alive).
    if (doc.content && doc.content.trim()) {
      // Use white-space:pre-line so newlines preserve. Wrap in <p>
      // segments split by double-newline.
      const segments = doc.content
        .split(/\n{2,}/)
        .map((s) => `<p>${escapeHtml(s).replace(/\n/g, "<br>")}</p>`)
        .join("");
      body.innerHTML = segments;
    }
  }
  const footer = main.querySelector(".doc-footer");
  if (footer) {
    const spans = footer.querySelectorAll("span");
    if (spans[0]) spans[0].textContent = `${doc.word_count || 0} 字`;
    if (spans[1])
      spans[1].textContent = `最后更新 ${_formatFolderUpdated(doc.updated_at)}`;
  }
  // Update the back link's target text to reflect the parent folder
  // (best-effort — we keep the prototype's "返回产品设计" copy when we
  // don't know the folder name).
  const back = main.querySelector(".back-link");
  const folderMain = document.querySelector(".folder-main");
  const folderName = folderMain?.querySelector(".folder-title h1")?.textContent.trim();
  if (back && folderName) {
    back.innerHTML =
      '<svg class="icon" style="width: 16px; height: 16px"><use href="#icon-chevron-right" /></svg>' +
      `返回${escapeHtml(folderName)}`;
  }
  _docEditorState.documentId = doc.id || null;
  _docEditorState.pending = null;
}

async function loadDocumentForEditor(documentId) {
  if (!documentId) return null;
  let doc;
  try {
    const r = await apiFetch(`/kb/documents/${documentId}?include_content=true`);
    doc = (r && r.data) || r;
  } catch (e) {
    console.error("[Mydow] /kb/documents/{id} failed", e);
    toast(`加载文档失败: ${e.message}`, "error");
    return null;
  }
  _hydrateDocEditor(doc);
  return doc;
}

async function patchCurrentDocument(updates) {
  const id = _docEditorState.documentId;
  if (!id) return null;
  try {
    const r = await apiFetch(`/kb/documents/${id}`, {
      method: "PATCH",
      body: updates,
    });
    return r;
  } catch (e) {
    console.error("[Mydow] PATCH /kb/documents/{id} failed", e);
    toast(`保存失败: ${e.message}`, "error");
    return null;
  }
}

function _scheduleDocPatch(updates, label) {
  // Debounced auto-save. We collect updates in _docEditorState.pending
  // and fire a single PATCH 800ms after the last edit.
  _docEditorState.pending = { ...(_docEditorState.pending || {}), ...updates };
  if (_docEditorState._timer) clearTimeout(_docEditorState._timer);
  _docEditorState._timer = setTimeout(async () => {
    const payload = _docEditorState.pending;
    _docEditorState.pending = null;
    if (!payload) return;
    const status = document.querySelector(".doc-editor-main .doc-status");
    if (status) status.innerHTML =
      '<svg class="icon" style="width: 15px; height: 15px"><use href="#icon-clock" /></svg>正在保存…';
    const r = await patchCurrentDocument(payload);
    if (r) {
      if (status) status.innerHTML =
        '<svg class="icon" style="width: 15px; height: 15px; color: #20b887"><use href="#icon-check-square" /></svg>已自动保存';
      // Update footer word count if backend returned new value.
      const data = (r && r.data) || r;
      const footer = document.querySelector(".doc-editor-main .doc-footer");
      if (footer && data.word_count != null) {
        const spans = footer.querySelectorAll("span");
        if (spans[0]) spans[0].textContent = `${data.word_count} 字`;
        if (spans[1])
          spans[1].textContent = `最后更新 ${_formatFolderUpdated(data.updated_at)}`;
      }
    }
  }, 800);
}

function bindDocRowClick() {
  // §15.9 stamps row.dataset.documentId. Capture-phase intercept so the
  // prototype's IIFE setPageMode("doc") still runs (it shows the editor)
  // but our hydrate populates real data first.
  document.addEventListener(
    "click",
    async (event) => {
      const row = event.target.closest(".doc-row[data-document-id]");
      if (!row) return;
      const docId = row.dataset.documentId;
      if (!docId) return;
      // Don't hijack inner action buttons.
      if (event.target.closest(".record-actions, button, a")) return;
      // Async hydrate; let the IIFE bubble-phase open the editor view.
      loadDocumentForEditor(docId);
    },
    true,
  );
}

function bindDocEditorAutoSave() {
  // Title input → debounce PATCH {title}.
  const main = document.querySelector(".doc-editor-main");
  if (!main) return;
  const title = main.querySelector(".doc-title-input");
  if (title) {
    title.addEventListener("input", (e) => {
      _scheduleDocPatch({ title: e.target.value }, "title");
    });
  }
  const body = main.querySelector(".doc-body");
  if (body) {
    body.addEventListener("input", () => {
      // Strip HTML to plain text — the API stores plain markdown-ish.
      const text = body.innerText || "";
      _scheduleDocPatch({ content: text }, "content");
    });
  }
  // Delete (in [data-modal="confirmDelete"]) is wired via the prototype
  // IIFE; we don't override here — once §15.10 P1 lands we'll add a
  // capture-phase wrap.
}

// ─────────────────────────────────────────────  §15.6.1 doc → drawer  ────
//
// PRD10 §10.7 / §20 — clicking a `.doc-row[data-document-id]` is currently
// claimed by §15.10 (open the full doc-editor view). §15.6.1 asks for an
// extra path: a *right-side* `[data-drawer="itemDetail"]` panel showing
// summary / source / tags + favorite / move / delete actions.
//
// To keep both paths alive without modifying biz/index.html, we inject a
// tiny ⓘ button into every rendered `.doc-row[data-document-id]` and
// listen for it via capture-phase. The button is placed absolutely so
// the prototype's row layout is unchanged.
//
// MutationObserver guarantees we cover rows added later by §15.9
// `loadFolderDetail` re-renders.

const ITEM_DETAIL_DRAWER_SELECTOR = '[data-drawer="itemDetail"]';
const DOC_INFO_BTN_CLASS = "bridge-doc-info-btn";

function _injectDocInfoButton(row) {
  if (!row || row.querySelector("." + DOC_INFO_BTN_CLASS)) return;
  const documentId = row.dataset.documentId;
  if (!documentId) return;
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = DOC_INFO_BTN_CLASS;
  btn.dataset.documentId = documentId;
  btn.setAttribute("aria-label", "查看文档详情");
  btn.title = "查看文档详情";
  btn.textContent = "ⓘ 详情";
  btn.style.cssText = [
    "position:absolute",
    "top:14px",
    "right:14px",
    "padding:4px 10px",
    "border-radius:8px",
    "border:1px solid rgba(123,140,255,.18)",
    "background:rgba(123,140,255,.10)",
    "color:#5a6b86",
    "font-size:11px",
    "font-weight:600",
    "cursor:pointer",
    "z-index:2",
  ].join(";");
  if (!row.style.position) row.style.position = "relative";
  row.appendChild(btn);
}

function _injectAllDocInfoButtons(root = document) {
  root
    .querySelectorAll(".doc-row[data-document-id]")
    .forEach((row) => _injectDocInfoButton(row));
}

function _formatDocDrawerMeta(doc) {
  const when = _formatFolderUpdated(doc.updated_at || doc.created_at);
  const type = doc.document_type || "note";
  const wc = doc.word_count != null ? `${doc.word_count} 字` : "";
  return [when, `类型 ${type}`, wc].filter(Boolean).join(" · ");
}

function _hydrateItemDetailDrawerForDocument(doc) {
  const drawer = document.querySelector(ITEM_DETAIL_DRAWER_SELECTOR);
  if (!drawer || !doc) return;
  const docId =
    doc.id != null && doc.id !== ""
      ? String(doc.id)
      : doc.document_id != null
        ? String(doc.document_id)
        : "";
  // Card drawer shares the same layer; clear card context when showing a KB document.
  delete drawer.dataset.cardId;
  drawer.dataset.documentId = docId;
  if (docId) drawer.setAttribute("data-document-id", docId);
  else drawer.removeAttribute("data-document-id");

  const titleEl = drawer.querySelector(".detail-drawer .drawer-head h2");
  const head = drawer.querySelector(".drawer-head");
  const subtitleEl =
    drawer.querySelector(".detail-drawer .drawer-head p") ||
    (head && head.querySelector("p"));
  if (titleEl) {
    titleEl.textContent = doc.title || "未命名文档";
  } else if (head) {
    const h2 = head.querySelector("h2");
    if (h2) h2.textContent = doc.title || "未命名文档";
  }
  if (subtitleEl) subtitleEl.textContent = _formatDocDrawerMeta(doc);
  const sections = drawer.querySelectorAll(".drawer-section");
  // (1) AI 摘要 + tags
  if (sections[0]) {
    const summaryP = sections[0].querySelector("p");
    if (summaryP) {
      summaryP.textContent =
        doc.summary || "（暂无摘要，请在编辑器中添加摘要并保存。）";
    }
    const tagBox = sections[0].querySelector(".source-chip-list");
    if (tagBox) {
      const tags = doc.tags || [];
      tagBox.innerHTML =
        tags.length > 0
          ? tags
              .map((t) => `<span class="tag">${escapeHtml(String(t))}</span>`)
              .join("")
          : '<span class="tag">无标签</span>';
    }
  }
  // (2) 来源与追溯
  if (sections[1]) {
    const articles = sections[1].querySelectorAll("article.quick-setting");
    if (articles[0]) {
      const strong = articles[0].querySelector("strong");
      const span = articles[0].querySelector("span");
      if (strong)
        strong.textContent =
          (doc.source && doc.source.name) || doc.title || "原始文档";
      if (span) {
        const t = (doc.source && doc.source.type) || "本地";
        const w = doc.word_count != null ? ` · ${doc.word_count} 字` : "";
        span.textContent = `${t}${w}`;
      }
    }
    if (articles[1]) {
      const strong = articles[1].querySelector("strong");
      const span = articles[1].querySelector("span");
      if (strong)
        strong.textContent =
          doc.folder && doc.folder.name
            ? `所属文件夹：${doc.folder.name}`
            : "未归档";
      if (span) span.textContent = "知识库";
    }
  }
  drawer.dataset.bridgeBound = "true";
}

function _openItemDetailDrawer() {
  document.querySelectorAll(".drawer-layer").forEach((layer) => {
    layer.hidden = true;
  });
  document.querySelectorAll(".surface-layer").forEach((layer) => {
    layer.hidden = true;
  });
  const drawer = document.querySelector(ITEM_DETAIL_DRAWER_SELECTOR);
  if (drawer) drawer.hidden = false;
}

async function loadDocumentForDrawer(documentId) {
  if (!documentId) return null;
  let doc;
  try {
    const r = await apiFetch(`/kb/documents/${documentId}?include_content=false`);
    doc = (r && r.data !== undefined) ? r.data : r;
  } catch (e) {
    console.error("[Mydow] /kb/documents/{id} (drawer) failed", e);
    toast(`打开文档详情失败: ${e.message}`, "error");
    return null;
  }
  if (!doc || typeof doc !== "object") {
    toast("打开文档详情失败: 响应无效", "error");
    return null;
  }
  _hydrateItemDetailDrawerForDocument(doc);
  _openItemDetailDrawer();
  window.dispatchEvent(
    new CustomEvent("mydow:doc-drawer-opened", { detail: { documentId, doc } }),
  );
  return doc;
}

function bindDocRowInfoButton() {
  // (1) Inject buttons for rows already rendered by §15.9 loadFolderDetail.
  _injectAllDocInfoButtons();
  // (2) Watch future renders so dynamically added rows also get the button.
  const observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
      m.addedNodes.forEach((node) => {
        if (node.nodeType !== 1) return;
        if (node.matches && node.matches(".doc-row[data-document-id]")) {
          _injectDocInfoButton(node);
        } else if (node.querySelectorAll) {
          _injectAllDocInfoButtons(node);
        }
      });
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
  // (3) Capture-phase click — wins against §15.10 bindDocRowClick.
  document.addEventListener(
    "click",
    async (event) => {
      const btn = event.target.closest("." + DOC_INFO_BTN_CLASS);
      if (!btn) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      const id = btn.dataset.documentId;
      if (!id) return;
      btn.disabled = true;
      try {
        await loadDocumentForDrawer(id);
      } finally {
        btn.disabled = false;
      }
    },
    true,
  );
}

async function patchDocumentById(documentId, updates) {
  if (!documentId) return null;
  try {
    const r = await apiFetch(`/kb/documents/${documentId}`, {
      method: "PATCH",
      body: updates,
    });
    return (r && r.data) || r;
  } catch (e) {
    console.error("[Mydow] PATCH /kb/documents/{id} failed", e);
    toast(`更新文档失败: ${e.message}`, "error");
    return null;
  }
}

async function deleteDocumentById(documentId) {
  if (!documentId) return null;
  try {
    return await apiFetch(`/kb/documents/${documentId}`, { method: "DELETE" });
  } catch (e) {
    console.error("[Mydow] DELETE /kb/documents/{id} failed", e);
    toast(`删除文档失败: ${e.message}`, "error");
    return null;
  }
}

async function moveDocumentById(documentId, targetFolderId) {
  if (!documentId || !targetFolderId) return null;
  try {
    return await apiFetch(`/kb/documents/${documentId}/move`, {
      method: "POST",
      body: { target_folder_id: targetFolderId },
    });
  } catch (e) {
    console.error("[Mydow] POST /kb/documents/{id}/move failed", e);
    toast(`移动文档失败: ${e.message}`, "error");
    return null;
  }
}

function bindItemDetailDrawerActions() {
  // Capture-phase: when itemDetail drawer represents a document (its
  // dataset.documentId is set by _hydrateItemDetailDrawerForDocument),
  // re-route the 移动 / 删除 footer buttons to real API calls instead
  // of the prototype's simulateAction toast.
  document.addEventListener(
    "click",
    async (event) => {
      const drawer = document.querySelector(ITEM_DETAIL_DRAWER_SELECTOR);
      if (!drawer || drawer.hidden) return;
      const documentId = drawer.dataset.documentId;
      if (!documentId) return;
      const btn = event.target.closest("button");
      if (!btn) return;
      const text = (btn.textContent || "").trim();
      // 移动到知识库 — V1: pick the first folder that's not the current
      // one from /kb/folders.
      if (/^移动到知识库$|^移动到/.test(text)) {
        event.preventDefault();
        event.stopImmediatePropagation();
        try {
          const r = await apiFetch("/kb/folders?include_counts=false&limit=20");
          const folders = (r && r.data && r.data.items) || [];
          const currentFolderText =
            drawer.querySelector(
              ".drawer-section:nth-child(3) article:nth-child(2) strong",
            )?.textContent || "";
          const candidate = folders.find(
            (f) => !currentFolderText.includes(f.name),
          );
          if (!candidate) {
            toast("没有其他文件夹可以移动到", "warning");
            return;
          }
          const moved = await moveDocumentById(documentId, candidate.id);
          if (moved) {
            toast(`已移动到「${candidate.name}」`, "success");
            const folderMain = document.querySelector(".folder-main");
            if (folderMain && folderMain.dataset.folderId) {
              loadFolderDetail(folderMain.dataset.folderId);
            }
            drawer.hidden = true;
          }
        } catch (e) {
          toast(`移动失败: ${e.message}`, "error");
        }
        return;
      }
      // 删除 — fire a real DELETE; the prototype's confirmDelete modal
      // is just a static toast simulation, so we use window.confirm
      // for explicit confirmation (V1 — replace with real modal in P1).
      if (/^删除$/.test(text) || /删除文档/.test(text)) {
        event.preventDefault();
        event.stopImmediatePropagation();
        const ok = window.confirm("确定要删除该文档吗？删除后将进入回收站。");
        if (!ok) return;
        const result = await deleteDocumentById(documentId);
        if (result) {
          toast("已删除文档", "success");
          drawer.hidden = true;
          const folderMain = document.querySelector(".folder-main");
          if (folderMain && folderMain.dataset.folderId) {
            loadFolderDetail(folderMain.dataset.folderId);
          }
        }
        return;
      }
    },
    true,
  );
}

// ─────────────────────────────────────────────  §9.6 keyboard shortcuts  ─
//
// The biz prototype IIFE already wires:
//   • Cmd/Ctrl+K  → open search modal (line 8164)
//   • Escape      → close search + all modals/drawers (line 8169-8176)
//
// We add the two missing shortcuts in bridge.js so we don't have to
// modify biz/index.html (per §3 territory rules):
//   • Cmd/Ctrl+Enter → submit capture text (when focus is in .capture textarea)
//   • "/"            → focus capture textarea (when not already in an input)
//
// Both shortcuts respect text-input contexts: typing "/" in an input or
// contenteditable still inserts the literal character; Cmd/Ctrl+Enter only
// fires when focus is in the home capture textarea (so AI chat / doc
// editor composer can keep their own newline behaviour).

function bindGlobalKeyboardShortcuts() {
  document.addEventListener("keydown", (event) => {
    // Cmd/Ctrl+Enter — submit capture from the home composer.
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      const composer = document.querySelector(".capture textarea");
      if (
        composer &&
        document.activeElement === composer &&
        (composer.value || "").trim()
      ) {
        event.preventDefault();
        const sendBtn =
          composer
            .closest(".capture")
            ?.querySelector(".send-button") || null;
        if (sendBtn) {
          sendBtn.click();
        }
        return;
      }
    }

    // "/" — focus the home capture textarea when not already in an editable.
    if (
      event.key === "/" &&
      !event.metaKey &&
      !event.ctrlKey &&
      !event.altKey &&
      !event.shiftKey
    ) {
      const target = event.target;
      const isEditable =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          (target.isContentEditable === true));
      if (isEditable) return;
      const composer = document.querySelector(".capture textarea");
      if (composer) {
        event.preventDefault();
        composer.focus();
      }
    }
  });
}

// ─────────────────────────────────────────────  §15.22 newDocument modal  ─
//
// biz/index.html ships a [data-modal="newDocument"] modal whose
// "创建并打开" button is wired by the inline IIFE to a static
// simulateAction → setPageMode("doc") path. We intercept in the
// capture phase, run a real POST /api/v1/kb/documents, then close
// the modal and hydrate the doc editor with the brand-new document
// id. The current folder context (when the user opened the modal from
// inside a folder detail page) is forwarded as folder_id so the
// document lands in the right place. Templates are mapped from the
// modal's display labels (空白文档 / 研究报告 / 方案框架) to the
// backend enum values (blank / research_report / solution_outline).

const _DOC_TEMPLATE_LABEL_TO_KEY = {
  "空白文档": "blank",
  "研究报告": "research_report",
  "方案框架": "solution_outline",
};

function _resolveCurrentFolderId() {
  const folderMain = document.querySelector(".folder-main[data-folder-id]");
  if (folderMain && folderMain.dataset.folderId) {
    return folderMain.dataset.folderId;
  }
  return null;
}

async function createDocumentFromModal({ title, templateKey, folderId }) {
  const body = {
    title: title || "新的产品设计笔记",
    template: templateKey || "blank",
  };
  if (folderId) body.folder_id = folderId;
  const r = await apiFetch("/kb/documents", {
    method: "POST",
    body,
  });
  return (r && r.data) || r || null;
}

function _applyDocPageMode() {
  const shell = document.querySelector(".page");
  if (!shell) return;
  const modes = [
    "knowledge-open",
    "folder-open",
    "ai-open",
    "garden-open",
    "skills-open",
    "notifications-open",
    "insights-full-open",
    "profile-open",
    "home-open",
    "doc-open",
  ];
  modes.forEach((m) => shell.classList.remove(m));
  shell.classList.add("doc-open");
  shell.classList.add("insights-open");
}

async function handleNewDocumentSubmit(button) {
  const modal = button.closest('[data-modal="newDocument"]');
  if (!modal) return;
  const titleInput = modal.querySelector(".form-field input");
  const templateSelect = modal.querySelector(".form-field select");
  const title = (titleInput?.value || "").trim() || "新的产品设计笔记";
  const templateLabel = (templateSelect?.value || "").trim() || "空白文档";
  const templateKey =
    _DOC_TEMPLATE_LABEL_TO_KEY[templateLabel] || "blank";
  const folderId = _resolveCurrentFolderId();

  button.disabled = true;
  const originalLabel = button.textContent;
  button.textContent = "创建中…";

  try {
    const doc = await createDocumentFromModal({
      title,
      templateKey,
      folderId,
    });
    if (!doc || !doc.id) {
      throw new Error("backend returned empty document");
    }
    closeAllModals();
    toast(`文档已创建：${doc.title}`, "success");
    _applyDocPageMode();
    await loadDocumentForEditor(doc.id);
    if (folderId) {
      try {
        await loadFolderDetail(folderId);
      } catch (_e) {
        /* non-fatal — folder detail will refresh next time */
      }
    }
    window.dispatchEvent(
      new CustomEvent("mydow:document-created", {
        detail: { id: doc.id, title: doc.title, folderId },
      }),
    );
  } catch (e) {
    console.error("[Mydow] newDocument submit failed", e);
    toast(`创建文档失败: ${e.message}`, "error");
  } finally {
    button.disabled = false;
    button.textContent = originalLabel;
  }
}

function bindKbNewDocumentSubmit() {
  document.addEventListener(
    "click",
    (event) => {
      const button = event.target.closest("[data-create-doc]");
      if (!button) return;
      const modal = button.closest('[data-modal="newDocument"]');
      if (!modal) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      handleNewDocumentSubmit(button).catch((e) =>
        console.error("[Mydow] newDocument modal handler", e),
      );
    },
    true,
  );
}

// ─────────────────────────────────────────────  §15.22 settings + logout  ─
//
// PRD10 §5.1 / §5.2 — the personal-center settings page in the biz prototype
// has 4 tabs (profile/security/preferences/billing) injected dynamically via
// the inline IIFE's `renderSettingsPanel(panel)`. Inside those panels:
//
//   • 主题模式 (segmented-control): "浅色模式" (active) + "深色模式"
//     [data-toast="已切换为浅色模式" / "深色模式已预览"]
//   • 自动保存 toggle (appears in profile AND preferences tab)
//     [data-toast="自动保存设置已更新"]
//   • 二步验证 toggle [data-toast="二步验证状态已更新"]
//
// All five buttons fire IIFE's `simulateAction` and persist nothing. We
// short-circuit them with capture-phase listeners that PATCH /me/preferences
// (the §15.22-introduced convenience alias) and update the visual state.
//
// `confirmDelete` modal additionally serves the security-tab "退出登录" /
// "清除本地缓存" sensitive-action buttons. The IIFE pops the modal but its
// "确认删除" button is generic. We track the most recent opener via a
// global ref and route the click accordingly.

const _CONFIRM_DELETE_CTX = { kind: null, label: null };

function _detectConfirmDeleteContext(opener) {
  // Walk up to find a meaningful label.
  if (!opener) return { kind: "generic", label: "确认删除" };
  const label = (opener.textContent || "").trim();
  if (label === "退出登录") return { kind: "logout", label };
  if (label === "清除本地缓存") return { kind: "clear_cache", label };
  // Document / card delete cases land in §15.10 P1 (out of scope for §15.22).
  return { kind: "generic", label: label || "确认删除" };
}

function bindConfirmDeleteContextTracking() {
  document.addEventListener(
    "click",
    (event) => {
      // (1) Direct opener buttons (security tab "退出登录" / "清除本地缓存"
      // and item-detail / doc-meta / folder-card delete buttons).
      const opener = event.target.closest('[data-open-modal="confirmDelete"]');
      if (opener) {
        const ctx = _detectConfirmDeleteContext(opener);
        _CONFIRM_DELETE_CTX.kind = ctx.kind;
        _CONFIRM_DELETE_CTX.label = ctx.label;
        // Debug breadcrumb so smoke tests can verify the tracker fires.
        window.__BIZ_LAST_CONFIRM_DELETE_CTX = { ...ctx, ts: Date.now() };
        return;
      }
      // (2) Account-menu "退出登录" item (biz/index.html line 7160). The IIFE
      // intercepts `[data-account-action="logout"]` and calls
      // ``openModal("confirmDelete")`` in JS, so there is no
      // `[data-open-modal]` attribute to detect. Sniff the menu action
      // instead so the same confirmDelete flow also lands on logout.
      const accountAction = event.target.closest(
        '[data-account-action="logout"]',
      );
      if (accountAction) {
        _CONFIRM_DELETE_CTX.kind = "logout";
        _CONFIRM_DELETE_CTX.label = "退出登录";
        window.__BIZ_LAST_CONFIRM_DELETE_CTX = {
          kind: "logout",
          label: "退出登录",
          ts: Date.now(),
        };
      }
    },
    true /* capture */,
  );
}

async function _performLogout() {
  // Clear PRD10 token + biz cache; reload reboots the auto-login flow which
  // either renders an auth overlay (if AGENTOS_DEMO_MODE off) or re-issues
  // a fresh demo session.
  try {
    setToken("");
  } catch {
    /* ignore */
  }
  safeLocalStorageRemove("mydow_biz_token");
  safeLocalStorageRemove(FAVORITE_SKILLS_KEY);
  toast("已退出登录，正在重新登录…", "info");
  // Reload after a short grace so the toast is visible.
  window.setTimeout(() => window.location.reload(), 700);
}

async function _performClearCache() {
  // Preserve auth token while wiping local UI state. Use safe wrappers so a
  // throwing localStorage (private mode / quota / blocker) doesn't fail the
  // operation — in-memory state is cleared regardless.
  const tok = safeLocalStorageGet("mydow_biz_token") || "";
  try {
    window.localStorage.clear();
  } catch {
    /* ignore — cannot clear, just rebuild memory */
  }
  _MEMORY_STORAGE.clear();
  if (tok) safeLocalStorageSet("mydow_biz_token", tok);
  toast("本地缓存已清除", "success");
}

function bindConfirmDeleteSubmit() {
  document.addEventListener(
    "click",
    (event) => {
      const button = event.target.closest(
        '[data-modal="confirmDelete"] button[data-toast]',
      );
      if (!button) return;
      const ctx = _CONFIRM_DELETE_CTX;
      // Debug breadcrumb so smoke tests can verify which branch ran.
      window.__BIZ_LAST_CONFIRM_DELETE_SUBMIT = {
        kind: ctx.kind,
        label: ctx.label,
        ts: Date.now(),
      };
      if (ctx.kind !== "logout" && ctx.kind !== "clear_cache") return;
      // We own this click — short-circuit the IIFE simulate.
      event.preventDefault();
      event.stopImmediatePropagation();
      closeAllModals();
      if (ctx.kind === "logout") {
        _performLogout().catch((e) => console.error("[Mydow] logout", e));
      } else if (ctx.kind === "clear_cache") {
        _performClearCache().catch((e) =>
          console.error("[Mydow] clear_cache", e),
        );
      }
      _CONFIRM_DELETE_CTX.kind = null;
      _CONFIRM_DELETE_CTX.label = null;
    },
    true,
  );
}

const _SETTINGS_TOGGLE_LABELS = new Set([
  "自动保存",
  "二步验证",
]);

function _toggleStateAfterClick(button) {
  // The IIFE flips `.active` on click via bubble phase; in capture phase the
  // class hasn't flipped yet. We compute the *intended* next state.
  return !button.classList.contains("active");
}

async function _patchPreferences(updates) {
  const r = await apiFetch("/me/preferences", {
    method: "PATCH",
    body: updates,
  });
  const me = (r && r.data) || r || null;
  if (me) {
    window._BIZ_ME_CACHE = me;
    window.dispatchEvent(
      new CustomEvent("mydow:me-updated", { detail: { me, payload: updates } }),
    );
  }
  return me;
}

async function _handleThemeToggle(button) {
  const wantDark = (button.textContent || "").includes("深色");
  const theme = wantDark ? "dark" : "light";
  try {
    await _patchPreferences({ theme });
    // Update segmented-control active class manually since we cancelled the IIFE.
    const group = button.parentElement;
    if (group) {
      group
        .querySelectorAll("button")
        .forEach((b) => b.classList.remove("active"));
      button.classList.add("active");
    }
    toast(`已切换为${wantDark ? "深色" : "浅色"}模式`, "success");
  } catch (e) {
    toast(`保存失败: ${e.message}`, "error");
  }
}

async function _handlePreferenceToggle(button, settingsKey, label) {
  const next = _toggleStateAfterClick(button);
  try {
    await _patchPreferences({ [settingsKey]: next });
    button.classList.toggle("active", next);
    button.setAttribute("aria-checked", String(next));
    toast(`${label}${next ? "已启用" : "已关闭"}`, "success");
  } catch (e) {
    toast(`保存失败: ${e.message}`, "error");
  }
}

function attachProfileSettingsHandlers() {
  document.addEventListener(
    "click",
    (event) => {
      const button = event.target.closest("button[data-toast]");
      if (!button) return;
      // Ignore buttons inside surface-layer modals — bindHomeModalSubmits
      // already routes those to dedicated handlers.
      if (button.closest(".surface-layer[data-modal]")) return;
      // Only fire inside the .profile-main settings page.
      if (!button.closest(".profile-main")) return;
      const toastText = (button.dataset.toast || "").trim();

      // Theme segmented-control.
      if (
        toastText === "已切换为浅色模式" ||
        toastText === "深色模式已预览"
      ) {
        event.preventDefault();
        event.stopImmediatePropagation();
        _handleThemeToggle(button).catch((e) =>
          console.error("[Mydow] theme toggle", e),
        );
        return;
      }

      // 自动保存 toggle (appears twice — both routes write `auto_save`).
      if (toastText === "自动保存设置已更新") {
        event.preventDefault();
        event.stopImmediatePropagation();
        _handlePreferenceToggle(button, "auto_save", "自动保存").catch((e) =>
          console.error("[Mydow] auto_save toggle", e),
        );
        return;
      }

      // 二步验证 toggle.
      if (toastText === "二步验证状态已更新") {
        event.preventDefault();
        event.stopImmediatePropagation();
        _handlePreferenceToggle(
          button,
          "two_factor_enabled",
          "二步验证",
        ).catch((e) => console.error("[Mydow] 2fa toggle", e));
        return;
      }
    },
    true /* capture */,
  );
}

function _hydrateSettingsPanelFromCache() {
  // Apply cached User.settings to the rendered settings panel so the
  // toggles / segmented-controls reflect the actual server-side state.
  // Called after [data-settings-panel] click + a microtask so the IIFE's
  // innerHTML rewrite has settled.
  const main = document.querySelector(".profile-main");
  if (!main) return;
  const settings = (window._BIZ_ME_CACHE && window._BIZ_ME_CACHE.settings) || {};

  // Theme segmented-control.
  const themeGroup = main.querySelector(".segmented-control");
  if (themeGroup) {
    const wantDark = settings.theme === "dark";
    themeGroup
      .querySelectorAll("button")
      .forEach((btn) => {
        const isDark = (btn.textContent || "").includes("深色");
        btn.classList.toggle("active", isDark === wantDark);
      });
  }

  // Toggles by data-toast label.
  main.querySelectorAll("button.toggle-switch").forEach((btn) => {
    const label = (btn.dataset.toast || "").trim();
    if (label === "自动保存设置已更新") {
      btn.classList.toggle("active", Boolean(settings.auto_save));
      btn.setAttribute("aria-checked", String(Boolean(settings.auto_save)));
    } else if (label === "二步验证状态已更新") {
      btn.classList.toggle(
        "active",
        Boolean(settings.two_factor_enabled),
      );
      btn.setAttribute(
        "aria-checked",
        String(Boolean(settings.two_factor_enabled)),
      );
    }
  });
}

function bindSettingsPanelHydration() {
  // The IIFE listens for [data-settings-panel] clicks and synchronously
  // rewrites profileStack.innerHTML. We piggy-back on the same trigger,
  // run after a microtask, then apply cached settings to the new DOM.
  document.addEventListener(
    "click",
    (event) => {
      const trigger = event.target.closest("[data-settings-panel]");
      if (!trigger) return;
      // Don't preventDefault — let the IIFE render normally.
      window.setTimeout(_hydrateSettingsPanelFromCache, 0);
    },
    false /* bubble — runs after IIFE's listener at document level */,
  );
}

// ─────────────────────────────────────────────  §15.23 boot aliases  ──────
//
// A previous editing pass wired four §15.23 names into ``boot()`` and
// ``window.MydowBridge`` without ever defining them (``attachSettingsBindings``
// / ``_watchProfileMainMutations`` / ``hydrateSettingsControlsFromMe`` /
// ``patchMePreference``). At runtime that crashed ``boot`` with a
// ``ReferenceError`` and silently disabled every later hydrator. We resolve
// the dangling references to the §15.22 helpers above so the existing boot
// signatures keep working without changing them.
//
// ─────────────────────────────────────────────  §10.3 onboarding tour  ────
//
// First-time visitors get a 4-step guided tour of the minimum demo loop
// (capture → KB → AI → personal-center). Subsequent visits are silent
// because the localStorage flag is set after a finish/skip click. An
// "重新观看引导" entry is stashed on `window.MydowBridge.restartOnboarding`
// so the bridge user can re-trigger the tour during an investor walk-
// through, e.g. via a console command or a future settings menu item.
// Implementation is DOM-only (no biz/index.html mutation) so it stays
// non-conflicting with other agents' lanes.

const _BIZ_ONBOARDING_KEY = "mydow_biz_onboarded_v1";

const _ONBOARDING_STEPS = [
  {
    title: "欢迎来到 Mydow",
    body:
      "用 30 秒走完 Mydow 的核心闭环：记录 → 知识库 → AI 提问 → 沉淀。"
      + " 全程真实数据驱动，所有按钮都接到了 PRD10 后端。",
    target: null,
    cta: "开始引导",
  },
  {
    title: "记录灵感（首页）",
    body:
      "在首页的输入框写一句想法，回车或点击右下蓝色提交按钮。"
      + " 后端会自动整理为「灵感卡片」并落入「最近捕捉」。",
    target: ".composer .send-button",
    targetFallback: ".send-button",
    targetPage: "home",
    cta: "下一步",
  },
  {
    title: "知识库（左导航第二项）",
    body:
      "点击「知识库」进入文件夹网格，6 个文件夹 / 20+ 篇文档实时呈现。"
      + " 文件夹点开后可看到文档列表，文档行可直接编辑、移动、删除。",
    target: '[data-nav-target="knowledge"]',
    cta: "下一步",
  },
  {
    title: "Mydow AI（左导航第四项）",
    body:
      "点击「Mydow AI」进入对话工作台，输入问题即可 SSE 真流式返回，"
      + " 引用知识库内容；回答可一键保存为知识卡 / 任务。",
    target: '[data-nav-target="ai"]',
    cta: "下一步",
  },
  {
    title: "右上头像 → 个人中心",
    body:
      "点击右上头像可打开个人中心：主题、自动保存、二步验证、通知偏好"
      + " 全都真实落库。左侧品牌旁「演示」微标可再次打开本引导；也可在控制台执行"
      + " window.MydowBridge.restartOnboarding()。",
    target: "[data-open-profile]",
    cta: "完成",
  },
];

function _onboardingShouldStart() {
  try {
    if (window.localStorage.getItem(_BIZ_ONBOARDING_KEY) === "1") return false;
  } catch {
    return false;
  }
  // Honor reduced-motion users by skipping the tour visuals; they can still
  // run it manually via restartOnboarding(). Defensive: matchMedia may be
  // unavailable in some headless environments.
  try {
    const m = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)");
    if (m && m.matches) return false;
  } catch {
    /* ignore */
  }
  return true;
}

function _ensureOnboardingStyles() {
  if (document.getElementById("mydow-onboarding-style")) return;
  const style = document.createElement("style");
  style.id = "mydow-onboarding-style";
  style.textContent = `
#mydow-onboarding-overlay {
  position: fixed; inset: 0; z-index: 99000;
  background: rgba(8, 14, 32, 0.55);
  display: flex; align-items: center; justify-content: center;
  backdrop-filter: blur(2px);
  animation: mydowOnbFade 220ms ease-out both;
}
#mydow-onboarding-card {
  width: min(520px, calc(100vw - 32px));
  background: linear-gradient(180deg, #ffffff, #f5f7ff);
  border-radius: 18px;
  box-shadow: 0 18px 48px rgba(34, 50, 100, 0.32);
  padding: 26px 28px 22px;
  font-family: inherit; color: #1f2640;
  position: relative;
  animation: mydowOnbRise 220ms ease-out both;
}
#mydow-onboarding-card .step-counter {
  font-size: 12px; letter-spacing: 1px; color: #6477ff;
  text-transform: uppercase; margin-bottom: 10px;
}
#mydow-onboarding-card h3 {
  margin: 0 0 8px; font-size: 22px; font-weight: 700; color: #1a2547;
}
#mydow-onboarding-card p {
  margin: 0 0 22px; font-size: 14px; line-height: 1.7; color: #38456a;
}
#mydow-onboarding-card .actions {
  display: flex; gap: 10px; justify-content: flex-end;
}
#mydow-onboarding-card .actions button {
  appearance: none; border: none; cursor: pointer;
  padding: 10px 20px; border-radius: 999px; font-size: 13px;
  transition: transform 120ms ease, box-shadow 160ms ease;
}
#mydow-onboarding-card .actions .skip {
  background: transparent; color: #6477ff;
}
#mydow-onboarding-card .actions .skip:hover { background: rgba(100, 119, 255, 0.08); }
#mydow-onboarding-card .actions .next {
  background: linear-gradient(135deg, #5b78ff, #8a6dff);
  color: #fff; font-weight: 600; box-shadow: 0 6px 18px rgba(92, 122, 255, 0.35);
}
#mydow-onboarding-card .actions .next:hover { transform: translateY(-1px); }
.mydow-onboarding-spotlight {
  position: fixed; z-index: 98900; pointer-events: none;
  border-radius: 14px;
  box-shadow: 0 0 0 4px rgba(255,255,255,0.95),
              0 0 0 9999px rgba(8,14,32,0.55),
              0 0 28px 6px rgba(91, 120, 255, 0.55);
  transition: top 200ms ease, left 200ms ease, width 200ms ease, height 200ms ease;
}
@keyframes mydowOnbFade { from { opacity: 0 } to { opacity: 1 } }
@keyframes mydowOnbRise {
  from { opacity: 0; transform: translateY(12px) scale(0.98) }
  to { opacity: 1; transform: translateY(0) scale(1) }
}
@media (prefers-reduced-motion: reduce) {
  #mydow-onboarding-overlay,
  #mydow-onboarding-card,
  .mydow-onboarding-spotlight {
    animation: none !important; transition: none !important;
  }
}
`;
  document.head.appendChild(style);
}

let _ONBOARDING_STATE = null;

function _onboardingTeardown() {
  const overlay = document.getElementById("mydow-onboarding-overlay");
  if (overlay) overlay.remove();
  document.querySelectorAll(".mydow-onboarding-spotlight").forEach((el) => el.remove());
  _ONBOARDING_STATE = null;
}

function _writeOnboardingFlag() {
  try {
    window.localStorage.setItem(_BIZ_ONBOARDING_KEY, "1");
  } catch {
    /* localStorage may be denied in private mode */
  }
}

function _onboardingFinish(reason) {
  _writeOnboardingFlag();
  _onboardingTeardown();
  window.dispatchEvent(
    new CustomEvent("mydow:onboarding-finished", { detail: { reason } }),
  );
  if (reason === "completed") {
    try {
      toast("引导已完成 · 投资人模式 ✓", "success");
    } catch {
      /* toast unavailable */
    }
  }
}

function _highlightSpotlight(targetSelector, targetFallback) {
  document.querySelectorAll(".mydow-onboarding-spotlight").forEach((el) => el.remove());
  if (!targetSelector) return;
  const target =
    document.querySelector(targetSelector)
    || (targetFallback && document.querySelector(targetFallback));
  if (!target) return;
  const rect = target.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return;
  const padding = 6;
  const spotlight = document.createElement("div");
  spotlight.className = "mydow-onboarding-spotlight";
  spotlight.style.top = `${Math.max(0, rect.top - padding)}px`;
  spotlight.style.left = `${Math.max(0, rect.left - padding)}px`;
  spotlight.style.width = `${rect.width + padding * 2}px`;
  spotlight.style.height = `${rect.height + padding * 2}px`;
  document.body.appendChild(spotlight);
}

function _renderOnboardingStep(idx) {
  const total = _ONBOARDING_STEPS.length;
  const step = _ONBOARDING_STEPS[idx];
  if (!step) {
    _onboardingFinish("completed");
    return;
  }
  _ONBOARDING_STATE = { idx };

  let overlay = document.getElementById("mydow-onboarding-overlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "mydow-onboarding-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", "Mydow 引导");
    document.body.appendChild(overlay);
  }

  const isLast = idx >= total - 1;
  overlay.innerHTML = `
<div id="mydow-onboarding-card">
  <div class="step-counter">第 ${idx + 1} / ${total} 步</div>
  <h3></h3>
  <p></p>
  <div class="actions">
    <button class="skip" type="button" data-onboarding-action="skip">跳过</button>
    <button class="next" type="button" data-onboarding-action="next">${isLast ? "完成" : (step.cta || "下一步")}</button>
  </div>
</div>`;
  // Use textContent to defang any HTML in step.body / step.title.
  const card = overlay.querySelector("#mydow-onboarding-card");
  card.querySelector("h3").textContent = step.title;
  card.querySelector("p").textContent = step.body;

  // Pre-navigate to the page that hosts the highlighted target where it
  // makes sense — e.g. step "记录灵感" needs to be on the home page so the
  // .send-button is actually rendered. We rely on the IIFE's setPageMode
  // which reacts to data-nav-target click.
  if (step.targetPage) {
    const navLink = document.querySelector(
      `[data-nav-target="${step.targetPage}"]`,
    );
    if (navLink) navLink.click();
  }

  // Position the spotlight after a tick so layout settles after any nav.
  window.setTimeout(() => _highlightSpotlight(step.target, step.targetFallback), 60);

  // Wire the actions (we don't keep handlers around; one click = next or
  // teardown).
  card.querySelectorAll("[data-onboarding-action]").forEach((btn) => {
    btn.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      const action = btn.dataset.onboardingAction;
      if (action === "skip") {
        _onboardingFinish("skipped");
        return;
      }
      if (idx + 1 < total) {
        _renderOnboardingStep(idx + 1);
      } else {
        _onboardingFinish("completed");
      }
    });
  });
}

function bootOnboardingIfFirstTime() {
  if (!_onboardingShouldStart()) return false;
  _ensureOnboardingStyles();
  // Defer one tick so the rest of boot's hydrators get a chance to mount.
  window.setTimeout(() => _renderOnboardingStep(0), 250);
  return true;
}

function restartOnboarding() {
  try {
    window.localStorage.removeItem(_BIZ_ONBOARDING_KEY);
  } catch {
    /* ignore */
  }
  _ensureOnboardingStyles();
  _renderOnboardingStep(0);
  return true;
}

/** Sidebar brand row: near-invisible chip for investor demos (§10.3). */
function _injectOnboardingRestartChip() {
  if (document.querySelector("[data-restart-onboarding]")) return;
  const brand = document.querySelector(".sidebar .brand");
  if (!brand) return;
  const chip = document.createElement("button");
  chip.type = "button";
  chip.dataset.restartOnboarding = "";
  chip.setAttribute("aria-label", "重新观看引导（演示）");
  chip.setAttribute("title", "投资人演示：重新打开首次引导");
  chip.textContent = "演示";
  chip.style.cssText = [
    "margin-left:6px",
    "font-size:10px",
    "font-weight:600",
    "letter-spacing:0.06em",
    "opacity:0.13",
    "cursor:pointer",
    "border:none",
    "background:transparent",
    "padding:2px 4px",
    "border-radius:4px",
    "color:inherit",
    "line-height:1",
  ].join(";");
  chip.addEventListener("mouseenter", () => {
    chip.style.opacity = "0.5";
  });
  chip.addEventListener("mouseleave", () => {
    chip.style.opacity = "0.13";
  });
  chip.addEventListener("click", (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    restartOnboarding();
  });
  brand.appendChild(chip);
}

function attachSettingsBindings() {
  bindConfirmDeleteContextTracking();
  bindConfirmDeleteSubmit();
  attachProfileSettingsHandlers();
  bindSettingsPanelHydration();
  _prefillEditProfileFromMe();
}

function hydrateSettingsControlsFromMe(me) {
  if (me) window._BIZ_ME_CACHE = me;
  _hydrateSettingsPanelFromCache();
}

function _watchProfileMainMutations() {
  // The IIFE rewrites ``.profile-main`` innerHTML each time the user
  // switches between settings tabs. A MutationObserver re-applies the
  // cached preference state every time so toggles don't visually drift
  // out of sync with the server-side User.settings JSON.
  const main = document.querySelector(".profile-main");
  if (!main || typeof MutationObserver === "undefined") return;
  const observer = new MutationObserver(() => {
    // Coalesce bursts; the IIFE typically does one full innerHTML swap
    // per tab change, but rerenders inside .profile-stack also bubble.
    window.setTimeout(_hydrateSettingsPanelFromCache, 0);
  });
  observer.observe(main, { childList: true, subtree: true });
}

async function patchMePreference(updates) {
  return await _patchPreferences(updates);
}

// ─────────────────────────────────────────────  Boot  ──────────────────────
async function boot() {
  const ok = await ensureSession();
  if (!ok) return;
  // §15.18 — refresh the user chip with /me; abort wiring if /me fails so
  // we don't leave the prototype in a half-bound state.
  const me = await refreshProfileChip();
  if (!me) {
    console.warn("[Mydow] /me failed; clearing token");
    setToken("");
    return;
  }
  injectMobileUsabilityFixes();
  injectBrandMeta();
  _injectOnboardingRestartChip();
  attachLayerStateMarkers();
  rebindCaptureSubmit();
  listenForFeedRefresh();
  bindHomeModalSubmits();
  attachInsightsFullPanelHandlers();
  attachGardenBoardHandlers();
  attachGardenControlHandlers();
  attachSkillsHandlers();
  // PRD10 §15.24 — register the capture-phase listener that stashes the
  // active skill_id when the user clicks `[data-open-modal="skillRun"]`
  // on a skill card. Without this, `handleSkillRunModal` always falls
  // back to the first card in the grid.
  _stashSkillRunContext();
  attachAiHandlers();
  attachAiContextHandlers();
  attachAiSaveHandlers();
  attachGlobalSearchHandlers();
  // §15.8 KB folder grid + favorite + new-folder modal
  bindKbStarActions();
  bindKbNewFolderSubmit();
  bindKbCardOpenFolder();
  // §15.6 idea-card click → drawer hydration + favorite toggle
  bindCardClickToDrawer();
  bindCardFavoriteAction();
  // §15.9 folder detail (loaded on demand via mydow:kb-folder-clicked)
  bindFolderClickToDetail();
  // §15.17 notifications mark-read + mark-all
  bindNotificationRowMarkRead();
  bindNotificationMarkAll();
  // §15.10 doc detail/edit
  bindDocRowClick();
  bindDocEditorAutoSave();
  // §15.5i daily-insight «查看洞察详情» link → open insights-full panel
  attachDailyInsightLink();
  // §15.6.1 doc-row 内 ⓘ 详情 → /kb/documents/{id} → itemDetail drawer
  // + drawer 内「移动到知识库」「删除」按钮 capture-phase 接 PRD10 真 API
  // (覆盖 §15.10 P1：DELETE 按钮 + move 文档)
  bindDocRowInfoButton();
  bindItemDetailDrawerActions();
  // §15.22 [data-modal=newDocument] 「创建并打开」 → POST /kb/documents 真创建
  bindKbNewDocumentSubmit();
  // §9.6 keyboard shortcuts — Cmd/Ctrl+Enter submits capture, "/" focuses
  // the home composer; Cmd/Ctrl+K and Esc are already wired by the IIFE.
  bindGlobalKeyboardShortcuts();
  // §15.22 5 个 detail-drawer / confirmDelete CRUD 按钮接真后端：
  // (移动卡片到知识库 / 删除卡片 / 创建整理任务 / 复制分享链接 / 收藏 Skill)
  bindDrawerOpenContextSync();
  bindDrawerCrudButtons();
  // §15.27 5 个 AI-action buttons 接 /skills/run + /cards 真后端
  bindDrawerAiActionButtons();
  // §15.23 个人中心设置 4 tab + 通知设置弹窗 + 编辑资料 modal → PATCH /api/v1/me
  attachSettingsBindings();
  // §15.30 v1.4 sync — 3 new modals: aiPersonalize / customInsight / insightHistory
  _prefillAiPersonalizeFromMe();
  _bindCustomInsightNotePicker();
  _bindInsightHistoryOpener();
  _watchProfileMainMutations();
  // Sync toggle / segmented states with cached /me right after first mount.
  if (window._BIZ_ME_CACHE) {
    hydrateSettingsControlsFromMe(window._BIZ_ME_CACHE);
  }
  window.__MYDOW_BRIDGE_BOOTED = true;
  if (window.MydowBridge) {
    window.MydowBridge.booted = true;
  }
  // §15.19 global search is bound by Agent 3 via attachGlobalSearchHandlers,
  // which runs after the search-modal is opened.
  // Fire-and-forget the data hydrators; failures only log + skip rendering.
  Promise.allSettled([
    refreshUnreadBadge(),
    refreshTodayInsights(),
    refreshFeedCounters(),
    loadFeedIntoRecentView(),
    refreshInsightsFullPanel(),
    refreshGardenBoard(),
    refreshSkillsGrid(),
    refreshAiHistory(),
    loadKbLibraryGrid(),
    loadNotifications(),
    // §15.5 right-side panel hydration (5 cards + mini-stats + topic-donut + bar-list)
    refreshHomeContentDistribution(),
    refreshHomeAiActivity(),
    refreshHomeDailyInsightCard(),
    refreshHomeRecentList(),
    refreshKbOverviewCard(),
    refreshNotificationMiniStats(),
    refreshFullInsightDrawer(),
    // §15.5j right-rail 顶部 3 张 stat-card（home 页 .right-rail .stats）
    refreshHomeRightRailStatCards(),
  ]).then(() => {
    toast("已连接 PRD10 后端 · demo 已登录", "success");
    bootOnboardingIfFirstTime();
  });
}

window.MydowBridge = {
  booted: false,
  apiFetch,
  toast,
  ensureSession,
  submitCaptureText,
  rebindCaptureSubmit,
  bindHomeModalSubmits,
  injectMobileUsabilityFixes,
  injectBrandMeta,
  uploadAndCommitFile,
  handleUploadFileModal,
  handleWebLinkModal,
  handleDeepResearchModal,
  handleVoiceInputModal,
  closeAllModals,
  syncLayerStateMarkers,
  attachLayerStateMarkers,
  refreshProfileChip,
  // §15.23 — settings PATCH /me + notification settings + edit profile
  patchMePreference,
  hydrateSettingsControlsFromMe,
  attachSettingsBindings,
  // §15.30 v1.4 sync exports
  handleAiPersonalizeModal,
  handleCustomInsightModal,
  loadInsightHistoryModal,
  refreshUnreadBadge,
  refreshTodayInsights,
  // §15.5 right-side panel hydrators (5 cards + mini-stats + topic-donut + bar-list)
  refreshHomeContentDistribution,
  refreshHomeAiActivity,
  refreshHomeDailyInsightCard,
  refreshHomeRecentList,
  refreshKbOverviewCard,
  refreshNotificationMiniStats,
  refreshFullInsightDrawer,
  refreshHomeRightRailStatCards,
  attachDailyInsightLink,
  refreshFeedCounters,
  loadFeedIntoRecentView,
  refreshInsightsFullPanel,
  dismissInsight,
  loadReportDetail,
  refreshGardenBoard,
  searchByTopic,
  attachGardenControlHandlers,
  refreshSkillsGrid,
  runSkill,
  // §15.12 AI workspace
  refreshAiHistory,
  loadAndRenderConversation,
  submitAiMessage,
  streamAiMessage,
  ensureActiveConversation,
  // §15.13 / §15.14 / §15.19
  refreshAiContextModal,
  attachAiContextHandlers,
  attachAiSaveHandlers,
  attachGlobalSearchHandlers,
  performGlobalSearch,
  // §15.8 KB
  loadKbLibraryGrid,
  toggleFolderFavorite,
  createFolderFromModal,
  bindKbStarActions,
  bindKbNewFolderSubmit,
  bindKbCardOpenFolder,
  // §15.6 cards
  loadCardForDrawer,
  hydrateItemDetailDrawer,
  bindCardClickToDrawer,
  favoriteCardById,
  bindCardFavoriteAction,
  // §15.9 folder detail
  loadFolderDetail,
  bindFolderClickToDetail,
  // §15.17 notifications list + mark
  loadNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  bindNotificationRowMarkRead,
  bindNotificationMarkAll,
  // §15.18 profile main
  hydrateProfileMain,
  // §15.10 doc detail/edit
  loadDocumentForEditor,
  patchCurrentDocument,
  bindDocRowClick,
  bindDocEditorAutoSave,
  // §15.6.1 doc-row → itemDetail drawer + drawer 移动/删除/收藏 capture-phase
  loadDocumentForDrawer,
  bindDocRowInfoButton,
  bindItemDetailDrawerActions,
  patchDocumentById,
  deleteDocumentById,
  moveDocumentById,
  // §15.23 newDocument modal real POST /kb/documents
  createDocumentFromModal,
  handleNewDocumentSubmit,
  bindKbNewDocumentSubmit,
  // §9.6 keyboard shortcuts (Cmd/Ctrl+Enter submit, "/" focus composer)
  bindGlobalKeyboardShortcuts,
  // §15.24 skillRun modal POST /skills/{id}/run
  handleSkillRunModal,
  // §15.25 notificationSettings modal PATCH /me { settings.notifications }
  handleNotificationSettingsModal,
  // §15.26 editProfile modal PATCH /me { name, settings.display_role }
  handleEditProfileModal,
  // §15.22 detail-drawer / confirmDelete CRUD buttons
  bindDrawerOpenContextSync,
  bindDrawerCrudButtons,
  moveCardToKb,
  deleteCurrentSubject,
  createTaskFromInsight,
  copyCardShareLink,
  toggleSkillFavorite,
  // §15.22 settings page toggles + confirmDelete logout/clear-cache wiring
  attachProfileSettingsHandlers,
  bindConfirmDeleteContextTracking,
  bindConfirmDeleteSubmit,
  bindSettingsPanelHydration,
  // §14.12 localStorage quota-safe helpers
  safeLocalStorageGet,
  safeLocalStorageSet,
  safeLocalStorageRemove,
  // §15.27 AI-action drawer buttons (5 data-toast intents on item-detail/insightDetail)
  bindDrawerAiActionButtons,
  /** §10.3 first-time tour + investor replay */
  restartOnboarding,
  runSkillForCard,
  generateCardFromCurrentDrawer,
  saveInsightToKb,
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot, { once: true });
} else {
  boot();
}
