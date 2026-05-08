# SPA 接入手册（给工程师 2 的 SPA 重写直接用）

> **作者**：Agent 4。
> **目的**：工程师 2 在重写 `static/mydow/{index.html,app.js,style.css}` 时，直接对照本文写渲染器与状态机，不需要再回 PRD10 与后端代码间反复跳转。
> **不变量**：PRD10 是产品标准；本手册只汇总当前已落地的后端契约，**不引入新 API**。如某项与 `docs/01-prd/PRD10.md` 冲突，以 PRD10 为准。
> **基础约定**：
> - Base URL：`/api/v1`
> - 鉴权：`Authorization: Bearer <jwt>`，`localStorage["mydow_token"]`
> - 响应统一信封：`{ "success": true, "data": ..., "request_id": "..." }`
> - 错误信封：`{ "success": false, "error": { "code", "message", "details" }, "request_id": "..." }`
> - 错误码：`UNAUTHORIZED(401) FORBIDDEN(403) NOT_FOUND(404) VALIDATION_ERROR(400) RATE_LIMITED(429) INTERNAL_ERROR(500) AI_PROVIDER_ERROR(502) JOB_FAILED(500)`
> - 时间：ISO 8601 UTC 字符串
> - 分页：`{ items, pagination: { page, page_size, total, has_more } }`
> - SPA 路由建议（hash）与首屏接口在 §6。

---

## 0. 一键起 demo（开发期前端必用）

```pwsh
# 后端环境
$env:DATABASE_URL = "sqlite+aiosqlite:///d:/Codes/whyme/.tmp/smoke.db"
$env:AGENTOS_PRD10_WORKER = "on"
$env:AGENTOS_PRD10_WORKER_INTERVAL = "2"
$env:AGENTOS_DEMO_MODE = "on"
$env:AGENTOS_AI_LLM = "off"           # 切真 LLM 时改 "on"
$env:PYTHONPATH = "d:/Codes/whyme/src"

# 一次性 seed（PRD10 §25.3 测试数据）
python scripts/seed_prd10.py --email demo@mydow.example --password demo123 --reset

# 起服务
python -m uvicorn agent_os.server.app:app --host 127.0.0.1 --port 8000
```

SPA 启动时**先调 demo 状态**，决定要不要跳过登录页：

| 步骤 | 调用 | 说明 |
|---|---|---|
| 1 | `GET /api/v1/demo/status` | `{ enabled, email }`；不带鉴权 |
| 2 (enabled) | `POST /api/v1/demo/login` | 返回 `{ access_token, refresh_token, token_type, expires_in }`，懒创建 demo 用户 |
| 2 (disabled) | 渲染登录表单 → `POST /api/v1/auth/login` | `{ username, password }` → `{ access_token, ... }` |

写入 `localStorage["mydow_token"]` 后所有后续请求带 Authorization。

---

## 1. 数据契约速查（按 PRD10 §5）

> **以「字段 ← 来源」标注**：DTO 字段名 ← DB/Service 提供。空字段在前端必须显示「空态」而不是「错误」。

### 1.1 User（`/me`）

```
{
  id: uuid, email, username, full_name?, role, locale?, timezone?,
  plan?, avatar_url?, settings?, created_at, updated_at
}
```

### 1.2 InboxItem（`prd10_inbox_items`）

```
{
  id, user_id, type, title?, raw_content?, source_url?, source_id?, target_folder_id?,
  status: 'received'|'processing'|'processed'|'archived'|'failed',
  processing_status: 'queued'|'running'|'completed'|'failed',
  priority: 'low'|'normal'|'high'|'urgent',
  auto_process: bool, tags: string[], extra: object,
  job_id?, created_at, updated_at
}
```

枚举：`type ∈ text | link | file | image | audio | video | manual_task`。

### 1.3 Source（`prd10_sources`）

```
{ id, user_id, type, name, url, mime_type?, size_bytes?, checksum?, parse_status, metadata, created_at }
```

### 1.4 Card（`cards`，§5.5 字段已扩齐）

```
{
  id, user_id, workspace_id?, title, summary?, cover_url?, content?,
  content_type: 'note'|'article'|'file'|'image'|'audio'|'task'|'ai_output'|'report',
  source_id?, inbox_item_id?, folder_id?, tags: string[], entities: string[],
  is_favorite, is_archived, visibility: 'private'|'shared'|'public',
  created_at, updated_at, deleted_at?
}
```

