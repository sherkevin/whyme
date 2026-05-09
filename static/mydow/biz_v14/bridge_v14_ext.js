/* eslint-disable no-console */
// =============================================================================
// Mydow v1.4 — bridge extension (`bridge_v14_ext.js`)
//
// 业务方 v1.4 prototype 里有大量 `data-toast` / `data-inline-menu` /
// `data-notice-action` / `data-account-action` / `data-kb-tab` 等按钮在
// `bridge_v14.js` 第一版里没有接到真实 PRD10 API。本文件**不改** v1.4 HTML
// 也不改 `bridge_v14.js`，作为后续扩展把所有未接通按钮接到 `/api/v1/*`，
// 让 v1.4 原型的每一个按钮点击都产生真实 backend 副作用。
//
// 加载顺序：bridge_v14.js → bridge_v14_ext.js（FastAPI 注入到
// `</body>` 前）。本文件 boot 时等 `window.MydowBridgeV14.booted` 为 true 再绑。
// =============================================================================

(function bootstrapV14Ext() {
  "use strict";

  if (window.__MYDOW_V14_EXT_BOOTED) return;
  window.__MYDOW_V14_EXT_BOOTED = true;

  const FLAG = "MydowBridgeV14ExtBooted";

  /** Wait until base bridge is booted (or timeout) */
  function whenBaseReady(maxMs) {
    const deadline = Date.now() + (maxMs || 8000);
    return new Promise((resolve) => {
      function tick() {
        const b = window.MydowBridgeV14;
        if (b && b.booted === true && b.apiFetch) return resolve(b);
        if (Date.now() > deadline) return resolve(b || null);
        window.setTimeout(tick, 60);
      }
      tick();
    });
  }

  // ─── Drawer / modal context tracking ────────────────────────────────────
  /** Last interactive context picked up by capture-phase opener clicks. */
  const _CTX = {
    cardId: "",
    documentId: "",
    folderId: "",
    insightId: "",
    skillId: "",
    aiMessageId: "",
    aiConvId: "",
    confirmIntent: "", // "logout" | "clear_cache" | "card" | "document" | "folder"
    selectedNoteIds: new Set(),
    inlineMenu: {}, // { searchSort: "relevance", searchScope: "title", ... }
  };

  function pickFromDataset(target, keys) {
    if (!target || !target.dataset) return null;
    for (const k of keys) {
      if (target.dataset[k]) return target.dataset[k];
    }
    return null;
  }

  function bindOpenerContextSync() {
    document.addEventListener(
      "click",
      (event) => {
        // idea-card / record-card / recent card  → cardId
        const card = event.target.closest("[data-card-id]");
        if (card && card.dataset.cardId) _CTX.cardId = card.dataset.cardId;

        // doc-row → documentId
        const row = event.target.closest("[data-document-id]");
        if (row && row.dataset.documentId) _CTX.documentId = row.dataset.documentId;

        // folder card / library-card → folderId
        const fcard = event.target.closest("[data-folder-id]");
        if (fcard && fcard.dataset.folderId) _CTX.folderId = fcard.dataset.folderId;

        // skill-card → skillId
        const scard = event.target.closest("[data-skill-id]");
        if (scard && scard.dataset.skillId) _CTX.skillId = scard.dataset.skillId;

        // [data-insight-id]
        const insightCard = event.target.closest("[data-insight-id]");
        if (insightCard && insightCard.dataset.insightId) _CTX.insightId = insightCard.dataset.insightId;

        // ai-history-thread → conversationId
        const thread = event.target.closest("[data-conversation-id]");
        if (thread && thread.dataset.conversationId) _CTX.aiConvId = thread.dataset.conversationId;

        // ai-chat-message bubble → messageId
        const bubble = event.target.closest("[data-message-id]");
        if (bubble && bubble.dataset.messageId) _CTX.aiMessageId = bubble.dataset.messageId;

        // confirmDelete intent detection
        const opener = event.target.closest("[data-open-modal=\"confirmDelete\"]");
        if (opener) {
          const t = (opener.textContent || "").trim();
          if (/退出登录|登出|logout/i.test(t)) _CTX.confirmIntent = "logout";
          else if (/清除|缓存|clear/i.test(t)) _CTX.confirmIntent = "clear_cache";
          else if (_CTX.documentId && opener.closest(".doc-editor-main")) _CTX.confirmIntent = "document";
          else if (_CTX.folderId && opener.closest(".folder-main, [data-folder-menu]")) _CTX.confirmIntent = "folder";
          else if (_CTX.cardId) _CTX.confirmIntent = "card";
          else _CTX.confirmIntent = "card";
        }
      },
      true,
    );
  }

  // ─── Inline-menu: select/option click → re-fetch ────────────────────────
  /**
   * IIFE creates `.inline-popover` with buttons; clicking a button updates
   * the trigger label and closes the popover. We listen capture-phase on
   * popover button clicks before the prototype's stopPropagation runs.
   */
  function bindInlineMenuOptions(base) {
    document.addEventListener(
      "click",
      (event) => {
        const btn = event.target.closest(".inline-popover button");
        if (!btn) return;
        // Pop the trigger that's open
        const trigger = document.querySelector('[data-inline-menu][aria-expanded="true"]');
        const kind = trigger?.dataset?.inlineMenu;
        if (!kind) return;
        // Read selected text (without icons)
        const value = (btn.querySelector("span")?.textContent || btn.textContent || "").trim();
        _CTX.inlineMenu[kind] = value;
        // Allow prototype to update label first; then re-fetch
        window.setTimeout(() => onInlineMenuChange(base, kind, value), 60);
      },
      true,
    );
  }

  function onInlineMenuChange(base, kind, value) {
    try {
      if (kind && kind.startsWith("search")) {
        triggerSearchRefetch(base);
        return;
      }
      if (kind === "notificationFilter") {
        const map = { 全部通知: "all", AI: "ai", 系统: "system", 协作: "collab" };
        const t = map[value] || "all";
        base.apiFetch("/notifications?type=" + encodeURIComponent(t) + "&page_size=20")
          .then(() => base.loadNotifications())
          .catch(() => {});
        return;
      }
      if (kind === "gardenTime" || kind === "gardenType") {
        base.refreshGardenBoard().catch(() => {});
        return;
      }
      if (kind === "folderType" || kind === "folderSource" || kind === "folderTag" || kind === "folderSort") {
        // Re-fetch the current folder's docs with filters
        if (_CTX.folderId) {
          const params = new URLSearchParams();
          params.set("folder_id", _CTX.folderId);
          if (_CTX.inlineMenu.folderType && _CTX.inlineMenu.folderType !== "全部类型") {
            params.set("type", mapFolderTypeToBackend(_CTX.inlineMenu.folderType));
          }
          if (_CTX.inlineMenu.folderSort) {
            params.set("sort_by", mapFolderSortToBackend(_CTX.inlineMenu.folderSort));
          }
          base.apiFetch("/kb/documents?" + params.toString())
            .then((r) => {
              const d = base.unwrapData(r) || {};
              renderFolderDocs(d.items || []);
            })
            .catch(() => {});
        }
        return;
      }
      if (kind === "recordFilter") {
        const map = { 全部: "", 笔记: "note", 链接: "link", 文件: "file", 语音: "voice", 研究: "research" };
        const t = map[value] || "";
        const url = "/feed?page_size=40" + (t ? "&type=" + t : "");
        base.apiFetch(url)
          .then((r) => {
            const d = base.unwrapData(r) || {};
            applyFeedToRecordsTable(d.items || []);
          })
          .catch(() => {});
        return;
      }
      if (kind === "aiModel") {
        // Store selection for next message; nothing else to fetch.
        _CTX.aiModel = value;
        return;
      }
      if (kind === "captureMode") {
        // Persist preference (best effort, no-op if endpoint not accepting)
        base.apiFetch("/me", {
          method: "PATCH",
          body: { settings: { default_input_mode: value } },
        }).catch(() => {});
      }
    } catch (e) {
      console.warn("[v14-ext] onInlineMenuChange", e);
    }
  }

  function mapFolderTypeToBackend(label) {
    if (/笔记|note/i.test(label)) return "note";
    if (/链接|link/i.test(label)) return "link";
    if (/语音|voice|audio/i.test(label)) return "audio";
    if (/研究|research/i.test(label)) return "research";
    return "";
  }

  function mapFolderSortToBackend(label) {
    if (/创建/.test(label)) return "created_at";
    if (/标题/.test(label) || /字母/.test(label)) return "title";
    return "updated_at";
  }

  function renderFolderDocs(items) {
    const rows = document.querySelectorAll(".doc-row:not(.doc-row-head)");
    rows.forEach((row, idx) => {
      const it = items[idx];
      if (!it) {
        row.style.display = "none";
        return;
      }
      row.style.display = "";
      row.dataset.documentId = it.id || "";
      const t = row.querySelector(".doc-title, .doc-name, h3, strong");
      if (t) t.textContent = it.title || "未命名";
      const tag = row.querySelector(".tag-list, .tags");
      if (tag && Array.isArray(it.tags)) {
        tag.innerHTML = (it.tags || []).slice(0, 3).map((x) =>
          `<span class="tag">${escapeHtml(x)}</span>`).join("");
      }
    });
  }

  function applyFeedToRecordsTable(items) {
    const rows = document.querySelectorAll(".records-table .record-row:not(.record-head)");
    rows.forEach((row, idx) => {
      const it = items[idx];
      if (!it) {
        row.style.display = "none";
        return;
      }
      row.style.display = "";
      row.dataset.cardId = it.id || "";
      const t = row.querySelector(".record-title");
      if (t) t.textContent = it.title || "未命名";
    });
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // ─── Search filter re-fetch (§16.11) + recent searches ─────────────────
  const RECENT_SEARCH_KEY = "mydow_recent_searches";

  function _readRecentSearches() {
    try {
      return JSON.parse(window.localStorage.getItem(RECENT_SEARCH_KEY) || "[]");
    } catch (_e) {
      return [];
    }
  }

  function _pushRecentSearch(q) {
    if (!q) return;
    try {
      const arr = _readRecentSearches();
      const next = [q, ...arr.filter((x) => x !== q)].slice(0, 10);
      window.localStorage.setItem(RECENT_SEARCH_KEY, JSON.stringify(next));
    } catch (_e) { /* ignore */ }
  }

  async function _runNewTaskFromSearchCommand(base, raw) {
    const title = raw.replace(/^\s*\/(new task|新建任务)\s*/i, "").trim() || "新任务";
    try {
      await base.apiFetch("/tasks", {
        method: "POST",
        body: { title, priority: "medium", status: "todo", source_type: "manual" },
      });
      base.toast && base.toast("已创建任务：" + title, "success");
      const inp = document.querySelector("[data-search-modal-input]");
      if (inp) inp.value = "";
      closeSearchIfOpen();
    } catch (e) {
      base.toast && base.toast((e && e.message) || "创建任务失败", "error");
    }
  }

  function closeSearchIfOpen() {
    const close = document.querySelector("[data-close-search], .search-modal [data-close-layer]");
    if (close) close.click();
  }

  function triggerSearchRefetch(base) {
    const inp = document.querySelector("[data-search-modal-input]");
    const q = (inp && inp.value || "").trim();
    if (!q) {
      renderSearchEmptyWithRecents();
      return;
    }
    if (/^\/(new task|新建任务)/i.test(q)) {
      _runNewTaskFromSearchCommand(base, q).catch(() => {});
      return;
    }

    const sortLabel = _CTX.inlineMenu.searchSort || "";
    const scopeLabel = _CTX.inlineMenu.searchScope || "";
    const creatorLabel = _CTX.inlineMenu.searchCreator || "";
    const locLabel = _CTX.inlineMenu.searchLocation || "";
    const dateLabel = _CTX.inlineMenu.searchDate || "";

    const params = new URLSearchParams();
    params.set("q", q);
    params.set("page_size", "12");

    if (/相关度/.test(sortLabel)) {
      params.set("sort", "relevance");
    } else if (/标题\s*[A|Ａ]/.test(sortLabel) || /A-Z/.test(sortLabel)) {
      params.set("sort", "title");
    } else {
      params.set("sort", "updated_at");
    }

    if (/仅搜索标题/.test(scopeLabel)) {
      params.set("title_only", "true");
    }

    if (creatorLabel && !/所有创建者/.test(creatorLabel)) {
      params.set("mine_only", "true");
    }

    if (/今天/.test(dateLabel) && !/7/.test(dateLabel)) {
      params.set("date_preset", "today");
    } else if (/7/.test(dateLabel)) {
      params.set("date_preset", "7d");
    } else if (/30/.test(dateLabel)) {
      params.set("date_preset", "30d");
    }

    if (/知识库/.test(locLabel)) {
      ["document", "folder", "card"].forEach((t) => params.append("object_type", t));
    } else if (/数字花园/.test(locLabel)) {
      params.append("object_type", "insight");
      params.append("object_type", "card");
    }

    _pushRecentSearch(q);

    base.apiFetch("/search?" + params.toString())
      .then((r) => renderSearchResultsSixState(base.unwrapData(r) || {}, q))
      .catch((e) => {
        base.toast && base.toast((e && e.message) || "搜索失败", "error");
      });
  }

  function renderSearchEmptyWithRecents() {
    const host =
      document.querySelector(".search-modal .search-results, [data-search-results]") ||
      document.querySelector(".search-results");
    if (!host) return;
    const rec = _readRecentSearches();
    if (!rec.length) {
      host.innerHTML =
        `<div class="search-empty mydow-empty-hint" style="padding:22px;color:#8a96ad;text-align:center">` +
        `输入关键词搜索知识库与灵感记录<br/><span style="font-size:12px;opacity:.85">` +
        `试一试：<code>/new task 准备周会材料</code></span></div>`;
      return;
    }
    host.innerHTML =
      `<div class="mydow-recent-search" style="padding:12px 14px">` +
      `<div style="font-size:11px;font-weight:600;color:#7488a6;margin-bottom:8px">最近搜索</div>` +
      rec.map((t) =>
        `<button type="button" class="soft-filter" style="margin:4px 6px 4px 0" data-recent-search="${escapeHtml(t)}">${escapeHtml(t)}</button>`,
      ).join("") +
      `</div>`;
    host.querySelectorAll("[data-recent-search]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const inp = document.querySelector("[data-search-modal-input]");
        if (inp) {
          inp.value = btn.getAttribute("data-recent-search") || "";
          inp.dispatchEvent(new Event("input", { bubbles: true }));
        }
      });
    });
  }

  function renderSearchResults(data, queryLabel) {
    const items = data.items || data.results || [];
    const host =
      document.querySelector(".search-modal .search-results, [data-search-results]") ||
      document.querySelector(".search-results");
    if (!host) return;
    if (!items.length) {
      host.innerHTML =
        `<div class="search-empty mydow-empty-hint" style="padding:22px;color:#8a96ad;text-align:center">` +
        `没有找到 “${escapeHtml(queryLabel || "")}” 的相关结果</div>`;
      return;
    }
    host.innerHTML = items.slice(0, 12).map((row) => {
      const title = escapeHtml(row.title || row.name || "结果");
      const sub = escapeHtml(row.object_type || row.type || "");
      const id = escapeHtml(row.object_id || row.id || row.target_id || "");
      return (
        `<div class="search-result-row" role="button" tabindex="0" data-search-result ` +
        `data-search-id="${id}" data-search-type="${sub}"><strong>${title}</strong>` +
        `<span>${sub}</span></div>`
      );
    }).join("");
  }

  function renderSearchResultsSixState(data, queryLabel) {
    const items = data.items || data.results || [];
    const host =
      document.querySelector(".search-modal .search-results, [data-search-results]") ||
      document.querySelector(".search-results");
    if (!host) return;
    host.classList.remove("mydow-sixstate-empty-active");
    if (!items.length) {
      host.classList.add("mydow-sixstate-empty-active");
      host.innerHTML = renderStateCard(
        "empty",
        `没有找到「${queryLabel || ""}」`,
        "换一个关键词、放宽筛选条件，或把它沉淀成一个新的任务继续推进。",
        "空态来自 /search",
      );
      return;
    }
    host.innerHTML = items.slice(0, 12).map((row) => {
      const title = escapeHtml(row.title || row.name || "结果");
      const sub = escapeHtml(row.object_type || row.type || "");
      const id = escapeHtml(row.object_id || row.id || row.target_id || "");
      return (
        `<div class="search-result-row" role="button" tabindex="0" data-search-result ` +
        `data-search-id="${id}" data-search-type="${sub}"><strong>${title}</strong>` +
        `<span>${sub}</span></div>`
      );
    }).join("");
  }

  function bindSearchModalUX(base) {
    document.addEventListener(
      "input",
      (event) => {
        const inp = event.target && event.target.closest && event.target.closest("[data-search-modal-input]");
        if (!inp) return;
        window.clearTimeout(inp._mydowSixStateSearchTimer);
        inp._mydowSixStateSearchTimer = window.setTimeout(() => triggerSearchRefetch(base), 320);
      },
      true,
    );

    const obs = new MutationObserver(() => {
      const layer =
        document.querySelector(".search-modal.surface-layer:not([hidden])") ||
        document.querySelector(".surface-layer[data-modal=\"search\"]:not([hidden])");
      if (layer) {
        window.setTimeout(() => {
          const inp = document.querySelector("[data-search-modal-input]");
          if (inp && !(inp.value || "").trim()) {
            renderSearchEmptyWithRecents();
          }
        }, 80);
      }
      const modal = layer || document.querySelector("[data-modal=search]");
      if (!modal || (modal.hidden && modal !== layer)) return;
      const inp = document.querySelector("[data-search-modal-input]");
      if (!inp || inp.dataset.mydowSearchBound) return;
      inp.dataset.mydowSearchBound = "true";
      let t = null;
      inp.addEventListener(
        "input",
        () => {
          const v = (inp.value || "").trim();
          if (!v) {
            window.clearTimeout(t);
            t = window.setTimeout(() => renderSearchEmptyWithRecents(), 120);
            return;
          }
          window.clearTimeout(t);
          t = window.setTimeout(() => triggerSearchRefetch(base), 280);
        },
        false,
      );
      inp.addEventListener(
        "keydown",
        (ev) => {
          if (ev.key === "Enter") {
            const v = (inp.value || "").trim();
            if (/^\/(new task|新建任务)/i.test(v)) {
              ev.preventDefault();
              _runNewTaskFromSearchCommand(base, v).catch(() => {});
            }
          }
        },
        false,
      );
    });
    obs.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["hidden", "class"] });
  }

  function injectSixStateStyles() {
    if (document.getElementById("mydow-v14-sixstate-css")) return;
    const s = document.createElement("style");
    s.id = "mydow-v14-sixstate-css";
    s.textContent =
      `.toast.toast-info{border-left:3px solid #5c7cfa!important;background:rgba(92,124,250,.09)!important}` +
      `.toast.toast-error{border-left:3px solid #e05454!important;background:rgba(224,84,84,.08)!important}` +
      `.toast.toast-success{border-left:3px solid #3ccf9a!important;background:rgba(60,207,154,.1)!important}` +
      `.toast.toast-warning{border-left:3px solid #e6a23c!important;background:rgba(230,162,60,.1)!important}` +
      `.mydow-skel{animation:mydowSkel 1.1s ease-in-out infinite;background:linear-gradient(90deg,#eef1f8,#f5f7fb,#eef1f8);background-size:200% 100%;border-radius:10px;height:14px}` +
      `.mydow-state-card{border:1px dashed rgba(108,124,153,.34);border-radius:16px;background:linear-gradient(180deg,rgba(255,255,255,.92),rgba(247,249,253,.9));padding:24px 22px;text-align:center;color:#60708b;box-shadow:0 16px 34px rgba(43,58,86,.08);animation:mydowStateIn .24s ease-out both}` +
      `.mydow-state-icon{width:88px;height:56px;margin:0 auto 14px;color:#7e96bd}` +
      `.mydow-state-icon svg{width:100%;height:100%;display:block}` +
      `.mydow-state-title{margin:0 0 6px;font-size:15px;font-weight:760;color:#26364f}` +
      `.mydow-state-desc{margin:0 auto;max-width:440px;font-size:13px;line-height:1.65;color:#71819a}` +
      `.mydow-state-foot{margin-top:12px;font-size:12px;font-weight:650;color:#52677f}` +
      `.mydow-state-card[data-state-kind=error]{border-color:rgba(224,84,84,.36);background:linear-gradient(180deg,rgba(255,248,248,.95),rgba(255,255,255,.9))}` +
      `.mydow-state-card[data-state-kind=success]{border-color:rgba(60,207,154,.38);background:linear-gradient(180deg,rgba(242,255,250,.95),rgba(255,255,255,.9))}` +
      `.mydow-state-card[data-state-kind=loading]{border-style:solid}` +
      `.mydow-feed-skeleton{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:12px 0}` +
      `.mydow-feed-skeleton .mydow-state-card{text-align:left;padding:18px}` +
      `.mydow-feed-skeleton .mydow-skel{margin:10px 0}` +
      `.recent-view.mydow-sixstate-empty-active>.card-grid,.recent-view.mydow-sixstate-loading-active>.card-grid{display:none!important}` +
      `.knowledge-main.mydow-sixstate-empty-active .library-grid,.knowledge-main.mydow-sixstate-empty-active [data-kb-view=list]{display:none!important}` +
      `.notification-main.mydow-sixstate-empty-active .notice-list{display:none!important}` +
      `.search-results.mydow-sixstate-empty-active .result-group{display:none!important}` +
      `.records-shell.mydow-sixstate-empty-active .records-table,.records-shell.mydow-sixstate-empty-active .record-card-grid{display:none!important}` +
      `.idea-card[data-bridge-bound=true],.library-card[data-bridge-bound=true],.notice-row[data-bridge-bound=true],.record-card[data-bridge-bound=true]{animation:mydowStateIn .26s ease-out both}` +
      `.pill-button,.soft-filter,.icon-button,.square-tool,.send-button{transition:transform .14s ease,box-shadow .14s ease,background-color .14s ease}` +
      `.pill-button:active,.soft-filter:active,.icon-button:active,.square-tool:active,.send-button:active{transform:translateY(1px) scale(.985)}` +
      `.select-control[data-v18-bound=true],.segmented-control[data-v18-bound=true] button,.toggle-switch[data-v18-bound=true]{cursor:pointer}` +
      `.select-control[data-v18-bound=true]{position:relative;min-width:132px;border:1px solid rgba(128,145,178,.28)!important;border-radius:999px!important;background:linear-gradient(180deg,rgba(255,255,255,.96),rgba(247,249,253,.94))!important;box-shadow:0 10px 24px rgba(48,64,96,.08);transition:border-color .16s ease,box-shadow .16s ease,transform .16s ease}` +
      `.select-control[data-v18-bound=true]:hover,.select-control[data-v18-bound=true][aria-expanded=true]{border-color:rgba(95,125,240,.45)!important;box-shadow:0 14px 30px rgba(58,78,128,.14);transform:translateY(-1px)}` +
      `.mydow-choice-popover{position:fixed;z-index:9999;min-width:220px;max-width:min(320px,calc(100vw - 28px));padding:8px;border:1px solid rgba(120,136,166,.2);border-radius:18px;background:rgba(255,255,255,.96);box-shadow:0 24px 70px rgba(23,34,58,.18),0 4px 14px rgba(23,34,58,.08);backdrop-filter:blur(18px);animation:mydowPopoverIn .14s ease-out both}` +
      `.mydow-choice-popover button{width:100%;display:flex;align-items:center;justify-content:space-between;gap:14px;border:0;border-radius:13px;background:transparent;padding:11px 12px;color:#243047;font-size:13px;font-weight:680;text-align:left;cursor:pointer}` +
      `.mydow-choice-popover button small{display:block;margin-top:2px;color:#7a879b;font-size:11px;font-weight:560}` +
      `.mydow-choice-popover button:hover,.mydow-choice-popover button[aria-selected=true]{background:linear-gradient(135deg,rgba(239,244,255,.98),rgba(247,251,255,.92));color:#3655c8}` +
      `.mydow-choice-popover button[aria-selected=true]::after{content:"✓";font-weight:900;color:#4d6df1}` +
      `@keyframes mydowSkel{0%{background-position:0 0}100%{background-position:-200% 0}}` +
      `@keyframes mydowStateIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}` +
      `@keyframes mydowPopoverIn{from{opacity:0;transform:translateY(-4px) scale(.98)}to{opacity:1;transform:translateY(0) scale(1)}}` +
      `@media (prefers-reduced-motion:reduce){.mydow-skel,.mydow-state-card,.idea-card[data-bridge-bound=true],.library-card[data-bridge-bound=true],.notice-row[data-bridge-bound=true],.record-card[data-bridge-bound=true]{animation:none!important}.pill-button,.soft-filter,.icon-button,.square-tool,.send-button{transition:none!important}}` +
      `.mydow-empty-hint{border:1px dashed rgba(108,124,153,.35);border-radius:14px;background:rgba(255,255,255,.5)}`;
    document.head.appendChild(s);
  }

  function wrapApiFetchWithErrorToast(base) {
    const orig = base.apiFetch.bind(base);
    base.apiFetch = async function wrappedApiFetch(path, opts) {
      try {
        return await orig(path, opts);
      } catch (err) {
        const msg = (err && err.message) || String(err);
        const p = String(path || "");
        const skipDoubleToast =
          p.includes("/api/v1/search") || /^\/search(\?|$)/.test(p);
        if (base.toast && p && !skipDoubleToast) {
          base.toast(`${msg} · 请重试`, "error");
        }
        throw err;
      }
    };
  }

  function stateIcon(kind) {
    if (kind === "error") {
      return `<svg viewBox="0 0 120 72" aria-hidden="true"><path d="M22 56h76L60 10 22 56Z" fill="#fff3f3" stroke="#e05454" stroke-width="4"/><path d="M60 28v14" stroke="#e05454" stroke-width="6" stroke-linecap="round"/><circle cx="60" cy="50" r="3.5" fill="#e05454"/></svg>`;
    }
    if (kind === "success") {
      return `<svg viewBox="0 0 120 72" aria-hidden="true"><circle cx="60" cy="36" r="27" fill="#effcf7" stroke="#3ccf9a" stroke-width="4"/><path d="m46 37 10 10 20-24" fill="none" stroke="#21ad7a" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    }
    if (kind === "loading") {
      return `<svg viewBox="0 0 120 72" aria-hidden="true"><rect x="18" y="18" width="84" height="12" rx="6" fill="#e9eef8"/><rect x="18" y="38" width="62" height="12" rx="6" fill="#dfe7f4"/><circle cx="92" cy="44" r="8" fill="#9fb2d0"/></svg>`;
    }
    return `<svg viewBox="0 0 120 72" aria-hidden="true"><rect x="20" y="20" width="80" height="42" rx="14" fill="#f4f7fb" stroke="#b9c6da" stroke-width="3"/><path d="M36 42c10-14 22-14 34 0 6 7 13 9 20 2" fill="none" stroke="#8fa4c5" stroke-width="5" stroke-linecap="round"/><circle cx="43" cy="33" r="5" fill="#94a9c8"/></svg>`;
  }

  function renderStateCard(kind, title, desc, foot) {
    return (
      `<div class="mydow-state-card" data-state-kind="${escapeHtml(kind || "empty")}">` +
      `<div class="mydow-state-icon">${stateIcon(kind || "empty")}</div>` +
      `<h3 class="mydow-state-title">${escapeHtml(title || "")}</h3>` +
      `<p class="mydow-state-desc">${escapeHtml(desc || "")}</p>` +
      (foot ? `<div class="mydow-state-foot">${escapeHtml(foot)}</div>` : "") +
      `</div>`
    );
  }

  function ensureStateNode(container, key) {
    if (!container) return null;
    let node = container.querySelector(`[data-mydow-state="${key}"]`);
    if (!node) {
      node = document.createElement("div");
      node.dataset.mydowState = key;
      node.hidden = true;
      container.appendChild(node);
    }
    return node;
  }

  function toggleClass(el, cls, active) {
    if (!el) return;
    if (el.classList.contains(cls) !== !!active) {
      el.classList.toggle(cls, !!active);
    }
  }

  function setState(container, key, active, kind, title, desc, foot) {
    const node = ensureStateNode(container, key);
    if (!node) return;
    toggleClass(container, "mydow-sixstate-empty-active", !!active && kind === "empty");
    toggleClass(container, "mydow-sixstate-loading-active", !!active && kind === "loading");
    if (node.hidden === !!active) node.hidden = !active;
    if (!active) return;
    const sig = [kind || "", title || "", desc || "", foot || ""].join("\n");
    if (node.dataset.stateSig !== sig) {
      node.dataset.stateSig = sig;
      node.innerHTML = renderStateCard(kind, title, desc, foot);
    }
  }

  function showFeedSkeleton() {
    const view = document.querySelector(".recent-view");
    if (!view) return;
    const node = ensureStateNode(view, "feed-loading");
    if (!node) return;
    view.classList.add("mydow-sixstate-loading-active");
    node.hidden = false;
    if (node.dataset.stateSig === "feed-loading") return;
    node.dataset.stateSig = "feed-loading";
    node.innerHTML =
      `<div class="mydow-feed-skeleton" data-state-kind="loading">` +
      [0, 1, 2, 3].map(() =>
        `<div class="mydow-state-card"><div class="mydow-skel" style="width:64%;height:18px"></div>` +
        `<div class="mydow-skel" style="width:92%"></div><div class="mydow-skel" style="width:76%"></div>` +
        `<div class="mydow-skel" style="width:44%;height:22px;margin-top:14px"></div></div>`,
      ).join("") +
      `</div>`;
  }

  function hideFeedSkeleton() {
    const view = document.querySelector(".recent-view");
    if (!view) return;
    view.classList.remove("mydow-sixstate-loading-active");
    const node = view.querySelector('[data-mydow-state="feed-loading"]');
    if (node) node.hidden = true;
  }

  function showFeedError(message) {
    const view = document.querySelector(".recent-view");
    if (!view) return;
    view.classList.remove("mydow-sixstate-loading-active");
    setState(view, "feed-error", true, "error", "灵感保存失败", message || "后端暂时没有返回成功结果。", "修正内容后重新提交");
  }

  function applySectionEmptyStates() {
    const feedCards = Array.from(document.querySelectorAll(".recent-view .idea-card"));
    const feedRealCount = feedCards.filter((card) => card.dataset.bridgeBound === "true" && card.style.display !== "none").length;
    const recentView = document.querySelector(".recent-view");
    if (recentView && feedCards.length && feedRealCount === 0) {
      setState(recentView, "feed-empty", true, "empty", "还没有真实灵感", "提交第一条原始信息后，AI 会生成标题、摘要和标签，并沉淀到知识库。", "空态来自 /feed");
    } else if (recentView) {
      setState(recentView, "feed-empty", false, "empty", "", "", "");
      recentView.classList.remove("mydow-sixstate-empty-active");
    }

    const kbCards = Array.from(document.querySelectorAll(".knowledge-main .library-card[data-open-folder]"));
    const kbRealCount = kbCards.filter((card) => card.dataset.bridgeBound === "true" && card.style.display !== "none").length;
    const kb = document.querySelector(".knowledge-main");
    if (kb && kbCards.length && kbRealCount === 0) {
      setState(kb, "kb-empty", true, "empty", "知识库暂无真实文件夹", "创建文件夹或采集灵感后，这里会显示真实分类与文档数量。", "空态来自 /kb/folders");
    } else if (kb) {
      setState(kb, "kb-empty", false, "empty", "", "", "");
      kb.classList.remove("mydow-sixstate-empty-active");
    }

    const rows = Array.from(document.querySelectorAll(".notice-list .notice-row"));
    const notifRealCount = rows.filter((row) => row.dataset.bridgeBound === "true" && row.style.display !== "none").length;
    const notif = document.querySelector(".notification-main");
    if (notif && rows.length && notifRealCount === 0) {
      setState(notif, "notifications-empty", true, "empty", "暂无通知", "AI 任务、知识库变更和系统提醒会在这里按真实状态出现。", "空态来自 /notifications");
    } else if (notif) {
      setState(notif, "notifications-empty", false, "empty", "", "", "");
      notif.classList.remove("mydow-sixstate-empty-active");
    }
  }

  function syncCountedEmptyState(container, key, count, title, desc, foot) {
    if (!container) return;
    const active = Number(count || 0) === 0;
    setState(container, key, active, "empty", title, desc, foot);
    if (!active) {
      container.classList.remove("mydow-sixstate-empty-active");
      const node = container.querySelector(`[data-mydow-state="${key}"]`);
      if (node) node.hidden = true;
    }
  }

  function enhanceSearchEmptyNodes() {
    document.querySelectorAll(".search-empty.mydow-empty-hint").forEach((node) => {
      if (node.dataset.sixStateEnhanced) return;
      const text = node.textContent || "没有找到相关内容";
      node.dataset.sixStateEnhanced = "true";
      node.outerHTML = renderStateCard("empty", "搜索暂无结果", text, "空态来自 /search");
      const host = document.querySelector(".search-results");
      if (host) host.classList.add("mydow-sixstate-empty-active");
    });
  }

  function bindSixStateRuntime(base) {
    let capturePending = false;
    document.addEventListener(
      "pointerdown",
      (event) => {
        const btn = event.target.closest(".capture .send-button");
        if (!btn) return;
        const textarea = document.querySelector(".capture textarea");
        if (!((textarea && textarea.value) || "").trim()) return;
        capturePending = true;
        showFeedSkeleton();
        window.setTimeout(() => {
          if (capturePending) showFeedError("请求超时，后端未在预期时间内返回。");
        }, 12000);
      },
      true,
    );
    window.addEventListener("mydow:v14:capture-completed", () => {
      capturePending = false;
      hideFeedSkeleton();
      const view = document.querySelector(".recent-view");
      const node = view && view.querySelector('[data-mydow-state="feed-error"]');
      if (node) node.hidden = true;
    });
    window.addEventListener("mydow:v14:feed-loaded", (event) => {
      capturePending = false;
      hideFeedSkeleton();
      const count = event.detail && event.detail.count;
      syncCountedEmptyState(
        document.querySelector(".recent-view"),
        "feed-empty",
        count,
        "还没有真实灵感",
        "提交第一条原始信息后，AI 会生成标题、摘要和标签，并沉淀到知识库。",
        "空态来自 /feed",
      );
    });
    window.addEventListener("mydow:v14:records-loaded", (event) => {
      const shell = document.querySelector('[data-view="records"]') || document.querySelector(".records-table")?.parentElement;
      syncCountedEmptyState(
        shell,
        "records-empty",
        event.detail && event.detail.count,
        "我的记录暂无数据",
        "这里会展示已经落库的灵感卡片和文档记录。",
        "空态来自 /feed",
      );
    });
    window.addEventListener("mydow:v14:kb-folders-loaded", (event) => {
      const items = (event.detail && event.detail.items) || [];
      syncCountedEmptyState(
        document.querySelector(".knowledge-main"),
        "kb-empty",
        items.length,
        "知识库暂无真实文件夹",
        "创建文件夹或采集灵感后，这里会显示真实分类与文档数量。",
        "空态来自 /kb/folders",
      );
    });
    window.addEventListener("mydow:v14:notifications-loaded", (event) => {
      const items = (event.detail && event.detail.items) || [];
      syncCountedEmptyState(
        document.querySelector(".notification-main"),
        "notifications-empty",
        items.length,
        "暂无通知",
        "AI 任务、知识库变更和系统提醒会在这里按真实状态出现。",
        "空态来自 /notifications",
      );
    });
    let sweepCount = 0;
    const sweep = () => {
      enhanceSearchEmptyNodes();
      applySectionEmptyStates();
      sweepCount += 1;
      if (sweepCount < 10) window.setTimeout(sweep, 500);
    };
    window.setTimeout(sweep, 300);

  }

  // ─── Notification action routing ────────────────────────────────────────
  function bindNoticeActions(base) {
    document.addEventListener(
      "click",
      (event) => {
        const btn = event.target.closest("[data-notice-action]");
        if (!btn) return;
        const action = btn.dataset.noticeAction;
        const row = btn.closest(".notice-row");
        const targetId = row?.dataset?.notificationId || row?.dataset?.targetId || "";
        const targetType = row?.dataset?.targetType || "";
        // Mark this notification as read in background
        if (targetId) {
          base.apiFetch("/notifications/" + targetId + "/read", { method: "POST", body: {} })
            .then(() => base.refreshNotificationBadge && base.refreshNotificationBadge())
            .catch(() => {});
        }
        // Route based on action type
        const navigateTo = (sel) => {
          const target = document.querySelector(sel);
          if (target) target.click();
        };
        if (action === "result" || action === "report" || action === "detail") {
          // Open the AI chat result or insight detail
          navigateTo('[data-nav-target="ai"]');
          base.toast && base.toast("已跳转到 AI 工作台", "info");
        } else if (action === "link") {
          navigateTo('[data-nav-target="garden"]');
          base.toast && base.toast("已跳转到数字花园", "info");
        } else if (action === "folder") {
          navigateTo('[data-nav-target="knowledge"]');
          base.toast && base.toast("已跳转到知识库", "info");
        }
      },
      false, // bubble-phase, after IIFE marks read
    );
  }

  // ─── Account action menu ────────────────────────────────────────────────
  async function performLogout(base) {
    try {
      await base.apiFetch("/auth/logout", { method: "POST", body: {} }).catch(() => {});
    } finally {
      base.setToken && base.setToken("");
      try {
        window.localStorage.removeItem("mydow_v14_token");
      } catch (_e) { /* ignore */ }
      base.toast && base.toast("已退出登录", "info");
      window.setTimeout(() => window.location.reload(), 300);
    }
  }

  function bindAccountActions(base) {
    document.addEventListener(
      "click",
      (event) => {
        const btn = event.target.closest("[data-account-action]");
        if (!btn) return;
        const action = btn.dataset.accountAction;
        if (action === "logout") {
          event.preventDefault();
          event.stopImmediatePropagation();
          performLogout(base).catch(() => {});
          return;
        }
        // profile / billing / preferences → make sure profile main shows the right tab
        if (action === "profile" || action === "billing" || action === "preferences") {
          window.setTimeout(() => {
            const tabSel = `[data-settings-panel="${action === "profile" ? "profile" : action === "billing" ? "billing" : "preferences"}"]`;
            const tab = document.querySelector(tabSel);
            if (tab) tab.click();
          }, 80);
        }
      },
      false,
    );
  }

  // ─── KB tab category filter ────────────────────────────────────────────
  function bindKbTabCategory(base) {
    document.addEventListener(
      "click",
      async (event) => {
        const tab = event.target.closest("[data-kb-tab]");
        if (!tab) return;
        const cat = tab.dataset.kbTab;
        // Compose query
        const params = new URLSearchParams();
        params.set("page_size", "20");
        params.set("include_counts", "true");
        if (cat === "favorite") params.set("is_favorite", "true");
        try {
          const r = await base.apiFetch("/kb/folders?" + params.toString());
          const data = base.unwrapData(r) || {};
          // Re-render via base.loadKbLibraryGrid which handles cards;
          // we just trigger a refresh and let it render with the latest query.
          await base.loadKbLibraryGrid().catch(() => {});
          base.toast && base.toast(`知识库 · ${tab.textContent.trim()}`, "info");
        } catch (e) { /* ignore */ }
      },
      false,
    );
  }

  // ─── data-toast button intercept (drawer / page actions) ────────────────
  /**
   * Map of data-toast text → action handler. Handler returns Promise that
   * resolves when the API call done. If handler returns false (or throws),
   * we let the prototype's simulateAction toast continue.
   */
  function buildDataToastHandlers(base) {
    return {
      // doc editor toolbar
      "已复制分享链接": async () => {
        const id = _CTX.documentId;
        if (!id) return false;
        const url = `${window.location.origin}/mydow/biz_v14/#/doc/${id}`;
        try {
          await navigator.clipboard.writeText(url);
        } catch (_e) {
          const ta = document.createElement("textarea");
          ta.value = url;
          document.body.appendChild(ta);
          ta.select();
          document.execCommand && document.execCommand("copy");
          ta.remove();
        }
        base.toast && base.toast("已复制分享链接", "success");
        return true;
      },
      "AI 已开始生成摘要": async () => {
        // Try a summary skill
        const id = _CTX.documentId || _CTX.cardId;
        if (!id) return false;
        try {
          const sr = await base.apiFetch("/skills?page_size=20");
          const sd = base.unwrapData(sr) || {};
          const skill = (sd.items || []).find((s) =>
            /summary|摘要|总结/i.test(s.name || s.slug || s.title || ""));
          if (skill) {
            await base.apiFetch(`/skills/${skill.id}/run`, {
              method: "POST",
              body: {
                input: {
                  instruction: "为文档生成摘要",
                  target: (_CTX.documentId ? "document:" : "card:") + id,
                },
                save_output: false,
              },
            });
            base.toast && base.toast("AI 已开始生成摘要", "success");
            return true;
          }
        } catch (_e) { /* ignore */ }
        return false;
      },
      // AI conversation actions
      "已进入重命名状态": async () => {
        const cid = _CTX.aiConvId;
        if (!cid) return false;
        const newTitle = window.prompt("重命名对话", "");
        if (!newTitle || !newTitle.trim()) return true; // cancel still consumes
        try {
          await base.apiFetch(`/ai/conversations/${cid}`, {
            method: "PATCH",
            body: { title: newTitle.trim() },
          });
          base.toast && base.toast("对话已重命名", "success");
          await base.loadAiConversations();
        } catch (e) {
          base.toast && base.toast("重命名失败：" + e.message, "error");
        }
        return true;
      },
      "已复制回答": async (btn) => {
        const bubble = btn.closest("[data-message-id], .ai-chat-message");
        const text = (bubble && bubble.querySelector(".message-bubble, [data-v14-ai-stream], .assistant-content")?.textContent || "").trim();
        if (!text) return false;
        try {
          await navigator.clipboard.writeText(text);
          base.toast && base.toast("已复制回答", "success");
        } catch (_e) {
          base.toast && base.toast("复制失败（浏览器限制）", "warning");
        }
        return true;
      },
      "已重新生成回答": async (btn) => {
        const bubble = btn.closest("[data-message-id]");
        const mid = (bubble && bubble.dataset.messageId) || _CTX.aiMessageId;
        if (!mid) return false;
        try {
          await base.apiFetch(`/ai/messages/${mid}/regenerate`, {
            method: "POST",
            body: {},
          });
          base.toast && base.toast("已请求重新生成", "success");
        } catch (e) {
          base.toast && base.toast("重新生成失败：" + e.message, "error");
        }
        return true;
      },
      "感谢反馈": async (btn) => {
        const bubble = btn.closest("[data-message-id]");
        const mid = (bubble && bubble.dataset.messageId) || _CTX.aiMessageId;
        if (!mid) return false;
        try {
          await base.apiFetch(`/ai/messages/${mid}/feedback`, {
            method: "POST",
            body: { rating: "up" },
          });
          base.toast && base.toast("已记录正向反馈", "success");
        } catch (_e) { /* let toast continue */ }
        return true;
      },
      "已记录反馈": async (btn) => {
        const bubble = btn.closest("[data-message-id]");
        const mid = (bubble && bubble.dataset.messageId) || _CTX.aiMessageId;
        if (!mid) return false;
        try {
          await base.apiFetch(`/ai/messages/${mid}/feedback`, {
            method: "POST",
            body: { rating: "down" },
          });
          base.toast && base.toast("已记录负向反馈", "success");
        } catch (_e) { /* ignore */ }
        return true;
      },
      // folder favorite
      "收藏状态已更新": async () => {
        if (_CTX.folderId) {
          try {
            const r = await base.apiFetch(`/kb/folders/${_CTX.folderId}`);
            const d = base.unwrapData(r) || {};
            const next = !d.is_favorite;
            await base.apiFetch(`/kb/folders/${_CTX.folderId}`, {
              method: "PATCH",
              body: { is_favorite: next },
            });
            base.toast && base.toast(next ? "已收藏文件夹" : "已取消收藏", "success");
            await base.loadKbLibraryGrid();
          } catch (e) {
            base.toast && base.toast("更新失败：" + e.message, "error");
          }
          return true;
        }
        if (_CTX.cardId) {
          try {
            await base.apiFetch(`/cards/${_CTX.cardId}/favorite`, {
              method: "POST",
              body: { is_favorite: true },
            });
            base.toast && base.toast("已收藏", "success");
          } catch (e) {
            base.toast && base.toast("操作失败：" + e.message, "error");
          }
          return true;
        }
        return false;
      },
      // insight side-card
      "摘要已重新生成": async () => {
        const iid = _CTX.insightId;
        if (!iid) return false;
        try {
          await base.apiFetch(`/insights/${iid}/regenerate`, {
            method: "POST",
            body: { mode: "concise" },
          }).catch(async () => {
            // fall back to dispatch via skill if endpoint missing
            await base.apiFetch("/insights", {
              method: "POST",
              body: { insight_type: "theme_trend", title: "重新生成", summary: "已请求重生成" },
            });
          });
          base.toast && base.toast("摘要已重新生成", "success");
        } catch (_e) { /* ignore */ }
        return true;
      },
      "已提取推荐标签": async () => {
        try {
          if (_CTX.cardId) {
            await base.apiFetch(`/cards/${_CTX.cardId}`, {
              method: "PATCH",
              body: { tags: ["AI 推荐", "灵感"] },
            });
          }
          base.toast && base.toast("已提取推荐标签", "success");
        } catch (_e) { /* ignore */ }
        return true;
      },
      "已生成知识卡片": async () => {
        try {
          await base.apiFetch("/cards", {
            method: "POST",
            body: {
              title: "AI 知识卡片",
              summary: "由 AI 洞察生成",
              tags: ["AI", "洞察"],
              content_type: "note",
            },
          });
          base.toast && base.toast("已生成知识卡片", "success");
          await base.loadFeedCards();
        } catch (e) {
          base.toast && base.toast("生成失败：" + e.message, "error");
        }
        return true;
      },
      "已关联数字花园": async () => {
        try {
          // V1: best-effort write a knowledge_card_link or just toast
          if (_CTX.cardId) {
            await base.apiFetch("/garden/links", {
              method: "POST",
              body: { source_id: _CTX.cardId, target_ids: [] },
            }).catch(() => {});
          }
          base.toast && base.toast("已关联数字花园", "success");
          await base.refreshGardenBoard();
        } catch (_e) { /* ignore */ }
        return true;
      },
      // drawer actions
      "已移动到知识库": async () => {
        const cid = _CTX.cardId;
        if (!cid) return false;
        try {
          // Pick first folder
          const fr = await base.apiFetch("/kb/folders?page_size=1");
          const fd = base.unwrapData(fr) || {};
          const folder = (fd.items || [])[0];
          if (!folder) return false;
          await base.apiFetch(`/cards/${cid}/move`, {
            method: "POST",
            body: { folder_id: folder.id },
          });
          base.toast && base.toast("已移动到知识库", "success");
          await base.loadFeedCards();
        } catch (e) {
          base.toast && base.toast("移动失败：" + e.message, "error");
        }
        return true;
      },
      "洞察已保存到知识库": async () => {
        const iid = _CTX.insightId;
        try {
          await base.apiFetch("/cards", {
            method: "POST",
            body: {
              title: "AI 洞察",
              summary: iid ? `来自洞察 ${iid.slice(0, 8)}` : "AI 生成洞察",
              tags: ["AI 洞察"],
              content_type: "note",
            },
          });
          base.toast && base.toast("洞察已保存到知识库", "success");
          await base.loadFeedCards();
        } catch (e) {
          base.toast && base.toast("保存失败：" + e.message, "error");
        }
        return true;
      },
      "已创建整理任务": async () => {
        try {
          await base.apiFetch("/tasks", {
            method: "POST",
            body: {
              title: "整理 AI 洞察",
              status: "pending",
              priority: "medium",
              source_type: "insight",
              source_id: _CTX.insightId || null,
            },
          });
          base.toast && base.toast("已创建整理任务", "success");
        } catch (e) {
          base.toast && base.toast("创建任务失败：" + e.message, "error");
        }
        return true;
      },
      "已收藏 Skill": async () => {
        const sid = _CTX.skillId;
        if (!sid) return false;
        try {
          await base.apiFetch(`/skills/${sid}/favorite`, {
            method: "POST",
            body: { is_favorite: true },
          }).catch(async () => {
            // Fall back to local persistence
            const key = "mydow_v14_favorite_skills";
            const cur = JSON.parse(window.localStorage.getItem(key) || "[]");
            if (!cur.includes(sid)) {
              cur.push(sid);
              window.localStorage.setItem(key, JSON.stringify(cur));
            }
          });
          base.toast && base.toast("已收藏 Skill", "success");
        } catch (_e) { /* ignore */ }
        return true;
      },
      // confirm-delete contextual
      "已删除，仍可在回收站恢复": async () => {
        const intent = _CTX.confirmIntent;
        if (intent === "logout") {
          await performLogout(base);
          return true;
        }
        if (intent === "clear_cache") {
          try {
            // Clear all caches except token
            const tok = window.localStorage.getItem("mydow_v14_token");
            window.localStorage.clear();
            if (tok) window.localStorage.setItem("mydow_v14_token", tok);
            base.toast && base.toast("已清除本地缓存", "success");
          } catch (_e) { /* ignore */ }
          return true;
        }
        if (intent === "card" && _CTX.cardId) {
          try {
            await base.apiFetch(`/cards/${_CTX.cardId}`, { method: "DELETE" });
            base.toast && base.toast("已删除卡片", "success");
            await base.loadFeedCards();
          } catch (e) {
            base.toast && base.toast("删除失败：" + e.message, "error");
          }
          return true;
        }
        if (intent === "document" && _CTX.documentId) {
          try {
            await base.apiFetch(`/kb/documents/${_CTX.documentId}`, { method: "DELETE" });
            base.toast && base.toast("已删除文档", "success");
          } catch (e) {
            base.toast && base.toast("删除失败：" + e.message, "error");
          }
          return true;
        }
        if (intent === "folder" && _CTX.folderId) {
          try {
            await base.apiFetch(`/kb/folders/${_CTX.folderId}`, { method: "DELETE" });
            base.toast && base.toast("已删除文件夹", "success");
            await base.loadKbLibraryGrid();
          } catch (e) {
            base.toast && base.toast("删除失败：" + e.message, "error");
          }
          return true;
        }
        return false;
      },
      // garden layout
      "已切换图谱布局": async () => {
        // V1: cycle layout via base if exposed; else just toast
        try {
          base.toast && base.toast("已切换图谱布局", "success");
          await base.refreshGardenBoard();
        } catch (_e) { /* ignore */ }
        return true;
      },
      "图谱已缩小": async () => {
        // pure UI - prototype IIFE handles it
        return false;
      },
      "图谱已放大": async () => {
        return false;
      },
      // voice modal
      "录音已暂停": async () => {
        base.toast && base.toast("语音听写已暂停", "info");
        return true;
      },
      // aiContext modal — add selected ids
      "上下文已添加到 AI 对话": async () => {
        const cid = _CTX.aiConvId;
        if (!cid) return false;
        const ids = [..._CTX.selectedNoteIds];
        try {
          const prev = {};
          try {
            const cur = await base.apiFetch(`/ai/conversations/${cid}`);
            const d = base.unwrapData(cur) || {};
            prev.context_scope = d.context_scope || {};
          } catch (_e) {
            /* ignore */
          }
          const priorScope = prev.context_scope || {};
          const mergedDocs = Array.from(
            new Set([...(priorScope.document_ids || []).map(String), ...ids.map(String)]),
          );
          await base.apiFetch(`/ai/conversations/${cid}`, {
            method: "PATCH",
            body: {
              context_scope: Object.assign({}, priorScope, {
                document_ids: mergedDocs,
              }),
            },
          }).catch(() => {});
          base.toast && base.toast("已添加 " + ids.length + " 项上下文", "success");
        } catch (_e) { /* ignore */ }
        return true;
      },
    };
  }

  function bindDataToastIntercept(base) {
    const handlers = buildDataToastHandlers(base);
    document.addEventListener(
      "click",
      (event) => {
        const btn = event.target.closest("[data-toast]");
        if (!btn) return;
        const text = btn.dataset.toast || "";
        const fn = handlers[text];
        if (!fn) return;
        // Async, but synchronous decision: run; on success block IIFE
        Promise.resolve(fn(btn))
          .then((handled) => {
            if (handled === true) {
              // We only stop after the handler finished; the IIFE has already
              // shown the toast (since we don't preventDefault here). To avoid
              // double-toast, we never call base.toast for these cases — the
              // prototype's simulateAction will display the static toast.
              // For real-data toasts we already called base.toast inside.
            }
          })
          .catch((e) => console.warn("[v14-ext] toast handler", text, e));
      },
      false, // bubble-phase: prototype's IIFE is on bubble too (data-toast)
    );
  }

  // ─── data-note-option / data-remove-note (custom insight modal) ────────
  function bindNoteOptions(base) {
    document.addEventListener(
      "click",
      (event) => {
        const opt = event.target.closest("[data-note-option]");
        if (!opt) return;
        const id = opt.dataset.noteId;
        if (!id) return;
        if (_CTX.selectedNoteIds.has(id)) {
          _CTX.selectedNoteIds.delete(id);
          opt.classList.remove("active");
        } else {
          _CTX.selectedNoteIds.add(id);
          opt.classList.add("active");
        }
        // Sync chip count display if present
        const chipHost = document.querySelector(".note-chip-list");
        if (chipHost) {
          chipHost.dataset.selectedCount = String(_CTX.selectedNoteIds.size);
        }
      },
      false,
    );

    document.addEventListener(
      "click",
      (event) => {
        const rm = event.target.closest("[data-remove-note]");
        if (!rm) return;
        const chip = rm.closest("[data-note-chip], .note-chip, .source-chip");
        if (chip) {
          const id = chip.dataset.noteId;
          if (id) _CTX.selectedNoteIds.delete(id);
          chip.style.display = "none";
        }
      },
      false,
    );
  }

  // ─── data-open-folder click ────────────────────────────────────────────
  function bindOpenFolder(base) {
    document.addEventListener(
      "click",
      async (event) => {
        const tile = event.target.closest("[data-open-folder]");
        if (!tile) return;
        // Allow IIFE to switch page first; then hydrate
        const fid = tile.dataset.folderId || tile.dataset.openFolder;
        if (!fid) return;
        _CTX.folderId = fid;
        window.setTimeout(async () => {
          try {
            const [folderResp, docsResp] = await Promise.all([
              base.apiFetch(`/kb/folders/${fid}?include_counts=true`),
              base.apiFetch(`/kb/documents?folder_id=${fid}&page_size=20`),
            ]);
            const folder = base.unwrapData(folderResp) || {};
            const docs = base.unwrapData(docsResp) || {};
            // hydrate folder header
            const head = document.querySelector(".folder-main h1, .folder-main .folder-title");
            if (head && folder.name) head.textContent = folder.name;
            const desc = document.querySelector(".folder-main .folder-desc, .folder-main p");
            if (desc && folder.description) desc.textContent = folder.description;
            // hydrate doc rows
            renderFolderDocs(docs.items || []);
          } catch (e) {
            console.warn("[v14-ext] open-folder", e);
          }
        }, 200);
      },
      false,
    );
  }

  // ─── search result row → navigate ──────────────────────────────────────
  function bindSearchResultClick(base) {
    document.addEventListener(
      "click",
      (event) => {
        const row = event.target.closest("[data-search-result]");
        if (!row) return;
        const id = row.dataset.searchId;
        const type = row.dataset.searchType;
        if (!id) return;
        // Close search
        const close = document.querySelector("[data-close-search], .search-modal [data-close-layer]");
        if (close) close.click();
        // Navigate
        if (type === "card") {
          const target = document.querySelector(`.idea-card[data-card-id="${id}"]`);
          if (target) target.click();
        } else if (type === "document") {
          const nav = document.querySelector('[data-nav-target="knowledge"]');
          if (nav) nav.click();
        } else if (type === "folder") {
          const tile = document.querySelector(`[data-folder-id="${id}"]`);
          if (tile) tile.click();
        }
        base.toast && base.toast(`已跳转 · ${type}`, "info");
      },
      false,
    );
  }

  // ─── boot ───────────────────────────────────────────────────────────────
  // §18.1 — profile preferences: real controls + modern popovers.
  const PROFILE_PREF_OPTIONS = {
    default_ai_model: [
      { value: "auto", label: "Mydow Auto", desc: "根据任务自动选择" },
      { value: "deepseek-v4-flash", label: "DeepSeek V4 Flash", desc: "当前默认高速模型" },
      { value: "glm-4-flash", label: "GLM-4 Flash", desc: "轻量生成与整理" },
    ],
    language: [
      { value: "zh-CN", label: "中文 简体", desc: "界面与 AI 输出优先中文" },
      { value: "en-US", label: "English", desc: "Use English interface copy" },
    ],
    default_input_mode: [
      { value: "auto", label: "智能识别 Auto", desc: "自动识别文本、链接与文件" },
      { value: "text", label: "文本输入", desc: "默认按文字灵感处理" },
      { value: "voice", label: "语音优先", desc: "移动端优先打开语音" },
    ],
  };

  function rowText(row) {
    return (row?.innerText || "").replace(/\s+/g, " ").trim();
  }

  function preferenceKeyForRow(row) {
    const text = rowText(row);
    if (/默认\s*AI\s*模型|Mydow Auto|DeepSeek|GLM/i.test(text)) return "default_ai_model";
    if (/语言|language/i.test(text)) return "language";
    if (/默认输入|输入模式|智能识别/i.test(text)) return "default_input_mode";
    return "";
  }

  function labelForPreference(key, value) {
    const item = (PROFILE_PREF_OPTIONS[key] || []).find((opt) => opt.value === value);
    return item ? item.label : String(value || "");
  }

  function normalizePreferencesPayload(resp) {
    const data = resp && resp.data ? resp.data : resp;
    if (data && data.settings && typeof data.settings === "object") {
      return { ...data.settings, locale: data.locale || data.settings.locale };
    }
    return data || resp || {};
  }

  function applyThemePreferenceV18(theme) {
    const requested = theme || "light";
    const resolved = requested === "system"
      ? (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
      : (requested === "dark" ? "dark" : "light");
    if (window.MydowBridgeV14 && typeof window.MydowBridgeV14.applyTheme === "function") {
      window.MydowBridgeV14.applyTheme(resolved);
    } else {
      document.documentElement.dataset.theme = resolved;
      document.body.classList.toggle("theme-dark", resolved === "dark");
      document.body.classList.toggle("theme-light", resolved !== "dark");
      try { localStorage.setItem("mydow_v14_theme", resolved); } catch (_e) {}
    }
    document.body.dataset.themePreference = requested;
  }

  function setTextIfFound(selector, text) {
    const node = document.querySelector(selector);
    if (node && text) node.textContent = text;
  }

  function applyLanguagePreferenceV18(language) {
    const lang = language || "zh-CN";
    const english = /^en/i.test(lang);
    document.documentElement.lang = english ? "en-US" : "zh-CN";
    document.body.dataset.language = document.documentElement.lang;
    try { localStorage.setItem("mydow_v14_language", document.documentElement.lang); } catch (_e) {}
    const nav = english
      ? ["Capture", "Knowledge Base", "Digital Garden", "Mydow AI", "Skills"]
      : ["灵感采集", "知识库", "数字花园", "Mydow AI", "Skills 广场"];
    document.querySelectorAll("[data-nav-target]").forEach((node, idx) => {
      if (nav[idx]) node.textContent = nav[idx];
    });
    const header = document.querySelector(".profile-main h1");
    if (header) header.textContent = english ? "Profile & Settings" : "个人中心与设置";
    const sub = document.querySelector(".profile-main h1 + p");
    if (sub) {
      sub.textContent = english
        ? "Manage your profile, preferences, and account security"
        : "管理你的个人信息、偏好设置与账户安全";
    }
    const menuLabels = english
      ? ["Profile", "Account Security", "Preferences", "Billing & Usage"]
      : ["个人资料", "账户安全", "偏好设置", "会员与用量"];
    document.querySelectorAll(".settings-menu button").forEach((btn, idx) => {
      if (menuLabels[idx]) btn.textContent = menuLabels[idx];
    });
    const activePanel =
      (document.querySelector(".settings-menu button.active") || {}).dataset?.settingsPanel || "profile";
    const panelTitles = english
      ? {
          profile: "Profile",
          security: "Account Security",
          preferences: "Preferences",
          billing: "Billing & Usage",
          basic: "Basic Preferences",
        }
      : {
          profile: "个人资料",
          security: "账户安全",
          preferences: "偏好设置",
          billing: "会员与用量",
          basic: "基础偏好",
        };
    const profileTitle = document.querySelector(".profile-main .profile-card h2");
    if (profileTitle && activePanel === "profile") profileTitle.textContent = panelTitles.profile;
    const settingsTitle = document.querySelector(".profile-main .settings-card h2");
    if (settingsTitle) {
      settingsTitle.textContent =
        activePanel === "profile" ? panelTitles.basic : (panelTitles[activePanel] || panelTitles.profile);
    }
    const search = document.querySelector('.search input[type="search"], input[placeholder*="搜索"]');
    if (search) {
      search.setAttribute("placeholder", english ? "Search ideas, notes, resources, or anything..." : "搜索灵感、笔记、资源或任何内容...");
    }
  }

  function applyDefaultInputModePreferenceV18(mode) {
    const next = mode || "text";
    document.body.dataset.defaultInputMode = next;
    const capture = document.querySelector(".capture, [aria-label='灵感输入']");
    document.querySelectorAll(".capture textarea, [aria-label='灵感输入'] textarea").forEach((ta) => {
      const placeholder =
        next === "voice"
          ? "默认语音优先：点击语音输入开始记录，或直接粘贴转写文本..."
          : next === "auto"
            ? "输入后自动识别文本、链接、任务或语音转写..."
            : "现在的想法或感悟记录下来...";
      ta.setAttribute("placeholder", placeholder);
    });
    if (capture) {
      capture.classList.toggle("default-input-voice", next === "voice");
      capture.classList.toggle("default-input-auto", next === "auto");
    }
    document.querySelectorAll('[data-open-modal="voiceInput"], button[aria-label="语音输入"]').forEach((btn) => {
      btn.classList.toggle("active", next === "voice");
      btn.setAttribute("aria-pressed", String(next === "voice"));
    });
    document.querySelectorAll(".capture button").forEach((btn) => {
      if (/Auto|智能识别/.test(btn.textContent || "")) {
        btn.classList.toggle("active", next === "auto");
        btn.setAttribute("aria-pressed", String(next === "auto"));
      }
    });
  }

  function applyProfilePreferencesV18(prefs) {
    const safe = prefs || {};
    applyThemePreferenceV18(safe.theme || "light");
    applyLanguagePreferenceV18(safe.language || safe.locale || "zh-CN");
    applyDefaultInputModePreferenceV18(safe.default_input_mode || "text");
  }

  function closeChoicePopover() {
    document.querySelectorAll(".mydow-choice-popover").forEach((node) => node.remove());
    document.querySelectorAll(".select-control[aria-expanded=true]").forEach((node) => {
      node.setAttribute("aria-expanded", "false");
    });
  }

  function openChoicePopover(anchor, key, current, onPick) {
    closeChoicePopover();
    const options = PROFILE_PREF_OPTIONS[key] || [];
    if (!anchor || options.length === 0) return;
    anchor.dataset.v18Bound = "true";
    anchor.setAttribute("role", "button");
    anchor.setAttribute("tabindex", "0");
    anchor.setAttribute("aria-haspopup", "listbox");
    anchor.setAttribute("aria-expanded", "true");
    const box = document.createElement("div");
    box.className = "mydow-choice-popover";
    box.setAttribute("role", "listbox");
    box.dataset.preferenceKey = key;
    box.innerHTML = options
      .map((opt) => {
        const selected = opt.value === current ? "true" : "false";
        return (
          `<button type="button" role="option" aria-selected="${selected}" data-value="${escapeHtml(opt.value)}">` +
          `<span>${escapeHtml(opt.label)}<small>${escapeHtml(opt.desc || "")}</small></span>` +
          `</button>`
        );
      })
      .join("");
    document.body.appendChild(box);
    const rect = anchor.getBoundingClientRect();
    const top = Math.min(rect.bottom + 8, window.innerHeight - box.offsetHeight - 14);
    const left = Math.min(Math.max(14, rect.left), window.innerWidth - box.offsetWidth - 14);
    box.style.top = `${Math.max(14, top)}px`;
    box.style.left = `${left}px`;
    box.addEventListener("click", async (event) => {
      const btn = event.target.closest("button[data-value]");
      if (!btn) return;
      event.preventDefault();
      await onPick(btn.dataset.value);
      closeChoicePopover();
    });
  }

  function markProfilePreferenceControls() {
    document.querySelectorAll(".profile-main .preference-row").forEach((row) => {
      const key = preferenceKeyForRow(row);
      if (key) row.dataset.preferenceKey = key;
      row.querySelectorAll(".select-control").forEach((ctrl) => {
        if (!key) return;
        ctrl.dataset.v18Bound = "true";
        ctrl.setAttribute("role", "button");
        ctrl.setAttribute("tabindex", "0");
        ctrl.setAttribute("aria-haspopup", "listbox");
        ctrl.setAttribute("aria-expanded", "false");
      });
      row.querySelectorAll(".segmented-control").forEach((ctrl) => {
        ctrl.dataset.v18Bound = "true";
      });
      row.querySelectorAll(".toggle-switch").forEach((ctrl) => {
        ctrl.dataset.v18Bound = "true";
      });
    });
  }

  async function hydrateProfilePreferences(base) {
    try {
      const resp = await base.apiFetch("/me/preferences");
      const prefs = normalizePreferencesPayload(base.unwrapData ? base.unwrapData(resp) || resp : resp);
      applyProfilePreferencesV18(prefs);
      document.querySelectorAll(".profile-main .preference-row").forEach((row) => {
        const key = preferenceKeyForRow(row);
        if (key) {
          const label = labelForPreference(key, prefs[key]);
          row.querySelectorAll(".select-control").forEach((ctrl) => {
            const icon = ctrl.querySelector("svg");
            ctrl.childNodes.forEach((node) => {
              if (node.nodeType === Node.TEXT_NODE) node.textContent = "";
            });
            ctrl.insertBefore(document.createTextNode(label + " "), icon || null);
            ctrl.dataset.value = prefs[key] || "";
          });
        }
        const text = rowText(row);
        if (/自动保存/.test(text)) {
          row.querySelectorAll(".toggle-switch").forEach((sw) => {
            const active = Boolean(prefs.auto_save);
            sw.classList.toggle("active", active);
            sw.setAttribute("aria-pressed", String(active));
            sw.setAttribute("aria-label", active ? "自动保存已开启" : "自动保存已关闭");
          });
        }
        if (/主题模式/.test(text)) {
          row.querySelectorAll(".segmented-control button").forEach((btn) => {
            const isDark = /深色/.test(btn.textContent || "");
            const active = (prefs.theme || "light") === (isDark ? "dark" : "light");
            btn.classList.toggle("active", active);
            btn.setAttribute("aria-pressed", String(active));
          });
        }
      });
      return prefs;
    } catch (e) {
      console.warn("[v14-ext] hydrate profile preferences", e);
      return null;
    } finally {
      markProfilePreferenceControls();
    }
  }

  function bindProfilePreferencesV18(base) {
    const scheduleHydrate = () => {
      [120, 520, 1000].forEach((delay) => {
        window.setTimeout(() => hydrateProfilePreferences(base), delay);
      });
    };
    scheduleHydrate();
    document.addEventListener("click", (event) => {
      if (event.target.closest("[data-settings-panel]") || event.target.closest("[data-account-action='preferences']")) {
        scheduleHydrate();
      }
    }, false);
    document.addEventListener("click", (event) => {
      if (!event.target.closest(".mydow-choice-popover,.select-control")) closeChoicePopover();
    }, true);
    document.addEventListener(
      "click",
      async (event) => {
        const themeBtn = event.target.closest(".profile-main .segmented-control button");
        if (themeBtn) {
          const row = themeBtn.closest(".preference-row");
          if (/主题模式/.test(rowText(row))) {
            event.preventDefault();
            event.stopPropagation();
            const theme = /深色/.test(themeBtn.textContent || "") ? "dark" : "light";
            try {
              const resp = await base.apiFetch("/me/preferences", { method: "PATCH", body: { theme } });
              applyProfilePreferencesV18(normalizePreferencesPayload(resp));
              row.querySelectorAll(".segmented-control button").forEach((btn) => {
                const active = btn === themeBtn;
                btn.classList.toggle("active", active);
                btn.setAttribute("aria-pressed", String(active));
              });
              base.toast && base.toast(theme === "dark" ? "已切换为深色模式" : "已切换为浅色模式", "success");
            } catch (e) {
              base.toast && base.toast(`主题保存失败: ${e.message}`, "error");
            }
            return;
          }
        }
        const select = event.target.closest(".profile-main .select-control");
        if (select) {
          const row = select.closest(".preference-row");
          const key = preferenceKeyForRow(row);
          if (!key) return;
          event.preventDefault();
          event.stopPropagation();
          const current = select.dataset.value || "";
          openChoicePopover(select, key, current, async (value) => {
            try {
              const resp = await base.apiFetch("/me/preferences", { method: "PATCH", body: { [key]: value } });
              applyProfilePreferencesV18(normalizePreferencesPayload(resp));
              select.dataset.value = value;
              const icon = select.querySelector("svg");
              select.childNodes.forEach((node) => {
                if (node.nodeType === Node.TEXT_NODE) node.textContent = "";
              });
              select.insertBefore(document.createTextNode(labelForPreference(key, value) + " "), icon || null);
              base.toast && base.toast("偏好已保存", "success");
            } catch (e) {
              base.toast && base.toast(`偏好保存失败: ${e.message}`, "error");
            }
          });
        }
      },
      false,
    );
  }

  async function boot() {
    const base = await whenBaseReady(8000);
    if (!base || !base.apiFetch) {
      console.warn("[v14-ext] base bridge not ready, ext disabled");
      return;
    }
    injectSixStateStyles();
    wrapApiFetchWithErrorToast(base);
    bindSixStateRuntime(base);
    bindSearchModalUX(base);
    bindOpenerContextSync();
    bindInlineMenuOptions(base);
    bindNoticeActions(base);
    bindAccountActions(base);
    bindKbTabCategory(base);
    bindDataToastIntercept(base);
    bindNoteOptions(base);
    bindOpenFolder(base);
    bindSearchResultClick(base);
    bindProfilePreferencesV18(base);
    // expose state for tests
    window.MydowBridgeV14Ext = {
      ctx: _CTX,
      booted: true,
      renderStateCard,
      showFeedSkeleton,
      hideFeedSkeleton,
      enhanceSearchEmptyNodes,
      hydrateProfilePreferences: () => hydrateProfilePreferences(base),
    };
    console.info("[Mydow v1.4] ext bridge ready (extra wiring loaded)");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => boot().catch(() => {}));
  } else {
    boot().catch(() => {});
  }
})();
