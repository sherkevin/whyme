/**
 * Mydow Web — true SPA driven by PRD10 backend.
 *
 * Design goals (drives every decision below):
 *   1. Every UI element must be JS-rendered from real backend data.
 *      No hardcoded sample lists, no `simulateAction` toasts that pretend
 *      to do work. If a button exists, clicking it hits a real API.
 *   2. All four UI states (Loading / Empty / Error / Success) are always
 *      visible affordances per page (PRD10 §20).
 *   3. Hash routing keeps every page deep-linkable.
 *      #/home, #/kb, #/kb/folder/<id>, #/kb/doc/<id>,
 *      #/ai, #/ai/<conv>, #/skills, #/garden, #/search?q=...
 *   4. No external runtime dependencies. Native ESM only.
 */

const API_BASE =
  (window.MYDOW_API_BASE && String(window.MYDOW_API_BASE)) || "/api/v1";
const TOKEN_KEY = "mydow_token";
const USER_KEY = "mydow_user";
const THEME_KEY = "mydow_theme";
const LOCALE_KEY = "mydow_locale";
const THEME_VALUES = ["system", "light", "dark"];
const LOCALE_VALUES = ["zh", "en"];

// ─────────────────────────────────────────────  Utilities  ──────────────

function $(html) {
  const tpl = document.createElement("template");
  tpl.innerHTML = html.trim();
  return tpl.content.firstElementChild;
}
function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") {
      node.addEventListener(k.slice(2).toLowerCase(), v);
    } else if (v != null && v !== false) {
      node.setAttribute(k, v === true ? "" : String(v));
    }
  }
  const arr = Array.isArray(children) ? children : [children];
  for (const c of arr) {
    if (c == null || c === false) continue;
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  if (tag === "button" && node.classList.contains("btn-icon")) {
    const label = attrs["aria-label"] || attrs.title;
    if (label && !node.getAttribute("aria-label")) {
      node.setAttribute("aria-label", String(label));
    }
  }
  if (tag !== "button" && node.getAttribute("role") === "button") {
    node.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        node.click();
      }
    });
  }
  return node;
}
function svg(name, size = 18) {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("class", "icon");
  s.setAttribute("width", size);
  s.setAttribute("height", size);
  const u = document.createElementNS("http://www.w3.org/2000/svg", "use");
  u.setAttributeNS(
    "http://www.w3.org/1999/xlink",
    "xlink:href",
    "#i-" + name,
  );
  u.setAttribute("href", "#i-" + name);
  s.appendChild(u);
  return s;
}
function escapeHtml(v) {
  if (v == null) return "";
  return String(v)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
function relTime(iso) {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (!t) return "";
  const diff = Math.floor((Date.now() - t) / 1000);
  if (diff < 60) return "刚刚";
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
  if (diff < 7 * 86400) return `${Math.floor(diff / 86400)} 天前`;
  return new Date(iso).toLocaleDateString("zh-CN");
}
function debounce(fn, ms) {
  let t = null;
  return (...args) => {
    if (t) clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

// ─────────────────────────────────────────────  Storage  ────────────────

const store = {
  token: () => localStorage.getItem(TOKEN_KEY),
  setToken: (v) =>
    v ? localStorage.setItem(TOKEN_KEY, v) : localStorage.removeItem(TOKEN_KEY),
  user: () => {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || "null");
    } catch (e) {
      return null;
    }
  },
  setUser: (v) =>
    v
      ? localStorage.setItem(USER_KEY, JSON.stringify(v))
      : localStorage.removeItem(USER_KEY),
  theme: () => {
    const saved = localStorage.getItem(THEME_KEY);
    return THEME_VALUES.includes(saved) ? saved : "system";
  },
  setTheme: (v) => {
    const next = THEME_VALUES.includes(v) ? v : "system";
    if (next === "system") localStorage.removeItem(THEME_KEY);
    else localStorage.setItem(THEME_KEY, next);
    return next;
  },
  locale: () => {
    const saved = localStorage.getItem(LOCALE_KEY);
    return LOCALE_VALUES.includes(saved) ? saved : null;
  },
  setLocale: (v) => {
    const next = normalizeLocale(v);
    localStorage.setItem(LOCALE_KEY, next);
    return next;
  },
  clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
};

function applyTheme(mode = store.theme()) {
  const root = document.documentElement;
  root.dataset.themePreference = mode;
  if (mode === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.dataset.theme = mode;
  }
  const toggle = document.querySelector("[data-theme-toggle]");
  if (toggle) {
    toggle.setAttribute("data-theme-mode", mode);
    toggle.setAttribute("title", themeLabel(mode));
    toggle.setAttribute("aria-label", themeLabel(mode));
    const use = toggle.querySelector("use");
    if (use) {
      const icon = mode === "dark" ? "#i-moon" : "#i-sun";
      use.setAttribute("href", icon);
      use.setAttributeNS("http://www.w3.org/1999/xlink", "xlink:href", icon);
    }
  }
  return mode;
}

function themeLabel(mode = store.theme()) {
  if (mode === "dark") return "深色模式";
  if (mode === "light") return "浅色模式";
  return "跟随系统";
}

function cycleTheme() {
  const current = store.theme();
  const next =
    current === "system" ? "light" : current === "light" ? "dark" : "system";
  applyTheme(store.setTheme(next));
  toast(`主题已切换：${themeLabel(next)}`, "success");
}

applyTheme();

// Locale is resolved from persisted user settings first, then the local
// browser preference. The switcher persists back to /me so it is not a
// cosmetic-only toggle.
const i18n = {
  locale: "zh",
  dict: {},
};

function normalizeLocale(value) {
  return String(value || "")
    .toLowerCase()
    .startsWith("en")
    ? "en"
    : "zh";
}

function resolveLocale() {
  const user = state.me || store.user() || {};
  const settings = user.settings || {};
  return normalizeLocale(
    user.locale ||
      settings.locale ||
      settings.language ||
      store.locale() ||
      navigator.language ||
      "zh-CN",
  );
}

async function loadLocale(locale = resolveLocale()) {
  const next = normalizeLocale(locale);
  try {
    const resp = await fetch(`./i18n/${next}.json`, { cache: "no-store" });
    if (!resp.ok) throw new Error(`i18n ${next} ${resp.status}`);
    i18n.dict = await resp.json();
    i18n.locale = next;
  } catch (e) {
    console.warn("[Mydow] i18n load failed, falling back to zh", e);
    i18n.locale = "zh";
    i18n.dict = {};
  }
  document.documentElement.lang = i18n.locale === "en" ? "en" : "zh-CN";
  document.documentElement.dataset.locale = i18n.locale;
  return i18n.locale;
}

function t(key, fallback = key, vars = {}) {
  const template = i18n.dict[key] || fallback || key;
  return String(template).replace(/\{(\w+)\}/g, (_, name) =>
    vars[name] == null ? "" : String(vars[name]),
  );
}

async function setLocale(locale, { persist = true } = {}) {
  const next = store.setLocale(locale);
  await loadLocale(next);
  if (persist && store.token()) {
    try {
      const apiLocale = next === "en" ? "en-US" : "zh-CN";
      const updated = await api("/me", {
        method: "PATCH",
        body: { locale: apiLocale, settings: { locale: apiLocale } },
      });
      const meData = updated && (updated.data || updated);
      if (meData) {
        state.me = meData;
        store.setUser(meData);
      }
    } catch (e) {
      toast(`语言偏好保存失败: ${e.message}`, "warning");
    }
  }
  renderShell();
  await renderPage();
  toast(t("toast.localeChanged", "语言已切换"), "success");
  return next;
}

// ─────────────────────────────────────────────  HTTP client  ─────────────

async function api(path, options = {}) {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const headers = Object.assign(
    { "Content-Type": "application/json" },
    options.headers || {},
  );
  const token = store.token();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const init = { ...options, headers };
  if (init.body && typeof init.body !== "string") {
    init.body = JSON.stringify(init.body);
  }

  let resp;
  try {
    resp = await fetch(url, init);
  } catch (e) {
    const err = new Error("网络异常，请检查后端是否启动");
    err.code = "NETWORK_ERROR";
    throw err;
  }
  const text = await resp.text();
  let body = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = { raw: text };
    }
  }
  if (!resp.ok) {
    const code =
      (body && body.error && body.error.code) || `HTTP_${resp.status}`;
    const message =
      (body && body.error && body.error.message) ||
      (body && body.detail && (body.detail.message || body.detail)) ||
      `Request failed: ${resp.status}`;
    const err = new Error(message);
    err.code = code;
    err.status = resp.status;
    err.body = body;
    if (resp.status === 401) {
      // Auth lost — clear main chrome so we never keep stale data under overlay.
      store.clearSession();
      const region401 = document.getElementById("page-region");
      if (region401) region401.innerHTML = "";
      renderAuthOverlay();
    }
    throw err;
  }
  return body;
}

// PRD10 surface mapped onto a single api() helper. Domain clients are
// purposely thin so tests / consoles can drive the backend uniformly.
const A = {
  me: () => api("/me"),
  today: () => api("/today"),
  feed: (q = {}) => api(`/feed${qs(q)}`),

  capture: {
    text: (b) => api("/capture/text", { method: "POST", body: b }),
    link: (b) => api("/capture/link", { method: "POST", body: b }),
    presign: (b) => api("/uploads/presign", { method: "POST", body: b }),
    commit: (b) => api("/capture/file/commit", { method: "POST", body: b }),
  },

  inbox: {
    list: (q = {}) => api(`/inbox${qs(q)}`),
    patch: (id, b) =>
      api(`/inbox/${encodeURIComponent(id)}`, { method: "PATCH", body: b }),
  },

  cards: {
    get: (id) => api(`/cards/${encodeURIComponent(id)}`),
    create: (b) => api("/cards", { method: "POST", body: b }),
    update: (id, b) =>
      api(`/cards/${encodeURIComponent(id)}`, { method: "PATCH", body: b }),
    remove: (id) =>
      api(`/cards/${encodeURIComponent(id)}`, { method: "DELETE" }),
    favorite: (id, is_favorite = true) =>
      api(`/cards/${encodeURIComponent(id)}/favorite`, {
        method: "POST",
        body: { is_favorite },
      }),
  },

  kb: {
    overview: () => api("/kb/overview"),
    folders: (q = {}) => api(`/kb/folders${qs(q)}`),
    createFolder: (b) => api("/kb/folders", { method: "POST", body: b }),
    updateFolder: (id, b) =>
      api(`/kb/folders/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: b,
      }),
    deleteFolder: (id) =>
      api(`/kb/folders/${encodeURIComponent(id)}`, { method: "DELETE" }),
    documents: (q = {}) => api(`/kb/documents${qs(q)}`),
    document: (id) => api(`/kb/documents/${encodeURIComponent(id)}`),
    updateDocument: (id, b) =>
      api(`/kb/documents/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: b,
      }),
    deleteDocument: (id) =>
      api(`/kb/documents/${encodeURIComponent(id)}`, { method: "DELETE" }),
    moveDocument: (id, target_folder_id) =>
      api(`/kb/documents/${encodeURIComponent(id)}/move`, {
        method: "POST",
        body: { target_folder_id },
      }),
  },

  ai: {
    list: (q = {}) => api(`/ai/conversations${qs(q)}`),
    create: (b) => api("/ai/conversations", { method: "POST", body: b }),
    detail: (id) => api(`/ai/conversations/${encodeURIComponent(id)}`),
    send: (id, b) =>
      api(`/ai/conversations/${encodeURIComponent(id)}/messages`, {
        method: "POST",
        body: b,
      }),
    streamUrl: (id) =>
      `${API_BASE}/ai/conversations/${encodeURIComponent(id)}/messages/stream`,
    streamSendUrl: (id) =>
      `${API_BASE}/ai/conversations/${encodeURIComponent(id)}/messages/stream`,
    cancelMessage: (mid) =>
      api(`/ai/messages/${encodeURIComponent(mid)}/cancel`, { method: "POST" }),
    cancel: (mid) =>
      api(`/ai/messages/${encodeURIComponent(mid)}/cancel`, { method: "POST" }),
    regenerateMessage: (mid) =>
      api(`/ai/messages/${encodeURIComponent(mid)}/regenerate`, { method: "POST" }),
    regenerate: (mid) =>
      api(`/ai/messages/${encodeURIComponent(mid)}/regenerate`, { method: "POST" }),
    saveToKb: (mid, b) =>
      api(`/ai/messages/${encodeURIComponent(mid)}/save-to-kb`, {
        method: "POST",
        body: b,
      }),
    createTasks: (mid, b) =>
      api(`/ai/messages/${encodeURIComponent(mid)}/create-tasks`, {
        method: "POST",
        body: b,
      }),
  },

  tasks: {
    list: (q = {}) => api(`/tasks${qs(q)}`),
    create: (b) => api("/tasks", { method: "POST", body: b }),
    update: (id, b) =>
      api(`/tasks/${encodeURIComponent(id)}`, { method: "PATCH", body: b }),
    complete: (id) =>
      api(`/tasks/${encodeURIComponent(id)}/complete`, { method: "POST" }),
    remove: (id) =>
      api(`/tasks/${encodeURIComponent(id)}`, { method: "DELETE" }),
  },

  skills: {
    list: (q = {}) => api(`/skills${qs(q)}`),
    detail: (id) => api(`/skills/${encodeURIComponent(id)}`),
    run: (id, b) =>
      api(`/skills/${encodeURIComponent(id)}/run`, {
        method: "POST",
        body: b,
      }),
  },

  garden: {
    overview: () => api("/garden/overview"),
    graph: (q = {}) => api(`/garden/graph${qs(q)}`),
  },

  search: {
    query: (q, params = {}) => api(`/search${qs({ q, ...params })}`),
    suggestions: (q, limit = 8) => api(`/search/suggestions${qs({ q, limit })}`),
  },

  notifications: {
    unread: () => api("/notifications/unread-count"),
    list: (q = {}) => api(`/notifications${qs(q)}`),
    markRead: (id) =>
      api(`/notifications/${encodeURIComponent(id)}/read`, { method: "POST" }),
    readAll: () => api("/notifications/read-all", { method: "POST" }),
  },

  jobs: {
    get: (id) => api(`/jobs/${encodeURIComponent(id)}`),
    cancel: (id) =>
      api(`/jobs/${encodeURIComponent(id)}/cancel`, { method: "POST" }),
  },

  auth: {
    login: (username, password) =>
      api("/auth/login", { method: "POST", body: { username, password } }),
    register: (b) => api("/auth/register", { method: "POST", body: b }),
    demoStatus: () => api("/demo/status"),
    demoLogin: () => api("/demo/login", { method: "POST" }),
  },
};