### 1.5 Folder（`kb_folders`）

```
{ id, user_id, parent_id?, name, description?, icon?, color?, document_count, card_count, is_favorite, sort_order, created_at, updated_at }
```

### 1.6 Document（`kb_documents`）

```
{
  id, user_id, folder_id?, source_id?, title, summary?, content?,
  document_type: 'note'|'markdown'|'pdf'|'docx'|'pptx'|'image'|'audio'|'link'|'ai_output',
  status: 'processing'|'ready'|'failed'|'archived',
  tags: string[], word_count, chunk_count, is_favorite,
  last_opened_at?, created_at, updated_at
}
```

### 1.7 AIConversation / AIMessage（`ai_conversations`, `ai_messages`）

```
Conversation: { id, user_id, title, mode, last_message_preview, message_count, context_scope, created_at, updated_at }
Message:      { id, conversation_id, user_id, role: 'user'|'assistant'|'system', content,
                status: 'queued'|'running'|'completed'|'failed', citations[], tool_calls[],
                attachments[], parent_message_id?, model?, input_tokens?, output_tokens?,
                latency_ms?, created_at }
```

### 1.8 Skill / SkillRun（`skills`, `skill_runs`）

```
Skill:    { id, name, description, category, icon, status, usage_count, is_installed_default,
            input_schema, output_schema }
SkillRun: { id, skill_id, user_id, job_id, input, output?, status, created_at }
```

### 1.9 Job（`prd10_jobs`） & Notification（`prd10_notifications`）

```
Job:          { id, user_id, job_type, status: 'queued|running|completed|failed|canceled',
                progress (0-100), input, output?, error?, correlation_id?, created_at, updated_at,
                started_at?, completed_at? }
Notification: { id, user_id, type, title, content, object_type?, object_id?, is_read, created_at }
```

`job_type` 全集：`parse_file | summarize | embed | index | generate_insight | generate_report | ai_chat | skill_run`。

### 1.10 Insight（`prd10_insights`）

```
{ id, user_id, title, summary?, insight_type: 'theme_trend'|'task_risk'|'knowledge_gap'|'connection'|'daily_summary'|'weekly_summary',
  confidence (0-1), related_card_ids: string[], related_document_ids: string[], actions: object[],
  status: 'active'|'dismissed'|'archived', created_at }
```

---

## 2. SPA 路由 → 首屏接口矩阵（按 PRD10 §25.1）

| SPA hash | 首屏必调（顺序） | 备注 |
|---|---|---|
| `#/today` | `GET /me` → `GET /today` → `GET /feed?page_size=20` → `GET /insights/summary` → `GET /notifications/unread-count` | 5 个并发都可，但 SPA 状态机以 `/today` 完成为准 |
| `#/kb` | `GET /kb/overview` → `GET /kb/folders?include_counts=true` → `GET /kb/documents?page_size=20` | 文件夹网格用 `/folders`，document panel 用 `/documents` |
| `#/kb/folder/:folder_id` | `GET /kb/folders` → `GET /kb/documents?folder_id=:folder_id` | 文件夹列表整体加载即可，路由的高亮通过本地状态切换 |
| `#/kb/doc/:document_id` | `GET /kb/documents/:id` | 抽屉式打开；返回里包含 `chunks_preview` `related_cards` `ai_suggestions` |
| `#/ai` | `GET /ai/conversations?page_size=20` | 空态时引导用户 `POST /ai/conversations` 创建第一个会话 |
| `#/ai/:conversation_id` | `GET /ai/conversations/:id` | 包含 `messages[]` 和 `related_context`；后续发消息走 §3.4 |
| `#/skills` | `GET /skills?page_size=20` | 列表卡片 → 点开走详情 |
| `#/skill/:skill_id` | `GET /skills/:id` | 抽屉/页面展示 input/output schema、运行历史 |
| `#/garden` | `GET /garden/overview` → `GET /garden/graph?limit=200` | 节点+边渲染；点节点可触发 `/search?q=:label` |
| `#/notifications` | `GET /notifications?page_size=50` | 全部已读走 §5 |
| `#/settings/*` | `GET /me`（其他子页面无新 API） | 设置项的提交目前都是 stub；保留 toast |
| 全局搜索弹窗 | `GET /search/suggestions?q=:prefix` (debounced 300ms) → 命中后 `GET /search?q=:q&page_size=20` | 弹窗关闭即停 polling |

---

