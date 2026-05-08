# Mydow 一级功能 UI 后端 PRD

> 版本：V1.0  
> 目标：根据当前一级功能 UI，定义一套能支撑前端真实跑通的后端系统。  
> 范围：全局框架、首页/灵感采集、知识库、Mydow AI、Skills 广场、全局搜索、通知中心、用户与权限、异步任务、数据模型、API 契约、验收标准。  
> 设计原则：前端页面不依赖假数据；所有列表、卡片、文件夹、AI 对话、右侧分析栏、上传、搜索、通知、状态流均可通过后端接口真实驱动。

---

## 1. 引言与目的

### 1.1 背景

当前 Mydow 一级功能 UI 已覆盖产品 V1 的主工作台结构：左侧全局导航、顶部全局搜索、首页/灵感采集输入区、内容流、右侧洞察栏、知识库文件夹与文档列表、Mydow AI 对话工作台，以及后续 Skills 广场入口。

本 PRD 的目标不是单纯描述后端能力，而是反向约束后端必须交付哪些数据、接口和任务流，才能保证前端 UI 可以真实运行、页面状态完整、核心交互闭环可用。

### 1.2 后端建设目标

V1 后端需要支持以下目标：

1. 用户登录后可以进入统一工作台，并加载个人基础信息、导航状态、统计信息、通知数量。
2. 用户可以在首页/灵感采集输入文本、上传文件、添加链接、录音或图片素材，后端生成 InboxItem / Card / Source / Chunk 等结构化数据。
3. 首页内容流可以展示最近内容、推荐内容、卡片摘要、来源信息、标签、收藏、更多操作和不同视图。
4. 右侧洞察中心可以展示用户知识统计、主题分布、任务提醒、AI 建议、日报/周报生成结果。
5. 知识库可以展示文件夹、文档列表、资源类型、更新时间、收藏、权限、文件详情。
6. Mydow AI 可以基于用户上下文进行对话、引用知识库内容、生成结构化结果，并保存会话历史。
7. 全局搜索可以搜索 Notes / Cards / Documents / Folders / Tasks / Chats / Skills，并支持语义检索和关键词检索。
8. 通知中心可以接收异步任务完成、AI 洞察生成、上传解析失败、写入成功、需要确认等事件。
9. 所有前端页面必须有 Loading / Empty / Error / Success / Permission Denied / Processing 状态可显示。
10. 后端要具备后续扩展 Agent、Skills、数字花园和商业化能力的基础数据结构。

### 1.3 V1 不做范围

V1 暂不做以下能力，但需要预留字段：

- 多 Workspace 商业协作后台。
- 复杂团队权限矩阵。
- Skill 交易市场支付闭环。
- 完整知识图谱自动推理系统。
- 多模态长视频深度理解。
- 第三方平台大规模自动抓取。
- 企业级审计与合规后台。

---

## 2. 产品信息架构与后端模块映射

### 2.1 前端一级导航

当前 UI 的一级导航对应后端模块如下：

| 前端一级入口 | 页面含义 | 后端模块 | 核心数据对象 |
|---|---|---|---|
| 首页/灵感采集 | 输入、记录、内容流、待办、洞察 | Capture / Inbox / Feed / Insight | InboxItem, Card, Task, Insight, Source |
| 知识库 | 文件夹、文档、知识资产管理 | Knowledge Base | Folder, Document, Resource, Chunk |
| 数字花园 | 认知结构、节点与连接 | Graph / Garden | KnowledgeNode, KnowledgeEdge, Insight |
| Mydow AI | AI 对话、任务生成、上下文调用 | AI Chat / Agent | Conversation, Message, ToolCall, Citation |
| Skills 广场 | Skill 浏览、调用、收藏 | Skills | Skill, SkillRun, SkillBinding |
| 全局搜索 | 跨模块搜索与命令 | Search | SearchDocument, SearchQuery |
| 通知中心 | 异步任务与系统事件 | Notification | Notification, Job |
| 个人信息/设置 | 用户配置、偏好、账户 | User / Settings | User, Preference, Integration |

### 2.2 后端服务边界

V1 建议拆分为 8 个服务域，可先在一个 Monorepo / Modular Monolith 中实现，后续再拆服务：

1. User Service：用户、登录态、个人设置。
2. Capture Service：文本、链接、文件、图片、音频等输入接收。
3. Knowledge Service：文件夹、文档、资源、Chunk、引用。
4. Feed Service：首页内容流、卡片、收藏、筛选、排序。
5. Search Service：统一索引、语义检索、关键词检索。
6. AI Service：对话、上下文检索、模型调用、Agent 任务。
7. Insight Service：统计分析、主题分布、日报/周报、建议。
8. Notification / Job Service：异步任务、通知、状态流。

---

## 3. 用户角色与权限

### 3.1 用户角色

V1 以个人用户为主，权限模型先保持简单：

| 角色 | 说明 | 权限 |
|---|---|---|
| Owner | 当前登录用户 | 拥有自己所有数据的读写权限 |
| Guest | 未登录用户 | 只能访问登录页、公开介绍页 |
| System | 系统任务身份 | 可执行解析、索引、总结、通知写入 |

### 3.2 数据隔离规则

所有核心数据表必须包含：

- `user_id`
- `workspace_id`，V1 默认个人空间，可为空间化预留
- `created_at`
- `updated_at`
- `deleted_at`

接口层必须基于 `user_id` 做数据隔离，避免用户读取他人数据。

---

## 4. 核心用户流程

### 4.1 首页初始化流程

用户进入首页后：

1. 前端读取登录态。
2. 调用 `/api/v1/me` 获取用户信息。
3. 调用 `/api/v1/today` 获取首页聚合数据。
4. 调用 `/api/v1/feed` 获取内容流。
5. 调用 `/api/v1/insights/summary` 获取右侧洞察。
6. 调用 `/api/v1/notifications/unread-count` 获取未读通知数。
7. 前端根据返回数据展示：输入区、内容卡片、任务提醒、知识统计、右侧分析栏。

### 4.2 用户记录一条想法

1. 用户在输入框输入文本。
2. 前端调用 `/api/v1/capture/text`。
3. 后端创建 `InboxItem`，状态为 `received`。
4. 后端创建异步 `IngestionJob`，状态为 `queued`。
5. 立即返回 `inbox_item_id` 和 `job_id`。
6. 前端展示记录成功，并可显示处理中状态。
7. 异步任务进行摘要、标签、分类、向量化、写入知识库。
8. 任务完成后生成 `Card` / `Document` / `SearchDocument`。
9. 后端写入通知：记录已整理完成。
10. 前端轮询或通过 SSE/WebSocket 接收更新。

### 4.3 用户上传文件