function qs(obj) {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(obj || {})) {
    if (v == null || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => usp.append(k, x));
    else usp.set(k, String(v));
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

// ─────────────────────────────────────────────  Toast  ──────────────────

const TOAST_LIMIT = 5;
const TOAST_KINDS = new Set(["info", "success", "warning", "error"]);

function toast(msg, kind = "info", options = {}) {
  const stack = document.getElementById("toast-stack");
  if (!stack) return;
  const type = TOAST_KINDS.has(kind) ? kind : "info";
  stack.setAttribute("aria-live", type === "error" ? "assertive" : "polite");
  stack.setAttribute("aria-atomic", "false");
  const close = el(
    "button",
    {
      class: "toast-close",
      title: "关闭提示",
      "aria-label": "关闭提示",
      onclick: () => dismissToast(node),
    },
    [svg("close", 14)],
  );
  const node = el(
    "div",
    {
      class: `toast toast-${type}`,
      role: type === "error" ? "alert" : "status",
      "data-toast-kind": type,
    },
    [
      el("span", { class: "toast-mark", "aria-hidden": "true" }),
      el("span", { class: "toast-message", text: msg }),
      close,
    ],
  );
  stack.appendChild(node);
  while (stack.querySelectorAll(".toast").length > TOAST_LIMIT) {
    dismissToast(stack.querySelector(".toast"), { immediate: true });
  }
  const duration =
    options.duration == null ? 3200 : Number(options.duration);
  if (duration > 0) {
    node._toastTimer = setTimeout(() => dismissToast(node), duration);
  }
}

function dismissToast(node, { immediate = false } = {}) {
  if (!node || !node.isConnected) return;
  if (node._toastTimer) clearTimeout(node._toastTimer);
  if (immediate) {
    node.remove();
    return;
  }
  node.classList.add("is-leaving");
  setTimeout(() => node.remove(), 220);
}

window.showToast = toast; // keep prototype's API alive for tests

// ─────────────────────────────────────────────  State + events  ─────────

const state = {
  me: null,
  today: null,
  unread: 0,
  cache: {},
  feedSelection: new Set(),
};

const bus = new EventTarget();

function emit(event, detail) {
  bus.dispatchEvent(new CustomEvent(event, { detail }));
}
function on(event, fn) {
  bus.addEventListener(event, fn);
}

// ─────────────────────────────────────────────  Router  ─────────────────

const routes = [
  { match: /^#?\/?$/, page: "home" },
  { match: /^#?\/home$/, page: "home" },
  { match: /^#?\/kb$/, page: "kb" },
  { match: /^#?\/kb\/folder\/([^/]+)$/, page: "folder" },
  { match: /^#?\/kb\/doc\/([^/]+)$/, page: "doc" },
  { match: /^#?\/ai$/, page: "ai" },
  { match: /^#?\/ai\/([^/]+)$/, page: "ai" },
  { match: /^#?\/skills$/, page: "skills" },
  { match: /^#?\/garden$/, page: "garden" },
  { match: /^#?\/today$/, page: "today" },
  { match: /^#?\/tasks$/, page: "tasks" },
  { match: /^#?\/inbox$/, page: "inbox" },
];

function navigate(hash, replace = false) {
  if (replace) {
    history.replaceState(null, "", hash);
  } else {
    location.hash = hash;
  }
}

function currentRoute() {
  const hash = location.hash || "#/home";
  for (const r of routes) {
    const m = hash.match(r.match);
    if (m) return { ...r, args: m.slice(1), hash };
  }
  return { page: "home", args: [], hash };
}

function applyPageMode(route = currentRoute()) {
  document.documentElement.dataset.page = route.page || "home";
  syncOverlayState();
}

// ─────────────────────────────────────────────  Shell  ──────────────────

function renderShell() {
  const root = document.getElementById("app");
  root.innerHTML = "";
  root.removeAttribute("aria-busy");
  root.appendChild(
    el("div", { class: "mydow-app" }, [renderSidebar(), renderMain()]),
  );
}

function renderSidebar() {
  const me = state.me || {};
  const items = [
    { key: "home", label: t("nav.home", "灵感采集"), icon: "home", hash: "#/home" },
    { key: "today", label: t("nav.today", "Today"), icon: "clock", hash: "#/today" },
    { key: "inbox", label: t("nav.inbox", "Inbox"), icon: "spark", hash: "#/inbox" },
    { key: "kb", label: t("nav.kb", "知识库"), icon: "kb", hash: "#/kb" },
    { key: "garden", label: t("nav.garden", "数字花园"), icon: "garden", hash: "#/garden" },
    { key: "ai", label: t("nav.ai", "Mydow AI"), icon: "ai", hash: "#/ai" },
    { key: "skills", label: t("nav.skills", "Skills 广场"), icon: "skills", hash: "#/skills" },
  ];

  const route = currentRoute();
  const nav = el(
    "nav",
    { class: "nav", "aria-label": "主导航" },
    items.map((item) =>
      el(
        "div",
        {
          class:
            "nav-item" +
            (route.page === item.key ||
            (item.key === "kb" &&
              ["folder", "doc"].includes(route.page))
              ? " is-active"
              : ""),
          "data-nav": item.key,
          "aria-current":
            route.page === item.key ||
            (item.key === "kb" &&
              ["folder", "doc"].includes(route.page))
              ? "page"
              : null,
          onclick: () => navigate(item.hash),
          role: "button",
          tabindex: "0",
        },
        [svg(item.icon), el("span", { text: item.label })],
      ),
    ),
  );

  return el(
    "aside",
    { class: "sidebar", "aria-label": "Mydow 主导航" },
    [
      el("div", { class: "brand" }, [
        el("div", { class: "brand-mark" }, "M"),
        el("div", {}, "Mydow"),
      ]),
      nav,
      el("div", { class: "spacer" }),
      el(
        "div",
        { class: "sidebar-foot" },
        [
          el(
            "div",
            {
              class: "user-chip",
              onclick: () => openUserMenu(),
              role: "button",
              tabindex: "0",
            },
            [
              el(
                "div",
                { class: "avatar" },
                (me.username && me.username[0].toUpperCase()) || "M",
              ),
              el("div", { style: "min-width:0;flex:1;" }, [
                el(
                  "div",
                  { class: "user-chip-name" },
                  me.username || "未登录",
                ),
                el(
                  "div",
                  { class: "user-chip-mail" },
                  me.email || "demo 模式",
                ),
              ]),
            ],
          ),
        ],
      ),
    ],
  );
}

function renderMain() {
  return el("div", { class: "main", id: "main-region" }, [
    renderTopbar(),
    el("main", {
      class: "page",
      id: "page-region",
      tabindex: "-1",
      "aria-live": "polite",
    }),
  ]);
}

function renderTopbar() {
  const searchInput = el("input", {
    type: "text",
    placeholder: t("topbar.search", "搜索 Mydow（笔记、文档、AI 对话、Skill）..."),
    "aria-label": t("topbar.searchAria", "全局搜索"),
    onkeydown: (e) => {
      if (e.key === "Enter") openSearchPanel(e.currentTarget.value);
    },
    onfocus: () => openSearchPanel(""),
  });
  return el("div", { class: "topbar" }, [
    el(
      "div",
      {
        class: "search-box",
        onclick: (e) => {
          if (e.target.tagName !== "INPUT") {
            e.currentTarget.querySelector("input").focus();
          }
        },
      },
      [svg("search"), searchInput, el("span", { class: "kbd" }, "⌘ K")],
    ),
    el("div", { class: "spacer" }),
    el(
      "button",
      {
        class: "icon-btn theme-toggle",
        title: themeLabel(),
        "aria-label": themeLabel(),
        "data-theme-toggle": "",
        "data-theme-mode": store.theme(),
        onclick: () => cycleTheme(),
      },
      [svg(store.theme() === "dark" ? "moon" : "sun")],
    ),
    el(
      "button",
      {
        class: "icon-btn locale-toggle",
        title: t("locale.title", "切换到英文"),
        "aria-label": t("locale.title", "切换到英文"),
        "data-locale-toggle": "",
        "data-locale-mode": i18n.locale,
        onclick: () => setLocale(i18n.locale === "en" ? "zh" : "en"),
      },
      t("locale.toggle", "EN"),
    ),
    el(
      "button",
      {
        class: "icon-btn",
        title: t("topbar.notifications", "通知"),
        "aria-label": t("topbar.notifications", "通知"),
        onclick: () => openNotificationDrawer(),
      },
      [
        svg("bell"),
        state.unread > 0
          ? el(
              "span",
              { class: "badge-dot", id: "notif-badge" },
              String(state.unread),
            )
          : null,
      ],
    ),
  ]);
}

// ─────────────────────────────────────────────  Page renderers  ─────────

async function renderPage() {
  const region = document.getElementById("page-region");
  if (!region) return;
  if (!store.token()) {
    region.innerHTML = "";
    renderAuthOverlay();
    return;
  }
  region.innerHTML = "";
  const skel = skeletonPage();
  region.appendChild(skel);
  // Force browser to paint the skeleton before we kick off async fetches.
  await new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve)),
  );
  const route = currentRoute();
  applyPageMode(route);
  // Re-render sidebar so the active state updates when route changes.
  const oldSidebar = document.querySelector(".sidebar");
  if (oldSidebar) oldSidebar.replaceWith(renderSidebar());

  const page =
    route.page === "home"
      ? renderHome
      : route.page === "kb"
        ? renderKB
        : route.page === "folder"
          ? () => renderFolder(route.args[0])
          : route.page === "doc"
            ? () => renderDoc(route.args[0])
            : route.page === "ai"
              ? () => renderAi(route.args[0])
              : route.page === "skills"
                ? renderSkills
                : route.page === "garden"
                  ? renderGarden
                  : route.page === "today"
                    ? renderTodayPage
                    : route.page === "tasks"
                      ? renderTasksPage
                      : route.page === "inbox"
                        ? renderInboxPage
                        : renderHome;
  try {
    const node = await page();
    region.innerHTML = "";
    region.appendChild(node);
  } catch (e) {
    region.innerHTML = "";
    region.appendChild(errorState(e));
  }
}

function skeletonPage() {
  const wrap = el("div", {
    class: "state-card state-loading",
    role: "status",
    "aria-live": "polite",
    "aria-label": "正在加载",
  });
  wrap.appendChild(el("div", { class: "skeleton skeleton-line", style: "width:30%;height:24px;" }));
  for (let i = 0; i < 6; i++) {
    wrap.appendChild(el("div", { class: "skeleton skeleton-card" }));
  }
  return wrap;
}

function stateCard(type, { icon = "spark", title, hint, detail, action } = {}) {
  const role = type === "error" || type === "forbidden" ? "alert" : "status";
  return el("div", { class: `state-card state-${type} ${type}-state`, role }, [
    stateIllustration(icon || type),
    title ? el("h3", { text: title }) : null,
    hint ? el("p", { text: hint }) : null,
    detail ? el("div", { class: "state-detail", text: detail }) : null,
    action,
  ]);
}

function emptyState({ icon = "spark", title, hint, action } = {}) {
  return stateCard("empty", { icon, title, hint, action });
}

function stateIllustration(kind = "spark") {
  const normalized = {
    star: "spark",
    check: "task",
    clock: "task",
    close: "error",
    kb: "folder",
  }[kind] || kind;
  const node = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  node.setAttribute("class", `state-visual-svg state-visual-${normalized}`);
  node.setAttribute("viewBox", "0 0 160 112");
  node.setAttribute("aria-hidden", "true");
  node.setAttribute("focusable", "false");
  const templates = {
    spark: `
      <path class="state-visual-surface" d="M36 84h88a10 10 0 0 0 10-10V34a10 10 0 0 0-10-10H36a10 10 0 0 0-10 10v40a10 10 0 0 0 10 10Z"/>
      <path class="state-visual-line" d="M46 43h42M46 57h68M46 71h34"/>
      <path class="state-visual-accent" d="m116 39 5 10 10 5-10 5-5 10-5-10-10-5 10-5 5-10Z"/>
      <circle class="state-visual-dot" cx="38" cy="28" r="4"/>
    `,
    folder: `
      <path class="state-visual-surface" d="M24 42h112v36a12 12 0 0 1-12 12H36a12 12 0 0 1-12-12V42Z"/>
      <path class="state-visual-accent" d="M24 42V32a10 10 0 0 1 10-10h28l12 14h52a10 10 0 0 1 10 10v8H24Z"/>
      <path class="state-visual-line" d="M46 62h68M46 74h42"/>
      <circle class="state-visual-dot" cx="120" cy="72" r="5"/>
    `,
    doc: `
      <path class="state-visual-surface" d="M48 18h48l24 24v52H48V18Z"/>
      <path class="state-visual-accent" d="M96 18v24h24"/>
      <path class="state-visual-line" d="M62 56h42M62 68h36M62 80h26"/>
      <path class="state-visual-dot" d="M34 76h14v14H34z"/>
    `,
    ai: `
      <path class="state-visual-surface" d="M40 34h80a16 16 0 0 1 16 16v24a16 16 0 0 1-16 16H56L40 102V90a16 16 0 0 1-16-16V50a16 16 0 0 1 16-16Z"/>
      <circle class="state-visual-accent" cx="61" cy="62" r="7"/>
      <circle class="state-visual-accent" cx="80" cy="62" r="7"/>
      <circle class="state-visual-accent" cx="99" cy="62" r="7"/>
      <path class="state-visual-line" d="M54 28V16M106 28V16"/>
    `,
    bell: `
      <path class="state-visual-surface" d="M52 76h56l-8-10V50a20 20 0 0 0-40 0v16l-8 10Z"/>
      <path class="state-visual-accent" d="M72 84a9 9 0 0 0 16 0"/>
      <path class="state-visual-line" d="M40 44c5-13 16-23 30-27M120 44c-5-13-16-23-30-27"/>
      <circle class="state-visual-dot" cx="120" cy="28" r="5"/>
    `,
    search: `
      <circle class="state-visual-surface" cx="70" cy="52" r="28"/>
      <path class="state-visual-accent" d="m91 73 28 28"/>
      <path class="state-visual-line" d="M55 48h32M55 60h20"/>
      <circle class="state-visual-dot" cx="116" cy="31" r="5"/>
    `,
    task: `
      <path class="state-visual-surface" d="M44 22h72a10 10 0 0 1 10 10v58H34V32a10 10 0 0 1 10-10Z"/>
      <path class="state-visual-line" d="M58 48h44M58 64h44M58 80h26"/>
      <path class="state-visual-accent" d="m48 47 5 5 10-12M48 63l5 5 10-12"/>
      <circle class="state-visual-dot" cx="116" cy="84" r="5"/>
    `,
    skills: `
      <path class="state-visual-surface" d="M46 28h28v28H46zM86 28h28v28H86zM46 68h28v28H46zM86 68h28v28H86z"/>
      <path class="state-visual-accent" d="M60 36v12M54 42h12M100 76v12M94 82h12"/>
      <path class="state-visual-line" d="M94 42h12M54 82h12"/>
    `,
    error: `
      <path class="state-visual-surface" d="M80 18 136 92H24L80 18Z"/>
      <path class="state-visual-accent" d="M80 44v24"/>
      <circle class="state-visual-dot" cx="80" cy="80" r="4"/>
    `,
  };
  node.innerHTML = templates[normalized] || templates.spark;
  return el("div", { class: `state-illustration state-illustration-${normalized}` }, node);
}

function forbiddenState(err) {
  const msg = (err && err.message) || "当前账号没有权限访问这个内容";
  return stateCard("forbidden", {
    icon: "close",
    title: "没有访问权限",
    hint: msg,
    detail: "请确认账号、工作区或分享权限后重试。",
  });
}

function errorState(err) {
  if (err && (err.status === 403 || err.code === "FORBIDDEN")) {
    return forbiddenState(err);
  }
  const readableMsg = (err && err.message) || "请求失败";
  return stateCard("error", {
    icon: "close",
    title: "出错了",
    hint: readableMsg,
    detail: "请检查后端服务、网络连接或稍后重试。",
  });
  const msg = (err && err.message) || "请求失败";
  return el("div", { class: "error-state" }, [
    svg("close"),
    el("div", {}, [
      el("strong", { text: "出错了" }),
      el("br"),
      el("span", { text: `${msg}（请检查后端是否启动 / 网络是否通畅）` }),
    ]),
  ]);
}

// ─────────────────────────────────────────────  Page: Home  ─────────────

function processingState({ title = "正在处理", hint = "任务已提交，完成后会同步更新。", action } = {}) {
  return stateCard("processing", { icon: "clock", title, hint, action });
}

function successState({ title = "已完成", hint = "操作已经保存。", action } = {}) {
  return stateCard("success", { icon: "check", title, hint, action });
}

async function renderHome() {
  const [todayResp, feedResp, insightResp] = await Promise.allSettled([
    A.today(),
    A.feed({ page_size: 12 }),
    A.notifications.unread().catch(() => null),
  ]);

  const today =
    todayResp.status === "fulfilled" ? todayResp.value.data : null;
  const feed =
    feedResp.status === "fulfilled" ? feedResp.value.data : null;

  const wrap = el("div", { class: "fade-in" });
  const displayName =
    today && today.user
      ? today.user.name || today.user.username || "Mydow 用户"
      : "";
  wrap.appendChild(
    el("div", { class: "page-head" }, [
      el(
        "h1",
        {},
        displayName
          ? `${t("home.greetingPrefix", "你好，")}${displayName}`
          : t("home.greetingFallback", "有想法，记下来"),
      ),
      el(
        "p",
        { class: "subtitle" },
        t("home.subtitle", "捕捉每一个闪现的灵感，AI 帮你整理成知识。"),
      ),
    ]),
  );

  // Capture box.
  const textarea = el("textarea", {
    placeholder: t("home.capturePlaceholder", "现在的想法或感悟，记录下来..."),
    rows: "3",
  });
  const submitBtn = el(
    "button",
    {
      class: "btn btn-primary",
      onclick: async () => {
        const content = textarea.value.trim();
        if (!content) return toast("请先输入想法", "error");
        submitBtn.disabled = true;
        try {
          await A.capture.text({ content, auto_process: true });
          textarea.value = "";
          toast("已记录到 Inbox，AI 正在整理", "success");
          await refreshHome();
        } catch (e) {
          toast(`保存失败: ${e.message}`, "error");
        } finally {
          submitBtn.disabled = false;
        }
      },
    },
    [svg("send", 16), t("home.submit", "提交")],
  );

  const captureBox = el("div", { class: "capture-box" }, [
    textarea,
    el("div", { class: "capture-actions" }, [
      el("div", { class: "capture-tools" }, [
        el(
          "button",
          {
            class: "btn-icon",
            title: "添加图片或文件",
            onclick: () => openUploadModal(),
          },
          [svg("upload", 16)],
        ),
        el(
          "button",
          {
            class: "btn-icon",
            title: "网页剪藏",
            onclick: () => openClipModal(),
          },
          [svg("link", 16)],
        ),
        el(
          "button",
          {
            class: "btn-icon",
            title: "语音输入（占位）",
            onclick: () => {
              toast("当前为 V1，语音输入会在 P1 开放", "info");
            },
          },
          [svg("mic", 16)],
        ),
      ]),
      submitBtn,
    ]),
  ]);

  // Quick actions.
  const quick = el("div", { class: "quick-actions" }, [
    quickAction("upload", t("home.upload", "上传文件"), () => openUploadModal()),
    quickAction("link", t("home.webClip", "网页剪藏"), () => openClipModal()),
    quickAction("mic", t("home.voice", "语音输入"), () => toast("V1 暂未开放语音", "info")),
    quickAction("spark", t("home.deepResearch", "深度研究"), () => openDeepResearchModal()),
  ]);

  // Stats panel.
  const sidePanel = renderHomeSidePanel(today);

  const apiErrBanner = el("div", { class: "home-api-errors", style: "margin-bottom:12px;" });
  if (todayResp.status === "rejected") {
    const e = todayResp.reason;
    if (!(e && e.status === 401))
      apiErrBanner.appendChild(
        el("div", {}, [
          el("div", { class: "muted", style: "font-size:12px;margin-bottom:4px;" }, "今日数据加载失败"),
          errorState(e),
        ]),
      );
  }
  if (feedResp.status === "rejected") {
    const e = feedResp.reason;
    if (!(e && e.status === 401))
      apiErrBanner.appendChild(
        el("div", {}, [
          el("div", { class: "muted", style: "font-size:12px;margin-bottom:4px;" }, "灵感流加载失败"),
          errorState(e),
        ]),
      );
  }

  // Feed grid + facet filters.
  const facets = (feed && feed.facets) || { types: [], tags: [] };
  const feedListHost = el("div", {});
  const refreshFeed = async (filter = {}) => {
    feedListHost.innerHTML = "";
    feedListHost.appendChild(skeletonPage());
    try {
      const r = await A.feed({ page_size: 12, ...filter });
      const items = (r.data && r.data.items) || [];
      feedListHost.innerHTML = "";
      if (!items.length) {
        feedListHost.appendChild(
          emptyState({
            title: t("empty.noMatchIdeas.title", "没有匹配的灵感"),
            hint: t("empty.noMatchIdeas.hint", "试试切换其他类型或清除筛选。"),
          }),
        );
      } else {
        feedListHost.appendChild(renderFeedGrid(items));
      }
    } catch (e) {
      feedListHost.innerHTML = "";
      feedListHost.appendChild(errorState(e));
    }
  };

  const filterRow = el(
    "div",
    {
      class: "row",
      style: "flex-wrap:wrap;gap:6px;margin:10px 0 4px;",
    },
    [
      el(
        "button",
        {
          class: "btn btn-sm btn-primary",
          "data-feed-filter": "all",
          onclick: (e) => {
            filterRow
              .querySelectorAll("button")
              .forEach((b) => b.classList.remove("btn-primary"));
            e.currentTarget.classList.add("btn-primary");
            refreshFeed();
          },
        },
        t("kb.all", "全部"),
      ),
      ...(facets.types || []).map((f) =>
        el(
          "button",
          {
            class: "btn btn-sm",
            onclick: (e) => {
              filterRow
                .querySelectorAll("button")
                .forEach((b) => b.classList.remove("btn-primary"));
              e.currentTarget.classList.add("btn-primary");
              refreshFeed({ type: f.value });
            },
          },
          [
            el("span", { text: f.label || f.value }),
            el("span", { class: "muted", style: "margin-left:6px;font-size:11px;" }, `${f.count}`),
          ],
        ),
      ),
    ],
  );

  let feedInitial;
  if (feedResp.status === "rejected" && !(feedResp.reason && feedResp.reason.status === 401)) {
    feedInitial = errorState(feedResp.reason);
  } else if (feed && feed.items && feed.items.length) {
    feedListHost.appendChild(renderFeedGrid(feed.items));
    feedInitial = feedListHost;
  } else {
    feedInitial = emptyState({
      title: t("empty.noIdeas.title", "还没有灵感"),
      hint: t("empty.noIdeas.hint", "上面的输入区写下第一条想法，回车提交。"),
    });
  }

  const feedSection = el("section", {}, [
    el("div", { class: "section-title" }, [
      el("h2", { style: "font-size:16px;font-weight:700;" }, t("home.recentIdeas", "最近的灵感")),
      el(
        "button",
        {
          class: "btn btn-ghost btn-sm",
          onclick: () => navigate("#/kb"),
        },
        t("home.viewAll", "查看全部"),
      ),
    ]),
    facets.types && facets.types.length ? filterRow : null,
    feedInitial,
  ]);

  const mainBlocks = [captureBox, quick];
  if (apiErrBanner.childNodes.length) mainBlocks.unshift(apiErrBanner);
  const main = el("div", {}, [...mainBlocks, feedSection]);
  wrap.appendChild(el("div", { class: "home-grid" }, [main, sidePanel]));
  return wrap;
}

function quickAction(icon, label, onclick) {
  return el(
    "button",
    { class: "quick-action", onclick: () => onclick() },
    [svg(icon), el("span", { text: label })],
  );
}

function renderFeedGrid(items) {
  const selected = state.feedSelection || new Set();
  state.feedSelection = selected;
  const countLabel = el("span", { class: "muted", text: "" });
  const archiveBtn = el(
    "button",
    {
      class: "btn btn-primary btn-sm",
      onclick: async () => {
        const ids = Array.from(selected);
        if (!ids.length) return;
        archiveBtn.disabled = true;
        try {
          await Promise.all(ids.map((id) => A.cards.update(id, { is_archived: true })));
          selected.clear();
          toast(`已归档 ${ids.length} 条灵感`, "success");
          await refreshHome();
        } catch (e) {
          toast(`归档失败: ${e.message}`, "error");
        } finally {
          archiveBtn.disabled = false;
        }
      },
    },
    [svg("folder", 14), "归档选中"],
  );
  const clearBtn = el(
    "button",
    {
      class: "btn btn-sm",
      onclick: () => {
        selected.clear();
        document
          .querySelectorAll(".feed-select input")
          .forEach((input) => (input.checked = false));
        updateFeedSelectionToolbar(toolbar, selected, countLabel);
      },
    },
    "清除选择",
  );
  const toolbar = el(
    "div",
    { class: "feed-selection-toolbar", hidden: selected.size === 0 },
    [countLabel, archiveBtn, clearBtn],
  );
  const list = el(
    "div",
    { class: "feed-list" },
    items.map((it) => {
      const checked = selected.has(it.id);
      const checkbox = el("input", {
        type: "checkbox",
        checked,
        "aria-label": `选择 ${it.title || "灵感"}`,
        onchange: (e) => {
          e.stopPropagation();
          if (e.currentTarget.checked) selected.add(it.id);
          else selected.delete(it.id);
          updateFeedSelectionToolbar(toolbar, selected, countLabel);
        },
        onclick: (e) => e.stopPropagation(),
      });
      return el(
        "article",
        {
          class: "feed-card" + (checked ? " is-selected" : ""),
          onclick: () => openCardDrawer(it.id),
        },
        [
          el("label", { class: "feed-select", onclick: (e) => e.stopPropagation() }, [
            checkbox,
            el("span", { text: "选择" }),
          ]),
          el("h3", { class: "feed-title", text: it.title || "未命名" }),
          el("p", { class: "feed-summary", text: it.summary || "" }),
          el("div", { class: "feed-tags" }, (it.tags || []).slice(0, 3).map((t) => el("span", { class: "tag", text: t }))),
          el("div", { class: "feed-meta" }, [
            el("span", { text: it.content_type || "note" }),
            el("span", { text: relTime(it.created_at) }),
          ]),
        ],
      );
    }),
  );
  updateFeedSelectionToolbar(toolbar, selected, countLabel);
  return el("div", { class: "feed-multiselect" }, [toolbar, list]);
}

function updateFeedSelectionToolbar(toolbar, selected, countLabel) {
  const count = selected.size;
  toolbar.hidden = count === 0;
  countLabel.textContent = count ? `已选择 ${count} 条` : "";
}

function renderHomeSidePanel(today) {
  const stats = (today && today.stats) || {};
  const tasks = (today && today.tasks) || [];
  const insightPreview = (today && today.insight_preview) || {};
  return el("aside", { class: "side-panel" }, [
    el("h2", { class: "section-title", style: "margin-bottom:12px;" }, "今日概览"),
    el("div", { class: "stat-grid" }, [
      statCard("今日捕捉", stats.today_capture_count ?? 0),
      statCard("待办任务", stats.pending_task_count ?? 0),
      statCard("知识条目", stats.knowledge_items_count ?? 0),
      statCard(
        "周增长",
        `${Math.round((stats.weekly_growth_rate ?? 0) * 100)}%`,
      ),
    ]),
    el("div", { style: "background:var(--bg-tint);border-radius:8px;padding:14px 16px;margin-top:8px;" }, [
      el("div", { style: "font-size:12px;color:var(--text-muted);margin-bottom:4px;" }, "AI 洞察"),
      el(
        "div",
        { style: "font-weight:600;font-size:14px;" },
        insightPreview.title || "继续记录会让我们生成你的第一条洞察",
      ),
      el(
        "div",
        { style: "color:var(--text-soft);font-size:12px;margin-top:4px;" },
        insightPreview.summary || "AI 会根据你近期捕捉的内容生成主题趋势和建议。",
      ),
    ]),
    tasks.length > 0
      ? el("div", { style: "margin-top:14px;" }, [
          el("div", { class: "section-title", style: "font-size:13px;margin-bottom:8px;" }, "待办任务"),
          ...tasks.slice(0, 4).map((t) =>
            el("div", { class: "row", style: "padding:6px 0;font-size:13px;" }, [
              svg("clock", 14),
              el("div", { style: "flex:1;" }, t.title || "未命名"),
              el("span", { class: "muted", text: relTime(t.due_at) }),
            ]),
          ),
        ])
      : null,
  ]);
}

function statCard(label, value) {
  return el("div", { class: "stat-card" }, [
    el("div", { class: "stat-num", text: String(value) }),
    el("div", { class: "stat-label", text: label }),
  ]);
}

async function refreshHome() {
  if (currentRoute().page === "home") {
    const region = document.getElementById("page-region");
    region.innerHTML = "";
    region.appendChild(await renderHome());
  }
  refreshUnread();
}

// ─────────────────────────────────────────────  Page: KB overview  ──────

async function renderKB() {
  const [foldersResp, overviewResp] = await Promise.allSettled([
    A.kb.folders({ include_counts: true }),
    A.kb.overview(),
  ]);
  const initialFolders =
    foldersResp.status === "fulfilled"
      ? foldersResp.value.data.items || []
      : [];
  const overview =
    overviewResp.status === "fulfilled" ? overviewResp.value.data : null;

  const gridHost = el("div", { class: "kb-grid-host" });
  let folderList = initialFolders;
  let listMode = "all";

  const search = el("input", {
    type: "text",
    placeholder: t("kb.searchFolders", "搜索文件夹..."),
    "aria-label": t("kb.searchFolders", "搜索文件夹"),
    style:
      "padding:6px 12px;border:1px solid var(--border);border-radius:8px;outline:none;width:240px;",
  });

  const filterRow = el("div", { class: "row" });

  const syncTabHighlight = (mode) => {
    const map = { all: 0, favorite: 1, recent: 2 };
    const idx = map[mode];
    filterRow.querySelectorAll("button").forEach((b, i) => {
      b.classList.toggle("btn-primary", i === idx);
    });
  };

  const paintFolderGrid = () => {
    gridHost.innerHTML = "";
    const q = search.value.trim().toLowerCase();
    const base = folderList;
    const shown = q
      ? base.filter((f) => (f.name || "").toLowerCase().includes(q))
      : base;

    if (!shown.length) {
      if (!base.length && listMode === "all") {
        gridHost.appendChild(
          emptyState({
            icon: "folder",
            title: t("empty.noFolders.title", "还没有文件夹"),
            hint: t("empty.noFolders.hint", "点击右上角「新建文件夹」开始整理你的知识。"),
            action: el(
              "button",
              {
                class: "btn btn-primary",
                style: "margin-top:18px;",
                onclick: () => openCreateFolderModal(),
              },
              [svg("plus", 16), t("kb.newFolder", "新建文件夹")],
            ),
          }),
        );
        return;
      }
      if (!base.length && listMode === "favorite") {
        gridHost.appendChild(
          emptyState({
            icon: "star",
            title: t("empty.noFavoriteFolders.title", "暂无收藏文件夹"),
            hint: "在文件夹卡片左上角点击星标，即可在这里快速找到它们。",
            action: el(
              "button",
              {
                class: "btn btn-primary",
                style: "margin-top:14px;",
                onclick: async () => {
                  await reloadFolderList("all");
                },
              },
              "返回全部",
            ),
          }),
        );
        return;
      }
      if (!base.length && listMode === "recent") {
        gridHost.appendChild(
          emptyState({
            icon: "clock",
            title: t("empty.noRecentFolders.title", "暂无文件夹"),
            hint: "请先创建文件夹，「最近」会按更新时间排序展示。",
          }),
        );
        return;
      }
      gridHost.appendChild(
        emptyState({
          title: t("empty.noFolderMatch.title", "没有匹配的文件夹"),
          hint: "换一个关键词试试，或清空搜索框查看当前筛选下的全部文件夹。",
        }),
      );
      return;
    }
    gridHost.appendChild(renderKBGrid(shown));
  };

  const reloadFolderList = async (mode) => {
    listMode = mode;
    syncTabHighlight(mode);
    const params = { include_counts: true };
    if (mode === "favorite") params.is_favorite = true;
    if (mode === "recent") params.sort_by = "updated_at";
    gridHost.innerHTML = "";
    gridHost.appendChild(skeletonPage());
    try {
      const r = await A.kb.folders(params);
      folderList = r.data.items || [];
    } catch (e) {
      gridHost.innerHTML = "";
      gridHost.appendChild(errorState(e));
      return;
    }
    paintFolderGrid();
  };

  filterRow.appendChild(
    el(
      "button",
      {
        class: "btn btn-sm btn-primary",
        onclick: () => reloadFolderList("all"),
      },
      t("kb.all", "全部"),
    ),
  );
  filterRow.appendChild(
    el(
      "button",
      {
        class: "btn btn-sm",
        onclick: () => reloadFolderList("favorite"),
      },
      [svg("star", 14), t("kb.favorite", "收藏")],
    ),
  );
  filterRow.appendChild(
    el(
      "button",
      {
        class: "btn btn-sm",
        onclick: () => reloadFolderList("recent"),
      },
      [svg("clock", 14), t("kb.recent", "最近")],
    ),
  );

  search.addEventListener(
    "input",
    debounce(() => {
      paintFolderGrid();
    }, 200),
  );

  const toolbar = el("div", { class: "row-spread" }, [
    el("div", { class: "row" }, [filterRow, search]),
    el(
      "button",
      {
        class: "btn btn-primary",
        onclick: () => openCreateFolderModal(),
      },
      [svg("plus", 16), t("kb.newFolder", "新建文件夹")],
    ),
  ]);

  syncTabHighlight("all");
  paintFolderGrid();

  return el("div", { class: "fade-in" }, [
    el("div", { class: "page-head" }, [
      el("h1", {}, t("kb.title", "知识库")),
      el(
        "p",
        { class: "subtitle" },
        overview
          ? `${overview.stats.folder_count} 个文件夹，${overview.stats.document_count} 篇文档，${overview.stats.favorite_count} 个收藏。`
          : "整理、沉淀和复用你的知识资产。",
      ),
    ]),
    toolbar,
    gridHost,
  ]);
}

function renderKBGrid(folders) {
  return el(
    "div",
    { class: "kb-grid" },
    folders.map((f) =>
      el(
        "div",
        {
          class: "kb-folder",
          onclick: () => navigate(`#/kb/folder/${f.id}`),
          ondragover: (e) => {
            if (e.dataTransfer.types.includes("application/x-mydow-document")) {
              e.preventDefault();
              e.currentTarget.classList.add("drag-over");
            }
          },
          ondragleave: (e) => e.currentTarget.classList.remove("drag-over"),
          ondrop: async (e) => {
            const docId = e.dataTransfer.getData("application/x-mydow-document");
            if (!docId) return;
            e.preventDefault();
            e.stopPropagation();
            e.currentTarget.classList.remove("drag-over");
            try {
              await A.kb.moveDocument(docId, f.id);
              toast(`已移动到「${f.name}」`, "success");
              renderPage();
            } catch (err) {
              toast(`移动失败: ${err.message}`, "error");
            }
          },
        },
        [
          el(
            "button",
            {
              class: "star-btn" + (f.is_favorite ? " is-on" : ""),
              title: f.is_favorite ? "取消收藏" : "收藏",
              onclick: async (e) => {
                e.stopPropagation();
                const r = await A.kb.updateFolder(f.id, {
                  is_favorite: !f.is_favorite,
                });
                f.is_favorite = !!(r && r.data && r.data.is_favorite);
                e.currentTarget.classList.toggle("is-on", f.is_favorite);
                toast(f.is_favorite ? "已收藏" : "已取消收藏", "success");
              },
            },
            [svg("star", 18)],
          ),
          el("div", { class: "folder-icon" }, [svg("folder", 22)]),
          el("h3", { text: f.name }),
          el(
            "div",
            { class: "folder-meta" },
            `${f.document_count ?? 0} 篇文档 · ${f.card_count ?? 0} 张卡片`,
          ),
        ],
      ),
    ),
  );
}

async function refreshKBSection() {
  const region = document.getElementById("page-region");
  region.innerHTML = "";
  region.appendChild(await renderKB());
}

// ─────────────────────────────────────────────  Page: Folder detail  ───

async function renderFolder(folderId) {
  let folder, docs;
  try {
    const [foldersResp, docsResp] = await Promise.all([
      A.kb.folders({ include_counts: "true" }),
      A.kb.documents({ folder_id: folderId, page_size: 50 }),
    ]);
    folder = (foldersResp.data.items || []).find((f) => f.id === folderId);
    docs = docsResp.data.items || [];
  } catch (e) {
    return errorState(e);
  }
  if (!folder) {
    return emptyState({
      title: "文件夹不存在",
      hint: "可能已被删除。",
      action: el(
        "button",
        {
          class: "btn btn-primary",
          onclick: () => navigate("#/kb"),
        },
        [svg("back", 16), "返回知识库"],
      ),
    });
  }

  const wrap = el("div", { class: "fade-in" });
  wrap.appendChild(
    el("div", { class: "breadcrumb" }, [
      el(
        "span",
        {
          class: "crumb",
          onclick: () => navigate("#/kb"),
          text: "知识库",
        },
      ),
      el("span", { class: "crumb-sep", text: "/" }),
      el("span", { class: "crumb-current", text: folder.name }),
    ]),
  );

  wrap.appendChild(
    el("div", { class: "row-spread page-head" }, [
      el("div", {}, [
        el("h1", { text: folder.name }),
        el(
          "p",
          { class: "subtitle" },
          folder.description || `${docs.length} 篇文档`,
        ),
      ]),
      el("div", { class: "row" }, [
        el(
          "button",
          {
            class: "btn",
            onclick: () => openRenameFolderModal(folder),
          },
          [svg("edit", 16), "重命名"],
        ),
        el(
          "button",
          {
            class: "btn btn-danger",
            onclick: () => confirmDeleteFolder(folder),
          },
          [svg("trash", 16), "删除"],
        ),
        el(
          "button",
          {
            class: "btn btn-primary",
            onclick: () => openUploadModal(folder.id),
          },
          [svg("plus", 16), "新建文档"],
        ),
      ]),
    ]),
  );

  if (docs.length === 0) {
    wrap.appendChild(
      emptyState({
        icon: "doc",
        title: "文件夹是空的",
        hint: "上传文件或创建一个文档来填充这个文件夹。",
        action: el(
          "button",
          {
            class: "btn btn-primary",
            style: "margin-top:18px;",
            onclick: () => openUploadModal(folder.id),
          },
          [svg("upload", 16), "上传文件"],
        ),
      }),
    );
  } else {
    wrap.appendChild(
      el(
        "div",
        { class: "doc-table" },
        docs.map((d) =>
          el(
            "div",
            {
              class: "doc-row",
              draggable: "true",
              ondragstart: (e) => {
                e.dataTransfer.setData("application/x-mydow-document", d.id);
                e.dataTransfer.effectAllowed = "move";
                e.currentTarget.classList.add("is-dragging");
              },
              ondragend: (e) => e.currentTarget.classList.remove("is-dragging"),
              onclick: () => navigate(`#/kb/doc/${d.id}`),
            },
            [
              svg("doc", 20),
              el("div", { style: "min-width:0;" }, [
                el("div", { class: "doc-title", text: d.title || "未命名" }),
                el("div", { class: "doc-summary", text: d.summary || "" }),
              ]),
              el("div", { class: "muted", text: d.document_type || "note" }),
              el("div", { class: "muted", text: relTime(d.updated_at) }),
              el(
                "button",
                {
                  class: "btn-icon",
                  onclick: (e) => {
                    e.stopPropagation();
                    openCardDocActions(d, folder);
                  },
                },
                [svg("more", 18)],
              ),
            ],
          ),
        ),
      ),
    );
  }
  return wrap;
}

// ─────────────────────────────────────────────  Page: Document detail  ─

async function renderDoc(docId) {
  let doc;
  try {
    doc = (await A.kb.document(docId)).data;
  } catch (e) {
    return errorState(e);
  }
  const wrap = el("div", { class: "fade-in" });
  wrap.appendChild(
    el("div", { class: "breadcrumb" }, [
      el("span", { class: "crumb", onclick: () => navigate("#/kb"), text: "知识库" }),
      el("span", { class: "crumb-sep", text: "/" }),
      doc.folder
        ? el(
            "span",
            {
              class: "crumb",
              onclick: () => navigate(`#/kb/folder/${doc.folder.id}`),
              text: doc.folder.name,
            },
          )
        : el("span", { class: "muted", text: "(根目录)" }),
      el("span", { class: "crumb-sep", text: "/" }),
      el("span", { class: "crumb-current", text: doc.title }),
    ]),
  );

  wrap.appendChild(
    el("div", { class: "row-spread page-head" }, [
      el("div", {}, [
        el("h1", { text: doc.title || "未命名" }),
        el("p", { class: "subtitle", text: doc.summary || "—" }),
      ]),
      el("div", { class: "row" }, [
        el(
          "button",
          {
            class: "btn",
            onclick: () => openEditDocModal(doc),
          },
          [svg("edit", 16), "编辑"],
        ),
        el(
          "button",
          {
            class: "btn",
            onclick: () => openMoveDocModal(doc),
          },
          [svg("folder", 16), "移动"],
        ),
        el(
          "button",
          {
            class: "btn",
            onclick: async () => {
              const r = await A.kb.updateDocument(doc.id, {
                is_favorite: !doc.is_favorite,
              });
              doc.is_favorite = !!(r && r.data && r.data.is_favorite);
              toast(
                doc.is_favorite ? "已收藏" : "已取消收藏",
                "success",
              );
              renderPage();
            },
          },
          [
            svg("star", 16),
            doc.is_favorite ? "已收藏" : "收藏",
          ],
        ),
        el(
          "button",
          {
            class: "btn btn-danger",
            onclick: async () => {
              if (!confirm(`确认删除「${doc.title}」？`)) return;
              await A.kb.deleteDocument(doc.id);
              toast("已删除", "success");
              navigate(doc.folder_id ? `#/kb/folder/${doc.folder_id}` : "#/kb");
            },
          },
          [svg("trash", 16), "删除"],
        ),
      ]),
    ]),
  );

  // Tags row.
  if (doc.tags && doc.tags.length) {
    wrap.appendChild(
      el(
        "div",
        { class: "row", style: "margin-bottom:18px;flex-wrap:wrap;gap:6px;" },
        doc.tags.map((t) => el("span", { class: "tag", text: t })),
      ),
    );
  }

  // Body.
  wrap.appendChild(
    el(
      "div",
      {
        class: "card card-pad",
        style: "white-space:pre-wrap;line-height:1.85;",
      },
      [
        el("strong", { style: "font-size:13px;color:var(--text-muted);", text: "正文" }),
        el("br"),
        el("br"),
        el("div", { text: doc.content || "（暂无正文，将在 worker 解析完成后填入）" }),
      ],
    ),
  );

  // Source + chunks preview.
  const lower = el("div", { style: "display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:18px;" });
  if (doc.source) {
    lower.appendChild(
      el(
        "div",
        { class: "card card-pad" },
        [
          el("strong", { style: "color:var(--text-muted);font-size:13px;", text: "来源" }),
          el("br"),
          el("br"),
          el("div", {}, doc.source.name || doc.source.url || "—"),
          doc.source.url
            ? el(
                "a",
                {
                  href: doc.source.url,
                  target: "_blank",
                  style: "font-size:12px;color:var(--primary);",
                  text: "打开原始来源 →",
                },
              )
            : null,
        ],
      ),
    );
  }
  if (doc.chunks_preview && doc.chunks_preview.length) {
    lower.appendChild(
      el(
        "div",
        { class: "card card-pad" },
        [
          el("strong", { style: "color:var(--text-muted);font-size:13px;", text: "分块预览" }),
          el("br"),
          el("br"),
          ...doc.chunks_preview.slice(0, 3).map((c) =>
            el("div", { style: "font-size:12px;color:var(--text-soft);margin-bottom:8px;" }, c.content || ""),
          ),
        ],
      ),
    );
  }
  wrap.appendChild(lower);

  return wrap;
}

// ─────────────────────────────────────────────  Page: AI  ───────────────

async function renderAi(convId) {
  let convs = [];
  try {
    const r = await A.ai.list({ page_size: 30 });
    convs = (r.data && r.data.items) || [];
  } catch (e) {
    return errorState(e);
  }

  // Pick conversation: explicit param > first existing > create one.
  let activeId = convId;
  if (!activeId && convs.length) activeId = convs[0].id;
  const createNewConversation = async () => {
    const r = await A.ai.create({ title: t("ai.newConversation", "新对话"), mode: "general" });
    navigate(`#/ai/${r.data.id}`);
  };

  const wrap = el("div", { class: "ai-layout fade-in" });

  const list = el("div", { class: "ai-conv-list" });
  list.appendChild(
    el(
      "div",
      {
        class: "new-conv",
        onclick: createNewConversation,
      },
      [svg("plus", 16), t("ai.newConversation", "新对话")],
    ),
  );
  for (const c of convs) {
    list.appendChild(
      el(
        "div",
        {
          class: "conv-item" + (c.id === activeId ? " is-active" : ""),
          onclick: () => navigate(`#/ai/${c.id}`),
        },
        [
          el("div", { class: "conv-title", text: c.title || "未命名" }),
          c.last_message_preview
            ? el(
                "div",
                {
                  class: "conv-preview",
                  text: c.last_message_preview,
                },
              )
            : null,
        ],
      ),
    );
  }
  wrap.appendChild(list);

  const pane = el("div", { class: "ai-pane" });
  if (!activeId) {
    pane.appendChild(
      emptyState({
        icon: "ai",
        title: t("ai.empty.title", "还没有对话"),
        hint: t("ai.empty.hint", "创建第一段对话后，Mydow AI 会基于你的知识库回答问题。"),
        action: el(
          "button",
          {
            class: "btn btn-primary",
            style: "margin-top:18px;",
            onclick: createNewConversation,
          },
          [svg("plus", 16), t("ai.empty.cta", "新建对话")],
        ),
      }),
    );
    wrap.appendChild(pane);
    return wrap;
  }
  const msgs = el("div", { class: "ai-msgs" });
  pane.appendChild(msgs);
  // Composer.
  const ta = el("textarea", {
    placeholder: "向 Mydow AI 提问，回车发送",
    onkeydown: (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.altKey) {
        e.preventDefault();
        e.currentTarget.parentElement.querySelector(".send-btn").click();
      }
    },
  });
  let activeStream = null;
  /** Filled by `streamAssistantMessage` on SSE `meta` — used so「停止」can POST /cancel immediately. */
  const streamAssistantMeta = { messageId: null };
  const sendBtn = el(
      "button",
      {
        class: "btn btn-primary send-btn",
        onclick: async () => {
          const content = ta.value.trim();
          if (!content) {
            toast("请先输入消息", "error");
            ta.focus();
            return;
          }
          ta.value = "";
          streamAssistantMeta.messageId = null;
          appendBubble(msgs, "user", content);
        const placeholder = appendBubble(msgs, "assistant", "▍", null, true);
        sendBtn.disabled = true;
        stopBtn.style.display = "inline-flex";
        stopBtn.disabled = false;
        try {
          const ok = await streamAssistantMessage(
            activeId,
            content,
            placeholder,
            (handle) => (activeStream = handle),
            streamAssistantMeta,
          );
          if (!ok) {
            // Stream not available — fallback to non-streaming.
            const r = await A.ai.send(activeId, { content });
            const am = r.data.assistant_message;
            placeholder.replaceWith(
              renderAssistantBubble(am.content || "（暂无回复）", am),
            );
          }
        } catch (e) {
          placeholder.textContent = `❌ AI 出错：${e.message}`;
          placeholder.classList.remove("is-typing");
        } finally {
          sendBtn.disabled = false;
          stopBtn.style.display = "none";
          stopBtn.disabled = true;
          activeStream = null;
          ta.focus();
        }
      },
    },
    [svg("send", 16), "发送"],
  );
  const stopBtn = el(
    "button",
    {
      class: "btn",
      style: "display:none;",
      title: "停止生成",
      onclick: () => {
        if (activeStream) {
          activeStream.abort();
          stopBtn.disabled = true;
        }
        const mid = streamAssistantMeta.messageId;
        if (mid) {
          A.ai.cancel(mid).catch(() => {});
        }
      },
    },
    "停止",
  );
  pane.appendChild(
    el("div", { class: "ai-composer" }, [ta, stopBtn, sendBtn]),
  );
  wrap.appendChild(pane);

  // Load detail / messages.
  try {
    const detail = await A.ai.detail(activeId);
    const messages = (detail.data && detail.data.messages) || [];
    if (messages.length === 0) {
      msgs.appendChild(
        el(
          "div",
          { class: "muted", style: "text-align:center;padding:40px 0;" },
          "开始一段对话吧。AI 会基于你的知识库回答。",
        ),
      );
    } else {
      for (const m of messages) {
        appendBubble(msgs, m.role || "assistant", m.content || "", m);
      }
    }
  } catch (e) {
    msgs.appendChild(errorState(e));
  }

  return wrap;
}

function appendBubble(container, role, text, msg, isStreaming = false) {
  const bubble = el("div", { class: `bubble ${role}` });
  bubble.dataset.role = role;
  bubble._mydow = { msg };
  if (isStreaming) bubble.classList.add("is-typing");
  bubble.appendChild(document.createTextNode(text || ""));
  if (msg) decorateAssistantBubble(bubble, text, msg);
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
  return bubble;
}

function renderAssistantBubble(text, msg) {
  const bubble = el("div", { class: "bubble assistant", text });
  bubble.dataset.role = "assistant";
  decorateAssistantBubble(bubble, text, msg);
  return bubble;
}

function decorateAssistantBubble(bubble, text, msg) {
  if (msg && msg.citations && msg.citations.length) {
    const cites = el("div", { class: "citations" });
    for (const c of msg.citations) {
      cites.appendChild(
        el("div", {}, [
          svg("doc", 12),
          el(
            "span",
            {
              style: "margin-left:4px;",
              text: c.title || c.document_id || "引用",
            },
          ),
        ]),
      );
    }
    bubble.appendChild(cites);
  }
  const isAsst =
    bubble.dataset.role === "assistant" ||
    (bubble.classList && bubble.classList.contains("assistant"));
  if (msg && isAsst && msg.id) {
    bubble.appendChild(
      el("div", { class: "ai-actions-after" }, [
        el(
          "button",
          {
            class: "btn-icon",
            title: "保存为知识库文档",
            onclick: () => openAiSaveToKbModal(msg.id, text),
          },
          [svg("kb", 14)],
        ),
        el(
          "button",
          {
            class: "btn-icon",
            title: "保存为任务",
            onclick: () => openAiCreateTasksModal(msg.id, text),
          },
          [svg("check", 14)],
        ),
        el(
          "button",
          {
            class: "btn-icon",
            title: "重新生成",
            onclick: async () => {
              try {
                await A.ai.regenerate(msg.id);
                toast("已请求重新生成", "success");
              } catch (e) {
                toast(`失败: ${e.message}`, "error");
              }
            },
          },
          [svg("spark", 14)],
        ),
      ]),
    );
  }
}

async function streamAssistantMessage(
  conversationId,
  content,
  placeholder,
  onAbortHandle,
  metaSlot = null,
) {
  // Use fetch streaming to avoid SSE auth quirks across browsers.
  const url = A.ai.streamSendUrl(conversationId);
  const ctrl = new AbortController();
  if (metaSlot) {
    metaSlot.messageId = null;
  }
  if (onAbortHandle) {
    onAbortHandle({ abort: () => ctrl.abort() });
  }
  let resp;
  try {
    resp = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${store.token()}`,
      },
      body: JSON.stringify({ content }),
      signal: ctrl.signal,
    });
  } catch (e) {
    if (e && e.name === "AbortError") {
      placeholder.classList.remove("is-typing");
      placeholder.textContent = "（已停止）";
      return true;
    }
    return false;
  }
  if (!resp.ok || !resp.body) return false;
  // Reset placeholder text.
  placeholder.textContent = "";
  placeholder.classList.add("is-typing");
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let assembled = "";
  let assistantMessageId = null;
  let citations = [];
  while (true) {
    let done, value;
    try {
      ({ done, value } = await reader.read());
    } catch (e) {
      if (e.name === "AbortError") {
        if (assistantMessageId) {
          A.ai.cancel(assistantMessageId).catch(() => {});
        }
        placeholder.classList.remove("is-typing");
        placeholder.textContent = (assembled || "") + "（已停止）";
        return true;
      }
      return false;
    }
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split(/\n\n/);
    buffer = events.pop() || "";
    for (const ev of events) {
      const lines = ev.split("\n");
      let event = "message";
      let data = "";
      for (const line of lines) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      let payload = null;
      if (data) {
        try {
          payload = JSON.parse(data);
        } catch {
          payload = { raw: data };
        }
      }
      if (event === "meta" && payload) {
        assistantMessageId =
          payload.message_id || payload.assistant_message_id || null;
        if (metaSlot && assistantMessageId) {
          metaSlot.messageId = assistantMessageId;
        }
      } else if (event === "token" && payload) {
        const chunk = payload.delta || payload.token || payload.text || "";
        assembled += chunk;
        placeholder.textContent = assembled + "▍";
        placeholder.parentElement?.scrollTo({
          top: placeholder.parentElement.scrollHeight,
          behavior: "smooth",
        });
      } else if (event === "citation" && payload) {
        citations.push(payload);
      } else if (event === "done") {
        placeholder.classList.remove("is-typing");
        placeholder.textContent = assembled || "（无内容）";
        if (assistantMessageId) {
          decorateAssistantBubble(placeholder, assembled, {
            id: assistantMessageId,
            citations,
          });
        }
        return true;
      } else if (event === "error" && payload) {
        placeholder.textContent = `❌ ${payload.message || "AI 出错"}`;
        placeholder.classList.remove("is-typing");
        return true;
      }
    }
  }
  // Stream closed without explicit done event.
  placeholder.classList.remove("is-typing");
  if (assembled) {
    placeholder.textContent = assembled;
    if (assistantMessageId) {
      decorateAssistantBubble(placeholder, assembled, {
        id: assistantMessageId,
        citations,
      });
    }
    return true;
  }
  return false;
}

// ─────────────────────────────────────────────  Page: Skills  ───────────

async function renderSkills() {
  let items = [];
  try {
    const r = await A.skills.list({ page_size: 24 });
    items = (r.data && r.data.items) || [];
  } catch (e) {
    return errorState(e);
  }
  const wrap = el("div", { class: "fade-in" }, [
    el("div", { class: "page-head" }, [
      el("h1", {}, "Skills 广场"),
      el(
        "p",
        { class: "subtitle" },
        "一组可复用的能力模块，把重复的工作交给 AI。",
      ),
    ]),
  ]);
  if (!items.length) {
    wrap.appendChild(
      emptyState({
        icon: "skills",
        title: "还没有 Skill",
        hint: "后端默认会种子化「Mydow 快速总结」一项。",
      }),
    );
    return wrap;
  }
  wrap.appendChild(
    el(
      "div",
      { class: "skills-grid" },
      items.map((s) =>
        el("div", { class: "skill-card" }, [
          el(
            "div",
            { class: "row" },
            [
              el(
                "div",
                { class: "skill-icon" },
                (s.icon && s.icon.slice(0, 2)) || "✦",
              ),
              el("div", { style: "min-width:0;" }, [
                el(
                  "div",
                  { class: "skill-name", text: s.name || "Skill" },
                ),
                el(
                  "div",
                  {
                    class: "muted",
                    style: "font-size:11px;",
                    text: s.category || "通用",
                  },
                ),
              ]),
            ],
          ),
          el("div", { class: "skill-desc", text: s.description || "" }),
          el("div", { class: "row" }, [
            el(
              "button",
              {
                class: "btn btn-primary btn-sm",
                onclick: () => openSkillRunModal(s),
              },
              "立即试用",
            ),
            el(
              "button",
              {
                class: "btn btn-sm",
                onclick: () =>
                  toast(`Skill ${s.name} 详情：${s.description || "—"}`),
              },
              "详情",
            ),
          ]),
        ]),
      ),
    ),
  );
  return wrap;
}

// ─────────────────────────────────────────────  Page: Garden  ───────────

async function renderGarden() {
  let overview, graph;
  try {
    [overview, graph] = await Promise.all([
      A.garden.overview(),
      A.garden.graph({ limit: 60 }).catch(() => ({ data: { nodes: [], edges: [] } })),
    ]);
  } catch (e) {
    return errorState(e);
  }
  const data = overview.data || {};
  const stats = data.stats || data;
  const topics = (data.top_topics || []).map((t) =>
    typeof t === "string" ? { name: t, count: 1 } : t,
  );

  const wrap = el("div", { class: "fade-in" }, [
    el("div", { class: "page-head" }, [
      el("h1", {}, "数字花园"),
      el(
        "p",
        { class: "subtitle" },
        `节点 ${stats.node_count ?? 0} · 边 ${stats.edge_count ?? 0} · 强连接 ${stats.strong_edge_count ?? 0}`,
      ),
    ]),
  ]);

  // Stats strip.
  wrap.appendChild(
    el("div", { class: "garden-stats card card-pad row" }, [
      gardenStat("节点", stats.node_count ?? 0),
      gardenStat("连接", stats.edge_count ?? 0),
      gardenStat("强连接", stats.strong_edge_count ?? 0),
      gardenStat("主题", topics.length),
    ]),
  );

  const canvasNode = el("div", { class: "garden-canvas" });
  canvasNode.appendChild(buildGardenSVG(topics, graph.data || { nodes: [], edges: [] }));

  const sidePanel = el("aside", { class: "side-panel" }, [
    el("h2", { class: "section-title", text: "热门主题" }),
    topics.length
      ? el(
          "div",
          { style: "display:flex;flex-direction:column;gap:8px;" },
          topics.slice(0, 8).map((t) =>
            el(
              "button",
              {
                class: "row btn btn-sm",
                style: "justify-content:space-between;",
                onclick: () => openSearchPanel(t.name),
              },
              [
                el("span", { class: "tag tag-primary", text: t.name }),
                el("span", { class: "muted", text: `${t.count || 1}` }),
              ],
            ),
          ),
        )
      : el("p", { class: "muted" }, "继续记录会让花园慢慢长出来。"),
  ]);

  wrap.appendChild(el("div", { class: "garden-wrap" }, [canvasNode, sidePanel]));
  return wrap;
}

function gardenStat(label, value) {
  return el("div", { class: "garden-stat" }, [
    el("div", { class: "stat-num", text: String(value) }),
    el("div", { class: "stat-label", text: label }),
  ]);
}

function buildGardenSVG(topics, graph) {
  const NS = "http://www.w3.org/2000/svg";
  const W = 720;
  const H = 540;
  const root = document.createElementNS(NS, "svg");
  root.setAttribute("viewBox", `0 0 ${W} ${H}`);
  root.setAttribute("preserveAspectRatio", "xMidYMid meet");

  // Nodes layout: center = "你"; topics radial; graph nodes scattered.
  const cx = W / 2;
  const cy = H / 2;
  const inner = 150;
  const outer = 230;
  const nodes = [{ id: "__me__", label: "你", x: cx, y: cy, w: 1, kind: "me" }];
  topics.slice(0, 8).forEach((t, i) => {
    const angle = (i / Math.max(topics.length, 1)) * Math.PI * 2 - Math.PI / 2;
    nodes.push({
      id: `topic-${i}`,
      label: t.name,
      x: cx + Math.cos(angle) * inner,
      y: cy + Math.sin(angle) * inner,
      w: t.count || 1,
      kind: "topic",
    });
  });
  (graph.nodes || []).slice(0, 12).forEach((n, i) => {
    const angle = (i / 12) * Math.PI * 2;
    nodes.push({
      id: n.id || `g-${i}`,
      label: n.label || n.title || `#${i + 1}`,
      x: cx + Math.cos(angle) * outer + (Math.random() - 0.5) * 20,
      y: cy + Math.sin(angle) * outer + (Math.random() - 0.5) * 20,
      w: 1,
      kind: "node",
    });
  });

  // Edges: center to topics + edges from graph.
  for (let i = 1; i < Math.min(nodes.length, 9); i++) {
    const line = document.createElementNS(NS, "line");
    line.setAttribute("x1", cx);
    line.setAttribute("y1", cy);
    line.setAttribute("x2", nodes[i].x);
    line.setAttribute("y2", nodes[i].y);
    line.setAttribute("stroke", "#a3b1d0");
    line.setAttribute("stroke-width", "1.4");
    root.appendChild(line);
  }
  (graph.edges || []).forEach((e) => {
    const a = nodes.find((n) => n.id === e.from);
    const b = nodes.find((n) => n.id === e.to);
    if (!a || !b) return;
    const line = document.createElementNS(NS, "line");
    line.setAttribute("x1", a.x);
    line.setAttribute("y1", a.y);
    line.setAttribute("x2", b.x);
    line.setAttribute("y2", b.y);
    line.setAttribute("stroke", "#cbd5ec");
    line.setAttribute("stroke-width", "1");
    line.setAttribute("stroke-dasharray", "4 4");
    root.appendChild(line);
  });

  // Nodes.
  nodes.forEach((n) => {
    const g = document.createElementNS(NS, "g");
    g.style.cursor = "grab";
    g.setAttribute("data-garden-node", n.kind);
    g.setAttribute("tabindex", "0");
    const r =
      n.kind === "me" ? 32 : Math.max(14, Math.min(30, 14 + (n.w || 1)));
    const circle = document.createElementNS(NS, "circle");
    circle.setAttribute("cx", n.x);
    circle.setAttribute("cy", n.y);
    circle.setAttribute("r", r);
    circle.setAttribute(
      "fill",
      n.kind === "me"
        ? "#3a5cff"
        : n.kind === "topic"
          ? "#e7eefb"
          : "#fff",
    );
    circle.setAttribute(
      "stroke",
      n.kind === "me" ? "#2546d8" : "#3a5cff",
    );
    circle.setAttribute("stroke-width", "1.5");
    g.appendChild(circle);
    const text = document.createElementNS(NS, "text");
    text.setAttribute("x", n.x);
    text.setAttribute("y", n.y + 4);
    text.setAttribute("text-anchor", "middle");
    text.setAttribute(
      "font-size",
      n.kind === "me" ? "13" : "11",
    );
    text.setAttribute("font-weight", n.kind === "me" ? "700" : "500");
    text.setAttribute("fill", n.kind === "me" ? "#fff" : "#1d2638");
    text.textContent = (n.label || "").slice(0, 6);
    g.appendChild(text);
    let dragState = null;
    g.addEventListener("pointerdown", (event) => {
      dragState = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        x: Number(circle.getAttribute("cx")),
        y: Number(circle.getAttribute("cy")),
        moved: false,
      };
      g.setPointerCapture(event.pointerId);
      g.classList.add("is-dragging");
      g.style.cursor = "grabbing";
    });
    g.addEventListener("pointermove", (event) => {
      if (!dragState || dragState.pointerId !== event.pointerId) return;
      const dx = event.clientX - dragState.startX;
      const dy = event.clientY - dragState.startY;
      if (Math.abs(dx) + Math.abs(dy) > 3) dragState.moved = true;
      const nextX = dragState.x + dx;
      const nextY = dragState.y + dy;
      circle.setAttribute("cx", nextX);
      circle.setAttribute("cy", nextY);
      text.setAttribute("x", nextX);
      text.setAttribute("y", nextY + 4);
    });
    g.addEventListener("pointerup", (event) => {
      if (!dragState || dragState.pointerId !== event.pointerId) return;
      g.releasePointerCapture(event.pointerId);
      g.classList.remove("is-dragging");
      g.style.cursor = "grab";
      g.dataset.dragged = dragState.moved ? "true" : "false";
      setTimeout(() => delete g.dataset.dragged, 0);
      dragState = null;
    });
    g.addEventListener("click", () => {
      if (g.dataset.dragged === "true") return;
      if (n.kind === "topic" || n.kind === "node") {
        openSearchPanel(n.label);
      } else {
        toast("这就是你的位置——所有知识围绕你展开 🌱");
      }
    });
    root.appendChild(g);
  });

  return root;
}

// ─────────────────────────────────────────────  Page: Today  ───────────

async function renderTodayPage() {
  let today;
  try {
    today = (await A.today()).data;
  } catch (e) {
    return errorState(e);
  }
  const stats = today.stats || {};
  const wrap = el("div", { class: "fade-in" }, [
    el("div", { class: "page-head" }, [
      el(
        "h1",
        {},
        `Today, ${today.user?.name || today.user?.username || "Mydow"}`,
      ),
      el(
        "p",
        { class: "subtitle" },
        new Date().toLocaleDateString("zh-CN", {
          weekday: "long",
          month: "long",
          day: "numeric",
        }),
      ),
    ]),
    el("div", { class: "stat-grid", style: "grid-template-columns:repeat(4,1fr);max-width:none;" }, [
      statCard("今日捕捉", stats.today_capture_count ?? 0),
      statCard("待办任务", stats.pending_task_count ?? 0),
      statCard("知识条目", stats.knowledge_items_count ?? 0),
      statCard(
        "周增长",
        `${Math.round((stats.weekly_growth_rate ?? 0) * 100)}%`,
      ),
    ]),
    el("section", { style: "margin-top:24px;" }, [
      el(
        "div",
        { class: "section-title" },
        [
          el("h2", { style: "font-size:16px;font-weight:700;" }, "今日任务"),
          el(
            "button",
            {
              class: "btn btn-primary btn-sm",
              onclick: () => openCreateTaskModal(),
            },
            [svg("plus", 14), "新建任务"],
          ),
        ],
      ),
      renderTodayTaskList(today.tasks || []),
    ]),
    today.insight_preview
      ? el(
          "section",
          { style: "margin-top:24px;" },
          [
            el("div", { class: "section-title" }, "AI 洞察"),
            el("div", { class: "card card-pad" }, [
              el(
                "h3",
                { style: "font-size:15px;margin-bottom:6px;" },
                today.insight_preview.title || "暂无洞察",
              ),
              el(
                "p",
                { class: "muted" },
                today.insight_preview.summary || "—",
              ),
            ]),
          ],
        )
      : null,
  ]);
  return wrap;
}

function renderTodayTaskList(tasks) {
  if (!tasks.length) {
    return emptyState({
      icon: "check",
      title: "今天没有待办任务",
      hint: "在 AI 对话中可以一键把回答转成任务。",
    });
  }
  return el(
    "div",
    { class: "card", style: "margin-top:12px;padding:8px;" },
    tasks.map((t) =>
      el(
        "div",
        {
          class: "row",
          style:
            "padding:10px 14px;border-bottom:1px solid var(--border-soft);",
        },
        [
          el(
            "button",
            {
              class: "btn-icon",
              title: t.status === "done" ? "未完成" : "标记完成",
              onclick: async () => {
                try {
                  await A.tasks.complete(t.id);
                  toast("任务已完成", "success");
                  renderPage();
                } catch (e) {
                  toast(`失败: ${e.message}`, "error");
                }
              },
            },
            [svg("check", 14)],
          ),
          el("div", { style: "flex:1;" }, [
            el(
              "div",
              {
                style:
                  "font-weight:600;" +
                  (t.status === "done" ? "text-decoration:line-through;color:var(--text-muted);" : ""),
              },
              t.title || "未命名",
            ),
            el(
              "div",
              { style: "font-size:11px;color:var(--text-muted);" },
              `优先级: ${t.priority || "medium"} ${t.due_at ? "· 截止 " + relTime(t.due_at) : ""}`,
            ),
          ]),
          el(
            "button",
            {
              class: "btn-icon",
              title: "删除",
              onclick: async () => {
                if (!confirm(`删除任务「${t.title}」？`)) return;
                try {
                  await A.tasks.remove(t.id);
                  toast("已删除", "success");
                  renderPage();
                } catch (e) {
                  toast(`失败: ${e.message}`, "error");
                }
              },
            },
            [svg("trash", 14)],
          ),
        ],
      ),
    ),
  );
}

async function renderTasksPage() {
  let tasks = [];
  try {
    const r = await A.tasks.list({ page_size: 100 });
    tasks = (r.data && (r.data.items || r.data)) || [];
  } catch (e) {
    return errorState(e);
  }
  return el("div", { class: "fade-in" }, [
    el("div", { class: "page-head" }, [
      el("h1", {}, "全部任务"),
      el("p", { class: "subtitle" }, `${tasks.length} 项任务`),
    ]),
    el("div", { class: "row-spread", style: "margin-bottom:14px;" }, [
      el("div", {}, ""),
      el(
        "button",
        {
          class: "btn btn-primary",
          onclick: () => openCreateTaskModal(),
        },
        [svg("plus", 16), "新建任务"],
      ),
    ]),
    renderTodayTaskList(tasks),
  ]);
}

function openCreateTaskModal() {
  const titleInput = el("input", { placeholder: "需要做什么？" });
  const priSel = el(
    "select",
    {},
    ["low", "medium", "high", "urgent"].map((p) =>
      el("option", { value: p, ...(p === "medium" ? { selected: true } : {}) }, p),
    ),
  );
  const dueInput = el("input", { type: "datetime-local" });
  const { close } = openModal(
    el("div", { class: "modal" }, [
      el("div", { class: "modal-head" }, [
        el("strong", {}, "新建任务"),
        el("button", { class: "btn-icon", title: "关闭", onclick: () => close() }, [svg("close", 16)]),
      ]),
      el("div", { class: "modal-body" }, [
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "标题" }),
          titleInput,
        ]),
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "优先级" }),
          priSel,
        ]),
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "截止时间（可选）" }),
          dueInput,
        ]),
      ]),
      el("div", { class: "modal-foot" }, [
        el("button", { class: "btn", onclick: () => close() }, "取消"),
        el(
          "button",
          {
            class: "btn btn-primary",
            onclick: async () => {
              const title = titleInput.value.trim();
              if (!title) return toast("请填写任务标题", "error");
              try {
                await A.tasks.create({
                  title,
                  priority: priSel.value,
                  due_at: dueInput.value
                    ? new Date(dueInput.value).toISOString()
                    : null,
                });
                toast("已创建", "success");
                close();
                renderPage();
              } catch (e) {
                toast(`失败: ${e.message}`, "error");
              }
            },
          },
          "创建",
        ),
      ]),
    ]),
  );
  setTimeout(() => titleInput.focus(), 0);
}