## 3. 域接口完整清单（按 PRD10 §7-§18）

### 3.1 Capture / Inbox（§8）

| 方法 | 路径 | 入参（关键） | 出参（关键） |
|---|---|---|---|
| POST | `/capture/text` | `{ content, title?, tags?[], target_folder_id?, type?, auto_process? }` | `{ inbox_item, job }` |
| POST | `/capture/link` | `{ url, note?, tags?[], auto_process? }` | `{ inbox_item_id, source_id, job_id, fetch_status }` |
| POST | `/uploads/presign` | `{ filename, mime_type, size_bytes }` | `{ upload_id, upload_url, upload_method, file_url, expires_in }` |
| PUT | `/uploads/local/{upload_id}` | `Content-Type: <mime>` + bytes | 200 |
| GET | `/uploads/local/{upload_id}/raw` | — | bytes（用于 `<img>` `<a>`） |
| POST | `/capture/file/commit` | `{ upload_id, filename, mime_type, size_bytes, target_folder_id?, auto_process? }` | `{ source_id, document_id, job_id, status }` |
| GET | `/inbox?type=&status=&keyword=&page=&page_size=` | — | `{ items[], pagination }` |
| PATCH | `/inbox/{id}` | `{ status?, tags?, priority?, title?, target_folder_id? }` | `{ inbox_item }` |

> **状态机**：`auto_process=true` 时 SPA 读到 `processing_status=queued` → 应订阅 `/notifications/stream` 或 2s 轮询 `/jobs/{job_id}` 直到 `completed`。

### 3.2 Feed / Cards（§9）

| 方法 | 路径 | 备注 |
|---|---|---|
| GET | `/feed?view=&type=&sort_by=&sort_order=&tag=&date_range=&page=&page_size=` | 含 `facets.types[]` `facets.tags[]` |
| GET | `/cards/{id}` | — |
| POST | `/cards` | `{ title, summary?, content?, content_type, folder_id?, tags?[] }` |
| PATCH | `/cards/{id}` | 任意 5.5 字段子集 |
| DELETE | `/cards/{id}` | 软删除 |
| POST | `/cards/{id}/favorite` | `{ is_favorite }` |

### 3.3 Knowledge Base（§10）

| 方法 | 路径 | 备注 |
|---|---|---|
| GET | `/kb/overview` | `{ stats, recent_documents, favorite_folders }` |
| GET | `/kb/folders?parent_id=&keyword=&include_counts=&is_favorite=&sort_by=` | `is_favorite=true`：仅收藏文件夹；`sort_by=updated_at`：按 `updated_at` 降序（「最近」视图）。响应 `data.items` 不带 pagination（特例） |
| POST | `/kb/folders` | `{ name, description?, parent_id?, color? }` |
| PATCH | `/kb/folders/{id}` | `{ name?, description?, is_favorite?, sort_order? }` |
| DELETE | `/kb/folders/{id}` | body `{ strategy: 'move_to_root'|'delete_children' }` |
| GET | `/kb/documents?folder_id=&document_type=&keyword=&tag=&status=&sort_by=&sort_order=&page=&page_size=` | — |
| GET | `/kb/documents/{id}` | 含 `chunks_preview[]` `related_cards[]` `ai_suggestions[]` |
| PATCH | `/kb/documents/{id}` | `{ title?, summary?, content?, folder_id?, tags?, is_favorite? }` |
| DELETE | `/kb/documents/{id}` | 软删除 |
| POST | `/kb/documents/{id}/move` | `{ target_folder_id }` |

### 3.4 Mydow AI（§11）

| 方法 | 路径 | 备注 |
|---|---|---|
| GET | `/ai/conversations?keyword=&page=&page_size=` | — |
| POST | `/ai/conversations` | `{ title?, mode?, context_scope? }` |
| GET | `/ai/conversations/{id}` | 含 `messages[]` `related_context[]` |
| POST | `/ai/conversations/{id}/messages` | `{ content, attachments?, context_scope?, stream? }`，非流式直返 placeholder/真 LLM |
| **POST** | **`/ai/conversations/{id}/messages/stream`** | **SSE：`text/event-stream`，事件 `meta`/`token`/`done` 或 PRD10 §11.4 的 `message.delta`/`message.citation`/`message.completed`/`message.error`**。需要 `AGENTOS_AI_LLM=on` 时才返回真模型 token；否则回 placeholder |
| POST | `/ai/messages/{id}/save-to-kb` | `{ folder_id?, title?, tags?[] }` → 入 `Job(parse_file, kind=ai_message_to_kb)` |
| POST | `/ai/messages/{id}/create-tasks` | `{ tasks: [{ title, due_at?, priority? }] }` → 入 `Job(generate_report, kind=ai_message_to_tasks)` |