1. 前端请求 `/api/v1/uploads/presign` 获取上传地址。
2. 前端直传对象存储。
3. 前端调用 `/api/v1/capture/file/commit`。
4. 后端创建 `Source`、`Document`、`IngestionJob`。
5. 后端异步解析文件、提取文本、生成 chunk、embedding、摘要。
6. 前端在知识库和首页内容流中看到该文件。

### 4.4 用户进入知识库

1. 前端调用 `/api/v1/kb/folders` 获取文件夹列表。
2. 前端调用 `/api/v1/kb/documents` 获取全部或当前文件夹文档。
3. 点击文件夹后调用 `/api/v1/kb/folders/{folder_id}` 和 `/api/v1/kb/documents?folder_id=xxx`。
4. 点击文档后调用 `/api/v1/kb/documents/{document_id}`。
5. 文档详情中可查看摘要、来源、标签、关联内容、AI 建议。

### 4.5 用户使用 Mydow AI

1. 用户进入 Mydow AI 页面。
2. 前端调用 `/api/v1/ai/conversations` 获取历史会话。
3. 用户输入问题并调用 `/api/v1/ai/conversations/{id}/messages`。
4. 后端创建用户消息。
5. AI Service 检索用户相关上下文。
6. 生成回答、引用、建议操作。
7. 返回流式输出。
8. 保存完整消息、引用、工具调用记录。
9. 可将回答保存为 Card / Document / Task。

---

## 5. 核心数据模型

以下模型为 V1 后端必须落库的数据结构。字段命名建议统一使用 snake_case；前端返回可使用 camelCase，二者通过 DTO 映射。

### 5.1 User 用户

```json
{
  "id": "usr_001",
  "name": "Alison",
  "avatar_url": "https://...",
  "email": "user@example.com",
  "role": "owner",
  "locale": "zh-CN",
  "timezone": "Asia/Shanghai",
  "plan": "free",
  "created_at": "2026-05-04T10:00:00+08:00",
  "updated_at": "2026-05-04T10:00:00+08:00"
}
```

### 5.2 UserPreference 用户偏好

```json
{
  "id": "pref_001",
  "user_id": "usr_001",
  "default_view": "card",
  "theme": "light",
  "language": "zh-CN",
  "ai_response_style": "concise_structured",
  "daily_report_time": "21:30",
  "notification_enabled": true
}
```

### 5.3 InboxItem 灵感/输入项

用于承接所有用户输入。

```json
{
  "id": "inbox_001",
  "user_id": "usr_001",
  "type": "text",
  "title": "关于产品设计的想法",
  "raw_content": "今天想到一个新的知识库交互方式...",
  "source_url": null,
  "source_id": null,
  "status": "processed",
  "processing_status": "completed",
  "priority": "normal",
  "tags": ["产品", "知识库"],
  "created_at": "2026-05-04T10:00:00+08:00",
  "updated_at": "2026-05-04T10:02:00+08:00"
}
```

枚举：

- `type`: `text | link | file | image | audio | video | manual_task`
- `status`: `draft | received | processing | processed | archived | failed`
- `priority`: `low | normal | high | urgent`

### 5.4 Source 来源

用于文件、链接、音频、图片等原始材料。

```json
{
  "id": "src_001",
  "user_id": "usr_001",
  "type": "pdf",
  "name": "产品设计参考.pdf",
  "url": "https://object-storage/...",
  "mime_type": "application/pdf",
  "size_bytes": 2048000,
  "checksum": "sha256_xxx",
  "metadata": {
    "page_count": 12,
    "duration_seconds": null,
    "origin": "upload"
  },
  "created_at": "2026-05-04T10:00:00+08:00"
}
```

### 5.5 Card 内容卡片

首页内容流的基础展示对象。

```json
{
  "id": "card_001",
  "user_id": "usr_001",
  "title": "Mydow 首页信息架构思考",
  "summary": "这条内容总结了首页输入、内容流和右侧洞察之间的关系。",
  "cover_url": "https://...",
  "content_type": "note",
  "source_id": "src_001",
  "inbox_item_id": "inbox_001",
  "folder_id": "folder_001",
  "tags": ["Mydow", "产品设计"],
  "entities": ["首页", "知识库", "AI"],
  "is_favorite": false,
  "is_archived": false,
  "visibility": "private",
  "created_at": "2026-05-04T10:03:00+08:00",
  "updated_at": "2026-05-04T10:03:00+08:00"
}
```

枚举：

- `content_type`: `note | article | file | image | audio | task | ai_output | report`

### 5.6 Folder 知识库文件夹

```json
{
  "id": "folder_001",
  "user_id": "usr_001",
  "parent_id": null,
  "name": "产品设计",
  "description": "产品设计相关文档、灵感和资料",
  "icon": "folder",
  "color": "blue",
  "document_count": 18,
  "card_count": 36,
  "is_favorite": true,
  "sort_order": 10,
  "created_at": "2026-05-01T10:00:00+08:00",
  "updated_at": "2026-05-04T10:00:00+08:00"
}
```

### 5.7 Document 知识库文档

```json
{
  "id": "doc_001",
  "user_id": "usr_001",
  "folder_id": "folder_001",
  "source_id": "src_001",
  "title": "UI 设计规范",
  "summary": "该文档定义了 Mydow V1 的主要 UI 风格和交互组件。",
  "content": "Markdown 或纯文本正文",
  "document_type": "pdf",
  "status": "ready",
  "tags": ["UI", "设计规范"],
  "word_count": 4200,
  "chunk_count": 18,
  "is_favorite": false,
  "last_opened_at": "2026-05-04T10:00:00+08:00",
  "created_at": "2026-05-01T10:00:00+08:00",
  "updated_at": "2026-05-04T10:00:00+08:00"
}
```

枚举：

- `document_type`: `note | markdown | pdf | docx | pptx | image | audio | link | ai_output`
- `status`: `processing | ready | failed | archived`

### 5.8 Chunk 文档分块

用于 AI 检索、引用和语义搜索。

```json
{
  "id": "chunk_001",
  "user_id": "usr_001",
  "document_id": "doc_001",
  "source_id": "src_001",
  "chunk_index": 0,
  "content": "文档中的一段内容...",
  "token_count": 512,
  "embedding_id": "emb_001",
  "metadata": {
    "page": 1,
    "section": "产品目标"
  },
  "created_at": "2026-05-04T10:00:00+08:00"
}
```

### 5.9 Task 任务

用于首页右侧提醒、AI 生成待办、用户手动任务。

```json
{
  "id": "task_001",
  "user_id": "usr_001",
  "title": "完善知识库后端接口",
  "description": "补齐 folder / document / search 接口。",
  "status": "todo",
  "priority": "high",
  "due_at": "2026-05-06T18:00:00+08:00",
  "source_type": "ai",
  "source_id": "msg_001",
  "tags": ["后端", "PRD"],
  "created_at": "2026-05-04T10:00:00+08:00",
  "updated_at": "2026-05-04T10:00:00+08:00"
}
```

枚举：