async function renderInboxPage() {
  let items = [];
  try {
    const r = await A.inbox.list({ page_size: 50 });
    items = (r.data && r.data.items) || [];
  } catch (e) {
    return errorState(e);
  }
  return el("div", { class: "fade-in" }, [
    el("div", { class: "page-head" }, [
      el("h1", {}, "Inbox"),
      el(
        "p",
        { class: "subtitle" },
        `${items.length} 条原始记录，等待 AI 整理或归档`,
      ),
    ]),
    items.length === 0
      ? emptyState({
          icon: "spark",
          title: "Inbox 是空的",
          hint: "在首页输入一条想法，会先进入这里。",
        })
      : el(
          "div",
          { class: "card", style: "padding:8px;" },
          items.map((i) =>
            el(
              "div",
              {
                class: "row",
                style:
                  "padding:12px 14px;border-bottom:1px solid var(--border-soft);",
              },
              [
                el("span", { class: "tag tag-primary", text: i.type || "?" }),
                el("div", { style: "flex:1;min-width:0;" }, [
                  el(
                    "div",
                    { style: "font-weight:600;" },
                    i.title || (i.raw_content || "").slice(0, 80) || "(空)",
                  ),
                  el(
                    "div",
                    { class: "muted", style: "font-size:11px;" },
                    `状态: ${i.status} · ${i.processing_status} · ${relTime(i.created_at)}`,
                  ),
                ]),
                el(
                  "button",
                  {
                    class: "btn-icon",
                    title: "归档",
                    onclick: async () => {
                      try {
                        await A.inbox.patch(i.id, { status: "archived" });
                        toast("已归档", "success");
                        renderPage();
                      } catch (e) {
                        toast(`失败: ${e.message}`, "error");
                      }
                    },
                  },
                  [svg("check", 14)],
                ),
              ],
            ),
          ),
        ),
  ]);
}

