# AgentOS API 文档

**版本**: v7.2
**最后更新**: 2026-03-01
**基础路径**: `/api`
**API 端点总数**: 162+
**生产状态**: ✅ 可用

---

## 📖 文档导航

### 按角色推荐阅读
- **前端开发者**: 从 [快速开始](#快速开始) 和 [核心 API](#核心-api) 开始
- **后端开发者**: 查看 [完整 API 参考](#完整-api-参考)
- **产品经理**: 查看 [功能模块概览](#功能模块概览)

### 快速链接
- [快速开始](#快速开始)
- [认证与授权](#认证与授权)
- [核心 API](#核心-api)
- [LLM 智能处理](#llm-智能处理) ✨ 新增
- [完整 API 参考](#完整-api-参考)
- [错误处理](#错误处理)

---

## 快速开始

### 1. 基础配置

```javascript
// API 基础配置
const API_BASE_URL = 'http://localhost:8000/api';

// 认证令牌存储
let accessToken = localStorage.getItem('access_token');
```

### 2. 通用请求函数

```javascript
async function apiRequest(endpoint, options = {}) {
  const config = {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${accessToken}`,
      ...options.headers,
    },
  };

  const response = await fetch(`${API_BASE_URL}${endpoint}`, config);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || '请求失败');
  }

  return response.json();
}
```

### 3. 认证流程

```javascript
// 登录
async function login(email, password) {
  const response = await fetch(`${API_BASE_URL}/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  const data = await response.json();
  localStorage.setItem('access_token', data.access_token);
  localStorage.setItem('refresh_token', data.refresh_token);
  return data;
}

// 使用邮箱验证码登录
async function sendVerificationCode(email) {
  const response = await fetch(`${API_BASE_URL}/v1/auth/send-code`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, code_type: 'login' }),
  });
  return response.json();
}

async function loginWithCode(email, code) {
  const response = await fetch(`${API_BASE_URL}/v1/auth/login/email`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, code }),
  });
  const data = await response.json();
  localStorage.setItem('access_token', data.access_token);
  return data;
}
```

---

## 功能模块概览

| 模块 | 端点数量 | 基础路径 | 描述 |
|------|---------|----------|------|
| 🔐 认证系统 | 9 | `/api/v1/auth` | 用户注册、登录、邮箱验证码 |
| 📝 任务管理 | 11 | `/api/v1/tasks` | 任务 CRUD、批量操作、统计 |
| 🧠 知识管理 | 4 | `/api/v1/knowledge` | 卡片管理 |
| 🔍 搜索引擎 | 15 | `/api/v1/search` | 全文搜索、洞察生成 |
| 📥 收件箱 | 6 | `/api/v1/inbox` | 内容收集与处理 |
| 📊 今日概览 | 2 | `/api/v1/today` | 每日聚合视图、Insight ✨ |
| 🤖 Agent 系统 | 18 | `/api/v1/agent` | 工作流、技能、LLM 处理 |
| 🌿 Garden 系统 | 3 | `/api/v1/garden` | 知识图谱、节点列表、边查询 ✨ |
| 💬 对话历史 | 4 | `/api/v1/conversations` | 会话管理 |
| 🔗 连接管理 | 6 | `/connections` | 知识图谱连接 |
| 📁 工作区 | 28 | `/prd4` | 工作区、区域、项目管理 |
| 🔌 集成服务 | 11 | `/integrations` | 微信、爬虫等 |
| 📈 可观测性 | 5 | `/observability` | 监控与指标 |

---

## 核心 API

### 任务管理

#### 获取今日任务
```javascript
// GET /api/v1/tasks/today
const todayTasks = await apiRequest('/v1/tasks/today');
```

#### 创建任务
```javascript
// POST /api/v1/tasks
const newTask = await apiRequest('/v1/tasks', {
  method: 'POST',
  body: JSON.stringify({
    title: "新任务",
    description: "任务描述",
    priority: "medium",
    due_date: "2026-03-01"
  })
});
```

#### 批量操作
```javascript
// 批量创建
await apiRequest('/v1/tasks/batch', {
  method: 'POST',
  body: JSON.stringify({ tasks: [...] })
});

// 批量更新
await apiRequest('/v1/tasks/batch', {
  method: 'PUT',
  body: JSON.stringify({
    ids: ['id1', 'id2'],
    updates: { status: 'completed' }
  })
});
```

---

### 知识管理

#### 创建卡片
```javascript
// POST /api/v1/knowledge/cards
const card = await apiRequest('/v1/knowledge/cards', {
  method: 'POST',
  body: JSON.stringify({
    title: "知识卡片",
    content: "卡片内容",
    type: "note"
  })
});
```

---

### 搜索引擎

#### 搜索查询
```javascript
// GET /api/v1/search?q=keyword
const results = await apiRequest(`/v1/search?q=${encodeURIComponent(keyword)}`);

// 高级搜索
const results = await apiRequest('/v1/search/query', {
  method: 'POST',
  body: JSON.stringify({
    query: "搜索词",
    filters: { type: 'card', date_range: 'last_week' },
    page: 1,
    limit: 20
  })
});
```

---

### 收件箱与 LLM 处理

#### 创建收件箱项目
```javascript
// POST /api/v1/inbox/items
const inboxItem = await apiRequest('/v1/inbox/items', {
  method: 'POST',
  body: JSON.stringify({
    content: "内容",
    source_type: "manual",
    source_meta: {}
  })
});
```

#### 处理收件箱项目（生成摘要和标签）
```javascript
// POST /api/v1/agent/process/{item_id}
const result = await apiRequest(`/v1/agent/process/${itemId}`, {
  method: 'POST'
});
```

**响应示例**:
```json
{
  "success": true,
  "item_id": "item-uuid",
  "title": "自动生成的标题",
  "summary": "AI 生成的摘要内容...",
  "item_type": "note",
  "metadata": {
    "tags": ["标签 1", "标签 2", "标签 3"],
    "llm_summary": true,
    "llm_tags": ["标签 1", "标签 2"]
  }
}
```

---

## LLM 智能处理 ✨

> **版本**: v7.0 新增功能
> **状态**: ✅ 生产可用

### 功能说明

系统集成了 DeepSeek 大模型，可自动为内容生成：
- **智能摘要**: 1-3 句话概括核心内容
- **关键词标签**: 3-8 个相关标签

### 配置

在 `.env` 中启用：
```bash
USE_LLM_PROCESSING=true
DEEPSEEK_API_KEY=sk-xxxxx
BASE_URL=https://api.deepseek.com/v1
```

### API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/agent/tick` | POST | 批量处理收件箱项目 |
| `/api/v1/agent/process/{item_id}` | POST | 处理单个项目 |
| `/api/v1/agent/status` | GET | 获取处理状态 |

### 前端使用示例

```javascript
// 上传内容后自动处理
async function createAndProcess(content) {
  // 1. 创建收件箱项目
  const item = await apiRequest('/v1/inbox/items', {
    method: 'POST',
    body: JSON.stringify({ content })
  });

  // 2. 触发 LLM 处理
  const result = await apiRequest(`/v1/agent/process/${item.id}`, {
    method: 'POST'
  });

  // 3. 获取生成的摘要和标签
  console.log('Summary:', result.summary);
  console.log('Tags:', result.metadata.tags);

  return result;
}
```

---

## 完整 API 参考

### 1. 认证系统 (`/api/v1/auth`)

| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/register` | POST | 用户注册 | ❌ |
| `/login` | POST | 用户名密码登录 | ❌ |
| `/login/email` | POST | 邮箱验证码登录 | ❌ |
| `/send-code` | POST | 发送验证码 | ❌ |
| `/verify-code` | POST | 验证邮箱 | ❌ |
| `/refresh` | POST | 刷新令牌 | ❌ |
| `/me` | GET | 获取用户信息 | ✅ |
| `/settings` | PUT | 更新设置 | ✅ |

<details>
<summary><strong>查看详细请求/响应示例</strong></summary>

#### 1.1 用户注册

**端点**: `POST /api/v1/auth/register`

**请求体**:
```json
{
  "username": "johndoe",
  "email": "john@example.com",
  "password": "SecurePass123!"
}
```

**响应** (201):
```json
{
  "access_token": "eyJ0eXAi...",
  "refresh_token": "eyJ0eXAi...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

#### 1.2 用户登录

**端点**: `POST /api/v1/auth/login`

**请求体** (form-data):
```
username: johndoe
password: SecurePass123!
```

**响应** (200):
```json
{
  "access_token": "eyJ0eXAi...",
  "refresh_token": "eyJ0eXAi...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

#### 1.3 邮箱验证码登录

**端点**: `POST /api/v1/auth/login/email`

**请求体**:
```json
{
  "email": "user@example.com",
  "code": "123456"
}
```

**响应** (200):
```json
{
  "access_token": "eyJ0eXAi...",
  "refresh_token": "eyJ0eXAi...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

#### 1.4 发送验证码

**端点**: `POST /api/v1/auth/send-code`

**请求体**:
```json
{
  "email": "user@example.com",
  "code_type": "login"
}
```

**响应** (200):
```json
{
  "code": "SUCCESS",
  "message": "验证码已发送",
  "data": {
    "expires_in": 300
  }
}
```

#### 1.5 刷新令牌

**端点**: `POST /api/v1/auth/refresh`

**请求体**:
```json
{
  "refresh_token": "eyJ0eXAi..."
}
```

**响应** (200):
```json
{
  "access_token": "eyJ0eXAi...",
  "refresh_token": "eyJ0eXAi...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

#### 1.6 获取用户信息

**端点**: `GET /api/v1/auth/me`

**请求头**:
```
Authorization: Bearer {access_token}
```

**响应** (200):
```json
{
  "id": "user-uuid",
  "username": "johndoe",
  "email": "john@example.com",
  "settings": {
    "daily_goal": 10,
    "theme": "dark",
    "language": "zh-CN"
  },
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

</details>

---

### 2. 任务管理 (`/api/v1/tasks`)

| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `` | GET | 列出任务 | ✅ |
| `` | POST | 创建任务 | ✅ |
| `/today` | GET | 今日任务 | ✅ |
| `/stats` | GET | 统计数据 | ✅ |
| `/batch` | POST | 批量创建 | ✅ |
| `/batch` | PUT | 批量更新 | ✅ |
| `/batch` | DELETE | 批量删除 | ✅ |
| `/{task_id}` | GET | 获取详情 | ✅ |
| `/{task_id}` | PUT | 更新任务 | ✅ |
| `/{task_id}/status` | PATCH | 更新状态 | ✅ |
| `/{task_id}` | DELETE | 删除任务 | ✅ |

<details>
<summary><strong>查看详细请求/响应示例</strong></summary>

#### 创建任务

**端点**: `POST /api/v1/tasks`

**请求体**:
```json
{
  "title": "完成 API 文档",
  "description": "编写完整的 API 参考文档",
  "status": "todo",
  "type": "feature",
  "priority": 8,
  "due_date": "2024-12-31"
}
```

**响应** (201):
```json
{
  "id": 1,
  "title": "完成 API 文档",
  "status": "todo",
  "priority": 8,
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### 今日任务

**端点**: `GET /api/v1/tasks/today`

**响应** (200):
```json
{
  "date": "2024-01-01",
  "tasks": [
    {
      "id": 1,
      "title": "完成 API 文档",
      "status": "todo",
      "priority": 8
    }
  ],
  "stats": {
    "total": 10,
    "todo": 5,
    "in_progress": 3,
    "done": 2,
    "completion_rate": 0.2
  }
}
```

</details>

---

### 3. 知识管理 (`/api/v1/knowledge`)

| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/cards` | POST | 创建卡片 | ✅ |
| `/cards` | GET | 列出卡片 | ✅ |
| `/cards/{card_id}` | GET | 获取详情 | ✅ |
| `/cards/{card_id}` | DELETE | 删除卡片 | ✅ |

---

### 4. 搜索引擎 (`/api/v1/search`)

| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `` | GET | 搜索查询 | ✅ |
| `/query` | POST | 复杂搜索 | ✅ |
| `/index` | POST | 创建索引 | ✅ |
| `/index/bulk` | POST | 批量索引 | ✅ |
| `/index/{type}/{id}` | DELETE | 删除索引 | ✅ |
| `/ingestion/jobs` | POST | 创建抓取 | ✅ |
| `/ingestion/jobs` | GET | 列出任务 | ✅ |
| `/insights/generate` | POST | 生成洞察 | ✅ |
| `/insights` | GET | 列出洞察 | ✅ |

---

### 5. 收件箱 (`/api/v1/inbox`)

| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/items` | POST | 创建项目 | ✅ |
| `/items` | GET | 列出项目 | ✅ |
| `/items/{item_id}` | GET | 获取详情 | ✅ |
| `/items/{item_id}` | PUT | 更新项目 | ✅ |
| `/items/{item_id}/status` | PATCH | 更新状态 | ✅ |
| `/items/{item_id}` | DELETE | 删除项目 | ✅ |

---

### 6. Agent 系统 (`/api/v1/agent`)

| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/tick` | POST | 处理周期 (LLM 批量处理) | ✅ |
| `/process/{item_id}` | POST | 处理项目 (LLM 单个处理) | ✅ |
| `/status` | GET | Agent 状态 | ✅ |
| `/flow/start` | POST | 启动工作流 | ✅ |
| `/flow/{id}/status` | GET | 工作流状态 | ✅ |
| `/skills` | POST | 创建技能 | ✅ |
| `/skills` | GET | 列出技能 | ✅ |
| `/skills/{skill_id}` | GET | 技能详情 | ✅ |

---

### 6.5 Garden 系统 (`/api/v1/garden`) - 内部服务 ✨

> **版本**: v7.1 新增功能
> **说明**: 以下是内部服务层 API，供其他服务调用

#### Garden Stats Service - 统计聚合服务

```python
from agent_os.garden import GardenStatsService

# 使用示例
service = GardenStatsService(db_session)
stats = await service.get_user_garden_stats(user_id, workspace_id)
```

**返回数据结构**:
```json
{
  "user_id": "uuid",
  "workspace_id": "uuid",
  "total_notes": 10,          // 活跃笔记/卡片总数
  "neural_connections": 5,    // 强边去重数 (A-B = B-A)
  "generated_insights": 3     // stable 且 level>=2 的 Insight 数
}
```

**计算口径**:
- `total_notes`: workspace 下 `status='active'` 的 Item 总数
- `neural_connections`: `relation_strength >= 0.65` 且去重的边数
- `generated_insights`: `status='stable'` 且 `level>=2`，按 `canonical_hash` 去重

#### Cluster Service - Cluster 强度计算

```python
from agent_os.garden import ClusterService

# 使用示例
service = ClusterService(db_session)
strength = await service.compute_cluster_strength(
    node_ids=["uuid1", "uuid2", "uuid3"],
    workspace_id="workspace-uuid"
)
```

**计算公式**:
```
cluster_strength = strong_edges_count + (avg_relation_strength * 2.0) + (1.0 / (avg_days_between_nodes + 1))
```

#### Insight Worker - Insight 聚合 Worker

```python
from agent_os.garden import InsightWorker

# 使用示例
worker = InsightWorker(db_session)

# 处理候选 Insight，检查是否满足 stable 条件
result = await worker.process_candidate_insight(
    insight_id="uuid",
    source_item_ids=["id1", "id2", "id3"],
    workspace_id="workspace-uuid"
)

# 去重方式创建/更新 Insight
result = await worker.upsert_insight_with_deduplication(
    workspace_id="workspace-uuid",
    user_id="user-uuid",
    canonical_hash="sha256-hash",
    title="Insight Title",
    content="Insight Content",
    source_item_ids=["id1", "id2"],
    level=2
)
```

**触发条件** (candidate -> stable):
- `sources >= 3`
- `timespan >= 3 天`
- `cluster_strength >= 2.5`

**去重逻辑**:
- 相同 `canonical_hash` 不新建记录
- 累加 `evidence_count += 1`
- 合并 `source_item_ids`

---

### 6.6 Garden 系统 HTTP API (PRD9 模块三) ✨

> **版本**: v7.2 新增功能
> **说明**: 以下是面向前端的花园图谱 HTTP API

#### 6.6.1 获取 Garden 节点列表

**端点**: `GET /api/v1/garden/nodes`

**认证**: ✅ 需要

**查询参数**:
| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `workspace_id` | uuid | 必填 | 工作区 ID |
| `date_range` | string | - | 日期范围：`last_7_days`, `last_90_days`, `all` |
| `types` | array | - | 类型过滤：`note`, `card`, `task` 等 |
| `limit` | integer | 300 | 每页数量 |
| `offset` | integer | 0 | 偏移量 |

**响应示例** (200):
```json
{
  "data": [
    {
      "id": "uuid",
      "object_type": "note",
      "title": "节点标题",
      "created_at": "2026-02-01T00:00:00Z",
      "strong_connection_count": 5,
      "snippet": "内容摘要..."
    }
  ],
  "total": 100,
  "limit": 300,
  "offset": 0
}
```

**前端使用示例**:
```javascript
// 获取节点列表
const nodes = await apiRequest('/v1/garden/nodes?workspace_id=xxx&limit=50');

// 带过滤条件
const recentNotes = await apiRequest(
  '/v1/garden/nodes?workspace_id=xxx&date_range=last_7_days&types[]=note'
);
```

#### 6.6.2 批量查询 Garden 边

**端点**: `POST /api/v1/garden/edges/batch`

**认证**: ✅ 需要

**查询参数**:
| 参数 | 类型 | 描述 |
|------|------|------|
| `workspace_id` | uuid | 工作区 ID |

**请求体**:
```json
{
  "node_ids": ["uuid1", "uuid2", "uuid3"]
}
```

**响应示例** (200):
```json
{
  "data": [
    {
      "id": "edge-uuid",
      "from_id": "uuid1",
      "to_id": "uuid2",
      "type": "related",
      "relation_strength": 0.85,
      "created_at": "2026-02-01T00:00:00Z"
    }
  ],
  "connections_count": 1,
  "metadata": {
    "threshold": 0.65,
    "requested_nodes": 3
  }
}
```

**说明**:
- 仅返回 `relation_strength >= 0.65` 的强边
- 边的起点和终点必须都在 `node_ids` 列表中

**前端使用示例**:
```javascript
// 获取节点间的强连接
const edges = await apiRequest('/v1/garden/edges/batch?workspace_id=xxx', {
  method: 'POST',
  body: JSON.stringify({ node_ids: ['uuid1', 'uuid2', 'uuid3'] })
});
```

#### 6.6.3 获取 Garden 节点详情

**端点**: `GET /api/v1/garden/nodes/{id}`

**认证**: ✅ 需要

**查询参数**:
| 参数 | 类型 | 描述 |
|------|------|------|
| `workspace_id` | uuid | 工作区 ID |

**响应示例** (200):
```json
{
  "id": "node-uuid",
  "object_type": "note",
  "title": "节点标题",
  "type": "note",
  "time": "2026-02-01T00:00:00Z",
  "summary": "内容摘要...",
  "jump_url": "/items/node-uuid",
  "connected_nodes": [
    {
      "id": "connected-uuid",
      "title": "连接节点",
      "object_type": "card",
      "relation_strength": 0.9,
      "jump_url": "/items/connected-uuid"
    }
  ]
}
```

**说明**:
- `connected_nodes` 最多返回 5 个相关节点
- 按 `relation_strength` 降序排列

**前端使用示例**:
```javascript
// 获取节点详情及连接
const nodeDetail = await apiRequest(
  `/v1/garden/nodes/${nodeId}?workspace_id=xxx`
);
```

---

### 6.7 今日 Insight API (PRD9 模块三) ✨

> **版本**: v7.2 新增功能

#### 获取今日 Insight

**端点**: `GET /api/v1/today/insight`

**认证**: ✅ 需要

**查询参数**:
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `day` | string | ✅ | 日期格式：`YYYY-MM-DD` |
| `workspace_id` | uuid | ✅ | 工作区 ID |
| `theme` | string | - | 可选的主题过滤 |

**响应示例** (200):
```json
{
  "data": [
    {
      "id": "insight-uuid",
      "claim": "洞察的核心主张",
      "rationale": "推理和解释内容...",
      "implications": ["影响 1", "影响 2"],
      "sources": [
        {
          "id": "source-uuid",
          "title": "来源标题",
          "item_type": "note"
        }
      ],
      "level": 2,
      "status": "stable",
      "evidence_count": 3,
      "created_at": "2026-02-01T00:00:00Z",
      "updated_at": "2026-02-01T00:00:00Z"
    }
  ],
  "day": "2026-02-01",
  "total": 1
}
```

**说明**:
- 仅返回 `status='stable'` 且 `level>=2` 的高质量洞察
- 必需字段：`claim`, `rationale`, `implications`, `sources`

**前端使用示例**:
```javascript
// 获取今日洞察
const todayInsights = await apiRequest(
  `/v1/today/insight?day=${today}&workspace_id=xxx`
);

// 渲染示例
todayInsights.data.forEach(insight => {
  console.log('主张:', insight.claim);
  console.log('理由:', insight.rationale);
  console.log('影响:', insight.implications);
  console.log('来源:', insight.sources);
});
```

---

### 6.8 获取用户信息 (PRD9 模块三更新) ✨

> **版本**: v7.2 更新 - 增加 stats 字段

#### 获取当前用户信息（带 Garden 统计）

**端点**: `GET /api/v1/auth/me`

**认证**: ✅ 需要

**查询参数**:
| 参数 | 类型 | 描述 |
|------|------|------|
| `workspace_id` | uuid | 可选，提供时返回 Garden 统计 |

**响应示例** (200):
```json
{
  "id": "user-uuid",
  "username": "johndoe",
  "email": "john@example.com",
  "settings": {
    "daily_goal": 10,
    "theme": "dark",
    "language": "zh-CN"
  },
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "stats": {
    "total_notes": 15,
    "neural_connections": 8,
    "generated_insights": 3
  }
}
```

**stats 字段说明**:
- `total_notes`: 工作区下活跃笔记/卡片总数
- `neural_connections`: 强边去重数量 (`relation_strength >= 0.65`)
- `generated_insights`: 稳定且 level>=2 的洞察数量

**前端使用示例**:
```javascript
// 获取用户信息（含 Garden 统计）
const userInfo = await apiRequest('/v1/auth/me?workspace_id=xxx');
console.log('笔记数:', userInfo.stats.total_notes);
console.log('连接数:', userInfo.stats.neural_connections);
console.log('洞察数:', userInfo.stats.generated_insights);
```

---

### 7. 对话历史 (`/api/v1/conversations`)

| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/{session_id}/history` | GET | 获取历史 | ✅ |
| `/{session_id}/tokens` | GET | Token 数 | ✅ |
| `/{conversation_id}` | DELETE | 删除消息 | ✅ |
| `/sessions/recent` | GET | 最近会话 | ✅ |

---

### 8. 工作区与项目 (`/prd4`)

#### 工作区
| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/workspaces` | POST | 创建工作区 | ✅ |
| `/workspaces` | GET | 列出工作区 | ✅ |
| `/workspaces/{id}` | GET | 获取详情 | ✅ |

#### 区域 (Area)
| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/areas` | POST | 创建区域 | ✅ |
| `/areas` | GET | 列出区域 | ✅ |
| `/areas/{id}` | GET | 获取详情 | ✅ |
| `/areas/{workspace_id}/tree` | GET | 区域树 | ✅ |

#### 项目 (Project)
| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/projects` | POST | 创建项目 | ✅ |
| `/projects` | GET | 列出项目 | ✅ |
| `/projects/{id}` | GET | 获取详情 | ✅ |

#### 条目 (Item)
| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/items` | POST | 创建条目 | ✅ |
| `/items` | GET | 列出条目 | ✅ |
| `/items/{id}` | GET | 获取详情 | ✅ |
| `/items/{id}` | PUT | 更新条目 | ✅ |
| `/items/{id}` | DELETE | 删除条目 | ✅ |

---

### 8. 工作区与项目 (`/prd4`)

| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/{node_id}` | GET | 获取连接 | ✅ |
| `/{node_id}/strong` | GET | 强连接 | ✅ |
| `/{node_id}/stats` | GET | 统计 | ✅ |
| `/{node_id}/graph` | GET | 连接图 | ✅ |
| `/recalculate` | POST | 重新计算 | ✅ |

---

### 9. 连接管理 (`/connections`)

| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/wechat/webhook` | GET/POST | 微信消息 | ❌ |
| `/wechat/send/text` | POST | 发送文本 | ✅ |
| `/wechat/send/news` | POST | 发送图文 | ✅ |
| `/crawler/crawl` | POST | 爬取 URL | ✅ |
| `/crawler/extract-links` | POST | 提取链接 | ✅ |

---

### 10. 集成服务 (`/integrations`)

| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/metrics` | GET | 性能指标 | ✅ |
| `/health` | GET | 健康状态 | ✅ |
| `/health/simple` | GET | 简单检查 | ✅ |
| `/info` | GET | 系统信息 | ✅ |

---

### 11. 可观测性 (`/observability`)

### 认证方式

使用 JWT Bearer Token 进行认证：

```
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

### 令牌有效期

| 令牌类型 | 有效期 | 用途 |
|---------|--------|------|
| Access Token | 30 分钟 | API 请求认证 |
| Refresh Token | 7 天 | 刷新 Access Token |

### 刷新令牌

```javascript
async function refreshAccessToken(refreshToken) {
  const response = await fetch(`${API_BASE_URL}/v1/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken })
  });

  const data = await response.json();
  localStorage.setItem('access_token', data.access_token);
  return data.access_token;
}
```

---

## 分页与过滤

### 分页参数

```
GET /api/v1/items?page=1&limit=20
```

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `page` | number | 1 | 页码 |
| `limit` | number | 20 | 每页数量 (max: 100) |

### 分页响应

```json
{
  "data": [...],
  "total": 100,
  "page": 1,
  "limit": 20,
  "total_pages": 5
}
```

### 过滤参数

| 参数 | 类型 | 描述 |
|------|------|------|
| `status` | string | 状态过滤 |
| `priority` | string | 优先级过滤 |
| `type` | string | 类型过滤 |
| `date_from` | string | 起始日期 |
| `date_to` | string | 结束日期 |

---

## 错误处理

### 错误响应格式

```json
{
  "detail": "错误描述信息"
}
```

### HTTP 状态码

| 状态码 | 含义 | 示例 |
|--------|------|------|
| 200 | 成功 | 请求成功 |
| 201 | 已创建 | 资源创建成功 |
| 204 | 无内容 | 删除成功 |
| 400 | 请求错误 | 参数无效 |
| 401 | 未认证 | Token 过期 |
| 403 | 无权限 | 资源访问被拒 |
| 404 | 未找到 | 资源不存在 |
| 500 | 服务器错误 | 内部错误 |

### 前端错误处理

```javascript
async function apiRequest(endpoint, options = {}) {
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${accessToken}`,
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json();

      // 处理 401 错误（Token 过期）
      if (response.status === 401) {
        await handleTokenRefresh();
        return apiRequest(endpoint, options);
      }

      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
}
```

---

## 数据模型

### Task

```typescript
interface Task {
  id: string;
  title: string;
  description?: string;
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled';
  priority: 'low' | 'medium' | 'high';
  due_date?: string;
  completed_at?: string;
  created_at: string;
  updated_at: string;
}
```

### Card

```typescript
interface Card {
  id: string;
  title: string;
  content: string;
  type: 'note' | 'reference' | 'idea';
  tags?: string[];
  summary?: string;
  created_at: string;
  updated_at: string;
}
```

### InboxItem

```typescript
interface InboxItem {
  id: string;
  content: string;
  status: 'raw' | 'processed';
  title?: string;
  summary?: string;
  item_type?: 'note' | 'task' | 'reference';
  metadata?: {
    tags?: string[];
    llm_summary?: boolean;
    llm_tags?: string[];
  };
  created_at: string;
  updated_at: string;
}
```

### Garden (PRD8)

```typescript
// 用户花园统计
interface GardenStats {
  user_id: string;
  workspace_id: string;
  total_notes: number;           // 活跃笔记数
  neural_connections: number;    // 强边去重数
  generated_insights: number;    // stable 且 level>=2 的 Insight 数
}

// 知识卡片连接 (无向图)
interface KnowledgeCardLink {
  id: string;
  workspace_id: string;
  from_id: string;  // 源节点 ID
  to_id: string;    // 目标节点 ID
  type: 'related' | 'support' | 'contradict' | 'reference';
  relation_strength: number;  // 0.0 - 1.0
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// 每日洞察
interface DailyInsight {
  id: string;
  workspace_id: string;
  user_id: string;
  title: string;
  content: string;
  status: 'draft' | 'candidate' | 'stable' | 'rejected';
  level: 1 | 2 | 3;
  canonical_hash: string;      // 用于去重
  stability_score: number;     // 0.0 - 1.0
  evidence_count: number;      // 证据计数
  source_item_ids: string[];   // 源项目 ID 列表
  created_at: string;
  updated_at: string;
}
```

---

## 更新日志

### v7.2 (2026-03-01) - PRD9 模块三 API 接口层

- ✨ 新增 PRD9 模块三 - Garden 系统 HTTP API
  - `GET /api/v1/garden/nodes`: 节点列表（支持分页、日期范围、类型过滤）
  - `POST /api/v1/garden/edges/batch`: 批量查询强边
  - `GET /api/v1/garden/nodes/{id}`: 节点详情（含 sorted connected_nodes）
  - `GET /api/v1/today/insight`: 今日洞察（claim, rationale, implications, sources）
  - `GET /api/v1/auth/me`: 增加 `stats` 字段（total_notes, neural_connections, generated_insights）
- 📝 新增 14 个 API 集成测试，覆盖率 100%
- 🐛 修复 `today/router.py` 导入问题
- 🐛 修复 `garden/router.py` type 字段访问问题

### v7.1 (2026-02-27)

- ✨ 新增 Garden 系统 (PRD8 模块二)
  - GardenStatsService: 用户花园统计 (total_notes, neural_connections, generated_insights)
  - ClusterService: Cluster 强度计算服务
  - InsightWorker: Insight 聚合与状态跃迁 Worker
- ✨ 配置管理新增 `GARDEN_STRONG_EDGE_THRESHOLD` (默认 0.65)
- 📝 新增 23 个单元测试，覆盖率 100%

### v7.0 (2026-02-27)

- ✨ 新增 LLM 智能摘要和标签生成
- ✨ 新增 DeepSeek 大模型集成
- 🐛 修复邮箱验证码登录问题
- 📝 完善 API 文档

### v6.0 (2026-02-16)

- ✨ 新增邮箱验证码登录
- 📝 完善 154+ API 端点文档

---

## 技术支持

- **GitHub Issues**: 报告问题
- **文档问题**: 在仓库中提 issue
- **API 变更**: 查看更新日志

---

## 附录

### 相关文档

- [数据库架构](../10-architecture/DATABASE_ARCHITECTURE.md)
- [向量嵌入指南](../10-architecture/EMBEDDING_VECTOR_GUIDE.md)

### OpenAPI 规范

完整的 OpenAPI 3.0 规范文件：[openapi.json](./openapi.json)

可使用 Swagger UI 或 Stoplight Studio 查看。