- `status`: `todo | doing | done | canceled`
- `source_type`: `manual | ai | inbox | document | insight`

### 5.10 Insight 洞察

```json
{
  "id": "insight_001",
  "user_id": "usr_001",
  "title": "你最近在持续关注产品信息架构",
  "summary": "过去 7 天内，产品设计、知识库和 Agent 相关内容占比最高。",
  "insight_type": "theme_trend",
  "confidence": 0.86,
  "related_card_ids": ["card_001", "card_002"],
  "related_document_ids": ["doc_001"],
  "actions": [
    {
      "type": "create_report",
      "label": "生成周报"
    }
  ],
  "status": "active",
  "created_at": "2026-05-04T10:00:00+08:00"
}
```

枚举：

- `insight_type`: `theme_trend | task_risk | knowledge_gap | connection | daily_summary | weekly_summary`
- `status`: `active | dismissed | archived`

### 5.11 Conversation AI 会话

```json
{
  "id": "conv_001",
  "user_id": "usr_001",
  "title": "Mydow 后端 PRD 讨论",
  "mode": "general",
  "last_message_preview": "我会帮你拆成接口和数据模型...",
  "message_count": 8,
  "created_at": "2026-05-04T10:00:00+08:00",
  "updated_at": "2026-05-04T10:20:00+08:00"
}
```

### 5.12 Message AI 消息

```json
{
  "id": "msg_001",
  "conversation_id": "conv_001",
  "user_id": "usr_001",
  "role": "assistant",
  "content": "这是生成的回答...",
  "status": "completed",
  "citations": [
    {
      "document_id": "doc_001",
      "chunk_id": "chunk_001",
      "title": "UI 设计规范",
      "snippet": "首页包含输入区、内容流和右侧洞察..."
    }
  ],
  "tool_calls": [
    {
      "tool_name": "search_kb",
      "status": "success"
    }
  ],
  "created_at": "2026-05-04T10:00:00+08:00"
}
```

### 5.13 Skill

```json
{
  "id": "skill_001",
  "name": "会议纪要生成",
  "description": "将录音或文本整理为会议纪要、行动项和负责人。",
  "category": "productivity",
  "icon": "sparkles",
  "status": "published",
  "input_schema": {
    "type": "object",
    "properties": {
      "source_id": { "type": "string" }
    }
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "summary": { "type": "string" },
      "tasks": { "type": "array" }
    }
  },
  "created_at": "2026-05-04T10:00:00+08:00"
}
```

### 5.14 SearchDocument 统一索引

```json
{
  "id": "sdoc_001",
  "user_id": "usr_001",
  "object_type": "document",
  "object_id": "doc_001",
  "title": "UI 设计规范",
  "summary": "Mydow V1 UI 设计文档",
  "content": "用于搜索的正文文本",
  "tags": ["UI", "Mydow"],
  "embedding_id": "emb_001",
  "updated_at": "2026-05-04T10:00:00+08:00"
}
```

枚举：

- `object_type`: `card | document | folder | task | conversation | message | skill | insight`

### 5.15 IngestionJob 异步任务

```json
{
  "id": "job_001",
  "user_id": "usr_001",
  "job_type": "parse_file",
  "status": "running",
  "progress": 45,
  "input": {
    "source_id": "src_001"
  },
  "output": null,
  "error": null,
  "created_at": "2026-05-04T10:00:00+08:00",
  "updated_at": "2026-05-04T10:01:00+08:00"
}
```

枚举：

- `job_type`: `parse_file | summarize | embed | index | generate_insight | generate_report | ai_chat | skill_run`
- `status`: `queued | running | completed | failed | canceled`

### 5.16 Notification 通知

```json
{
  "id": "noti_001",
  "user_id": "usr_001",
  "type": "job_completed",
  "title": "文件解析完成",
  "content": "《UI 设计规范》已整理进知识库。",
  "object_type": "document",
  "object_id": "doc_001",
  "is_read": false,
  "created_at": "2026-05-04T10:00:00+08:00"
}
```

---

## 6. API 总体规范

### 6.1 基础约定

- Base URL：`/api/v1`
- 请求格式：JSON
- 时间格式：ISO 8601
- 鉴权：Bearer Token / Session Cookie 二选一，Web 优先 Session Cookie
- 分页：统一使用 `page`, `page_size`, `total`, `has_more`
- 排序：统一使用 `sort_by`, `sort_order`
- 删除：默认软删除

### 6.2 统一成功响应

```json
{
  "success": true,
  "data": {},
  "request_id": "req_001"
}
```

### 6.3 统一分页响应

```json
{
  "success": true,
  "data": {
    "items": [],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 128,
      "has_more": true
    }
  },
  "request_id": "req_001"
}
```