// ─────────────────────────────────────────────  Drawers + modals  ───────

function syncOverlayState() {
  const openDrawer = document.querySelector(".drawer.is-open");
  const openModal = document.querySelector(".modal-mask.is-open");
  const root = document.documentElement;

  if (openDrawer) {
    root.dataset.drawer = openDrawer.id || "drawer";
    root.dataset.drawerOpen = "true";
  } else {
    delete root.dataset.drawer;
    delete root.dataset.drawerOpen;
  }

  if (openModal) {
    root.dataset.modal = openModal.dataset.modal || "modal";
    root.dataset.modalOpen = "true";
  } else {
    delete root.dataset.modal;
    delete root.dataset.modalOpen;
  }
}

function ensureDrawer(id) {
  let mask = document.getElementById(`${id}-mask`);
  let drawer = document.getElementById(id);
  if (!mask) {
    mask = el("div", {
      id: `${id}-mask`,
      class: "drawer-mask",
      onclick: () => closeDrawer(id),
    });
    document.body.appendChild(mask);
  }
  if (!drawer) {
    drawer = el("aside", { id, class: "drawer", "data-drawer": id });
    document.body.appendChild(drawer);
  }
  return drawer;
}
function openDrawer(id) {
  const mask = document.getElementById(`${id}-mask`);
  const drawer = document.getElementById(id);
  if (mask) {
    mask.classList.add("is-open");
    mask.dataset.drawer = id;
    mask.dataset.drawerOpen = "true";
  }
  if (drawer) {
    drawer.classList.add("is-open");
    drawer.dataset.drawer = id;
    drawer.dataset.drawerOpen = "true";
  }
  syncOverlayState();
}
function closeDrawer(id) {
  const mask = document.getElementById(`${id}-mask`);
  const drawer = document.getElementById(id);
  if (mask) {
    mask.classList.remove("is-open");
    delete mask.dataset.drawerOpen;
  }
  if (drawer) {
    drawer.classList.remove("is-open");
    delete drawer.dataset.drawerOpen;
  }
  syncOverlayState();
}

