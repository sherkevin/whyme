# Mydow Web API Contract v1.4

更新时间：2026-05-06  
适用前端：`mydow.html` v1.4 Final UX Interaction Update

## 1. 通用协议

### 1.1 Base URL

```text
/api/v1
```

### 1.2 Auth

```http
Authorization: Bearer <accessToken>
Content-Type: application/json
```

文件上传使用 `multipart/form-data`。

### 1.3 通用响应

```json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "requestId": "req_20260506_0001"
}
```

### 1.4 分页响应

```json
{
  "items": [],
  "page": 1,
  "pageSize": 20,
  "total": 120,
  "hasMore": true
}
```

### 1.5 错误响应

```json
{
  "code": 40001,
  "message": "Invalid request",
  "details": {
    "field": "topic",
    "reason": "Topic is required"
  },
  "requestId": "req_20260506_0002"
}
```

## 2. 核心数据模型

### 2.1 User

```ts
type User = {
  id: string;
  name: string;
  email: string;
  avatarUrl?: string;
  plan: "free" | "pro" | "team";
  locale: "zh-CN" | "en-US";
  timezone: string;
};
```

### 2.2 CaptureItem

```ts
type CaptureItem = {
  id: string;
  title: string;
  content: string;
  type: "idea" | "todo" | "file" | "link" | "voice" | "research";
  source: "manual" | "upload" | "web" | "voice" | "ai";
  tags: string[];
  favorite: boolean;
  createdAt: string;
  updatedAt: string;
  summary?: string;
  folderId?: string;
};
```

### 2.3 Knowledge

```ts
type KBFolder = {
  id: string;
  name: string;
  description?: string;
  category: "mine" | "auto" | "favorite";
  docCount: number;
  updatedAt: string;
};

type KBDoc = {
  id: string;
  folderId: string;
  title: string;
  content: string;
  type: "doc" | "summary" | "research" | "import";
  tags: string[];
  updatedAt: string;
};
```

### 2.4 Digital Garden

```ts
type GardenNode = {
  id: string;
  title: string;
  type: "note" | "link" | "audio" | "research" | "insight" | "strategy" | "user";
  x?: number;
  y?: number;
  sourceId?: string;
  sourceType?: "capture" | "kbDoc" | "insight";
  count?: number;
};

type GardenEdge = {
  id: string;
  source: string;
  target: string;
  weight: number;
  relation: "references" | "supports" | "similar" | "derived_from";
};
```

### 2.5 Insight

```ts
type Insight = {
  id: string;
  title: string;
  summary: string;
  type: "insight";
  colorType: "yellow" | "green" | "blue" | "purple";
  createdAt: string;
  sourceId?: string;
  connectedNotes: ConnectedNote[];
};

type ConnectedNote = {
  id: string;
  title: string;
  type: "note" | "research" | "link" | "audio";
  updatedAt: string;
  sourceUrl?: string;
};

type NewInsightPayload = {
  topic: string;
  connectedNoteIds: string[];
};
```

### 2.6 AI

```ts
type AIChat = {
  id: string;
  title: string;
  model: string;
  mode: "efficient" | "all" | "research" | "write";
  pinned?: boolean;
  updatedAt: string;
};

type AIMessage = {
  id: string;
  chatId: string;
  role: "user" | "assistant" | "system";
  content: string;
  status: "pending" | "streaming" | "done" | "error";
  createdAt: string;
  contextIds?: string[];
};
```

### 2.7 Notification

```ts
type NotificationItem = {
  id: string;
  title: string;
  body: string;
  type: "ai" | "system" | "collab" | "garden" | "kb";
  unread: boolean;
  targetType: "aiChat" | "insight" | "gardenNode" | "kbFolder" | "kbDoc" | "settings";
  targetId?: string;
  actionLabel?: string;
  createdAt: string;
};
```

## 3. 接口清单

### 3.1 Account / Settings