### 6.4 统一错误响应

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "标题不能为空",
    "details": {
      "field": "title"
    }
  },
  "request_id": "req_001"
}
```

### 6.5 通用错误码

| 错误码 | HTTP 状态 | 说明 |
|---|---:|---|
| UNAUTHORIZED | 401 | 未登录或登录态过期 |
| FORBIDDEN | 403 | 无权限 |
| NOT_FOUND | 404 | 资源不存在 |
| VALIDATION_ERROR | 400 | 参数错误 |
| RATE_LIMITED | 429 | 请求过于频繁 |
| INTERNAL_ERROR | 500 | 服务异常 |
| AI_PROVIDER_ERROR | 502 | AI 服务异常 |
| JOB_FAILED | 500 | 异步任务失败 |

---

## 7. 首页 / Today 聚合接口

### 7.1 获取首页聚合数据

`GET /api/v1/today`

用途：支持首页初始化，包括顶部统计、输入区状态、待办、最近内容、右侧摘要。

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| date | string | 否 | 默认今天 |
| timezone | string | 否 | 默认用户时区 |

响应：

```json
{
  "success": true,
  "data": {
    "user": {
      "id": "usr_001",
      "name": "Alison",
      "avatar_url": "https://..."
    },
    "stats": {
      "today_capture_count": 16,
      "pending_task_count": 8,
      "knowledge_items_count": 735,
      "weekly_growth_rate": 0.12
    },
    "quick_actions": [
      { "key": "text", "label": "记录想法", "icon": "edit" },
      { "key": "link", "label": "添加链接", "icon": "link" },
      { "key": "audio", "label": "语音输入", "icon": "mic" },
      { "key": "file", "label": "上传文件", "icon": "upload" }
    ],
    "tasks": [
      {
        "id": "task_001",
        "title": "完善 PRD 接口字段",
        "status": "todo",
        "priority": "high",
        "due_at": "2026-05-06T18:00:00+08:00"
      }
    ],
    "insight_preview": {
      "title": "最近关注产品架构",
      "summary": "过去 7 天产品、AI、知识库内容占比最高。"
    }
  },
  "request_id": "req_001"
}
```

前端用途：

- 左侧用户信息。
- 首页右侧统计卡。
- 待办数量。
- 知识库数量。
- 输入框快捷入口。
- 空态和初始化状态。

---

## 8. Capture / Inbox 接口

### 8.1 创建文本记录

`POST /api/v1/capture/text`

请求：

```json
{
  "content": "今天想到一个新的产品想法...",
  "title": "可选标题",
  "tags": ["产品", "灵感"],
  "target_folder_id": "folder_001",
  "auto_process": true
}
```

响应：

```json
{
  "success": true,
  "data": {
    "inbox_item": {
      "id": "inbox_001",
      "type": "text",
      "status": "received",
      "processing_status": "queued",
      "created_at": "2026-05-04T10:00:00+08:00"
    },
    "job": {
      "id": "job_001",
      "status": "queued"
    }
  },
  "request_id": "req_001"
}
```

### 8.2 创建链接记录

`POST /api/v1/capture/link`

请求：

```json
{
  "url": "https://example.com/article",
  "note": "这篇文章值得分析",
  "tags": ["AI", "文章"],
  "auto_process": true
}
```

响应需返回：

- `inbox_item_id`
- `source_id`
- `job_id`
- `fetch_status`

### 8.3 获取上传预签名地址

`POST /api/v1/uploads/presign`

请求：

```json
{
  "filename": "产品设计.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 2048000
}
```

响应：

```json
{
  "success": true,
  "data": {
    "upload_id": "upl_001",
    "upload_url": "https://object-storage/presign-url",
    "file_url": "https://object-storage/file-url",
    "expires_in": 900
  },
  "request_id": "req_001"
}
```

### 8.4 文件上传完成确认

`POST /api/v1/capture/file/commit`

请求：

```json
{
  "upload_id": "upl_001",
  "filename": "产品设计.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 2048000,
  "target_folder_id": "folder_001",
  "auto_process": true
}
```

响应：

```json
{
  "success": true,
  "data": {
    "source_id": "src_001",
    "document_id": "doc_001",
    "job_id": "job_001",
    "status": "processing"
  },
  "request_id": "req_001"
}
```

### 8.5 查询 Inbox 列表

`GET /api/v1/inbox`

参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| type | string | text/link/file/image/audio |
| status | string | received/processing/processed/failed |
| keyword | string | 搜索关键词 |
| page | number | 页码 |
| page_size | number | 每页数量 |

### 8.6 更新 Inbox 状态

`PATCH /api/v1/inbox/{id}`

请求：

```json
{
  "status": "archived",
  "tags": ["产品", "已整理"],
  "target_folder_id": "folder_001"
}
```

---

## 9. Feed / 内容流接口

### 9.1 获取首页内容流

`GET /api/v1/feed`

参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| view | string | card/list/table |
| type | string | note/article/file/image/audio/task/ai_output |
| sort_by | string | created_at/updated_at/relevance |
| sort_order | string | desc/asc |
| tag | string | 标签过滤 |
| date_range | string | today/week/month/all |
| page | number | 页码 |
| page_size | number | 每页数量 |

响应：

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "card_001",
        "title": "AI 产品设计参考",
        "summary": "这是一条自动整理后的内容摘要...",
        "cover_url": "https://...",
        "content_type": "article",
        "tags": ["AI", "产品"],
        "source": {
          "id": "src_001",
          "type": "link",
          "name": "example.com"
        },
        "is_favorite": false,
        "created_at": "2026-05-04T10:00:00+08:00",
        "updated_at": "2026-05-04T10:00:00+08:00"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 88,
      "has_more": true
    },
    "facets": {
      "types": [
        { "value": "article", "label": "文章", "count": 12 },
        { "value": "note", "label": "笔记", "count": 26 }
      ],
      "tags": [
        { "value": "AI", "count": 15 },
        { "value": "产品", "count": 9 }
      ]
    }
  },
  "request_id": "req_001"
}
```

### 9.2 获取卡片详情

`GET /api/v1/cards/{id}`

响应包括：

- 卡片基础信息。
- 原始来源。
- 摘要。
- 标签。
- 关联文档。
- AI 建议。
- 可执行操作。

### 9.3 创建卡片

`POST /api/v1/cards`

请求：

```json
{
  "title": "新的内容卡片",
  "summary": "摘要内容",
  "content": "正文内容",
  "content_type": "note",
  "folder_id": "folder_001",
  "tags": ["产品"]
}
```

### 9.4 更新卡片

`PATCH /api/v1/cards/{id}`

支持更新：

- `title`
- `summary`
- `content`
- `tags`
- `folder_id`
- `is_favorite`
- `is_archived`

### 9.5 删除卡片

`DELETE /api/v1/cards/{id}`

默认软删除。

### 9.6 收藏/取消收藏

`POST /api/v1/cards/{id}/favorite`

请求：

```json
{
  "is_favorite": true
}
```

---

## 10. Knowledge Base 知识库接口

### 10.1 获取知识库概览

`GET /api/v1/kb/overview`

响应：

```json
{
  "success": true,
  "data": {
    "stats": {
      "folder_count": 6,
      "document_count": 735,
      "favorite_count": 18,
      "recent_updated_count": 16
    },
    "recent_documents": [],
    "favorite_folders": []
  },
  "request_id": "req_001"
}
```

### 10.2 获取文件夹列表

`GET /api/v1/kb/folders`

参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| parent_id | string | 父文件夹，空表示根目录 |
| keyword | string | 文件夹搜索 |
| include_counts | boolean | 是否返回数量 |

响应：

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "folder_001",
        "name": "产品设计",
        "description": "产品设计相关文档",
        "parent_id": null,
        "document_count": 18,
        "card_count": 36,
        "is_favorite": true,
        "updated_at": "2026-05-04T10:00:00+08:00"
      }
    ]
  },
  "request_id": "req_001"
}
```

### 10.3 创建文件夹

`POST /api/v1/kb/folders`

请求：

```json
{
  "name": "产品设计",
  "description": "产品设计资料",
  "parent_id": null,
  "color": "blue"
}
```

### 10.4 更新文件夹

`PATCH /api/v1/kb/folders/{folder_id}`

请求：

```json
{
  "name": "产品设计资料库",
  "description": "更新后的说明",
  "is_favorite": true,
  "sort_order": 20
}
```

### 10.5 删除文件夹

`DELETE /api/v1/kb/folders/{folder_id}`

删除规则：

- 默认软删除。
- 若文件夹下存在文档，必须支持两种策略：
  - `move_to_root`
  - `delete_children`

请求：

```json
{
  "strategy": "move_to_root"
}
```

### 10.6 获取文档列表

`GET /api/v1/kb/documents`

参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| folder_id | string | 文件夹 ID |
| document_type | string | 文档类型 |
| keyword | string | 关键词 |
| tag | string | 标签 |
| status | string | ready/processing/failed |
| sort_by | string | updated_at/created_at/title |
| sort_order | string | desc/asc |
| page | number | 页码 |
| page_size | number | 数量 |

响应：

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "doc_001",
        "title": "UI 设计规范",
        "summary": "文档摘要...",
        "document_type": "pdf",
        "status": "ready",
        "folder_id": "folder_001",
        "tags": ["UI"],
        "word_count": 4200,
        "is_favorite": false,
        "updated_at": "2026-05-04T10:00:00+08:00"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 18,
      "has_more": false
    }
  },
  "request_id": "req_001"
}
```