async function openCardDrawer(cardId) {
  const drawer = ensureDrawer("card-drawer");
  drawer.innerHTML = "";
  drawer.appendChild(
    el("div", { class: "drawer-head" }, [
      el("strong", {}, "卡片详情"),
      el(
        "button",
        { class: "btn-icon", title: "关闭", onclick: () => closeDrawer("card-drawer") },
        [svg("close", 16)],
      ),
    ]),
  );
  const body = el("div", { class: "drawer-body" });
  drawer.appendChild(body);
  body.appendChild(skeletonPage());
  openDrawer("card-drawer");
  try {
    const r = await A.cards.get(cardId);
    const card = r.data;
    body.innerHTML = "";
    body.appendChild(
      el("h2", { style: "font-size:20px;margin-bottom:6px;" }, card.title || "未命名"),
    );
    body.appendChild(
      el(
        "div",
        { class: "muted", style: "font-size:12px;margin-bottom:14px;" },
        relTime(card.created_at),
      ),
    );
    if (card.tags && card.tags.length) {
      body.appendChild(
        el(
          "div",
          { class: "row", style: "flex-wrap:wrap;gap:6px;margin-bottom:14px;" },
          card.tags.map((t) => el("span", { class: "tag", text: t })),
        ),
      );
    }
    if (card.summary) {
      body.appendChild(
        el(
          "div",
          {
            class: "card card-pad",
            style: "background:var(--bg-tint);margin-bottom:14px;",
          },
          card.summary,
        ),
      );
    }
    body.appendChild(
      el(
        "div",
        {
          style: "white-space:pre-wrap;line-height:1.85;font-size:14px;",
        },
        card.content || "（无正文）",
      ),
    );
    body.appendChild(
      el("div", { class: "row", style: "gap:8px;margin-top:18px;" }, [
        el(
          "button",
          {
            class: "btn",
            onclick: () => openEditCardModal(card),
          },
          [svg("edit", 14), "编辑"],
        ),
        el(
          "button",
          {
            class: "btn",
            onclick: async () => {
              const r = await A.cards.favorite(card.id, !card.is_favorite);
              card.is_favorite = !!(r && r.data && r.data.is_favorite);
              toast(card.is_favorite ? "已收藏" : "已取消收藏", "success");
              openCardDrawer(card.id);
            },
          },
          [svg("star", 14), card.is_favorite ? "已收藏" : "收藏"],
        ),
        el(
          "button",
          {
            class: "btn btn-danger",
            onclick: async () => {
              if (!confirm(`确认删除「${card.title}」？`)) return;
              await A.cards.remove(card.id);
              closeDrawer("card-drawer");
              toast("已删除", "success");
              if (currentRoute().page === "home") refreshHome();
            },
          },
          [svg("trash", 14), "删除"],
        ),
      ]),
    );
  } catch (e) {
    body.innerHTML = "";
    body.appendChild(errorState(e));
  }
}

