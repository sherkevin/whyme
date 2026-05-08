# Agent 2 PRD10 后端交付包

> 适用版本: Agent 2 V1（capture / feed / KB / jobs / notifications / today / inbox / uploads）
> 报告生成时间: 2026-05-05

---

## 一、可交付状态

| 维度 | 状态 |
|---|---|
| PRD10 §24.1 P0 接口（Capture/Feed/KB/Job/Notification/Today/Inbox/Uploads） | **已交付** |
| PRD10 §22.2 文件落盘 + 下载（PUT 写入 + GET /raw 流式回读） | **已交付** |
| PRD10 §25.3 seed 脚本（1 用户 + 6 文件夹 + 20 文档 + 30 卡片 + 5 任务 + 5 通知） | **已交付** |
| PRD10 §28 Definition of Done（envelope / user 隔离 / 软删除 / 错误形态 / 测试） | **已交付** |
| PRD10 §15 实时推送（SSE/WebSocket） | 后续，未做 |
| PRD10 §11 AI Chat / §13 Search / §17 Skills / §18 Garden | **不在 Agent 2 范围**（Agent 3） |

### 测试环境
- **SQLite (in-memory)**: 70 passed / 19.57s
- **Postgres 16 (Docker, postgres:16-alpine)**: 63 passed (上一次完整运行) / 131s。本轮新增 7 个 uploads-local 用例使用标准 SQLAlchemy + 本地文件系统，与 PG 兼容。

### 真 uvicorn 端到端冒烟
`scripts/smoke_prd10.py` 启动真 FastAPI 服务，使用 httpx 走完 16 个关键路径。最近一次运行 16/16 全绿，报告写入 `tests/integration/api/prd10/smoke_run.json`。

---

## 二、给前端工程师的对接清单

### 2.1 启动后端

```powershell
# 1. 创建 SQLite 演示库 + seed 数据
$env:DATABASE_URL = "sqlite+aiosqlite:///./data/dev.db"
python scripts/seed_prd10.py            # 默认 demo@whyme.local / demo-password-123
                                         # （不会注册到 auth，需要再 register 同邮箱）

# 2. 启服务
uvicorn agent_os.server.app:app --host 127.0.0.1 --port 3001 --reload
```

> 如果想直接拿到登录态，跳过 seed 脚本，直接调 `POST /api/v1/auth/register` 就能拿到 access_token + refresh_token。