### 10.7 获取文档详情

`GET /api/v1/kb/documents/{document_id}`

响应：

```json
{
  "success": true,
  "data": {
    "id": "doc_001",
    "title": "UI 设计规范",
    "summary": "文档摘要...",
    "content": "Markdown 正文...",
    "document_type": "pdf",
    "status": "ready",
    "folder": {
      "id": "folder_001",
      "name": "产品设计"
    },
    "source": {
      "id": "src_001",
      "name": "UI 设计规范.pdf",
      "url": "https://..."
    },
    "tags": ["UI", "设计"],
    "chunks_preview": [
      {
        "id": "chunk_001",
        "content": "文档第一段内容...",
        "metadata": { "page": 1 }
      }
    ],
    "related_cards": [],
    "ai_suggestions": [
      {
        "type": "ask_ai",
        "label": "让 Mydow AI 总结这份文档"
      }
    ],
    "created_at": "2026-05-04T10:00:00+08:00",
    "updated_at": "2026-05-04T10:00:00+08:00"
  },
  "request_id": "req_001"
}
```

### 10.8 更新文档

`PATCH /api/v1/kb/documents/{document_id}`

支持字段：

- `title`
- `summary`
- `content`
- `folder_id`
- `tags`
- `is_favorite`

### 10.9 删除文档

`DELETE /api/v1/kb/documents/{document_id}`

### 10.10 移动文档

`POST /api/v1/kb/documents/{document_id}/move`

请求：

```json
{
  "target_folder_id": "folder_002"
}
```

---

## 11. Mydow AI 接口

### 11.1 获取会话列表

`GET /api/v1/ai/conversations`

参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| keyword | string | 搜索会话标题 |
| page | number | 页码 |
| page_size | number | 数量 |

响应：

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "conv_001",
        "title": "产品 PRD 讨论",
        "last_message_preview": "我们可以从数据模型开始...",
        "message_count": 12,
        "updated_at": "2026-05-04T10:00:00+08:00"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 3,
      "has_more": false
    }
  },
  "request_id": "req_001"
}
```

### 11.2 创建会话

`POST /api/v1/ai/conversations`

请求：

```json
{
  "title": "新的对话",
  "mode": "general",
  "context_scope": {
    "folder_ids": [],
    "document_ids": [],
    "include_recent": true
  }
}
```

响应：

```json
{
  "success": true,
  "data": {
    "id": "conv_001",
    "title": "新的对话",
    "mode": "general",
    "created_at": "2026-05-04T10:00:00+08:00"
  },
  "request_id": "req_001"
}
```

### 11.3 获取会话详情与消息

`GET /api/v1/ai/conversations/{conversation_id}`

响应包括：

- 会话基础信息。
- 消息列表。
- 引用列表。
- 右侧相关上下文。
- 建议继续提问。

### 11.4 发送消息

`POST /api/v1/ai/conversations/{conversation_id}/messages`

请求：

```json
{
  "content": "请帮我总结最近关于产品设计的内容",
  "attachments": [
    {
      "source_id": "src_001"
    }
  ],
  "context_scope": {
    "folder_ids": ["folder_001"],
    "document_ids": [],
    "include_recent": true
  },
  "stream": true
}
```

响应非流式：

```json
{
  "success": true,
  "data": {
    "user_message_id": "msg_user_001",
    "assistant_message_id": "msg_ai_001",
    "status": "running"
  },
  "request_id": "req_001"
}
```

流式建议：

- SSE Endpoint：`GET /api/v1/ai/messages/{assistant_message_id}/stream`
- 事件类型：
  - `message.delta`
  - `message.citation`
  - `message.tool_call`
  - `message.completed`
  - `message.error`

SSE 示例：

```text
event: message.delta
data: {"delta":"这是"}

event: message.delta
data: {"delta":"一段回答"}

event: message.citation
data: {"document_id":"doc_001","chunk_id":"chunk_001","title":"UI 设计规范"}

event: message.completed
data: {"message_id":"msg_ai_001","status":"completed"}
```

### 11.5 停止生成

`POST /api/v1/ai/messages/{message_id}/cancel`

### 11.6 重新生成回答

`POST /api/v1/ai/messages/{message_id}/regenerate`

### 11.7 将 AI 输出保存为知识库文档

`POST /api/v1/ai/messages/{message_id}/save-to-kb`

请求：

```json
{
  "folder_id": "folder_001",
  "title": "AI 生成的产品分析",
  "tags": ["AI输出", "产品"]
}
```

### 11.8 将 AI 输出保存为任务

`POST /api/v1/ai/messages/{message_id}/create-tasks`

请求：

```json
{
  "tasks": [
    {
      "title": "补充知识库接口",
      "due_at": "2026-05-06T18:00:00+08:00",
      "priority": "high"
    }
  ]
}
```

---

## 12. Insight / 右侧分析栏接口

### 12.1 获取洞察概览

`GET /api/v1/insights/summary`

参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| range | string | today/week/month/all |
| source | string | 来源类型 |

响应：

```json
{
  "success": true,
  "data": {
    "stats": {
      "capture_count": 16,
      "knowledge_count": 735,
      "task_count": 8,
      "completed_task_count": 3
    },
    "theme_distribution": [
      { "name": "产品设计", "value": 42 },
      { "name": "AI", "value": 28 },
      { "name": "运营", "value": 18 }
    ],
    "quality_distribution": [
      { "name": "高价值", "value": 30 },
      { "name": "待整理", "value": 12 }
    ],
    "insights": [
      {
        "id": "insight_001",
        "title": "产品设计内容持续增加",
        "summary": "最近 7 天新增 12 条产品相关内容。",
        "insight_type": "theme_trend"
      }
    ],
    "recommended_actions": [
      {
        "type": "generate_report",
        "label": "生成日报"
      }
    ]
  },
  "request_id": "req_001"
}
```

### 12.2 获取洞察列表

`GET /api/v1/insights`

参数：

- `insight_type`
- `status`
- `range`
- `page`
- `page_size`

### 12.3 生成日报/周报/月报

`POST /api/v1/reports/generate`

请求：

```json
{
  "report_type": "daily",
  "time_range": {
    "start": "2026-05-04T00:00:00+08:00",
    "end": "2026-05-04T23:59:59+08:00"
  },
  "include_sources": true,
  "save_to_kb": true
}
```

响应：

```json
{
  "success": true,
  "data": {
    "job_id": "job_001",
    "status": "queued"
  },
  "request_id": "req_001"
}
```

### 12.4 获取报告详情

`GET /api/v1/reports/{report_id}`

---

## 13. Global Search 全局搜索接口

### 13.1 搜索

`GET /api/v1/search`

参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| q | string | 搜索词 |
| type | string | card/document/folder/task/message/skill/insight |
| mode | string | hybrid/semantic/keyword |
| page | number | 页码 |
| page_size | number | 数量 |

响应：

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "object_type": "document",
        "object_id": "doc_001",
        "title": "UI 设计规范",
        "summary": "命中的摘要内容...",
        "highlight": "...首页包含 <mark>输入区</mark> 和内容流...",
        "score": 0.89,
        "url": "/kb/doc_001",
        "updated_at": "2026-05-04T10:00:00+08:00"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 10,
      "total": 24,
      "has_more": true
    },
    "facets": {
      "types": [
        { "value": "document", "count": 12 },
        { "value": "card", "count": 8 }
      ]
    }
  },
  "request_id": "req_001"
}
```