| Method | Path | 用途 |
|---|---|---|
| `GET` | `/me` | 当前用户信息 |
| `PATCH` | `/me` | 更新个人资料 |
| `POST` | `/auth/logout` | 退出登录 |
| `GET` | `/settings/preferences` | 偏好设置 |
| `PATCH` | `/settings/preferences` | 更新偏好 |
| `GET` | `/settings/notifications` | 通知设置 |
| `PATCH` | `/settings/notifications` | 保存通知设置 |
| `GET` | `/settings/security` | 账户安全配置 |
| `PATCH` | `/settings/security/2fa` | 二步验证开关 |
| `GET` | `/billing/summary` | 会员和用量 |
| `POST` | `/billing/portal-session` | 打开订阅管理 |

### 3.2 Capture / Inspiration

| Method | Path | 前端触发 |
|---|---|---|
| `GET` | `/capture/items` | `data-view-target`, `recordFilter`, 首屏列表 |
| `GET` | `/capture/items/:id` | 打开记录详情 |
| `POST` | `/capture/items` | 发送灵感 |
| `PATCH` | `/capture/items/:id` | 编辑记录 |
| `PATCH` | `/capture/items/:id/favorite` | 收藏 |
| `DELETE` | `/capture/items/:id` | 删除 |
| `POST` | `/capture/upload` | 上传图片 / 文件 |
| `POST` | `/capture/link` | 网页剪藏 |
| `POST` | `/capture/voice/sessions` | 开始录音 |
| `PATCH` | `/capture/voice/sessions/:id` | 暂停 / 继续录音 |
| `POST` | `/capture/voice/sessions/:id/finish` | 结束并保存 |

`GET /capture/items` query:

```ts
{
  view?: "records" | "recent";
  type?: "all" | "idea" | "todo" | "file" | "link" | "voice" | "research";
  keyword?: string;
  page?: number;
  pageSize?: number;
}
```

### 3.3 Knowledge Base

| Method | Path | 用途 |
|---|---|---|
| `GET` | `/kb/folders` | 文件夹列表 |
| `POST` | `/kb/folders` | 新建文件夹 |
| `GET` | `/kb/folders/:id` | 文件夹详情 |
| `PATCH` | `/kb/folders/:id` | 重命名 / 描述 |
| `DELETE` | `/kb/folders/:id` | 删除文件夹 |
| `POST` | `/kb/folders/:id/duplicate` | 复制文件夹 |
| `PATCH` | `/kb/folders/:id/move` | 移动文件夹 |
| `PATCH` | `/kb/folders/:id/permissions` | 权限设置 |
| `GET` | `/kb/folders/:id/docs` | 文件夹文档列表 |
| `POST` | `/kb/docs` | 新建文档 |
| `GET` | `/kb/docs/:id` | 文档详情 |
| `PATCH` | `/kb/docs/:id` | 保存文档 |
| `DELETE` | `/kb/docs/:id` | 删除文档 |
| `POST` | `/kb/docs/from-capture` | 从灵感生成文档 |
| `POST` | `/kb/docs/from-ai` | 保存 AI 结果为文档 |
| `POST` | `/kb/docs/from-insight` | 保存洞察为文档 |

### 3.4 Digital Garden

| Method | Path | 用途 |
|---|---|---|
| `GET` | `/garden/graph` | 图谱节点和边 |
| `GET` | `/garden/nodes/:id` | 节点详情 |
| `POST` | `/garden/links` | 建立知识连接 |
| `DELETE` | `/garden/links/:id` | 删除连接 |
| `GET` | `/garden/insights/current` | 当前 AI 生成洞察 |
| `GET` | `/garden/insights` | 洞察历史列表 |
| `POST` | `/garden/insights` | 创建自定义洞察 |
| `DELETE` | `/garden/insights/:insightId` | 删除洞察 |
| `DELETE` | `/garden/insights/:insightId/notes/:noteId` | 移除关联笔记 |
| `GET` | `/garden/insights/:insightId/source` | 获取洞察主来源 |

`GET /garden/graph` query:

```ts
{
  range?: "7d" | "30d" | "90d" | "1y" | "all";
  type?: "all" | "note" | "link" | "audio" | "research" | "insight";
  depth?: number;
}
```