async function openNotificationDrawer() {
  const drawer = ensureDrawer("notif-drawer");
  drawer.innerHTML = "";
  drawer.appendChild(
    el("div", { class: "drawer-head" }, [
      el("strong", {}, "通知中心"),
      el("div", { class: "row" }, [
        el(
          "button",
          {
            class: "btn btn-sm",
            onclick: async () => {
              await A.notifications.readAll();
              toast("全部标记为已读", "success");
              openNotificationDrawer();
              refreshUnread();
            },
          },
          "全部已读",
        ),
        el(
          "button",
          { class: "btn-icon", title: "关闭", onclick: () => closeDrawer("notif-drawer") },
          [svg("close", 16)],
        ),
      ]),
    ]),
  );
  const body = el("div", { class: "drawer-body" });
  drawer.appendChild(body);
  body.appendChild(skeletonPage());
  openDrawer("notif-drawer");
  try {
    const r = await A.notifications.list({ page_size: 30 });
    const items = (r.data && r.data.items) || [];
    body.innerHTML = "";
    if (!items.length) {
      body.appendChild(
        emptyState({
          icon: "bell",
          title: "暂时没有通知",
          hint: "异步任务完成、AI 输出保存等事件会出现在这里。",
        }),
      );
    } else {
      for (const n of items) {
        body.appendChild(
          el(
            "div",
            {
              class: "notif-row" + (n.is_read ? " is-read" : ""),
              onclick: async () => {
                if (!n.is_read) {
                  await A.notifications.markRead(n.id);
                  refreshUnread();
                  openNotificationDrawer();
                }
              },
            },
            [
              el("div", { class: "notif-dot" }),
              el("div", { style: "flex:1;min-width:0;" }, [
                el("div", { class: "notif-title", text: n.title || "" }),
                el("div", { class: "notif-content", text: n.content || "" }),
                el("div", { class: "notif-time", text: relTime(n.created_at) }),
              ]),
            ],
          ),
        );
      }
    }
  } catch (e) {
    body.innerHTML = "";
    body.appendChild(errorState(e));
  }
}

// ─── Search panel ─────────────────────────────────────────────

let _searchPanel;
function openSearchPanel(initial = "") {
  if (!_searchPanel) buildSearchPanel();
  _searchPanel.classList.add("is-open");
  const input = _searchPanel.querySelector("input");
  input.value = initial;
  input.focus();
  if (initial) doSearch(initial);
}
function closeSearchPanel() {
  if (_searchPanel) _searchPanel.classList.remove("is-open");
}
function buildSearchPanel() {
  const results = el("div", { class: "search-results" });
  const input = el("input", {
    type: "text",
    placeholder: "输入要搜索的内容...",
    onkeydown: (e) => {
      if (e.key === "Escape") closeSearchPanel();
    },
  });
  input.addEventListener(
    "input",
    debounce(() => doSearch(input.value), 220),
  );
  const panel = el("div", { class: "search-panel" }, [
    el("div", { class: "search-panel-input" }, [
      svg("search", 18),
      input,
      el(
        "button",
        { class: "btn-icon", title: "关闭搜索", onclick: closeSearchPanel },
        [svg("close", 16)],
      ),
    ]),
    results,
  ]);
  _searchPanel = el(
    "div",
    {
      class: "search-panel-mask",
      onclick: (e) => {
        if (e.target === e.currentTarget) closeSearchPanel();
      },
    },
    panel,
  );
  document.body.appendChild(_searchPanel);
}
async function doSearch(q) {
  const results = _searchPanel.querySelector(".search-results");
  results.innerHTML = "";
  if (!q.trim()) {
    // Show suggestions from /search/suggestions when empty / very short.
    try {
      const sug = await A.search.suggestions("", 8);
      const items = (sug.data && sug.data.suggestions) || [];
      if (items.length) {
        results.appendChild(
          el(
            "div",
            { style: "padding:8px 18px;color:var(--text-muted);font-size:11px;" },
            "建议",
          ),
        );
        for (const s of items) {
          results.appendChild(
            el(
              "div",
              {
                class: "search-result",
                onclick: () => {
                  closeSearchPanel();
                  if (s.command) {
                    handleSearchCommand(s.command);
                  } else if (s.object_id) {
                    if (s.type === "document") navigate(`#/kb/doc/${s.object_id}`);
                    else if (s.type === "folder") navigate(`#/kb/folder/${s.object_id}`);
                  }
                },
              },
              [
                el("div", { class: "row" }, [
                  el("span", { class: "tag", text: s.type || "建议" }),
                  el("span", { class: "res-title", text: s.label || "" }),
                ]),
              ],
            ),
          );
        }
      } else {
        results.appendChild(
          el(
            "div",
            {
              style: "padding:24px;color:var(--text-muted);text-align:center;",
            },
            "输入关键词开始搜索（试试 /new task）",
          ),
        );
      }
    } catch {
      results.appendChild(
        el(
          "div",
          { style: "padding:24px;color:var(--text-muted);text-align:center;" },
          "输入关键词开始搜索",
        ),
      );
    }
    return;
  }

  // Slash-command mode.
  if (q.startsWith("/")) {
    const cmds = [
      { label: "新建任务", command: "/new task" },
      { label: "新建文件夹", command: "/new folder" },
      { label: "网页剪藏", command: "/clip" },
      { label: "上传文件", command: "/upload" },
      { label: "深度研究", command: "/research" },
    ].filter((c) => c.command.startsWith(q.toLowerCase()));
    for (const c of cmds) {
      results.appendChild(
        el(
          "div",
          {
            class: "search-result",
            onclick: () => {
              closeSearchPanel();
              handleSearchCommand(c.command);
            },
          },
          [
            el("div", { class: "row" }, [
              el("span", { class: "tag tag-primary", text: "command" }),
              el("span", { class: "res-title", text: c.label }),
              el("span", { class: "muted", style: "margin-left:auto;font-size:11px;" }, c.command),
            ]),
          ],
        ),
      );
    }
    if (!cmds.length) {
      results.appendChild(
        el(
          "div",
          { style: "padding:24px;color:var(--text-muted);text-align:center;" },
          `没有匹配的命令: ${q}`,
        ),
      );
    }
    return;
  }

  results.appendChild(
    el(
      "div",
      { style: "padding:24px;color:var(--text-muted);text-align:center;" },
      "搜索中...",
    ),
  );
  try {
    const r = await A.search.query(q, { page_size: 12 });
    const items = (r.data && r.data.items) || [];
    results.innerHTML = "";
    if (!items.length) {
      results.appendChild(
        emptyState({
          icon: "search",
          title: t("empty.search.title", "没有找到结果"),
          hint: t("empty.search.hint", "没有匹配「{query}」的知识、灵感或对话。", { query: q }),
        }),
      );
      return;
    }
    for (const it of items) {
      const onclick = () => {
        closeSearchPanel();
        if (it.object_type === "document" && it.object_id) {
          navigate(`#/kb/doc/${it.object_id}`);
        } else if (it.object_type === "folder" && it.object_id) {
          navigate(`#/kb/folder/${it.object_id}`);
        } else if (it.object_type === "card" && it.object_id) {
          openCardDrawer(it.object_id);
        } else if (it.object_type === "conversation" && it.object_id) {
          navigate(`#/ai/${it.object_id}`);
        } else if (it.object_type === "skill" && it.object_id) {
          navigate("#/skills");
        } else {
          toast(`已选中: ${it.title}`);
        }
      };
      results.appendChild(
        el("div", { class: "search-result", onclick }, [
          el("div", { class: "row" }, [
            el("span", { class: "tag tag-primary", text: it.object_type || "?" }),
            el("span", { class: "res-title", text: it.title || "未命名" }),
          ]),
          el("div", {
            class: "res-summary",
            html: it.highlight || escapeHtml(it.summary || ""),
          }),
        ]),
      );
    }
  } catch (e) {
    results.innerHTML = "";
    results.appendChild(errorState(e));
  }
}