### 13.2 命令建议

`GET /api/v1/search/suggestions`

参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| q | string | 输入中的搜索词 |

响应：

```json
{
  "success": true,
  "data": {
    "suggestions": [
      {
        "type": "command",
        "label": "新建任务",
        "command": "/new task"
      },
      {
        "type": "document",
        "label": "UI 设计规范",
        "object_id": "doc_001"
      }
    ]
  },
  "request_id": "req_001"
}
```

---

## 14. Task 接口

### 14.1 获取任务列表

`GET /api/v1/tasks`

参数：

- `status`
- `priority`
- `due_range`
- `source_type`
- `page`
- `page_size`

### 14.2 创建任务

`POST /api/v1/tasks`

请求：

```json
{
  "title": "完成后端 PRD",
  "description": "补齐接口和验收标准",
  "priority": "high",
  "due_at": "2026-05-06T18:00:00+08:00",
  "tags": ["后端"]
}
```

### 14.3 更新任务

`PATCH /api/v1/tasks/{task_id}`

### 14.4 完成任务

`POST /api/v1/tasks/{task_id}/complete`

---

## 15. Notifications 通知接口

### 15.1 获取未读通知数量

`GET /api/v1/notifications/unread-count`

响应：

```json
{
  "success": true,
  "data": {
    "count": 3
  },
  "request_id": "req_001"
}
```

### 15.2 获取通知列表

`GET /api/v1/notifications`

参数：

- `is_read`
- `type`
- `page`
- `page_size`

### 15.3 标记已读

`POST /api/v1/notifications/{notification_id}/read`

### 15.4 全部已读

`POST /api/v1/notifications/read-all`

---

## 16. Jobs 异步任务接口

### 16.1 获取任务状态

`GET /api/v1/jobs/{job_id}`

响应：

```json
{
  "success": true,
  "data": {
    "id": "job_001",
    "job_type": "parse_file",
    "status": "running",
    "progress": 45,
    "error": null,
    "created_at": "2026-05-04T10:00:00+08:00",
    "updated_at": "2026-05-04T10:01:00+08:00"
  },
  "request_id": "req_001"
}
```

### 16.2 取消任务

`POST /api/v1/jobs/{job_id}/cancel`

### 16.3 前端轮询策略

- `queued/running`：每 2 秒请求一次。
- 超过 60 秒未完成：降低为每 5 秒一次。
- `completed/failed/canceled`：停止轮询。
- 文件解析失败时，后端必须返回可展示的错误文案。

---

## 17. Skills 广场接口

### 17.1 获取 Skill 列表

`GET /api/v1/skills`

参数：

- `category`
- `keyword`
- `status`
- `page`
- `page_size`