`POST /garden/insights` body:

```json
{
  "topic": "Personal Agent 责任性",
  "connectedNoteIds": ["note_agent_responsibility", "note_ai_trust"]
}
```

### 3.5 Insights Center

| Method | Path | 用途 |
|---|---|---|
| `GET` | `/insights/dashboard` | 洞察中心指标和列表 |
| `GET` | `/insights/:id` | 洞察详情 |
| `GET` | `/insights/history` | 历史洞察 |
| `POST` | `/insights/:id/regenerate` | 重新生成 |
| `POST` | `/insights/rules` | 自定义洞察规则 |
| `PATCH` | `/insights/rules/:id` | 更新规则 |
| `DELETE` | `/insights/rules/:id` | 删除规则 |

### 3.6 Mydow AI

| Method | Path | 用途 |
|---|---|---|
| `GET` | `/ai/models` | 可用模型 |
| `GET` | `/ai/chats` | 对话列表 |
| `POST` | `/ai/chats` | 新建对话 |
| `GET` | `/ai/chats/:id` | 对话详情 |
| `PATCH` | `/ai/chats/:id` | 更新标题、模型、模式 |
| `DELETE` | `/ai/chats/:id` | 删除对话 |
| `GET` | `/ai/chats/:id/messages` | 消息列表 |
| `POST` | `/ai/messages` | 发送消息 |
| `GET` | `/ai/messages/:id/stream` | SSE 流式回复，可选 |
| `POST` | `/ai/messages/:id/feedback` | 反馈 |
| `POST` | `/ai/context/search` | 搜索上下文 |
| `POST` | `/ai/chats/:id/context` | 添加上下文 |
| `POST` | `/ai/tasks/summarize` | AI 摘要任务 |
| `POST` | `/ai/tasks/extract-tags` | 提取标签 |

`POST /ai/messages` body:

```json
{
  "chatId": "chat_001",
  "content": "帮我总结最近的产品设计笔记",
  "model": "Mydow Auto",
  "mode": "efficient",
  "contextIds": ["doc_001", "note_002"]
}
```

### 3.7 Skills

| Method | Path | 用途 |
|---|---|---|
| `GET` | `/skills` | Skill 广场列表 |
| `GET` | `/skills/:id` | Skill 详情 |
| `PATCH` | `/skills/:id/favorite` | 收藏 |
| `POST` | `/skills/:id/run` | 运行 Skill |
| `GET` | `/skills/runs/:id` | 运行状态 |

### 3.8 Notifications

| Method | Path | 前端触发 |
|---|---|---|
| `GET` | `/notifications` | `data-open-notifications`, `data-notice-filter`, `notificationFilter` |
| `GET` | `/notifications/stats` | 通知右侧统计卡 |
| `PATCH` | `/notifications/:id/read` | 点击通知行 |
| `POST` | `/notifications/read-all` | `data-notice-quick="markRead"` |
| `DELETE` | `/notifications/:id` | 删除通知 |

`GET /notifications` query:

```ts
{
  type?: "all" | "ai" | "system" | "collab";
  unread?: boolean;
  page?: number;
  pageSize?: number;
}
```

通知行按钮 `data-notice-action` 映射：

| action | targetType | 推荐行为 |
|---|---|---|
| `result` | `insight` / `aiChat` | 打开结果详情或洞察详情 |
| `link` | `gardenNode` | 进入数字花园并高亮节点 |
| `folder` | `kbFolder` | 进入知识库文件夹 |
| `report` | `aiChat` / `kbDoc` | 打开日报详情 |
| `detail` | `kbDoc` / `settings` | 打开对应详情 |

### 3.9 Search

| Method | Path | 前端触发 |
|---|---|---|
| `GET` | `/search` | `data-search-trigger`、搜索输入、搜索筛选 |

`GET /search` query:

```ts
{
  q: string;
  sort?: "relevance" | "updatedAt" | "visitedAt" | "title";
  scope?: "title" | "all" | "tag";
  creator?: string;
  location?: "all" | "current" | "kb" | "garden";
  dateRange?: "all" | "today" | "7d" | "30d";
  limit?: number;
}
```