> **SSE 客户端最小实现**：`new EventSource(url, { headers: ... })` 不支持自定义头；用 `fetch` + `ReadableStream` + `TextDecoder` 解析 `event:` `data:` 行。后端在 `AGENTOS_AI_LLM=off` 时仍会发出固定 placeholder token；测试 fixture 见 `tests/integration/api/test_prd10_ai_llm.py`。

### 3.5 Insights & Reports（§12）

| 方法 | 路径 | 备注 |
|---|---|---|
| GET | `/insights/summary?range=today\|week\|month\|all&source=` | `{ stats, theme_distribution[], quality_distribution[], insights[], recommended_actions[] }` |
| GET | `/insights?insight_type=&status=&range=&page=&page_size=` | — |
| POST | `/insights` | `{ insight_type, title, summary?, confidence?, related_card_ids?[], related_document_ids?[], actions?[] }` |
| POST | `/insights/{id}/dismiss` | — |
| POST | `/reports/generate` | `{ report_type: 'daily'|'weekly'|'monthly', time_range, include_sources?, save_to_kb? }` → `{ job_id, status }` |
| GET | `/reports/{id}` | — |

### 3.6 Search（§13）

| 方法 | 路径 | 备注 |
|---|---|---|
| GET | `/search?q=&type=&mode=hybrid\|semantic\|keyword&page=&page_size=` | 命中带 `highlight` `score` `url`；`semantic` / `hybrid` 已使用 `SearchIndex.embedding` 持久向量排序，hybrid = 70% vector + 30% lexical |
| GET | `/search/suggestions?q=&limit=` | `[ { type: 'command'|'document'|'card'|..., label, command?, object_id? } ]` |

### 3.7 Tasks（§14）

| 方法 | 路径 | 备注 |
|---|---|---|
| GET | `/tasks?status=&priority=&due_range=&source_type=&page=&page_size=` | PRD10 §14.1；真实表 `prd10_tasks`，返回分页 envelope |
| POST | `/tasks` | `{ title, description?, priority?, status?, due_at?, source_type?, source_id?, tags?, extra? }` |
| GET | `/tasks/{id}` | 只返回当前用户未删除任务 |
| PATCH | `/tasks/{id}` | 局部更新 title/status/priority/due_at/tags/extra 等 |
| POST | `/tasks/{id}/complete` | 设置 `status='done'` 并写 `completed_at` |
| DELETE | `/tasks/{id}` | 软删除，返回 `{ id, deleted: true }` |
| 首页入口 | `/today` 的 `data.tasks[]` | 同样由 `prd10_tasks` 派生；不再走 `Prd10InboxItem(type=manual_task)` 替代方案 |

### 3.8 Notifications（§15）

| 方法 | 路径 | 备注 |
|---|---|---|
| GET | `/notifications/unread-count` | `{ count }` |
| GET | `/notifications?is_read=&type=&page=&page_size=` | — |
| POST | `/notifications/{id}/read` | — |
| POST | `/notifications/read-all` | `{ updated }` |
| **GET (SSE)** | **`/notifications/stream`** | **SSE 推送新通知；Windows + ASGITransport 测试链有兼容问题，但产线 uvicorn 已通过 Chrome MCP 实测** |

### 3.9 Jobs（§16）

| 方法 | 路径 | 备注 |
|---|---|---|
| GET | `/jobs/{id}` | `{ job_type, status, progress, error? }` |
| POST | `/jobs/{id}/cancel` | 终态 job 返回 `VALIDATION_ERROR` |

> **轮询策略**：`queued/running` 每 2s；超 60s 退化为 5s；`completed/failed/canceled` 停止。

### 3.10 Skills（§17）

| 方法 | 路径 | 备注 |
|---|---|---|
| GET | `/skills?category=&keyword=&status=&page=&page_size=` | 排序：`usage_count DESC` |
| GET | `/skills/{id}` | 返回 input/output schema |
| POST | `/skills/{id}/run` | `{ input, save_output? }` → `{ job_id, skill_run_id, status }` |