function handleSearchCommand(command) {
  switch (command) {
    case "/new task":
      openCreateTaskModal();
      break;
    case "/new folder":
      openCreateFolderModal();
      break;
    case "/clip":
      openClipModal();
      break;
    case "/upload":
      openUploadModal();
      break;
    case "/research":
      openDeepResearchModal();
      break;
    default:
      toast(`未识别的命令: ${command}`);
  }
}

// ─── Modals ────────────────────────────────────────────────────────────

function openModal(content) {
  const mask = el(
    "div",
    {
      class: "modal-mask is-open",
      "data-modal": "modal",
      "data-modal-open": "true",
      onclick: (e) => {
        if (e.target === e.currentTarget) close();
      },
    },
    content,
  );
  document.body.appendChild(mask);
  syncOverlayState();
  const close = () => {
    mask.remove();
    syncOverlayState();
  };
  return { mask, close };
}

function openCreateFolderModal() {
  const nameInput = el("input", { placeholder: "如：产品设计资料" });
  const descInput = el("textarea", {
    rows: "3",
    placeholder: "可选：这个文件夹里放什么？",
  });
  const { close } = openModal(
    el("div", { class: "modal" }, [
      el("div", { class: "modal-head" }, [
        el("strong", {}, "新建文件夹"),
        el("button", { class: "btn-icon", title: "关闭", onclick: () => close() }, [svg("close", 16)]),
      ]),
      el("div", { class: "modal-body" }, [
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "文件夹名" }),
          nameInput,
        ]),
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "描述（可选）" }),
          descInput,
        ]),
      ]),
      el("div", { class: "modal-foot" }, [
        el("button", { class: "btn", onclick: () => close() }, "取消"),
        el(
          "button",
          {
            class: "btn btn-primary",
            onclick: async () => {
              const name = nameInput.value.trim();
              if (!name) return toast("请填写文件夹名", "error");
              try {
                const r = await A.kb.createFolder({
                  name,
                  description: descInput.value.trim() || null,
                });
                toast("已创建", "success");
                close();
                navigate(`#/kb/folder/${r.data.id}`);
              } catch (e) {
                toast(`创建失败: ${e.message}`, "error");
              }
            },
          },
          "创建",
        ),
      ]),
    ]),
  );
  setTimeout(() => nameInput.focus(), 0);
}

function openRenameFolderModal(folder) {
  const input = el("input", { value: folder.name });
  const { close } = openModal(
    el("div", { class: "modal" }, [
      el("div", { class: "modal-head" }, [
        el("strong", {}, "重命名文件夹"),
        el("button", { class: "btn-icon", title: "关闭", onclick: () => close() }, [svg("close", 16)]),
      ]),
      el(
        "div",
        { class: "modal-body" },
        [
          el("label", { class: "field" }, [
            el("div", { class: "field-label", text: "新的名字" }),
            input,
          ]),
        ],
      ),
      el("div", { class: "modal-foot" }, [
        el("button", { class: "btn", onclick: () => close() }, "取消"),
        el(
          "button",
          {
            class: "btn btn-primary",
            onclick: async () => {
              const name = input.value.trim();
              if (!name) return;
              await A.kb.updateFolder(folder.id, { name });
              toast("已重命名", "success");
              close();
              renderPage();
            },
          },
          "保存",
        ),
      ]),
    ]),
  );
}

async function confirmDeleteFolder(folder) {
  if (!confirm(`确认删除「${folder.name}」？文件夹下的文档将移动到根目录。`))
    return;
  await A.kb.deleteFolder(folder.id);
  toast("已删除", "success");
  navigate("#/kb");
}

function openClipModal() {
  const url = el("input", {
    placeholder: "https://example.com/article",
  });
  const note = el("textarea", {
    rows: "3",
    placeholder: "可选笔记：你为什么剪藏这条？",
  });
  const { close } = openModal(
    el("div", { class: "modal" }, [
      el("div", { class: "modal-head" }, [
        el("strong", {}, "网页剪藏"),
        el("button", { class: "btn-icon", title: "关闭", onclick: () => close() }, [svg("close", 16)]),
      ]),
      el("div", { class: "modal-body" }, [
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "网页 URL" }),
          url,
        ]),
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "备注（可选）" }),
          note,
        ]),
      ]),
      el("div", { class: "modal-foot" }, [
        el("button", { class: "btn", onclick: () => close() }, "取消"),
        el(
          "button",
          {
            class: "btn btn-primary",
            onclick: async () => {
              const u = url.value.trim();
              if (!u) return toast("请填写 URL", "error");
              try {
                await A.capture.link({
                  url: u,
                  note: note.value.trim() || null,
                  auto_process: true,
                });
                toast("已剪藏到 Inbox，AI 正在解析", "success");
                close();
                if (currentRoute().page === "home") refreshHome();
              } catch (e) {
                toast(`剪藏失败: ${e.message}`, "error");
              }
            },
          },
          "保存",
        ),
      ]),
    ]),
  );
  setTimeout(() => url.focus(), 0);
}

function openUploadModal(folderId) {
  const fileInput = el("input", { type: "file" });
  const { close } = openModal(
    el("div", { class: "modal" }, [
      el("div", { class: "modal-head" }, [
        el("strong", {}, "上传文件"),
        el("button", { class: "btn-icon", title: "关闭", onclick: () => close() }, [svg("close", 16)]),
      ]),
      el("div", { class: "modal-body" }, [
        el(
          "div",
          { class: "muted", style: "font-size:12px;margin-bottom:8px;" },
          "支持 .txt / .md / .pdf / .docx / .pptx / 图片 / 音频；V1 单文件最大 50MB。",
        ),
        fileInput,
      ]),
      el("div", { class: "modal-foot" }, [
        el("button", { class: "btn", onclick: () => close() }, "取消"),
        el(
          "button",
          {
            class: "btn btn-primary",
            onclick: async () => {
              const file = fileInput.files && fileInput.files[0];
              if (!file) return toast("请选择文件", "error");
              try {
                const presign = await A.capture.presign({
                  filename: file.name,
                  mime_type: file.type || "application/octet-stream",
                  size_bytes: file.size,
                });
                const data = presign.data || {};
                const uploadUrl = data.upload_url || data.url;
                if (uploadUrl) {
                  const hdr = {
                    "Content-Type":
                      file.type || "application/octet-stream",
                    ...(typeof data.headers === "object" && data.headers
                      ? data.headers
                      : {}),
                  };
                  if (!hdr.Authorization && store.token()) {
                    hdr.Authorization = `Bearer ${store.token()}`;
                  }
                  await fetch(uploadUrl, {
                    method: data.upload_method || data.method || "PUT",
                    headers: hdr,
                    body: file,
                  });
                }
                const commit = await A.capture.commit({
                  upload_id: data.upload_id,
                  filename: file.name,
                  mime_type: file.type || "application/octet-stream",
                  size_bytes: file.size,
                  target_folder_id: folderId || null,
                  auto_process: true,
                });
                toast("已上传，正在解析", "success");
                close();
                if (commit.data && commit.data.job_id) {
                  pollJob(commit.data.job_id);
                }
                renderPage();
              } catch (e) {
                toast(`上传失败: ${e.message}`, "error");
              }
            },
          },
          "上传",
        ),
      ]),
    ]),
  );
}

function openDeepResearchModal() {
  const topic = el("input", { placeholder: "你想研究什么主题？" });
  const requirement = el("textarea", {
    rows: "3",
    placeholder: "希望 AI 输出哪些角度？",
  });
  const { close } = openModal(
    el("div", { class: "modal" }, [
      el("div", { class: "modal-head" }, [
        el("strong", {}, "深度研究"),
        el("button", { class: "btn-icon", title: "关闭", onclick: () => close() }, [svg("close", 16)]),
      ]),
      el("div", { class: "modal-body" }, [
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "研究主题" }),
          topic,
        ]),
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "输出要求" }),
          requirement,
        ]),
      ]),
      el("div", { class: "modal-foot" }, [
        el("button", { class: "btn", onclick: () => close() }, "取消"),
        el(
          "button",
          {
            class: "btn btn-primary",
            onclick: async () => {
              const t = topic.value.trim();
              if (!t) return toast("请填写研究主题", "error");
              try {
                const conv = await A.ai.create({
                  title: `研究: ${t.slice(0, 30)}`,
                  mode: "report",
                });
                await A.ai.send(conv.data.id, {
                  content: `请基于我的知识库做关于「${t}」的研究。\n\n要求：${requirement.value.trim() || "总结趋势、证据和下一步行动。"}`,
                });
                toast("研究对话已创建，正在生成首轮回答", "success");
                close();
                navigate(`#/ai/${conv.data.id}`);
              } catch (e) {
                toast(`深度研究启动失败: ${e.message}`, "error");
              }
            },
          },
          "开始研究",
        ),
      ]),
    ]),
  );
}

function openEditCardModal(card) {
  const titleInput = el("input", { value: card.title || "" });
  const summaryInput = el("textarea", {
    rows: "3",
    text: card.summary || "",
  });
  const tagsInput = el("input", {
    value: (card.tags || []).join(", "),
  });
  const contentInput = el("textarea", {
    rows: "8",
    style: "font-family:var(--font-mono);font-size:13px;",
    text: card.content || "",
  });
  const { close } = openModal(
    el("div", { class: "modal", style: "width:min(640px,92vw);" }, [
      el("div", { class: "modal-head" }, [
        el("strong", {}, "编辑卡片"),
        el("button", { class: "btn-icon", title: "关闭", onclick: () => close() }, [svg("close", 16)]),
      ]),
      el("div", { class: "modal-body" }, [
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "标题" }),
          titleInput,
        ]),
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "摘要" }),
          summaryInput,
        ]),
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "标签（逗号分隔）" }),
          tagsInput,
        ]),
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "正文" }),
          contentInput,
        ]),
      ]),
      el("div", { class: "modal-foot" }, [
        el("button", { class: "btn", onclick: () => close() }, "取消"),
        el(
          "button",
          {
            class: "btn btn-primary",
            onclick: async () => {
              try {
                await A.cards.update(card.id, {
                  title: titleInput.value.trim(),
                  summary: summaryInput.value.trim() || null,
                  content: contentInput.value,
                  tags: tagsInput.value
                    .split(/[,，]/)
                    .map((t) => t.trim())
                    .filter(Boolean),
                });
                toast("已保存", "success");
                close();
                openCardDrawer(card.id);
                if (currentRoute().page === "home") refreshHome();
              } catch (e) {
                toast(`保存失败: ${e.message}`, "error");
              }
            },
          },
          "保存",
        ),
      ]),
    ]),
  );
}

function openEditDocModal(doc) {
  const titleInput = el("input", { value: doc.title || "" });
  const summaryInput = el("textarea", {
    rows: "3",
    text: doc.summary || "",
  });
  const tagsInput = el("input", {
    value: (doc.tags || []).join(", "),
  });
  const contentInput = el("textarea", {
    rows: "10",
    style: "font-family:var(--font-mono);font-size:13px;",
    text: doc.content || "",
  });
  const { close } = openModal(
    el("div", { class: "modal", style: "width:min(720px,92vw);" }, [
      el("div", { class: "modal-head" }, [
        el("strong", {}, "编辑文档"),
        el("button", { class: "btn-icon", title: "关闭", onclick: () => close() }, [svg("close", 16)]),
      ]),
      el("div", { class: "modal-body" }, [
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "标题" }),
          titleInput,
        ]),
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "摘要" }),
          summaryInput,
        ]),
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "标签（逗号分隔）" }),
          tagsInput,
        ]),
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "正文" }),
          contentInput,
        ]),
      ]),
      el("div", { class: "modal-foot" }, [
        el("button", { class: "btn", onclick: () => close() }, "取消"),
        el(
          "button",
          {
            class: "btn btn-primary",
            onclick: async () => {
              try {
                await A.kb.updateDocument(doc.id, {
                  title: titleInput.value.trim(),
                  summary: summaryInput.value.trim() || null,
                  content: contentInput.value,
                  tags: tagsInput.value
                    .split(/[,，]/)
                    .map((t) => t.trim())
                    .filter(Boolean),
                });
                toast("已保存", "success");
                close();
                renderPage();
              } catch (e) {
                toast(`保存失败: ${e.message}`, "error");
              }
            },
          },
          "保存",
        ),
      ]),
    ]),
  );
}

async function openMoveDocModal(doc) {
  let folders = [];
  try {
    folders = (await A.kb.folders({ include_counts: "true" })).data.items || [];
  } catch {}
  const folderSel = el(
    "select",
    {},
    [
      el("option", { value: "" }, "（移到根目录）"),
      ...folders.map((f) =>
        el(
          "option",
          { value: f.id, ...(f.id === doc.folder_id ? { selected: true } : {}) },
          f.name,
        ),
      ),
    ],
  );
  const { close } = openModal(
    el("div", { class: "modal" }, [
      el("div", { class: "modal-head" }, [
        el("strong", {}, "移动到其他文件夹"),
        el("button", { class: "btn-icon", title: "关闭", onclick: () => close() }, [svg("close", 16)]),
      ]),
      el("div", { class: "modal-body" }, [
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "目标文件夹" }),
          folderSel,
        ]),
      ]),
      el("div", { class: "modal-foot" }, [
        el("button", { class: "btn", onclick: () => close() }, "取消"),
        el(
          "button",
          {
            class: "btn btn-primary",
            onclick: async () => {
              try {
                await A.kb.moveDocument(doc.id, folderSel.value || null);
                toast("已移动", "success");
                close();
                renderPage();
              } catch (e) {
                toast(`移动失败: ${e.message}`, "error");
              }
            },
          },
          "移动",
        ),
      ]),
    ]),
  );
}