`SearchResult`:

```ts
type SearchResult = {
  id: string;
  title: string;
  type: "capture" | "kbDoc" | "folder" | "gardenNode" | "aiChat" | "skill" | "notification";
  subtitle?: string;
  targetId: string;
  updatedAt?: string;
};
```

## 4. 前端按钮 / 钩子映射补充

### 4.1 新增或重点钩子

| 钩子 | 所在页面 | 后端建议 |
|---|---|---|
| `data-inline-menu="searchSort"` | 全局搜索 | 更新 `sort` 后重新请求 `/search` |
| `data-inline-menu="searchScope"` | 全局搜索 | 更新 `scope` 后重新请求 `/search` |
| `data-inline-menu="searchCreator"` | 全局搜索 | 更新 `creator` 后重新请求 `/search` |
| `data-inline-menu="searchLocation"` | 全局搜索 | 更新 `location` 后重新请求 `/search` |
| `data-inline-menu="searchDate"` | 全局搜索 | 更新 `dateRange` 后重新请求 `/search` |
| `data-inline-menu="notificationFilter"` | 通知中心 | 请求 `/notifications` |
| `data-notice-filter` | 通知中心 Tab | 请求 `/notifications` |
| `data-notice-action` | 通知行按钮 | 按 notification target 跳转 |
| `data-notice-quick="markRead"` | 通知右侧快捷操作 | `POST /notifications/read-all` |
| `data-open-modal="customInsight"` | 数字花园 / 洞察历史 | 打开新建洞察弹窗 |
| `data-generate-insight` | 新建洞察弹窗 | `POST /garden/insights` |
| `data-note-option` | 新建洞察弹窗 | 前端选择 note，提交时传 ids |
| `data-remove-note` | AI 生成洞察卡片 | `DELETE /garden/insights/:id/notes/:noteId` |

### 4.2 建议不要改名的钩子

- `data-nav-target`
- `data-open-modal`
- `data-open-drawer`
- `data-inline-menu`
- `data-view-target`
- `data-kb-tab`
- `data-kb-view-target`
- `data-ai-chat-open`
- `data-ai-chat-back`
- `data-open-notifications`

这些钩子可直接作为 E2E 测试选择器。

## 5. 后端联调优先级

### P0

1. `GET /me`
2. `GET /capture/items`
3. `POST /capture/items`
4. `GET /kb/folders`
5. `GET /kb/folders/:id/docs`
6. `GET /ai/chats`
7. `POST /ai/messages`
8. `GET /notifications`
9. `POST /notifications/read-all`
10. `GET /search`

### P1

1. 文件上传、网页剪藏、语音输入。
2. 文档创建、文档保存、从 AI/洞察保存到知识库。
3. 数字花园图谱和节点详情。
4. AI 生成洞察、洞察历史、新建洞察。
5. Skills 列表、详情和运行。

### P2

1. 账单、订阅、用量。
2. 权限、协作、团队成员。
3. SSE/WebSocket 实时通知和 AI 流式回复。

## 6. Mock 到真实 API 替换点

在 `mydow.html` 中重点搜索：

```text
simulateAction(
showToast(
openDrawer(
openModal(
data-toast=
```

替换策略：

1. 保留 `openModal/openDrawer` 作为 UI 层。
2. 在点击事件里先执行 API，再按成功结果调用 `showToast` 和刷新 DOM。
3. 对失败返回显示错误 Toast，并保留弹窗内容。
4. 对列表筛选类接口，统一封装 `loadCaptureItems/loadNotifications/loadSearchResults/loadGardenInsights`。

## 7. 测试建议

- 单元测试：API client、数据模型转换、错误处理。
- E2E：使用 `data-*` 选择器覆盖搜索、通知、AI、数字花园、新建洞察。
- 视觉回归：重点测 1366x768、1440x900、1920x1080。
- 长文本测试：洞察标题、关联笔记标题、通知标题、搜索结果标题必须不溢出。