> **空库场景**：空列表时后端会自动 seed 一个 `Mydow 快速总结` skill（见 Agent 3 task 3.7）；SPA 不需要为「skills 列表为空」做特殊处理。

### 3.11 Garden（§18）

| 方法 | 路径 | 备注 |
|---|---|---|
| GET | `/garden/overview` | `{ node_count, edge_count, strong_edge_count, top_topics[], recent_insights[] }` |
| GET | `/garden/graph?range=&topic=&depth=&limit=` | `{ nodes[], edges[] }` |

### 3.12 Auth（PRD0/PRD5/PRD6）

| 方法 | 路径 | 备注 |
|---|---|---|
| POST | `/auth/register` | `{ username, email, password }` → `Token` |
| POST | `/auth/login` | `{ username (= email or username), password }` → `Token` |
| POST | `/auth/refresh` | `{ refresh_token }` |
| POST | `/auth/send-code` `/auth/verify-code` `/auth/register/email` `/auth/login/email` | 邮箱验证码登录注册（`PRD5/PRD6`） |
| GET | `/me` | 当前用户 |
| PUT | `/auth/settings` | 用户偏好 |
| **GET** | **`/api/v1/demo/status`** | demo 模式探针 |
| **POST** | **`/api/v1/demo/login`** | demo 一键登录（`AGENTOS_DEMO_MODE=on`） |

---

## 4. 状态机模板（每页都要写完整）

PRD10 §20 要求 5 种状态都得画。SPA 渲染器最小套路：

```js
// 伪代码：每个 panel 一份
const PanelState = {
  idle: 'idle',         // 未挂载
  loading: 'loading',   // 调中：渲染骨架屏
  empty: 'empty',       // 200 + items=[]：渲染空态卡
  ready: 'ready',       // 200 + items.length>0：正常列表
  forbidden: 'forbidden', // 403：渲染权限提示
  error: 'error',       // 4xx/5xx：渲染错误卡 + retry
  processing: 'processing', // job queued/running：渲染进度条
};
```

| 接口出 `success: false` | UI 切到 | 文案来源 |
|---|---|---|
| `error.code === 'UNAUTHORIZED'` | 退到登录态 | `error.message` |
| `error.code === 'FORBIDDEN'` | `forbidden` | `error.message` |
| `error.code === 'NOT_FOUND'` | `empty`（路由错时） | 静态 |
| `error.code === 'VALIDATION_ERROR'` | 表单错位标红 | `error.details.field` |
| `error.code === 'AI_PROVIDER_ERROR'` | `error` + 可重试 | `error.message` |
| `error.code === 'JOB_FAILED'` | `error` + 可重新触发 | `error.message` |

---

## 5. 实时刷新策略

| 触发 | 推荐做法 |
|---|---|
| Capture 提交后 inbox/feed 同步 | A：`POST /capture/text` 后 200 立即把 `inbox_item` 乐观插入；B：`/notifications/stream` 收到 `record_processed`/`document_ready`/`ai_output_saved` 后局部刷新；C：兜底 30s 轮询 `/feed?page=1&page_size=20` |
| AI saveToKb 后 KB 刷新 | 监听 `/notifications/stream` 的 `ai_output_saved` 事件 → 调 `GET /kb/documents?page=1&sort_by=created_at` |
| Skill run 后看运行结果 | `POST /skills/{id}/run` 拿 `job_id` → 2s 轮 `/jobs/{job_id}` 直到 `completed`/`failed` → 若 `save_output=true` 跳到 `/kb/documents?keyword=skill_run` |
| Notifications 红点 | `/notifications/unread-count`：进入页面拉一次 + 每 30s 轮询 + SSE push 时立即刷新 |

---

## 6. SPA 路由 hash 与 PRD10 路由对照（建议）

```
#/today                 → GET /today + 首屏 5 套
#/kb                    → /kb/overview + /kb/folders（默认）
#/kb/folder/:id         → /kb/folders + /kb/documents?folder_id
#/kb/doc/:id            → /kb/documents/:id（抽屉打开）
#/ai                    → /ai/conversations
#/ai/:cid               → /ai/conversations/:cid + send 时走 /messages
#/skills                → /skills
#/skill/:id             → /skills/:id
#/garden                → /garden/overview + /garden/graph
#/notifications         → /notifications
#/search/:q             → /search + /search/suggestions
#/settings/profile      → /me（修改 stub）
```

---

## 7. 渲染器骨架（建议结构）