async function openAiSaveToKbModal(messageId, fallbackText) {
  let folders = [];
  try {
    folders = (await A.kb.folders({ include_counts: "true" })).data.items || [];
  } catch {}
  const titleInput = el("input", {
    placeholder: "自动总结的标题",
    value: (fallbackText || "AI 输出").slice(0, 60),
  });
  const folderSel = el("select", { class: "" }, [
    el("option", { value: "" }, "（不指定文件夹）"),
    ...folders.map((f) =>
      el("option", { value: f.id }, f.name),
    ),
  ]);
  const tagsInput = el("input", {
    placeholder: "用逗号分隔多个标签",
    value: "AI生成",
  });
  const { close } = openModal(
    el("div", { class: "modal" }, [
      el("div", { class: "modal-head" }, [
        el("strong", {}, "保存到知识库"),
        el("button", { class: "btn-icon", title: "关闭", onclick: () => close() }, [svg("close", 16)]),
      ]),
      el("div", { class: "modal-body" }, [
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "标题" }),
          titleInput,
        ]),
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "文件夹" }),
          folderSel,
        ]),
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "标签" }),
          tagsInput,
        ]),
      ]),
      el("div", { class: "modal-foot" }, [
        el("button", { class: "btn", onclick: () => close() }, "取消"),
        el(
          "button",
          {
            class: "btn btn-primary",
            onclick: async () => {
              try {
                await A.ai.saveToKb(messageId, {
                  title: titleInput.value.trim() || null,
                  folder_id: folderSel.value || null,
                  tags: tagsInput.value
                    .split(/[,，]/)
                    .map((t) => t.trim())
                    .filter(Boolean),
                });
                toast("已入队保存到知识库", "success");
                close();
              } catch (e) {
                toast(`保存失败: ${e.message}`, "error");
              }
            },
          },
          "保存",
        ),
      ]),
    ]),
  );
  setTimeout(() => titleInput.focus(), 0);
}

function openAiCreateTasksModal(messageId, fallbackText) {
  const tasks = [
    { title: (fallbackText || "AI 任务").slice(0, 60) || "新任务", priority: "medium" },
  ];
  const listEl = el("div", {});
  const renderList = () => {
    listEl.innerHTML = "";
    tasks.forEach((t, i) => {
      const titleInput = el("input", { value: t.title });
      titleInput.addEventListener("input", () => (t.title = titleInput.value));
      const priSel = el(
        "select",
        { style: "margin-left:8px;" },
        ["low", "medium", "high", "urgent"].map((p) =>
          el(
            "option",
            { value: p, ...(p === t.priority ? { selected: true } : {}) },
            p,
          ),
        ),
      );
      priSel.addEventListener("change", () => (t.priority = priSel.value));
      const removeBtn = el(
        "button",
        {
          class: "btn-icon",
          title: "移除任务项",
          style: "margin-left:8px;",
          onclick: () => {
            tasks.splice(i, 1);
            renderList();
          },
        },
        [svg("close", 14)],
      );
      listEl.appendChild(
        el(
          "div",
          { style: "display:flex;align-items:center;margin-bottom:8px;" },
          [titleInput, priSel, removeBtn],
        ),
      );
    });
  };
  renderList();
  const { close } = openModal(
    el("div", { class: "modal" }, [
      el("div", { class: "modal-head" }, [
        el("strong", {}, "创建任务"),
        el("button", { class: "btn-icon", title: "关闭", onclick: () => close() }, [svg("close", 16)]),
      ]),
      el("div", { class: "modal-body" }, [
        listEl,
        el(
          "button",
          {
            class: "btn btn-sm",
            onclick: () => {
              tasks.push({ title: "新任务", priority: "medium" });
              renderList();
            },
          },
          [svg("plus", 14), "添加一项"],
        ),
      ]),
      el("div", { class: "modal-foot" }, [
        el("button", { class: "btn", onclick: () => close() }, "取消"),
        el(
          "button",
          {
            class: "btn btn-primary",
            onclick: async () => {
              const valid = tasks
                .map((t) => ({
                  title: (t.title || "").trim(),
                  priority: t.priority,
                }))
                .filter((t) => t.title);
              if (!valid.length) return toast("请填写至少一项任务", "error");
              try {
                await A.ai.createTasks(messageId, { tasks: valid });
                toast("已入队创建任务", "success");
                close();
              } catch (e) {
                toast(`创建失败: ${e.message}`, "error");
              }
            },
          },
          "创建",
        ),
      ]),
    ]),
  );
}

function openSkillRunModal(skill) {
  const ta = el("textarea", {
    rows: "5",
    placeholder: "粘贴/输入这个 Skill 要处理的内容",
  });
  const { close } = openModal(
    el("div", { class: "modal" }, [
      el("div", { class: "modal-head" }, [
        el("strong", {}, `运行 Skill: ${skill.name}`),
        el("button", { class: "btn-icon", title: "关闭", onclick: () => close() }, [svg("close", 16)]),
      ]),
      el("div", { class: "modal-body" }, [
        el("p", { class: "muted", style: "margin-bottom:10px;font-size:12px;" }, skill.description || ""),
        el("label", { class: "field" }, [
          el("div", { class: "field-label", text: "输入内容" }),
          ta,
        ]),
      ]),
      el("div", { class: "modal-foot" }, [
        el("button", { class: "btn", onclick: () => close() }, "取消"),
        el(
          "button",
          {
            class: "btn btn-primary",
            onclick: async () => {
              try {
                await A.skills.run(skill.id, {
                  input: { text: ta.value.trim() },
                  save_output: true,
                });
                toast("Skill 已入队，结果会在通知中心提醒", "success");
                close();
              } catch (e) {
                toast(`运行失败: ${e.message}`, "error");
              }
            },
          },
          "运行",
        ),
      ]),
    ]),
  );
}

function openCardDocActions(doc, folder) {
  const { close } = openModal(
    el("div", { class: "modal" }, [
      el("div", { class: "modal-head" }, [
        el("strong", {}, doc.title || "文档操作"),
        el("button", { class: "btn-icon", title: "关闭", onclick: () => close() }, [svg("close", 16)]),
      ]),
      el("div", { class: "modal-body" }, [
        el(
          "button",
          {
            class: "btn",
            style: "width:100%;justify-content:flex-start;margin-bottom:8px;",
            onclick: async () => {
              const r = await A.kb.updateDocument(doc.id, {
                is_favorite: !doc.is_favorite,
              });
              doc.is_favorite = !!(r && r.data && r.data.is_favorite);
              toast(
                doc.is_favorite ? "已收藏" : "已取消收藏",
                "success",
              );
              close();
              renderPage();
            },
          },
          [svg("star", 14), doc.is_favorite ? "取消收藏" : "收藏"],
        ),
        el(
          "button",
          {
            class: "btn",
            style: "width:100%;justify-content:flex-start;margin-bottom:8px;",
            onclick: () => {
              close();
              navigate(`#/kb/doc/${doc.id}`);
            },
          },
          [svg("doc", 14), "打开详情"],
        ),
        el(
          "button",
          {
            class: "btn btn-danger",
            style: "width:100%;justify-content:flex-start;",
            onclick: async () => {
              if (!confirm(`确认删除「${doc.title}」？`)) return;
              await A.kb.deleteDocument(doc.id);
              toast("已删除", "success");
              close();
              renderPage();
            },
          },
          [svg("trash", 14), "删除"],
        ),
      ]),
    ]),
  );
}

function openUserMenu() {
  const me = state.me || store.user() || {};
  const drawer = ensureDrawer("profile-drawer");
  drawer.innerHTML = "";
  drawer.appendChild(
    el("div", { class: "drawer-head" }, [
      el("strong", {}, "个人中心"),
      el(
        "button",
        {
          class: "btn-icon",
          title: "关闭个人中心",
          onclick: () => closeDrawer("profile-drawer"),
        },
        [svg("close", 16)],
      ),
    ]),
  );
  const body = el("div", { class: "drawer-body" }, [
    el("div", { class: "field" }, [
      el("div", { class: "field-label", text: "账号" }),
      el("div", { class: "muted", text: me.email || "demo@mydow.example" }),
    ]),
    el("div", { class: "field" }, [
      el("div", { class: "field-label", text: "用户名" }),
      el("div", { class: "muted", text: me.username || "demo" }),
    ]),
    el("div", { class: "field" }, [
      el("div", { class: "field-label", text: "计划" }),
      el("div", { class: "muted", text: me.plan || "free" }),
    ]),
    el("div", { class: "field" }, [
      el("div", { class: "field-label", text: "状态" }),
      el("div", { class: "muted", text: "当前会话已登录，可随时退出" }),
    ]),
    el("div", { class: "row", style: "margin-top:16px;" }, [
      el(
        "button",
        {
          class: "btn",
          onclick: () => closeDrawer("profile-drawer"),
        },
        "关闭",
      ),
      el(
        "button",
        {
          class: "btn btn-primary",
          onclick: () => {
            store.clearSession();
            closeDrawer("profile-drawer");
            renderAuthOverlay();
            toast("已退出登录", "success");
          },
        },
        "退出登录",
      ),
    ]),
  ]);
  drawer.appendChild(body);
  openDrawer("profile-drawer");
}

// ─────────────────────────────────────────────  Auth overlay  ───────────

function renderAuthOverlay() {
  const overlay = document.getElementById("auth-overlay");
  if (!overlay) return;
  overlay.innerHTML = "";
  overlay.hidden = false;

  const usernameInput = el("input", { placeholder: "邮箱或用户名" });
  const passwordInput = el("input", { type: "password", placeholder: "密码" });
  const card = el("div", { class: "auth-card" }, [
    el("h2", {}, "登录 Mydow"),
    el("p", {}, "演示模式可一键登录，也可使用账号密码。"),
    el(
      "button",
      {
        class: "btn btn-primary",
        style: "width:100%;justify-content:center;margin-bottom:14px;",
        onclick: async () => {
          try {
            const status = await A.auth.demoStatus();
            if (!status.enabled) {
              toast("Demo 模式未开启 (AGENTOS_DEMO_MODE=on)", "error");
              return;
            }
            const r = await A.auth.demoLogin();
            store.setToken(r.access_token);
            const me = await A.me();
            const meData = me.data || me;
            store.setUser(meData);
            state.me = meData;
            overlay.hidden = true;
            boot();
          } catch (e) {
            toast(`Demo 登录失败: ${e.message}`, "error");
          }
        },
      },
      "🚀 一键 Demo 登录",
    ),
    el("label", { class: "field" }, [
      el("div", { class: "field-label", text: "账号" }),
      usernameInput,
    ]),
    el("label", { class: "field" }, [
      el("div", { class: "field-label", text: "密码" }),
      passwordInput,
    ]),
    el("div", { class: "row" }, [
      el(
        "button",
        {
          class: "btn",
          style: "flex:1;justify-content:center;",
          onclick: async () => {
            try {
              const r = await A.auth.login(
                usernameInput.value.trim(),
                passwordInput.value,
              );
              store.setToken(r.access_token);
              const me = await A.me();
              const meData = me.data || me;
              store.setUser(meData);
              state.me = meData;
              overlay.hidden = true;
              boot();
            } catch (e) {
              toast(`登录失败: ${e.message}`, "error");
            }
          },
        },
        "登录",
      ),
      el(
        "button",
        {
          class: "btn btn-primary",
          style: "flex:1;justify-content:center;",
          onclick: async () => {
            const value = usernameInput.value.trim();
            const password = passwordInput.value;
            if (!value || !password) return toast("请填写账号密码", "error");
            const looksLikeEmail = value.includes("@");
            const username = looksLikeEmail
              ? value.split("@")[0].replace(/[^a-zA-Z0-9_]/g, "_") ||
                `mydow_${Date.now()}`
              : value;
            const email = looksLikeEmail ? value : `${username}@mydow.example`;
            try {
              const r = await A.auth.register({ username, email, password });
              store.setToken(r.access_token);
              const me = await A.me();
              store.setUser((me && (me.data || me)) || null);
              state.me = (me && (me.data || me)) || null;
              overlay.hidden = true;
              boot();
            } catch (e) {
              toast(`注册失败: ${e.message}`, "error");
            }
          },
        },
        "注册",
      ),
    ]),
  ]);
  overlay.appendChild(card);
}

// ─────────────────────────────────────────────  Job polling  ───────────

const _pollers = new Map();
function pollJob(jobId, opts = {}) {
  const start = Date.now();
  const tick = async () => {
    try {
      const r = await A.jobs.get(jobId);
      const job = r.data;
      if (job.status === "completed") {
        toast(opts.successMsg || "任务已完成", "success");
        renderPage();
        _pollers.delete(jobId);
        refreshUnread();
        return;
      }
      if (job.status === "failed") {
        toast(
          (opts.errorPrefix || "任务失败") +
            (job.error?.message ? `: ${job.error.message}` : ""),
          "error",
        );
        _pollers.delete(jobId);
        return;
      }
      if (job.status === "canceled") {
        toast("任务已取消", "info");
        _pollers.delete(jobId);
        return;
      }
      // queued / running — schedule next.
      const elapsed = (Date.now() - start) / 1000;
      const next = elapsed > 60 ? 5000 : 2000;
      _pollers.set(jobId, setTimeout(tick, next));
    } catch (e) {
      _pollers.delete(jobId);
    }
  };
  tick();
}

// ─────────────────────────────────────────────  Refresh helpers  ────────

async function refreshUnread() {
  try {
    const r = await A.notifications.unread();
    state.unread = (r.data && r.data.count) || 0;
    const badge = document.getElementById("notif-badge");
    if (badge) {
      if (state.unread > 0) badge.textContent = String(state.unread);
      else badge.remove();
    } else if (state.unread > 0) {
      const btn = document.querySelector('.icon-btn[title="通知"]');
      if (btn) {
        btn.appendChild(
          el(
            "span",
            { class: "badge-dot", id: "notif-badge" },
            String(state.unread),
          ),
        );
      }
    }
  } catch {
    /* ignore */
  }
}

// ─────────────────────────────────────────────  Boot  ──────────────────

async function tryDemoAutoLogin() {
  if (store.token()) return true;
  try {
    const status = await A.auth.demoStatus();
    if (!status.enabled) return false;
    const r = await A.auth.demoLogin();
    store.setToken(r.access_token);
    const me = await A.me();
    const meData = (me && (me.data || me)) || null;
    if (meData) store.setUser(meData);
    state.me = meData;
    console.info("[Mydow] Demo auto-login completed");
    return true;
  } catch (e) {
    return false;
  }
}

async function boot() {
  try {
    if (!store.token()) {
      const ok = await tryDemoAutoLogin();
      if (!ok) {
        renderAuthOverlay();
        return;
      }
    } else {
      try {
        const me = await A.me();
        state.me = (me && (me.data || me)) || null;
        if (state.me) store.setUser(state.me);
      } catch {
        store.clearSession();
        renderAuthOverlay();
        return;
      }
    }
    await loadLocale(resolveLocale());
    document.getElementById("auth-overlay").hidden = true;
    renderShell();
    await renderPage();
    refreshUnread();
    setInterval(refreshUnread, 30000);
  } catch (e) {
    document.getElementById("app").innerHTML = "";
    document.getElementById("app").appendChild(errorState(e));
  }
}

window.addEventListener("hashchange", () => {
  if (store.token()) renderPage();
  else {
    const region = document.getElementById("page-region");
    if (region) region.innerHTML = "";
    renderAuthOverlay();
  }
});

document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    openSearchPanel("");
  }
});

boot();

// ─────────────────────────────────────────────  Public surface  ─────────

window.MydowAPI = {
  apiBase: API_BASE,
  fetch: api,
  store,
  i18n: { t, loadLocale, setLocale, resolveLocale },
  navigate,
  state,
  pollJob,
  uiStates: {
    skeletonPage,
    emptyState,
    errorState,
    forbiddenState,
    processingState,
    successState,
  },
  // Domain clients (kept for tests / console).
  search: A.search,
  ai: A.ai,
  skills: A.skills,
  garden: A.garden,
  feed: { list: A.feed },
  cards: A.cards,
  kb: A.kb,
  capture: A.capture,
  inbox: A.inbox,
  notifications: A.notifications,
  jobs: A.jobs,
  tasks: A.tasks,
  today: { fetch: A.today },
  me: { fetch: A.me },
  auth: A.auth,
};