响应：

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "skill_001",
        "name": "会议纪要生成",
        "description": "将录音或文本整理为会议纪要。",
        "category": "productivity",
        "icon": "sparkles",
        "is_installed": true,
        "usage_count": 12
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 10,
      "has_more": false
    }
  },
  "request_id": "req_001"
}
```

### 17.2 获取 Skill 详情

`GET /api/v1/skills/{skill_id}`

### 17.3 运行 Skill

`POST /api/v1/skills/{skill_id}/run`

请求：

```json
{
  "input": {
    "source_id": "src_001",
    "instruction": "请生成会议纪要"
  },
  "save_output": true
}
```

响应：

```json
{
  "success": true,
  "data": {
    "job_id": "job_001",
    "skill_run_id": "run_001",
    "status": "queued"
  },
  "request_id": "req_001"
}
```

---

## 18. 数字花园接口预留

虽然当前 UI 中数字花园入口已存在，但 V1 可先提供基础接口，保证页面能加载空态或简化图谱。

### 18.1 获取图谱概览

`GET /api/v1/garden/overview`

响应：

```json
{
  "success": true,
  "data": {
    "node_count": 128,
    "edge_count": 245,
    "strong_edge_count": 36,
    "top_topics": ["产品设计", "AI", "运营"],
    "recent_insights": []
  },
  "request_id": "req_001"
}
```

### 18.2 获取图谱节点和边

`GET /api/v1/garden/graph`

参数：

- `range`
- `topic`
- `depth`
- `limit`

响应：

```json
{
  "success": true,
  "data": {
    "nodes": [
      {
        "id": "node_001",
        "label": "产品设计",
        "type": "topic",
        "size": 12,
        "object_type": "folder",
        "object_id": "folder_001"
      }
    ],
    "edges": [
      {
        "id": "edge_001",
        "source": "node_001",
        "target": "node_002",
        "weight": 0.82,
        "relation_type": "semantic_related"
      }
    ]
  },
  "request_id": "req_001"
}
```

---

## 19. 解析、索引与 AI 流水线

### 19.1 Ingestion Pipeline

每个输入项进入系统后，统一走以下流水线：

1. Receive：接收输入，创建 InboxItem / Source。
2. Normalize：标准化格式，提取文本。
3. Parse：解析文件、网页、音频转写、图片 OCR。
4. Summarize：生成标题、摘要、关键点。
5. Classify：识别类型、主题、标签、实体。
6. Chunk：按语义或长度切分。
7. Embed：生成向量。
8. Index：写入统一搜索索引。
9. Persist：生成 Card / Document。
10. Notify：通知前端任务完成。

### 19.2 内容解析要求

| 输入类型 | V1 处理能力 | 产物 |
|---|---|---|
| 文本 | 直接保存、摘要、标签 | InboxItem, Card, Chunk |
| 链接 | 抓取网页标题、正文、封面 | Source, Document, Card |
| PDF | 提取文本、页码、摘要 | Source, Document, Chunk |
| DOCX | 提取段落、标题 | Source, Document, Chunk |
| PPTX | 提取页面文本，保留文件来源 | Source, Document, Chunk |
| 图片 | 保存文件，V1 可做简单 OCR | Source, Card |
| 音频 | V1 可接入转写服务 | Source, Transcript, Document |

### 19.3 搜索索引策略

V1 使用混合检索：

- 语义检索：70%。
- 关键词检索：30%。
- 支持对象类型过滤。
- 支持标签过滤。
- 支持时间排序。
- 支持高亮。

---

## 20. 前端状态支持要求

为保证前端能完整跑通，每个核心接口都必须能支持以下 UI 状态。

### 20.1 Loading

接口请求中，前端展示骨架屏。

后端要求：

- 接口响应时间可观测。
- 慢接口必须有异步 job 方案。

### 20.2 Empty

列表为空时，后端返回空数组，而不是错误。

示例：

```json
{
  "success": true,
  "data": {
    "items": [],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 0,
      "has_more": false
    }
  }
}
```

### 20.3 Error

接口失败时必须返回：

- `error.code`
- `error.message`
- `request_id`

前端可展示用户可理解文案。

### 20.4 Processing

文件解析、AI 生成、报告生成、Skill 运行必须返回 job 状态。

### 20.5 Permission Denied

无权限时返回 403，不能返回空数据伪装成功。

---

## 21. 数据库设计建议

### 21.1 推荐技术栈

结合 V1 快速交付，建议：

- API：Node.js / NestJS 或 Next.js Route Handlers。
- DB：MongoDB 或 PostgreSQL。
- 向量库：pgvector / Qdrant / Pinecone。
- 缓存：Redis。
- 对象存储：S3 / R2 / OSS。
- 队列：BullMQ / Cloud Tasks / Inngest。
- AI：OpenAI / Anthropic / Gemini / 国内模型可通过 Provider 抽象层接入。

如果团队当前以 Node.js + Serverless + Mongo 为主，V1 可以采用：

- Next.js 前端。
- Node.js 后端。
- MongoDB 存核心业务数据。
- Qdrant / pgvector 存向量。
- S3/R2 存上传文件。
- Redis/BullMQ 跑异步任务。

### 21.2 核心集合 / 表

| 表/集合 | 说明 |
|---|---|
| users | 用户 |
| user_preferences | 用户设置 |
| inbox_items | 输入项 |
| sources | 原始来源 |
| cards | 首页内容卡片 |
| folders | 知识库文件夹 |
| documents | 知识库文档 |
| chunks | 文档分块 |
| tasks | 任务 |
| insights | 洞察 |
| reports | 报告 |
| conversations | AI 会话 |
| messages | AI 消息 |
| skills | Skill 定义 |
| skill_runs | Skill 运行记录 |
| search_documents | 搜索索引元数据 |
| ingestion_jobs | 异步任务 |
| notifications | 通知 |
| audit_logs | 操作日志 |

### 21.3 必要索引

| 集合 | 索引 |
|---|---|
| inbox_items | user_id + created_at, user_id + status |
| cards | user_id + created_at, user_id + folder_id, user_id + tags |
| folders | user_id + parent_id, user_id + name |
| documents | user_id + folder_id, user_id + updated_at, user_id + status |
| chunks | document_id + chunk_index, user_id + source_id |
| tasks | user_id + status + due_at |
| conversations | user_id + updated_at |
| messages | conversation_id + created_at |
| notifications | user_id + is_read + created_at |
| jobs | user_id + status + created_at |
| search_documents | user_id + object_type + updated_at |

---

## 22. 安全与合规要求

### 22.1 鉴权

- 所有 `/api/v1/*` 默认需要登录。
- 静态公开接口除外。
- Session 过期时返回 401。

### 22.2 文件安全

- 上传文件大小限制：V1 默认单文件 50MB，可配置。
- 支持 MIME 类型白名单。
- 上传后进行基础病毒/恶意内容扫描，或至少预留扫描状态。
- 文件 URL 不直接公开，使用签名 URL。

### 22.3 AI 隐私

- 所有发送给模型的上下文需要记录调用日志。
- 用户可关闭“使用个人知识库作为 AI 上下文”。
- AI 响应必须记录引用来源，避免黑盒生成。

### 22.4 删除策略

- 用户删除文档时软删除。
- 软删除后默认 30 天内可恢复。
- 彻底删除时需要同步删除对象存储、chunk、embedding、search index。

---

## 23. 埋点与可观测性

### 23.1 关键业务指标

| 指标 | 说明 |
|---|---|
| capture_created_count | 用户新增输入数量 |
| capture_processed_success_rate | 输入处理成功率 |
| document_uploaded_count | 上传文档数量 |
| ai_message_count | AI 对话数量 |
| search_query_count | 搜索次数 |
| report_generated_count | 报告生成数量 |
| job_failed_rate | 异步任务失败率 |

### 23.2 日志要求

每个请求记录：

- `request_id`
- `user_id`
- `endpoint`
- `latency_ms`
- `status_code`
- `error_code`

每个 AI 调用记录：

- `provider`
- `model`
- `input_tokens`
- `output_tokens`
- `latency_ms`
- `cost_estimate`
- `context_document_ids`

---

## 24. MVP 交付优先级

### 24.1 P0：前端必须跑通

| 编号 | 模块 | 交付内容 |
|---|---|---|
| B-01 | Auth/User | 登录态、用户信息接口 |
| B-02 | Today | `/today` 聚合接口 |
| B-03 | Capture | 文本记录、文件上传、链接记录 |
| B-04 | Feed | 首页内容流、卡片详情、收藏 |
| B-05 | KB Folder | 文件夹增删改查 |
| B-06 | KB Document | 文档列表、详情、移动、删除 |
| B-07 | Job | 异步任务状态查询 |
| B-08 | Notification | 未读数量、通知列表 |
| B-09 | AI Chat | 会话、消息、流式输出 |
| B-10 | Search | 全局搜索基础版 |

### 24.2 P1：体验增强

| 编号 | 模块 | 交付内容 |
|---|---|---|
| B-11 | Insight | 右侧洞察统计 |
| B-12 | Report | 日报/周报生成 |
| B-13 | Index | embedding + 语义检索 |
| B-14 | Skills | Skill 列表与运行 |
| B-15 | Garden | 数字花园基础图谱 |

### 24.3 P2：后续扩展

| 编号 | 模块 | 交付内容 |
|---|---|---|
| B-16 | Integration | 第三方数据源接入 |
| B-17 | Permission | 多 Workspace 权限 |
| B-18 | Billing | 订阅与积分 |
| B-19 | Marketplace | Skill 市场交易 |

---

## 25. 前后端联调数据契约

### 25.1 前端路由与后端接口映射

| 前端路由 | 页面 | 首屏必调接口 |
|---|---|---|
| `/today` | 首页/灵感采集 | `/me`, `/today`, `/feed`, `/insights/summary`, `/notifications/unread-count` |
| `/kb` | 知识库首页 | `/kb/overview`, `/kb/folders`, `/kb/documents` |
| `/kb/:folderId` | 文件夹详情 | `/kb/folders/:id`, `/kb/documents?folder_id=xxx` |
| `/kb/doc/:documentId` | 文档详情 | `/kb/documents/:id` |
| `/ai` | Mydow AI 空态/首页 | `/ai/conversations` |
| `/ai/:conversationId` | AI 对话详情 | `/ai/conversations/:id` |
| `/skills` | Skills 广场 | `/skills` |
| `/garden` | 数字花园 | `/garden/overview`, `/garden/graph` |
| 全局搜索弹窗 | 搜索/命令 | `/search/suggestions`, `/search` |

### 25.2 首屏接口性能目标

| 接口 | P95 响应时间 |
|---|---:|
| `/me` | < 200ms |
| `/today` | < 500ms |
| `/feed` | < 700ms |
| `/kb/folders` | < 500ms |
| `/kb/documents` | < 700ms |
| `/ai/conversations` | < 600ms |
| `/search/suggestions` | < 300ms |

### 25.3 Mock 数据要求

后端必须提供 seed 脚本，至少生成：

- 1 个测试用户。
- 6 个知识库文件夹。
- 20 个文档。
- 30 张内容卡片。
- 5 条任务。
- 5 条通知。
- 3 个 AI 会话。
- 10 条 AI 消息。
- 5 个 Skills。
- 10 条 SearchDocument。

前端开发环境可通过 `.env` 切换：

- `NEXT_PUBLIC_API_BASE_URL=http://localhost:3001/api/v1`
- `NEXT_PUBLIC_USE_MOCK=false`

---

## 26. 验收标准

### 26.1 首页验收

用户进入首页后必须满足：

- 页面能显示用户头像、名称。
- 内容流能真实加载卡片。
- 卡片支持收藏、打开详情。
- 输入文本后能生成一条记录。
- 上传文件后能在知识库看到处理中状态。
- 右侧统计能显示真实数量。
- 无数据时显示空态，不报错。

### 26.2 知识库验收

- 能加载文件夹网格。
- 能新建、重命名、收藏、删除文件夹。
- 能进入文件夹并看到文档列表。
- 能上传文件并生成文档。
- 文档解析完成后能搜索到。
- 文档详情能看到摘要、正文、来源。

### 26.3 Mydow AI 验收

- 能创建新会话。
- 能发送消息。
- 能流式返回 AI 回答。
- AI 回答能保存会话历史。
- 有知识库上下文时能返回引用。
- 能停止生成和重新生成。
- 能将 AI 回答保存为文档或任务。

### 26.4 搜索验收

- 顶部搜索框可输入关键词。
- 能搜索到文档、卡片、任务、AI 会话。
- 搜索结果有标题、摘要、高亮、类型。
- 支持跳转到对应页面。

### 26.5 通知验收

- 顶部通知显示未读数量。
- 文件解析完成后生成通知。
- AI 报告生成完成后生成通知。
- 通知可以标记已读。

### 26.6 异步任务验收

- 文件上传后返回 job_id。
- 前端可查询 job 状态。
- job 完成后生成 document/card/index。
- job 失败后返回失败原因并生成通知。

---

## 27. 开发里程碑建议

### Week 1：基础接口与首页跑通

| 序号 | 行动项 | 交付物 |
|---|---|---|
| 1 | 完成 Auth/User 基础能力 | `/me` |
| 2 | 完成 Today 聚合接口 | `/today` |
| 3 | 完成 Feed 列表与卡片详情 | `/feed`, `/cards/:id` |
| 4 | 完成文本 Capture | `/capture/text` |
| 5 | 完成通知未读数量 | `/notifications/unread-count` |

### Week 2：知识库与上传跑通

| 序号 | 行动项 | 交付物 |
|---|---|---|
| 1 | 完成文件夹 CRUD | `/kb/folders` |
| 2 | 完成文档列表/详情 | `/kb/documents` |
| 3 | 完成上传预签名与 commit | `/uploads/presign`, `/capture/file/commit` |
| 4 | 完成异步任务状态 | `/jobs/:id` |
| 5 | 完成基础解析与索引 | Source/Document/Chunk/SearchDocument |

### Week 3：Mydow AI 与搜索跑通

| 序号 | 行动项 | 交付物 |
|---|---|---|
| 1 | 完成 AI 会话 CRUD | `/ai/conversations` |
| 2 | 完成消息发送与流式输出 | `/messages`, `/stream` |
| 3 | 完成知识库上下文检索 | citations |
| 4 | 完成全局搜索 | `/search` |
| 5 | 完成 AI 输出保存为文档/任务 | save-to-kb/create-tasks |

### Week 4：洞察、报告、Skills 与数字花园基础

| 序号 | 行动项 | 交付物 |
|---|---|---|
| 1 | 完成右侧洞察统计 | `/insights/summary` |
| 2 | 完成日报/周报生成 | `/reports/generate` |
| 3 | 完成 Skills 列表与运行 | `/skills`, `/skills/:id/run` |
| 4 | 完成数字花园基础图谱 | `/garden/overview`, `/garden/graph` |
| 5 | 完成整体压测与异常状态 | 验收报告 |

---

## 28. 后端完成定义 Definition of Done

一个接口只有满足以下条件才算完成：

1. 数据真实落库。
2. 有鉴权与 user_id 隔离。
3. 有参数校验。
4. 有统一错误返回。
5. 有接口文档。
6. 有单元测试或集成测试。
7. 有 seed/mock 数据。
8. 前端能联调通过。
9. 有 Loading / Empty / Error / Success 对应状态。
10. 关键操作有日志。

---

## 29. 关键风险与解决方案

| 风险 | 表现 | 解决方案 |
|---|---|---|
| 前端字段不稳定 | 页面频繁改字段 | 先冻结 DTO，后端内部模型可变化 |
| AI 接口慢 | 页面等待时间过长 | 全部长任务异步化，AI 输出流式返回 |
| 文件解析失败 | 上传后无反馈 | Job 状态 + Notification + 可重试 |
| 搜索结果不准 | 找不到内容 | 先关键词，后混合检索，逐步调权重 |
| 数据关系混乱 | Card/Document/Source 重复 | 统一 Source -> Document/Card 的生成规则 |
| 成本不可控 | AI 调用过多 | 限流、缓存摘要、记录 token 成本 |

---

## 30. V1 最小可运行闭环

后端 V1 的最小闭环定义为：

用户登录 → 首页加载 → 输入一条想法 → 后端生成 InboxItem → 异步整理成 Card → 首页内容流展示 → 进入知识库看到文档/卡片 → 使用 Mydow AI 提问 → AI 检索知识库并回答 → 回答保存为文档或任务 → 通知中心提示完成。

只要这个闭环能跑通，当前一级功能 UI 就具备了从展示型 Demo 进入真实产品原型的基础。