```
static/mydow/
├── index.html           # 仅装载点 + 主题 css 引用
├── style.css            # 设计令牌（color/font/space/shadow）
├── app.js               # 入口：HashRouter + AuthBoot + Layout
├── api.js               # = 现 mydow-api.js 的 fetch + domain client（保留）
├── views/
│   ├── today.js
│   ├── kb.js
│   ├── kb-folder.js
│   ├── kb-doc.js
│   ├── ai-list.js
│   ├── ai-chat.js
│   ├── skills.js
│   ├── skill-detail.js
│   ├── garden.js
│   ├── notifications.js
│   ├── search.js
│   └── settings.js
└── components/
    ├── nav-sidebar.js
    ├── topbar-search.js
    ├── notif-button.js
    ├── insight-rail.js
    ├── modal.js
    ├── toast.js
    ├── card.js
    ├── empty.js
    ├── error.js
    └── skeleton.js
```

每个 view 默认导出：

```js
export default {
  async mount(root, params) { /* 渲染 + 拉数据 + 绑事件 */ },
  unmount() { /* 取消订阅、停轮询 */ }
};
```

`app.js` 用 `import('./views/today.js').then(m => m.default.mount(root, params))` 做 ESM 动态加载，路由切换时调 unmount。

---

## 8. 已知坑（前端必读）

1. `/kb/folders` 当前响应 **`data.items` 没有 pagination**——其他列表都有。
2. `/me` 的 EmailStr 校验拒绝 `.local` 后缀，所以 demo email 用 `demo@mydow.example` 而非 `demo@whyme.local`。
3. `/auth/login` 旧 endpoint **不返回 PRD10 envelope**，直接返回 `Token` 模型；SPA 需要兼容两种形态：`resp.access_token` 或 `resp.data.access_token`。
4. SSE 在 Windows + ASGITransport 链上有死锁，但**产线 uvicorn 没问题**。SPA 不需要测试这个，工程师 1/2 已经在跟。
5. `/api/v1/tasks` 已是 PRD10 §14 canonical 路径（UUID user 隔离 + envelope）；历史 `Prd10InboxItem(type=manual_task)` 仅保留为兼容旧 worker/旧视图的过渡记录。
6. `/api/v1/skills` 空库时会自动 seed 一个 `Mydow 快速总结` Skill（避免 SPA 打开 Skills 页面是空白）。
7. AI 流式接口需要 `AGENTOS_AI_LLM=on` 才返回真模型 token，否则回 placeholder。
8. Worker 间隔默认 30s（生产）/ 2s（demo）。SPA 不要假设 capture 后立刻能在 KB 看到——必须看 `processing_status` 或订阅通知。

---

## 9. 测试口径（工程师 2 写完 SPA 后回归用）

```pwsh
# 后端 acceptance 套件
python -m pytest `
  tests/integration/api/test_prd10_v1_acceptance.py `
  tests/integration/api/test_prd10_frontend_binding.py `
  tests/integration/api/test_prd10_ai_api.py `
  tests/integration/api/test_prd10_ai_llm.py `
  tests/integration/api/test_prd10_search_api.py `
  tests/integration/api/test_prd10_skills_api.py `
  tests/integration/api/test_prd10_garden_api.py `
  tests/integration/api/test_prd10_observability.py `
  tests/integration/api/test_prd10_app_wiring.py `
  tests/integration/api/test_prd10_models_intelligence.py `
  tests/integration/api/test_prd10_e2e_flow.py `
  tests/integration/api/test_prd10_product_data_api.py `
  tests/integration/api/test_prd10_insights_api.py `
  tests/integration/api/prd10/ `
  -q -p no:cacheprovider
```

工程师 2 重写完 SPA 必须保证：
- 上面这套数字不下降；
- `tests/integration/api/test_prd10_frontend_binding.py` 的静态契约重写一份（DOM hooks 名字会变，但**对 PRD10 路由的依赖**不能少）。

---

## 10. 协作约定

- **Agent 4 在 SPA 重写期不会修改** `static/mydow/` 任何 JS/HTML/CSS、`auth/router.py:demo_router`、`mydow-api.js`；如发现冲突第一时间停手。
- **新增前端文件**统一放进上面 §7 的目录结构。
- 任何 SPA 渲染需要后端**新加字段或端点**时，先在 `agent-progress-report.md` 写一条 Milestone，再让 Agent 1/2/3 评估；不要私改 router/DTO。
