// =============================================================================
// Mydow v1.4 prototype ↔ PRD10 backend bridge (§15.31 / §15.32).
//
// Injected by FastAPI before </body>. Uses capture-phase handlers so real
// `/api/v1/*` calls win over the prototype IIFE `simulateAction` toasts.
// =============================================================================

(function bootstrapV14() {
  "use strict";

  const API_BASE = "/api/v1";
  const TOKEN_KEY = "mydow_v14_token";
  const FLAG_KEY = "__MYDOW_V14_BRIDGE_BOOTED";

  if (window[FLAG_KEY]) return;

  /** @type {{
   *   notifFilter: string,
   *   activeSkillId: string,
   *   aiConvId: string|null,
   *   streamAbort: AbortController|null,
   *   allFolders: any[],
   *   aiModel: string,
   *   contextScope: {
   *     document_ids: string[],
   *     folder_ids: string[],
   *     sources: { type: string, label: string, ref?: string }[],
   *     notes: string[]
   *   },
   *   contextDocsCache: Record<string, { id: string, title: string, folder_id?: string }>,
   *   contextFoldersCache: Record<string, { id: string, title: string }>,
   *   skillRunDoneIds: Record<string, string>,
   *   allSkills: any[],
   *   activeSkillFilter: string,
   * }} */
  const V14 = {
    notifFilter: "all",
    activeSkillId: "",
    aiConvId: null,
    streamAbort: null,
    allFolders: [],
    gardenLayout: 0,
    gardenZoom: 1,
    /** Assistant message UUID from SSE ``event: meta`` (save-to-kb). */
    lastAssistantMessageId: "",
    /** §15.37 selected AI model name (Mydow Auto / Opus 4.6 / Gemini 2.5 Flash / GPT-5.2). */
    aiModel: "Mydow Auto",
    /** §16.4 — current conversation's pinned context (mirrors backend conv.context_scope). */
    contextScope: { document_ids: [], folder_ids: [], sources: [], notes: [] },
    /** §16.4 — cached doc summaries for chip rendering ({id → {id,title,folder_id}}). */
    contextDocsCache: {},
    /** §18.3 — cached folder summaries for AI context chips. */
    contextFoldersCache: {},
    /** §16.6 — skill id → saved document id (or "1" if none) after a completed run. */
    skillRunDoneIds: {},
    /** §18.8 — full real `/skills` cache used by the category chips. */
    allSkills: [],
    /** §18.8 — current Skills filter label, synced to the URL hash. */
    activeSkillFilter: "",
  };

  const INSIGHT_TAG_LABELS_V14 = {
    theme_trend: "趋势洞察",
    task_risk: "风险洞察",
    knowledge_gap: "缺口洞察",
    connection: "关联洞察",
    daily_summary: "日报",
    weekly_summary: "周报",
    monthly_summary: "月报",
  };

  const INSIGHT_ICON_HREFS_V14 = {
    theme_trend: "#icon-user",
    task_risk: "#icon-bookmark",
    knowledge_gap: "#icon-book",
    connection: "#icon-link",
    daily_summary: "#icon-cube",
    weekly_summary: "#icon-cube",
    monthly_summary: "#icon-cube",
  };

  function escapeHtmlV14(s) {
    const t = String(s == null ? "" : s);
    return t
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatReportDateV14(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleDateString("zh-CN", { month: "long", day: "numeric" });
  }

  // ─── toast ───────────────────────────────────────────────────────────────
  function toast(message, kind) {
    kind = kind || "info";
    const stack =
      document.querySelector("[data-toast-stack]") ||
      document.querySelector(".toast-stack");
    if (!stack) {
      console.info("[Mydow v1.4]", message);
      return;
    }
    const node = document.createElement("div");
    node.className = "toast toast-" + kind;
    const icon = document.createElement("span");
    icon.style.cssText =
      "display:inline-grid;place-items:center;width:26px;height:26px;border-radius:9px;background:rgba(112,140,255,0.12);color:#5b78ff;font-weight:700;font-size:12px;";
    icon.textContent = kind === "error" ? "!" : kind === "warning" ? "△" : "✓";
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
  }

  function closeV14Layers() {
    document.querySelectorAll(".surface-layer[data-modal], .drawer-layer[data-drawer]").forEach((layer) => {
      if (!layer.hidden) {
        layer.classList.remove("is-open", "is-leaving", "is-instant");
        layer.hidden = true;
      }
    });
    document.body.classList.remove("layer-lock");
  }

  // ─── token / fetch ───────────────────────────────────────────────────────
  function getToken() {
    return window.localStorage.getItem(TOKEN_KEY) || "";
  }
  function setToken(value) {
    if (value) window.localStorage.setItem(TOKEN_KEY, value);
    else window.localStorage.removeItem(TOKEN_KEY);
  }

  function unwrapData(payload) {
    if (!payload) return {};
    if (payload.success === true && payload.data !== undefined) return payload.data;
    if (payload.code === 0 && payload.data !== undefined) return payload.data;
    return payload;
  }

  async function apiFetch(path, options) {
    options = options || {};
    const headers = {
      "Content-Type": "application/json",
      "X-Client-Platform": "web",
      "X-Client-Version": "1.4.0",
    };
    const tok = getToken();
    if (tok) headers["Authorization"] = "Bearer " + tok;
    const init = {
      method: options.method || "GET",
      headers: Object.assign(headers, options.headers || {}),
      cache: "no-store",
    };
    if (options.body !== undefined) {
      init.body = typeof options.body === "string"
        ? options.body
        : JSON.stringify(options.body);
    }
    const resp = await fetch(API_BASE + path, init);
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
        resp.statusText ||
        "请求失败";
      const err = new Error(msg);
      err.status = resp.status;
      err.payload = payload;
      throw err;
    }
    return payload;
  }

  /**
   * §15.31：v1.4 契约路径 → PRD10，并把 `{success,data,request_id}` 投影为
   * `{code,message,data,requestId}`（不改后端）。
   */
  function toV14ContractEnvelope(raw) {
    if (!raw || typeof raw !== "object") return raw;
    if ("success" in raw) {
      return {
        code: raw.success === true ? 0 : 1,
        message: raw.message || (raw.success === true ? "ok" : "error"),
        data: raw.data,
        requestId: raw.request_id || raw.requestId,
      };
    }
    return raw;
  }

  function translateV14GetPath(pathWithQuery) {
    const qi = pathWithQuery.indexOf("?");
    const rawPath = qi >= 0 ? pathWithQuery.slice(0, qi) : pathWithQuery;
    const search = qi >= 0 ? pathWithQuery.slice(qi + 1) : "";
    let p = rawPath.replace(/^\/api\/v1/, "") || "/";
    if (!p.startsWith("/")) p = "/" + p;
    const incoming = new URLSearchParams(search);

    if (p === "/capture/items") {
      const out = new URLSearchParams();
      out.set("page", incoming.get("page") || "1");
      out.set(
        "page_size",
        incoming.get("pageSize") || incoming.get("page_size") || "20",
      );
      const t = incoming.get("type");
      if (t && t !== "all") out.set("type", t);
      const kw = incoming.get("keyword");
      if (kw) out.set("tag", kw);
      return "/feed?" + out.toString();
    }
    if (p === "/insights/dashboard" || p === "/insights/history") {
      return "/insights/summary?range=week";
    }
    const docm = p.match(/^\/kb\/docs\/([^/?]+)$/);
    if (docm) return "/kb/documents/" + docm[1] + (search ? "?" + search : "");
    if (p === "/ai/chats") {
      const out = new URLSearchParams(search);
      const ps = out.get("pageSize");
      if (ps) {
        out.set("page_size", ps);
        out.delete("pageSize");
      }
      if (!out.has("page_size")) out.set("page_size", "20");
      return "/ai/conversations?" + out.toString();
    }
    if (p === "/settings/preferences") return "/me/preferences";
    const rel = pathWithQuery.startsWith("/api/v1")
      ? pathWithQuery.slice(7)
      : pathWithQuery;
    return rel.startsWith("/") ? rel : "/" + rel;
  }

  function translateV14WritePath(path, body, method) {
    let p = path.replace(/^\/api\/v1/, "") || "/";
    if (!p.startsWith("/")) p = "/" + p;
    const b = body && typeof body === "object" ? body : {};
    if (p === "/capture/items") {
      return {
        path: "/capture/text",
        body: {
          content: b.content || b.text || "",
          auto_process: b.auto_process !== false,
        },
      };
    }
    if (p === "/ai/chats" && method === "POST") {
      return {
        path: "/ai/conversations",
        body: { title: b.title || "新的对话", mode: b.mode || "general" },
      };
    }
    if (p === "/ai/messages" && b.chatId) {
      return {
        path: "/ai/conversations/" + b.chatId + "/messages",
        body: { content: b.content },
      };
    }
    const rel = p;
    return { path: rel, body };
  }

  async function apiFetchV14(pathWithQuery, options) {
    options = options || {};
    const method = (options.method || "GET").toUpperCase();
    let full = pathWithQuery;
    if (!full.startsWith("/")) full = "/" + full;
    if (full.startsWith("/api/v1")) full = full.slice(7);
    let fetchPath;
    let body = options.body;
    if (method === "GET") {
      fetchPath = translateV14GetPath(full);
    } else {
      const tw = translateV14WritePath(full, body, method);
      fetchPath = tw.path;
      body = tw.body;
    }
    const raw = await apiFetch(fetchPath, Object.assign({}, options, { body }));
    return toV14ContractEnvelope(raw);
  }

  async function rawFetch(path, init) {
    const headers = Object.assign({}, init.headers || {});
    const tok = getToken();
    if (tok && !headers["Authorization"]) headers["Authorization"] = "Bearer " + tok;
    return fetch(API_BASE + path, Object.assign({ cache: "no-store" }, init, { headers }));
  }

  async function fetchAiStreamWithSession(path, body, signal) {
    await ensureSession();
    const buildInit = () => {
      const headers = {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      };
      const tok = getToken();
      if (tok) headers.Authorization = "Bearer " + tok;
      return {
        method: "POST",
        headers,
        body: JSON.stringify(body),
        signal,
        cache: "no-store",
      };
    };
    let resp = await fetch(API_BASE + path, buildInit());
    if (resp.status === 401) {
      setToken("");
      const refreshed = await ensureSession();
      if (refreshed) resp = await fetch(API_BASE + path, buildInit());
    }
    return resp;
  }

  async function ensureSession() {
    if (getToken()) {
      try {
        const me = await apiFetch("/me");
        if (me && (me.success === true || me.data || me.id)) return true;
      } catch (e) {
        if (e.status !== 401) {
          console.warn("[Mydow v1.4] /me failed", e);
          return true;
        }
        setToken("");
      }
    }
    let status;
    try {
      status = await apiFetch("/demo/status");
    } catch (e) {
      console.warn("[Mydow v1.4] /demo/status failed", e);
      return false;
    }
    const enabled = (status && status.data && status.data.enabled) ||
                    (status && status.enabled);
    if (!enabled) return false;
    let login;
    try {
      login = await apiFetch("/demo/login", { method: "POST", body: {} });
    } catch (e) {
      console.warn("[Mydow v1.4] /demo/login failed", e);
      return false;
    }
    const access =
      (login && login.access_token) ||
      (login && login.data && login.data.access_token) ||
      null;
    if (!access) return false;
    setToken(access);
    return true;
  }

  // ─── profile ─────────────────────────────────────────────────────────────
  async function refreshProfileChip() {
    let me;
    try {
      me = await apiFetch("/me");
    } catch (e) {
      console.warn("[Mydow v1.4] /me lookup failed", e);
      return null;
    }
    const data = unwrapData(me) || {};
    window._BIZ_V14_ME_CACHE = data;
    const name =
      data.name ||
      (data.email && String(data.email).split("@")[0]) ||
      "demo";
    const plan = data.plan || "free";
    const planLabel =
      plan === "pro" ? "Pro Plan" : plan === "team" ? "Team Plan" : "Free Plan";
    const chip = document.querySelector(".account[data-open-profile]");
    if (chip) {
      const strong = chip.querySelector(".account-info strong");
      const span = chip.querySelector(".account-info span");
      if (strong) strong.textContent = "你好，" + name;
      if (span) span.textContent = planLabel;
      chip.dataset.bridgeBound = "true";
    }
    window.dispatchEvent(
      new CustomEvent("mydow:v14:me-loaded", { detail: { me: data } }),
    );
    return data;
  }

  // ─── §16.4 AI conversation context (pin docs / chips / scope sync) ──────
  /**
   * Detect whether the user is currently on the AI workspace surface so that
   * uploads / web links / newly created docs can opt-in to conversation
   * context pinning. We check three signals: hash, page class, and the
   * presence of an active conversation id on `V14`.
   *
   * @returns {boolean}
   */
  function isAiWorkspaceActive() {
    const isVisible = (el) => {
      if (!el) return false;
      const rect = el.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return false;
      const style = window.getComputedStyle(el);
      return style.display !== "none" && style.visibility !== "hidden" && style.opacity !== "0";
    };
    try {
      const hash = (window.location.hash || "").toLowerCase();
      if (hash.includes("/ai") || hash.startsWith("#/ai")) return true;
    } catch (_e) {
      /* ignore */
    }
    const page = document.querySelector(".page");
    if (page && page.className && /\bai-(open|history-open|chat-open)\b/.test(page.className)) {
      return true;
    }
    if (V14.aiConvId && isVisible(document.querySelector(".ai-main, .ai-workspace-canvas"))) {
      // A remembered conversation id should only pin when the AI workspace is
      // actually visible; hidden composer DOM exists on other pages too.
      return true;
    }
    return false;
  }

  /**
   * Backend PATCH replaces `context_scope` wholesale — merge in notes /
   * include_recent already on the conversation so pinning never wipes §15.39
   * modal state.
   */
  function mergedContextScopeV16(patch) {
    const base = V14.contextScope || {};
    const out = {
      document_ids:
        patch.document_ids != null
          ? patch.document_ids.map(String)
          : (base.document_ids || []).map(String),
      folder_ids:
        patch.folder_ids != null ? patch.folder_ids.map(String) : (base.folder_ids || []).map(String),
      sources:
        patch.sources != null
          ? patch.sources
          : Array.isArray(base.sources)
            ? base.sources.slice()
            : [],
      notes:
        patch.notes != null
          ? patch.notes.slice()
          : Array.isArray(base.notes)
            ? base.notes.slice()
            : [],
    };
    const inc =
      patch.include_recent != null ? patch.include_recent : base.include_recent;
    if (typeof inc === "boolean") {
      out.include_recent = inc;
    }
    return out;
  }

  /**
   * Patch the active AI conversation's `context_scope` so the next user
   * message includes the document as RAG context. Idempotent: if the doc id
   * is already present, no PATCH is fired (returns "already_pinned"). Mirrors
   * `V14.contextScope` and `V14.contextDocsCache` so the chip strip can
   * render without an extra round trip.
   *
   * @param {{id:string,title:string,folder_id?:string|null,kind?:string}} doc
   * @returns {Promise<{ok:true,added:boolean}>}
   */
  async function pinDocumentToActiveConversation(doc) {
    if (!doc || !doc.id) throw new Error("doc.id 缺失");
    const cid = V14.aiConvId;
    if (!cid) {
      // Caller is responsible for opening / creating a conversation first.
      throw new Error("当前没有活跃的 AI 对话，无法附加文档");
    }
    const docId = String(doc.id);
    const existing = (V14.contextScope.document_ids || []).map(String);
    if (existing.includes(docId)) {
      return { ok: true, added: false };
    }
    const nextDocIds = [...existing, docId];
    const folderIds = (V14.contextScope.folder_ids || []).map(String);
    const sources = Array.isArray(V14.contextScope.sources) ? V14.contextScope.sources.slice() : [];
    sources.push({
      type: "doc",
      label: String(doc.title || "未命名文档"),
      ref: docId,
    });
    const body = {
      context_scope: mergedContextScopeV16({
        document_ids: nextDocIds,
        folder_ids: folderIds,
        sources,
      }),
    };
    await apiFetch("/ai/conversations/" + cid, { method: "PATCH", body });
    V14.contextScope.document_ids = nextDocIds;
    V14.contextScope.sources = sources;
    V14.contextDocsCache[docId] = {
      id: docId,
      title: String(doc.title || "未命名文档"),
      folder_id: doc.folder_id != null ? String(doc.folder_id) : null,
      kind: doc.kind || "doc",
    };
    renderContextChipsV16();
    return { ok: true, added: true };
  }

  /**
   * Reverse of `pinDocumentToActiveConversation`. Removes the doc id from
   * the conversation's `context_scope` and the local cache.
   *
   * @param {string} docId
   */
  async function unpinDocumentFromActiveConversation(docId) {
    const cid = V14.aiConvId;
    const id = String(docId || "");
    if (!cid || !id) return;
    const cur = (V14.contextScope.document_ids || []).map(String);
    if (!cur.includes(id)) return;
    const next = cur.filter((x) => x !== id);
    const folderIds = (V14.contextScope.folder_ids || []).map(String);
    try {
      await apiFetch("/ai/conversations/" + cid, {
        method: "PATCH",
        body: {
          context_scope: mergedContextScopeV16({
            document_ids: next,
            folder_ids: folderIds,
            sources: (V14.contextScope.sources || []).filter(
              (s) => !(s && String(s.ref) === id),
            ),
          }),
        },
      });
      V14.contextScope.document_ids = next;
      V14.contextScope.sources = (V14.contextScope.sources || []).filter(
        (s) => !(s && s.ref === id),
      );
      delete V14.contextDocsCache[id];
      renderContextChipsV16();
    } catch (e) {
      toast("移除上下文失败：" + e.message, "error");
    }
  }

  async function unpinFolderFromActiveConversation(folderId) {
    const cid = V14.aiConvId;
    const id = String(folderId || "");
    if (!cid || !id) return;
    const folderIds = (V14.contextScope.folder_ids || []).map(String);
    if (!folderIds.includes(id)) return;
    const nextFolderIds = folderIds.filter((x) => x !== id);
    try {
      await apiFetch("/ai/conversations/" + cid, {
        method: "PATCH",
        body: {
          context_scope: mergedContextScopeV16({
            document_ids: (V14.contextScope.document_ids || []).map(String),
            folder_ids: nextFolderIds,
            sources: (V14.contextScope.sources || []).filter(
              (s) => !(s && String(s.ref) === id),
            ),
          }),
        },
      });
      V14.contextScope.folder_ids = nextFolderIds;
      V14.contextScope.sources = (V14.contextScope.sources || []).filter(
        (s) => !(s && String(s.ref) === id),
      );
      delete V14.contextFoldersCache[id];
      renderContextChipsV16();
    } catch (e) {
      toast("移除上下文失败：" + e.message, "error");
    }
  }

  /**
   * Render the in-composer chip strip showing all pinned documents so users
   * always know what RAG context the next prompt will see. Each chip has an
   * `×` button wired to `unpinDocumentFromActiveConversation`. We inject the
   * strip lazily above each `.ai-composer`.
   */
  function renderContextChipsV16() {
    const composers = document.querySelectorAll(
      ".ai-composer, .ai-chat-composer",
    );
    composers.forEach((composer) => {
      let strip = composer.querySelector("[data-v16-context-strip]");
      const ids = (V14.contextScope.document_ids || []).map(String);
      const folderIds = (V14.contextScope.folder_ids || []).map(String);
      if (ids.length === 0 && folderIds.length === 0) {
        if (strip) strip.remove();
        return;
      }
      if (!strip) {
        strip = document.createElement("div");
        strip.dataset.v16ContextStrip = "true";
        strip.setAttribute("aria-label", "已附加上下文");
        strip.style.cssText = [
          "display:flex",
          "flex-wrap:wrap",
          "gap:6px",
          "padding:6px 10px 4px",
          "border-bottom:1px dashed rgba(108,124,153,0.18)",
          "max-height:90px",
          "overflow-y:auto",
        ].join(";");
        composer.insertBefore(strip, composer.firstChild);
      }
      strip.innerHTML = "";
      const appendChip = (id, meta, kind) => {
        const chip = document.createElement("button");
        chip.type = "button";
        if (kind === "folder") chip.dataset.contextFolderId = id;
        else chip.dataset.contextDocId = id;
        chip.title = `已附加：${meta.title}`;
        chip.style.cssText = [
          "display:inline-flex",
          "align-items:center",
          "gap:6px",
          "padding:4px 10px",
          "border-radius:999px",
          "background:rgba(117,140,255,0.14)",
          "border:1px solid rgba(117,140,255,0.32)",
          "color:#3548a6",
          "font-size:12px",
          "cursor:pointer",
          "max-width:min(280px,100%)",
          "min-width:0",
          "flex:0 1 auto",
        ].join(";");
        chip.innerHTML = `
          <svg class="icon" style="width:12px;height:12px;"><use href="${kind === "folder" ? "#icon-folder" : "#icon-link"}" /></svg>
          <span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtmlV14(meta.title)}</span>
          <span aria-hidden="true" style="opacity:0.6;font-weight:600;">×</span>
        `;
        chip.addEventListener("click", (ev) => {
          ev.preventDefault();
          ev.stopPropagation();
          if (kind === "folder") unpinFolderFromActiveConversation(id);
          else unpinDocumentFromActiveConversation(id);
        });
        strip.appendChild(chip);
      };
      ids.forEach((docId) => {
        const meta = V14.contextDocsCache[docId] || { id: docId, title: docId.slice(0, 8) };
        appendChip(docId, meta, "doc");
      });
      folderIds.forEach((folderId) => {
        const meta = V14.contextFoldersCache[folderId] || { id: folderId, title: folderId.slice(0, 8) };
        appendChip(folderId, meta, "folder");
      });
    });
  }

  function injectAiComposerLayoutFixV18() {
    if (document.getElementById("mydow-ai-composer-layout-fix-v18")) return;
    const style = document.createElement("style");
    style.id = "mydow-ai-composer-layout-fix-v18";
    style.textContent = `
      .ai-composer,
      .ai-chat-composer {
        box-sizing: border-box;
        min-width: 0;
      }
      .ai-composer [data-v16-context-strip],
      .ai-chat-composer [data-v16-context-strip],
      .ai-context-chips {
        max-width: 100%;
        min-width: 0;
      }
      .ai-composer [data-v16-context-strip] button,
      .ai-chat-composer [data-v16-context-strip] button,
      .ai-context-chip {
        max-width: min(280px, 100%);
        min-width: 0;
        flex: 0 1 auto;
      }
      .ai-composer [data-v16-context-strip] button span:first-of-type,
      .ai-chat-composer [data-v16-context-strip] button span:first-of-type,
      .ai-context-chip span {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .page.ai-chat-open .ai-chat-composer {
        display: grid !important;
        grid-template-columns: auto 1fr !important;
        grid-template-areas:
          "tools tools"
          "actions input" !important;
        align-items: end !important;
        gap: 8px 10px !important;
        padding: 10px 12px 10px !important;
        width: min(760px, calc(100% - 48px)) !important;
        border-radius: 20px !important;
      }
      .page.ai-chat-open .ai-chat-composer [data-v16-context-strip],
      .page.ai-chat-open .ai-chat-composer .ai-chat-inline-tools {
        grid-area: tools !important;
        display: flex !important;
        width: 100%;
        min-width: 0;
        max-width: 100%;
        overflow-x: auto;
        overflow-y: hidden;
        flex-wrap: nowrap !important;
        padding-bottom: 2px;
        scrollbar-width: none;
      }
      .page.ai-chat-open .ai-chat-composer [data-v16-context-strip] {
        margin-bottom: 0;
      }
      .page.ai-chat-open .ai-chat-composer [data-v16-context-strip]::-webkit-scrollbar,
      .page.ai-chat-open .ai-chat-composer .ai-chat-inline-tools::-webkit-scrollbar {
        display: none;
      }
      .page.ai-chat-open .ai-chat-composer .ai-chat-inline-tools > *,
      .page.ai-chat-open .ai-chat-composer [data-v16-context-strip] > * {
        flex: 0 0 auto;
      }
      .ai-chat-composer textarea.ai-input,
      .ai-composer textarea.ai-input {
        display: block;
        width: 100%;
        min-width: 0;
        max-height: 180px;
        overflow-y: auto;
        box-sizing: border-box;
      }
      .page.ai-chat-open .ai-chat-composer textarea.ai-input {
        grid-area: input !important;
        min-height: 44px !important;
        height: auto !important;
        padding: 10px 8px !important;
        line-height: 1.45 !important;
        resize: none;
        align-self: center !important;
      }
      .ai-chat-composer .submit-row,
      .ai-chat-composer .ai-tools,
      .ai-composer .submit-row,
      .ai-composer .ai-tools {
        min-width: 0;
        flex-wrap: wrap;
      }
      .page.ai-chat-open .ai-chat-composer .submit-row {
        grid-area: actions !important;
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
        flex-wrap: nowrap !important;
        align-self: center !important;
        min-width: max-content;
      }
      @media (min-width: 900px) {
        .page.ai-chat-open .ai-chat-composer {
          position: sticky !important;
          left: auto !important;
          right: auto !important;
          bottom: 20px !important;
          transform: none !important;
          width: min(920px, calc(100vw - 96px)) !important;
          margin: 18px auto 0 !important;
          align-self: stretch;
          z-index: 12;
        }
      }
      .page.ai-chat-open .ai-workspace-canvas {
        display: flex;
        flex-direction: column;
        min-height: min(780px, calc(100vh - 120px));
      }
      .page.ai-chat-open .ai-conversation-view {
        flex: 1 1 auto;
        min-height: 0;
        padding-bottom: 18px;
      }
      .page.ai-chat-open .ai-chat-composer {
        flex: 0 0 auto;
        max-width: calc(100% - 28px);
      }
      .v20-select-shell {
        position: relative;
      }
      .v20-select-shell select {
        appearance: none;
        -webkit-appearance: none;
        width: 100%;
        border: 1px solid rgba(91,120,255,.18);
        border-radius: 14px;
        background:
          linear-gradient(180deg, rgba(255,255,255,.92), rgba(246,248,255,.9));
        box-shadow: 0 12px 34px rgba(30,45,95,.08);
        color: #263652;
        font-weight: 650;
        padding: 12px 42px 12px 14px;
        outline: none;
      }
      .v20-select-shell::after {
        content: "";
        position: absolute;
        right: 16px;
        top: 50%;
        width: 8px;
        height: 8px;
        border-right: 2px solid #6e7f9d;
        border-bottom: 2px solid #6e7f9d;
        transform: translateY(-65%) rotate(45deg);
        pointer-events: none;
      }
    `;
    document.head.appendChild(style);
  }

  /**
   * Pull the active conversation's `context_scope` from the backend and seed
   * `V14.contextScope` + `V14.contextDocsCache`. Called whenever the user
   * switches conversation, opens an AI thread, or completes pinning. Best-
   * effort: a missing conv simply clears the local state.
   */
  async function loadActiveConversationContextScope() {
    const cid = V14.aiConvId;
    if (!cid) {
      V14.contextScope = { document_ids: [], folder_ids: [], sources: [], notes: [] };
      V14.contextDocsCache = {};
      V14.contextFoldersCache = {};
      renderContextChipsV16();
      return;
    }
    let detail;
    try {
      const resp = await apiFetch("/ai/conversations/" + cid);
      detail = unwrapData(resp) || resp || {};
    } catch (e) {
      console.warn("[Mydow v1.4] context_scope hydrate failed", e);
      return;
    }
    const conv = detail.conversation || detail || {};
    const scope = (conv.context_scope || {}) || {};
    V14.contextScope = {
      document_ids: (scope.document_ids || []).map(String),
      folder_ids: (scope.folder_ids || []).map(String),
      sources: Array.isArray(scope.sources) ? scope.sources.slice() : [],
      notes: Array.isArray(scope.notes) ? scope.notes.slice() : [],
    };
    V14.contextFoldersCache = {};
    V14.contextScope.sources.forEach((src) => {
      if (!src || typeof src !== "object") return;
      if (src.type === "folder" && src.ref) {
        V14.contextFoldersCache[String(src.ref)] = {
          id: String(src.ref),
          title: String(src.label || "知识库文件夹"),
        };
      }
    });
    // Hydrate doc cache so chips render with real titles.
    const ids = V14.contextScope.document_ids;
    if (ids.length > 0) {
      try {
        const resp = await apiFetch(
          "/kb/documents?page_size=" + Math.max(20, ids.length * 2),
        );
        const items = (unwrapData(resp)?.items) || [];
        items.forEach((d) => {
          const id = String(d.id);
          if (ids.includes(id)) {
            V14.contextDocsCache[id] = {
              id,
              title: d.title || "未命名文档",
              folder_id: d.folder_id != null ? String(d.folder_id) : null,
              kind: "doc",
            };
          }
        });
      } catch (_e) {
        /* ignore — chips will fall back to id slices */
      }
    }
    const folderIds = V14.contextScope.folder_ids;
    if (folderIds.length > 0) {
      try {
        const resp = await apiFetch("/kb/folders?include_counts=true");
        const items = (unwrapData(resp)?.items) || [];
        items.forEach((f) => {
          const id = String(f.id);
          if (folderIds.includes(id)) {
            V14.contextFoldersCache[id] = {
              id,
              title: String(f.name || "知识库文件夹"),
            };
          }
        });
      } catch (_e) {
        /* best effort; source labels already cover most cases */
      }
    }
    renderContextChipsV16();
  }

  // Re-hydrate chips whenever the active conversation flips (set elsewhere).
  function bindAiConvIdWatcher() {
    let last = V14.aiConvId;
    setInterval(() => {
      if (V14.aiConvId !== last) {
        last = V14.aiConvId;
        loadActiveConversationContextScope().catch(() => {});
      }
    }, 800);
  }

  /** §16.4 — 「新建空白文档」快捷入口：`POST /kb/documents` blank + patch ctx. */
  async function createBlankDocAndPinAsContextV16() {
    try {
      const cid = await ensureAiConversationId();
      if (!cid) throw new Error("无法确定 AI 会话");
      const resp = await apiFetch("/kb/documents", {
        method: "POST",
        body: {
          title:
            "AI 草稿 · " +
            new Date().toLocaleTimeString("zh-CN", {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            }),
          template: "blank",
          document_type: "markdown",
          tags: [],
        },
      });
      const data = unwrapData(resp) || resp || {};
      const newDocId = data.id || data.document_id;
      if (!newDocId) throw new Error("未返回文档 ID");
      await pinDocumentToActiveConversation({
        id: String(newDocId),
        title: data.title || "AI 草稿",
        folder_id: data.folder_id != null ? data.folder_id : null,
        kind: "doc",
      });
      toast("已新建空白文档并附加为上下文", "success");
      await loadKbLibraryGrid().catch(() => {});
    } catch (e) {
      throw e instanceof Error ? e : new Error(String(e));
    }
  }

  // ─── upload / capture modals ─────────────────────────────────────────────
  async function uploadAndCommitFile(file) {
    const mimeType = file.type || "application/octet-stream";
    const presign = await apiFetch("/uploads/presign", {
      method: "POST",
      body: {
        filename: file.name,
        mime_type: mimeType,
        size_bytes: file.size,
      },
    });
    const presignData = unwrapData(presign) || presign || {};
    const uploadId = presignData.upload_id;
    const uploadUrl = presignData.upload_url;
    if (!uploadId || !uploadUrl) throw new Error("presign 未返回 upload_id / upload_url");

    const putResp = await fetch(uploadUrl, {
      method: "PUT",
      headers: Object.assign(
        { "Content-Type": mimeType },
        getToken() ? { Authorization: "Bearer " + getToken() } : {},
      ),
      body: file,
    });
    if (!putResp.ok) throw new Error(`上传失败：${putResp.status}`);

    return apiFetch("/capture/file/commit", {
      method: "POST",
      body: {
        upload_id: uploadId,
        filename: file.name,
        mime_type: mimeType,
        size_bytes: file.size,
        auto_process: true,
      },
    });
  }

  async function handleUploadFileModal(button, layer) {
    let input = layer.querySelector('input[type="file"][data-v14-upload]');
    if (!input) {
      input = document.createElement("input");
      input.type = "file";
      input.setAttribute("data-v14-upload", "true");
      input.style.display = "none";
      layer.appendChild(input);
    }
    input.value = "";
    const file = await new Promise((resolve) => {
      const onChange = () => {
        input.removeEventListener("change", onChange);
        resolve(input.files && input.files[0] ? input.files[0] : null);
      };
      input.addEventListener("change", onChange);
      input.click();
    });
    if (!file) {
      toast("没有选择文件", "warning");
      return;
    }
    button.disabled = true;
    button.classList.add("is-loading");
    try {
      const commitResp = await uploadAndCommitFile(file);
      // §16.4 — when on AI workspace, pin the freshly uploaded document
      // into the active conversation's context_scope so the next prompt
      // RAG-cites it. We do this best-effort: missing conv / 4xx → just
      // toast and skip; never block the upload success path.
      const commitData = unwrapData(commitResp) || commitResp || {};
      const newDocId = commitData.document_id ? String(commitData.document_id) : "";
      const onAiPage = isAiWorkspaceActive();
      if (newDocId && onAiPage) {
        try {
          await ensureAiConversationId();
          const cached = {
            id: newDocId,
            title: commitData.title || file.name,
            folder_id: commitData.folder_id || null,
            kind: "upload",
          };
          await pinDocumentToActiveConversation(cached);
          toast("已添加为上下文：" + cached.title, "success");
        } catch (pinErr) {
          console.warn("[Mydow v1.4] pin upload to ctx failed", pinErr);
          toast("已上传（添加上下文失败，可手动 @ 引用）", "warning");
        }
      } else {
        toast("已上传，正在整理", "success");
      }
      closeV14Layers();
      await loadFeedCards();
      await loadFeedIntoRecordsTable();
      await refreshNotificationBadge();
    } catch (e) {
      toast("上传失败: " + e.message, "error");
    } finally {
      button.disabled = false;
      button.classList.remove("is-loading");
    }
  }

  async function handleWebLinkModal(button, layer) {
    const inp = layer.querySelector("input");
    const url = (inp && inp.value.trim()) || "";
    if (!url) {
      toast("请先填入网页 URL", "warning");
      return;
    }
    button.disabled = true;
    button.classList.add("is-loading");
    try {
      const resp = await apiFetch("/capture/link", {
        method: "POST",
        body: { url, auto_process: true },
      });
      const data = unwrapData(resp) || resp || {};
      if (data.fetch_status === "failed") {
        const jobError = data.job?.error;
        const msg =
          data.fetch_error ||
          (jobError && (jobError.message || jobError.code)) ||
          data.job?.message ||
          "网页抓取失败";
        throw new Error(
          msg + (data.status_code ? "（HTTP " + data.status_code + "）" : ""),
        );
      }
      // §16.4 — when on AI workspace, pin the link's resulting card/doc
      // into the active conversation's context_scope so RAG sees it.
      const onAi = isAiWorkspaceActive();
      const docId = data.document_id || (data.card && data.card.document_id) || "";
      if (onAi && docId) {
        try {
          await ensureAiConversationId();
          await pinDocumentToActiveConversation({
            id: String(docId),
            title: data.title || data.card?.title || url,
            folder_id: data.folder_id || null,
            kind: "link",
          });
          toast("网页已保存并附加为 AI 上下文", "success");
        } catch (pinErr) {
          console.warn("[Mydow v1.4] pin link to ctx failed", pinErr);
          toast("网页已保存（自动附加上下文失败）", "warning");
        }
      } else {
        toast("网页已保存", "success");
      }
      closeV14Layers();
      await loadFeedCards();
      await loadFeedIntoRecordsTable();
      await loadKbLibraryGrid().catch(() => {});
      if (docId && !onAi) {
        toast("网页正文已抓取并保存为知识库文档", "success");
        await openKbDocumentEditorV20(docId);
      } else if (data.card) {
        revealItemDetailDrawerV18(data.card);
      } else if (data.card_id) {
        const detail = await loadCardForDrawer(String(data.card_id));
        if (detail) revealItemDetailDrawerV18(detail);
      }
    } catch (e) {
      toast("剪藏失败: " + e.message, "error");
      const preview = layer.querySelector(".form-field textarea, .form-field .preview, .modal-body textarea");
      if (preview && "value" in preview) {
        preview.value = "剪藏失败：" + e.message;
      }
      const previewText = layer.querySelector(".state-card p");
      if (previewText) previewText.textContent = "剪藏失败：" + e.message;
    } finally {
      button.disabled = false;
      button.classList.remove("is-loading");
    }
  }

  async function handleDeepResearchModal(button, layer) {
    const topic = layer.querySelector("input")?.value.trim() || "";
    const scope = layer.querySelector("select")?.value || "";
    const output = layer.querySelector("textarea")?.value.trim() || "";
    if (!topic) {
      toast("请填写研究主题", "warning");
      return;
    }
    button.disabled = true;
    button.classList.add("is-loading");
    try {
      const resp = await apiFetch("/research/tasks", {
        method: "POST",
        body: { topic, scope, output, include_sources: true, save_to_kb: true },
      });
      const data = unwrapData(resp) || resp || {};
      const conv = await apiFetch("/ai/conversations", {
        method: "POST",
        body: { title: data.title || "深度研究：" + topic, mode: "report" },
      });
      const cdata = unwrapData(conv) || conv || {};
      const cid = cdata.id || cdata.conversation_id;
      if (cid && data.summary) {
        await apiFetch(`/ai/conversations/${cid}/messages`, {
          method: "POST",
          body: { content: `${data.title || "深度研究：" + topic}\n\n${data.summary}` },
        });
      }
      toast(data.used_llm ? "深度研究报告已生成" : "深度研究已基于真实资料生成（LLM 未启用）", data.used_llm ? "success" : "warning");
      closeV14Layers();
      await loadAiConversations();
      await loadKbLibraryGrid();
      await refreshInsightsFullV14();
      await refreshNotificationBadge();
    } catch (e) {
      toast("研究创建失败: " + e.message, "error");
    } finally {
      button.disabled = false;
      button.classList.remove("is-loading");
    }
  }

  let voiceRecognitionV18 = null;

  function hydrateVoiceInputModalV18(layer) {
    if (!layer || layer.dataset.v18VoiceHydrated === "true") return;
    const panel = layer.querySelector(".voice-panel");
    if (!panel) return;
    layer.dataset.v18VoiceHydrated = "true";
    panel.innerHTML = `
      <div class="voice-wave" aria-hidden="true"><span></span><span></span><span></span><span></span><span></span><span></span><span></span></div>
      <strong data-v18-voice-status>准备听写</strong>
      <p style="margin:0;color:#7d8aa0">可使用浏览器语音识别，或直接粘贴已转写文本。保存后会作为语音记录写入最近捕捉和知识库处理链路。</p>
      <textarea data-v18-voice-transcript rows="5" placeholder="在这里输入或粘贴语音转写文本..." style="width:100%;margin-top:12px;border:1px solid rgba(111,128,160,.18);border-radius:14px;padding:12px 14px;resize:vertical;font:inherit;color:#25324a;background:rgba(255,255,255,.88);outline:none;"></textarea>
      <button class="pill-button small" type="button" data-v18-voice-start style="margin-top:10px;">开始听写</button>
    `;
    const status = panel.querySelector("[data-v18-voice-status]");
    const transcript = panel.querySelector("[data-v18-voice-transcript]");
    const startBtn = panel.querySelector("[data-v18-voice-start]");
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      if (status) status.textContent = "当前浏览器不支持自动听写";
      if (startBtn) {
        startBtn.disabled = true;
        startBtn.textContent = "请手动输入转写文本";
      }
      return;
    }
    startBtn?.addEventListener("click", () => {
      try {
        if (voiceRecognitionV18) {
          voiceRecognitionV18.stop();
          voiceRecognitionV18 = null;
        }
        const recognition = new SpeechRecognition();
        recognition.lang = "zh-CN";
        recognition.continuous = true;
        recognition.interimResults = true;
        let finalText = transcript.value || "";
        recognition.onstart = () => {
          if (status) status.textContent = "正在听写";
          startBtn.textContent = "重新开始听写";
        };
        recognition.onresult = (event) => {
          let interim = "";
          for (let i = event.resultIndex; i < event.results.length; i += 1) {
            const chunk = event.results[i][0]?.transcript || "";
            if (event.results[i].isFinal) finalText += chunk;
            else interim += chunk;
          }
          transcript.value = (finalText + interim).trim();
        };
        recognition.onerror = (event) => {
          if (status) status.textContent = "听写失败，可手动输入";
          toast("语音听写失败：" + (event.error || "请检查麦克风权限"), "warning");
        };
        recognition.onend = () => {
          if (status && status.textContent === "正在听写") status.textContent = "听写已停止";
        };
        voiceRecognitionV18 = recognition;
        recognition.start();
      } catch (e) {
        toast("无法启动语音听写：" + e.message, "warning");
      }
    });
  }

  async function handleVoiceInputModal(button, layer) {
    if (button.dataset.toast !== "语音记录已保存") return;
    hydrateVoiceInputModalV18(layer);
    if (voiceRecognitionV18) {
      try { voiceRecognitionV18.stop(); } catch (_e) { /* noop */ }
      voiceRecognitionV18 = null;
    }
    const transcript = layer.querySelector("[data-v18-voice-transcript]");
    const content = (transcript && transcript.value.trim()) || "";
    if (!content) {
      toast("请先录入或粘贴语音转写文本", "warning");
      transcript?.focus();
      return;
    }
    button.disabled = true;
    button.classList.add("is-loading");
    try {
      await apiFetch("/capture/text", {
        method: "POST",
        body: {
          content,
          title: "语音记录 " + new Date().toLocaleString("zh-CN", { hour12: false }),
          tags: ["语音"],
          type: "voice",
          auto_process: true,
        },
      });
      toast("语音记录已保存到最近捕捉", "success");
      closeV14Layers();
      await Promise.allSettled([
        loadFeedCards(),
        refreshHomeRightRailStatCardsV14(),
        refreshHomeRecentList(),
        loadKbLibraryGrid(),
      ]);
    } catch (e) {
      toast("语音记录保存失败：" + e.message, "error");
    } finally {
      button.disabled = false;
      button.classList.remove("is-loading");
    }
  }

  function bindVoiceInputModalV18() {
    document.addEventListener(
      "click",
      (event) => {
        const opener = event.target.closest('[data-open-modal="voiceInput"]');
        if (opener) {
          window.setTimeout(() => {
            hydrateVoiceInputModalV18(document.querySelector('.surface-layer[data-modal="voiceInput"]'));
          }, 0);
          return;
        }
        const pause = event.target.closest('[data-toast="录音已暂停"]');
        if (pause) {
          event.preventDefault();
          event.stopImmediatePropagation();
          if (voiceRecognitionV18) {
            try { voiceRecognitionV18.stop(); } catch (_e) { /* noop */ }
            voiceRecognitionV18 = null;
          }
          const layer = pause.closest('.surface-layer[data-modal="voiceInput"]');
          const status = layer?.querySelector("[data-v18-voice-status]");
          if (status) status.textContent = "听写已暂停";
          toast("语音听写已暂停", "success");
          return;
        }
        const finish = event.target.closest('[data-toast="语音记录已保存"]');
        const layer = finish?.closest('.surface-layer[data-modal="voiceInput"]');
        if (finish && layer) {
          event.preventDefault();
          event.stopImmediatePropagation();
          Promise.resolve(handleVoiceInputModal(finish, layer)).catch((e) =>
            console.error("[v14] voice input", e),
          );
        }
      },
      true,
    );
  }

  async function handleNewFolderModal(button, layer) {
    const fields = layer.querySelectorAll(".form-field");
    const nameInp = fields[0]?.querySelector("input");
    const descTa = fields[1]?.querySelector("textarea");
    const name = (nameInp && nameInp.value.trim()) || "";
    if (!name) {
      toast("请填写文件夹名称", "warning");
      return;
    }
    const description = (descTa && descTa.value.trim()) || "";
    button.disabled = true;
    button.classList.add("is-loading");
    try {
      await apiFetch("/kb/folders", {
        method: "POST",
        body: { name, description, is_favorite: false },
      });
      toast("文件夹已创建", "success");
      closeV14Layers();
      await loadKbLibraryGrid();
    } catch (e) {
      toast("创建失败: " + e.message, "error");
    } finally {
      button.disabled = false;
      button.classList.remove("is-loading");
    }
  }

  function mapTemplateKey(label) {
    const t = String(label || "").trim();
    if (/研究报告/.test(t)) return "research_report";
    if (/方案|框架/.test(t)) return "solution_outline";
    return "blank";
  }

  async function handleNewDocumentModal(button, layer) {
    const inputs = layer.querySelectorAll(".form-field input");
    const titleInp = inputs[0];
    const title = (titleInp && titleInp.value.trim()) || "未命名文档";
    const select = layer.querySelector("select");
    const template = mapTemplateKey(select && select.selectedOptions[0]
      ? select.selectedOptions[0].textContent
      : "");

    button.disabled = true;
    button.classList.add("is-loading");
    try {
      const resp = await apiFetch("/kb/documents", {
        method: "POST",
        body: {
          title,
          template,
          document_type: "markdown",
          tags: [],
        },
      });
      const data = unwrapData(resp) || resp || {};
      const newDocId = data.id || data.document_id || "";
      // §16.4 — when on AI workspace, pin the freshly created doc into
      // the active conversation's context_scope so RAG cites it.
      const onAi = isAiWorkspaceActive();
      if (onAi && newDocId) {
        try {
          await ensureAiConversationId();
          await pinDocumentToActiveConversation({
            id: String(newDocId),
            title: data.title || title,
            folder_id: data.folder_id || null,
            kind: "doc",
          });
          toast("文档已创建并附加为 AI 上下文", "success");
        } catch (pinErr) {
          console.warn("[Mydow v1.4] pin new doc to ctx failed", pinErr);
          toast("文档已创建（自动附加上下文失败）", "warning");
        }
      } else {
        toast("文档已创建", "success");
      }
      closeV14Layers();
      await loadKbLibraryGrid();
    } catch (e) {
      toast("创建文档失败: " + e.message, "error");
    } finally {
      button.disabled = false;
      button.classList.remove("is-loading");
    }
  }

  async function _pollSkillRunUntilDone(runId, jobId, maxIterations) {
    const max = maxIterations || 30;
    for (let i = 0; i < max; i += 1) {
      await new Promise((r) => setTimeout(r, 1500));
      try {
        const r = await apiFetch(`/skills/runs/${runId}`);
        const data = unwrapData(r) || r || {};
        const status = data.status;
        if (
          status === "completed" || status === "failed" || status === "canceled"
        ) {
          return data;
        }
      } catch (e) {
        // /skills/runs/:id 还没 deploy 或 transient — 退化到查 /jobs/:id
        try {
          const j = await apiFetch(`/jobs/${jobId}`);
          const jd = unwrapData(j) || j || {};
          if (
            jd.status === "completed" || jd.status === "failed" || jd.status === "canceled"
          ) {
            return {
              status: jd.status,
              output: jd.output,
              error: jd.error,
            };
          }
        } catch (_e2) { /* keep polling */ }
      }
    }
    return null;
  }

  function _renderSkillResultDrawer(skillName, runResult) {
    const layer =
      document.querySelector('[data-drawer="skillRunResult"]') ||
      document.body.appendChild(
        Object.assign(document.createElement("aside"), {
          className: "surface-layer",
          innerHTML: '<div class="drawer-card"></div>',
        }),
      );
    layer.dataset.drawer = "skillRunResult";
    let card = layer.querySelector(".drawer-card");
    if (!card) {
      card = document.createElement("div");
      card.className = "drawer-card";
      layer.appendChild(card);
    }
    layer.style.cssText =
      "position:fixed;inset:0 0 0 auto;width:min(560px,90vw);" +
      "background:rgba(255,255,255,0.98);border-left:1px solid rgba(108,124,153,0.15);" +
      "box-shadow:-12px 0 40px rgba(28,41,80,0.12);z-index:10000;overflow:auto;padding:28px;";
    const output = runResult && runResult.output;
    const content = (output && (output.content || output.summary)) || "";
    const documentId = output && (output.document_id || output.saved_object_id);
    const status = runResult && runResult.status;
    const usage = output && output.usage;

    card.innerHTML =
      '<header style="display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;">' +
      `<h2 style="margin:0;font-size:18px;color:#1c2940;">${escapeHtmlV14(skillName)} · 运行结果</h2>` +
      '<button type="button" data-close-skill-result aria-label="关闭" ' +
      'style="border:0;background:transparent;font-size:22px;color:#8794aa;cursor:pointer;">×</button>' +
      "</header>" +
      `<div style="margin-bottom:14px;">` +
      `<span style="display:inline-block;padding:4px 10px;border-radius:999px;background:${status === "completed" ? "rgba(112,200,170,0.16)" : "rgba(216,72,74,0.12)"};color:${status === "completed" ? "#118a6c" : "#a4373a"};font-size:12px;font-weight:600;">${escapeHtmlV14(status || "未知")}</span>` +
      "</div>" +
      `<div style="white-space:pre-wrap;line-height:1.7;color:#29384f;font-size:14px;background:#f6f8fc;border-radius:12px;padding:16px;border:1px solid rgba(108,124,153,0.12);max-height:55vh;overflow:auto;">` +
      `${escapeHtmlV14(content || "（暂无内容）")}` +
      "</div>" +
      (usage
        ? `<div style="margin-top:14px;font-size:12px;color:#8794aa;">tokens · prompt ${usage.prompt_tokens || 0} · completion ${usage.completion_tokens || 0}</div>`
        : "") +
      (documentId
        ? `<div style="margin-top:18px;display:flex;gap:10px;">` +
          `<button type="button" data-skill-result-open-doc="${escapeHtmlV14(String(documentId))}" ` +
          'class="pill-button small" style="padding:8px 14px;background:#5b78ff;color:#fff;border:0;border-radius:10px;cursor:pointer;font-weight:600;">打开生成的文档</button>' +
          "</div>"
        : "");

    layer.hidden = false;
    layer.classList.add("is-open");
    document.body.classList.add("layer-lock");
  }

  function bindSkillResultDrawerCloseV14() {
    document.addEventListener(
      "click",
      (event) => {
        const close = event.target.closest("[data-close-skill-result]");
        if (close) {
          const layer = close.closest('[data-drawer="skillRunResult"]');
          if (layer) {
            layer.hidden = true;
            layer.classList.remove("is-open");
            document.body.classList.remove("layer-lock");
          }
          return;
        }
        const openDoc = event.target.closest("[data-skill-result-open-doc]");
        if (openDoc) {
          const id = openDoc.getAttribute("data-skill-result-open-doc");
          openKbDocumentEditorV20(id).catch((e) => toast("打开文档失败: " + e.message, "error"));
          const layer = openDoc.closest('[data-drawer="skillRunResult"]');
          if (layer) {
            layer.hidden = true;
            layer.classList.remove("is-open");
            document.body.classList.remove("layer-lock");
          }
        }
      },
      true,
    );
  }

  async function handleSkillRunModal(button, layer) {
    const sid = V14.activeSkillId;
    if (!sid) {
      toast("未找到 Skill，请从广场卡片打开", "warning");
      return;
    }
    const textarea = layer.querySelector("textarea");
    /** Prototype output-format <select> lives under `.form-field`; doc picker is in `[data-v16-skill-doc-picker]` */
    const formatSelect = layer.querySelector(".form-field select");
    const instruction = (textarea && textarea.value.trim()) || "运行 Skill";
    const output_format =
      formatSelect && formatSelect.value ? formatSelect.value : (
        formatSelect && formatSelect.selectedOptions[0]
          ? formatSelect.selectedOptions[0].textContent
          : ""
      );

    const docSel = layer.querySelector("select[data-v16-skill-doc-select]");
    const documentId =
      docSel && String(docSel.value || "").trim()
        ? String(docSel.value).trim()
        : "";
    const outputFolderSel = layer.querySelector("select[data-v20-skill-output-folder]");
    const outputFolderId =
      outputFolderSel && String(outputFolderSel.value || "").trim()
        ? String(outputFolderSel.value).trim()
        : "";
    const modeInp = layer.querySelector(
      'input[name="v16-skill-output-mode"]:checked',
    );
    const output_mode = modeInp && modeInp.value === "transform" ? "transform" : "generate";
    if (output_mode === "transform" && !documentId) {
      toast("「修改所选文档」需要先选择知识库文档", "warning");
      return;
    }

    const skillCard = document.querySelector(`.skill-card[data-skill-id="${sid}"]`);
    const skillName =
      (skillCard && skillCard.querySelector("h3")?.textContent.trim()) || "Skill";

    const inputPayload = {
      instruction,
      output_format,
      text: instruction,
      ...(documentId ? { document_id: documentId, output_mode } : {}),
      ...(outputFolderId && output_mode === "generate" ? { folder_id: outputFolderId } : {}),
    };

    button.disabled = true;
    button.classList.add("is-loading");
    try {
      const r = await apiFetch(`/skills/${sid}/run`, {
        method: "POST",
        body: {
          input: inputPayload,
          save_output: true,
        },
      });
      const d = unwrapData(r) || {};
      const runId = d.skill_run_id;
      const jobId = d.job_id;
      toast(
        "Skill 运行中…" + (jobId ? "（job " + String(jobId).slice(0, 8) + "）" : ""),
        "info",
      );
      closeV14Layers();

      // 异步轮询，结果到了再开抽屉。
      _pollSkillRunUntilDone(runId, jobId).then((finalRun) => {
        if (!finalRun) {
          toast("Skill 运行超时，请到通知中心查看", "warning");
          return;
        }
        if (finalRun.status === "completed") {
          toast(`Skill「${skillName}」运行完成`, "success");
          const docId =
            finalRun.output &&
            (finalRun.output.document_id || finalRun.output.saved_object_id);
          rememberSkillRunCompletedV16(sid, docId);
          paintSkillRunDoneChipsV16();
          _renderSkillResultDrawer(skillName, finalRun);
          // 异步刷新通知 + KB 文件夹列表
          refreshNotificationBadge().catch(() => {});
          loadKbLibraryGrid().catch(() => {});
        } else {
          toast(
            `Skill「${skillName}」运行失败：${(finalRun.error && finalRun.error.message) || finalRun.status}`,
            "error",
          );
        }
      });
    } catch (e) {
      toast("运行失败: " + e.message, "error");
    } finally {
      button.disabled = false;
      button.classList.remove("is-loading");
    }
  }

  async function handleEditProfileModal(button, layer) {
    const inputs = layer.querySelectorAll(".form-field input");
    const name = (inputs[0] && inputs[0].value.trim()) || "";
    const role = (inputs[2] && inputs[2].value.trim()) || "";
    if (!name) {
      toast("姓名不能为空", "warning");
      return;
    }
    button.disabled = true;
    try {
      await apiFetch("/me", {
        method: "PATCH",
        body: { name, settings: { display_role: role } },
      });
      toast("个人资料已更新", "success");
      closeV14Layers();
      await refreshProfileChip();
    } catch (e) {
      toast("更新失败: " + e.message, "error");
    } finally {
      button.disabled = false;
    }
  }

  async function handleNotificationSettingsModal(button, layer) {
    const labelMap = {
      "浏览器通知": { kind: "top", key: "notification_enabled" },
      "AI 任务结果": { kind: "channel", key: "ai_done" },
      "知识连接提醒": { kind: "channel", key: "knowledge_link" },
    };
    const settings = {};
    const channels = {};
    layer.querySelectorAll(".toggle-switch").forEach((sw) => {
      const active =
        sw.classList.contains("active") || sw.getAttribute("aria-checked") === "true";
      const article = sw.closest("article.quick-setting");
      const label = (article && article.querySelector("strong") && article.querySelector("strong").textContent || "").trim();
      const mapping = labelMap[label];
      if (!mapping) return;
      if (mapping.kind === "top") settings[mapping.key] = active;
      else channels[mapping.key] = active;
    });
    if (Object.keys(channels).length > 0) settings.notification_channels = channels;
    button.disabled = true;
    try {
      await apiFetch("/me", { method: "PATCH", body: { settings } });
      toast("通知偏好已保存", "success");
      closeV14Layers();
      await refreshProfileChip();
    } catch (e) {
      toast("保存失败: " + e.message, "error");
    } finally {
      button.disabled = false;
    }
  }

  async function handleAiPersonalizeModal(button, layer) {
    // §18.4 — persist AI personalization into the canonical PRD10
    // preferences shape. Earlier code wrote a nested settings object through
    // PATCH /me, but the backend whitelist intentionally dropped it.
    const payload = {};
    const readSelectValue = (pattern, fallback) => {
      const field = Array.from(layer.querySelectorAll(".form-field")).find((node) =>
        pattern.test(node.querySelector("label")?.textContent || ""),
      );
      const select = field && field.querySelector("select");
      return (select && select.value) || fallback;
    };
    payload.ai_response_style = readSelectValue(/默认回答风格/, "concise_structured");
    payload.ai_detail_level = readSelectValue(/输出详细程度/, "balanced");
    payload.language = readSelectValue(/常用语言/, "zh-CN");
    layer.querySelectorAll(".toggle-switch").forEach((sw) => {
      const active =
        sw.classList.contains("active") ||
        sw.getAttribute("aria-checked") === "true" ||
        sw.getAttribute("aria-pressed") === "true";
      const article = sw.closest("article, .quick-setting, .form-row");
      const label = (
        (article && article.querySelector("strong, label, .form-label")) || sw
      ).textContent.trim();
      if (label.includes("默认引用知识库") || label.includes("引用上下文")) {
        payload.cite_knowledge_by_default = active;
      } else if (label.includes("自动建议")) {
        payload.ai_auto_suggest = active;
      } else if (label.includes("流式")) {
        payload.ai_streaming = active;
      }
    });
    button.disabled = true;
    try {
      await apiFetch("/me/preferences", { method: "PATCH", body: payload });
      toast("AI 个性化设置已保存", "success");
      closeV14Layers();
      await refreshProfileChip();
    } catch (e) {
      toast("保存失败: " + e.message, "error");
    } finally {
      button.disabled = false;
    }
  }

  const AI_PERSONALIZE_SELECTS_V18 = {
    ai_response_style: [
      { value: "concise_structured", label: "清晰、直接、可执行", desc: "适合日常问答和任务推进" },
      { value: "concise", label: "简洁", desc: "只保留结论和关键步骤" },
      { value: "detailed", label: "更具创意", desc: "补充发散选项与启发式建议" },
      { value: "academic", label: "更正式专业", desc: "适合研究、方案与报告语气" },
    ],
    ai_detail_level: [
      { value: "balanced", label: "适中", desc: "默认长度，兼顾速度和信息量" },
      { value: "brief", label: "简洁", desc: "短回答、少解释" },
      { value: "deep", label: "详细", desc: "包含背景、推理和下一步" },
    ],
    language: [
      { value: "zh-CN", label: "中文 简体", desc: "默认使用简体中文" },
      { value: "en-US", label: "English", desc: "Prefer English responses" },
    ],
  };

  function injectAiPersonalizeStylesV18() {
    if (document.getElementById("mydow-ai-personalize-v18")) return;
    const style = document.createElement("style");
    style.id = "mydow-ai-personalize-v18";
    style.textContent = `
      [data-modal="aiPersonalize"] .form-field { position: relative; }
      [data-modal="aiPersonalize"] select[data-v18-native-select] {
        position: absolute !important;
        width: 1px !important;
        height: 1px !important;
        opacity: 0 !important;
        pointer-events: none !important;
      }
      .v18-ai-select-button {
        width: 100%;
        min-height: 48px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 14px;
        padding: 8px 12px 8px 14px;
        border: 1px solid rgba(111, 128, 160, .18);
        border-radius: 15px;
        color: #23324b;
        background: linear-gradient(180deg, rgba(255,255,255,.98), rgba(247,249,255,.94));
        box-shadow: 0 12px 30px rgba(42, 56, 95, .08), inset 0 1px 0 rgba(255,255,255,.9);
        cursor: pointer;
        transition: transform .16s ease, border-color .16s ease, box-shadow .16s ease;
      }
      .v18-ai-select-button:hover,
      .v18-ai-select-button[aria-expanded="true"],
      .v18-ai-select-button:focus-visible {
        transform: translateY(-1px);
        border-color: rgba(91,120,255,.42);
        box-shadow: 0 18px 42px rgba(42, 56, 95, .13);
        outline: 0;
      }
      .v18-ai-select-button strong {
        display: block;
        color: #21304a;
        font-size: 13px;
        line-height: 1.2;
      }
      .v18-ai-select-button small {
        display: block;
        margin-top: 2px;
        color: #7c899e;
        font-size: 11px;
        font-weight: 620;
      }
      .v18-ai-select-panel {
        position: absolute;
        left: 0;
        right: 0;
        top: calc(100% + 8px);
        z-index: 90;
        display: grid;
        gap: 5px;
        padding: 8px;
        border: 1px solid rgba(111, 128, 160, .18);
        border-radius: 18px;
        background: rgba(255,255,255,.98);
        box-shadow: 0 24px 70px rgba(23, 34, 58, .18);
        backdrop-filter: blur(18px);
      }
      .v18-ai-select-panel[hidden] { display: none; }
      .v18-ai-select-panel button {
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 10px 11px;
        border: 0;
        border-radius: 13px;
        background: transparent;
        text-align: left;
        color: #26354f;
        cursor: pointer;
      }
      .v18-ai-select-panel button:hover,
      .v18-ai-select-panel button[aria-selected="true"],
      .v18-ai-select-panel button:focus-visible {
        background: linear-gradient(135deg, rgba(239,244,255,.98), rgba(247,251,255,.94));
        color: #3655c8;
        outline: 0;
      }
      .v18-ai-select-panel button[aria-selected="true"]::after {
        content: "✓";
        font-weight: 900;
        color: #4d6df1;
      }
    `;
    document.head.appendChild(style);
  }

  function aiPersonalizeFieldKeyV18(field) {
    const label = field?.querySelector("label")?.textContent || "";
    if (/默认回答风格/.test(label)) return "ai_response_style";
    if (/输出详细程度/.test(label)) return "ai_detail_level";
    if (/常用语言/.test(label)) return "language";
    return "";
  }

  function aiPersonalizeOptionV18(key, value) {
    const opts = AI_PERSONALIZE_SELECTS_V18[key] || [];
    return opts.find((opt) => opt.value === value) || opts[0] || { value, label: value, desc: "" };
  }

  function setAiPersonalizeSelectValueV18(field, key, value) {
    const select = field.querySelector("select");
    const btn = field.querySelector(".v18-ai-select-button");
    const panel = field.querySelector(".v18-ai-select-panel");
    const opt = aiPersonalizeOptionV18(key, value);
    if (select) select.value = opt.value;
    if (btn) {
      btn.dataset.value = opt.value;
      btn.innerHTML =
        `<span><strong>${escapeHtmlV14(opt.label)}</strong><small>${escapeHtmlV14(opt.desc || "")}</small></span>` +
        '<svg class="icon" aria-hidden="true" style="width:14px;height:14px"><use href="#icon-chevron-down" /></svg>';
    }
    if (panel) {
      panel.querySelectorAll("button[data-value]").forEach((item) => {
        item.setAttribute("aria-selected", String(item.dataset.value === opt.value));
      });
    }
  }

  function prepareAiPersonalizeSelectV18(field, key, value) {
    const select = field.querySelector("select");
    if (!select || !key) return;
    injectAiPersonalizeStylesV18();
    select.dataset.v18NativeSelect = "true";
    const opts = AI_PERSONALIZE_SELECTS_V18[key] || [];
    select.innerHTML = opts
      .map((opt) => `<option value="${escapeHtmlV14(opt.value)}">${escapeHtmlV14(opt.label)}</option>`)
      .join("");
    let btn = field.querySelector(".v18-ai-select-button");
    if (!btn) {
      btn = document.createElement("button");
      btn.type = "button";
      btn.className = "v18-ai-select-button";
      btn.dataset.v18AiSelect = key;
      btn.setAttribute("aria-haspopup", "listbox");
      btn.setAttribute("aria-expanded", "false");
      select.insertAdjacentElement("afterend", btn);
    }
    let panel = field.querySelector(".v18-ai-select-panel");
    if (!panel) {
      panel = document.createElement("div");
      panel.className = "v18-ai-select-panel";
      panel.setAttribute("role", "listbox");
      panel.hidden = true;
      panel.innerHTML = opts
        .map((opt) =>
          `<button type="button" role="option" data-value="${escapeHtmlV14(opt.value)}">` +
          `<span><strong>${escapeHtmlV14(opt.label)}</strong><small>${escapeHtmlV14(opt.desc || "")}</small></span>` +
          `</button>`,
        )
        .join("");
      field.appendChild(panel);
    }
    setAiPersonalizeSelectValueV18(field, key, value);
  }

  async function hydrateAiPersonalizeControlsV18() {
    const layer = document.querySelector('.surface-layer[data-modal="aiPersonalize"]');
    if (!layer) return;
    let prefs = {};
    try {
      prefs = unwrapData(await apiFetch("/me/preferences")) || {};
    } catch (_e) {
      prefs = {};
    }
    layer.querySelectorAll(".form-field").forEach((field) => {
      const key = aiPersonalizeFieldKeyV18(field);
      if (!key) return;
      const fallback =
        key === "ai_response_style" ? "concise_structured" :
        key === "ai_detail_level" ? "balanced" :
        "zh-CN";
      prepareAiPersonalizeSelectV18(field, key, prefs[key] || fallback);
    });
    layer.querySelectorAll(".toggle-switch").forEach((sw) => {
      const label = sw.closest("article")?.querySelector("strong")?.textContent || "";
      if (!/默认引用知识库|引用上下文/.test(label)) return;
      const active = Boolean(prefs.cite_knowledge_by_default);
      sw.classList.toggle("active", active);
      sw.setAttribute("aria-pressed", String(active));
    });
  }

  function closeAiPersonalizePanelsV18(except) {
    document.querySelectorAll(".v18-ai-select-panel").forEach((panel) => {
      if (panel === except) return;
      panel.hidden = true;
      const btn = panel.parentElement?.querySelector(".v18-ai-select-button");
      if (btn) btn.setAttribute("aria-expanded", "false");
    });
  }

  function bindAiPersonalizeModernControlsV18() {
    injectAiPersonalizeStylesV18();
    document.addEventListener(
      "click",
      (event) => {
        const open = event.target.closest('[data-open-modal="aiPersonalize"]');
        if (open) window.setTimeout(() => hydrateAiPersonalizeControlsV18(), 120);
        const selectBtn = event.target.closest(".v18-ai-select-button");
        if (selectBtn) {
          event.preventDefault();
          event.stopImmediatePropagation();
          const panel = selectBtn.parentElement?.querySelector(".v18-ai-select-panel");
          const willOpen = !panel || panel.hidden;
          closeAiPersonalizePanelsV18(panel);
          if (panel) {
            panel.hidden = !willOpen;
            selectBtn.setAttribute("aria-expanded", String(willOpen));
            if (willOpen) panel.querySelector("button[aria-selected='true'], button")?.focus();
          }
          return;
        }
        const option = event.target.closest(".v18-ai-select-panel button[data-value]");
        if (option) {
          event.preventDefault();
          event.stopImmediatePropagation();
          const field = option.closest(".form-field");
          const key = aiPersonalizeFieldKeyV18(field);
          if (field && key) setAiPersonalizeSelectValueV18(field, key, option.dataset.value || "");
          closeAiPersonalizePanelsV18();
          field?.querySelector(".v18-ai-select-button")?.focus();
          return;
        }
        if (!event.target.closest(".v18-ai-select-panel,.v18-ai-select-button")) {
          closeAiPersonalizePanelsV18();
        }
      },
      true,
    );
    document.addEventListener(
      "keydown",
      (event) => {
        const btn = event.target.closest(".v18-ai-select-button");
        if (btn && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          btn.click();
          return;
        }
        const option = event.target.closest(".v18-ai-select-panel button[data-value]");
        if (!option) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          option.click();
        } else if (event.key === "Escape") {
          closeAiPersonalizePanelsV18();
          option.closest(".form-field")?.querySelector(".v18-ai-select-button")?.focus();
        } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
          event.preventDefault();
          const items = Array.from(option.closest(".v18-ai-select-panel").querySelectorAll("button[data-value]"));
          const idx = items.indexOf(option);
          const next = event.key === "ArrowDown"
            ? items[(idx + 1) % items.length]
            : items[(idx - 1 + items.length) % items.length];
          next?.focus();
        }
      },
      true,
    );
    window.setTimeout(() => hydrateAiPersonalizeControlsV18(), 0);
  }

  async function handleAiSaveModal(button, layer) {
    const mid = V14.lastAssistantMessageId;
    if (!mid) {
      toast("请先完成一轮 AI 流式回复，再保存到知识库", "warning");
      return;
    }
    const titleField =
      layer.querySelector(".form-grid .form-field:nth-of-type(2) input") ||
      layer.querySelector(".form-field input");
    const title = (titleField && titleField.value.trim()) || "AI 输出";
    const tags = [...layer.querySelectorAll(".source-chip-list .tag")].map((t) =>
      t.textContent.trim()).filter(Boolean);
    button.disabled = true;
    button.classList.add("is-loading");
    try {
      await apiFetch("/ai/messages/" + mid + "/save-to-kb", {
        method: "POST",
        body: {
          title,
          tags: tags.length ? tags : ["AI 生成"],
          folder_id: null,
        },
      });
      toast("已排队写入知识库", "success");
      closeV14Layers();
      await loadKbLibraryGrid().catch(() => {});
    } catch (e) {
      toast("保存失败: " + e.message, "error");
    } finally {
      button.disabled = false;
      button.classList.remove("is-loading");
    }
  }

  const MODAL_SUBMIT_HANDLERS = {
    uploadFile: handleUploadFileModal,
    webLink: handleWebLinkModal,
    deepResearch: handleDeepResearchModal,
    voiceInput: handleVoiceInputModal,
    newFolder: handleNewFolderModal,
    newDocument: handleNewDocumentModal,
    skillRun: handleSkillRunModal,
    editProfile: handleEditProfileModal,
    notificationSettings: handleNotificationSettingsModal,
    aiPersonalize: handleAiPersonalizeModal,
    aiSave: handleAiSaveModal,
  };

  function bindModalSubmitsCapture() {
    document.addEventListener(
      "click",
      (event) => {
        const btn = event.target.closest("button[data-toast]");
        if (!btn || btn.matches("[data-close-layer]")) return;
        const layer = btn.closest(".surface-layer[data-modal]");
        if (!layer) return;
        const modalName = layer.dataset.modal;
        if (modalName === "customInsight") return;
        const fn = MODAL_SUBMIT_HANDLERS[modalName];
        if (!fn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        Promise.resolve(fn(btn, layer)).catch((e) =>
          console.error("[v14] modal", e));
      },
      true,
    );
  }

  function bindCreateDocCapture() {
    document.addEventListener(
      "click",
      (event) => {
        const btn = event.target.closest("[data-create-doc]");
        if (!btn) return;
        const layer = btn.closest('.surface-layer[data-modal="newDocument"]');
        if (!layer) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        handleNewDocumentModal(btn, layer).catch(() => {});
      },
      true,
    );
  }

  // ─── custom insight ───────────────────────────────────────────────────────
  /** §16.12 — Garden 弹窗「生成洞察」→ ``POST /api/v1/garden/insights``（契约§3.4） */
  async function submitCustomInsight(button) {
    const layer =
      button.closest('.surface-layer[data-modal="customInsight"]') ||
      button.closest(".surface-layer.new-insight-modal") ||
      document.querySelector('[data-modal="customInsight"]');
    if (!layer) return;
    const topic = (
      layer.querySelector("[data-new-insight-topic]")?.value || ""
    ).trim();
    if (topic.length < 2) {
      toast("主题至少 2 个字", "warning");
      return;
    }
    const connected_note_ids = [
      ...layer.querySelectorAll("[data-selected-note-chip]"),
    ]
      .map((c) => (c.getAttribute("data-selected-note-chip") || "").trim())
      .filter(Boolean);

    const oldLabel = button.textContent;
    button.disabled = true;
    button.textContent = "生成中…";
    try {
      await apiFetch("/garden/insights", {
        method: "POST",
        body: { topic, connected_note_ids },
      });
      toast("洞察已创建", "success");
      closeV14Layers();
      if (typeof refreshInsightsFullV14 === "function") {
        refreshInsightsFullV14().catch(() => {});
      }
    } catch (e) {
      toast("生成失败: " + (e && e.message ? e.message : "未知错误"), "error");
    } finally {
      button.disabled = false;
      button.textContent = oldLabel;
    }
  }

  function bindCustomInsightSubmit() {
    document.addEventListener(
      "click",
      (event) => {
        const btn = event.target.closest("[data-generate-insight]");
        if (!btn || btn.disabled) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        submitCustomInsight(btn).catch(() => {});
      },
      true,
    );
  }

  // ─── capture textarea send (homepage) ───────────────────────────────────────
  function bindCaptureSubmit() {
    document.addEventListener(
      "click",
      async (event) => {
        const button = event.target.closest(".send-button");
        if (!button) return;
        if (!button.closest(".capture")) return;
        const textarea = document.querySelector(".capture textarea");
        const text = (textarea && textarea.value || "").trim();
        if (!text) return;
        event.stopImmediatePropagation();
        try {
          const r = await apiFetch("/capture/text", {
            method: "POST",
            body: { content: text, auto_process: true },
          });
          const data = unwrapData(r) || r || {};
          toast("灵感已保存", "success");
          if (textarea) textarea.value = "";
          window.dispatchEvent(
            new CustomEvent("mydow:v14:capture-completed", { detail: { data } }),
          );
          await loadFeedCards();
          await loadFeedIntoRecordsTable();
          await refreshNotificationBadge();
          const cardId = data.card_id || data.card?.id;
          if (data.card) {
            revealItemDetailDrawerV18(data.card);
          } else if (cardId) {
            const detail = await loadCardForDrawer(String(cardId));
            if (detail) revealItemDetailDrawerV18(detail);
          }
        } catch (e) {
          toast("保存失败: " + e.message, "error");
        }
      },
      true,
    );
  }

  // ─── feed cards (recent view) ────────────────────────────────────────────
  function relTime(ts) {
    if (!ts) return "";
    try {
      const d = new Date(ts);
      return d.toLocaleString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  }

  async function loadFeedCards() {
    let resp;
    try {
      resp = await apiFetch("/feed?page_size=30");
    } catch (e) {
      console.warn("[Mydow v1.4] /feed failed", e);
      return null;
    }
    const data = unwrapData(resp) || resp || {};
    const items = data.items || [];
    const cards = document.querySelectorAll(".recent-view .idea-card");
    const recentRows = document.querySelectorAll(".recent-doc-list .recent-doc-row");
    if (!cards.length && !recentRows.length) return data;

    cards.forEach((card, idx) => {
      const row = items[idx];
      if (!row) {
        card.style.opacity = "0.35";
        return;
      }
      card.dataset.cardId = row.id || "";
      card.dataset.bridgeBound = "true";
      const titleEl = card.querySelector(".card-title, h2.card-title");
      if (titleEl) titleEl.textContent = row.title || "灵感";
      const tagHost = card.querySelector(".tags");
      if (tagHost && Array.isArray(row.tags)) {
        tagHost.innerHTML = (row.tags || []).slice(0, 4).map((t) =>
          `<span class="tag">${String(t)}</span>`).join("") || `<span class="tag">灵感</span>`;
      }
      const metaSpan = card.querySelector(".card-meta span");
      if (metaSpan) metaSpan.textContent = relTime(row.updated_at || row.created_at);
    });
    recentRows.forEach((row, idx) => {
      const it = items[idx];
      if (!it) {
        row.style.display = "none";
        return;
      }
      row.style.display = "";
      row.dataset.cardId = it.id || "";
      row.dataset.bridgeBound = "true";
      const title = row.querySelector("strong");
      if (title) title.textContent = it.title || "未命名";
      const sub = row.querySelector("div span");
      if (sub) {
        const type = it.document_type || it.content_type || "灵感记录";
        sub.textContent = `${type} · ${relTime(it.updated_at || it.created_at) || "刚刚"}`;
      }
      const tail = row.querySelector(":scope > span:not(.recent-item-icon)");
      if (tail) tail.textContent = relTime(it.updated_at || it.created_at) || "";
    });
    window.dispatchEvent(new CustomEvent("mydow:v14:feed-loaded", { detail: { count: items.length } }));
    return data;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /** 「我的记录」列表 + 网格 — 与 /feed 同源 */
  async function loadFeedIntoRecordsTable() {
    let resp;
    try {
      resp = await apiFetch("/feed?page_size=40");
    } catch (e) {
      console.warn("[Mydow v1.4] records feed failed", e);
      return null;
    }
    const data = unwrapData(resp) || resp || {};
    const items = data.items || [];

    const rows = document.querySelectorAll(
      ".records-table .record-row:not(.record-head)",
    );
    rows.forEach((row, idx) => {
      const it = items[idx];
      if (!it) {
        row.style.display = "none";
        return;
      }
      row.style.display = "";
      row.dataset.cardId = it.id || "";
      const title = row.querySelector(".record-title");
      if (title) title.textContent = it.title || "未命名";
      const times = row.querySelectorAll(".record-time");
      const t = relTime(it.updated_at || it.created_at);
      if (times[0]) times[0].textContent = t;
    });

    const cards = document.querySelectorAll(".record-card-grid .record-card");
    cards.forEach((card, idx) => {
      const it = items[idx];
      if (!it) {
        card.style.display = "none";
        return;
      }
      card.style.display = "";
      card.dataset.cardId = it.id || "";
      const h3 = card.querySelector("h3");
      if (h3) h3.textContent = it.title || "未命名";
      const meta = card.querySelector(".record-card-meta");
      if (meta) {
        const tags = (it.tags || []).slice(0, 2).join(" · ") || "灵感";
        meta.innerHTML =
          `<span>${escapeHtmlV14(tags)}</span><span>私人</span><span>${escapeHtmlV14(
            relTime(it.updated_at || it.created_at),
          )}</span>`;
      }
    });
    window.dispatchEvent(
      new CustomEvent("mydow:v14:records-loaded", { detail: { count: items.length } }),
    );
    return data;
  }

  function bindHomeFeedViewTabs() {
    document.addEventListener(
      "click",
      (event) => {
        const tab = event.target.closest(
          '[data-view-target="records"], [data-view-target="recent"]',
        );
        if (!tab) return;
        window.setTimeout(() => {
          const v = tab.getAttribute("data-view-target");
          if (v === "recent") loadFeedCards().catch(() => {});
          if (v === "records") loadFeedIntoRecordsTable().catch(() => {});
        }, 120);
      },
      true,
    );
  }

  /** 首页 + 洞察侧栏若干卡片（轻量 hydration，不替换 §15.5 全量） */
  async function refreshInsightsFullV14() {
    try {
      const todayR = await apiFetch("/today");
      const today = unwrapData(todayR) || {};
      const stats = today.stats || {};
      const captureN = Number(stats.today_capture_count || 0);

      document.querySelectorAll(".insight-stack .insight-graph").forEach((card) => {
        const h3 = card.querySelector("h3");
        if (!h3) return;
        const title = h3.textContent || "";
        const sv = card.querySelector(".stat-value");
        if (title.includes("今日灵感") && sv) sv.textContent = String(captureN);
      });

      let msgTotal = 0;
      try {
        const aiR = await apiFetch("/ai/conversations?page_size=20");
        const aid = unwrapData(aiR) || {};
        const convs = aid.items || [];
        msgTotal = convs.reduce(
          (acc, c) => acc + Number(c.message_count || c.messages_count || 0),
          0,
        );
      } catch (_e) { /* ignore */ }

      document.querySelectorAll(".insight-stack .insight-graph").forEach((card) => {
        const h3 = card.querySelector("h3");
        if (!h3) return;
        const title = h3.textContent || "";
        if (!title.includes("AI") || !title.includes("活跃")) return;
        const sv = card.querySelector(".stat-value");
        const note = card.querySelector(".stat-note");
        if (sv) {
          sv.textContent = msgTotal >= 20 ? "高" : msgTotal >= 8 ? "中" : "低";
        }
        if (note) {
          note.textContent = "帮助你梳理了 " + msgTotal + " 条对话消息";
        }
      });

      try {
        const insR = await apiFetch("/insights/summary?range=week");
        const ins = unwrapData(insR) || {};
        const list = ins.items || ins.insights || [];
        const first = list[0];
        const daily = document.querySelector(".daily-insight p, .insight-card.daily-insight p");
        if (daily && first) {
          daily.innerHTML =
            "<strong>" + escapeHtml(first.title || "洞察") + "</strong> · " +
            escapeHtml((first.summary || "").slice(0, 120));
        }
      } catch (_e) { /* ignore */ }

      try {
        const feedR = await apiFetch("/feed?page_size=3");
        const fd = unwrapData(feedR) || {};
        const recentItems = fd.items || [];
        const recentArts = document.querySelectorAll(".recent-list .recent-item");
        recentArts.forEach((art, idx) => {
          const it = recentItems[idx];
          if (!it) return;
          art.dataset.cardId = it.id || "";
          const strong = art.querySelector("strong");
          const span = art.querySelector("div > span");
          if (strong) strong.textContent = it.title || "";
          if (span) span.textContent = relTime(it.updated_at || it.created_at);
        });
      } catch (_e) { /* ignore */ }

      try {
        const kbR = await apiFetch("/kb/overview");
        const kb = unwrapData(kbR) || {};
        const st = kb.stats || kb;
        const docCount = Number(st.document_count != null ? st.document_count : st.documents || 0);
        document.querySelectorAll(".insight-card.kb-overview .stat-value").forEach((sv) => {
          let inner = sv.querySelector("span");
          if (!inner) {
            inner = document.createElement("span");
            inner.style.cssText = "font-size:13px;color:#718098";
            inner.textContent = " 条记录";
          }
          sv.textContent = String(docCount);
          sv.appendChild(inner);
        });
      } catch (_e) { /* ignore */ }
    } catch (e) {
      console.warn("[v14] refreshInsightsFullV14", e);
    }
    try {
      await hydrateInsightsFullMain();
    } catch (_e) { /* ignore */ }
  }

  function renderMetricTilesInsightsFull(main, summaryResp) {
    const tiles = main.querySelectorAll(".metric-grid .metric-tile");
    if (!tiles.length) return;
    const data = unwrapData(summaryResp) || {};
    const stats = data.stats || {};
    const themeDist = data.theme_distribution || [];
    const insights = data.insights || [];
    const spec = [
      {
        label: "本周捕捉",
        value: Number(stats.capture_count || 0),
        note: stats.capture_count > 0 ? "较上周 +" + stats.capture_count : "持平",
      },
      {
        label: "本周洞察",
        value: insights.length,
        note: insights.length ? "活跃 " + insights.length + " 条" : "暂无",
      },
      {
        label: "重点主题",
        value: themeDist.length,
        note: themeDist.length ? "共 " + themeDist.length + " 个" : "暂无",
      },
      {
        label: "知识库文档",
        value: Number(stats.knowledge_count || 0),
        note: (stats.task_count || 0) + " 个任务",
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

  function renderCoreInsightCardsInsightsFull(main, summaryResp) {
    const grid = main.querySelector(".insight-wide-panel .core-insight-grid");
    if (!grid) return;
    const data = unwrapData(summaryResp) || {};
    const insightItems = (data.insights || []).slice(0, 3);
    if (!insightItems.length) return;
    grid.innerHTML = "";
    insightItems.forEach((it, idx) => {
      const card = document.createElement("article");
      card.className = "core-insight-card";
      card.dataset.insightId = it.id || "";
      const tagLabel = INSIGHT_TAG_LABELS_V14[it.insight_type] || "洞察";
      const iconHref = INSIGHT_ICON_HREFS_V14[it.insight_type] || "#icon-sparkles";
      const iconClass = idx === 1 ? "green" : "";
      card.style.position = "relative";
      card.innerHTML =
        '<span class="notice-icon ' +
        iconClass +
        '"><svg class="icon"><use href="' +
        iconHref +
        '" /></svg></span><h3>' +
        escapeHtml(it.title || "未命名洞察") +
        "</h3><p>" +
        escapeHtml(String(it.summary || it.body || "")) +
        '</p><span class="tag">' +
        escapeHtml(tagLabel) +
        "</span>" +
        '<button class="bridge-dismiss-btn" type="button" aria-label="忽略" ' +
        'style="position:absolute;top:14px;right:14px;padding:4px 9px;border-radius:8px;' +
        'border:1px solid rgba(108,124,153,0.18);background:rgba(255,255,255,0.6);' +
        'color:#5a6b86;font-size:11px;font-weight:600;cursor:pointer;line-height:1">忽略</button>';
      grid.appendChild(card);
    });
    grid.dataset.bridgeBound = "true";
  }

  function renderReportListInsightsFull(main, listResp) {
    const reportList = main.querySelector(
      ".insights-bottom-grid .split-panel:nth-child(1) .report-list",
    );
    if (!reportList) return;
    const raw = unwrapData(listResp) || {};
    const all = raw.items || [];
    const items = all
      .filter((it) =>
        ["daily_summary", "weekly_summary", "monthly_summary"].includes(it.insight_type),
      )
      .slice(0, 3);
    if (!items.length) return;
    const iconColors = ["", "purple", "file"];
    reportList.innerHTML = "";
    items.forEach((it, idx) => {
      const row = document.createElement("article");
      row.className = "report-row";
      row.dataset.reportId = it.id || "";
      const tagLabel = INSIGHT_TAG_LABELS_V14[it.insight_type] || "报告";
      const iconClass = iconColors[idx % iconColors.length];
      const iconHref = INSIGHT_ICON_HREFS_V14[it.insight_type] || "#icon-cube";
      row.style.cursor = "pointer";
      row.tabIndex = 0;
      row.innerHTML =
        '<span class="recent-item-icon ' +
        iconClass +
        '"><svg class="icon"><use href="' +
        iconHref +
        '" /></svg></span><div><strong>' +
        escapeHtml(it.title || "未命名") +
        "</strong><span>" +
        escapeHtml(tagLabel) +
        "</span></div><span>" +
        escapeHtml(formatReportDateV14(it.created_at)) +
        "</span>";
      reportList.appendChild(row);
    });
    reportList.dataset.bridgeBound = "true";
  }

  function renderSourceListInsightsFull(main, feedResp) {
    const sourceList = main.querySelector(
      ".insights-bottom-grid .split-panel:nth-child(2) .source-list",
    );
    if (!sourceList) return;
    const raw = unwrapData(feedResp) || {};
    const feedItems = (raw.items || []).slice(0, 3);
    if (!feedItems.length) return;
    sourceList.innerHTML = "";
    feedItems.forEach((it) => {
      const row = document.createElement("article");
      row.className = "source-row";
      row.dataset.cardId = it.id || "";
      const tag = (it.tags && it.tags[0]) || "灵感";
      row.innerHTML =
        '<span class="source-thumb"></span><div><strong>' +
        escapeHtml(it.title || "未命名") +
        "</strong><span>笔记 · " +
        escapeHtml(tag) +
        "</span></div><span>" +
        escapeHtml(relTime(it.created_at)) +
        "</span>";
      sourceList.appendChild(row);
    });
    sourceList.dataset.bridgeBound = "true";
  }

  async function hydrateInsightsFullMain() {
    const main = document.querySelector(".insights-full-main");
    if (!main) return;
    let summary = null;
    let listData = null;
    let feedData = null;
    try {
      summary = await apiFetch("/insights/summary?range=week");
    } catch (_e) { /* ignore */ }
    try {
      listData = await apiFetch("/insights?range=month&page_size=10");
    } catch (_e) { /* ignore */ }
    try {
      feedData = await apiFetch("/feed?page_size=3");
    } catch (_e) { /* ignore */ }
    renderMetricTilesInsightsFull(main, summary);
    renderCoreInsightCardsInsightsFull(main, summary);
    renderReportListInsightsFull(main, listData);
    renderSourceListInsightsFull(main, feedData);
    main.dataset.bridgeBound = "true";
  }

  async function loadCardForDrawer(cardId) {
    let card;
    try {
      card = await apiFetch("/cards/" + cardId);
    } catch (e) {
      console.warn("[v14] /cards/{id}", e);
      return null;
    }
    return unwrapData(card) || card;
  }

  function _findItemDetailDrawer() {
    return document.querySelector('[data-drawer="itemDetail"]');
  }

  function hydrateItemDetailDrawer(drawer, payload) {
    if (!drawer || !payload) return;
    const title = drawer.querySelector("h2");
    if (title) {
      title.textContent =
        payload.title || (payload.summary && payload.summary.slice(0, 60)) || "未命名";
    }
    const summary =
      drawer.querySelector(".drawer-summary") ||
      drawer.querySelector(".drawer-section p, article p, .panel-text");
    if (summary && payload.summary) summary.textContent = payload.summary;
    const tags = drawer.querySelector(".tag-list, .source-chip-list");
    if (tags && Array.isArray(payload.tags)) {
      tags.innerHTML = payload.tags
        .slice(0, 8)
        .map((t) => `<span class="tag">${escapeHtmlV14(String(t))}</span>`)
        .join("");
    }
    Array.from(drawer.querySelectorAll(".drawer-section")).forEach((section) => {
      const label = section.querySelector("h3")?.textContent || "";
      if (
        !section.dataset.bridgeCardSource &&
        !section.dataset.bridgeCardContent &&
        /来源|追溯|Source/i.test(label)
      ) {
        section.hidden = true;
      }
    });
    const cardText = String(payload.content || payload.raw_content || "").trim();
    const sourceObj = payload.source && typeof payload.source === "object" ? payload.source : null;
    const sourceLabel =
      payload.source_url ||
      payload.url ||
      (typeof payload.source === "string" ? payload.source : "") ||
      sourceObj?.url ||
      sourceObj?.name ||
      "手动输入";
    const sourceKind = payload.document_type || (sourceLabel.startsWith("http") ? "网页剪藏" : payload.content_type || "灵感记录");
    let contentSection = drawer.querySelector("[data-bridge-card-content]");
    if (!contentSection) {
      contentSection = document.createElement("div");
      contentSection.className = "drawer-section";
      contentSection.dataset.bridgeCardContent = "true";
      const actionSection = Array.from(drawer.querySelectorAll(".drawer-section")).find((sec) =>
        /下一步|Next/i.test(sec.querySelector("h3")?.textContent || ""),
      );
      const parent = actionSection?.parentElement || drawer.querySelector(".detail-drawer") || drawer;
      parent.insertBefore(contentSection, actionSection || null);
    }
    contentSection.innerHTML = `
      <h3>原始内容</h3>
      <p style="white-space:pre-wrap;line-height:1.75;word-break:break-word;">${escapeHtmlV14(cardText || "暂无原文")}</p>
    `;
    let sourceSection = drawer.querySelector("[data-bridge-card-source]");
    if (!sourceSection) {
      sourceSection = document.createElement("div");
      sourceSection.className = "drawer-section";
      sourceSection.dataset.bridgeCardSource = "true";
      contentSection.insertAdjacentElement("afterend", sourceSection);
    }
    sourceSection.innerHTML = `
      <h3>来源与追溯</h3>
      <article class="quick-setting">
        <svg class="icon"><use href="#icon-file-text" /></svg>
        <div>
          <strong>${escapeHtmlV14(sourceKind)}</strong>
          <span>${escapeHtmlV14(sourceLabel)} · ${cardText.length || 0} 字</span>
        </div>
        <svg class="icon"><use href="#icon-chevron-right" /></svg>
      </article>
    `;
    drawer.dataset.cardId = payload.id || "";
    drawer.dataset.cardFavorite = String(Boolean(payload.is_favorite));
    drawer.__bridgeCard = payload;
  }

  function revealItemDetailDrawerV18(payload) {
    const drawer = _findItemDetailDrawer();
    if (!drawer) return;
    hydrateItemDetailDrawer(drawer, payload);
    document.querySelectorAll(".drawer-layer").forEach((layer) => {
      if (layer === drawer) {
        layer.hidden = false;
        layer.classList.remove("is-leaving");
        document.body.classList.add("layer-lock");
        requestAnimationFrame(() => layer.classList.add("is-open"));
      } else if (layer.dataset.drawer) {
        layer.classList.remove("is-open");
        layer.hidden = true;
      }
    });
  }

  function bindCardClickToDrawer() {
    document.addEventListener(
      "click",
      async (event) => {
        const el = event.target.closest(
          ".idea-card[data-card-id], .record-card[data-card-id], .record-row[data-card-id], .recent-doc-row[data-card-id]",
        );
        if (!el) return;
        const cardId = el.dataset.cardId;
        if (!cardId) return;
        if (event.target.closest(".save-icon, .favorite, button, a")) return;
        const drawer = _findItemDetailDrawer();
        if (!drawer) return;
        const payload = await loadCardForDrawer(cardId);
        if (payload) hydrateItemDetailDrawer(drawer, payload);
        else toast("加载卡片详情失败", "error");
      },
      true,
    );
  }

  async function favoriteCardById(cardId, makeFavorite) {
    return apiFetch("/cards/" + cardId + "/favorite", {
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
          const unr = unwrapData(res) || res || {};
          const newFav = Boolean(unr.is_favorite ?? next);
          card.dataset.cardFavorite = String(newFav);
          star.classList.toggle("active", newFav);
          toast(newFav ? "已加入收藏" : "已取消收藏", "success");
        } catch (e) {
          toast("收藏失败: " + e.message, "error");
        }
      },
      true,
    );
  }

  function bindSkillRunModalContext() {
    document.addEventListener(
      "click",
      (event) => {
        const opener = event.target.closest('[data-open-modal="skillRun"]');
        if (!opener) return;
        const card = opener.closest(".skill-card[data-skill-id]") ||
          document.querySelector(".skills-open .skill-card[data-skill-id], .skill-grid .skill-card[data-skill-id]");
        if (card) V14.activeSkillId = card.dataset.skillId || "";
        queueMicrotask(() => {
          hydrateSkillRunModalDocumentPickerV165().catch(() => {});
        });
      },
      true,
    );
  }

  /**
   * §16.5 — Inject @KB document picker + generate vs transform toggles into the
   * skillRun modal without editing index.html. Populates from GET /kb/documents.
   */
  function injectSkillRunPickerStylesV18() {
    if (document.getElementById("mydow-skill-run-picker-v18")) return;
    const style = document.createElement("style");
    style.id = "mydow-skill-run-picker-v18";
    style.textContent = `
      .skill-doc-picker-v18 {
        display: grid;
        gap: 10px;
        margin-bottom: 14px;
        padding: 13px;
        border: 1px solid rgba(91,120,255,.18);
        border-radius: 18px;
        background: linear-gradient(180deg, rgba(255,255,255,.98), rgba(247,250,255,.94));
        box-shadow: 0 18px 48px rgba(42, 56, 95, .10);
      }
      .skill-doc-picker-v18 .picker-label {
        color: #4b5f81;
        font-size: 12px;
        font-weight: 820;
      }
      .skill-doc-picker-v18 .skill-doc-search {
        min-height: 43px;
        display: flex;
        align-items: center;
        gap: 9px;
        padding: 0 12px;
        border: 1px solid rgba(108,124,153,.16);
        border-radius: 14px;
        background: #fff;
      }
      .skill-doc-picker-v18 input[type="search"] {
        width: 100%;
        border: 0;
        outline: 0;
        color: #22304a;
        font-size: 13px;
        font-weight: 650;
        background: transparent;
      }
      .skill-doc-picker-v18 select[data-v16-skill-doc-select] {
        position: absolute !important;
        width: 1px !important;
        height: 1px !important;
        opacity: 0 !important;
        pointer-events: none !important;
      }
      .skill-doc-list-v18 {
        display: grid;
        gap: 7px;
        max-height: 210px;
        overflow: auto;
        padding-right: 4px;
      }
      .skill-doc-option-v18 {
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 10px 11px;
        border: 1px solid rgba(108,124,153,.14);
        border-radius: 14px;
        color: #26354f;
        background: rgba(255,255,255,.92);
        text-align: left;
        cursor: pointer;
      }
      .skill-doc-option-v18:hover,
      .skill-doc-option-v18:focus-visible {
        outline: 0;
        border-color: rgba(91,120,255,.36);
        background: #fff;
      }
      .skill-doc-option-v18[aria-selected="true"] {
        border-color: rgba(91,120,255,.52);
        background: rgba(239,244,255,.96);
        color: #3655c8;
      }
      .skill-doc-option-v18 strong { display:block;font-size:13px;line-height:1.25; }
      .skill-doc-option-v18 small { display:block;margin-top:3px;color:#7c899e;font-size:11px;font-weight:620; }
      .skill-run-mode-v18 {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
      }
      .skill-run-mode-v18 label {
        min-height: 34px;
        display: inline-flex;
        align-items: center;
        gap: 7px;
        padding: 0 11px;
        border: 1px solid rgba(108,124,153,.14);
        border-radius: 999px;
        background: rgba(255,255,255,.8);
        color: #4f5f79;
        font-size: 12px;
        font-weight: 720;
        cursor: pointer;
      }
      .skill-run-mode-v18 label:has(input:checked) {
        border-color: rgba(91,120,255,.34);
        background: rgba(239,244,255,.96);
        color: #3655c8;
      }
      .skill-run-mode-v18 input { accent-color: #5b78ff; }
      .skill-doc-picker-v18 .picker-meta {
        color: #7c899e;
        font-size: 11px;
        font-weight: 620;
      }
    `;
    document.head.appendChild(style);
  }

  async function hydrateSkillRunModalDocumentPickerV165() {
    const layer = document.querySelector('.surface-layer[data-modal="skillRun"]');
    if (!layer) return;
    const body = layer.querySelector(".modal-body .form-grid");
    if (!body || body.querySelector("[data-v16-skill-doc-picker]")) return;
    injectSkillRunPickerStylesV18();

    const wrap = document.createElement("div");
    wrap.dataset.v16SkillDocPicker = "true";
    wrap.className = "skill-doc-picker-v18";
    wrap.innerHTML =
      '<div class="picker-label">@ 知识库文档（可选）</div>' +
      '<label class="skill-doc-search"><svg class="icon" aria-hidden="true" style="width:15px;height:15px;color:#8090aa"><use href="#icon-search" /></svg>' +
      '<input type="search" data-v18-skill-doc-search role="searchbox" aria-label="搜索知识库文档" placeholder="搜索文档标题、摘要或标签..." autocomplete="off" /></label>' +
      '<select data-v16-skill-doc-select aria-label="选择知识库文档"><option value="">— 不引用文档，仅用下方输入 —</option></select>' +
      '<div class="skill-doc-list-v18" role="listbox" data-v18-skill-doc-list aria-label="Skill 知识库文档搜索结果"></div>' +
      '<div class="skill-run-mode-v18" data-v16-skill-mode-row>' +
      '<span class="picker-meta">输出</span>' +
      '<label>' +
      '<input type="radio" name="v16-skill-output-mode" value="generate" checked /> 生成新文档</label>' +
      '<label>' +
      '<input type="radio" name="v16-skill-output-mode" value="transform" /> 修改所选文档</label></div>' +
      '<label class="skill-output-folder-v20"><span class="picker-meta">新文档保存到</span>' +
      '<select data-v20-skill-output-folder aria-label="选择生成文档保存的知识库"><option value="">按 AI 标签自动归类</option></select></label>' +
      '<p class="picker-meta" data-v18-skill-doc-meta>' +
      "选择文档后，运行会把文档正文并入提示词；选「修改所选文档」时，LLM 输出会写回该文档而非新建。</p>";

    body.insertBefore(wrap, body.firstChild);

    const sel = wrap.querySelector("[data-v16-skill-doc-select]");
    const modeRow = wrap.querySelector("[data-v16-skill-mode-row]");
    const folderSel = wrap.querySelector("[data-v20-skill-output-folder]");
    const search = wrap.querySelector("[data-v18-skill-doc-search]");
    const list = wrap.querySelector("[data-v18-skill-doc-list]");
    const meta = wrap.querySelector("[data-v18-skill-doc-meta]");
    let docs = [];

    const renderDocs = (query) => {
      const q = String(query || "").trim().toLowerCase();
      const filtered = docs
        .filter((d) => {
          if (!q) return true;
          return [
            d.title,
            d.summary,
            d.folder_name,
            ...(Array.isArray(d.tags) ? d.tags : []),
          ].join(" ").toLowerCase().includes(q);
        })
        .slice(0, 24);
      if (meta) {
        meta.textContent = filtered.length
          ? `${filtered.length} 个可选文档${q ? " · " + query : ""}`
          : "没有找到匹配文档，可直接粘贴材料运行";
      }
      if (!list) return;
      if (!filtered.length) {
        list.innerHTML = '<div class="picker-meta" style="padding:12px;text-align:center;">暂无匹配文档</div>';
        return;
      }
      const selected = sel ? String(sel.value || "") : "";
      list.innerHTML = filtered.map((d) => {
        const title = escapeHtmlV14(String(d.title || "未命名文档"));
        const folder = escapeHtmlV14(String(d.folder_name || d.folder?.name || "知识库"));
        const summary = escapeHtmlV14(String(d.summary || "").slice(0, 72));
        const id = escapeHtmlV14(String(d.id || ""));
        return (
          `<button type="button" class="skill-doc-option-v18" role="option" tabindex="0" ` +
          `aria-selected="${String(d.id) === selected ? "true" : "false"}" data-doc-id="${id}">` +
          `<span><strong>${title}</strong><small>${folder}${summary ? " · " + summary : ""}</small></span>` +
          `</button>`
        );
      }).join("");
    };

    try {
      const foldersResp = await apiFetch("/kb/folders?include_counts=true&page_size=80").catch(() => null);
      const foldersData = foldersResp ? (unwrapData(foldersResp) || {}) : {};
      (foldersData.items || []).forEach((folder) => {
        if (!folder || !folder.id || !folderSel) return;
        const option = document.createElement("option");
        option.value = folder.id;
        option.textContent = String(folder.name || "未命名知识库").slice(0, 80);
        folderSel.appendChild(option);
      });
      const resp = await apiFetch("/kb/documents?page_size=48");
      const data = unwrapData(resp) || {};
      const items = data.items || [];
      docs = items;
      items.forEach((d) => {
        if (!d || !d.id) return;
        const o = document.createElement("option");
        o.value = d.id;
        o.textContent = String(d.title || "未命名").slice(0, 96);
        sel.appendChild(o);
      });
      renderDocs("");
    } catch (e) {
      console.warn("[Mydow v1.4] skillRun doc list failed", e);
      if (meta) meta.textContent = "读取知识库文档失败，可直接粘贴材料运行";
    }

    const syncMode = () => {
      const hasDoc = !!(sel && sel.value);
      if (!modeRow) return;
      modeRow.querySelectorAll('input[name="v16-skill-output-mode"]').forEach((inp) => {
        inp.disabled = !hasDoc && inp.value === "transform";
      });
      if (!hasDoc) {
        const gen = modeRow.querySelector('input[value="generate"]');
        if (gen) gen.checked = true;
      }
    };
    sel.addEventListener("change", syncMode);
    if (search) {
      let t = null;
      search.addEventListener("input", () => {
        window.clearTimeout(t);
        t = window.setTimeout(() => renderDocs(search.value), 140);
      });
      search.addEventListener("keydown", (ev) => {
        if (ev.key === "ArrowDown") {
          ev.preventDefault();
          list?.querySelector("button")?.focus();
        }
      });
    }
    if (list) {
      list.addEventListener("click", (ev) => {
        const opt = ev.target.closest("[data-doc-id]");
        if (!opt) return;
        const id = opt.dataset.docId || "";
        if (sel) {
          sel.value = id;
          sel.dispatchEvent(new Event("change", { bubbles: true }));
        }
        renderDocs(search ? search.value : "");
      });
      list.addEventListener("keydown", (ev) => {
        const opt = ev.target.closest("[data-doc-id]");
        if (!opt) return;
        const items = Array.from(list.querySelectorAll("[data-doc-id]"));
        const idx = items.indexOf(opt);
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          opt.click();
        } else if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
          ev.preventDefault();
          const next = ev.key === "ArrowDown"
            ? items[(idx + 1) % items.length]
            : items[(idx - 1 + items.length) % items.length];
          next?.focus();
        }
      });
    }
    syncMode();
  }

  // ─── KB ────────────────────────────────────────────────────────────────────
  function kbFilterFolders(tab, items) {
    if (!tab || tab === "all") return items;
    if (tab === "favorite") return items.filter((f) => f.is_favorite);
    const autoHints = /自动|收件|捕获|import/i;
    if (tab === "auto") return items.filter((f) => autoHints.test(f.name || ""));
    if (tab === "mine") return items.filter((f) => !autoHints.test(f.name || ""));
    return items;
  }

  async function loadKbLibraryGrid(kbTab) {
    const tab = kbTab || document.querySelector(".kb-tab.active")?.dataset.kbTab || "all";
    let resp;
    try {
      resp = await apiFetch("/kb/folders?include_counts=true");
    } catch (e) {
      console.warn("[Mydow v1.4] /kb/folders failed", e);
      return null;
    }
    const data = unwrapData(resp) || resp || {};
    const rawItems = data.items || [];
    V14.allFolders = rawItems;
    const items = kbFilterFolders(tab, rawItems).slice(0, 12);
    const cards = document.querySelectorAll(".library-card[data-open-folder]");
    if (!cards.length) return data;

    cards.forEach((card, idx) => {
      const folder = items[idx];
      if (!folder) {
        card.style.display = "none";
        return;
      }
      card.style.display = "";
      card.dataset.folderId = folder.id || "";
      card.dataset.bridgeBound = "true";
      const titleEl = card.querySelector("h2, h3, .library-card-title");
      if (titleEl) titleEl.textContent = folder.name || "未命名";
      const descEl = card.querySelector(".library-subtitle, .library-card-desc, p");
      if (descEl) {
        descEl.textContent =
          folder.description || descEl.textContent || "";
      }
      const stats = card.querySelector(".library-stats");
      if (stats) {
        const count = folder.document_count || folder.docCount || 0;
        const firstSpan = stats.querySelector("span");
        if (firstSpan) {
          const svg = firstSpan.querySelector("svg");
          firstSpan.textContent = "";
          if (svg) firstSpan.appendChild(svg);
          firstSpan.appendChild(document.createTextNode(" " + count + " 篇文档"));
        }
      }
      // §17.2 — reflect backend is_favorite onto the star button
      const star = card.querySelector(".star-action");
      if (star) {
        const isFav = !!folder.is_favorite;
        star.classList.toggle("active", isFav);
        star.setAttribute("aria-pressed", String(isFav));
      }
    });

    const listRows = document.querySelectorAll(".knowledge-main .kb-list-row[data-open-folder]");
    listRows.forEach((row, idx) => {
      const folder = items[idx];
      if (!folder) {
        row.style.display = "none";
        return;
      }
      row.style.display = "";
      row.dataset.prd10FolderId = folder.id || "";
      row.dataset.bridgeBound = "true";
      const strong = row.querySelector("strong");
      if (strong) strong.textContent = folder.name || "未命名";
      const sub = row.querySelector("div > span");
      if (sub && folder.description) sub.textContent = folder.description;
      const statSpans = row.querySelectorAll(".kb-list-stat");
      const cnt = folder.document_count || folder.docCount || 0;
      if (statSpans[0]) {
        const ic = statSpans[0].querySelector("svg");
        statSpans[0].textContent = "";
        if (ic) statSpans[0].appendChild(ic);
        statSpans[0].appendChild(document.createTextNode(" " + cnt + " 篇文档"));
      }
    });

    window.dispatchEvent(
      new CustomEvent("mydow:v14:kb-folders-loaded", {
        detail: { items: items.slice(0, 6), tab },
      }),
    );
    return data;
  }

  function bindKbTabCapture() {
    document.addEventListener(
      "click",
      (event) => {
        const tabBtn = event.target.closest("[data-kb-tab]");
        if (!tabBtn) return;
        window.setTimeout(() => {
          const t = tabBtn.dataset.kbTab || "all";
          loadKbLibraryGrid(t).catch(() => {});
        }, 80);
      },
      true,
    );
  }

  // ─── skills ───────────────────────────────────────────────────────────────
  /** §16.6 — remember a completed skill run so the grid can show 「✓ 已生成」. */
  function rememberSkillRunCompletedV16(skillId, documentId) {
    if (!skillId) return;
    V14.skillRunDoneIds[String(skillId)] = documentId
      ? String(documentId)
      : "1";
  }

  function ensureSkillGeneratedChipOnCard(card, docId) {
    let chip = card.querySelector("[data-skill-generated-chip]");
    if (!chip) {
      chip = document.createElement("span");
      chip.setAttribute("data-skill-generated-chip", "true");
      chip.className = "skill-generated-chip";
      const meta = card.querySelector(".skill-meta");
      if (meta) meta.after(chip);
      else card.appendChild(chip);
    }
    chip.textContent = "✓ 已生成";
    const hasDoc = !!(docId && docId !== "1");
    chip.title = hasDoc ? "已写入知识库 · 点击打开文档" : "最近一次运行已完成";
    chip.style.cursor = hasDoc ? "pointer" : "default";
    if (hasDoc) chip.dataset.generatedDocId = String(docId);
    else delete chip.dataset.generatedDocId;
    if (hasDoc && chip.dataset.docClickBound !== "true") {
      chip.dataset.docClickBound = "true";
      chip.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        const id = chip.dataset.generatedDocId;
        if (!id) return;
        if (window.MydowBridgeV14Ext && MydowBridgeV14Ext.openDocDrawer) {
          MydowBridgeV14Ext.openDocDrawer(String(id));
        } else {
          window.location.hash = "#/kb/doc/" + id;
        }
      });
    }
  }

  function paintSkillRunDoneChipsV16() {
    document.querySelectorAll(".skill-card[data-skill-id]").forEach((card) => {
      const sid = card.dataset.skillId;
      if (!sid || !V14.skillRunDoneIds[sid]) return;
      ensureSkillGeneratedChipOnCard(card, V14.skillRunDoneIds[sid]);
    });
  }

  /** Walk notification rows for `ai_output_saved` + `skill_run`, resolve run → skill_id. */
  async function ingestNotificationsForSkillRunChipsV16(rawItems) {
    if (!Array.isArray(rawItems) || !rawItems.length) return;
    const runIds = [];
    const seen = new Set();
    for (const n of rawItems) {
      if (String(n.type || "") !== "ai_output_saved") continue;
      if (String(n.object_type || "") !== "skill_run") continue;
      const oid = n.object_id;
      if (!oid || seen.has(oid)) continue;
      seen.add(oid);
      runIds.push(String(oid));
      if (runIds.length > 16) break;
    }
    if (!runIds.length) return;
    await Promise.all(
      runIds.map(async (rid) => {
        try {
          const r = await apiFetch(`/skills/runs/${rid}`);
          const d = unwrapData(r) || {};
          if (d.status === "completed" && d.skill_id) {
            const docId =
              d.output &&
              (d.output.document_id || d.output.saved_object_id);
            rememberSkillRunCompletedV16(String(d.skill_id), docId);
          }
        } catch (_e) {
          /* skip */
        }
      }),
    );
    paintSkillRunDoneChipsV16();
  }

  /** §15.40 — render ALL skills returned by /skills (was previously bounded to
   *  the 6 placeholder cards baked into the v1.4 HTML, hiding extras like
   *  "Markdown 美化", "OKR 拆解", "用户访谈大纲" etc).  We clone the first
   *  card to backfill any gap so the grid grows to match the API count.
   */
  const _SKILL_ICON_VARIANTS = ["", "purple", "green", "yellow"];

  async function loadSkillsGrid() {
    let resp;
    try {
      resp = await apiFetch("/skills?page_size=50");
    } catch (e) {
      console.warn("[Mydow v1.4] /skills failed", e);
      return null;
    }
    const data = unwrapData(resp) || resp || {};
    const items = data.items || [];
    V14.allSkills = items.slice();
    const hashFilter = readSkillFilterFromHashV18();
    if (hashFilter) V14.activeSkillFilter = hashFilter;
    const renderItems = V14.activeSkillFilter
      ? _filterSkillsByChip(V14.activeSkillFilter)
      : items;
    const grid =
      document.querySelector(".skills-open .skill-grid") ||
      document.querySelector(".skill-grid");
    if (!grid) return data;

    let cards = [...grid.querySelectorAll(".skill-card")];
    const template = cards[0];

    // Backfill: clone template card so we have at least items.length cards.
    while (cards.length < renderItems.length && template) {
      const clone = template.cloneNode(true);
      grid.appendChild(clone);
      cards.push(clone);
    }

    cards.forEach((card, idx) => {
      const sk = renderItems[idx];
      if (!sk) {
        card.style.display = "none";
        return;
      }
      card.style.display = "";
      card.dataset.skillId = sk.id || "";
      card.dataset.bridgeBound = "true";

      const h = card.querySelector("h3");
      if (h) h.textContent = sk.name || "Skill";
      const p = card.querySelector("p");
      if (p) p.textContent = sk.description || sk.summary || "";

      // Cycle icon variant by index to keep palette varied.
      const icon = card.querySelector(".skill-icon");
      if (icon) {
        icon.classList.remove("purple", "green", "yellow");
        const variant = _SKILL_ICON_VARIANTS[idx % _SKILL_ICON_VARIANTS.length];
        if (variant) icon.classList.add(variant);
      }

      // Render real tag list (replace the static "用户研究 / 洞察分析" 等).
      const tagHost = card.querySelector(".tags");
      if (tagHost) {
        const tags = [sk.category, ...(sk.tags || [])]
          .filter(Boolean)
          .slice(0, 3);
        if (tags.length) {
          tagHost.innerHTML = tags
            .map((t) => `<span class="tag">${escapeHtmlV14(String(t))}</span>`)
            .join("");
        }
      }

      // Replace the static "by Momo / ★ 4.9 / 1.2k" meta with REAL author + uses.
      const meta = card.querySelector(".skill-meta");
      if (meta) {
        const author = sk.author || sk.created_by || "Mydow 团队";
        const usage = sk.usage_count != null ? sk.usage_count : "—";
        const button = meta.querySelector("button");
        const buttonHtml = button ? button.outerHTML : '<button class="pill-button small bridge-skill-run" type="button" data-open-modal="skillRun">试用</button>';
        meta.innerHTML =
          `<span>by ${escapeHtmlV14(String(author))}</span>` +
          `<span>使用 ${escapeHtmlV14(String(usage))} 次</span>` +
          `<span>${escapeHtmlV14(sk.category || "")}</span>` +
          buttonHtml;
        // Re-attach data-open-modal on the button (cloning may have stripped it).
        const btn = meta.querySelector("button");
        if (btn && !btn.getAttribute("data-open-modal")) {
          btn.setAttribute("data-open-modal", "skillRun");
        }
      }
    });

    window.dispatchEvent(
      new CustomEvent("mydow:v14:skills-loaded", {
        detail: { count: renderItems.length, total: items.length, filter: V14.activeSkillFilter || "全部" },
      }),
    );
    paintSkillRunDoneChipsV16();
    markSkillFilterActiveV18(V14.activeSkillFilter || "全部");
    renderSkillFilterEmptyStateV18(renderItems, V14.activeSkillFilter || "全部");
    // §17.5 — render the personalized recommendations drawer above the grid
    loadSkillRecommendationsV17(items).catch(() => {});
    return data;
  }

  // §17.5 — Personalized Skill recommendations drawer.
  //
  // Calls `GET /api/v1/skills/recommendations` (already implemented at
  // `skills/router.py:587`) which scores skills by tag overlap with the
  // user's recent Card.tags + favourite signals. We render a collapsible
  // `<details>` "summary + grid" widget directly inside `.skills-main`.
  // The drawer is **collapsed by default** so it stays out of the way
  // until the user opens it (per the user's pain-point: 个性化推荐展示不
  // 完整, 隐藏栏点击展开).
  function formatSkillRecommendationScoreV17(raw) {
    const n = Number(raw || 0);
    if (!Number.isFinite(n) || n <= 0) return "";
    const pct = n <= 1 ? n * 100 : n;
    return Math.max(1, Math.min(100, Math.round(pct))) + "%";
  }

  async function loadSkillRecommendationsV17(allSkills) {
    const main = document.querySelector(".skills-main");
    if (!main) return;
    let resp;
    try {
      resp = await apiFetch("/skills/recommendations?limit=6");
    } catch (e) {
      console.warn("[Mydow v1.4] /skills/recommendations failed", e);
      return;
    }
    const data = unwrapData(resp) || resp || {};
    const recs = data.items || [];
    let drawer = main.querySelector(".skill-rec-drawer");
    if (!drawer) {
      drawer = document.createElement("details");
      drawer.className = "skill-rec-drawer";
      const summary = document.createElement("summary");
      summary.innerHTML =
        '为你推荐 <span style="color:#5b78ff;font-weight:600;font-size:12px;margin-left:6px;">' +
        recs.length + " 个 Skill</span>";
      drawer.appendChild(summary);
      const grid = document.createElement("div");
      grid.className = "rec-grid";
      drawer.appendChild(grid);
      // Insert at the top of main, before the existing grid header
      const firstChild = main.firstElementChild;
      if (firstChild) main.insertBefore(drawer, firstChild);
      else main.appendChild(drawer);
    }
    const grid = drawer.querySelector(".rec-grid");
    grid.innerHTML = "";
    if (!recs.length) {
      const empty = document.createElement("div");
      empty.className = "rec-empty";
      empty.textContent =
        "暂无个性化推荐 — 多用一些 Skill 或在「灵感采集」打更多标签后再来看看。";
      grid.appendChild(empty);
      return;
    }
    recs.forEach((rec) => {
      const card = document.createElement("div");
      card.className = "rec-card";
      card.dataset.skillId = rec.id;
      const title = document.createElement("div");
      title.className = "rec-card-title";
      title.textContent = rec.name || "Skill";
      const reason = document.createElement("div");
      reason.className = "rec-card-reason";
      const recScore = formatSkillRecommendationScoreV17(rec.recommendation_score);
      const score = recScore ? "匹配度 " + recScore + " · " : "";
      reason.textContent =
        score + (rec.recommendation_reason || rec.description || rec.summary || "");
      card.appendChild(title);
      card.appendChild(reason);
      card.addEventListener("click", () => {
        V14.activeSkillId = rec.id;
        // Open the skillRun modal directly via the IIFE plumbing
        const opener = document.querySelector('[data-open-modal="skillRun"]');
        if (opener) opener.click();
        else toast("无法打开运行面板", "warning");
      });
      grid.appendChild(card);
    });

    // Sidebar card + «其他推荐» (`.skills-drawer`) — same API payload, second surface.
    try {
      hydrateSkillsDrawerRecommendationsV17(data, recs);
    } catch (_e) {
      /* ignore */
    }

    return data;
  }

  /** §17.5 — sidebar `.skills-drawer` top card + compact list (paired with main-page drawer). */
  function hydrateSkillsDrawerRecommendationsV17(data, items) {
    if (!items || !items.length) return data;
    const card = document.querySelector(".skills-drawer .recommend-card");
    if (card) {
      const top = items[0];
      const titleEl = card.querySelector("h3");
      const descEl = card.querySelector("p");
      const button = card.querySelector(".pill-button");
      if (titleEl) titleEl.textContent = top.name || "推荐 Skill";
      if (descEl) {
        const matched = (top.matched_tags || []).slice(0, 3).join(" / ");
        descEl.textContent =
          (top.description || "").trim() +
          (matched ? `（匹配关键词：${matched}）` : "");
      }
      if (button) {
        button.dataset.skillId = top.id || "";
        button.dataset.bridgeBound = "true";
      }
      card.dataset.skillId = top.id || "";
      card.dataset.matched = (top.matched_tags || []).join(",");
    }

    const drawer = document.querySelector(".skills-drawer .insight-panel");
    if (drawer && items.length > 1) {
      let extra = drawer.querySelector("[data-v17-recommend-list]");
      if (!extra || extra.tagName !== "DETAILS") {
        const old = extra;
        extra = document.createElement("details");
        extra.dataset.v17RecommendList = "true";
        extra.className = "skill-side-rec-list-v18";
        const recCard = drawer.querySelector(".recommend-card");
        if (old && old.parentNode) {
          old.replaceWith(extra);
        } else if (recCard && recCard.parentNode === drawer) {
          recCard.insertAdjacentElement("afterend", extra);
        } else {
          drawer.appendChild(extra);
        }
      }
      const wasOpen = !!extra.open;
      extra.innerHTML = "";
      const summary = document.createElement("summary");
      summary.innerHTML = `<span>其他推荐 Skill</span><small>${items.length - 1} 个</small>`;
      extra.appendChild(summary);
      const rows = document.createElement("div");
      rows.className = "skill-side-rec-items-v18";
      extra.appendChild(rows);
      extra.open = wasOpen;
      items.slice(1).forEach((it) => {
        const row = document.createElement("article");
        row.className = "compact-row";
        row.dataset.skillId = it.id;
        row.innerHTML = `
          <span class="recent-item-icon"><svg class="icon"><use href="#icon-sparkles" /></svg></span>
          <strong>${escapeHtmlV14(it.name || "")}</strong>
          <span>${formatSkillRecommendationScoreV17(it.recommendation_score)}</span>
        `;
        row.addEventListener("click", () => {
          V14.activeSkillId = it.id;
          const sc = document.querySelector(`.skill-card[data-skill-id="${it.id}"]`);
          if (sc) {
            const tryButton = sc.querySelector('[data-open-modal="skillRun"], .pill-button');
            if (tryButton) {
              tryButton.click();
              return;
            }
          }
          const opener = document.querySelector('[data-open-modal="skillRun"]');
          if (opener) opener.click();
        });
        rows.appendChild(row);
      });
    }
    return data;
  }

  function bindSkillCardStash() {
    document.addEventListener(
      "click",
      (event) => {
        const card = event.target.closest(".skill-card[data-skill-id]");
        if (card) V14.activeSkillId = card.dataset.skillId || "";
      },
      true,
    );
  }

  // ─── §16.7 — Skill detail drawer：GET /skills/{id}/runs → 「运行历史」 ───
  let _skillDetailRunsFetchGen = 0;

  async function hydrateSkillDetailRunHistoryV17(skillId) {
    const layer = document.querySelector('[data-drawer="skillDetail"]');
    if (!layer) return;
    const aside = layer.querySelector("aside.detail-drawer");
    if (!aside) return;
    let host = aside.querySelector(".bridge-skill-detail-run-history");
    if (!host) {
      host = document.createElement("div");
      host.className = "drawer-section bridge-skill-detail-run-history";
      host.setAttribute("aria-live", "polite");
      const sections = [...aside.querySelectorAll(":scope > .drawer-section")];
      const ops = sections.find((sec) => {
        const h = sec.querySelector(":scope > h3");
        return h && h.textContent.trim() === "操作";
      });
      if (ops && ops.parentNode === aside) aside.insertBefore(host, ops);
      else aside.appendChild(host);
    }

    const gen = ++_skillDetailRunsFetchGen;
    host.innerHTML =
      '<h3>运行历史</h3><p class="bridge-run-history-loading" style="color:#718098;font-size:13px;margin:0;">加载中…</p>';

    const sid = String(skillId || "").trim();
    if (!sid) {
      host.innerHTML =
        '<h3>运行历史</h3><p style="color:#718098;font-size:13px;margin:0;">无法解析 Skill ID（请先点击一张 Skill 卡片）</p>';
      return;
    }

    try {
      const raw = await apiFetch(
        "/skills/" + encodeURIComponent(sid) + "/runs?page=1&page_size=8",
      );
      const data = unwrapData(raw) || {};
      if (gen !== _skillDetailRunsFetchGen) return;
      const items = data.items || [];
      const heading = "<h3>运行历史</h3>";
      if (!items.length) {
        host.innerHTML =
          heading +
          '<p style="color:#718098;font-size:13px;margin:0;">暂无运行记录。点击「立即试用」开始第一次运行。</p>';
        return;
      }
      const rows = items.map((run) => {
        const prev = String(run.output_preview || "")
          .replace(/\s+/g, " ")
          .trim();
        const shortPrev =
          prev.length > 140 ? prev.slice(0, 140) + "…" : prev;
        const when = run.completed_at || run.created_at || "";
        let whenLabel = "—";
        if (when) {
          const dt = new Date(when);
          whenLabel = Number.isNaN(dt.getTime())
            ? when
            : dt.toLocaleString("zh-CN", {
                month: "numeric",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              });
        }
        const st = String(run.status || "—");
        const statusColor =
          st === "completed"
            ? "#2f855a"
            : st === "failed"
              ? "#c53030"
              : "#718098";
        const rid = escapeHtmlV14(run.id || "");
        const documentId = escapeHtmlV14(run.document_id || run.output_object_id || "");
        return (
          '<article class="quick-setting bridge-skill-run-row" data-skill-run-id="' +
          rid +
          '" data-document-id="' +
          documentId +
          '" style="cursor:pointer;">' +
          '<svg class="icon"><use href="#icon-sparkles" /></svg>' +
          '<div><strong>' +
          escapeHtmlV14(whenLabel) +
          '</strong><span style="display:block;font-size:12px;color:' +
          statusColor +
          ";margin-top:2px;\">" +
          escapeHtmlV14(st) +
          "</span>" +
          (shortPrev
            ? '<span style="display:block;margin-top:6px;font-size:12px;color:#4a5568;line-height:1.45;">' +
              escapeHtmlV14(shortPrev) +
              "</span>"
            : "") +
          "</div></article>"
        );
      });
      host.innerHTML =
        heading +
        '<div class="bridge-run-history-list" style="display:flex;flex-direction:column;gap:8px;margin-top:8px;">' +
        rows.join("") +
        "</div>";
    } catch (e) {
      if (gen !== _skillDetailRunsFetchGen) return;
      host.innerHTML =
        '<h3>运行历史</h3><p style="color:#c53030;font-size:13px;margin:0;">加载失败：' +
        escapeHtmlV14(e && e.message ? e.message : String(e)) +
        "</p>";
    }
  }

  function bindSkillDetailRunHistoryV17() {
    const layer = document.querySelector('[data-drawer="skillDetail"]');
    if (!layer) return;
    const obs = new MutationObserver(() => {
      if (layer.hidden) return;
      const sid = V14.activeSkillId || "";
      hydrateSkillDetailRunHistoryV17(sid).catch(() => {});
    });
    obs.observe(layer, { attributes: true, attributeFilter: ["hidden"] });
    if (!layer.hidden) {
      hydrateSkillDetailRunHistoryV17(V14.activeSkillId || "").catch(() => {});
    }
    document.addEventListener(
      "click",
      async (event) => {
        const row = event.target.closest(".bridge-skill-run-row[data-skill-run-id]");
        if (!row) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const docId = row.dataset.documentId || "";
        if (docId) {
          await openKbDocumentEditorV20(docId);
          return;
        }
        const runId = row.dataset.skillRunId || "";
        if (!runId) return;
        try {
          const raw = await apiFetch("/skills/runs/" + encodeURIComponent(runId));
          const data = unwrapData(raw) || raw || {};
          const output = data.output || {};
          const nextDocId = output.document_id || output.saved_object_id || data.output_object_id || "";
          if (nextDocId) {
            await openKbDocumentEditorV20(nextDocId);
          } else {
            _renderSkillResultDrawer(data.skill_name || "Skill", data);
          }
        } catch (e) {
          toast("打开运行结果失败: " + e.message, "error");
        }
      },
      true,
    );
  }

  // ─── §15.40 — Skills 广场 category filter chips ──────────────────────────
  // The v1.4 prototype renders 8 plain `.skill-chip` buttons (全部 / 热门 /
  // 最新 / 内容创作 / 研究分析 / 效率工具 / 工作流 / 我的收藏) without any
  // data-* hooks. This binder reads the chip text on click, filters the
  // currently-cached skill list (from V14.allSkills) by category mapping or
  // localStorage favorites, and re-renders the grid in-place.

  const _SKILL_FILTER_SLUGS_V18 = {
    "全部": "all",
    "热门": "hot",
    "最新": "new",
    "内容创作": "content",
    "研究分析": "research",
    "效率工具": "productivity",
    "工作流": "workflow",
    "我的收藏": "favorites",
  };
  const _SKILL_FILTER_LABELS_V18 = Object.fromEntries(
    Object.entries(_SKILL_FILTER_SLUGS_V18).map(([label, slug]) => [slug, label]),
  );

  function normalizeSkillFilterLabelV18(label) {
    const raw = String(label || "").replace(/\s+/g, "");
    const known = Object.keys(_SKILL_FILTER_SLUGS_V18).find((it) => raw.includes(it));
    return known || "全部";
  }

  function readSkillFilterFromHashV18() {
    const hash = String(window.location.hash || "");
    const match = hash.match(/[?&]filter=([^&]+)/);
    if (!match) return "";
    const value = decodeURIComponent(match[1] || "");
    return _SKILL_FILTER_LABELS_V18[value] || normalizeSkillFilterLabelV18(value);
  }

  function syncSkillFilterHashV18(label) {
    const clean = normalizeSkillFilterLabelV18(label);
    const slug = _SKILL_FILTER_SLUGS_V18[clean] || encodeURIComponent(clean);
    const next = window.location.pathname + window.location.search + "#skills?filter=" + slug;
    if (window.location.pathname + window.location.search + window.location.hash !== next) {
      window.history.replaceState(null, "", next);
    }
  }

  function openSkillsFromHashV18() {
    if (!String(window.location.hash || "").startsWith("#skills")) return;
    window.setTimeout(() => {
      const page = document.querySelector(".page");
      if (!page || page.classList.contains("skills-open")) return;
      const nav = document.querySelector('[data-nav-target="skills"]');
      if (nav) nav.click();
    }, 0);
  }

  function skillFilterBlobV18(skill) {
    return [
      skill.name,
      skill.description,
      skill.summary,
      skill.category,
      skill.author,
      skill.created_by,
      ...(Array.isArray(skill.tags) ? skill.tags : []),
    ].filter(Boolean).join(" ").toLowerCase();
  }

  const _SKILL_CATEGORY_BUCKETS = {
    "热门": (a, b) =>
      (Number(b.usage_count || 0) + Number(b.favorite_count || 0)) -
      (Number(a.usage_count || 0) + Number(a.favorite_count || 0)),
    "最新": (a, b) => {
      const at = Date.parse(a.created_at || a.updated_at || a.last_used_at || "") || 0;
      const bt = Date.parse(b.created_at || b.updated_at || b.last_used_at || "") || 0;
      return bt - at;
    },
  };

  const _SKILL_CATEGORY_GROUPS = {
    "内容创作": ["writing", "format", "content", "markdown", "邮件", "写作", "内容", "卡片"],
    "研究分析": ["research", "interview", "analysis", "竞品", "研究", "访谈", "分析"],
    "效率工具": ["productivity", "ideate", "okr", "效率", "脑暴", "拆解"],
    "工作流": ["report", "development", "workflow", "周报", "代码", "流程"],
  };

  function markSkillFilterActiveV18(label) {
    const clean = normalizeSkillFilterLabelV18(label);
    document.querySelectorAll(".skills-categories .skill-chip").forEach((chip) => {
      const active = normalizeSkillFilterLabelV18(chip.textContent || "") === clean;
      chip.classList.toggle("active", active);
      chip.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }

  function renderSkillFilterEmptyStateV18(items, label) {
    const grid =
      document.querySelector(".skills-open .skill-grid") ||
      document.querySelector(".skill-grid");
    if (!grid) return;
    let empty = grid.querySelector("[data-v18-skill-filter-empty]");
    if (items && items.length) {
      if (empty) empty.remove();
      return;
    }
    if (!empty) {
      empty = document.createElement("div");
      empty.dataset.v18SkillFilterEmpty = "true";
      empty.className = "skill-filter-empty-v18";
      grid.appendChild(empty);
    }
    empty.textContent = `暂无「${normalizeSkillFilterLabelV18(label)}」Skill，换个分类看看。`;
  }

  function _renderSkillsGridFromCache(items) {
    const grid =
      document.querySelector(".skills-open .skill-grid") ||
      document.querySelector(".skill-grid");
    if (!grid) return;
    let cards = [...grid.querySelectorAll(".skill-card")];
    const template = cards[0];
    while (cards.length < items.length && template) {
      const clone = template.cloneNode(true);
      grid.appendChild(clone);
      cards.push(clone);
    }
    cards.forEach((card, idx) => {
      const sk = items[idx];
      if (!sk) {
        card.style.display = "none";
        return;
      }
      card.style.display = "";
      card.dataset.skillId = sk.id || "";
      card.dataset.bridgeBound = "true";
      const h = card.querySelector("h3");
      if (h) h.textContent = sk.name || "Skill";
      const p = card.querySelector("p");
      if (p) p.textContent = sk.description || sk.summary || "";
      const tagHost = card.querySelector(".tags");
      if (tagHost) {
        const tags = [sk.category, ...(sk.tags || [])]
          .filter(Boolean)
          .slice(0, 3);
        if (tags.length) {
          tagHost.innerHTML = tags
            .map((t) => `<span class="tag">${escapeHtmlV14(String(t))}</span>`)
            .join("");
        }
      }
      const meta = card.querySelector(".skill-meta");
      if (meta) {
        const author = sk.author || sk.created_by || "Mydow 团队";
        const usage = sk.usage_count != null ? sk.usage_count : "—";
        const button = meta.querySelector("button");
        const buttonHtml = button
          ? button.outerHTML
          : '<button class="pill-button small bridge-skill-run" type="button" data-open-modal="skillRun">试用</button>';
        meta.innerHTML =
          `<span>by ${escapeHtmlV14(String(author))}</span>` +
          `<span>使用 ${escapeHtmlV14(String(usage))} 次</span>` +
          `<span>${escapeHtmlV14(sk.category || "")}</span>` +
          buttonHtml;
        const btn = meta.querySelector("button");
        if (btn && !btn.getAttribute("data-open-modal")) {
          btn.setAttribute("data-open-modal", "skillRun");
        }
      }
    });
    renderSkillFilterEmptyStateV18(items, V14.activeSkillFilter || "全部");
  }

  function _filterSkillsByChip(label) {
    const clean = normalizeSkillFilterLabelV18(label);
    const all = (V14.allSkills || []).slice();
    if (!clean || clean === "全部") return all;
    if (clean === "我的收藏") {
      let favs = [];
      try {
        favs = JSON.parse(window.localStorage.getItem("mydow_v14_fav_skills") || "[]");
      } catch { /* ignore */ }
      const set = new Set(favs);
      return all.filter((s) => set.has(s.id) || s.is_favorite === true);
    }
    const sortFn = _SKILL_CATEGORY_BUCKETS[clean];
    if (sortFn) return all.slice().sort(sortFn);
    const cats = _SKILL_CATEGORY_GROUPS[clean];
    if (cats) {
      return all.filter((s) => {
        const blob = skillFilterBlobV18(s);
        return cats.some((c) => blob.includes(String(c).toLowerCase()));
      });
    }
    return all;
  }

  function applySkillsFilterV18(label, options) {
    const clean = normalizeSkillFilterLabelV18(label);
    V14.activeSkillFilter = clean === "全部" ? "" : clean;
    const items = _filterSkillsByChip(clean);
    markSkillFilterActiveV18(clean);
    _renderSkillsGridFromCache(items);
    renderSkillFilterEmptyStateV18(items, clean);
    if (!options || options.syncUrl !== false) syncSkillFilterHashV18(clean);
    window.dispatchEvent(
      new CustomEvent("mydow:v14:skills-filter", {
        detail: { label: clean, count: items.length, total: (V14.allSkills || []).length },
      }),
    );
    return items;
  }

  function bindSkillsCategoryFilterV40() {
    document.addEventListener(
      "click",
      (event) => {
        const chip = event.target.closest(".skills-categories .skill-chip");
        if (!chip) return;
        // Allow IIFE to update active class first.
        window.setTimeout(() => {
          applySkillsFilterV18(chip.textContent || "全部");
        }, 60);
      },
      true,
    );
  }

  /** Re-hydrate Skills grid when the user navigates to the Skills page so all
   *  seeded items (>6) appear immediately even if the very first boot call
   *  already populated the page. */
  function bindSkillsPageHydration() {
    const page = document.querySelector(".page");
    if (!page) return;
    let lastOpen = page.classList.contains("skills-open");
    let busy = false;
    const obs = new MutationObserver(() => {
      const isOpen = page.classList.contains("skills-open");
      if (isOpen && !lastOpen && !busy) {
        busy = true;
        loadSkillsGrid()
          .catch(() => {})
          .finally(() => { busy = false; });
      }
      lastOpen = isOpen;
    });
    obs.observe(page, { attributes: true, attributeFilter: ["class"] });
  }

  // ─── garden (overview text) ───────────────────────────────────────────────
  async function refreshGardenBoard() {
    const main = document.querySelector(".garden-main");
    if (!main) return null;
    // §17.3 — pass the user's filter selections to the backend
    const range = V14.gardenRange || "90d";
    const type = V14.gardenType || "all";
    let resp;
    try {
      const q = new URLSearchParams();
      q.set("range", range);
      if (type !== "all") q.set("type", type);
      resp = await apiFetch("/garden/overview?" + q.toString());
    } catch (e) {
      // Fall back to no-param call if the new query params aren't supported
      try {
        resp = await apiFetch("/garden/overview");
      } catch (e2) {
        return null;
      }
    }
    const d = unwrapData(resp) || {};
    const topics = Array.isArray(d.top_topics) ? d.top_topics : [];
    const edgeCount = Number(d.edge_count || 0);

    const pillButtons = main.querySelectorAll(".garden-filters .pill-button");
    const edgePill = [...pillButtons].find((b) =>
      /连接数/.test(b.textContent || ""),
    );
    if (edgePill) {
      [...edgePill.childNodes]
        .filter((n) => n.nodeType === Node.TEXT_NODE)
        .forEach((n) => n.remove());
      edgePill.appendChild(document.createTextNode("连接数 " + edgeCount));
      edgePill.dataset.bridgeBound = "true";
    }

    const coreStrong = main.querySelector(
      ".garden-node.core .node-copy strong, .garden-node.core strong",
    );
    if (coreStrong && topics[0]) coreStrong.textContent = topics[0];
    const coreNode = main.querySelector(".garden-node.core");
    if (coreNode && topics[0]) {
      coreNode.dataset.gardenTopic = topics[0];
      coreNode.dataset.bridgeBound = "true";
      coreNode.style.cursor = "pointer";
    }

    const satellites = [
      ...main.querySelectorAll(".garden-map .garden-node:not(.core)"),
    ].slice(0, 6);
    satellites.forEach((node, i) => {
      const topic = topics[i + 1];
      if (!topic) return;
      const el = node.querySelector(".node-copy strong, strong");
      if (el) el.textContent = topic;
      node.dataset.gardenTopic = topic;
      node.dataset.bridgeBound = "true";
      node.style.cursor = "pointer";
    });

    main.dataset.bridgeEdgeCount = String(edgeCount);
    return d;
  }

  function attachGardenTopicSearchV14() {
    const main = document.querySelector(".garden-main");
    if (!main || main.dataset.v14GardenSearch === "true") return;
    main.dataset.v14GardenSearch = "true";
    main.addEventListener(
      "click",
      async (ev) => {
        const node = ev.target.closest(".garden-node[data-garden-topic]");
        if (!node) return;
        const topic = node.dataset.gardenTopic;
        if (!topic) return;
        ev.preventDefault();
        ev.stopPropagation();
        // §17.3 — Open the nodeDetail drawer with real backend data
        // (search hits + summary) so node clicks become a real navigation
        // affordance rather than a passing toast.
        try {
          const r = await apiFetch(
            "/search?q=" + encodeURIComponent(topic) + "&page_size=8",
          );
          const data = unwrapData(r) || {};
          const items = data.items || [];
          openGardenNodeDetailV17(topic, items);
        } catch (e) {
          toast("搜索失败: " + e.message, "error");
        }
      },
      false,
    );
  }

  // §17.3 — Render real node detail into the v1.4 nodeDetail drawer.
  //
  // The IIFE prototype renders a static drawer when `[data-open-drawer="nodeDetail"]`
  // is clicked. We keep the IIFE drawer animation but rewrite its content
  // with real /search hits + a topic header. The drawer surface is
  // `.drawer[data-drawer="nodeDetail"]`; we mutate the nodes within it in
  // place so the IIFE close handler still works.
  function openGardenNodeDetailV17(topic, items) {
    // Trigger the IIFE drawer-open path via a synthetic click on the
    // hidden control, so animations and `aria-hidden=false` are applied
    // by the prototype's own DOM machinery.
    const trigger =
      document.querySelector('[data-open-drawer="nodeDetail"]') ||
      document.querySelector('.garden-filters [data-open-drawer="nodeDetail"]');
    if (trigger) trigger.click();

    // Wait one tick so the IIFE has time to mount the drawer.
    window.setTimeout(() => {
      const drawer =
        document.querySelector('.drawer[data-drawer="nodeDetail"]') ||
        document.querySelector('.drawer.is-open[data-drawer]');
      if (!drawer) return;
      const titleEl =
        drawer.querySelector("h3, h2, .drawer-title") || drawer.querySelector("strong");
      if (titleEl) titleEl.textContent = topic;
      // Replace the content area with real hits.
      const body =
        drawer.querySelector(".drawer-body") ||
        drawer.querySelector(".drawer-content") ||
        drawer;
      const list = document.createElement("ul");
      list.style.cssText =
        "margin: 12px 0 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 8px;";
      if (!items.length) {
        const empty = document.createElement("p");
        empty.style.cssText = "color: #97a3b7; font-size: 13px; padding: 12px 0;";
        empty.textContent = "「" + topic + "」暂无相关内容";
        body.querySelectorAll("[data-v17-node-list]").forEach((el) => el.remove());
        const wrap = document.createElement("div");
        wrap.dataset.v17NodeList = "true";
        wrap.appendChild(empty);
        body.appendChild(wrap);
        return;
      }
      items.slice(0, 8).forEach((hit) => {
        const li = document.createElement("li");
        li.style.cssText =
          "padding: 10px 12px; background: rgba(91,120,255,0.05); border-radius: 10px; cursor: pointer;";
        const title = document.createElement("div");
        title.style.cssText = "font-weight: 700; color: #1d2742; font-size: 13px;";
        title.textContent = hit.title || "未命名";
        const meta = document.createElement("div");
        meta.style.cssText = "color: #6b7892; font-size: 11px; margin-top: 4px;";
        meta.textContent = (hit.object_type || hit.type || "结果") +
          (hit.summary ? " · " + (hit.summary || "").slice(0, 60) : "");
        li.appendChild(title);
        li.appendChild(meta);
        li.addEventListener("click", () => {
          // Reuse search result navigation for consistency
          if (typeof window.handleGlobalSearchHit === "function") {
            window.handleGlobalSearchHit(hit);
          } else {
            toast("打开「" + (hit.title || "结果") + "」", "success");
          }
        });
        list.appendChild(li);
      });
      // Replace any prior bridge-injected list
      body.querySelectorAll("[data-v17-node-list]").forEach((el) => el.remove());
      const wrap = document.createElement("div");
      wrap.dataset.v17NodeList = "true";
      wrap.appendChild(list);
      body.appendChild(wrap);
    }, 60);
  }

  function attachGardenControlHandlersV14() {
    const board = document.querySelector(".garden-main .garden-board");
    if (!board || board.dataset.v14GardenControls === "true") return;
    board.dataset.v14GardenControls = "true";

    document.addEventListener(
      "click",
      (ev) => {
        const btn = ev.target.closest(".garden-board .zoom-control button");
        if (!btn || !board.contains(btn)) return;
        const label = btn.getAttribute("data-toast") || "";
        if (label.includes("缩小")) {
          V14.gardenZoom = Math.max(0.6, V14.gardenZoom - 0.1);
        } else if (label.includes("放大")) {
          V14.gardenZoom = Math.min(1.6, V14.gardenZoom + 0.1);
        } else {
          return;
        }
        ev.preventDefault();
        ev.stopImmediatePropagation();
        const map = board.querySelector(".garden-map");
        const zoomSpan = board.querySelector(".garden-controls .zoom-control span");
        if (map) map.style.transform = "scale(" + V14.gardenZoom + ")";
        if (zoomSpan) zoomSpan.textContent = Math.round(V14.gardenZoom * 100) + "%";
        toast(label, "success");
      },
      true,
    );

    document.addEventListener(
      "click",
      (ev) => {
        const tool = ev.target.closest(
          ".garden-controls .square-tool[aria-label=\"切换图谱布局\"]",
        );
        if (!tool || !board.contains(tool)) return;
        ev.preventDefault();
        ev.stopImmediatePropagation();
        V14.gardenLayout = (V14.gardenLayout + 1) % 3;
        const svg = board.querySelector(".garden-network-svg");
        const deg = V14.gardenLayout === 0 ? 0 : V14.gardenLayout === 1 ? -5 : 6;
        if (svg) {
          svg.style.transform = "rotate(" + deg + "deg)";
          svg.style.transition = "transform 220ms ease-out";
        }
        toast("已切换图谱布局", "success");
      },
      true,
    );
  }

  // §17.3 — Garden inline-menu real backend filtering.
  //
  // The IIFE prototype renders the gardenTime / gardenType menus as visual
  // popovers but the picked option only updates the chip label — no API
  // request is made. We watch for the "label changed" mutation on the
  // chip text node and re-fetch /garden/graph with the new range/type so
  // the SVG and surrounding cards update with real data.
  const _GARDEN_TIME_TO_RANGE = {
    "最近7天": "7d",
    "最近30天": "30d",
    "最近90天": "90d",
    "最近1年": "1y",
    "全部时间": "all",
  };
  const _GARDEN_TYPE_TO_TYPE = {
    "全部类型": "all",
    "笔记": "note",
    "链接": "link",
    "音频": "audio",
    "研究": "research",
    "洞察": "insight",
  };

  function attachGardenInlineMenuV17() {
    const filters = document.querySelector(".garden-main .garden-filters");
    if (!filters || filters.dataset.v17InlineFilter === "true") return;
    filters.dataset.v17InlineFilter = "true";

    V14.gardenRange = V14.gardenRange || "90d";
    V14.gardenType = V14.gardenType || "all";

    // Prefer mutation-observer over click handlers because the popover
    // dispatches its selection from outside the chip. We trigger refetch
    // when the chip's `[data-inline-label]` text changes.
    const observe = (chip, kind) => {
      const labelEl = chip.querySelector("[data-inline-label]");
      if (!labelEl) return;
      const obs = new MutationObserver(() => {
        const value = labelEl.textContent.trim();
        if (kind === "time") {
          const next = _GARDEN_TIME_TO_RANGE[value] || "all";
          if (next !== V14.gardenRange) {
            V14.gardenRange = next;
            refreshGardenBoard().catch(() => {});
            toast("已切换时间范围: " + value, "success");
          }
        } else if (kind === "type") {
          const next = _GARDEN_TYPE_TO_TYPE[value] || "all";
          if (next !== V14.gardenType) {
            V14.gardenType = next;
            refreshGardenBoard().catch(() => {});
            toast("已切换节点类型: " + value, "success");
          }
        }
      });
      obs.observe(labelEl, { childList: true, characterData: true, subtree: true });
    };

    const timeBtn = filters.querySelector('[data-inline-menu="gardenTime"]');
    const typeBtn = filters.querySelector('[data-inline-menu="gardenType"]');
    if (timeBtn) observe(timeBtn, "time");
    if (typeBtn) observe(typeBtn, "type");
  }

  // ─── notifications ───────────────────────────────────────────────────────
  function notifQueryParams() {
    const f = V14.notifFilter;
    const q = new URLSearchParams();
    q.set("page_size", "40");
    if (f === "unread") q.set("is_read", "false");
    return q.toString();
  }

  function clientFilterNotifications(items, f) {
    if (f === "all") return items;
    if (f === "unread") return items.filter((x) => !x.is_read);
    const t = (x) => String(x.type || "");
    if (f === "ai") {
      return items.filter((x) =>
        /ai|job_|skill|report|insight/i.test(t(x)) ||
        ["ai_output_saved", "job_completed", "job_failed"].includes(x.type),
      );
    }
    if (f === "system") {
      return items.filter((x) =>
        ["system", "upload_failed", "job_failed", "daily_insight", "kb_update"].includes(
          x.type,
        ) || /system|upload|sync/i.test(t(x)),
      );
    }
    if (f === "collab") {
      return items.filter((x) =>
        /collab|shared|garden|协作/i.test(t(x) + (x.title || "")),
      );
    }
    return items;
  }

  async function loadNotifications() {
    let resp;
    try {
      resp = await apiFetch("/notifications?" + notifQueryParams());
    } catch (e) {
      console.warn("[Mydow v1.4] /notifications failed", e);
      return null;
    }
    const data = unwrapData(resp) || resp || {};
    const rawItems = data.items || [];
    ingestNotificationsForSkillRunChipsV16(rawItems).catch((e) =>
      console.warn("[Mydow v1.4] skill-run chips from notifications", e),
    );
    let items = rawItems;
    items = clientFilterNotifications(items, V14.notifFilter);
    items = items.slice(0, 12);

    const rows = document.querySelectorAll(".notice-row[data-notice-type], .notifications-open .notice-row");
    rows.forEach((row, idx) => {
      const notif = items[idx];
      if (!notif) {
        row.style.display = "none";
        return;
      }
      row.style.display = "";
      row.dataset.notificationId = notif.id || "";
      row.dataset.bridgeBound = "true";
      const titleEl = row.querySelector("strong, h2, h4");
      if (titleEl && notif.title) titleEl.textContent = notif.title;
      const bodyEl = row.querySelector(".notice-body, p");
      const contentText = notif.body || notif.content;
      if (bodyEl && contentText) bodyEl.textContent = contentText;
      const isUnread = !notif.is_read;
      row.classList.toggle("is-unread", isUnread);
    });

    window.dispatchEvent(
      new CustomEvent("mydow:v14:notifications-loaded", { detail: { items } }),
    );
    return data;
  }

  async function refreshNotificationBadge() {
    let resp;
    try {
      resp = await apiFetch("/notifications/unread-count");
    } catch {
      return null;
    }
    const data = unwrapData(resp) || resp || {};
    const count = Number(data.count != null ? data.count : data.unread_count || 0);
    document.querySelectorAll("[data-open-notifications] .badge, [data-notification-count]").forEach((b) => {
      b.textContent = String(count);
      b.dataset.bridgeBound = "true";
    });
    return count;
  }

  function bindNoticeFilterCapture() {
    document.addEventListener(
      "click",
      (event) => {
        const pill = event.target.closest("[data-notice-filter]");
        if (!pill) return;
        V14.notifFilter = pill.dataset.noticeFilter || "all";
      },
      true,
    );

    document.addEventListener(
      "click",
      (event) => {
        const pill = event.target.closest("[data-notice-filter]");
        if (!pill) return;
        window.setTimeout(() => {
          loadNotifications().catch(() => {});
        }, 0);
      },
      false,
    );
  }

  function bindNoticeQuickCapture() {
    document.addEventListener(
      "click",
      (event) => {
        const el = event.target.closest("[data-notice-quick=\"markRead\"]");
        if (!el) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        apiFetch("/notifications/read-all", { method: "POST", body: {} })
          .then(() => {
            toast("已全部标记为已读", "success");
            return loadNotifications();
          })
          .then(() => refreshNotificationBadge())
          .catch((e) => toast("操作失败: " + e.message, "error"));
      },
      true,
    );
  }

  function bindNoticeRowMarkRead() {
    document.addEventListener(
      "click",
      (event) => {
        const row = event.target.closest(".notice-row");
        if (!row || !row.dataset.notificationId) return;
        if (event.target.closest("[data-notice-action]")) return;
        const id = row.dataset.notificationId;
        rawFetch(`/notifications/${id}/read`, { method: "POST", body: "{}" })
          .then(() => {
            row.classList.remove("is-unread");
            refreshNotificationBadge().catch(() => {});
          })
          .catch(() => {});
      },
      false,
    );
  }

  // ─── AI SSE (composer `.ai-chat-composer` / GPT layout) ───────────────────
  function aiMessageListHost() {
    return document.querySelector(".ai-message-list");
  }

  function ensureAiConversationVisibleV18(title) {
    const page =
      document.querySelector(".page.ai-open") ||
      document.querySelector(".page:has(.ai-conversation-view)") ||
      document.querySelector(".page");
    if (page) {
      page.classList.add("ai-open", "ai-chat-open");
      page.classList.remove("profile-open", "notifications-open", "skills-open", "garden-open", "knowledge-open", "folder-open", "doc-open");
    }
    const view = document.querySelector(".ai-conversation-view");
    if (view) {
      view.hidden = false;
      view.removeAttribute("hidden");
    }
    const label = String(title || "当前对话").trim();
    document.querySelectorAll('[data-inline-menu="aiConversation"] [data-inline-label]').forEach((node) => {
      node.textContent = label;
    });
    document.querySelectorAll("[data-ai-chat-open]").forEach((thread) => {
      if (thread.dataset.conversationId && V14.aiConvId) {
        thread.classList.toggle("active", thread.dataset.conversationId === V14.aiConvId);
      }
    });
    document.querySelectorAll(".ai-chat-message").forEach((msg) => {
      msg.style.opacity = "1";
      msg.style.transform = "none";
    });
  }

  function appendAiUserBubble(text) {
    const list = aiMessageListHost();
    if (!list) return;
    ensureAiConversationVisibleV18();
    const el = document.createElement("article");
    el.className = "ai-chat-message user-message";
    el.innerHTML = '<div class="message-bubble"></div>';
    el.querySelector(".message-bubble").textContent = text;
    list.appendChild(el);
    list.scrollTop = list.scrollHeight;
  }

  function appendAiAssistantPlaceholder() {
    const list = aiMessageListHost();
    if (!list) return null;
    ensureAiConversationVisibleV18();
    const el = document.createElement("article");
    el.className = "ai-chat-message assistant-message is-thinking";
    el.innerHTML = `
      <div class="assistant-avatar" aria-hidden="true"><span class="brand-mark"></span></div>
      <div class="assistant-content">
        <span class="ai-thinking-indicator" aria-live="polite">
          <span class="thinking-dot"></span><span class="thinking-dot"></span><span class="thinking-dot"></span>
          <span>正在生成…</span>
        </span>
        <p data-v14-ai-stream></p>
        <div class="ai-message-actions" aria-label="回答操作" style="display:none;margin-top:10px;gap:6px;">
          <button type="button" data-toast="已复制回答" aria-label="复制回答">复制</button>
          <button type="button" data-toast="已重新生成回答" aria-label="重新生成">重新生成</button>
          <button type="button" data-toast="感谢反馈" aria-label="点赞">👍</button>
          <button type="button" data-toast="已记录反馈" aria-label="点踩">👎</button>
        </div>
      </div>`;
    list.appendChild(el);
    el.style.opacity = "1";
    list.scrollTop = list.scrollHeight;
    return el.querySelector("[data-v14-ai-stream]");
  }

  function _showAssistantActions(article, messageId) {
    if (!article) return;
    if (messageId) article.dataset.messageId = String(messageId);
    const actions = article.querySelector(".ai-message-actions");
    if (actions) {
      actions.style.display = "flex";
      actions.querySelectorAll("button").forEach((b) => {
        b.style.cssText =
          "padding:5px 10px;border-radius:8px;border:1px solid rgba(108,124,153,0.18);" +
          "background:rgba(255,255,255,0.6);color:#5a6b86;font-size:12px;cursor:pointer;";
      });
    }
  }

  /**
   * §16.8 — Open KB / feed target for a citation object (shared by chips +
   * inline ``[#n]`` markers).
   */
  function _openCitationTargetV16(c) {
    if (!c) {
      toast("未找到对应引用", "warning");
      return;
    }
    const oid = String(c.object_id || "").trim();
    const otype = String(c.object_type || "document").toLowerCase();
    if (!oid) {
      toast("该引用暂无链接", "warning");
      return;
    }
    if (otype === "card") {
      window.location.hash = "#/home";
      window.setTimeout(() => {
        const target = document.querySelector(`.idea-card[data-card-id="${oid}"]`);
        if (target) target.click();
        else toast(`引用：${c.title || "灵感卡片"}`, "info");
      }, 180);
      return;
    }
    toast(`引用：${c.title || "知识库文档"}`);
    window.location.hash = `#kb/doc/${oid}`;
    if (window.MydowBridgeV14Ext && typeof window.MydowBridgeV14Ext.openDocDrawer === "function") {
      window.MydowBridgeV14Ext.openDocDrawer(oid);
    }
  }

  function _decorateAiStreamInlineCitations(streamEl, citations) {
    if (!streamEl || !Array.isArray(citations) || citations.length === 0) return;
    if (streamEl.dataset.inlineCitationsDecorated === "true") return;
    const raw = streamEl.textContent || "";
    if (!/\[#\d+\]/.test(raw)) return;
    const re = /\[#(\d+)\]/g;
    const frag = document.createDocumentFragment();
    let last = 0;
    let m;
    while ((m = re.exec(raw)) !== null) {
      if (m.index > last) {
        frag.appendChild(document.createTextNode(raw.slice(last, m.index)));
      }
      const num = parseInt(m[1], 10);
      const cite = num >= 1 && num <= citations.length ? citations[num - 1] : null;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ai-citation-inline";
      btn.textContent = m[0];
      btn.setAttribute("aria-label", cite ? `打开引用 ${num}：${cite.title || ""}` : `引用 ${num}`);
      btn.style.cssText =
        "display:inline-flex;align-items:center;vertical-align:baseline;" +
        "margin:0 2px;padding:0 6px;border-radius:999px;border:1px solid rgba(91,120,255,0.35);" +
        "background:rgba(91,120,255,0.1);color:#3548a6;font-size:inherit;" +
        "font-weight:600;line-height:1.4;cursor:pointer;font-family:inherit;";
      btn.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        _openCitationTargetV16(cite);
      });
      frag.appendChild(btn);
      last = re.lastIndex;
    }
    if (last < raw.length) frag.appendChild(document.createTextNode(raw.slice(last)));
    streamEl.textContent = "";
    streamEl.appendChild(frag);
    streamEl.dataset.inlineCitationsDecorated = "true";
  }

  // §15.43 — render citation chips directly from SSE payload (preferred path).
  function _renderCitationChipsFromPayload(article, citations) {
    if (!article || !Array.isArray(citations) || !citations.length) return;
    if (article.dataset.citationsRendered === "true") return;
    article.dataset.citationsRendered = "true";
    const content = article.querySelector(".assistant-content") || article;
    let host = article.querySelector(".ai-message-citations");
    if (host) host.remove();
    host = document.createElement("div");
    host.className = "ai-message-citations";
    host.setAttribute("aria-label", "知识库引用");
    host.style.cssText =
      "display:flex;flex-wrap:wrap;gap:8px;margin-top:14px;" +
      "padding:12px;background:rgba(108,124,153,0.06);" +
      "border-radius:14px;border:1px solid rgba(108,124,153,0.12);";
    const heading = document.createElement("div");
    heading.style.cssText =
      "flex-basis:100%;font-size:11px;letter-spacing:0.05em;" +
      "color:#7488a6;text-transform:uppercase;font-weight:600;margin-bottom:2px;";
    heading.textContent = `引用 · 共 ${citations.length} 条来自你的知识库`;
    host.appendChild(heading);
    citations.slice(0, 6).forEach((c, idx) => {
      const chip = document.createElement("a");
      chip.className = "ai-citation-chip";
      chip.dataset.citationIdx = String(idx + 1);
      chip.dataset.objectId = c.object_id || "";
      chip.dataset.folderId = c.folder_id || "";
      chip.href = c.anchor_url || `/mydow/biz_v14/#kb/doc/${c.object_id}`;
      const folderLabel = c.folder_name || c.folder_id || "知识库";
      const score =
        typeof c.score === "number" && c.score > 0
          ? ` · ${(c.score * 100).toFixed(0)}%`
          : "";
      chip.style.cssText =
        "display:inline-flex;align-items:center;gap:6px;padding:6px 12px;" +
        "background:#fff;border:1px solid rgba(108,124,153,0.2);border-radius:999px;" +
        "color:#1f2940;font-size:12px;text-decoration:none;font-weight:500;" +
        "transition:transform 120ms ease, box-shadow 120ms ease;cursor:pointer;";
      const titleText = escapeHtmlV14(c.title || "未命名");
      chip.innerHTML =
        `<span style="font-weight:700;color:#5b78ff;">[#${idx + 1}]</span>` +
        `<span style="max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">` +
        `${titleText}` +
        `</span>` +
        `<span style="color:#7488a6;font-weight:500;">${escapeHtmlV14(folderLabel)}${score}</span>`;
      const cleanSnippet = String(c.snippet || "")
        .replace(/<mark>|<\/mark>/g, "")
        .slice(0, 220);
      if (cleanSnippet) chip.title = cleanSnippet;
      chip.addEventListener("click", (ev) => {
        ev.preventDefault();
        _openCitationTargetV16(c);
      });
      host.appendChild(chip);
    });
    content.appendChild(host);
  }

  async function streamV14AiReply(conversationId, content) {
    if (V14.streamAbort) {
      try {
        V14.streamAbort.abort();
      } catch (_e) { /* ignore */ }
    }
    V14.streamAbort = new AbortController();
    const streamEl = appendAiAssistantPlaceholder();
    const streamPath = `/ai/conversations/${conversationId}/messages/stream`;
    /** §15.37.f — propagate selected AI model + mode to backend.
     * Read label live from the IIFE-controlled DOM so we always pick up the
     * latest user choice (the IIFE manages aiModel state via uiMemory). */
    const labelEl = document.querySelector(
      '[data-inline-menu="aiModel"] [data-inline-label]',
    );
    const liveModel = (labelEl && labelEl.textContent.trim()) || V14.aiModel;
    if (liveModel && liveModel !== V14.aiModel) {
      V14.aiModel = liveModel;
      try {
        window.localStorage.setItem("mydow_v14_ai_model", liveModel);
      } catch (_e) { /* ignore quota */ }
    }
    const body = { content, attachments: [] };
    if (liveModel && liveModel !== "Mydow Auto") {
      body.model = liveModel;
    }
    const modeBtn = document.querySelector(".ai-mode-button.active[data-ai-mode]");
    if (modeBtn) body.mode = modeBtn.dataset.aiMode || "efficient";
    /** §16.4 — 显式传 context_scope（与 PATCH 会话一致）；避免会话对象未刷新时 RAG 漏上下文。 */
    const docPins = (V14.contextScope.document_ids || []).map(String).filter(Boolean);
    const folderPins = (V14.contextScope.folder_ids || []).map(String).filter(Boolean);
    if (docPins.length || folderPins.length) {
      body.context_scope = {
        document_ids: docPins,
        folder_ids: folderPins,
        sources: Array.isArray(V14.contextScope.sources)
          ? V14.contextScope.sources.slice()
          : ["doc"],
      };
    }
    const resp = await fetchAiStreamWithSession(streamPath, body, V14.streamAbort.signal);
    if (!resp.ok || !resp.body) {
      if (streamEl) streamEl.textContent = "（生成失败 " + resp.status + "）";
      toast(resp.status === 401 ? "登录已刷新，请再试一次" : "AI 请求失败", "error");
      return;
    }
    const parent = streamEl && streamEl.closest(".ai-chat-message");
    if (parent) {
      parent.classList.remove("is-thinking");
      const indicator = parent.querySelector(".ai-thinking-indicator");
      if (indicator) indicator.remove();
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let first = true;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() || "";
      for (const block of blocks) {
        const lines = block.split(/\r?\n/);
        const eventLine = lines.find((l) => l.startsWith("event:"));
        const dataLine = lines.find((l) => l.startsWith("data:"));
        if (!eventLine || !dataLine) continue;
        const eventType = eventLine.slice(eventLine.indexOf(":") + 1).trim();
        const raw = dataLine.slice(dataLine.indexOf(":") + 1).trim();
        let payload = null;
        try {
          payload = JSON.parse(raw);
        } catch {
          payload = { _raw: raw };
        }
        if (eventType === "meta" && payload && payload.assistant_message_id) {
          V14.lastAssistantMessageId = String(payload.assistant_message_id);
          if (streamEl) {
            const article = streamEl.closest(".ai-chat-message");
            if (article) {
              article.dataset.messageId = V14.lastAssistantMessageId;
              if (payload.agent_enabled) article.dataset.agentMode = "true";
            }
          }
        } else if (eventType === "agent_step" && payload && streamEl) {
          // §15.49 — render visible plan/retrieve/synthesize chips above the bubble.
          const article = streamEl.closest(".ai-chat-message");
          _appendAgentStep(article, payload);
        } else if (eventType === "token" && payload && payload.delta && streamEl) {
          if (first) {
            streamEl.textContent = "";
            first = false;
          }
          streamEl.textContent += payload.delta;
          const list = aiMessageListHost();
          if (list) list.scrollTop = list.scrollHeight;
        } else if (eventType === "error" && streamEl) {
          streamEl.textContent = (payload && payload.message) || "错误";
        } else if (eventType === "done" && streamEl) {
          if (first) streamEl.textContent = "模型没有返回内容，请检查 LLM 配置或稍后重试。";
          const article = streamEl.closest(".ai-chat-message");
          _showAssistantActions(article, V14.lastAssistantMessageId);
          if (payload && Array.isArray(payload.citations) && article) {
            _renderCitationChipsFromPayload(article, payload.citations);
            _decorateAiStreamInlineCitations(streamEl, payload.citations);
          }
        }
      }
    }
    /** Final safety: even if upstream never sent `event: done`, surface
     *  the action toolbar so the user can copy/regenerate/feedback. */
    if (streamEl) {
      const article = streamEl.closest(".ai-chat-message");
      _showAssistantActions(article, V14.lastAssistantMessageId);
      // §15.43 — pull citations from the persisted assistant message and
      // render real KB chips below the bubble. Hidden on errors / no hits.
      _renderCitationsForArticle(article, conversationId, V14.lastAssistantMessageId).catch(
        (err) => console.warn("[Mydow v1.4] citation render failed", err),
      );
    }
    V14.streamAbort = null;
  }

  /** §15.49 — Append a visible agent-step badge above the assistant bubble
   * so the user sees the ReAct plan / retrieve / synthesize timeline as it
   * unfolds. Each step lands as a soft pill with a colored dot. Idempotent
   * by ``data-step`` so duplicate events don't double-render.
   */
  function _appendAgentStep(article, step) {
    if (!article || !step) return;
    let host = article.querySelector(".ai-agent-steps");
    if (!host) {
      host = document.createElement("div");
      host.className = "ai-agent-steps";
      host.setAttribute("aria-label", "AI 思考过程");
      host.style.cssText =
        "display:flex;flex-direction:column;gap:6px;margin:8px 0 12px;" +
        "padding:10px 12px;background:rgba(255,255,255,0.55);" +
        "border-radius:14px;border:1px dashed rgba(108,124,153,0.18);" +
        "font-size:12px;color:#4a5b78;";
      const head = document.createElement("div");
      head.style.cssText =
        "font-weight:600;color:#5b78ff;letter-spacing:0.04em;font-size:11px;text-transform:uppercase;";
      head.textContent = "Mydow Agent";
      host.appendChild(head);
      const content = article.querySelector(".assistant-content") || article;
      // Place agent steps BEFORE the streaming text, not after.
      const streamP = content.querySelector("[data-v14-ai-stream]");
      if (streamP) content.insertBefore(host, streamP);
      else content.appendChild(host);
    }
    const stepKey = `step-${step.step ?? "?"}-${step.kind ?? ""}`;
    if (host.querySelector(`[data-step="${stepKey}"]`)) return;
    const row = document.createElement("div");
    row.dataset.step = stepKey;
    row.style.cssText = "display:flex;align-items:flex-start;gap:8px;";
    const colorMap = {
      plan: "#ffb547",
      retrieve: "#5b78ff",
      synthesize: "#7fcabd",
      tool: "#c779e8",
    };
    const dot = document.createElement("span");
    dot.style.cssText =
      "flex:none;width:8px;height:8px;border-radius:50%;margin-top:5px;background:" +
      (colorMap[step.kind] || "#7488a6") + ";";
    const body = document.createElement("div");
    const titleEl = document.createElement("strong");
    titleEl.style.cssText = "display:block;color:#1f2940;font-weight:600;";
    titleEl.textContent = `${step.step ?? "?"}. ${step.title || step.kind || "step"}`;
    body.appendChild(titleEl);
    if (step.detail) {
      const detailEl = document.createElement("span");
      detailEl.style.cssText = "color:#5a6b86;";
      detailEl.textContent = step.detail;
      body.appendChild(detailEl);
    }
    if (Array.isArray(step.top_titles) && step.top_titles.length) {
      const ul = document.createElement("div");
      ul.style.cssText = "display:flex;flex-wrap:wrap;gap:4px;margin-top:4px;";
      step.top_titles.slice(0, 3).forEach((t) => {
        const tag = document.createElement("span");
        tag.style.cssText =
          "padding:1px 8px;background:rgba(91,120,255,0.08);" +
          "border-radius:8px;font-size:11px;color:#4a5b78;";
        tag.textContent = t;
        ul.appendChild(tag);
      });
      body.appendChild(ul);
    }
    row.appendChild(dot);
    row.appendChild(body);
    host.appendChild(row);
  }

  /** §15.43 — Fetch persisted assistant message citations and render
   * inline knowledge-base reference chips below the GPT-style bubble.
   * Failure is silent so the UI never blocks the stream success path. */
  async function _renderCitationsForArticle(article, conversationId, messageId) {
    if (!article || !conversationId || !messageId) return;
    if (article.dataset.citationsRendered === "true") return;
    let detail;
    try {
      const resp = await apiFetch(`/ai/conversations/${conversationId}`);
      detail = unwrapData(resp) || {};
    } catch (_e) {
      return;
    }
    const messages = (detail && detail.messages) || [];
    const msg = messages.find((m) => m && m.id === String(messageId));
    if (!msg) return;
    const citations = Array.isArray(msg.citations) ? msg.citations : [];
    if (!citations.length) return;

    let host = article.querySelector(".ai-message-citations");
    if (!host) {
      host = document.createElement("div");
      host.className = "ai-message-citations";
      host.setAttribute("aria-label", "知识库引用");
      host.style.cssText =
        "display:flex;flex-wrap:wrap;gap:8px;margin-top:14px;" +
        "padding:12px;background:rgba(108,124,153,0.06);" +
        "border-radius:14px;border:1px solid rgba(108,124,153,0.12);";
      const heading = document.createElement("div");
      heading.style.cssText =
        "flex-basis:100%;font-size:11px;letter-spacing:0.05em;" +
        "color:#7488a6;text-transform:uppercase;font-weight:600;margin-bottom:2px;";
      heading.textContent = `引用 · 共 ${citations.length} 条来自你的知识库`;
      host.appendChild(heading);
      const content = article.querySelector(".assistant-content") || article;
      content.appendChild(host);
    }
    citations.slice(0, 6).forEach((c, idx) => {
      const chip = document.createElement("a");
      chip.className = "ai-citation-chip";
      chip.dataset.citationIdx = String(idx + 1);
      chip.dataset.objectId = c.object_id || "";
      chip.dataset.folderId = c.folder_id || "";
      const url = c.anchor_url || `/mydow/biz_v14/#kb/doc/${c.object_id}`;
      chip.href = url;
      const folderLabel = c.folder_name || c.folder_id || "知识库";
      const score =
        typeof c.score === "number" && c.score > 0
          ? ` · ${(c.score * 100).toFixed(0)}%`
          : "";
      chip.style.cssText =
        "display:inline-flex;align-items:center;gap:6px;padding:6px 12px;" +
        "background:#fff;border:1px solid rgba(108,124,153,0.2);border-radius:999px;" +
        "color:#1f2940;font-size:12px;text-decoration:none;font-weight:500;" +
        "transition:transform 120ms ease, box-shadow 120ms ease;cursor:pointer;";
      chip.innerHTML =
        `<span style="font-weight:700;color:#5b78ff;">[#${idx + 1}]</span>` +
        `<span style="max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">` +
        `${escapeHtmlV14(c.title || "未命名")}` +
        `</span>` +
        `<span style="color:#7488a6;font-weight:500;">${escapeHtmlV14(folderLabel)}${score}</span>`;
      chip.addEventListener(
        "mouseenter",
        () => {
          chip.style.transform = "translateY(-1px)";
          chip.style.boxShadow = "0 6px 18px rgba(91,120,255,0.18)";
        },
      );
      chip.addEventListener("mouseleave", () => {
        chip.style.transform = "";
        chip.style.boxShadow = "";
      });
      // Intercept default navigation so we can route to the document drawer
      // inside the SPA-like prototype. Falls through to ``window.location``
      // when the document id is invalid (defensive).
      chip.addEventListener("click", (ev) => {
        ev.preventDefault();
        _openCitationTargetV16(c);
      });
      host.appendChild(chip);
    });
    const streamP = article.querySelector("[data-v14-ai-stream]");
    _decorateAiStreamInlineCitations(streamP, citations);
    article.dataset.citationsRendered = "true";
  }

  async function ensureAiConversationId() {
    if (V14.aiConvId) return V14.aiConvId;
    const threads = [...document.querySelectorAll("[data-ai-chat-open][data-conversation-id]")];
    const active = threads.find((t) => t.classList.contains("active"));
    const cid = (active || threads[0])?.dataset.conversationId;
    if (cid) {
      V14.aiConvId = cid;
      loadActiveConversationContextScope().catch(() => {});
      return cid;
    }
    const conv = await apiFetch("/ai/conversations", {
      method: "POST",
      body: { title: "新对话", mode: "general" },
    });
    const cdata = unwrapData(conv) || {};
    const id = cdata.id;
    if (!id) throw new Error("无法创建会话");
    V14.aiConvId = id;
    const th = threads[0] || document.querySelector("[data-ai-chat-open]");
    if (th) {
      th.dataset.conversationId = id;
      th.classList.add("active");
    }
    loadActiveConversationContextScope().catch(() => {});
    return id;
  }

  async function hydrateAiConversationFromThread(thread) {
    const cid = thread.dataset.conversationId;
    if (!cid) return;
    V14.aiConvId = cid;
    ensureAiConversationVisibleV18(thread.dataset.title || thread.querySelector("strong")?.textContent || "当前对话");
    loadActiveConversationContextScope().catch(() => {});
    const list = aiMessageListHost();
    if (!list) return;
    try {
      const r = await apiFetch(`/ai/conversations/${cid}`);
      const d = unwrapData(r) || {};
      const messages = d.messages || [];
      list.innerHTML = "";
      messages.forEach((m) => {
        const role = m.role || "user";
        const content = m.content || "";
        if (role === "user") appendAiUserBubble(content);
        else {
          const ph = appendAiAssistantPlaceholder();
          if (ph) {
            const wrap = ph.closest(".ai-chat-message");
            if (wrap) wrap.classList.remove("is-thinking");
            const indicator = wrap?.querySelector(".ai-thinking-indicator");
            if (indicator) indicator.remove();
            ph.textContent = content;
            const cites = Array.isArray(m.citations) ? m.citations : [];
            if (cites.length)
              window.setTimeout(() => _decorateAiStreamInlineCitations(ph, cites), 0);
          }
        }
      });
    } catch (e) {
      console.warn("[v14] hydrate conv", e);
    }
  }

  function bindAiThreadHydrate() {
    document.addEventListener(
      "click",
      (event) => {
        const th = event.target.closest("[data-ai-chat-open]");
        if (!th) return;
        window.setTimeout(() => hydrateAiConversationFromThread(th), 120);
      },
      false,
    );
  }

  function bindAiComposerCapture() {
    document.addEventListener(
      "click",
      async (event) => {
        const send = event.target.closest(".ai-chat-composer .send-button, .ai-composer .send-button");
        if (!send || send.closest(".capture")) return;
        const composer = send.closest(".ai-composer, .ai-chat-composer");
        const input = composer && composer.querySelector("[data-ai-input], .ai-input");
        const text = (input && (input.value || input.textContent || "").trim()) || "";
        if (!text) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        send.disabled = true;
        send.classList.add("is-loading");
        try {
          await ensureSession();
          const cid = await ensureAiConversationId();
          appendAiUserBubble(text);
          if (input) {
            input.value = "";
            if (input.contentEditable === "true") input.textContent = "";
            input.dispatchEvent(new Event("input", { bubbles: true }));
          }
          await streamV14AiReply(cid, text);
          await loadAiConversations();
        } catch (e) {
          toast("发送失败: " + e.message, "error");
        } finally {
          send.disabled = false;
          send.classList.remove("is-loading");
        }
      },
      true,
    );
  }

  // ─── AI history list ─────────────────────────────────────────────────────
  async function loadAiConversations() {
    let resp;
    try {
      resp = await apiFetch("/ai/conversations?page_size=20");
    } catch (e) {
      console.warn("[Mydow v1.4] /ai/conversations failed", e);
      return null;
    }
    const data = unwrapData(resp) || resp || {};
    const items = data.items || [];
    const threads = document.querySelectorAll(".ai-history-thread[data-ai-chat-open]");
    if (!threads.length) return data;
    threads.forEach((thread, idx) => {
      const conv = items[idx];
      if (!conv) {
        thread.style.display = "none";
        return;
      }
      thread.style.display = "";
      thread.dataset.conversationId = conv.id || "";
      thread.dataset.title = conv.title || thread.dataset.title || "";
      thread.dataset.bridgeBound = "true";
      const titleEl = thread.querySelector("strong");
      if (titleEl) titleEl.textContent = conv.title || "对话";
      const timeEl = thread.querySelector("small");
      if (timeEl) {
        timeEl.textContent = relTime(conv.updated_at || conv.created_at) ||
          (conv.last_message_preview || "").slice(0, 24);
      }
    });
    window.dispatchEvent(
      new CustomEvent("mydow:v14:ai-history-loaded", { detail: { items } }),
    );
    if (!V14.aiConvId && items.length && threads[0]) {
      const firstId = items[0].id;
      if (firstId) {
        V14.aiConvId = String(firstId);
        loadActiveConversationContextScope().catch(() => {});
      }
    }
    return data;
  }

  // ─── search debounce ─────────────────────────────────────────────────────
  // §17.6 — When the user picks a result row we route to the right detail
  // surface based on the result's ``object_type`` field instead of just
  // showing a "已选中" toast. card → home idea-card; document → KB doc
  // drawer; folder → KB folder detail; skill → skill drawer; insight →
  // insights center; ai_message → AI conversation.
  let _SEARCH_LAST_RESULTS = [];

  function bindGlobalSearch() {
    let t = null;
    document.addEventListener(
      "input",
      (event) => {
        const inp = event.target.closest("[data-search-modal-input]");
        if (!inp) return;
        clearTimeout(t);
        t = setTimeout(async () => {
          const q = (inp.value || "").trim();
          if (q.length < 1) return;
          try {
            const r = await apiFetch("/search?q=" + encodeURIComponent(q) + "&page_size=10");
            const d = unwrapData(r) || {};
            const results = d.items || d.results || [];
            _SEARCH_LAST_RESULTS = results;
            const host = document.querySelector(".search-modal .search-results, [data-search-results]");
            if (!host || !results.length) return;
            host.innerHTML = results.slice(0, 8).map((row, idx) => {
              const title = row.title || row.name || "结果";
              const sub = row.object_type || row.type || "";
              const summary = (row.summary || "").slice(0, 60);
              return (
                '<div class="search-result-row" role="button" tabindex="0" '
                + 'data-search-hit-idx="' + idx + '" '
                + 'style="padding:10px 12px; cursor:pointer; border-radius:8px;">'
                + '<strong>' + escapeHtmlV14(title) + '</strong>'
                + '<span style="margin-left:8px; color:#7b8aa6; font-size:12px;">' + escapeHtmlV14(sub) + '</span>'
                + (summary ? '<div style="margin-top:4px; color:#97a3b7; font-size:11px;">' + escapeHtmlV14(summary) + '</div>' : '')
                + '</div>'
              );
            }).join("");
          } catch (_e) { /* ignore */ }
        }, 240);
      },
      true,
    );

    // Real navigation on row click — capture-phase so we win over the IIFE.
    document.addEventListener(
      "click",
      (event) => {
        const row = event.target.closest("[data-search-hit-idx]");
        if (!row) return;
        const idx = Number(row.dataset.searchHitIdx);
        const hit = _SEARCH_LAST_RESULTS[idx];
        if (!hit) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        navigateToSearchHitV17(hit);
      },
      true,
    );
  }

  function navigateToSearchHitV17(hit) {
    const type = (hit.object_type || hit.type || "").toLowerCase();
    const id = hit.object_id || hit.target_id || hit.id;
    closeV14Layers();
    // Wait one tick so closeV14Layers DOM mutations land first
    window.setTimeout(() => {
      if (type === "card" || type === "capture" || type === "inspiration") {
        // navigate to home + open the matching idea-card drawer
        const navBtn = document.querySelector('[data-nav-target="home"]');
        if (navBtn) navBtn.click();
        window.setTimeout(() => {
          const card = document.querySelector('.idea-card[data-card-id="' + id + '"]');
          if (card) card.click();
          else toast("「" + (hit.title || "卡片") + "」已找到，列表中可查看", "info");
        }, 180);
      } else if (type === "document" || type === "kbdoc" || type === "kb_doc") {
        if (id) {
          openKbDocumentEditorV20(id).catch((e) => toast("打开文档失败: " + e.message, "error"));
        } else {
          const navBtn = document.querySelector('[data-nav-target="knowledge"]');
          if (navBtn) navBtn.click();
          toast("已打开知识库 — 文档「" + (hit.title || "") + "」", "success");
        }
      } else if (type === "folder" || type === "kbfolder" || type === "kb_folder") {
        const navBtn = document.querySelector('[data-nav-target="knowledge"]');
        if (navBtn) navBtn.click();
        window.setTimeout(() => {
          const opener = document.querySelector(
            '.library-card[data-folder-id="' + id + '"]',
          );
          if (opener) opener.click();
          else toast("文件夹「" + (hit.title || "") + "」已就绪", "info");
        }, 180);
      } else if (type === "skill") {
        const navBtn = document.querySelector('[data-nav-target="skills"]');
        if (navBtn) navBtn.click();
        window.setTimeout(() => {
          V14.activeSkillId = id;
          const card = document.querySelector(
            '.skill-card[data-skill-id="' + id + '"]',
          );
          if (card) card.click();
          else toast("Skill「" + (hit.title || "") + "」已就绪", "info");
        }, 180);
      } else if (type === "insight" || type === "ai_insight") {
        const opener = document.querySelector('[data-insights-full]');
        if (opener) opener.click();
        toast("洞察「" + (hit.title || "") + "」已聚焦", "info");
      } else if (type === "ai_message" || type === "ai_chat" || type === "conversation") {
        const navBtn = document.querySelector('[data-nav-target="ai"]');
        if (navBtn) navBtn.click();
        toast("已切换到 Mydow AI 工作台", "success");
      } else {
        toast("已打开「" + (hit.title || "结果") + "」", "info");
      }
    }, 80);
  }
  // Expose to other modules (e.g. garden node detail drawer)
  window.handleGlobalSearchHit = navigateToSearchHitV17;

  function attachInsightsFullHandlersV14() {
    document.addEventListener(
      "click",
      (event) => {
        const main = document.querySelector(".insights-full-main");
        if (main && main.contains(event.target)) {
          const dismiss = event.target.closest(".bridge-dismiss-btn");
          if (dismiss) {
            const card = dismiss.closest("[data-insight-id]");
            const iid = card && card.dataset.insightId;
            if (iid) {
              event.preventDefault();
              event.stopImmediatePropagation();
              apiFetch("/insights/" + iid + "/dismiss", { method: "POST" })
                .then(() => {
                  card.remove();
                  toast("已忽略", "success");
                })
                .catch((e) => toast("操作失败: " + e.message, "error"));
              return;
            }
          }
        }
        const open = event.target.closest("[data-insights-full]");
        if (open) {
          window.setTimeout(() => {
            refreshInsightsFullV14().catch(() => {});
          }, 220);
          return;
        }
        const reportRow = event.target.closest(
          ".insights-full-main .report-row[data-report-id]",
        );
        if (!reportRow) return;
        const rid = reportRow.dataset.reportId;
        if (!rid) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        apiFetch("/reports/" + rid)
          .then((r) => {
            const d = unwrapData(r) || {};
            const preview = String(d.body || d.summary || d.content || "").slice(0, 180);
            toast((d.title || "报告预览") + (preview ? " — " + preview : ""), "info");
          })
          .catch((e) => toast("读取报告失败: " + e.message, "error"));
      },
      true,
    );
  }

  function listenForFeedRefreshV14() {
    window.addEventListener("mydow:v14:capture-completed", () => {
      loadFeedCards().catch(() => {});
      loadFeedIntoRecordsTable().catch(() => {});
      refreshInsightsFullV14().catch(() => {});
    });
  }

  // ─── §15.38 — High-frequency assistant message action buttons ────────────
  // Business-owner contract maps these to:
  //   data-toast="已复制回答"    → navigator.clipboard.writeText(content)
  //   data-toast="已重新生成回答" → POST /ai/messages/{id}/regenerate (PRD10 §3.14)
  //   data-toast="感谢反馈"      → POST /ai/messages/{id}/feedback   {rating: up}
  //   data-toast="已记录反馈"    → POST /ai/messages/{id}/feedback   {rating: down}
  // The 4 buttons live as adjacent siblings inside .ai-msg-actions /
  // .assistant-message-actions; we resolve the owning message via the
  // closest assistant bubble id or fall back to V14.lastAssistantMessageId.
  function _resolveAssistantContext(buttonEl) {
    const bubble =
      buttonEl.closest(".assistant-message[data-message-id]") ||
      buttonEl.closest("[data-message-id]") ||
      buttonEl.closest(".ai-chat-message.assistant-message");
    let msgId = null;
    let textNode = null;
    if (bubble) {
      msgId = bubble.dataset && bubble.dataset.messageId;
      textNode =
        bubble.querySelector("[data-v14-ai-stream]") ||
        bubble.querySelector(".message-bubble") ||
        bubble.querySelector(".assistant-content p") ||
        bubble.querySelector(".assistant-content");
    }
    if (!msgId) msgId = V14.lastAssistantMessageId || "";
    const text = (textNode && textNode.textContent || "").trim();
    return { messageId: msgId, content: text, bubble: bubble };
  }

  async function _copyTextToClipboard(text) {
    if (!text) return false;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (_e) { /* fall through */ }
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch (_e) {
      return false;
    }
  }

  function bindAssistantActionButtonsV14() {
    document.addEventListener(
      "click",
      async (event) => {
        const profileAutoToggle = event.target.closest(".profile-main .toggle-switch");
        if (profileAutoToggle) {
          const row = profileAutoToggle.closest(".preference-row");
          const text = (row && row.innerText || "").replace(/\s+/g, "");
          if (/自动保存/.test(text)) {
            event.preventDefault();
            event.stopImmediatePropagation();
            const next = !profileAutoToggle.classList.contains("active");
            try {
              await _patchMePreference("auto_save", next);
              profileAutoToggle.classList.toggle("active", next);
              profileAutoToggle.setAttribute("aria-pressed", String(next));
              profileAutoToggle.setAttribute("aria-label", next ? "自动保存已开启" : "自动保存已关闭");
              toast(next ? "自动保存已开启" : "自动保存已关闭", "success");
            } catch (e) {
              toast("保存失败: " + e.message, "error");
            }
            return;
          }
        }
        const btn = event.target.closest("button[data-toast]");
        if (!btn) return;
        const toast_text = btn.dataset.toast || "";
        const intentMap = {
          "已复制回答": "copy",
          "已重新生成回答": "regenerate",
          "感谢反馈": "thumbs_up",
          "已记录反馈": "thumbs_down",
        };
        const intent = intentMap[toast_text];
        if (!intent) return;

        // Only intercept when the button lives in an assistant action
        // toolbar; never on capture composer / modal foot buttons.
        // v1.4 uses ``.ai-message-actions`` (singular); legacy markup used
        // ``.ai-msg-actions``. Match both plus the chat-message wrapper so
        // the §15.39 e2e button sweep counts these clicks as real.
        const inAssistantToolbar = btn.closest(
          ".ai-message-actions, .ai-msg-actions, .assistant-message-actions, .ai-chat-message.assistant-message"
        );
        if (!inAssistantToolbar) return;

        event.preventDefault();
        event.stopImmediatePropagation();

        const ctx = _resolveAssistantContext(btn);
        if (!ctx.messageId && intent !== "copy") {
          toast("找不到对应的 AI 回复", "warning");
          return;
        }

        if (intent === "copy") {
          const ok = await _copyTextToClipboard(ctx.content);
          toast(ok ? "已复制回答到剪贴板" : "复制失败，请手动复制", ok ? "success" : "warning");
          return;
        }

        btn.disabled = true;
        const oldLabel = btn.getAttribute("aria-label");

        try {
          if (intent === "regenerate") {
            await apiFetch(`/ai/messages/${ctx.messageId}/regenerate`, {
              method: "POST",
              body: {},
            });
            toast("已请求重新生成", "success");
            // Trigger a fresh stream by replaying the user's last prompt.
            if (V14.aiConvId) {
              hydrateAiConversationFromThread({
                dataset: { conversationId: V14.aiConvId },
              }).catch(() => {});
            }
            return;
          }
          if (intent === "thumbs_up" || intent === "thumbs_down") {
            const rating = intent === "thumbs_up" ? "up" : "down";
            await apiFetch(`/ai/messages/${ctx.messageId}/feedback`, {
              method: "POST",
              body: { rating },
            });
            const human = rating === "up" ? "感谢你的反馈" : "已记录反馈，我们会改进";
            toast(human, "success");
            return;
          }
        } catch (e) {
          toast("操作失败：" + (e && e.message ? e.message : "未知错误"), "error");
        } finally {
          btn.disabled = false;
          if (oldLabel) btn.setAttribute("aria-label", oldLabel);
        }
      },
      true,
    );
  }

  // ─── §15.39 — Custom Insight：实现见上方 ``submitCustomInsight`` + ``bindCustomInsightSubmit``（§16.12 garden insights）

  // ─── §15.38 — Logout via account menu (`data-account-action="logout"`) ─
  function bindLogoutAction() {
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest('[data-account-action="logout"]');
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        try {
          await apiFetch("/auth/logout", { method: "POST", body: {} }).catch(
            () => {},
          );
        } finally {
          setToken("");
          toast("已退出登录", "success");
          window.setTimeout(() => {
            window.location.reload();
          }, 600);
        }
      },
      true,
    );
  }

  // ═════════════════════════════════════════════════════════════════════════
  // §15.37 — Comprehensive v1.4 button wiring (rev2 — coexists with §15.38)
  //   Wires the remaining 20+ data-toast / data-* placeholder buttons to real
  //   PRD10 endpoints. Capture-phase + stopImmediatePropagation everywhere so
  //   the prototype IIFE simulateAction never wins.
  // ═════════════════════════════════════════════════════════════════════════
  function _activateNavTargetV37(target) {
    const nav = document.querySelector('[data-nav-target="' + target + '"]');
    if (!nav) return false;
    nav.click();
    return true;
  }

  // §15.37.a — Notice action button navigation (6 notice rows × Action button)
  function bindNoticeActionV37() {
    document.addEventListener(
      "click",
      (event) => {
        const btn = event.target.closest("[data-notice-action]");
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const action = btn.getAttribute("data-notice-action") || "";
        const row = btn.closest(".notice-row");
        const nid = row && row.dataset.notificationId;
        if (nid) {
          rawFetch(`/notifications/${nid}/read`, { method: "POST", body: "{}" })
            .then(() => {
              if (row) row.classList.remove("is-unread");
              refreshNotificationBadge().catch(() => {});
            })
            .catch(() => {});
        }
        const routeMap = {
          result: "ai",
          link: "garden",
          folder: "knowledge",
          report: "insightsFull",
          detail: "knowledge",
          settings: "profile",
        };
        const target = routeMap[action] || "knowledge";
        if (target === "insightsFull") {
          const insightsBtn = document.querySelector("[data-insights-full]");
          if (insightsBtn) insightsBtn.click();
        } else {
          _activateNavTargetV37(target);
        }
        toast("已为你跳转到对应页面", "success");
      },
      true,
    );
  }

  // §15.37.b — AI thread three-dot menu (rename / delete) ─────────────
  function _closePopoverV37() {
    document.querySelectorAll(".v37-bridge-popover").forEach((el) => el.remove());
  }

  function _openPopoverV37(anchor, items) {
    _closePopoverV37();
    const pop = document.createElement("div");
    pop.className = "v37-bridge-popover";
    pop.setAttribute("role", "menu");
    pop.style.cssText =
      "position:fixed;z-index:9999;background:#fff;border:1px solid rgba(108,124,153,0.15);" +
      "border-radius:12px;box-shadow:0 12px 40px rgba(28,41,80,0.18);padding:6px;" +
      "min-width:160px;font-size:13px;color:#29384f;";
    items.forEach((it) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = it.label;
      b.style.cssText =
        "display:block;width:100%;text-align:left;padding:9px 12px;border:0;background:transparent;" +
        "border-radius:8px;cursor:pointer;color:" +
        (it.danger ? "#d8484a" : "#29384f") + ";";
      b.addEventListener("mouseenter", () => {
        b.style.background = it.danger ? "rgba(216,72,74,0.08)" : "rgba(112,140,255,0.08)";
      });
      b.addEventListener("mouseleave", () => { b.style.background = "transparent"; });
      b.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopImmediatePropagation();
        _closePopoverV37();
        Promise.resolve(it.handler()).catch(
          (e) => toast("操作失败: " + (e && e.message), "error"),
        );
      });
      pop.appendChild(b);
    });
    document.body.appendChild(pop);
    const r = anchor.getBoundingClientRect();
    const popR = pop.getBoundingClientRect();
    let left = r.left;
    if (left + popR.width > window.innerWidth - 16) {
      left = window.innerWidth - popR.width - 16;
    }
    pop.style.left = Math.max(12, left) + "px";
    pop.style.top = r.bottom + 6 + "px";
    const closer = (ev) => {
      if (!pop.contains(ev.target)) {
        _closePopoverV37();
        document.removeEventListener("click", closer, true);
      }
    };
    setTimeout(() => document.addEventListener("click", closer, true), 0);
  }

  async function _renameAiConvV37(thread) {
    const cid = thread.dataset.conversationId;
    if (!cid) {
      toast("未找到对话 ID", "warning");
      return;
    }
    const current = thread.querySelector("strong")?.textContent.trim() || "对话";
    const next = window.prompt("重命名对话", current);
    if (!next || !next.trim()) return;
    const title = next.trim().slice(0, 80);
    try {
      await apiFetch("/ai/conversations/" + cid, {
        method: "PATCH",
        body: { title },
      });
      const strong = thread.querySelector("strong");
      if (strong) strong.textContent = title;
      thread.dataset.title = title;
      toast("对话已重命名", "success");
    } catch (e) {
      toast("重命名失败: " + e.message, "error");
    }
  }

  async function _deleteAiConvV37(thread) {
    const cid = thread.dataset.conversationId;
    if (!cid) return;
    const title = thread.querySelector("strong")?.textContent.trim() || "对话";
    if (!window.confirm("确定要删除「" + title + "」吗？该操作不可撤销。")) return;
    try {
      await apiFetch("/ai/conversations/" + cid, { method: "DELETE" });
      thread.style.display = "none";
      if (V14.aiConvId === cid) V14.aiConvId = null;
      toast("对话已删除", "success");
      await loadAiConversations();
    } catch (e) {
      toast("删除失败: " + e.message, "error");
    }
  }

  function bindAiThreadMenuV37() {
    document.addEventListener(
      "click",
      (event) => {
        const trigger = event.target.closest("[data-ai-thread-menu]");
        if (!trigger) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const thread = trigger.closest(".ai-history-thread");
        if (!thread) return;
        _openPopoverV37(trigger, [
          { label: "重命名", handler: () => _renameAiConvV37(thread) },
          { label: "删除", danger: true, handler: () => _deleteAiConvV37(thread) },
        ]);
      },
      true,
    );
  }

  function _activeAiThreadV37() {
    return (
      document.querySelector(".ai-history-thread.active") ||
      document.querySelector(".ai-history-thread[data-conversation-id]")
    );
  }

  async function saveAiConversationToKbV20(conversationId) {
    const cid = String(conversationId || V14.aiConvId || "").trim();
    if (!cid) throw new Error("请先打开一个对话");
    const raw = await apiFetch("/ai/conversations/" + encodeURIComponent(cid));
    const data = unwrapData(raw) || raw || {};
    const conv = data.conversation || {};
    const messages = Array.isArray(data.messages) ? data.messages : [];
    const title = conv.title || "Mydow AI 对话";
    const lines = messages.map((msg) => {
      const role = msg.role === "assistant" ? "Mydow AI" : "我";
      return `## ${role}\n\n${msg.content || ""}`.trim();
    });
    const content =
      `# ${title}\n\n` +
      `保存时间：${new Date().toLocaleString("zh-CN")}\n\n` +
      lines.join("\n\n---\n\n");
    const docRaw = await apiFetch("/kb/documents", {
      method: "POST",
      body: {
        title,
        summary: (conv.last_message_preview || content).slice(0, 500),
        content,
        document_type: "note",
        tags: ["AI 对话", "Mydow AI"],
      },
    });
    const doc = unwrapData(docRaw) || docRaw || {};
    await loadKbLibraryGrid().catch(() => {});
    return doc;
  }

  function bindAiChatRenameV37() {
    document.addEventListener(
      "click",
      (event) => {
        const btn = event.target.closest(
          'button[aria-label="重命名对话"], button[data-toast="已进入重命名状态"]',
        );
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const thread = _activeAiThreadV37();
        if (!thread) {
          toast("请先选中一个对话", "warning");
          return;
        }
        _renameAiConvV37(thread);
      },
      true,
    );
  }

  function bindAiChatMoreV37() {
    document.addEventListener(
      "click",
      (event) => {
        const btn = event.target.closest("[data-ai-chat-more]");
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const thread = _activeAiThreadV37();
        _openPopoverV37(btn, [
          { label: "重命名", handler: () => thread && _renameAiConvV37(thread) },
          {
            label: "保存到知识库",
            handler: async () => {
              try {
                const cid = (thread && thread.dataset.conversationId) || V14.aiConvId || "";
                const doc = await saveAiConversationToKbV20(cid);
                toast("对话已保存到知识库", "success");
                if (doc && doc.id) await openKbDocumentEditorV20(doc.id);
              } catch (e) {
                toast("保存到知识库失败: " + e.message, "error");
              }
            },
          },
          {
            label: "分享对话链接",
            handler: async () => {
              const cid = (thread && thread.dataset.conversationId) || V14.aiConvId || "";
              if (!cid) {
                toast("请先打开一个对话", "warning");
                return;
              }
              const url = `${window.location.origin}${window.location.pathname}#/ai/${cid}`;
              const ok = await _copyTextToClipboard(url);
              if (ok) {
                toast("已复制对话链接", "success");
              } else {
                window.prompt("复制对话链接", url);
              }
            },
          },
          { label: "删除对话", danger: true, handler: () => thread && _deleteAiConvV37(thread) },
        ]);
      },
      true,
    );
  }

  // §15.37.c — AI model selector tracking + persistence
  function trackAiModelV37() {
    document.addEventListener(
      "click",
      (event) => {
        const item = event.target.closest(".inline-popover button[data-menu-value]");
        if (!item) return;
        const trigger = document.querySelector(
          '[data-inline-menu="aiModel"][aria-expanded="true"]',
        );
        if (!trigger) return;
        const value = item.dataset.menuValue || "";
        if (!value) return;
        V14.aiModel = value;
        try { window.localStorage.setItem("mydow_v14_ai_model", value); } catch (_e) {}
      },
      false,
    );
  }

  function _restoreAiModelV37() {
    try {
      const saved = window.localStorage.getItem("mydow_v14_ai_model");
      if (saved) {
        V14.aiModel = saved;
        const triggerLabel = document.querySelector(
          '[data-inline-menu="aiModel"] [data-inline-label]',
        );
        if (triggerLabel) triggerLabel.textContent = saved;
      }
    } catch (_e) { /* ignore */ }
  }

  // §15.37.d — Card share link copy
  function bindCardShareV37() {
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest('[data-toast="已复制分享链接"]');
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const drawer = _findItemDetailDrawer();
        let cardId = (drawer && drawer.dataset.cardId) || "";
        if (!cardId) {
          const card = btn.closest(".idea-card[data-card-id]");
          cardId = (card && card.dataset.cardId) || "";
        }
        const url = cardId
          ? `${window.location.origin}/mydow/biz_v14/#card/${cardId}`
          : `${window.location.origin}/mydow/biz_v14/`;
        const ok = await _copyTextToClipboard(url);
        toast(ok ? "已复制分享链接" : "复制失败", ok ? "success" : "error");
      },
      true,
    );
  }

  // §17.4 + §16.4 — extend the IIFE's `aiAdd` inline-menu popover with three
  // extra entries (知识库 / 新建文档 / 语音输入) on top of the prototype's 3
  // (添加图片和文档 / 添加技能 / 链接网页). MutationObserver watches body for
  // the IIFE-created popover and injects the extras live so we never modify
  // the original HTML.
  function bindAiAddMenuExtrasV17() {
    const KNOWLEDGE_LABEL = "添加知识库背景";
    const NEW_DOC_LABEL = "新建空白文档";
    const VOICE_LABEL = "添加语音笔记";

    const onPopoverCreated = (popover) => {
      // Identify the popover via the trigger linked to it (aria-expanded=true)
      const opener = document.querySelector(
        '[data-inline-menu="aiAdd"][aria-expanded="true"]',
      );
      if (!opener) return;
      // Avoid double-injection
      if (popover.dataset.v17AiAddExtras === "true") return;
      popover.dataset.v17AiAddExtras = "true";

      const inject = (label, action) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.dataset.menuValue = label;
        btn.dataset.v17ExtraAction = action;
        btn.innerHTML = `<span>${label}</span>`;
        // Use IIFE's stagger animation pattern so the visual is consistent.
        btn.style.animationDelay = "120ms";
        btn.classList.add("stagger-enter");
        // Capture-phase to win over IIFE before stopPropagation.
        btn.addEventListener(
          "click",
          (event) => {
            event.preventDefault();
            event.stopImmediatePropagation();
            // Close the popover via opener
            opener.setAttribute("aria-expanded", "false");
            popover.classList.add("is-leaving");
            window.setTimeout(() => popover.remove(), 180);
            // Open the right modal / drawer
            if (action === "knowledge") {
              const trigger = document.querySelector(
                '[data-open-modal="aiContext"]',
              );
              if (trigger) trigger.click();
              else toast("请在 AI 输入框输入 @ 触发知识库选择", "info");
            } else if (action === "newdoc") {
              // §16.4 — create a fresh blank KB document, pin it as context.
              createBlankDocAndPinAsContextV16().catch((err) => {
                console.warn("[Mydow v1.4] new-doc add failed", err);
                toast("新建文档失败：" + err.message, "error");
              });
            } else if (action === "voice") {
              const trigger = document.querySelector(
                '[data-open-modal="voiceInput"]',
              );
              if (trigger) trigger.click();
              else toast("语音录入面板未就绪", "warning");
            }
          },
          true,
        );
        popover.appendChild(btn);
      };

      // Insert separator + extras after the existing buttons
      const sep = document.createElement("div");
      sep.style.cssText =
        "border-top:1px dashed rgba(108,124,153,0.18);margin:4px 0;height:0;";
      popover.appendChild(sep);
      inject(KNOWLEDGE_LABEL, "knowledge");
      inject(NEW_DOC_LABEL, "newdoc");
      inject(VOICE_LABEL, "voice");
    };

    // Observe document body for inline-popover insertions
    const obs = new MutationObserver((muts) => {
      for (const m of muts) {
        for (const node of m.addedNodes) {
          if (!(node instanceof HTMLElement)) continue;
          if (node.classList && node.classList.contains("inline-popover")) {
            // The IIFE only fires the menu for one menu at a time; check
            // currently-expanded trigger
            const opener = document.querySelector(
              '[data-inline-menu="aiAdd"][aria-expanded="true"]',
            );
            if (opener) onPopoverCreated(node);
          }
        }
      }
    });
    obs.observe(document.body, { childList: true, subtree: false });
  }

  // §17.5.recommend-card click — open skillRun for the recommended skill
  function bindRecommendCardClickV17() {
    document.addEventListener(
      "click",
      (event) => {
        const target = event.target.closest(".recommend-card .pill-button, .recommend-card");
        if (!target) return;
        const card = target.closest(".recommend-card");
        const sid = card?.dataset.skillId || "";
        if (!sid) return;
        V14.activeSkillId = sid;
        // Open the skillRun modal — the IIFE will handle DOM transition.
        const opener = document.querySelector('[data-open-modal="skillRun"]');
        if (opener) {
          event.preventDefault();
          event.stopImmediatePropagation();
          opener.click();
        }
      },
      true,
    );
  }

  // §17.2 — KB folder card `.star-action` button (real folder grid).
  // The IIFE wires this button as a static toggle with no backend call.
  // We intercept capture-phase, resolve folder_id via the parent
  // `.library-card[data-folder-id]` (set by `loadKbLibraryGrid`), call
  // `PATCH /kb/folders/{id}` with the next is_favorite, and update the
  // visual state (.active class + aria-pressed). On error we toast and
  // revert. Falls through to the IIFE only when no folder_id can be
  // resolved (e.g. brand-new card before bridge bound).
  function bindKbStarActionFavoriteV17() {
    document.addEventListener(
      "click",
      async (event) => {
        const star = event.target.closest(".star-action");
        if (!star) return;
        const card = star.closest(".library-card");
        const folderId = card?.dataset.folderId || "";
        if (!folderId) return; // let IIFE handle no-bridge case
        event.preventDefault();
        event.stopImmediatePropagation();
        const wasActive =
          star.classList.contains("active") ||
          star.getAttribute("aria-pressed") === "true";
        const next = !wasActive;
        // Optimistic UI flip
        star.classList.toggle("active", next);
        star.setAttribute("aria-pressed", String(next));
        try {
          await apiFetch("/kb/folders/" + folderId, {
            method: "PATCH",
            body: { is_favorite: next },
          });
          toast(next ? "已收藏" : "已取消收藏", "success");
          // Update V14 cache so the favorite tab filter works without
          // refetching.
          if (Array.isArray(V14.allFolders)) {
            const found = V14.allFolders.find((f) => String(f.id) === folderId);
            if (found) found.is_favorite = next;
          }
        } catch (e) {
          // Revert on failure
          star.classList.toggle("active", wasActive);
          star.setAttribute("aria-pressed", String(wasActive));
          toast("操作失败：" + e.message, "error");
        }
      },
      true, // capture-phase so we win over the IIFE bubble handler
    );
  }

  // §15.37.e — Folder favorite toggle (data-toast="收藏状态已更新")
  function bindFolderFavoriteV37() {
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest('[data-toast="收藏状态已更新"]');
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        let folderId = "";
        const card = btn.closest("[data-folder-id]");
        if (card) folderId = card.dataset.folderId || "";
        if (!folderId) {
          const folderCard =
            document.querySelector(".folder-main[data-folder-id]") ||
            document.querySelector('[data-folder-id]:not([data-folder-id=""])');
          folderId = (folderCard && folderCard.dataset.folderId) || "";
        }
        if (!folderId && V14.allFolders && V14.allFolders.length > 0) {
          folderId = V14.allFolders[0].id || "";
        }
        if (!folderId) {
          toast("未找到文件夹 ID", "warning");
          return;
        }
        const next = btn.getAttribute("aria-pressed") !== "true";
        try {
          await apiFetch("/kb/folders/" + folderId, {
            method: "PATCH",
            body: { is_favorite: next },
          });
          btn.setAttribute("aria-pressed", String(next));
          btn.classList.toggle("active", next);
          toast(next ? "已加入收藏" : "已取消收藏", "success");
          await loadKbLibraryGrid();
        } catch (e) {
          toast("收藏失败: " + e.message, "error");
        }
      },
      true,
    );
  }

  // §15.37.f — Skill favorite toggle (data-toast="已收藏 Skill")
  function bindSkillFavoriteV37() {
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest('[data-toast="已收藏 Skill"]');
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const sid =
          V14.activeSkillId ||
          document.querySelector(".skill-card[data-skill-id]")?.dataset.skillId ||
          "";
        if (!sid) {
          toast("未找到 Skill ID", "warning");
          return;
        }
        const key = "mydow_v14_fav_skills";
        let favs = [];
        try { favs = JSON.parse(window.localStorage.getItem(key) || "[]"); } catch {}
        const set = new Set(favs);
        const wasFav = set.has(sid);
        if (wasFav) set.delete(sid); else set.add(sid);
        try { window.localStorage.setItem(key, JSON.stringify([...set])); } catch {}
        try {
          await apiFetch("/skills/" + sid + "/favorite", {
            method: "POST",
            body: { is_favorite: !wasFav },
          });
        } catch (e) {
          if (e.status !== 404 && e.status !== 405) {
            console.warn("[v14] skill favorite", e);
          }
        }
        toast(wasFav ? "已取消收藏" : "已收藏 Skill", "success");
      },
      true,
    );
  }

  // §18.5 — Document editor hydrate + autosave + focus polish.
  let _docEditorSaveTimerV18 = null;

  function injectDocEditorPolishCssV18() {
    if (document.getElementById("mydow-doc-editor-v18")) return;
    const style = document.createElement("style");
    style.id = "mydow-doc-editor-v18";
    style.textContent = `
      .doc-editor-surface {
        transition: border-color .18s ease, box-shadow .18s ease, background .18s ease;
      }
      .doc-editor-surface:focus-within {
        border-color: rgba(91,120,255,.30) !important;
        box-shadow: 0 28px 80px rgba(39, 55, 96, .13), 0 0 0 4px rgba(91,120,255,.08) !important;
        background: rgba(255,255,255,.94) !important;
      }
      .doc-title-input,
      .doc-body[contenteditable="true"] {
        outline: none !important;
        box-shadow: none !important;
        caret-color: #5b78ff;
      }
      .doc-title-input:focus-visible,
      .doc-body[contenteditable="true"]:focus-visible {
        outline: none !important;
      }
      .doc-body[contenteditable="true"] {
        min-height: 360px;
        border-radius: 16px;
        padding: 6px 8px;
        margin: -6px -8px 0;
        transition: background .18s ease;
      }
      .doc-body[contenteditable="true"]:focus {
        background: linear-gradient(180deg, rgba(248,250,255,.72), rgba(255,255,255,.32));
      }
      .doc-status[data-v18-state="saving"] { color: #5b78ff; background: rgba(91,120,255,.10); }
      .doc-status[data-v18-state="error"] { color: #c44646; background: rgba(216,72,74,.10); }
      .doc-status[data-v18-state="saved"] { color: #158c72; background: rgba(112,200,170,.13); }
    `;
    document.head.appendChild(style);
  }

  function docTextToHtmlV18(text) {
    const raw = String(text || "").trim();
    if (!raw) return "<p></p>";
    return raw
      .split(/\n{2,}/)
      .map((para) => `<p>${escapeHtmlV14(para).replace(/\n/g, "<br>")}</p>`)
      .join("");
  }

  function getDocEditorMainV18() {
    return document.querySelector(".doc-editor-main");
  }

  function setDocEditorStatusV18(state, text) {
    const main = getDocEditorMainV18();
    const status = main && main.querySelector(".doc-status");
    if (!status) return;
    status.dataset.v18State = state || "saved";
    const icon = state === "error" ? "!" : state === "saving" ? "…" : "✓";
    status.innerHTML =
      `<span aria-hidden="true" style="font-weight:900">${icon}</span>` +
      escapeHtmlV14(text || (state === "saving" ? "正在保存" : state === "error" ? "保存失败" : "已自动保存"));
  }

  function hydrateDocEditorFooterV18(doc) {
    const main = getDocEditorMainV18();
    const footer = main && main.querySelector(".doc-footer");
    if (!footer) return;
    const text = String(doc.content || "").trim();
    const words = doc.word_count || (text ? text.length : 0);
    const updated = doc.updated_at ? new Date(doc.updated_at).toLocaleString("zh-CN") : "刚刚";
    footer.innerHTML =
      `<span>${Number(words || 0).toLocaleString("zh-CN")} 字</span>` +
      `<span>最后更新 ${escapeHtmlV14(updated)}</span>`;
  }

  async function hydrateDocEditorFromDocumentV18(documentId) {
    const id = String(documentId || "").trim();
    if (!id) return;
    injectDocEditorPolishCssV18();
    const main = getDocEditorMainV18();
    if (!main) return;
    main.dataset.documentId = id;
    setDocEditorStatusV18("saving", "正在读取文档");
    try {
      const resp = await apiFetch("/kb/documents/" + encodeURIComponent(id));
      const doc = unwrapData(resp) || resp || {};
      main.dataset.documentId = doc.id || id;
      const title = main.querySelector(".doc-title-input");
      const body = main.querySelector(".doc-body");
      if (title) {
        title.value = doc.title || "未命名文档";
        title.dataset.v18SavedValue = title.value;
      }
      if (body) {
        body.innerHTML = docTextToHtmlV18(doc.content || doc.summary || "");
        body.dataset.v18SavedValue = body.innerText || body.textContent || "";
      }
      hydrateDocEditorFooterV18(doc);
      setDocEditorStatusV18("saved", "已同步到知识库");
    } catch (e) {
      setDocEditorStatusV18("error", "读取失败");
      toast("读取文档失败: " + e.message, "error");
    }
  }

  async function saveDocEditorNowV18() {
    const main = getDocEditorMainV18();
    const docId = main && main.dataset.documentId;
    if (!docId) return;
    const title = main.querySelector(".doc-title-input");
    const body = main.querySelector(".doc-body");
    const nextTitle = (title && title.value.trim()) || "未命名文档";
    const nextContent = (body && (body.innerText || body.textContent || "").trim()) || "";
    const patch = {};
    if (title && nextTitle !== (title.dataset.v18SavedValue || "")) patch.title = nextTitle;
    if (body && nextContent !== (body.dataset.v18SavedValue || "")) patch.content = nextContent;
    if (!Object.keys(patch).length) return;
    setDocEditorStatusV18("saving", "正在保存");
    try {
      const resp = await apiFetch("/kb/documents/" + encodeURIComponent(docId), {
        method: "PATCH",
        body: patch,
      });
      const doc = unwrapData(resp) || resp || {};
      if (title) title.dataset.v18SavedValue = nextTitle;
      if (body) body.dataset.v18SavedValue = nextContent;
      hydrateDocEditorFooterV18(doc);
      setDocEditorStatusV18("saved", "已自动保存");
    } catch (e) {
      setDocEditorStatusV18("error", "保存失败");
      toast("文档保存失败: " + e.message, "error");
    }
  }

  function scheduleDocEditorSaveV18() {
    window.clearTimeout(_docEditorSaveTimerV18);
    setDocEditorStatusV18("saving", "等待自动保存");
    _docEditorSaveTimerV18 = window.setTimeout(() => {
      saveDocEditorNowV18().catch(() => {});
    }, 750);
  }

  function bindDocEditorHydrateAndAutosaveV18() {
    injectDocEditorPolishCssV18();
    document.addEventListener(
      "click",
      (event) => {
        const row = event.target.closest(".doc-row[data-document-id], [data-open-drawer='docDetail'][data-doc-id], .kb-list-row[data-doc-id]");
        if (!row) return;
        const id = row.dataset.documentId || row.dataset.docId || "";
        if (!id) return;
        window.setTimeout(() => hydrateDocEditorFromDocumentV18(id), 160);
      },
      false,
    );
    document.addEventListener(
      "input",
      (event) => {
        const target = event.target;
        if (!target || !target.closest) return;
        if (!target.closest(".doc-editor-main")) return;
        if (!target.matches(".doc-title-input, .doc-body")) return;
        scheduleDocEditorSaveV18();
      },
      true,
    );
    document.addEventListener(
      "blur",
      (event) => {
        const target = event.target;
        if (!target || !target.closest) return;
        if (!target.closest(".doc-editor-main")) return;
        if (!target.matches(".doc-title-input, .doc-body")) return;
        window.clearTimeout(_docEditorSaveTimerV18);
        saveDocEditorNowV18().catch(() => {});
      },
      true,
    );
  }

  async function openKbDocumentEditorV20(documentId, options = {}) {
    const id = String(documentId || "").trim();
    if (!id) {
      toast("缺少文档 ID，无法打开", "warning");
      return null;
    }
    closeV14Layers();
    const page = document.querySelector(".page");
    if (page) {
      [
        "knowledge-open",
        "folder-open",
        "ai-open",
        "ai-chat-open",
        "garden-open",
        "skills-open",
        "notifications-open",
        "profile-open",
        "insights-full-open",
      ].forEach((cls) => page.classList.remove(cls));
      page.classList.add("doc-open");
    }
    document.querySelectorAll("[data-nav-target]").forEach((nav) => {
      nav.classList.remove("active");
      nav.removeAttribute("aria-current");
    });
    if (options.updateHash !== false) {
      try {
        window.history.replaceState(null, "", "#/kb/doc/" + encodeURIComponent(id));
      } catch (_e) {}
    }
    await hydrateDocEditorFromDocumentV18(id);
    const main = getDocEditorMainV18();
    if (main) {
      main.scrollIntoView({ block: "start", behavior: "smooth" });
    }
    return main;
  }

  // §15.37.g — Doc AI actions: 5 buttons in doc-editor toolbar
  function _resolveDocSubjectV37() {
    const main = document.querySelector(".doc-editor-main, .doc-editor-drawer");
    if (!main) return null;
    const docId = main.dataset.documentId || "";
    const titleEl = main.querySelector(".doc-title-input, h1, .doc-title");
    const title =
      (titleEl && ((titleEl.value && titleEl.value.trim()) || titleEl.textContent.trim())) ||
      "未命名文档";
    return { docId, title, hostEl: main };
  }

  async function _runFirstSkillForDocV37(instruction) {
    let skills;
    try {
      const resp = await apiFetch("/skills?page_size=5");
      skills = unwrapData(resp) || resp || {};
    } catch (e) {
      throw new Error("无法获取 Skill: " + e.message);
    }
    const list = (skills && skills.items) || [];
    const sid = (list[0] && list[0].id) || "";
    if (!sid) throw new Error("没有可用 Skill");
    const subject = _resolveDocSubjectV37();
    return apiFetch("/skills/" + sid + "/run", {
      method: "POST",
      body: {
        input: { instruction, target: subject ? "doc:" + subject.docId : "" },
        save_output: true,
      },
    });
  }

  function bindDocAiActionsV37() {
    const handlers = {
      "AI 已开始生成摘要": async () => {
        await _runFirstSkillForDocV37("为当前文档生成结构化摘要 (200 字以内)");
        toast("AI 摘要任务已入队", "success");
      },
      "摘要已重新生成": async () => {
        await _runFirstSkillForDocV37("重新生成当前文档的摘要，强调关键决策与下一步行动");
        toast("已重新生成摘要", "success");
      },
      "已提取推荐标签": async () => {
        await _runFirstSkillForDocV37("基于文档内容提取 3-5 个推荐标签 (中文)");
        toast("推荐标签已生成", "success");
      },
      "已生成知识卡片": async () => {
        const subject = _resolveDocSubjectV37();
        if (!subject) {
          toast("请先打开一篇文档", "warning");
          return;
        }
        const body = subject.hostEl.querySelector(".doc-body, [contenteditable]");
        const text = (body && body.textContent.trim()) || "";
        await apiFetch("/cards", {
          method: "POST",
          body: {
            title: "由文档生成: " + subject.title.slice(0, 40),
            summary: text.slice(0, 240),
            tags: ["AI 生成", "文档摘录"],
            content_type: "card",
          },
        });
        toast("已生成知识卡片", "success");
      },
      "已关联数字花园": async () => {
        const subject = _resolveDocSubjectV37();
        if (!subject || !subject.docId) {
          toast("请先打开一篇文档", "warning");
          return;
        }
        const body = subject.hostEl.querySelector(".doc-body, [contenteditable]");
        const text = (body && body.textContent.trim()) || "";
        await apiFetch("/cards", {
          method: "POST",
          body: {
            title: "数字花园节点: " + subject.title.slice(0, 48),
            summary: (text || subject.title).slice(0, 240),
            tags: ["数字花园", "文档关联"],
            content_type: "note",
            source_id: subject.docId,
          },
        });
        await apiFetch("/garden/overview");
        toast("已创建数字花园节点", "success");
      },
    };
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest("button[data-toast]");
        if (!btn) return;
        const label = btn.getAttribute("data-toast") || "";
        const fn = handlers[label];
        if (!fn) return;
        if (btn.closest(".notice-row")) return;
        if (btn.closest(".surface-layer[data-modal]")) return;
        if (btn.closest(".ai-msg-actions, .assistant-message-actions")) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        btn.disabled = true;
        try { await fn(); }
        catch (e) { toast("操作失败: " + e.message, "error"); }
        finally { btn.disabled = false; }
      },
      true,
    );
  }

  // §15.37.h — Insight actions (save to KB / create cleanup task / move)
  function bindInsightActionsV37() {
    const handlers = {
      "洞察已保存到知识库": async (btn) => {
        const drawer = btn.closest('[data-drawer="insightDetail"]');
        const insightId = drawer && drawer.dataset.insightId;
        const titleEl = drawer && drawer.querySelector("h2");
        const title = (titleEl && titleEl.textContent.trim()) || "AI 洞察";
        const summaryEl = drawer && drawer.querySelector(".drawer-summary, p");
        const summary = (summaryEl && summaryEl.textContent.trim()) || "";
        await apiFetch("/cards", {
          method: "POST",
          body: {
            title,
            summary,
            tags: ["AI 洞察"],
            source_id: insightId || null,
            content_type: "insight",
          },
        });
        toast("洞察已保存到知识库", "success");
      },
      "已创建整理任务": async (btn) => {
        const drawer = btn.closest('[data-drawer="insightDetail"]');
        const insightId = drawer && drawer.dataset.insightId;
        const titleEl = drawer && drawer.querySelector("h2");
        const title = (titleEl && titleEl.textContent.trim()) || "整理洞察";
        await apiFetch("/tasks", {
          method: "POST",
          body: {
            title: "整理: " + title,
            source_type: "insight",
            source_id: insightId || null,
            priority: 2,
            status: "todo",
          },
        });
        toast("已创建整理任务", "success");
      },
      "已移动到知识库": async (btn) => {
        const drawer = btn.closest('[data-drawer="itemDetail"]');
        const cardId = drawer && drawer.dataset.cardId;
        if (!cardId) {
          toast("未找到卡片 ID", "warning");
          return;
        }
        let folders;
        try {
          const resp = await apiFetch("/kb/folders?page_size=1");
          folders = unwrapData(resp) || {};
        } catch (e) {
          toast("无法获取文件夹: " + e.message, "error");
          return;
        }
        const fid = (folders.items && folders.items[0] && folders.items[0].id) || "";
        if (!fid) {
          toast("请先创建一个文件夹", "warning");
          return;
        }
        await apiFetch("/cards/" + cardId + "/move", {
          method: "POST",
          body: { folder_id: fid },
        });
        toast("已移动到知识库", "success");
      },
    };
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest("button[data-toast]");
        if (!btn) return;
        const label = btn.getAttribute("data-toast") || "";
        const fn = handlers[label];
        if (!fn) return;
        if (btn.closest(".surface-layer[data-modal]")) return;
        if (btn.closest(".notice-row")) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        btn.disabled = true;
        try { await fn(btn); }
        catch (e) { toast("操作失败: " + e.message, "error"); }
        finally { btn.disabled = false; }
      },
      true,
    );
  }

  // ═════════════════════════════════════════════════════════════════════════
  // §15.39 — Wire the remaining 25 unhandled v1.4 data-toast labels.
  //   Each entry maps a Chinese toast label to either a real PRD10 API call
  //   or a UI-only behaviour (theme, voice, etc.). Capture-phase handlers
  //   beat the prototype IIFE simulateAction so the user sees real state.
  //   When a handler is defined, the prototype's existing toast still
  //   fires (we don't kill it) but the bridge runs first to do the side
  //   effect (DB write / route change / preference patch).
  // ═════════════════════════════════════════════════════════════════════════

  function injectDarkThemeCssV20() {
    if (document.getElementById("mydow-dark-theme-v20")) return;
    const style = document.createElement("style");
    style.id = "mydow-dark-theme-v20";
    style.textContent = `
      html[data-theme="dark"] {
        color-scheme: dark;
        --bg: #111113;
        --panel: rgba(31,31,35,.78);
        --panel-strong: rgba(39,39,43,.94);
        --ink: #f5f5f7;
        --text: #e4e4e7;
        --muted: #a1a1aa;
        --faint: #71717a;
        --line: rgba(255,255,255,.13);
        --line-soft: rgba(255,255,255,.08);
        --accent: #8ea2ff;
        --accent-deep: #a6b4ff;
        --mint: #74d3c2;
        --gold: #e8c078;
        --rose: #e2a3ad;
        --shadow: 0 22px 70px rgba(0,0,0,.34);
        --soft-shadow: 0 14px 36px rgba(0,0,0,.26);
      }
      body.theme-dark {
        --bg: #111113;
        --panel: rgba(31,31,35,.78);
        --panel-strong: rgba(39,39,43,.94);
        --ink: #f5f5f7;
        --text: #e4e4e7;
        --muted: #a1a1aa;
        --faint: #71717a;
        --line: rgba(255,255,255,.13);
        --line-soft: rgba(255,255,255,.08);
        --accent: #8ea2ff;
        --accent-deep: #a6b4ff;
        --shadow: 0 22px 70px rgba(0,0,0,.34);
        --soft-shadow: 0 14px 36px rgba(0,0,0,.26);
        --mydow-dark-bg: #111113;
        --mydow-dark-sidebar: #1c1c1e;
        --mydow-dark-surface: #242426;
        --mydow-dark-surface-2: #2c2c2e;
        --mydow-dark-surface-3: #363638;
        --mydow-dark-text: #f5f5f7;
        --mydow-dark-muted: #a1a1aa;
        --mydow-dark-subtle: #73737c;
        --mydow-dark-border: rgba(255,255,255,.12);
        --mydow-dark-border-strong: rgba(255,255,255,.2);
        --mydow-dark-accent: #8ea2ff;
        --mydow-dark-accent-strong: #a6b4ff;
        background:
          radial-gradient(circle at 82% 8%, rgba(142, 162, 255, .16), transparent 32rem),
          linear-gradient(180deg, #111113 0%, #151517 100%) !important;
        color: var(--mydow-dark-text) !important;
        transition: background-color .24s ease, color .24s ease;
      }
      body.theme-dark .page,
      body.theme-dark .app,
      body.theme-dark .app-shell,
      body.theme-dark .content-grid {
        background: transparent !important;
        color: var(--mydow-dark-text) !important;
      }
      body.theme-dark .topbar {
        background: transparent !important;
        border-color: transparent !important;
      }
      body.theme-dark .search {
        background: rgba(31,31,35,.86) !important;
        border: 1px solid var(--mydow-dark-border) !important;
        box-shadow: 0 18px 42px rgba(0,0,0,.26) !important;
      }
      body.theme-dark .search input {
        background: transparent !important;
        color: var(--mydow-dark-text) !important;
      }
      html[data-theme="dark"] body,
      html.dark body {
        background:
          radial-gradient(circle at 84% 10%, rgba(142, 162, 255, .12), transparent 30rem),
          linear-gradient(180deg, #111113 0%, #151517 100%) !important;
        color: var(--mydow-dark-text, #f5f5f7) !important;
      }
      body.theme-dark .workspace {
        background: transparent !important;
        color: var(--mydow-dark-text) !important;
      }
      body.theme-dark aside:first-child,
      body.theme-dark .side-nav,
      body.theme-dark .sidebar,
      body.theme-dark .app-sidebar {
        background: rgba(28, 28, 30, .94) !important;
        border-color: var(--mydow-dark-border) !important;
        box-shadow: inset -1px 0 0 var(--mydow-dark-border) !important;
      }
      body.theme-dark aside:first-child a,
      body.theme-dark .side-nav a,
      body.theme-dark .nav-item,
      body.theme-dark [data-nav],
      body.theme-dark [data-route] {
        color: var(--mydow-dark-muted) !important;
      }
      body.theme-dark aside:first-child .active,
      body.theme-dark .side-nav .active,
      body.theme-dark .nav-item.active,
      body.theme-dark [aria-current="page"] {
        background: rgba(255,255,255,.08) !important;
        color: var(--mydow-dark-text) !important;
        border-color: var(--mydow-dark-border-strong) !important;
        box-shadow: none !important;
      }
      body.theme-dark .main-column,
      body.theme-dark .right-rail,
      body.theme-dark .knowledge-main,
      body.theme-dark .folder-main,
      body.theme-dark .doc-main,
      body.theme-dark .ai-main,
      body.theme-dark .skills-main,
      body.theme-dark .profile-main {
        background: transparent !important;
        color: var(--mydow-dark-text) !important;
      }
      body.theme-dark .hero,
      body.theme-dark .page-hero,
      body.theme-dark .capture-hero {
        background: linear-gradient(135deg, rgba(31,31,35,.88), rgba(17,17,19,.94)) !important;
        color: var(--mydow-dark-text) !important;
        border-color: var(--mydow-dark-border) !important;
        box-shadow: 0 24px 80px rgba(0,0,0,.2) !important;
      }
      body.theme-dark .capture,
      body.theme-dark .capture-panel,
      body.theme-dark .capture-card,
      body.theme-dark .capture-input,
      body.theme-dark .composer-card,
      body.theme-dark .ai-composer,
      body.theme-dark .ai-chat-composer,
      body.theme-dark .ai-input-panel {
        background: rgba(36,36,38,.9) !important;
        color: var(--mydow-dark-text) !important;
        border-color: var(--mydow-dark-border-strong) !important;
        box-shadow: 0 22px 70px rgba(0,0,0,.28) !important;
      }
      body.theme-dark .capture::before,
      body.theme-dark .capture::after,
      body.theme-dark .capture .capture-footer,
      body.theme-dark .capture .capture-actions,
      body.theme-dark .capture .capture-meta,
      body.theme-dark .capture .input-toolbar {
        background: rgba(36,36,38,.9) !important;
        border-color: var(--mydow-dark-border) !important;
      }
      body.theme-dark .profile-main,
      body.theme-dark .settings-card,
      body.theme-dark .profile-card,
      body.theme-dark .account-card,
      body.theme-dark .user-card,
      body.theme-dark .surface-layer .modal-card,
      body.theme-dark .drawer-layer .detail-drawer,
      body.theme-dark .drawer-card,
      body.theme-dark .recent-list-panel,
      body.theme-dark .content-view,
      body.theme-dark .stat-card,
      body.theme-dark .insight-panel,
      body.theme-dark .skill-card,
      body.theme-dark .record-card,
      body.theme-dark .idea-card,
      body.theme-dark .library-card,
      body.theme-dark .folder-card,
      body.theme-dark .quick-action,
      body.theme-dark .quick-setting,
      body.theme-dark .recommend-card,
      body.theme-dark .compact-row,
      body.theme-dark .topic-pill,
      body.theme-dark .skill-chip,
      body.theme-dark .skill-rec-drawer,
      body.theme-dark .skill-rec-drawer .rec-card,
      html[data-theme="dark"] .profile-card,
      html[data-theme="dark"] .account-card,
      html[data-theme="dark"] .skill-chip,
      html[data-theme="dark"] .topic-pill,
      html[data-theme="dark"] .recommend-card,
      body.theme-dark .notice-row {
        background: rgba(36,36,38,.92) !important;
        color: var(--mydow-dark-text) !important;
        border-color: var(--mydow-dark-border) !important;
        box-shadow: 0 18px 50px rgba(0,0,0,.22) !important;
      }
      body.theme-dark h1,
      body.theme-dark h2,
      body.theme-dark h3,
      body.theme-dark h4,
      body.theme-dark strong,
      body.theme-dark .record-title,
      body.theme-dark .card-title,
      body.theme-dark .doc-title,
      body.theme-dark .doc-title-input {
        color: var(--mydow-dark-text) !important;
      }
      body.theme-dark p,
      body.theme-dark .drawer-summary,
      body.theme-dark .profile-main .preference-row span,
      body.theme-dark .settings-card span,
      body.theme-dark .meta,
      body.theme-dark .muted,
      body.theme-dark .subtle,
      body.theme-dark .record-meta,
      body.theme-dark .stat-note {
        color: var(--mydow-dark-muted) !important;
      }
      body.theme-dark input,
      body.theme-dark textarea,
      body.theme-dark select,
      body.theme-dark .select-control,
      body.theme-dark .segmented-control,
      body.theme-dark .doc-editor-surface {
        background: rgba(44,44,46,.88) !important;
        color: var(--mydow-dark-text) !important;
        border-color: var(--mydow-dark-border) !important;
        outline-color: rgba(142,162,255,.55) !important;
      }
      body.theme-dark input::placeholder,
      body.theme-dark textarea::placeholder,
      body.theme-dark [contenteditable="true"]:empty::before {
        color: var(--mydow-dark-subtle) !important;
      }
      body.theme-dark .pill-button,
      body.theme-dark .ai-top-action,
      body.theme-dark .quick-action,
      body.theme-dark .skill-chip,
      body.theme-dark .topic-pill,
      body.theme-dark .recent-doc-row,
      body.theme-dark .record-row:not(.record-head) {
        background: rgba(44,44,46,.82) !important;
        color: var(--mydow-dark-text) !important;
        border-color: var(--mydow-dark-border) !important;
        box-shadow: none !important;
      }
      body.theme-dark .pill-button:hover,
      body.theme-dark .ai-top-action:hover,
      body.theme-dark .quick-action:hover,
      body.theme-dark .skill-chip:hover,
      body.theme-dark .topic-pill:hover,
      body.theme-dark .recent-doc-row:hover,
      body.theme-dark .record-row:not(.record-head):hover,
      body.theme-dark .quick-setting:hover {
        background: rgba(58,58,60,.96) !important;
        border-color: var(--mydow-dark-border-strong) !important;
      }
      body.theme-dark .record-head,
      body.theme-dark .table-head,
      body.theme-dark .list-head {
        background: transparent !important;
        color: var(--mydow-dark-muted) !important;
        border-color: var(--mydow-dark-border) !important;
      }
      body.theme-dark .segmented-control button.active,
      body.theme-dark .toggle-switch.active,
      body.theme-dark .skill-chip.active,
      body.theme-dark .topic-pill.active,
      html[data-theme="dark"] .skill-chip.active,
      html[data-theme="dark"] .topic-pill.active,
      html[data-theme="dark"] .sidebar a.active {
        background: rgba(142,162,255,.18) !important;
        color: #e9edff !important;
        border-color: rgba(142,162,255,.38) !important;
        box-shadow: 0 8px 22px rgba(142,162,255,.26) !important;
      }
      body.theme-dark .send-button,
      body.theme-dark .ai-send-button,
      body.theme-dark [data-send],
      body.theme-dark [data-submit] {
        background: linear-gradient(135deg, var(--mydow-dark-accent), var(--mydow-dark-accent-strong)) !important;
        color: #fff !important;
        border-color: transparent !important;
      }
      body.theme-dark .surface-layer,
      body.theme-dark .drawer-layer {
        background: rgba(0,0,0,.4) !important;
      }
      body.theme-dark a {
        color: #b7c3ff !important;
      }
      body.theme-dark hr,
      body.theme-dark .divider,
      body.theme-dark .drawer-section,
      body.theme-dark .modal-foot-actions {
        border-color: var(--mydow-dark-border) !important;
      }
    `;
    document.head.appendChild(style);
  }

  // §15.39.theme — 主题切换（写 localStorage + html dataset，不依赖后端）
  function _applyTheme(name) {
    injectDarkThemeCssV20();
    const root = document.documentElement;
    if (name === "dark") {
      root.dataset.theme = "dark";
      document.body.classList.add("theme-dark");
      document.body.classList.remove("theme-light");
    } else {
      root.dataset.theme = "light";
      document.body.classList.add("theme-light");
      document.body.classList.remove("theme-dark");
    }
    try { window.localStorage.setItem("mydow_v14_theme", name); } catch (_e) {}
  }

  function _restoreThemeV39() {
    let saved = "light";
    try { saved = window.localStorage.getItem("mydow_v14_theme") || "light"; } catch {}
    _applyTheme(saved);
  }

  // §15.39.confirmDelete — 上下文化删除：根据 _DRAWER_CTX 推断 cards/docs/folders
  function _activeDrawerContextV39() {
    const drawer =
      document.querySelector(
        '[data-drawer="itemDetail"]:not([hidden]), [data-drawer="insightDetail"]:not([hidden]), [data-drawer="skillDetail"]:not([hidden])'
      ) || _findItemDetailDrawer();
    if (!drawer) return {};
    return {
      cardId: drawer.dataset.cardId || "",
      documentId: drawer.dataset.documentId || "",
      folderId: drawer.dataset.folderId || "",
      insightId: drawer.dataset.insightId || "",
      drawer,
    };
  }

  async function _performContextualDelete() {
    const ctx = _activeDrawerContextV39();
    if (ctx.cardId) {
      await apiFetch("/cards/" + ctx.cardId, { method: "DELETE" });
      window.dispatchEvent(new CustomEvent("mydow:capture-completed"));
      return "card";
    }
    if (ctx.documentId) {
      await apiFetch("/kb/documents/" + ctx.documentId, { method: "DELETE" });
      return "document";
    }
    if (ctx.folderId) {
      await apiFetch("/kb/folders/" + ctx.folderId, { method: "DELETE" });
      await loadKbLibraryGrid();
      return "folder";
    }
    return "";
  }

  function bindConfirmDeleteV39() {
    document.addEventListener(
      "click",
      async (event) => {
        const directBtn = event.target.closest('.drawer-actions [data-open-modal="confirmDelete"]');
        if (directBtn) {
          event.preventDefault();
          event.stopImmediatePropagation();
          if (!window.confirm("确定删除当前内容吗？")) return;
          directBtn.disabled = true;
          try {
            const kind = await _performContextualDelete();
            if (!kind) {
              toast("未找到删除对象（请先打开抽屉/选择卡片）", "warning");
            } else {
              toast(kind === "card" ? "卡片已删除" : kind === "document" ? "文档已删除" : "文件夹已删除", "success");
              closeV14Layers();
              await Promise.allSettled([loadFeedCards(), loadFeedIntoRecordsTable(), loadKbLibraryGrid()]);
            }
          } catch (e) {
            toast("删除失败: " + e.message, "error");
          } finally {
            directBtn.disabled = false;
          }
          return;
        }
        const btn = event.target.closest('[data-toast="已删除，仍可在回收站恢复"]');
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        btn.disabled = true;
        try {
          const kind = await _performContextualDelete();
          if (!kind) {
            toast("未找到删除对象（请先打开抽屉/选择卡片）", "warning");
          } else {
            toast(
              kind === "card"
                ? "卡片已删除"
                : kind === "document"
                ? "文档已删除"
                : "文件夹已删除",
              "success"
            );
            closeV14Layers();
          }
        } catch (e) {
          toast("删除失败: " + e.message, "error");
        } finally {
          btn.disabled = false;
        }
      },
      true
    );
  }

  // §15.39.movePanel — 「移动到」面板：读取文件夹列表，提示用户选择目标
  async function _openMovePanelForCard(cardId) {
    try {
      const resp = await apiFetch("/kb/folders?page_size=20");
      const data = unwrapData(resp) || resp || {};
      const folders = (data.items || []).filter((f) => f && f.id);
      if (folders.length === 0) {
        toast("尚无文件夹，请先创建一个", "warning");
        return;
      }
      const labels = folders
        .map((f, i) => `${i + 1}. ${f.name}`)
        .join("\n");
      const choice = window.prompt(
        `选择目标文件夹（输入序号 1-${folders.length}）：\n${labels}`,
        "1"
      );
      const idx = parseInt(choice || "0", 10) - 1;
      if (idx < 0 || idx >= folders.length) {
        toast("已取消移动", "info");
        return;
      }
      const folder = folders[idx];
      await apiFetch("/cards/" + cardId + "/move", {
        method: "POST",
        body: { folder_id: folder.id },
      });
      toast(`已移动到「${folder.name}」`, "success");
    } catch (e) {
      toast("移动失败: " + e.message, "error");
    }
  }

  function bindMovePanelV39() {
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest('[data-toast="已打开移动面板"]');
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const ctx = _activeDrawerContextV39();
        if (!ctx.cardId) {
          toast("请先打开一张卡片再点移动", "warning");
          return;
        }
        await _openMovePanelForCard(ctx.cardId);
      },
      true
    );
  }

  // §15.39.themeToggle — 浅色 / 深色模式切换 → localStorage + body class
  function bindThemeToggleV39() {
    document.addEventListener(
      "click",
      (event) => {
        const lightBtn = event.target.closest(
          '[data-toast="已切换为浅色模式"]'
        );
        const darkBtn = event.target.closest('[data-toast="深色模式已预览"]');
        const target = lightBtn ? "light" : darkBtn ? "dark" : null;
        if (!target) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        _applyTheme(target);
        toast(
          target === "dark" ? "已切换为深色模式" : "已切换为浅色模式",
          "success"
        );
      },
      true
    );
  }

  // §15.39.preference — 偏好开关：自动保存 / 二步验证（PATCH /me/preferences）
  async function _patchMePreference(key, value) {
    return apiFetch("/me/preferences", {
      method: "PATCH",
      body: { [key]: value },
    });
  }

  function formatSecurityTimeV18(value) {
    if (!value) return "尚未记录";
    try {
      const d = new Date(value);
      if (Number.isNaN(d.getTime())) return String(value);
      return d.toLocaleString("zh-CN", { hour12: false });
    } catch (_e) {
      return String(value);
    }
  }

  function renderAccountSecurityV18(security) {
    const data = security || {};
    const root = document.querySelector(".profile-main");
    if (!root) return;
    const emailBtn = root.querySelector('[data-toast="邮箱验证链接已发送"]');
    if (emailBtn) {
      emailBtn.textContent = data.email_verified ? "已验证" : data.email_verification_requested_at ? "重新发送" : "验证邮箱";
      emailBtn.classList.toggle("active", Boolean(data.email_verified));
      emailBtn.setAttribute("aria-pressed", String(Boolean(data.email_verified)));
      emailBtn.disabled = Boolean(data.email_verified);
    }
    const emailRow = emailBtn?.closest(".preference-row, article, .quick-setting");
    const emailSub = emailRow?.querySelector("span");
    if (emailSub && data.email) {
      const tail = data.email_verified
        ? " · 已验证"
        : data.email_verification_requested_at
          ? " · 待验证 " + formatSecurityTimeV18(data.email_verification_requested_at)
          : "";
      emailSub.textContent = String(data.email) + tail;
    }

    const twoFactor = root.querySelector('[data-toast="二步验证状态已更新"]');
    if (twoFactor) {
      const on = Boolean(data.two_factor_enabled);
      twoFactor.classList.toggle("active", on);
      twoFactor.setAttribute("aria-pressed", String(on));
      twoFactor.setAttribute("aria-label", on ? "二步验证已开启" : "二步验证已关闭");
    }

    const refreshBtn = root.querySelector('[data-toast="已刷新登录设备"]');
    const deviceRow = refreshBtn?.closest(".preference-row, article, .quick-setting");
    const deviceText = deviceRow?.querySelector("span");
    const firstDevice = Array.isArray(data.login_devices) ? data.login_devices[0] : null;
    if (deviceText && firstDevice) {
      deviceText.textContent =
        `${firstDevice.label || "当前设备"} · ${formatSecurityTimeV18(firstDevice.last_seen_at)}`;
    }
    if (refreshBtn && data.last_security_refresh_at) {
      refreshBtn.dataset.lastRefreshAt = data.last_security_refresh_at;
      refreshBtn.setAttribute("aria-label", "刷新登录设备，上次刷新 " + formatSecurityTimeV18(data.last_security_refresh_at));
    }
  }

  async function hydrateAccountSecurityV18() {
    try {
      const resp = await apiFetch("/me/security");
      renderAccountSecurityV18(unwrapData(resp) || resp || {});
    } catch (e) {
      console.warn("[Mydow v1.4] account security hydrate failed", e);
    }
  }

  function bindAccountSecurityHydrateV18() {
    const schedule = () => [120, 520, 1000].forEach((delay) => window.setTimeout(hydrateAccountSecurityV18, delay));
    document.addEventListener("click", (event) => {
      if (event.target.closest('[data-settings-panel="security"]')) schedule();
    }, false);
    schedule();
  }

  function bindPrefToggleV39() {
    const map = {
      "自动保存设置已更新": "auto_save",
      "二步验证状态已更新": "two_factor_enabled",
    };
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest("button[data-toast]");
        if (!btn) return;
        const label = btn.getAttribute("data-toast") || "";
        const key = map[label];
        if (!key) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const sw =
          (btn.matches(".toggle-switch") ? btn : null) ||
          btn.closest("article")?.querySelector(".toggle-switch") ||
          btn.querySelector(".toggle-switch");
        const wasActive = sw && sw.classList.contains("active");
        const next = !wasActive;
        try {
          await _patchMePreference(key, next);
          if (sw) {
            sw.classList.toggle("active", next);
            sw.setAttribute("aria-pressed", String(next));
            if (key === "auto_save") {
              sw.setAttribute("aria-label", next ? "自动保存已开启" : "自动保存已关闭");
            }
            if (key === "two_factor_enabled") {
              sw.setAttribute("aria-label", next ? "二步验证已开启" : "二步验证已关闭");
            }
          }
          if (key === "two_factor_enabled") hydrateAccountSecurityV18();
          toast(label, "success");
        } catch (e) {
          toast("保存失败: " + e.message, "error");
        }
      },
      true
    );
  }

  function bindAiBackButtonV20() {
    document.addEventListener(
      "click",
      (event) => {
        const btn = event.target.closest(".ai-top-action[data-page-back]");
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const page = document.querySelector(".page");
        if (page && page.classList.contains("ai-chat-open")) {
          page.classList.remove("ai-chat-open");
          page.classList.add("ai-open");
          toast("已返回 Mydow AI 工作台", "success");
          return;
        }
        const nav = document.querySelector('[data-nav-target="home"]');
        if (nav) nav.click();
      },
      true,
    );
  }

  function enhanceNativeSelectsV20() {
    document.querySelectorAll(".surface-layer select, .modal-card select").forEach((select) => {
      if (select.closest(".v20-select-shell")) return;
      const shell = document.createElement("span");
      shell.className = "v20-select-shell";
      select.parentNode.insertBefore(shell, select);
      shell.appendChild(select);
    });
  }

  async function openBestSearchHitV20(title) {
    const query = String(title || "").trim();
    if (!query) return false;
    try {
      const params = new URLSearchParams({ q: query, page_size: "6" });
      ["document", "card", "folder", "insight"].forEach((type) => params.append("object_type", type));
      const resp = await apiFetch("/search?" + params.toString());
      const data = unwrapData(resp) || resp || {};
      const hit = (data.items || [])[0];
      if (!hit) return false;
      navigateToSearchHitV17(hit);
      return true;
    } catch (e) {
      console.warn("[Mydow v1.4] linked row search failed", e);
      return false;
    }
  }

  async function openOrCreateLinkedDocumentV23(row) {
    const title = (
      row.querySelector("strong")?.textContent ||
      row.textContent ||
      ""
    )
      .replace(/^关联节点[:：]\s*/, "")
      .replace(/\s+/g, " ")
      .trim();
    if (!title) return false;
    const drawer = row.closest(".drawer-layer, .detail-drawer");
    const drawerTitle =
      drawer?.querySelector("h2")?.textContent?.replace(/\s+/g, " ").trim() || "";
    const meta = row.querySelector("span")?.textContent?.replace(/\s+/g, " ").trim() || "";
    const sectionTitle =
      row.closest(".drawer-section")?.querySelector("h3")?.textContent?.trim() || "关联内容";

    const params = new URLSearchParams({ q: title, page_size: "8" });
    params.append("object_type", "document");
    try {
      const resp = await apiFetch("/search?" + params.toString());
      const data = unwrapData(resp) || resp || {};
      const exact = (data.items || []).find((hit) => {
        const ht = String(hit.title || hit.name || "").trim();
        return ht === title || ht.includes(title) || title.includes(ht);
      });
      const hit = exact || (data.items || [])[0];
      const docId = hit?.object_id || hit?.id || hit?.document_id || "";
      if (docId) {
        await openKbDocumentEditorV20(docId);
        closeV14Layers();
        return true;
      }
    } catch (e) {
      console.warn("[Mydow v1.4] linked document search failed", e);
    }

    const content = [
      `# ${title}`,
      drawerTitle ? `来源抽屉：${drawerTitle}` : "",
      meta ? `条目元信息：${meta}` : "",
      `关联区块：${sectionTitle}`,
      "",
      "该文档由关联内容点击自动创建，用于把原型中的关联条目沉淀为可追溯的知识库资产。",
    ].filter(Boolean).join("\n\n");
    const created = await apiFetch("/kb/documents", {
      method: "POST",
      body: {
        title,
        content,
        summary: `${title} - ${meta || sectionTitle}`,
        document_type: "markdown",
        tags: ["关联内容", sectionTitle, drawerTitle].filter(Boolean),
      },
    });
    const doc = unwrapData(created) || created || {};
    await loadKbLibraryGrid().catch(() => {});
    if (doc.id) {
      await openKbDocumentEditorV20(doc.id);
      closeV14Layers();
      return true;
    }
    return false;
  }

  function bindDrawerLinkedRowsV20() {
    document.addEventListener(
      "click",
      async (event) => {
        const row = event.target.closest(
          '.drawer-layer.is-open .drawer-section .quick-setting, .drawer-layer.is-open .drawer-section .related-row, [data-drawer="nodeDetail"] .quick-setting, [data-drawer="insightDetail"] .quick-setting, [data-drawer="itemDetail"] .quick-setting',
        );
        if (!row) return;
        if (event.target.closest("button, a, [data-open-modal], [data-toast]")) return;
        const title = row.querySelector("strong")?.textContent || row.textContent || "";
        if (!title.trim()) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        row.setAttribute("aria-busy", "true");
        row.classList.add("is-loading");
        try {
          const ok = await openOrCreateLinkedDocumentV23(row);
          if (ok) toast("已打开关联知识库文档", "success");
          else toast("未找到关联内容：" + title.trim().slice(0, 32), "warning");
        } catch (e) {
          toast("打开关联文档失败: " + e.message, "error");
        } finally {
          row.removeAttribute("aria-busy");
          row.classList.remove("is-loading");
        }
      },
      true,
    );
  }

  function bindGenerateHandbookV20() {
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest('[data-open-modal="aiSave"]');
        if (!btn || !/生成手册/.test(btn.textContent || "")) return;
        const drawer = btn.closest('[data-drawer="nodeDetail"], [data-drawer="insightDetail"], [data-drawer="itemDetail"]');
        if (!drawer) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const title = drawer.querySelector("h2")?.textContent?.trim() || "知识手册";
        const context = Array.from(drawer.querySelectorAll(".drawer-section"))
          .map((sec) => (sec.textContent || "").replace(/\s+/g, " ").trim())
          .filter(Boolean)
          .slice(0, 8)
          .join("\n");
        btn.disabled = true;
        btn.classList.add("is-loading");
        try {
          const resp = await apiFetch("/research/tasks", {
            method: "POST",
            body: {
              topic: title + " 手册",
              scope: context || title,
              output: "生成一份可沉淀到知识库的结构化手册，包含背景、关键发现、操作步骤和后续建议。",
              include_sources: true,
              save_to_kb: true,
            },
          });
          const data = unwrapData(resp) || resp || {};
          const docId = data.document_id || data.report?.document_id || "";
          toast("手册已生成并保存到知识库", "success");
          if (docId) await openKbDocumentEditorV20(docId);
          else await loadKbLibraryGrid().catch(() => {});
        } catch (e) {
          toast("生成手册失败: " + e.message, "error");
        } finally {
          btn.disabled = false;
          btn.classList.remove("is-loading");
        }
      },
      true,
    );
  }

  // §15.39.passwordModal — 「修改密码入口已打开」→ 弹 prompt 收集旧/新密码
  //   并 POST /me/password。与 §8.16 后端配合。
  function bindPasswordModalV39() {
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest('[data-toast="修改密码入口已打开"]');
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const current = window.prompt("请输入当前密码", "");
        if (!current) return;
        const next = window.prompt("请输入新密码（≥6 位）", "");
        if (!next || next.length < 6) {
          toast("新密码长度至少 6 位", "warning");
          return;
        }
        try {
          await apiFetch("/me/password", {
            method: "POST",
            body: { current_password: current, new_password: next },
          });
          toast("密码修改成功，请用新密码登录", "success");
        } catch (e) {
          toast("修改失败: " + (e.message || "原密码错误"), "error");
        }
      },
      true
    );
  }

  // §15.39.billing — 「订阅管理已打开」→ real billing plan snapshot/update.
  function bindBillingV39() {
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest('[data-toast="订阅管理已打开"]');
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        btn.disabled = true;
        try {
          const overviewRaw = await apiFetch("/billing/overview");
          const plansRaw = await apiFetch("/billing/plans");
          const overview = unwrapData(overviewRaw) || overviewRaw || {};
          const plansData = unwrapData(plansRaw) || plansRaw || {};
          const current = (overview.subscription && overview.subscription.plan) || "free";
          const items = Array.isArray(plansData.items) ? plansData.items : [];
          const labels = items.map((p) => `${p.code}: ${p.name || p.code}`).join("\n");
          const next = window.prompt(
            `当前订阅：${current}\n可选计划：\n${labels}\n\n输入计划代码以切换，留空则只查看。`,
            current,
          );
          const plan = String(next || "").trim().toLowerCase();
          if (!plan || plan === current) {
            toast(`当前订阅：${current}，余额 ${overview.credit_balance ?? 0} credits`, "success");
            return;
          }
          if (!items.some((p) => p.code === plan)) {
            toast("未找到该订阅计划", "warning");
            return;
          }
          const updatedRaw = await apiFetch("/billing/subscription", {
            method: "PATCH",
            body: { plan, billing_cycle: "monthly" },
          });
          const updated = unwrapData(updatedRaw) || updatedRaw || {};
          toast(`订阅已切换为 ${updated.plan || plan}`, "success");
          await hydrateMe();
        } catch (e) {
          toast("订阅管理失败: " + e.message, "error");
        } finally {
          btn.disabled = false;
        }
      },
      true
    );
  }

  // §18.12.email — 邮箱验证请求必须写入真实账号安全状态。
  function bindEmailVerifyV39() {
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest('[data-toast="邮箱验证链接已发送"]');
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        if (btn.disabled) return;
        btn.disabled = true;
        const oldText = btn.textContent;
        btn.textContent = "发送中...";
        try {
          const resp = await apiFetch("/me/security/email-verification", {
            method: "POST",
            body: {},
          });
          const data = unwrapData(resp) || resp || {};
          renderAccountSecurityV18(data);
          const delivery = data.email_verification_delivery === "smtp" ? "验证邮件已发送" : "验证请求已保存到本地安全记录";
          toast(delivery, "success");
        } catch (e) {
          btn.disabled = false;
          btn.textContent = oldText || "验证邮箱";
          toast("邮箱验证失败: " + e.message, "error");
        }
      },
      true
    );
  }

  // §15.39.permissions — persist the user's default permission intent.
  function bindPermissionsV39() {
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest('[data-toast="权限设置已打开"]');
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        btn.disabled = true;
        try {
          await apiFetch("/me/preferences", {
            method: "PATCH",
            body: {
              permission_acl_mode: "owner_only",
              permission_default_visibility: "private",
              permission_settings_opened_at: new Date().toISOString(),
            },
          });
          toast("权限默认值已保存为仅自己可见", "success");
        } catch (e) {
          toast("权限设置保存失败: " + e.message, "error");
        } finally {
          btn.disabled = false;
        }
      },
      true
    );
  }

  // §15.39.storage — 「存储详情已刷新」 → 拉 /kb/overview + /me 显示真实容量
  function bindStorageRefreshV39() {
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest('[data-toast="存储详情已刷新"]');
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        try {
          const resp = await apiFetch("/kb/overview");
          const data = unwrapData(resp) || resp || {};
          const docs = data.document_count || (data.totals && data.totals.documents) || 0;
          const folders = data.folder_count || (data.totals && data.totals.folders) || 0;
          toast(`存储已刷新：${folders} 个文件夹 / ${docs} 篇文档`, "success");
        } catch (e) {
          toast("刷新失败: " + e.message, "error");
        }
      },
      true
    );
  }

  // §18.12.security — 「已刷新登录设备」 → 真实写入当前会话设备列表。
  function bindSecurityDevicesV39() {
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest('[data-toast="已刷新登录设备"]');
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        btn.disabled = true;
        const oldText = btn.textContent;
        btn.textContent = "刷新中...";
        try {
          const resp = await apiFetch("/me/security/devices/refresh", {
            method: "POST",
            body: {},
          });
          renderAccountSecurityV18(unwrapData(resp) || resp || {});
          toast("登录设备已刷新", "success");
        } catch (e) {
          toast("刷新失败: " + e.message, "error");
        } finally {
          btn.disabled = false;
          btn.textContent = oldText || "刷新";
        }
      },
      true
    );
  }

  // §15.46 — Hydrate the aiContext modal with real KB documents whenever
  // it opens. We watch the layer for the `is-open` class via MutationObserver
  // and replace the static `.notice-list` rows with documents fetched from
  // ``/kb/documents``, plus a per-row select/deselect button that drives
  // selection state for the §15.39.aiContext add handler.
  /**
   * @typedef {{ id:string, title:string, folder_name?:string, summary?:string, tags?:string[] }} CtxDoc
   */
  function injectAiContextPickerStylesV18() {
    if (document.getElementById("mydow-ai-context-picker-v18")) return;
    const style = document.createElement("style");
    style.id = "mydow-ai-context-picker-v18";
    style.textContent = `
      .ai-context-picker-v18 {
        display: grid;
        gap: 10px;
        margin: 0 0 14px;
        padding: 12px;
        border: 1px solid rgba(117, 140, 255, 0.18);
        border-radius: 18px;
        background: linear-gradient(180deg, rgba(255,255,255,.98), rgba(247,249,255,.94));
        box-shadow: 0 18px 50px rgba(37, 50, 91, 0.10);
      }
      .ai-context-picker-v18 label {
        display: flex;
        align-items: center;
        gap: 8px;
        min-height: 42px;
        padding: 0 12px;
        border-radius: 14px;
        background: rgba(255,255,255,.95);
        border: 1px solid rgba(108,124,153,.16);
      }
      .ai-context-picker-v18 input {
        width: 100%;
        border: 0;
        outline: 0;
        background: transparent;
        color: #21304a;
        font-size: 14px;
        font-weight: 650;
      }
      .ai-context-picker-v18 input::placeholder { color: #9aa6bb; font-weight: 590; }
      .ai-context-picker-v18 .picker-meta {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        color: #7b88a0;
        font-size: 12px;
        font-weight: 650;
      }
      .notice-list.ai-context-list-v18 {
        display: grid;
        gap: 8px;
        max-height: min(54vh, 520px);
        overflow: auto;
        padding-right: 4px;
      }
      .notice-row.context-source-v18 {
        border: 1px solid rgba(108,124,153,.14);
        border-radius: 16px;
        background: rgba(255,255,255,.92);
        box-shadow: 0 8px 24px rgba(37,50,91,.06);
        transition: transform .16s ease, border-color .16s ease, background .16s ease;
      }
      .notice-row.context-source-v18:hover,
      .notice-row.context-source-v18:focus-visible {
        transform: translateY(-1px);
        border-color: rgba(91,120,255,.38);
        background: #fff;
        outline: 0;
      }
      .notice-row.context-source-v18.active {
        border-color: rgba(91,120,255,.52);
        background: rgba(239,244,255,.95);
      }
      .notice-row.context-source-v18 .notice-action {
        border: 0;
        border-radius: 999px;
        background: rgba(91,120,255,.10);
        color: #4f65d8;
        font-weight: 780;
      }
      .notice-row.context-source-v18.active .notice-action {
        background: #5b78ff;
        color: #fff;
      }
    `;
    document.head.appendChild(style);
  }

  function bindAiContextDrawerHydrateV14() {
    const layer = document.querySelector('.surface-layer[data-modal="aiContext"]');
    if (!layer) return;
    injectAiContextPickerStylesV18();

    function ensureSearchBox() {
      const list = layer.querySelector(".notice-list");
      if (!list) return null;
      let picker = layer.querySelector("[data-ai-context-picker]");
      if (!picker) {
        picker = document.createElement("div");
        picker.className = "ai-context-picker-v18";
        picker.dataset.aiContextPicker = "true";
        picker.innerHTML = `
          <label>
            <svg class="icon" aria-hidden="true"><use href="#icon-search" /></svg>
            <input type="search" data-ai-context-search role="searchbox" aria-label="搜索知识库文档或文件夹" placeholder="搜索知识库、文档、卡片或文件夹..." autocomplete="off" />
          </label>
          <div class="picker-meta">
            <span data-ai-context-count>正在读取知识库...</span>
            <span>Enter 选择 · Esc 关闭</span>
          </div>`;
        list.parentNode.insertBefore(picker, list);
      }
      return picker.querySelector("[data-ai-context-search]");
    }

    async function hydrate(keyword) {
      const list = layer.querySelector(".notice-list");
      if (!list) return;
      const search = ensureSearchBox();
      const queryText = String(
        keyword != null ? keyword : (search && search.value) || "",
      ).trim();
      // On AI surface, resolve conversation first so "已选" matches this chat's context_scope.
      if (isAiWorkspaceActive()) {
        try {
          await ensureAiConversationId();
        } catch (_e) {
          /* drawer still works; highlights stay empty until a conv exists */
        }
      }
      // Ask the user's current AI conversation so we can highlight already-pinned docs.
      let alreadyPinned = new Set();
      if (V14.aiConvId) {
        try {
          const detail = unwrapData(
            await apiFetch("/ai/conversations/" + V14.aiConvId),
          );
          const scope = detail?.conversation?.context_scope || {};
          (scope.document_ids || []).forEach((id) => alreadyPinned.add(String(id)));
        } catch (_e) {
          /* ignore — drawer still works with empty selection */
        }
      }

      // Pull both folders and recent docs so the user has something to pick.
      let docs = [];
      let folders = [];
      try {
        const docPath = "/kb/documents?page_size=30" + (queryText ? "&keyword=" + encodeURIComponent(queryText) : "");
        const folderPath = "/kb/folders?include_counts=true" + (queryText ? "&keyword=" + encodeURIComponent(queryText) : "");
        const [docsResp, foldersResp] = await Promise.all([
          apiFetch(docPath),
          apiFetch(folderPath),
        ]);
        docs = (unwrapData(docsResp)?.items) || [];
        folders = (unwrapData(foldersResp)?.items) || [];
      } catch (_e) {
        /* ignore — fallback below */
      }
      const folderById = Object.fromEntries(
        folders.map((f) => [String(f.id), f.name || ""]),
      );

      // Build new rows. Folders first (count badge), then top documents.
      const rows = [];
      folders.slice(0, 8).forEach((f) => {
        const id = String(f.id);
        const isOn = (V14.contextScope.folder_ids || []).map(String).includes(id);
        rows.push(`
          <article class="notice-row context-source context-source-v18 ${isOn ? "active" : ""}" role="option" tabindex="0" aria-selected="${isOn ? "true" : "false"}" data-source-id="${id}" data-source-type="folder" data-source-title="${escapeHtmlV14(f.name || "未命名文件夹")}" style="grid-template-columns: 48px minmax(0,1fr) 80px;cursor:pointer;">
            <span class="notice-icon ${isOn ? "green" : ""}"><svg class="icon"><use href="#icon-folder" /></svg></span>
            <div class="notice-body"><h2>${escapeHtmlV14(f.name || "未命名文件夹")}</h2><p>${escapeHtmlV14(String(f.document_count ?? 0))} 篇文档 · 文件夹</p></div>
            <button class="notice-action" type="button" data-context-toggle>${isOn ? "已选" : "选择"}</button>
          </article>`);
      });
      docs.slice(0, 20).forEach((d) => {
        const id = String(d.id);
        const fold = folderById[String(d.folder_id || "")] || "";
        const summary = (d.summary || (d.content || "").slice(0, 80) || "未填写摘要").trim();
        const isOn = alreadyPinned.has(id);
        rows.push(`
          <article class="notice-row context-source context-source-v18 ${isOn ? "active" : ""}" role="option" tabindex="0" aria-selected="${isOn ? "true" : "false"}" data-source-id="${id}" data-source-type="document" data-source-title="${escapeHtmlV14(d.title || "未命名文档")}" data-folder-id="${escapeHtmlV14(String(d.folder_id || ""))}" style="grid-template-columns: 48px minmax(0,1fr) 80px;cursor:pointer;">
            <span class="notice-icon ${isOn ? "green" : ""}"><svg class="icon"><use href="#icon-file-text" /></svg></span>
            <div class="notice-body"><h2>${escapeHtmlV14(d.title || "未命名文档")}</h2><p>${escapeHtmlV14(summary)}${fold ? " · " + escapeHtmlV14(fold) : ""}</p></div>
            <button class="notice-action" type="button" data-context-toggle>${isOn ? "已选" : "选择"}</button>
          </article>`);
      });
      if (rows.length === 0) {
        rows.push(
          `<article class="notice-row" style="grid-template-columns: 1fr;"><div class="notice-body"><p>${queryText ? "没有匹配的知识库内容，换个关键词试试。" : "当前知识库还没有文档。先去「灵感采集」记录一条吧。"}</p></div></article>`,
        );
      }
      list.classList.add("ai-context-list-v18");
      list.setAttribute("role", "listbox");
      list.setAttribute("aria-label", "知识库上下文搜索结果");
      list.innerHTML = rows.join("");
      const count = layer.querySelector("[data-ai-context-count]");
      if (count) count.textContent = `${folders.length + docs.length} 个结果${queryText ? " · " + queryText : ""}`;
      if (search && document.activeElement !== search) search.focus({ preventScroll: true });
      list.dataset.bridgeBound = "true";
    }

    function bindToggleClicks() {
      layer.addEventListener("click", (ev) => {
        const row = ev.target.closest(".context-source[data-source-id]");
        if (!row) return;
        ev.preventDefault();
        ev.stopPropagation();
        const wasOn = row.classList.toggle("active");
        row.setAttribute("aria-selected", wasOn ? "true" : "false");
        const btn = row.querySelector("[data-context-toggle]");
        if (btn) btn.textContent = wasOn ? "已选" : "选择";
        const icon = row.querySelector(".notice-icon");
        if (icon) icon.classList.toggle("green", wasOn);
      });
      layer.addEventListener("keydown", (ev) => {
        const input = ev.target.closest("[data-ai-context-search]");
        if (input) {
          if (ev.key === "Escape") closeV14Layers();
          if (ev.key === "ArrowDown") {
            ev.preventDefault();
            layer.querySelector(".context-source-v18")?.focus();
          }
          return;
        }
        const row = ev.target.closest(".context-source-v18[data-source-id]");
        if (!row) return;
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          row.click();
        } else if (ev.key === "ArrowDown") {
          ev.preventDefault();
          row.nextElementSibling?.focus?.();
        } else if (ev.key === "ArrowUp") {
          ev.preventDefault();
          row.previousElementSibling?.focus?.() || layer.querySelector("[data-ai-context-search]")?.focus();
        }
      });
      let searchTimer = null;
      layer.addEventListener("input", (ev) => {
        const input = ev.target.closest("[data-ai-context-search]");
        if (!input) return;
        window.clearTimeout(searchTimer);
        const count = layer.querySelector("[data-ai-context-count]");
        if (count) count.textContent = "正在搜索...";
        searchTimer = window.setTimeout(() => {
          hydrate(input.value).catch((e) =>
            console.warn("[Mydow v1.4] aiContext search failed", e),
          );
        }, 220);
      });
    }

    if (!layer.dataset.bridgeContextHydrate) {
      bindToggleClicks();
      const obs = new MutationObserver(() => {
        if (!layer.hidden && layer.classList.contains("is-open")) {
          // Hydrate in the next tick so the IIFE finishes its open animation.
          window.setTimeout(() => {
            hydrate().catch((e) =>
              console.warn("[Mydow v1.4] aiContext hydrate failed", e),
            );
          }, 60);
        }
      });
      obs.observe(layer, { attributes: true, attributeFilter: ["class", "hidden"] });
      layer.dataset.bridgeContextHydrate = "true";
    }
  }

  // §15.39.aiContext — 「上下文已添加到 AI 对话」 → PATCH /ai/conversations/{id}
  //   把 modal 中选中的 KB 资源写入 conversation.context_scope
  function bindAiContextAddV39() {
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest('[data-toast="上下文已添加到 AI 对话"]');
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        let cid;
        try {
          cid = await ensureAiConversationId();
        } catch (_e) {
          toast("无法创建或找到 AI 对话，请稍后再试", "warning");
          return;
        }
        if (!cid) {
          toast("请先选择一个 AI 对话再添加上下文", "warning");
          return;
        }
        const layer = btn.closest('.surface-layer[data-modal="aiContext"]');
        const documentIds = [];
        const folderIds = [];
        const sources = [];
        if (layer) {
          layer.querySelectorAll(".context-source[data-source-id].active").forEach((el) => {
            const t = el.dataset.sourceType || "document";
            const id = String(el.dataset.sourceId || "");
            const title =
              el.dataset.sourceTitle ||
              el.querySelector(".notice-body h2")?.textContent?.trim() ||
              (t === "folder" ? "知识库文件夹" : "未命名文档");
            if (!id) return;
            if (t === "folder") {
              folderIds.push(id);
              V14.contextFoldersCache[id] = { id, title };
              sources.push({ type: "folder", label: title, ref: id });
            } else {
              documentIds.push(id);
              V14.contextDocsCache[id] = {
                id,
                title,
                folder_id: el.dataset.folderId || null,
                kind: "doc",
              };
              sources.push({ type: "doc", label: title, ref: id });
            }
          });
        }
        if (documentIds.length === 0 && folderIds.length === 0) {
          toast("请先选择至少一个文档或文件夹", "warning");
          return;
        }
        try {
          await apiFetch("/ai/conversations/" + cid, {
            method: "PATCH",
            body: {
              context_scope: mergedContextScopeV16({
                document_ids: documentIds,
                folder_ids: folderIds,
                sources,
              }),
            },
          });
          toast(
            `上下文已添加（${documentIds.length} 文档 + ${folderIds.length} 文件夹）`,
            "success",
          );
          closeV14Layers();
          await loadActiveConversationContextScope();
        } catch (e) {
          toast("添加失败: " + e.message, "error");
        }
      },
      true
    );
  }

  // §15.39.duplicateFolder — 「副本已创建」 → 用 POST /kb/folders 创建同名副本
  function bindDuplicateFolderV39() {
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest('[data-toast="副本已创建"]');
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const ctx = _activeDrawerContextV39();
        const card = btn.closest("[data-folder-id]");
        const folderId = ctx.folderId || (card && card.dataset.folderId) || "";
        const name = card && card.querySelector("strong, .library-card-title");
        const baseName = (name && name.textContent.trim()) || "未命名文件夹";
        try {
          await apiFetch("/kb/folders", {
            method: "POST",
            body: { name: `${baseName}（副本）` },
          });
          toast("副本已创建", "success");
          await loadKbLibraryGrid();
        } catch (e) {
          toast("复制失败: " + e.message, "error");
        }
      },
      true
    );
  }

  // §18.10.voice — 「录音已暂停」 stops the real browser speech recognizer.
  function bindVoicePauseV39() {
    document.addEventListener(
      "click",
      (event) => {
        const btn = event.target.closest('[data-toast="录音已暂停"]');
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        if (voiceRecognitionV18) {
          try { voiceRecognitionV18.stop(); } catch (_e) { /* noop */ }
          voiceRecognitionV18 = null;
        }
        const layer = btn.closest('.surface-layer[data-modal="voiceInput"]');
        const status = layer?.querySelector("[data-v18-voice-status]");
        if (status) status.textContent = "听写已暂停";
        toast("语音听写已暂停", "success");
      },
      true
    );
  }

  // §15.39.notifPrefs — 「通知设置已保存」 → PATCH /me/preferences.notifications
  function bindNotifPrefsSaveV39() {
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest('[data-toast="通知设置已保存"]');
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const layer = btn.closest('.surface-layer[data-modal="notificationSettings"]');
        const channels = {};
        if (layer) {
          layer.querySelectorAll(".toggle-switch").forEach((sw, i) => {
            const labelEl = sw.closest("article")?.querySelector("strong");
            const key = labelEl
              ? (labelEl.textContent || `channel_${i}`).trim()
              : `channel_${i}`;
            channels[key] = sw.classList.contains("active");
          });
        }
        try {
          await apiFetch("/me/preferences", {
            method: "PATCH",
            body: { notification_channels: channels },
          });
          toast("通知设置已保存", "success");
          closeV14Layers();
        } catch (e) {
          toast("保存失败: " + e.message, "error");
        }
      },
      true
    );
  }

  // §15.39.profileSave — 「个人资料已更新」 → PATCH /me
  function bindProfileSaveV39() {
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest('[data-toast="个人资料已更新"]');
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const layer = btn.closest('.surface-layer[data-modal="editProfile"]');
        const body = {};
        if (layer) {
          const fullName = layer.querySelector('input[name="full_name"], input[data-field="fullName"]');
          if (fullName) body.full_name = fullName.value.trim();
          const email = layer.querySelector('input[type="email"], input[name="email"]');
          if (email && email.value.trim()) body.email = email.value.trim();
          const tz = layer.querySelector('select[name="timezone"], select[data-field="timezone"]');
          if (tz) body.timezone = tz.value;
        }
        try {
          await apiFetch("/me", { method: "PATCH", body });
          await refreshProfileChip();
          toast("个人资料已更新", "success");
          closeV14Layers();
        } catch (e) {
          toast("保存失败: " + e.message, "error");
        }
      },
      true
    );
  }

  // §15.39.aiPersonalize — 「AI 个性化设置已保存」 → PATCH /me/preferences
  function bindAiPersonalizeV39() {
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest('[data-toast="AI 个性化设置已保存"]');
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const layer = btn.closest('.surface-layer[data-modal="aiPersonalize"]');
        const ai = {};
        if (layer) {
          layer.querySelectorAll(".toggle-switch").forEach((sw, i) => {
            const labelEl = sw.closest("article")?.querySelector("strong");
            const key = labelEl
              ? (labelEl.textContent || `pref_${i}`).trim()
              : `ai_pref_${i}`;
            ai[key] = sw.classList.contains("active");
          });
        }
        try {
          await apiFetch("/me/preferences", {
            method: "PATCH",
            body: { ai_personalization: ai },
          });
          toast("AI 个性化设置已保存", "success");
          closeV14Layers();
        } catch (e) {
          toast("保存失败: " + e.message, "error");
        }
      },
      true
    );
  }

  // §15.39.aiSaveModal — 「AI 结果已保存到知识库」 → POST /ai/messages/{id}/save-to-kb
  function bindAiSaveResultV39() {
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest('[data-toast="AI 结果已保存到知识库"]');
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const mid = V14.lastAssistantMessageId;
        if (!mid) {
          toast("请先完成一轮 AI 回复", "warning");
          return;
        }
        try {
          await apiFetch("/ai/messages/" + mid + "/save-to-kb", {
            method: "POST",
            body: {},
          });
          toast("AI 结果已保存到知识库", "success");
          closeV14Layers();
        } catch (e) {
          toast("保存失败: " + e.message, "error");
        }
      },
      true
    );
  }

  // §15.39.skillRunModal — 「Skill 正在运行」 → POST /skills/{id}/run
  function bindSkillRunModalV39() {
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest('[data-toast="Skill 正在运行"]');
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const sid = V14.activeSkillId;
        if (!sid) {
          toast("请先在 Skills 广场选择一个 Skill", "warning");
          return;
        }
        const layer = btn.closest('.surface-layer[data-modal="skillRun"]');
        const ta = layer && layer.querySelector("textarea");
        const text = (ta && ta.value.trim()) || "";
        try {
          await apiFetch("/skills/" + sid + "/run", {
            method: "POST",
            body: { input: { text }, save_output: true },
          });
          toast("Skill 已开始运行，结果会进知识库", "success");
          closeV14Layers();
        } catch (e) {
          toast("运行失败: " + e.message, "error");
        }
      },
      true
    );
  }

  // §18.10.voiceFinish — 「语音记录已保存」 → POST /capture/text(type=voice) 落库
  function bindVoiceFinishV39() {
    document.addEventListener(
      "click",
      async (event) => {
        const btn = event.target.closest('[data-toast="语音记录已保存"]');
        if (!btn) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        await handleVoiceInputModal(btn, btn.closest('.surface-layer[data-modal="voiceInput"]'));
      },
      true
    );
  }

  // §15.39 master register — wires every helper above + restores theme.
  function bindAllRemainingV39() {
    bindConfirmDeleteV39();
    bindMovePanelV39();
    bindThemeToggleV39();
    bindAccountSecurityHydrateV18();
    bindPrefToggleV39();
    bindPasswordModalV39();
    bindBillingV39();
    bindEmailVerifyV39();
    bindPermissionsV39();
    bindStorageRefreshV39();
    bindSecurityDevicesV39();
    bindAiBackButtonV20();
    bindDrawerLinkedRowsV20();
    bindGenerateHandbookV20();
    bindAiContextAddV39();
    bindAiContextDrawerHydrateV14();
    bindDuplicateFolderV39();
    bindVoicePauseV39();
    bindNotifPrefsSaveV39();
    bindProfileSaveV39();
    bindAiPersonalizeV39();
    bindAiSaveResultV39();
    bindSkillRunModalV39();
    bindVoiceFinishV39();
    enhanceNativeSelectsV20();
    document.addEventListener("click", () => window.setTimeout(enhanceNativeSelectsV20, 80), false);
    _restoreThemeV39();
  }

  // ─── §15.42 — a11y fixes (axe-core critical/serious resolutions) ─────────
  // Business owner's HTML uses `<button aria-selected>` for tab toggle,
  // which axe-core marks critical (`aria-allowed-attr`). Convert to
  // `aria-pressed` (a valid button-toggle attribute), preserving visual
  // state. We don't touch `mydow.html` itself; this runs at boot and on
  // mutation to also catch dynamically rendered tabs.
  function applyA11yFixesV14() {
    const fixOnce = () => {
      // 1. button[data-view-target] / [data-kb-tab] / [data-notice-filter]
      //    use aria-selected which is invalid for plain buttons.
      const tabButtonSelectors = [
        'button[data-view-target][aria-selected]',
        'button[data-kb-tab][aria-selected]',
        'button[data-notice-filter][aria-selected]',
        'button[data-tab][aria-selected]',
      ];
      document.querySelectorAll(tabButtonSelectors.join(",")).forEach((btn) => {
        const sel = btn.getAttribute("aria-selected") === "true";
        btn.removeAttribute("aria-selected");
        btn.setAttribute("aria-pressed", String(sel));
        if (!btn.hasAttribute("type")) btn.setAttribute("type", "button");
      });
      // 2. <article role="button" aria-label="..."> with <h3> inside
      //    triggers heading-order + aria-allowed-role. Promote to <div>
      //    role-equivalent: keep article but drop role=button (the
      //    article itself is keyboard-clickable via tabindex=0 + click
      //    listeners; assistive tech can read the children).
      document
        .querySelectorAll('article[role="button"]')
        .forEach((art) => {
          art.removeAttribute("role");
          if (!art.hasAttribute("tabindex")) art.setAttribute("tabindex", "0");
        });
    };
    fixOnce();
    // Re-apply when the DOM mutates (the prototype IIFE re-renders tabs).
    const mo = new MutationObserver(() => fixOnce());
    mo.observe(document.body, { subtree: true, childList: true });
  }

  // ─── §15.44/§15.47 — Layout & polish CSS injection ───────────────────────
  // The v1.4 prototype caps several `*-main` panels at a fixed pixel height
  // with ``overflow: hidden`` so taller content (Skills 12 cards, KB many
  // documents, AI chat thread, Insights full panel) gets clipped. We inject
  // a stylesheet that:
  //   1. Removes the cap → swaps to ``overflow-y: auto`` so users can scroll.
  //   2. Adds a polished scrollbar that matches the brand palette.
  //   3. Raises the chip filter affordance, keeps the action buttons sticky
  //      to the bottom of the viewport so investors always see them.
  //   4. Renders citation chips with a soft hover lift and the brand color.
  // Nothing in this CSS overrides class semantics; it only relaxes overflow.
  function injectInvestorPolishCss() {
    if (document.getElementById("mydow-v14-polish-css")) return;
    const style = document.createElement("style");
    style.id = "mydow-v14-polish-css";
    style.textContent = `
/* §15.44 — Allow tall page bodies to scroll within the viewport.
 * The prototype originally clipped content with a fixed pixel max-height
 * (548px), so anything below the fold disappeared. We swap that for a
 * viewport-aware bound + custom scrollbar so all content stays reachable
 * without breaking the surrounding grid layout. */
.skills-main,
.knowledge-main,
.folder-main,
.garden-main,
.notification-main,
.insights-full-main,
.profile-main {
  max-height: calc(100vh - 120px) !important;
  overflow-y: auto !important;
  padding-bottom: 56px;
  scrollbar-gutter: stable;
}
.ai-main {
  /* AI workspace already manages its own internal scroll on the message list. */
  max-height: calc(100vh - 84px) !important;
  overflow-y: auto !important;
}

/* Custom scrollbar matching the brand palette */
.skills-main::-webkit-scrollbar,
.knowledge-main::-webkit-scrollbar,
.folder-main::-webkit-scrollbar,
.garden-main::-webkit-scrollbar,
.notification-main::-webkit-scrollbar,
.insights-full-main::-webkit-scrollbar,
.profile-main::-webkit-scrollbar,
.ai-main::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
.skills-main::-webkit-scrollbar-thumb,
.knowledge-main::-webkit-scrollbar-thumb,
.folder-main::-webkit-scrollbar-thumb,
.garden-main::-webkit-scrollbar-thumb,
.notification-main::-webkit-scrollbar-thumb,
.insights-full-main::-webkit-scrollbar-thumb,
.profile-main::-webkit-scrollbar-thumb,
.ai-main::-webkit-scrollbar-thumb {
  background: rgba(108,124,153,0.22);
  border-radius: 999px;
}
.skills-main::-webkit-scrollbar-thumb:hover,
.knowledge-main::-webkit-scrollbar-thumb:hover,
.folder-main::-webkit-scrollbar-thumb:hover,
.garden-main::-webkit-scrollbar-thumb:hover,
.notification-main::-webkit-scrollbar-thumb:hover,
.insights-full-main::-webkit-scrollbar-thumb:hover,
.profile-main::-webkit-scrollbar-thumb:hover,
.ai-main::-webkit-scrollbar-thumb:hover {
  background: rgba(91,120,255,0.45);
}

/* Skills chip + grid polish */
.skills-open .skill-grid {
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 18px;
}
.skills-open .skill-card {
  transition: transform 160ms ease, box-shadow 160ms ease;
}
.skills-open .skill-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 28px -10px rgba(91,120,255,0.28);
}
.skills-open .skill-chip {
  transition: background 140ms ease, color 140ms ease, transform 140ms ease;
}
.skills-open .skill-chip:hover {
  transform: translateY(-1px);
}
.skill-filter-empty-v18 {
  grid-column: 1 / -1;
  min-height: 150px;
  display: grid;
  place-items: center;
  padding: 24px;
  border: 1px dashed rgba(99,135,232,.24);
  border-radius: 16px;
  color: #6f7f98;
  background: rgba(255,255,255,.68);
  font-size: 13px;
  font-weight: 680;
}

/* §16.6 — Completed skill run badge on grid cards (notification + poll). */
.skill-card .skill-generated-chip {
  display: inline-flex;
  align-items: center;
  margin-top: 8px;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: #118a6c;
  background: rgba(112, 200, 170, 0.18);
  border: 1px solid rgba(17, 138, 108, 0.22);
}
.skill-card .skill-generated-chip[style*="cursor: pointer"]:hover {
  background: rgba(112, 200, 170, 0.28);
}

/* §15.43 citation chip polish (drawn by _renderCitationsForArticle) */
.ai-citation-chip:focus-visible {
  outline: 2px solid #5b78ff;
  outline-offset: 2px;
}

/* §15.47 — micro-animation on the AI thinking dots */
.ai-chat-message.is-thinking .thinking-dot {
  animation: mydow-thinking 1.05s infinite ease-in-out;
}
.ai-chat-message.is-thinking .thinking-dot:nth-child(2) { animation-delay: 0.18s; }
.ai-chat-message.is-thinking .thinking-dot:nth-child(3) { animation-delay: 0.36s; }
@keyframes mydow-thinking {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* §15.47 — Toast stack readability */
.toast-stack {
  z-index: 10000 !important;
}

/* §15.47 — Empty state hint inside KB / AI when no data */
.kb-empty-hint, .ai-empty-hint {
  display: flex; align-items: center; gap: 12px;
  padding: 24px 28px;
  background: linear-gradient(135deg, rgba(91,120,255,0.06), rgba(127,202,189,0.06));
  border-radius: 18px;
  color: #5a6b86;
  font-size: 14px;
}

/* §15.47 — focus ring for accessibility on every actionable element */
button:focus-visible,
a:focus-visible,
.notice-row:focus-visible,
.skill-card:focus-visible,
.idea-card:focus-visible {
  outline: 2px solid rgba(91,120,255,0.55);
  outline-offset: 3px;
  border-radius: 12px;
}

/* §15.47 — reduce-motion respect (a11y) */
@media (prefers-reduced-motion: reduce) {
  .ai-chat-message.is-thinking .thinking-dot { animation: none; }
  .skills-open .skill-card { transition: none; }
  .ai-citation-chip { transition: none !important; }
}

/* §17.2 — Favorite star "lit" state on KB folder cards.
 * The IIFE prototype only toggled a hidden ARIA attribute; users couldn't
 * see the favourite state. We light up the star with the brand accent +
 * fill the SVG so the visual matches the backend is_favorite flag. */
.star-action.active {
  color: #f5b700 !important;
  background: rgba(255, 200, 60, 0.16) !important;
}
.star-action.active svg {
  fill: #f5b700;
  stroke: #f5b700;
}
.star-action {
  transition: color 160ms ease, background 160ms ease, transform 200ms ease;
}
.star-action.active:hover {
  transform: scale(1.05);
}
.star-action svg {
  transition: fill 160ms ease, stroke 160ms ease;
}

/* §17.2 — KB tab pressed state visual */
[data-kb-tab][aria-pressed="true"],
[data-kb-tab].active {
  background: rgba(91, 120, 255, 0.12) !important;
  color: #5b78ff !important;
}

/* §17.5 — Skills personalised recommendation drawer */
.skill-rec-drawer {
  margin: 12px 0 18px;
  padding: 14px 18px;
  border: 1px solid rgba(91,120,255,0.18);
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(91,120,255,0.04), rgba(127,202,189,0.04));
}
.skill-rec-drawer summary {
  cursor: pointer;
  list-style: none;
  font-weight: 700;
  color: #1d2742;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.skill-rec-drawer summary::-webkit-details-marker { display: none; }
.skill-rec-drawer summary::before {
  content: "▶";
  font-size: 10px;
  color: #5b78ff;
  transition: transform 140ms ease;
}
.skill-rec-drawer[open] summary::before { transform: rotate(90deg); }
.skill-rec-drawer .rec-grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}
.skill-rec-drawer .rec-card {
  padding: 12px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid rgba(91,120,255,0.12);
  cursor: pointer;
  transition: transform 140ms ease, box-shadow 140ms ease;
}
.skill-rec-drawer .rec-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px -4px rgba(91,120,255,0.2);
}
.skill-rec-drawer .rec-card-title {
  font-weight: 700;
  color: #1d2742;
  font-size: 13px;
  margin-bottom: 4px;
}
.skill-rec-drawer .rec-card-reason {
  font-size: 11px;
  color: #6b7892;
}
.skill-rec-drawer .rec-empty {
  padding: 18px;
  color: #97a3b7;
  font-size: 12px;
}

/* §18.7 — Skills side rail must not clip recommendations/recent usage. */
.page.skills-open .content-grid {
  grid-template-columns: minmax(0, 1fr) minmax(260px, 280px) !important;
  gap: 24px !important;
  width: min(100%, calc(100vw - 316px)) !important;
  max-width: calc(100vw - 316px) !important;
  overflow: visible !important;
}
.page.skills-open .right-rail,
.page.skills-open .skills-drawer {
  min-width: 0 !important;
  width: min(280px, 100%) !important;
}
.page.skills-open .skills-main {
  min-width: 0 !important;
}
.page.skills-open .skills-drawer .insight-panel {
  overflow-y: auto !important;
  max-height: calc(100vh - 126px) !important;
  height: auto !important;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
  padding-right: 12px !important;
}
.page.skills-open .skills-drawer .insight-panel::-webkit-scrollbar {
  width: 7px;
}
.page.skills-open .skills-drawer .insight-panel::-webkit-scrollbar-thumb {
  background: rgba(108,124,153,.22);
  border-radius: 999px;
}
.skills-drawer .recommend-card {
  margin-bottom: 12px;
}
@media (max-width: 1180px) {
  .page.skills-open .content-grid {
    grid-template-columns: minmax(0, 1fr) !important;
    max-width: calc(100vw - 300px) !important;
  }
  .page.skills-open .right-rail {
    display: none !important;
  }
}
.skill-side-rec-list-v18 {
  margin: 12px 0 16px;
  border: 1px solid rgba(99,135,232,.15);
  border-radius: 15px;
  background: rgba(255,255,255,.72);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.8);
}
.skill-side-rec-list-v18 summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-height: 42px;
  padding: 10px 12px;
  cursor: pointer;
  color: #293650;
  font-size: 13px;
  font-weight: 780;
  list-style: none;
}
.skill-side-rec-list-v18 summary::-webkit-details-marker { display: none; }
.skill-side-rec-list-v18 summary::before {
  content: "▶";
  color: #6387e8;
  font-size: 10px;
  transition: transform .16s ease;
}
.skill-side-rec-list-v18[open] summary::before {
  transform: rotate(90deg);
}
.skill-side-rec-list-v18 summary span {
  flex: 1;
}
.skill-side-rec-list-v18 summary small {
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(99,135,232,.1);
  color: #6387e8;
  font-size: 11px;
  font-weight: 760;
}
.skill-side-rec-items-v18 {
  display: grid;
  gap: 8px;
  padding: 0 10px 10px;
}
.skill-side-rec-list-v18 .compact-row {
  display: grid;
  grid-template-columns: 28px minmax(0,1fr) auto;
  gap: 10px;
  align-items: center;
  min-height: 38px;
  padding: 7px 8px;
  border-radius: 11px;
  cursor: pointer;
  background: rgba(247,249,255,.78);
  transition: background .14s ease, transform .14s ease;
}
.skill-side-rec-list-v18 .compact-row:hover {
  transform: translateY(-1px);
  background: rgba(239,244,255,.96);
}
.skill-side-rec-list-v18 .compact-row strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #1d2742;
  font-size: 13px;
}
.skill-side-rec-list-v18 .compact-row > span:last-child {
  color: #7d8ba3;
  font-size: 11px;
  font-weight: 720;
}
.skills-drawer .section-label {
  clear: both;
}
`;
    document.head.appendChild(style);
  }

  // ============================================================================
  // §16.7 — 首页右栏 3 张 stat-card 真实数据 + click 跳真实详情
  // ============================================================================

  function _formatRelMonth(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const now = new Date();
    const ms = now - d;
    const min = Math.floor(ms / 60000);
    if (min < 1) return "刚刚";
    if (min < 60) return min + " 分钟前";
    const hr = Math.floor(min / 60);
    if (hr < 24) return hr + " 小时前";
    const day = Math.floor(hr / 24);
    if (day < 7) return day + " 天前";
    return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
  }

  /**
   * §16.7 (a) Hydrate the 3 home right-rail stat cards with real PRD10 data:
   *   - "今日新增灵感" → /today.stats.today_capture_count + week trend
   *   - "AI 周报总结"  → /ai/conversations + /reports activity heuristic
   *   - "本月灵感捕捉" → /feed?date_range=month total
   * Failures degrade silently to keep the prototype values visible.
   */
  async function refreshHomeRightRailStatCardsV14() {
    const stats = document.querySelectorAll(".right-rail .stats .stat-card");
    if (!stats.length) return null;

    const [todayResp, monthResp, aiResp] = await Promise.all([
      apiFetch("/today").catch(() => null),
      apiFetch("/feed?date_range=month&page_size=1").catch(() => null),
      apiFetch("/ai/conversations?page_size=20").catch(() => null),
    ]);

    const todayStats =
      (todayResp && todayResp.data && todayResp.data.stats) || {};
    const todayCount = Number(
      todayStats.today_capture_count != null
        ? todayStats.today_capture_count
        : todayStats.today_captures != null
          ? todayStats.today_captures
          : 0,
    );
    const weeklyGrowth = Number(todayStats.weekly_growth_rate || 0);

    const monthTotal = Number(
      (monthResp && monthResp.data && monthResp.data.pagination &&
        monthResp.data.pagination.total) || 0,
    );

    let totalMessages = 0;
    let convCount = 0;
    if (aiResp && aiResp.data && Array.isArray(aiResp.data.items)) {
      convCount = aiResp.data.items.length;
      for (const c of aiResp.data.items) {
        totalMessages += Number(c.message_count || 0);
      }
    }
    let aiTier = "中";
    if (weeklyGrowth >= 0.2 || totalMessages >= 10) aiTier = "高";
    else if (totalMessages === 0 && weeklyGrowth < 0) aiTier = "低";
    const aiNote =
      totalMessages > 0
        ? "帮助你梳理了 " + totalMessages + " 条对话消息"
        : convCount > 0
          ? "已开始 " + convCount + " 个对话"
          : "记录第一条想法即可开启";

    const trendNote = (() => {
      if (weeklyGrowth > 0.001) return "较上周\u00a0\u00a0+" + Math.round(weeklyGrowth * 100) + "%";
      if (weeklyGrowth < -0.001) return "较上周\u00a0\u00a0" + Math.round(weeklyGrowth * 100) + "%";
      return todayCount > 0 ? "今日仍在记录中" : "记录第一条灵感";
    })();

    const SLOTS = {
      "今日新增灵感": {
        value: String(todayCount),
        note: trendNote,
        action: "today_feed",
      },
      "AI 周报总结": {
        value: aiTier,
        note: aiNote,
        action: "weekly_report",
      },
      "本月灵感捕捉": {
        value: String(monthTotal),
        note: monthTotal === 0 ? "本月暂无灵感" : "本月共 " + monthTotal + " 条",
        action: "month_feed",
      },
    };

    stats.forEach((card) => {
      const h3 = card.querySelector("h3");
      if (!h3) return;
      const heading = (h3.textContent || "").trim();
      const slot = SLOTS[heading];
      if (!slot) return;
      const sv = card.querySelector(".stat-value");
      if (sv) sv.textContent = slot.value;
      const note = card.querySelector(".stat-note");
      if (note) note.textContent = slot.note;
      card.dataset.statAction = slot.action;
      card.dataset.statHydrated = "1";
    });

    return { todayCount, monthTotal, totalMessages, aiTier };
  }

  /**
   * §16.7 (b) Build a feed list overlay for "今日新增灵感" / "本月灵感捕捉" cards.
   * Renders the actual /feed?date_range=... items in a dynamically-injected
   * dialog so users can click into individual idea cards.
   */
  function _ensureFeedListOverlay() {
    let overlay = document.querySelector("[data-v14-feed-list-overlay]");
    if (overlay) return overlay;
    overlay = document.createElement("div");
    overlay.setAttribute("data-v14-feed-list-overlay", "1");
    overlay.className = "v14-feed-overlay";
    overlay.style.cssText =
      "position:fixed;inset:0;background:rgba(15,23,42,0.42);z-index:99999;" +
      "display:flex;align-items:center;justify-content:center;padding:32px;" +
      "pointer-events:auto;opacity:1;visibility:visible;";
    overlay.innerHTML =
      '<aside class="detail-drawer wide" role="dialog" aria-modal="true" aria-label="灵感记录列表" ' +
      'style="position:relative;max-width:680px;width:100%;max-height:80vh;overflow-y:auto;background:#fff;' +
      'border-radius:18px;box-shadow:0 20px 50px rgba(15,23,42,0.18);padding:24px 28px;pointer-events:auto;z-index:1;">' +
      '  <div class="drawer-head" style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px;">' +
      '    <div><h2 data-v14-feed-list-title style="font-size:20px;margin:0 0 6px;">灵感列表</h2>' +
      '      <p data-v14-feed-list-meta style="margin:0;color:#718098;font-size:13px;">…</p></div>' +
      '    <button class="modal-close" type="button" data-v14-feed-list-close ' +
      'style="background:none;border:0;font-size:24px;color:#718098;cursor:pointer;padding:4px 12px;line-height:1;pointer-events:auto;">×</button>' +
      '  </div>' +
      '  <div data-v14-feed-list-body><div style="padding:32px 0;text-align:center;color:#718098;">正在加载…</div></div>' +
      '</aside>';
    document.body.appendChild(overlay);
    overlay.style.display = "none";
    overlay.addEventListener("click", (ev) => {
      if (ev.target === overlay) _hideFeedListOverlay();
    });
    overlay.querySelector("[data-v14-feed-list-close]").addEventListener(
      "click",
      () => _hideFeedListOverlay(),
    );
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") {
        const o = document.querySelector("[data-v14-feed-list-overlay]");
        if (o && o.style.display !== "none") _hideFeedListOverlay();
      }
    });
    return overlay;
  }

  function _hideFeedListOverlay() {
    const overlay = document.querySelector("[data-v14-feed-list-overlay]");
    if (!overlay) return;
    overlay.style.display = "none";
  }

  async function _showFeedListV14(range, headerTitle) {
    const overlay = _ensureFeedListOverlay();
    overlay.style.display = "flex";
    overlay.querySelector("[data-v14-feed-list-title]").textContent = headerTitle;
    overlay.querySelector("[data-v14-feed-list-meta]").textContent = "正在加载…";
    const body = overlay.querySelector("[data-v14-feed-list-body]");
    body.innerHTML = '<div style="padding:32px 0;text-align:center;color:#718098;">正在加载…</div>';
    try {
      const r = await apiFetch("/feed?date_range=" + encodeURIComponent(range) + "&page_size=30");
      const data = unwrapData(r) || {};
      const items = data.items || [];
      const total = (data.pagination && data.pagination.total) || items.length;
      overlay.querySelector("[data-v14-feed-list-meta]").textContent =
        "区间内共 " + total + " 条记录" + (range === "today" ? " · 今日" : range === "month" ? " · 本月" : "");
      if (!items.length) {
        body.innerHTML =
          '<div style="padding:48px 0;text-align:center;color:#718098;">' +
          '<div style="font-size:48px;margin-bottom:12px;">🌱</div>' +
          '<div style="font-size:15px;margin-bottom:6px;">该区间内暂无灵感记录</div>' +
          '<div style="font-size:13px;color:#9aaac0;">在首页输入区写下你的第一条想法</div>' +
          '</div>';
        return;
      }
      const rows = items.map((it) => {
        const title = escapeHtmlV14(it.title || "未命名");
        const summary = escapeHtmlV14((it.summary || it.content || "").slice(0, 140));
        const time = _formatRelMonth(it.updated_at || it.created_at);
        const tags = (it.tags || [])
          .slice(0, 4)
          .map((t) => '<span class="tag" style="background:rgba(91,120,255,0.08);color:#5b78ff;padding:2px 8px;border-radius:8px;font-size:11px;margin-right:4px;">' + escapeHtmlV14(t) + "</span>")
          .join("");
        const ctype = it.content_type ? '<span style="color:#9aaac0;font-size:11px;margin-left:6px;">· ' + escapeHtmlV14(it.content_type) + "</span>" : "";
        return (
          '<article class="quick-setting" data-v14-feed-item-id="' + escapeHtmlV14(it.id || "") + '" ' +
          'style="display:flex;flex-direction:column;gap:6px;padding:14px 16px;border:1px solid rgba(15,23,42,0.06);border-radius:14px;margin-bottom:10px;cursor:pointer;transition:background 120ms ease;" ' +
          'onmouseover="this.style.background=\'rgba(91,120,255,0.04)\'" onmouseout="this.style.background=\'transparent\'">' +
          '<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">' +
          '<strong style="font-size:14px;color:#1d2742;">' + title + ctype + "</strong>" +
          '<span style="color:#9aaac0;font-size:11px;flex-shrink:0;">' + escapeHtmlV14(time) + "</span></div>" +
          '<p style="margin:0;color:#5a6b86;font-size:13px;line-height:1.5;">' + summary + "</p>" +
          (tags ? '<div style="margin-top:4px;">' + tags + "</div>" : "") +
          "</article>"
        );
      });
      body.innerHTML = rows.join("");
      body.querySelectorAll("[data-v14-feed-item-id]").forEach((row) => {
        row.addEventListener("click", () => {
          const cardId = row.getAttribute("data-v14-feed-item-id");
          if (!cardId) return;
          _hideFeedListOverlay();
          if (window.MydowBridgeV14Ext && typeof window.MydowBridgeV14Ext.openCardDrawer === "function") {
            window.MydowBridgeV14Ext.openCardDrawer(cardId);
          } else {
            const itemDrawer = document.querySelector('[data-drawer="itemDetail"]');
            if (itemDrawer) {
              itemDrawer.hidden = false;
              const heading = itemDrawer.querySelector(".drawer-head h2");
              if (heading) heading.textContent = row.querySelector("strong").firstChild.textContent.trim();
            }
          }
        });
      });
    } catch (e) {
      body.innerHTML =
        '<div style="padding:32px 0;text-align:center;color:#c2360c;">' +
        '加载失败：' + escapeHtmlV14(String(e && e.message || e || "未知错误")) + "</div>";
    }
  }

  async function _showAiWeeklyReportV14() {
    const overlay = _ensureFeedListOverlay();
    overlay.style.display = "flex";
    overlay.querySelector("[data-v14-feed-list-title]").textContent = "AI 周报总结";
    overlay.querySelector("[data-v14-feed-list-meta]").textContent = "AI 正在生成你的本周周报…";
    const body = overlay.querySelector("[data-v14-feed-list-body]");
    body.innerHTML =
      '<div style="padding:32px 0;text-align:center;color:#5b78ff;">' +
      '<div style="font-size:32px;margin-bottom:12px;">📊</div>' +
      '<div style="font-size:14px;">AI 正在分析你本周的灵感与对话…</div></div>';
    try {
      const gen = await apiFetch("/reports/generate", {
        method: "POST",
        body: { report_type: "weekly", include_sources: true },
      });
      const genData = unwrapData(gen) || {};
      const reportId = genData.report_id;
      if (!reportId) throw new Error("缺少 report_id");
      const detail = await apiFetch("/reports/" + encodeURIComponent(reportId));
      const dd = unwrapData(detail) || {};
      const reportInfo = dd.report || {};
      const stats = reportInfo.stats || {};
      const themes = reportInfo.themes || [];
      const usedLlm = (dd.extra || {}).used_llm === true || (reportInfo || {}).used_llm === true;
      const model = (dd.extra || {}).model || "";
      overlay.querySelector("[data-v14-feed-list-meta]").textContent =
        (usedLlm ? "AI 真实生成" + (model ? " · " + model : "") : "已聚合统计") +
        " · " + (dd.created_at ? new Date(dd.created_at).toLocaleString("zh-CN") : "");
      const bodyText = dd.body || dd.content || "";
      const bodyHtml = bodyText
        .split(/\n+/)
        .map((line) => {
          const trimmed = line.trim();
          if (!trimmed) return "";
          if (trimmed.startsWith("## ")) {
            return '<h3 style="margin:18px 0 8px;font-size:15px;color:#1d2742;">' + escapeHtmlV14(trimmed.slice(3)) + "</h3>";
          }
          if (trimmed.startsWith("# ")) {
            return '<h2 style="margin:0 0 12px;font-size:18px;color:#1d2742;">' + escapeHtmlV14(trimmed.slice(2)) + "</h2>";
          }
          if (trimmed.startsWith("- ")) {
            return '<div style="padding:4px 0 4px 14px;color:#3b495d;font-size:13px;">• ' + escapeHtmlV14(trimmed.slice(2)) + "</div>";
          }
          return '<p style="margin:6px 0;color:#3b495d;font-size:13px;line-height:1.6;">' + escapeHtmlV14(trimmed) + "</p>";
        })
        .join("");
      const themesHtml = themes.length
        ? '<div style="margin-top:18px;padding:12px 14px;background:rgba(91,120,255,0.04);border-radius:12px;">' +
          '<strong style="font-size:13px;color:#5b78ff;">高频主题</strong>' +
          themes.slice(0, 6).map((t) =>
            '<div style="display:flex;justify-content:space-between;padding:4px 0;font-size:12px;color:#3b495d;">' +
            '<span>' + escapeHtmlV14(t.name) + "</span>" +
            '<span style="color:#9aaac0;">' + Number(t.value || 0) + "</span></div>",
          ).join("") + "</div>"
        : "";
      const statsBlock =
        '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:18px;">' +
        '<div style="padding:10px 12px;background:rgba(91,120,255,0.06);border-radius:10px;text-align:center;">' +
        '<div style="font-size:18px;font-weight:700;color:#1d2742;">' + Number(stats.capture_count || 0) + "</div>" +
        '<div style="font-size:11px;color:#718098;">灵感记录</div></div>' +
        '<div style="padding:10px 12px;background:rgba(127,202,189,0.10);border-radius:10px;text-align:center;">' +
        '<div style="font-size:18px;font-weight:700;color:#1d2742;">' + Number(stats.knowledge_count || 0) + "</div>" +
        '<div style="font-size:11px;color:#718098;">知识库文档</div></div>' +
        '<div style="padding:10px 12px;background:rgba(245,183,0,0.10);border-radius:10px;text-align:center;">' +
        '<div style="font-size:18px;font-weight:700;color:#1d2742;">' + Number(stats.task_count || 0) + "</div>" +
        '<div style="font-size:11px;color:#718098;">任务/待办</div></div></div>';
      body.innerHTML = statsBlock + bodyHtml + themesHtml;
      toast(usedLlm ? "AI 周报已生成" : "周报已聚合", "success");
    } catch (e) {
      body.innerHTML =
        '<div style="padding:32px 0;text-align:center;color:#c2360c;">' +
        '生成失败：' + escapeHtmlV14(String(e && e.message || e || "未知错误")) + "</div>";
    }
  }

  /** §16.7 (c) Capture-phase click handler that overrides the prototype's
   * data-open-drawer="itemDetail/insightDetail" behaviour so the 3 home
   * stat-cards open real listings/reports instead of the static drawer. */
  function bindHomeStatCardClicksV14() {
    document.addEventListener(
      "click",
      (ev) => {
        const card = ev.target.closest(".right-rail .stats .stat-card");
        if (!card) return;
        const action = card.dataset.statAction;
        if (!action) return;
        ev.preventDefault();
        ev.stopPropagation();
        if (action === "today_feed") {
          _showFeedListV14("today", "今日新增灵感").catch(() => {});
        } else if (action === "month_feed") {
          _showFeedListV14("month", "本月灵感捕捉").catch(() => {});
        } else if (action === "weekly_report") {
          _showAiWeeklyReportV14().catch(() => {});
        }
      },
      true,
    );
    document.addEventListener(
      "keydown",
      (ev) => {
        if (ev.key !== "Enter" && ev.key !== " ") return;
        const card = ev.target.closest && ev.target.closest(".right-rail .stats .stat-card");
        if (!card || !card.dataset.statAction) return;
        ev.preventDefault();
        card.click();
      },
      true,
    );
  }

  // ─── boot ─────────────────────────────────────────────────────────────────
  async function boot() {
    const ok = await ensureSession();
    if (!ok) {
      console.warn("[Mydow v1.4] session failed; prototype simulateAction only");
      return;
    }

    injectAiComposerLayoutFixV18();
    bindCaptureSubmit();
    bindModalSubmitsCapture();
    bindCreateDocCapture();
    bindCardClickToDrawer();
    bindCardFavoriteAction();
    bindSkillRunModalContext();
    bindVoiceInputModalV18();
    bindNoticeFilterCapture();
    bindNoticeQuickCapture();
    bindNoticeRowMarkRead();
    bindKbTabCapture();
    bindKbStarActionFavoriteV17();
    bindRecommendCardClickV17();
    bindAiAddMenuExtrasV17();
    attachGardenInlineMenuV17();
    bindSkillCardStash();
    bindSkillDetailRunHistoryV17();
    bindSkillsCategoryFilterV40();
    bindSkillsPageHydration();
    openSkillsFromHashV18();
    bindAiThreadHydrate();
    bindAiComposerCapture();
    bindAiConvIdWatcher();
    bindGlobalSearch();
    bindHomeFeedViewTabs();
    listenForFeedRefreshV14();
    attachInsightsFullHandlersV14();
    attachGardenTopicSearchV14();
    attachGardenControlHandlersV14();

    // §15.38 — assistant message action buttons + logout
    bindAssistantActionButtonsV14();
    bindCustomInsightSubmit();
    bindLogoutAction();

    // §15.37 — Comprehensive button wiring (rev2)
    bindNoticeActionV37();
    bindAiThreadMenuV37();
    bindAiChatRenameV37();
    bindAiChatMoreV37();
    trackAiModelV37();
    bindAiPersonalizeModernControlsV18();
    bindCardShareV37();
    bindFolderFavoriteV37();
    bindSkillFavoriteV37();
    bindDocEditorHydrateAndAutosaveV18();
    bindDocAiActionsV37();
    bindInsightActionsV37();
    _restoreAiModelV37();
    // §15.40 — Skill run result drawer (close + open-doc)
    bindSkillResultDrawerCloseV14();

    // §15.39 — remaining 25 unhandled v1.4 toasts (theme / prefs /
    // confirmDelete / move panel / billing / security / etc.)
    bindAllRemainingV39();

    // §15.42 — a11y critical fixes (aria-selected on button / role=button on article)
    applyA11yFixesV14();

    // §15.44 / §15.47 — Layout fix (max-height) + investor visual polish.
    injectInvestorPolishCss();

    // §16.7 — Home right-rail 3 stat-cards: real data + real click navigation.
    bindHomeStatCardClicksV14();

    const me = await refreshProfileChip();
    if (!me) {
      setToken("");
      return;
    }

    await Promise.allSettled([
      loadKbLibraryGrid(),
      loadAiConversations(),
      loadNotifications(),
      refreshNotificationBadge(),
      loadFeedCards(),
      loadFeedIntoRecordsTable(),
      loadSkillsGrid(),
      loadSkillRecommendationsV17(),
      refreshGardenBoard(),
      refreshInsightsFullV14(),
      refreshHomeRightRailStatCardsV14(),
    ]);
    toast("已连接 PRD10 后端 · v1.4 bridge 扩展已加载", "success");
  }

  window[FLAG_KEY] = true;
  window.MydowBridgeV14 = {
    apiFetch,
    apiFetchV14,
    unwrapData,
    toV14ContractEnvelope,
    toast,
    getToken,
    setToken,
    ensureSession,
    refreshProfileChip,
    loadKbLibraryGrid,
    bindAiConvIdWatcher,
    loadAiConversations,
    loadNotifications,
    refreshNotificationBadge,
    loadFeedCards,
    loadFeedIntoRecordsTable,
    loadSkillsGrid,
    refreshGardenBoard,
    refreshInsightsFullV14,
    attachGardenTopicSearchV14,
    attachGardenControlHandlersV14,
    attachGardenInlineMenuV17,
    openGardenNodeDetailV17,
    openKbDocumentEditorV20,
    saveAiConversationToKbV20,
    loadSkillRecommendationsV17,
    navigateToSearchHitV17,
    loadActiveConversationContextScope,
    bindAssistantActionButtonsV14,
    bindCustomInsightSubmit,
    bindLogoutAction,
    applyA11yFixesV14,
    injectInvestorPolishCss,
    // §15.37 exports
    bindNoticeActionV37,
    bindAiThreadMenuV37,
    bindAiChatRenameV37,
    bindAiChatMoreV37,
    bindCardShareV37,
    bindFolderFavoriteV37,
    bindKbStarActionFavoriteV17,
    bindRecommendCardClickV17,
    bindAiAddMenuExtrasV17,
    bindSkillFavoriteV37,
    bindDocAiActionsV37,
    bindInsightActionsV37,
    // §15.39 exports
    bindConfirmDeleteV39,
    bindMovePanelV39,
    bindThemeToggleV39,
    bindPrefToggleV39,
    bindPasswordModalV39,
    bindBillingV39,
    bindEmailVerifyV39,
    bindPermissionsV39,
    bindStorageRefreshV39,
    bindSecurityDevicesV39,
    bindAiContextAddV39,
    bindAiContextDrawerHydrateV14,
    _renderCitationsForArticle,
    bindDuplicateFolderV39,
    bindVoicePauseV39,
    bindAllRemainingV39,
    applyTheme: _applyTheme,
    state: V14,
    booted: false,
    refreshHomeRightRailStatCardsV14,
    bindHomeStatCardClicksV14,
    showFeedListV14: _showFeedListV14,
    showAiWeeklyReportV14: _showAiWeeklyReportV14,
  };

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      () => {
        boot().then(() => {
          window.MydowBridgeV14.booted = true;
        });
      },
      { once: true },
    );
  } else {
    boot().then(() => {
      window.MydowBridgeV14.booted = true;
    });
  }
})();

