# Mydow API Reference (PRD10 V1)

> **真理来源**：`docs/01-prd/PRD10.md` + `agent-1-backend-contract.md` + 路由代码本身。
> **任务来源**：`todo-tasks.md` 8.13。
>
> 本文档面向：
> 1. 投资人 / 客户方技术尽职 — 想 30 分钟摸清能力边界。
> 2. SDK / 第三方集成方 — 直接抄 curl 然后改 base_url 即可。
> 3. 多人协作 — 前端 / mobile / Agent 想拼出新流时知道有什么端点。
>
> 互动版：FastAPI 自动 OpenAPI 在 [`/docs`](http://localhost:8000/docs) / [`/redoc`](http://localhost:8000/redoc)（部署后）。

---

## 0. 通用约定

### 0.1 Base URL

```
http://localhost:8000/api/v1   # 本地开发
https://demo.mydow.com/api/v1  # 演示环境
```

### 0.2 鉴权

除显式标注 "公开" 的端点，所有 `/api/v1/*` 都需要 `Authorization: Bearer <jwt>`。

获取 JWT：

```bash
# 注册
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","email":"alice@example.com","password":"pass123456"}'

# 登录
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"pass123456"}'

# 演示模式（AGENTOS_DEMO_MODE=on）
curl -X POST http://localhost:8000/api/v1/demo/login
```

返回（PRD10 envelope）：

```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### 0.3 响应信封（PRD10 §6）

#### 成功

```json
{
  "success": true,
  "data": {},
  "request_id": "req_abc123"
}
```

#### 列表 / 分页

```json
{
  "success": true,
  "data": {
    "items": [...],
    "pagination": {"page": 1, "page_size": 20, "total": 100, "has_more": true}
  },
  "request_id": "req_abc123"
}
```

#### 错误

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid mode 'bogus'. Allowed: general, knowledge, planning, report",
    "details": {}
  },
  "request_id": "req_abc123"
}
```

错误 code 枚举：`UNAUTHORIZED` / `FORBIDDEN` / `NOT_FOUND` / `VALIDATION_ERROR` / `RATE_LIMITED` / `INTERNAL_ERROR` / `AI_PROVIDER_ERROR` / `JOB_FAILED`。

### 0.4 通用 query 参数

- `page` — 1-based，默认 1
- `page_size` — 默认 20，最大 100
- `keyword` / `q` — 模糊搜索

### 0.5 异步任务（PRD10 §16）

长任务（capture、文件解析、AI 报告、Skill 运行）都返回 `Job`，调用方轮询 `/api/v1/jobs/{job_id}` 看状态：`queued` → `running` → `completed` / `failed` / `canceled`。

```bash
JOB=$(curl -s -X POST http://localhost:8000/api/v1/skills/$SKILL/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input":{"goal":"周报"},"save_output":true}' \
  | jq -r '.data.job_id')

curl http://localhost:8000/api/v1/jobs/$JOB \
  -H "Authorization: Bearer $TOKEN"
```

---

## 1. 用户与设置（PRD10 §11.1 §3.1）

| 端点 | 方法 | 说明 |
|---|---|---|
| `/auth/register` | POST | 注册（公开） |
| `/auth/login` | POST | JSON body 登录（公开） |
| `/auth/refresh` | POST | 刷新 token（公开） |
| `/auth/send-code` | POST | 发送邮箱验证码（公开，需 SMTP + Redis）|
| `/auth/verify-code` | POST | 验证码登录（公开，需 SMTP + Redis）|
| `/auth/me` | GET | 当前用户 PRD10 §5.1 字段 |
| `/auth/settings` | PUT | 更新 settings JSON |
| `/auth/logout` | POST | 注销 |
| `/me` | GET | 等价于 `/auth/me`（前端首屏调用）|
| `/demo/status` | GET | 查询 demo 模式是否开启（公开） |
| `/demo/login` | POST | 一键登录（公开，需 `AGENTOS_DEMO_MODE=on`） |

```bash
# 当前用户
curl http://localhost:8000/api/v1/me \
  -H "Authorization: Bearer $TOKEN"

# 更新设置
curl -X PUT http://localhost:8000/api/v1/auth/settings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"settings":{"theme":"dark","language":"zh"}}'
```

---

## 2. 首页 / Today（PRD10 §7）

| 端点 | 方法 | 说明 |
|---|---|---|
| `/today` | GET | 首页聚合：user + stats + tasks + insight_preview + quick_actions |
| `/insights/summary` | GET | 右侧洞察统计 |
| `/notifications/unread-count` | GET | 顶部未读数 |

```bash
curl http://localhost:8000/api/v1/today \
  -H "Authorization: Bearer $TOKEN"
```

返回示例（PRD10 §7.1）：

```json
{
  "success": true,
  "data": {
    "user": {"id":"...","name":"Alice","avatar_url":null},
    "stats": {
      "today_capture_count": 3,
      "pending_task_count": 2,
      "knowledge_items_count": 28,
      "weekly_growth_rate": 0.15
    },
    "quick_actions": [
      {"key":"text","label":"记录想法","icon":"edit"},
      {"key":"link","label":"添加链接","icon":"link"},
      {"key":"audio","label":"语音输入","icon":"mic"},
      {"key":"file","label":"上传文件","icon":"upload"}
    ],
    "tasks": [],
    "insight_preview": {"title":"...", "summary":"..."},
    "favorite_folders": [...]
  },
  "request_id": "req_abc123"
}
```

---

## 3. Capture / 灵感采集（PRD10 §8）

| 端点 | 方法 | 说明 |
|---|---|---|
| `/capture/text` | POST | 记录文本想法 |
| `/capture/link` | POST | 网页剪藏 |
| `/uploads/presign` | POST | 获取上传地址（V1 是本地存储签名） |
| `/uploads/local/{upload_id}` | PUT | 单文件直传（小于 10 MiB 用） |
| `/uploads/local/{upload_id}/raw` | GET | 本地上传原始文件（V1 用，预留替换为 S3） |
| `/uploads/multipart/init` | POST | **大文件分片上传**：初始化分片 session（§12.5） |
| `/uploads/multipart/{upload_id}/{chunk_index}` | PUT | 上传单个分片（顺序无关） |
| `/uploads/multipart/{upload_id}` | GET | 查询已收分片，支持断点续传 |
| `/uploads/multipart/{upload_id}/complete` | POST | 拼接分片并写入 Source（与单文件 PUT 同 envelope） |
| `/uploads/multipart/{upload_id}` | DELETE | 取消分片 session 并清理临时文件（幂等） |
| `/capture/file/commit` | POST | 文件上传完成后 commit（异步解析；与单 PUT / multipart 都兼容） |
| `/inbox` | GET | InboxItem 列表（PRD10 §8.5） |
| `/inbox/{id}` | PATCH | 更新 InboxItem 状态 |

```bash
# 记录文本
curl -X POST http://localhost:8000/api/v1/capture/text \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content":"今天产品评审决定 V1 必须打通最小闭环"}'

# 网页剪藏
curl -X POST http://localhost:8000/api/v1/capture/link \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/article","title":"参考文档"}'

# 上传文件三步（presign → 上传 → commit）
curl -X POST http://localhost:8000/api/v1/uploads/presign \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"filename":"spec.pdf","mime_type":"application/pdf","size_bytes":102400}'
# → 拿到 upload_id 与 upload_url

curl -X PUT $upload_url --data-binary @spec.pdf

curl -X POST http://localhost:8000/api/v1/capture/file/commit \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"upload_id":"$upload_id","filename":"spec.pdf","folder_id":null}'
```

### 3.1 大文件分片上传（PRD10 §12.5 / §16.3）

> 适用于 ≥ 10 MiB 的文件、慢网或需要断点续传的场景。`init` → 多次 `PUT` chunk → `complete` 后端 envelope 与单文件 PUT 完全一致，复用 `/capture/file/commit` 收尾。

```bash
# 1) 初始化 multipart session（服务器算 chunk_size 与 total_chunks）
curl -X POST http://localhost:8000/api/v1/uploads/multipart/init \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"filename":"video.mp4","total_size_bytes":52428800,"mime_type":"video/mp4"}'
# → data: { upload_id, chunk_size: 5242880, total_chunks: 10, expires_at, ... }

# 2) 推送每一个 chunk（顺序无关）；body 是该 chunk 的纯字节
for ((i=0; i<10; i++)); do
  dd if=video.mp4 bs=5242880 count=1 skip=$i 2>/dev/null | \
  curl -X PUT "http://localhost:8000/api/v1/uploads/multipart/$upload_id/$i" \
    -H "Authorization: Bearer $TOKEN" \
    --data-binary @-
done
# → 每个响应里有 received_count / is_complete / sha256

# 3) 断点续传：失败后查已收 chunk
curl "http://localhost:8000/api/v1/uploads/multipart/$upload_id" \
  -H "Authorization: Bearer $TOKEN"
# → data.missing_chunks: [3, 7]   # 只补这两片即可

# 4) 全部 chunk 到位后拼装 + 写 Source
curl -X POST "http://localhost:8000/api/v1/uploads/multipart/$upload_id/complete" \
  -H "Authorization: Bearer $TOKEN"
# → data: { upload_id, filename, size_bytes, file_url, total_chunks, completed_at }

# 5) 用同一个 upload_id 走标准 commit，触发异步解析
curl -X POST http://localhost:8000/api/v1/capture/file/commit \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"upload_id":"$upload_id","filename":"video.mp4","mime_type":"video/mp4","size_bytes":52428800}'

# 取消会话（幂等，cancelled=false 表示根本不存在该 session）
curl -X DELETE "http://localhost:8000/api/v1/uploads/multipart/$upload_id" \
  -H "Authorization: Bearer $TOKEN"
```

**实现细节**：

- 每个非末尾 chunk 必须等于 server 选定的 `chunk_size`（默认 5 MiB，env `AGENTOS_UPLOAD_MULTIPART_CHUNK_SIZE` 可调，client 可在 init 时显式指定 1 KiB – 64 MiB）。
- 末尾 chunk 长度由 `total_size_bytes` 推算并校验。
- session TTL 默认 24 h（env `AGENTOS_UPLOAD_MULTIPART_TTL_SECONDS`）；超时 PUT 返 400 `VALIDATION_ERROR`。
- 单 session 总大小硬上限默认 2 GiB（env `AGENTOS_UPLOAD_MULTIPART_MAX_BYTES`）。
- 临时 chunk 文件落 `data/uploads/multipart/<user_id>/<upload_id>/chunks/<index>.part`，`complete` 时拼装到正式 `data/uploads/<user_id>/<upload_id>/<filename>` 后立即清空临时目录；`cancel` 同样清空。
- 所有 5 个端点都有 user_id 隔离：跨用户 GET/PUT/POST/DELETE 一律 404，不泄漏 session 存在性。

---

## 4. Feed / Cards（PRD10 §9）

| 端点 | 方法 | 说明 |
|---|---|---|
| `/feed` | GET | 内容流（卡片视图，可分页 / 排序 / 筛选） |
| `/cards/{id}` | GET / PATCH / DELETE | 卡片详情 / 更新 / 软删除 |
| `/cards` | POST | 创建卡片 |
| `/cards/{id}/favorite` | POST | 收藏 / 取消收藏 |

```bash
# 拉首页 feed
curl "http://localhost:8000/api/v1/feed?view=card&date_range=week&page=1&page_size=20" \
  -H "Authorization: Bearer $TOKEN"

# 收藏
curl -X POST http://localhost:8000/api/v1/cards/$CARD/favorite \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_favorite":true}'
```

---

## 5. 知识库（PRD10 §10）

| 端点 | 方法 | 说明 |
|---|---|---|
| `/kb/overview` | GET | 概览统计 |
| `/kb/folders` | GET / POST | 文件夹列表 / 创建 |
| `/kb/folders/{id}` | GET / PATCH / DELETE | 单个文件夹（rename/move 通过 PATCH 改 name/parent_id 也可） |
| `/kb/folders/{id}/move` | POST | 显式 move（含 cycle 防护） |
| `/kb/folders/{id}/rename` | POST | 显式 rename |
| `/kb/documents` | GET | 文档列表（支持 folder_id 过滤） |
| `/kb/documents/{id}` | GET / PATCH / DELETE | 单文档 |
| `/kb/documents/{id}/move` | POST | 移动到其它文件夹 |

```bash
# 新建文件夹
curl -X POST http://localhost:8000/api/v1/kb/folders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"产品设计","color":"#1f2937","is_favorite":true}'

# 移动文件夹
curl -X POST http://localhost:8000/api/v1/kb/folders/$CHILD/move \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"parent_id":"$PARENT"}'

# 列出文件夹下的文档
curl "http://localhost:8000/api/v1/kb/documents?folder_id=$FOLDER&page=1" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 6. Mydow AI（PRD10 §11）

| 端点 | 方法 | 说明 |
|---|---|---|
| `/ai/conversations` | GET | 列表（keyword + page） |
| `/ai/conversations` | POST | 新建（title + mode + context_scope） |
| `/ai/conversations/{id}` | GET | 详情 + messages + 上下文 + 建议 |
| `/ai/conversations/{id}/messages` | POST | 同步发送，立即返回 placeholder 或真 LLM 回答 |
| `/ai/conversations/{id}/messages/stream` | POST | **SSE 流式** 发送（meta → token* → done） |
| `/ai/messages/{id}/cancel` | POST | 停止生成（PRD10 §11.5）|
| `/ai/messages/{id}/regenerate` | POST | 重新生成（PRD10 §11.6）|
| `/ai/messages/{id}/save-to-kb` | POST | 把 assistant 回答存为 KB document（异步） |
| `/ai/messages/{id}/create-tasks` | POST | 把 assistant 回答存为 tasks（异步） |

```bash
# 新会话
CONV=$(curl -s -X POST http://localhost:8000/api/v1/ai/conversations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"产品方向讨论","mode":"general"}' \
  | jq -r '.data.id')

# 发送消息（同步）
curl -X POST http://localhost:8000/api/v1/ai/conversations/$CONV/messages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content":"请帮我总结本周产品决策"}'

# 发送消息（SSE 流式）
curl -N -X POST http://localhost:8000/api/v1/ai/conversations/$CONV/messages/stream \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content":"用 100 字解释 Mydow"}'
# 响应（PRD10 §11.4 + §12.4 SSE 心跳契约）：
#   retry: 5000                                            ← 客户端重连提示
#   event: meta
#   data: {"user_message_id":"...","assistant_message_id":"...","job_id":"...",
#          "heartbeat_seconds":15}
#
#   event: token
#   data: {"delta":"Mydow"}
#
#   event: token
#   data: {"delta":" 是"}
#   ...
#   event: keepalive                                       ← 每 N 秒（默认 15s）
#   data: {"ts":1715000000.123,"elapsed_ms":15012,"count":1}
#   ...
#   event: done
#   data: {"assistant_message_id":"...","job_id":"...","status":"completed",
#          "latency_ms":2340}
#
# 出错时：
#   event: error
#   data: {"code":"AI_PROVIDER_ERROR","message":"..."}
#   event: done
#   data: {"status":"failed",...}

# 取消未完成消息
curl -X POST http://localhost:8000/api/v1/ai/messages/$MID/cancel \
  -H "Authorization: Bearer $TOKEN"

# 重新生成
curl -X POST http://localhost:8000/api/v1/ai/messages/$MID/regenerate \
  -H "Authorization: Bearer $TOKEN"

# 把回答存为 KB 文档
curl -X POST http://localhost:8000/api/v1/ai/messages/$MID/save-to-kb \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"folder_id":null,"title":"AI 总结：本周产品","tags":["AI","产品"]}'
```

---

## 7. Skills（PRD10 §17）

| 端点 | 方法 | 说明 |
|---|---|---|
| `/skills` | GET | 列表（category + keyword + status） |
| `/skills/{id}` | GET | 详情 |
| `/skills/{id}/run` | POST | 运行（写 `Job(skill_run, queued)` + `SkillRun`） |

```bash
curl http://localhost:8000/api/v1/skills \
  -H "Authorization: Bearer $TOKEN"

curl -X POST http://localhost:8000/api/v1/skills/$SKILL/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input":{"goal":"本周周报"},"save_output":"kb"}'
```

---

## 8. 数字花园（PRD10 §18）

| 端点 | 方法 | 说明 |
|---|---|---|
| `/garden/overview` | GET | node_count / edge_count / strong_edge_count / top_topics / recent_insights |
| `/garden/graph` | GET | nodes + edges（range / topic / depth / limit） |

```bash
curl "http://localhost:8000/api/v1/garden/graph?range=30d&depth=1&limit=200" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 9. 全局搜索（PRD10 §13）

| 端点 | 方法 | 说明 |
|---|---|---|
| `/search` | GET | 跨 object_type 搜索（card / document / folder / task / conversation / message / skill / insight），支持 `mode=keyword|semantic|hybrid` |
| `/search/suggestions` | GET | 输入框自动补全 |

```bash
curl "http://localhost:8000/api/v1/search?q=Mydow&mode=hybrid&object_type=document&object_type=card&page=1" \
  -H "Authorization: Bearer $TOKEN"
```

`semantic` 使用 `SearchIndex.embedding` 的 deterministic `hash64-v1` 向量相似度；缺失 embedding 的旧行会用标题、摘要和正文即时回填计算。`hybrid` 采用 70% semantic + 30% keyword lexical score，适合 SPA 默认搜索体验。

---

## 10. 通知中心（PRD10 §15）

| 端点 | 方法 | 说明 |
|---|---|---|
| `/notifications` | GET | 列表（is_read / type 过滤） |
| `/notifications/unread-count` | GET | 未读数 |
| `/notifications/{id}/read` | POST | 单点已读 |
| `/notifications/read-all` | POST | 全部已读 |
| `/notifications/stream` | GET | **SSE 实时推送**（ready → notification* → keepalive*） |

```bash
# 实时订阅（前端 EventSource 直连）
curl -N http://localhost:8000/api/v1/notifications/stream \
  -H "Authorization: Bearer $TOKEN"
# 响应（PRD10 §15 + §12.4 SSE 心跳契约）：
#   retry: 5000                            ← 客户端重连提示（5s）
#   event: ready
#   data: {"user_id":"..."}
#
#   event: notification
#   data: {"id":"...","type":"job_completed","title":"文件解析完成",...}
#
#   event: ping                            ← 每 ~25s 心跳防代理 timeout
#   data: {}
```

### 12.x SSE 心跳与断线重连（PRD10 §12.4）

两条 SSE 通道（`/ai/conversations/{id}/messages/stream` 与
`/notifications/stream`）都遵循统一的稳健性契约：

| 项 | AI streaming | Notifications stream |
|---|---|---|
| 首帧 `retry:` 提示 | ✅ `retry: 5000`（与 meta 同 block） | ✅ `retry: 5000`（与 ready 同 block） |
| `event: keepalive` / `event: ping` | ✅ `event: keepalive`（默认每 15s） | ✅ `event: ping`（每 ~25s） |
| `Cache-Control` | `no-store` | `no-cache` |
| `Connection: keep-alive` | ✅ | ✅ |
| `X-Accel-Buffering: no` | ✅ 防 nginx 缓冲 | ✅ 防 nginx 缓冲 |
| 客户端断线检测 | 由心跳触发 SSE `onerror` | `request.is_disconnected()` 主动检 |
| 配置 | `AGENTOS_SSE_HEARTBEAT_SECONDS`（默认 15）| 固定 25s |

#### 浏览器侧推荐写法

```javascript
const es = new EventSource("/api/v1/notifications/stream", {
  withCredentials: true,
});
es.addEventListener("ready", (e) => console.log("subscribed", JSON.parse(e.data)));
es.addEventListener("notification", (e) => handleNotification(JSON.parse(e.data)));
es.addEventListener("ping", () => {/* idle keepalive — no-op */});
es.onerror = () => {
  // EventSource 会自动按 retry: 提示的 5000ms 重连
  console.log("[sse] reconnecting…");
};
```

#### 反向代理建议

- **nginx**：`proxy_buffering off; proxy_read_timeout 300s; proxy_set_header Connection '';`
  （已经在 `docker/nginx/mydow.conf` 配置）
- **Cloudflare**：默认 ≥ 100s idle timeout 不会中断；`Cache-Control: no-store` + `X-Accel-Buffering: no` 让 CDN 不缓存 SSE。
- **uvicorn (Windows)**：worker process 的 idle timeout 由 `AGENTOS_SSE_HEARTBEAT_SECONDS` 兜底保活。

#### 调优

```bash
# AI SSE 心跳 5s（适合小流量演示，更快感知断线）
export AGENTOS_SSE_HEARTBEAT_SECONDS=5

# AI SSE 心跳 30s（适合代理 idle 超时较高的环境）
export AGENTOS_SSE_HEARTBEAT_SECONDS=30
```

---

## 11. 异步任务（PRD10 §16）

| 端点 | 方法 | 说明 |
|---|---|---|
| `/jobs/{id}` | GET | Job 详情（status / progress / input / output / error） |
| `/jobs/{id}/cancel` | POST | 取消 |

```bash
curl http://localhost:8000/api/v1/jobs/$JOB_ID \
  -H "Authorization: Bearer $TOKEN"
```

---

## 12. 健康检查与运维

| 端点 | 方法 | 说明 |
|---|---|---|
| `/health` | GET | 简单 200 OK（公开） |
| `/api/v1/observability/health` | GET | 详细 health（DB / Redis / 对象存储） |
| `/docs` | GET | Swagger UI（公开） |
| `/redoc` | GET | ReDoc（公开） |
| `/openapi.json` | GET | OpenAPI schema |

### 12.1 OpenAPI examples 与可复制 curl

`/openapi.json` 会在 FastAPI 自动 schema 的基础上注入 PRD10 示例：

- `components.securitySchemes.BearerAuth`：JWT Bearer 鉴权说明。
- `servers`：本地 `http://localhost:8000` 与 demo `https://demo.mydow.com`。
- 关键端点 request/response examples：登录、灵感采集、知识库文件夹、AI 会话、AI SSE、Skill 运行、搜索。
- ReDoc 扩展 `x-codeSamples`：每个关键端点都带一段可复制 curl。

快速检查：

```bash
curl -s http://localhost:8000/openapi.json \
  | jq '.paths["/api/v1/capture/text"].post.requestBody.content["application/json"].examples'

curl -s http://localhost:8000/openapi.json \
  | jq '.paths["/api/v1/skills/{skill_id}/run"].post["x-codeSamples"][0].source'
```

---

## 13. SDK 使用建议

### 前端 JS（已内置）

`/mydow/mydow-api.js` + `/mydow/app.js` 提供 `window.MydowAPI`：

```javascript
const me = await window.MydowAPI.me.fetch();
const conv = await window.MydowAPI.ai.createConversation({ title: 'demo', mode: 'general' });
const reply = await window.MydowAPI.ai.sendMessage(conv.data.id, { content: '你好' });
```

### Python

```python
import httpx

base = "http://localhost:8000/api/v1"
async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}) as client:
    me = (await client.get(f"{base}/me")).json()
    feed = (await client.get(f"{base}/feed", params={"page_size": 20})).json()
```

### 第三方对接

直接 hit `/api/v1/*`，按 §0.3 envelope 处理响应。错误用 §0.3 error.code 分流。

---

## 14. 速率限制（PRD10 §29，已实装；任务 12.2）

由 `RateLimitMiddleware` 提供（`agent_os/common/rate_limit.py` + `agent_os/common/middleware.py`）。**默认 OFF**，生产开启方式：

```bash
AGENTOS_RATE_LIMIT=on
```

启用后按下表分桶（token-bucket 算法，refill = capacity / 60s）：

| Policy | 端点 | 配额 | 桶范围 |
|---|---|---:|---|
| `auth_login` | `POST /api/v1/auth/login` | 10/分钟 | 每 IP |
| `auth_register` | `POST /api/v1/auth/register` | 5/分钟 | 每 IP |
| `auth_send_code` | `POST /api/v1/auth/{send-code,forgot-password,resend-verification}` | 5/分钟 | 每 IP |
| `ai_messages` | `POST /api/v1/ai/conversations/...messages` 或 `/messages/...` | 30/分钟 | 每用户（按 Bearer token；缺 token 退化按 IP） |
| `search` | `ANY /api/v1/search...` | 120/分钟 | 每用户 |
| `capture` | `POST/PUT /api/v1/capture` 或 `/api/v1/uploads` | 120/分钟 | 每用户 |
| `global` | `ANY /api/v1/...`（兜底） | 600/分钟 | 每 IP |

匹配规则：第一个 policy 命中即生效，特定路径优先于 `global`。

### 14.1 响应头

每个匹配限流的请求都会附加：

| Header | 含义 |
|---|---|
| `X-RateLimit-Policy` | 命中的 policy 名 |
| `X-RateLimit-Limit` | 桶容量 |
| `X-RateLimit-Remaining` | 剩余 token 数（命中限流时为 `0`） |
| `Retry-After` | **仅 429 时存在**，建议等待秒数 |

### 14.2 触发示例（429）

```bash
$ curl -i -X POST http://localhost:8000/api/v1/auth/login \
    -d '{"username":"x","password":"x"}'
HTTP/1.1 429 Too Many Requests
Retry-After: 6
X-RateLimit-Policy: auth_login
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 0
X-Request-ID: req_abc123def456
content-type: application/json

{
  "success": false,
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded for policy 'auth_login'. Please retry later.",
    "details": {
      "policy": "auth_login",
      "scope": "ip",
      "limit": 10,
      "retry_after_seconds": 6
    }
  },
  "request_id": "req_abc123def456"
}
```

### 14.3 客户端建议（FE / SDK）

1. **检测 429** → 读 `Retry-After` 等待该秒数后重试一次。
2. **解析 PRD10 envelope** → `error.code == "RATE_LIMITED"` 时区分于其他错误。
3. **指数退避** 给关键路径（auth、capture）做重复请求保护。
4. **观察 `X-RateLimit-Remaining`** 来判断接近上限的非阻塞预警。

### 14.4 多实例部署注意

当前默认存储是 **in-memory**（`InMemoryRateLimitStore`），单进程内 asyncio-safe。多实例 / 多 zone 部署需要切换到 Redis 后端（PRD10 §29 follow-up），否则计数不共享。代码层已抽象 `consume(key, capacity, refill_per_second)` 接口，替换 store 不需改 caller。

---

## 修订记录

- 2026-05-05 v1：初版（任务 8.13），覆盖 PRD10 §7–§18 全部端点 + 8 大 curl 示例。
- 2026-05-06 v1.1：§14 速率限制改为已实装（任务 12.2 done）；新增 14.1 响应头、14.2 触发示例、14.3 客户端建议、14.4 多实例注意事项。