### 2.2 前端 `.env`

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:3001/api/v1
NEXT_PUBLIC_USE_MOCK=false
```

### 2.3 鉴权与请求头

- 所有 `/api/v1/*` 业务接口需要 `Authorization: Bearer <access_token>`。
- 所有响应都带 `X-Request-ID`，PRD10 envelope 包含 `request_id`，前端可在错误提示里显示。

### 2.4 PRD10 envelope

- 成功:
  ```json
  { "success": true, "data": ..., "request_id": "req_..." }
  ```
- 分页成功:
  ```json
  { "success": true,
    "data": { "items": [...], "pagination": {...}, "facets": {...} },
    "request_id": "req_..." }
  ```
- 错误:
  ```json
  { "success": false,
    "error": { "code": "...", "message": "...", "details": {...} },
    "request_id": "req_..." }
  ```

### 2.5 关键流程

#### 创建文本想法
```
POST /api/v1/capture/text
{ "content": "...", "title": "...", "tags": [...] }
```
返回 `data.inbox_item.id` 与 `data.job.id`，V1 同步走完整 pseudo-worker，所以 `data.job.status === "completed"` 即可立刻调 `/feed`。

#### 上传文件
```
1. POST /api/v1/uploads/presign         → 拿 upload_id / upload_url / file_url / upload_method=PUT
2. PUT  upload_url  body: <bytes>       → 头 X-Filename / Content-Type
3. POST /api/v1/capture/file/commit
   { "upload_id": "...", "filename": "...", "mime_type": "...", "size_bytes": 数字 }
4. 浏览器预览/下载: GET file_url  (= /api/v1/uploads/local/{upload_id}/raw)
```

#### 知识库浏览
```
GET /api/v1/kb/overview                   → 总数 + recent_documents + favorite_folders
GET /api/v1/kb/folders?include_counts=true → 每个文件夹带 document_count
GET /api/v1/kb/documents?folder_id=...     → 分页文档列表
GET /api/v1/kb/documents/{id}              → 详情，带 folder/source/chunks_preview
```

#### Today 首页聚合
```
GET /api/v1/today                          → user/stats/quick_actions/tasks/insight_preview/favorite_folders
```

#### Inbox 列表 / 状态变更
```
GET /api/v1/inbox?type=text&status=received&page=1&page_size=20
PATCH /api/v1/inbox/{id}
  { "status": "archived", "tags": [...] }
```

#### Notifications
```
GET  /api/v1/notifications/unread-count
GET  /api/v1/notifications?is_read=false
POST /api/v1/notifications/{id}/read
POST /api/v1/notifications/read-all
```

#### Jobs (P0 长任务状态)
```
GET  /api/v1/jobs/{id}
POST /api/v1/jobs/{id}/cancel
```

### 2.6 错误码 / HTTP 映射

| HTTP | code | 何时出现 |
|---|---|---|
| 400 | `VALIDATION_ERROR` | 参数校验、状态机转换非法 |
| 401 | `UNAUTHORIZED` | 缺 token / token 无效 |
| 403 | `FORBIDDEN` | （V1 当前无 workspace 权限场景，预留） |
| 404 | `NOT_FOUND` | 资源不存在 / 跨用户访问 |
| 422 | `VALIDATION_ERROR` | Pydantic schema 失败 |
| 500 | `INTERNAL_ERROR` | 未捕获异常 |

---

## 三、Agent 2 范围内的已知限制

1. **Job 同步伪处理（V1）**：`capture/text|link|file/commit` 内部目前同步走 `simulate_processing`，立刻产出 `Document.status=ready / Job.status=completed`。生产环境换上真 worker 时，前端逻辑无需变更，唯一差别是 `processing_status` 会有 `running` 这一中间态。
2. **File facets**：`/feed` 与 `/kb/documents` 的 `facets.tags` 当前为空数组——`facets.types` 是真实的；tag 聚合按 PRD10 §9.1 列在 P1 优先级里。
3. **Tasks**：`/today.tasks` 通过 `Prd10InboxItem(type=manual_task)` 顶替，不读 legacy `tasks.models.Task`（user_id 是 Integer 与 UUID 冲突，等 Agent 1 协调）。Agent 4 已经把 AI 输出"创建任务"的 worker 接到 `manual_task` inbox 上。
4. **Workspace**：DB 列保留 `workspace_id` 但 PRD10 接口不暴露；V1 等价 personal workspace。

---

## 四、Agent 2 不负责但 Web 必须有的部分

| 模块 | 负责人 | 备注 |
|---|---|---|
| `/api/v1/auth/*`、`/me` | Agent 1 | 已就绪 |
| `/api/v1/ai/*` (PRD10 §11) | Agent 3 | 已部分就绪 |
| `/api/v1/search` (PRD10 §13) | Agent 3 | 已部分就绪 |
| `/api/v1/skills` (PRD10 §17) | Agent 3 | 已部分就绪 |
| `/api/v1/garden` (PRD10 §18) | Agent 3 | 已部分就绪 |
| 前端代码本身 | 前端工程师 | `Mydow_Web_Frontend_Complete_Package.zip` 仍在工作区根目录 |

---

## 五、本地复现 / 手动联调 30 分钟流程

```powershell
# 1. 准备 venv（已有可跳过）
$env:PYTHONPATH = (Resolve-Path .\src).Path

# 2. 跑 PRD10 测试 (SQLite, ~20s)
pytest tests/integration/api/prd10/ -q -p no:cacheprovider

# 3. 跑 Postgres 测试（需要 Docker Desktop）
docker run -d --name whyme-prd10-pg `
    -e POSTGRES_USER=agentos -e POSTGRES_PASSWORD=agentos `
    -e POSTGRES_DB=agentos_db -p 5433:5432 postgres:16-alpine
docker exec whyme-prd10-pg psql -U agentos -d agentos_db -c `
    "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO agentos;"
$env:TEST_DATABASE_URL = "postgresql+asyncpg://agentos:agentos@localhost:5433/agentos_db"
pytest tests/integration/api/prd10/ -q -p no:cacheprovider

# 4. 跑端到端 smoke（启真 uvicorn → 走 16 步）
Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
python scripts/smoke_prd10.py
# → tests/integration/api/prd10/smoke_run.json

# 5. seed 演示数据，前端可直接读
$env:DATABASE_URL = "sqlite+aiosqlite:///./data/dev.db"
python scripts/seed_prd10.py
uvicorn agent_os.server.app:app --port 3001 --reload
```

完成以上五步即可进入"前端工程师对接 = 配 base URL 就能在浏览器里看到真实卡片流"的状态。
