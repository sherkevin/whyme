# AgentOS API 完整参考文档

**版本**: v6.0
**最后更新**: 2026-02-16
**基础路径**: `/api/v1`
**总计**: 154+ API 端点（新增2个邮箱验证码端点）

---

## 📋 目录

1. [认证系统 (Auth)](#1-认证系统-auth)
2. [知识管理 (Knowledge)](#2-知识管理-knowledge)
3. [任务管理 (Tasks)](#3-任务管理-tasks)
4. [搜索引擎 (Search)](#4-搜索引擎-search)
5. [收件箱 (Inbox)](#5-收件箱-inbox)
6. [今日概览 (Today)](#6-今日概览-today)
7. [聚合数据 (Aggregation)](#7-聚合数据-aggregation)
8. [对话历史 (Conversations)](#8-对话历史-conversations)
9. [工作流与技能 (Stage3 Agent)](#9-工作流与技能-stage3-agent)
10. [Agent 核心 (Agent Core)](#10-agent-核心-agent-core)
11. [集成服务 (Integrations)](#11-集成服务-integrations)
12. [连接管理 (Connections)](#12-连接管理-connections)
13. [工作区与条目 (Items)](#13-工作区与条目-items)
14. [可观测性 (Observability)](#14-可观测性-observability)
15. [认证与授权](#认证与授权)
16. [分页与过滤](#分页与过滤)
17. [错误处理](#错误处理)
18. [版本历史](#版本历史)

---

## 1. 认证系统 (Auth)

**基础路径**: `/api/v1/auth`

### 1.1 用户注册

创建新用户账户并返回认证令牌

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

**错误响应** (400):
```json
{
  "detail": "Username already registered"
}
```

### 1.2 用户登录

使用用户名/邮箱和密码登录

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

**错误响应** (401):
```json
{
  "detail": "Incorrect username or password"
}
```

### 1.3 刷新令牌

使用刷新令牌获取新的访问令牌

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

### 1.4 获取用户信息

获取当前认证用户的信息

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

### 1.5 更新用户设置

更新用户偏好设置

**端点**: `PUT /api/v1/auth/settings`

**请求头**:
```
Authorization: Bearer {access_token}
```

**请求体**:
```json
{
  "settings": {
    "daily_goal": 15,
    "theme": "light",
    "language": "en-US"
  }
}
```

**响应** (200):
```json
{
  "id": "user-uuid",
  "username": "johndoe",
  "email": "john@example.com",
  "settings": {
    "daily_goal": 15,
    "theme": "light",
    "language": "en-US"
  },
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 1.6 发送验证码 (B-03B)

向用户邮箱发送 6 位数字验证码

**端点**: `POST /api/v1/auth/send-code`

**请求体**:
```json
{
  "email": "user@example.com",
  "code_type": "login"
}
```

**参数说明**:
- `email`: 接收验证码的邮箱地址
- `code_type`: 验证码类型
  - `login`: 登录验证
  - `bind`: 绑定邮箱
  - `reset`: 重置密码
  - 默认: `login`

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

**频控响应** (200):
```json
{
  "code": "RATE_LIMITED",
  "message": "发送过于频繁，请 60 秒后重试",
  "retry_after": 60
}
```

**错误响应** (400):
```json
{
  "detail": "邮箱格式不正确"
}
```

**特性**:
- 生成 6 位随机数字验证码
- 验证码有效期 5 分钟（300 秒）
- 频率限制：同邮箱 60 秒内只能发送 1 次
- IP 频率限制：同 IP 60 秒内只能发送 1 次
- 防止邮箱枚举：即使邮箱不存在也返回成功

---

### 1.7 邮箱验证码注册 ⭐ NEW

**端点**: `POST /api/v1/auth/register/email`

使用邮箱和验证码注册新账号（无需用户名）

**功能说明**:
- 用户只需提供邮箱和验证码即可注册
- 系统自动从邮箱地址生成用户名
- 支持所有邮箱类型（QQ、Gmail、163等）
- 验证码通过邮件发送，5分钟有效

**请求体**:
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "code": "123456"
}
```

**参数说明**:
- `email` (string): 用户邮箱地址（必填）
- `password` (string): 设置密码，至少6位（必填）
- `code` (string): 邮箱收到的6位验证码（必填）

**响应** (201 Created):
```json
{
  "access_token": "eyJ0eXAiOiJ...",
  "refresh_token": "eyJ0eXAiOiJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**成功返回数据**:
- `access_token`: 访问令牌，用于后续API调用
- `refresh_token`: 刷新令牌，用于获取新的访问令牌
- `token_type`: 令牌类型，固定为 "bearer"
- `expires_in`: 访问令牌有效期（秒），默认30分钟

**错误响应**:

邮箱已存在 (409 Conflict):
```json
{
  "detail": "Email already registered"
}
```

验证码无效 (422 Unprocessable Entity):
```json
{
  "detail": "Invalid or expired verification code"
}
```

验证码过期 (422 Unprocessable Entity):
```json
{
  "detail": "Verification code has expired. Please request a new one."
}
```

**使用示例**:
```bash
# 1. 发送验证码
curl -X POST http://localhost:8003/api/v1/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"email":"newuser@example.com","code_type":"login"}'

# 2. 使用验证码注册
curl -X POST http://localhost:8003/api/v1/auth/register/email \
  -H "Content-Type: application/json" \
  -d '{"email":"newuser@example.com","password":"mypassword","code":"123456"}'
```

**用户名生成规则**:
- 从邮箱地址提取：`user@example.com` → `user`
- 清理特殊字符：`user.name@example.com` → `user_name`
- 如有冲突，自动添加序号：`user_1`, `user_2`

**安全特性**:
- ✅ 验证码一次性使用（验证后自动失效）
- ✅ 频率限制：60秒内只能发送1次
- ✅ 有效期限制：5分钟后自动过期
- ✅ 失败保护：5次失败后锁定30分钟

---

### 1.8 邮箱验证码登录 ⭐ NEW

**端点**: `POST /api/v1/auth/login/email`

使用邮箱和验证码登录（无需密码）

**功能说明**:
- 无需记忆密码，更安全便捷
- 输入邮箱和验证码即可登录
- 验证码通过邮件发送，2秒内到达
- 支持所有邮箱类型

**请求体**:
```json
{
  "email": "user@example.com",
  "code": "123456"
}
```

**参数说明**:
- `email` (string): 已注册的邮箱地址（必填）
- `code` (string): 邮箱收到的6位验证码（必填）

**响应** (200 OK):
```json
{
  "access_token": "eyJ0eXAiOiJ...",
  "refresh_token": "eyJ0eXAiOiJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**成功返回数据**:
- `access_token`: 访问令牌
- `refresh_token`: 刷新令牌
- `token_type`: "bearer"
- `expires_in`: 有效期（秒），默认30分钟

**错误响应**:

用户不存在 (401 Unauthorized):
```json
{
  "detail": "User not found. Please register first."
}
```

验证码无效 (401 Unauthorized):
```json
{
  "detail": "Invalid or expired verification code"
}
```

账户已锁定 (423 Locked):
```json
{
  "detail": "Account temporarily locked. Please try again later"
}
```

验证码过期 (422 Unprocessable Entity):
```json
{
  "detail": "Verification code has expired. Please request a new one."
}
```

**使用示例**:
```bash
# 1. 发送验证码
curl -X POST http://localhost:8003/api/v1/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"email":"existinguser@example.com","code_type":"login"}'

# 2. 使用验证码登录
curl -X POST http://localhost:8003/api/v1/auth/login/email \
  -H "Content-Type: application/json" \
  -d '{"email":"existinguser@example.com","code":"123456"}'
```

**安全特性**:
- ✅ 无密码登录（更安全）
- ✅ 验证码一次性使用
- ✅ 自动更新最后登录时间
- ✅ 失败次数限制
- ✅ 账户锁定保护

---

### 1.9 验证验证码 (B-03C)

验证用户提交的验证码

**端点**: `POST /api/v1/auth/verify-code`

**请求体**:
```json
{
  "email": "user@example.com",
  "code": "123456",
  "code_type": "login"
}
```

**参数说明**:
- `email`: 邮箱地址
- `code`: 6 位数字验证码
- `code_type`: 验证码类型（默认: `login`）

**响应** (200):
```json
{
  "code": "SUCCESS",
  "message": "验证通过",
  "data": {
    "token": "eyJ0eXAi...",
    "user_id": "user-uuid"
  }
}
```

**错误响应** - 验证码错误 (400):
```json
{
  "detail": "验证码错误，还剩 2 次机会"
}
```

**错误响应** - 验证码过期 (400):
```json
{
  "detail": "验证码已过期，请重新获取"
}
```

**错误响应** - 尝试次数过多 (423):
```json
{
  "detail": "验证失败次数过多，请 30 分钟后重试"
}
```

**特性**:
- 一次性使用：验证成功后立即删除验证码
- 失败计数：最多允许 5 次错误尝试
- 自动锁定：5 次失败后锁定 30 分钟
- 安全保护：不区分"验证码错误"和"验证码不存在"

**请求头**:
```
Authorization: Bearer {access_token}
```

**请求体**:
```json
{
  "settings": {
    "daily_goal": 15,
    "theme": "light",
    "language": "en-US"
  }
}
```

**响应** (200):
```json
{
  "id": "user-uuid",
  "username": "johndoe",
  "email": "john@example.com",
  "settings": {
    "daily_goal": 15,
    "theme": "light",
    "language": "en-US"
  },
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

## 2. 知识管理 (Knowledge)

**基础路径**: `/api/v1/knowledge`

### 2.1 创建卡片

创建知识卡片

**端点**: `POST /api/v1/knowledge/cards`

**请求头**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**请求体**:
```json
{
  "title": "RESTful API 设计原则",
  "content": "RESTful API 应遵循无状态、统一接口等设计原则",
  "para_type": "concept",
  "tags": ["API", "REST", "架构"],
  "source_inbox_item_id": null
}
```

**响应** (201):
```json
{
  "id": "card-uuid",
  "workspace_id": "workspace-uuid",
  "user_id": "user-uuid",
  "title": "RESTful API 设计原则",
  "content": "RESTful API 应遵循无状态、统一接口等设计原则",
  "para_type": "concept",
  "tags": ["API", "REST", "架构"],
  "source_inbox_item_id": null,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### 2.2 获取卡片详情

获取单个知识卡片

**端点**: `GET /api/v1/knowledge/cards/{card_id}`

**请求头**:
```
Authorization: Bearer {access_token}
```

**路径参数**:
- `card_id`: 卡片 UUID

**响应** (200):
```json
{
  "id": "card-uuid",
  "workspace_id": "workspace-uuid",
  "user_id": "user-uuid",
  "title": "RESTful API 设计原则",
  "content": "RESTful API 应遵循无状态、统一接口等设计原则",
  "para_type": "concept",
  "tags": ["API", "REST", "架构"],
  "source_inbox_item_id": null,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### 2.3 列出卡片

列出知识卡片，支持过滤和分页

**端点**: `GET /api/v1/knowledge/cards`

**请求头**:
```
Authorization: Bearer {access_token}
```

**查询参数**:
- `para_type`: 段落类型过滤 (concept, action, reference)
- `tags`: 标签过滤 (逗号分隔，如: "API,REST")
- `page`: 页码 (默认: 1)
- `page_size`: 每页数量 (默认: 20, 最大: 100)

**响应** (200):
```json
{
  "items": [
    {
      "id": "card-uuid",
      "title": "RESTful API 设计原则",
      "content": "RESTful API 应遵循无状态、统一接口等设计原则",
      "para_type": "concept",
      "tags": ["API", "REST", "架构"],
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```

### 2.4 删除卡片

删除知识卡片

**端点**: `DELETE /api/v1/knowledge/cards/{card_id}`

**请求头**:
```
Authorization: Bearer {access_token}
```

**路径参数**:
- `card_id`: 卡片 UUID

**响应** (204): 无内容

---

## 3. 任务管理 (Tasks)

**基础路径**: `/api/v1/tasks`

### 3.1 创建任务

创建新任务

**端点**: `POST /api/v1/tasks`

**请求头**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**请求体**:
```json
{
  "title": "完成 API 文档",
  "description": "编写完整的 API 参考文档",
  "status": "todo",
  "type": "feature",
  "priority": 8,
  "scheduled_date": "2024-12-31",
  "due_date": "2024-12-31",
  "estimated_time_minutes": 120,
  "area_id": "area-uuid",
  "project_id": "project-uuid"
}
```

**响应** (201):
```json
{
  "id": 1,
  "title": "完成 API 文档",
  "description": "编写完整的 API 参考文档",
  "status": "todo",
  "type": "feature",
  "priority": 8,
  "scheduled_date": "2024-12-31",
  "due_date": "2024-12-31",
  "estimated_time_minutes": 120,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### 3.2 获取任务详情

获取单个任务

**端点**: `GET /api/v1/tasks/{task_id}`

**请求头**:
```
Authorization: Bearer {access_token}
```

**路径参数**:
- `task_id`: 任务 ID (整数)

**响应** (200):
```json
{
  "id": 1,
  "title": "完成 API 文档",
  "status": "todo",
  "priority": 8,
  "due_date": "2024-12-31"
}
```

### 3.3 列出任务

列出任务，支持过滤、排序和分页

**端点**: `GET /api/v1/tasks`

**请求头**:
```
Authorization: Bearer {access_token}
```

**查询参数**:
- `status`: 状态过滤 (todo, in_progress, done, cancelled)
- `type`: 类型过滤
- `priority_min`: 最小优先级 (1-10)
- `priority_max`: 最大优先级 (1-10)
- `date_from`: 开始日期过滤
- `date_to`: 结束日期过滤
- `scheduled_date`: 精确日期过滤
- `page`: 页码 (默认: 1)
- `page_size`: 每页数量 (默认: 20, 最大: 100)
- `sort_by`: 排序字段 (默认: created_at)
- `sort_order`: 排序方向 (asc, desc, 默认: desc)

**响应** (200):
```json
{
  "items": [
    {
      "id": 1,
      "title": "完成 API 文档",
      "status": "todo",
      "priority": 8
    }
  ],
  "total": 25,
  "page": 1,
  "page_size": 20
}
```

### 3.4 更新任务

更新任务信息

**端点**: `PUT /api/v1/tasks/{task_id}`

**请求头**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**请求体**:
```json
{
  "title": "更新后的标题",
  "status": "in_progress",
  "priority": 9
}
```

**响应** (200):
```json
{
  "id": 1,
  "title": "更新后的标题",
  "status": "in_progress",
  "priority": 9,
  "updated_at": "2024-01-01T12:00:00Z"
}
```

### 3.5 更新任务状态

快速更新任务状态

**端点**: `PATCH /api/v1/tasks/{task_id}/status`

**请求头**:
```
Authorization: Bearer {access_token}
```

**请求体**:
```json
{
  "status": "done"
}
```

**响应** (200):
```json
{
  "id": 1,
  "status": "done",
  "completed_at": "2024-01-01T15:30:00Z"
}
```

### 3.6 删除任务

删除任务

**端点**: `DELETE /api/v1/tasks/{task_id}`

**请求头**:
```
Authorization: Bearer {access_token}
```

**响应** (204): 无内容

### 3.7 今日任务

获取今天的任务及统计

**端点**: `GET /api/v1/tasks/today`

**请求头**:
```
Authorization: Bearer {access_token}
```

**查询参数**:
- `include_knowledge`: 是否包含知识上下文 (默认: false)

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
  },
  "knowledge_context": null
}
```

### 3.8 任务统计

获取任务统计信息

**端点**: `GET /api/v1/tasks/stats`

**请求头**:
```
Authorization: Bearer {access_token}
```

**查询参数**:
- `date_from`: 开始日期
- `date_to`: 结束日期

**响应** (200):
```json
{
  "total": 100,
  "todo": 40,
  "in_progress": 30,
  "done": 25,
  "cancelled": 5,
  "completion_rate": 0.25,
  "avg_priority": 6.5
}
```

### 3.9 批量创建任务

批量创建多个任务

**端点**: `POST /api/v1/tasks/batch`

**请求头**:
```
Authorization: Bearer {access_token}
```

**请求体**:
```json
{
  "tasks": [
    {
      "title": "任务1",
      "priority": 5
    },
    {
      "title": "任务2",
      "priority": 7
    }
  ]
}
```

**响应** (201):
```json
{
  "items": [
    {"id": 1, "title": "任务1"},
    {"id": 2, "title": "任务2"}
  ],
  "total": 2,
  "page": 1,
  "page_size": 2
}
```

### 3.10 批量更新任务

批量更新任务

**端点**: `PUT /api/v1/tasks/batch`

**请求头**:
```
Authorization: Bearer {access_token}
```

**请求体**:
```json
{
  "task_ids": [1, 2, 3],
  "updates": {
    "status": "in_progress"
  }
}
```

**响应** (200):
```json
{
  "message": "Updated 3 tasks",
  "updated_count": 3
}
```

### 3.11 批量删除任务

批量删除任务

**端点**: `DELETE /api/v1/tasks/batch`

**请求头**:
```
Authorization: Bearer {access_token}
```

**查询参数**:
- `task_ids`: 任务 ID 列表 (逗号分隔)

**响应** (200):
```json
{
  "message": "Deleted 3 tasks",
  "deleted_count": 3
}
```

---

## 4. 搜索引擎 (Search)

**基础路径**: `/api/v1/search`

### 4.1 创建/更新索引

为项目创建或更新搜索索引

**端点**: `POST /api/v1/search/index`

**请求头**:
```
Authorization: Bearer {access_token}
```

**请求体**:
```json
{
  "item_type": "card",
  "item_id": "card-uuid",
  "title": "RESTful API 设计",
  "content": "详细内容...",
  "tags": ["API", "REST"],
  "search_metadata": {
    "author": "John"
  },
  "embedding": null
}
```

**响应** (201):
```json
{
  "id": "index-uuid",
  "item_type": "card",
  "item_id": "card-uuid",
  "title": "RESTful API 设计",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### 4.2 批量创建索引

批量创建搜索索引

**端点**: `POST /api/v1/search/index/bulk`

**请求头**:
```
Authorization: Bearer {access_token}
```

**请求体**:
```json
{
  "items": [
    {
      "item_type": "card",
      "item_id": "card-uuid-1",
      "title": "标题1",
      "content": "内容1"
    },
    {
      "item_type": "task",
      "item_id": "task-uuid-2",
      "title": "标题2",
      "content": "内容2"
    }
  ]
}
```

**响应** (201):
```json
{
  "indexed": 2,
  "failed": 0,
  "errors": []
}
```

### 4.3 更新索引

更新搜索索引

**端点**: `PUT /api/v1/search/index/{item_type}/{item_id}`

**请求头**:
```
Authorization: Bearer {access_token}
```

**路径参数**:
- `item_type`: 项目类型
- `item_id`: 项目 UUID

**请求体**:
```json
{
  "title": "更新后的标题",
  "content": "更新后的内容"
}
```

**响应** (200):
```json
{
  "id": "index-uuid",
  "title": "更新后的标题",
  "updated_at": "2024-01-01T12:00:00Z"
}
```

### 4.4 删除索引

删除搜索索引

**端点**: `DELETE /api/v1/search/index/{item_type}/{item_id}`

**请求头**:
```
Authorization: Bearer {access_token}
```

**响应** (204): 无内容

### 4.5 重建索引

重建整个搜索索引

**端点**: `POST /api/v1/search/index/rebuild`

**请求头**:
```
Authorization: Bearer {access_token}
```

**响应** (200):
```json
{
  "status": "completed",
  "message": "Rebuilt search index with 150 items",
  "total_indexed": 150,
  "duration_seconds": 2.5
}
```

### 4.6 搜索查询 (GET)

执行搜索查询

**端点**: `GET /api/v1/search`

**请求头**:
```
Authorization: Bearer {access_token}
```

**查询参数**:
- `query`: 搜索关键词 (必填)
- `item_types`: 项目类型过滤 (可多个)
- `tags`: 标签过滤 (可多个)
- `date_from`: 开始日期
- `date_to`: 结束日期
- `page`: 页码 (默认: 1)
- `page_size`: 每页数量 (默认: 20)
- `sort_by`: 排序方式 (relevance, date, -date)

**响应** (200):
```json
{
  "total": 50,
  "page": 1,
  "page_size": 20,
  "results": [
    {
      "item_type": "card",
      "item_id": "card-uuid",
      "title": "RESTful API 设计",
      "content_snippet": "RESTful API 应遵循...",
      "score": 0.95,
      "tags": ["API", "REST"],
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 4.7 搜索查询 (POST)

执行复杂搜索查询

**端点**: `POST /api/v1/search/query`

**请求头**:
```
Authorization: Bearer {access_token}
```

**请求体**:
```json
{
  "query": "搜索关键词",
  "item_types": ["card", "task"],
  "tags": ["重要"],
  "date_from": "2024-01-01T00:00:00Z",
  "date_to": "2024-12-31T23:59:59Z",
  "page": 1,
  "page_size": 20,
  "sort_by": "relevance",
  "include_vectors": false
}
```

**响应** (200): 同 4.6

### 4.8 创建内容抓取任务

创建内容抓取任务

**端点**: `POST /api/v1/search/ingestion/jobs`

**请求头**:
```
Authorization: Bearer {access_token}
```

**请求体**:
```json
{
  "source_type": "url",
  "source_url": "https://example.com/article",
  "source_file_path": null,
  "chunk_size": 1000,
  "overlap": 200
}
```

**响应** (201):
```json
{
  "id": "job-uuid",
  "source_type": "url",
  "source_url": "https://example.com/article",
  "status": "pending",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 4.9 列出抓取任务

列出内容抓取任务

**端点**: `GET /api/v1/search/ingestion/jobs`

**请求头**:
```
Authorization: Bearer {access_token}
```

**查询参数**:
- `status`: 状态过滤
- `limit`: 返回数量 (默认: 50)
- `offset`: 偏移量 (默认: 0)

**响应** (200):
```json
{
  "total": 10,
  "jobs": [
    {
      "id": "job-uuid",
      "source_type": "url",
      "source_url": "https://example.com",
      "status": "completed"
    }
  ]
}
```

### 4.10 获取抓取任务详情

获取单个抓取任务

**端点**: `GET /api/v1/search/ingestion/jobs/{job_id}`

**请求头**:
```
Authorization: Bearer {access_token}
```

**响应** (200):
```json
{
  "id": "job-uuid",
  "source_type": "url",
  "source_url": "https://example.com",
  "status": "completed",
  "title": "文章标题",
  "content": "抓取的内容...",
  "error": null
}
```

### 4.11 启动抓取任务

启动抓取任务处理

**端点**: `POST /api/v1/search/ingestion/jobs/{job_id}/start`

**请求头**:
```
Authorization: Bearer {access_token}
```

**响应** (200):
```json
{
  "id": "job-uuid",
  "status": "processing",
  "started_at": "2024-01-01T00:00:00Z"
}
```

### 4.12 生成洞察

生成洞察分析

**端点**: `POST /api/v1/search/insights/generate`

**请求头**:
```
Authorization: Bearer {access_token}
```

**查询参数**:
- `cluster_type`: 洞察类型 (summary, trend, topic, pattern)
- `item_type`: 源项目类型
- `item_ids`: 可选的项目 ID 列表
- `num_topics`: 主题数量 (默认: 5)
- `group_by`: 时间分组 (day, week, month)
- `metric`: 指标类型
- `pattern_type`: 模式类型
- `name`: 可选的洞察名称

**响应** (201):
```json
{
  "id": "insight-uuid",
  "cluster_type": "summary",
  "name": "内容摘要",
  "description": "过去7天的主要内容摘要",
  "insight_data": {
    "summary": "共创建了100个卡片..."
  },
  "confidence": 0.9,
  "generated_at": "2024-01-01T00:00:00Z"
}
```

### 4.13 列出洞察

列出洞察集群

**端点**: `GET /api/v1/search/insights`

**请求头**:
```
Authorization: Bearer {access_token}
```

**查询参数**:
- `cluster_type`: 集群类型过滤
- `source_item_type`: 源项目类型过滤
- `limit`: 返回数量 (默认: 50)
- `offset`: 偏移量 (默认: 0)

**响应** (200):
```json
{
  "total": 20,
  "insights": [
    {
      "id": "insight-uuid",
      "cluster_type": "summary",
      "name": "内容摘要"
    }
  ]
}
```

### 4.14 获取洞察详情

获取单个洞察

**端点**: `GET /api/v1/search/insights/{insight_id}`

**请求头**:
```
Authorization: Bearer {access_token}
```

**响应** (200):
```json
{
  "id": "insight-uuid",
  "cluster_type": "summary",
  "name": "内容摘要",
  "insight_data": {}
}
```

### 4.15 删除洞察

删除洞察

**端点**: `DELETE /api/v1/search/insights/{insight_id}`

**请求头**:
```
Authorization: Bearer {access_token}
```

**响应** (204): 无内容

---

## 5. 收件箱 (Inbox)

**基础路径**: `/api/v1/inbox`

### 5.1 创建收件箱项目

创建新的收件箱项目

**端点**: `POST /api/v1/inbox/items`

**请求头**:
```
Authorization: Bearer {access_token}
```

**请求体**:
```json
{
  "workspace_id": "workspace-uuid",
  "type": "note",
  "title": "会议记录",
  "content": "今天讨论了...",
  "source_type": "manual",
  "source_meta": {
    "device": "mobile"
  }
}
```

**响应** (201):
```json
{
  "id": "inbox-uuid",
  "workspace_id": "workspace-uuid",
  "creator_id": "user-uuid",
  "type": "note",
  "title": "会议记录",
  "content": "今天讨论了...",
  "summary": null,
  "source_type": "manual",
  "source_meta": {},
  "status": "raw",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### 5.2 列出收件箱项目

列出收件箱项目

**端点**: `GET /api/v1/inbox/items`

**请求头**:
```
Authorization: Bearer {access_token}
```

**查询参数**:
- `workspace_id`: 工作区 ID (必填)
- `status`: 状态过滤 (raw, processing, processed)
- `type`: 类型过滤
- `source_type`: 来源类型过滤
- `search`: 搜索关键词
- `page`: 页码 (默认: 1)
- `page_size`: 每页数量 (默认: 20)

**响应** (200):
```json
{
  "items": [
    {
      "id": "inbox-uuid",
      "type": "note",
      "title": "会议记录",
      "status": "raw"
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 20,
  "has_more": true
}
```

### 5.3 获取收件箱项目

获取单个收件箱项目

**端点**: `GET /api/v1/inbox/items/{item_id}`

**请求头**:
```
Authorization: Bearer {access_token}
```

**查询参数**:
- `workspace_id`: 工作区 ID (必填)

**响应** (200):
```json
{
  "id": "inbox-uuid",
  "type": "note",
  "title": "会议记录",
  "content": "今天讨论了...",
  "status": "raw"
}
```

### 5.4 更新收件箱项目

更新收件箱项目

**端点**: `PUT /api/v1/inbox/items/{item_id}`

**请求头**:
```
Authorization: Bearer {access_token}
```

**查询参数**:
- `workspace_id`: 工作区 ID (必填)

**请求体**:
```json
{
  "title": "更新后的标题",
  "content": "更新后的内容",
  "type": "task"
}
```

**响应** (200): 返回更新后的项目

### 5.5 更新收件箱项目状态

更新收件箱项目状态

**端点**: `PATCH /api/v1/inbox/items/{item_id}/status`

**请求头**:
```
Authorization: Bearer {access_token}
```

**查询参数**:
- `workspace_id`: 工作区 ID (必填)

**请求体**:
```json
{
  "status": "processed"
}
```

**响应** (200): 返回更新后的项目

### 5.6 删除收件箱项目

删除收件箱项目

**端点**: `DELETE /api/v1/inbox/items/{item_id}`

**请求头**:
```
Authorization: Bearer {access_token}
```

**查询参数**:
- `workspace_id`: 工作区 ID (必填)

**响应** (204): 无内容

---

## 6. 今日概览 (Today)

**基础路径**: `/api/v1/today`

### 6.1 获取今日视图

获取今日聚合视图

**端点**: `GET /api/v1/today`

**请求头**:
```
Authorization: Bearer {access_token}
```

**查询参数**:
- `workspace_id`: 工作区 ID (必填)
- `limit`: 返回数量限制 (默认: 50)

**响应** (200):
```json
{
  "workspace_id": "workspace-uuid",
  "user_id": "user-uuid",
  "items": [
    {
      "id": "item-uuid",
      "type": "task",
      "title": "完成文档",
      "content": "编写API文档",
      "status": "todo",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z",
      "source_type": "inbox"
    }
  ],
  "summary": {
    "total_items": 15,
    "pending_items": 5,
    "completed_items": 10
  },
  "generated_at": "2024-01-01T00:00:00Z"
}
```

---

## 7. 聚合数据 (Aggregation)

**基础路径**: `/api/v1`

### 7.1 获取今日汇总

获取跨模块的今日汇总

**端点**: `GET /api/v1/today`

**查询参数**:
- `user_id`: 用户 ID (必填)

**响应** (200):
```json
{
  "inbox": {
    "pending": 5,
    "processed": 10,
    "total": 15
  },
  "tasks": [
    {
      "id": 1,
      "title": "完成文档",
      "status": "todo",
      "priority": 8
    }
  ],
  "knowledge": {
    "recent_cards": [
      {
        "id": "card-uuid",
        "title": "API设计",
        "tags": ["API"],
        "created_at": "2024-01-01T00:00:00Z"
      }
    ],
    "total_today": 5
  },
  "conversations": [
    {
      "id": 1,
      "session_id": "session-123",
      "role": "user",
      "content": "如何使用API...",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "summary": {
    "total_inbox": 15,
    "pending_inbox": 5,
    "total_tasks": 10,
    "pending_tasks": 5,
    "recent_knowledge": 5,
    "active_sessions": 3
  }
}
```

### 7.2 获取简化的今日汇总

获取简化的今日汇总（用于仪表盘）

**端点**: `GET /api/v1/today/summary`

**查询参数**:
- `user_id`: 用户 ID

**响应** (200):
```json
{
  "total_inbox": 15,
  "pending_inbox": 5,
  "total_tasks": 10,
  "pending_tasks": 5,
  "recent_knowledge": 5,
  "active_sessions": 3
}
```

---

## 8. 对话历史 (Conversations)

**基础路径**: `/api/v1/conversations`

### 8.1 获取对话历史

获取会话的对话历史

**端点**: `GET /api/v1/conversations/{session_id}/history`

**查询参数**:
- `session_id`: 会话 ID (必填)
- `user_id`: 用户 ID (必填)
- `limit`: 返回数量 (默认: 50)
- `before_id`: 获取此 ID 之前的消息

**响应** (200):
```json
[
  {
    "id": 1,
    "role": "user",
    "content": "如何使用 API？",
    "tool_calls": null,
    "model": "gpt-4",
    "tokens": 100,
    "created_at": "2024-01-01T00:00:00Z"
  },
  {
    "id": 2,
    "role": "assistant",
    "content": "您可以通过...",
    "tool_calls": null,
    "model": "gpt-4",
    "tokens": 200,
    "created_at": "2024-01-01T00:00:01Z"
  }
]
```

### 8.2 获取会话 Token 数量

获取会话的总 Token 数量

**端点**: `GET /api/v1/conversations/{session_id}/tokens`

**查询参数**:
- `session_id`: 会话 ID
- `user_id`: 用户 ID

**响应** (200):
```json
{
  "session_id": "session-123",
  "total_tokens": 1500
}
```

### 8.3 删除对话消息

删除单条对话消息

**端点**: `DELETE /api/v1/conversations/{conversation_id}`

**查询参数**:
- `conversation_id`: 对话 ID
- `user_id`: 用户 ID

**响应** (200):
```json
{
  "status": "deleted",
  "conversation_id": 1
}
```

### 8.4 获取最近会话

获取最近的会话列表

**端点**: `GET /api/v1/conversations/sessions/recent`

**查询参数**:
- `user_id`: 用户 ID
- `limit`: 返回数量 (默认: 10)

**响应** (200):
```json
[
  "session-123",
  "session-456",
  "session-789"
]
```

---

## 9. 工作流与技能 (Stage3 Agent)

**基础路径**: `/api/v1/agent`

### 9.1 启动工作流

启动 Agent 工作流执行

**端点**: `POST /api/v1/agent/flow/start`

**请求头**:
```
Authorization: Bearer {access_token}
```

**请求体**:
```json
{
  "task_id": "task-uuid",
  "skill_id": "skill-uuid",
  "initial_context": {
    "user_input": "帮我分析数据"
  }
}
```

**响应** (201):
```json
{
  "execution_id": "execution-uuid",
  "task_id": "task-uuid",
  "skill_id": "skill-uuid",
  "status": "running",
  "current_step": "step1"
}
```

### 9.2 获取工作流状态

获取工作流执行状态

**端点**: `GET /api/v1/agent/flow/{execution_id}/status`

**请求头**:
```
Authorization: Bearer {access_token}
```

**响应** (200):
```json
{
  "execution_id": "execution-uuid",
  "status": "waiting_decision",
  "current_step": "step3",
  "completed_steps": ["step1", "step2"],
  "context": {}
}
```

### 9.3 继续工作流

在决策确认后继续工作流

**端点**: `POST /api/v1/agent/flow/{execution_id}/continue`

**请求头**:
```
Authorization: Bearer {access_token}
```

**请求体**:
```json
{
  "decision_id": "decision-uuid",
  "selected_option_id": "option-uuid"
}
```

**响应** (200):
```json
{
  "execution_id": "execution-uuid",
  "status": "running",
  "current_step": "step4"
}
```

### 9.4 暂停工作流

暂停正在运行的工作流

**端点**: `POST /api/v1/agent/flow/{execution_id}/pause`

**请求头**:
```
Authorization: Bearer {access_token}
```

**响应** (200):
```json
{
  "execution_id": "execution-uuid",
  "status": "paused",
  "message": "Flow paused successfully"
}
```

### 9.5 恢复工作流

恢复暂停的工作流

**端点**: `POST /api/v1/agent/flow/{execution_id}/resume`

**请求头**:
```
Authorization: Bearer {access_token}
```

**响应** (200):
```json
{
  "execution_id": "execution-uuid",
  "status": "running",
  "message": "Flow resumed successfully"
}
```

### 9.6 获取决策点

获取决策点详情

**端点**: `GET /api/v1/agent/decisions/{decision_id}`

**请求头**:
```
Authorization: Bearer {access_token}
```

**响应** (200):
```json
{
  "id": "decision-uuid",
  "task_id": "task-uuid",
  "title": "选择处理方式",
  "description": "请选择如何处理此任务",
  "options": [
    {
      "id": "option-1",
      "title": "自动处理",
      "description": "让AI自动完成"
    },
    {
      "id": "option-2",
      "title": "手动处理",
      "description": "手动指定步骤"
    }
  ],
  "selected_option_id": null,
  "confirmed_by": null,
  "confirmed_at": null
}
```

### 9.7 确认决策

确认决策点选择

**端点**: `POST /api/v1/agent/decisions/{decision_id}/confirm`

**请求头**:
```
Authorization: Bearer {access_token}
```

**请求体**:
```json
{
  "selected_option_id": "option-1",
  "confirmed_by": "user-uuid"
}
```

**响应** (200):
```json
{
  "id": "decision-uuid",
  "selected_option_id": "option-1",
  "confirmed_by": "user-uuid",
  "confirmed_at": "2024-01-01T00:00:00Z"
}
```

### 9.8 获取任务的决策点

获取任务的所有决策点

**端点**: `GET /api/v1/agent/tasks/{task_id}/decisions`

**请求头**:
```
Authorization: Bearer {access_token}
```

**响应** (200):
```json
[
  {
    "id": "decision-uuid-1",
    "title": "决策1"
  },
  {
    "id": "decision-uuid-2",
    "title": "决策2"
  }
]
```

### 9.9 创建技能

创建新的技能

**端点**: `POST /api/v1/agent/skills`

**请求头**:
```
Authorization: Bearer {access_token}
```

**请求体**:
```json
{
  "name": "数据分析技能",
  "description": "自动分析数据的技能",
  "category": "analysis",
  "version": "1.0.0",
  "applicable_item_types": ["task"],
  "required_tags": ["data"],
  "steps": [
    {
      "step_order": 1,
      "step_type": "llm",
      "description": "分析数据",
      "config": {}
    }
  ]
}
```

**响应** (201):
```json
{
  "id": "skill-uuid",
  "name": "数据分析技能",
  "description": "自动分析数据的技能",
  "category": "analysis",
  "version": "1.0.0",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 9.10 列出技能

列出所有技能

**端点**: `GET /api/v1/agent/skills`

**请求头**:
```
Authorization: Bearer {access_token}
```

**查询参数**:
- `category`: 类别过滤
- `limit`: 返回数量 (默认: 100)
- `offset`: 偏移量 (默认: 0)

**响应** (200):
```json
[
  {
    "id": "skill-uuid",
    "name": "数据分析技能",
    "category": "analysis",
    "is_active": true
  }
]
```

### 9.11 获取技能详情

获取单个技能

**端点**: `GET /api/v1/agent/skills/{skill_id}`

**请求头**:
```
Authorization: Bearer {access_token}
```

**响应** (200):
```json
{
  "id": "skill-uuid",
  "name": "数据分析技能",
  "description": "自动分析数据的技能",
  "steps": []
}
```

### 9.12 更新技能

更新技能

**端点**: `PUT /api/v1/agent/skills/{skill_id}`

**请求头**:
```
Authorization: Bearer {access_token}
```

**请求体**:
```json
{
  "name": "更新后的名称",
  "description": "更新后的描述"
}
```

**响应** (200): 返回更新后的技能

### 9.13 删除技能

删除技能

**端点**: `DELETE /api/v1/agent/skills/{skill_id}`

**请求头**:
```
Authorization: Bearer {access_token}
```

**响应** (204): 无内容

### 9.14 推荐技能

获取任务推荐的技能

**端点**: `POST /api/v1/agent/skills/recommend`

**请求头**:
```
Authorization: Bearer {access_token}
```

**请求体**:
```json
{
  "task_type": "analysis",
  "task_tags": ["data", "report"],
  "task_content": "分析销售数据",
  "limit": 5
}
```

**响应** (200):
```json
[
  {
    "skill": {
      "id": "skill-uuid",
      "name": "数据分析技能"
    },
    "score": 0.95,
    "match_reason": "技能类型和标签匹配"
  }
]
```

### 9.15 获取执行日志

获取任务的执行日志

**端点**: `GET /api/v1/agent/tasks/{task_id}/execution-logs`

**请求头**:
```
Authorization: Bearer {access_token}
```

**查询参数**:
- `limit`: 返回数量 (默认: 100)

**响应** (200):
```json
[
  {
    "id": "log-uuid",
    "task_id": "task-uuid",
    "step_order": 1,
    "step_name": "step1",
    "status": "completed",
    "input": {},
    "output": {},
    "error": null,
    "started_at": "2024-01-01T00:00:00Z",
    "completed_at": "2024-01-01T00:01:00Z"
  }
]
```

---

## 10. Agent 核心 (Agent Core)

**基础路径**: `/api/v1/agent`

### 10.1 Agent Tick

触发 Agent 处理周期

**端点**: `POST /api/v1/agent/tick`

**请求头**:
```
Authorization: Bearer {access_token}
```

**请求体**:
```json
{
  "max_items": 10,
  "force_reprocess": false
}
```

**响应** (200):
```json
{
  "processed": 10,
  "succeeded": 9,
  "failed": 1,
  "skipped": 0,
  "results": [
    {
      "item_id": "item-uuid",
      "success": true,
      "from_status": "raw",
      "to_status": "processed",
      "title": "生成的标题",
      "summary": "生成的摘要",
      "item_type": "note"
    }
  ]
}
```

### 10.2 处理单个项目

处理指定的单个项目

**端点**: `POST /api/v1/agent/process/{item_id}`

**请求头**:
```
Authorization: Bearer {access_token}
```

**请求体**:
```json
{
  "force_reprocess": false
}
```

**响应** (200):
```json
{
  "success": true,
  "item_id": "item-uuid",
  "from_status": "raw",
  "to_status": "processed",
  "title": "生成的标题",
  "summary": "生成的摘要",
  "item_type": "note",
  "error": null,
  "processed_at": "2024-01-01T00:00:00Z"
}
```

### 10.3 获取 Agent 状态

获取 Agent 处理状态

**端点**: `GET /api/v1/agent/status`

**请求头**:
```
Authorization: Bearer {access_token}
```

**响应** (200):
```json
{
  "raw_count": 5,
  "processed_count": 100,
  "recent_raw_items": [
    {
      "id": "item-uuid",
      "title": "未处理的项目",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

---

## 11. 集成服务 (Integrations)

**基础路径**: `/integrations`

### 11.1 微信 Webhook 验证

验证微信服务器配置

**端点**: `GET /integrations/wechat/webhook`

**查询参数**:
- `signature`: 微信签名
- `timestamp`: 时间戳
- `nonce`: 随机数
- `echostr`: 验证字符串

**响应** (200): 返回 echostr

### 11.2 接收微信消息

接收来自微信的消息推送

**端点**: `POST /integrations/wechat/webhook`

**请求体** (XML):
```xml
<xml>
  <ToUserName><![CDATA[gh_example]]></ToUserName>
  <FromUserName><![CDATA[oEXAMPLE]]></FromUserName>
  <CreateTime>1234567890</CreateTime>
  <MsgType><![CDATA[text]]></MsgType>
  <Content><![CDATA[Hello]]></Content>
  <MsgId>1234567890123456</MsgId>
</xml>
```

**响应** (200):
```json
{
  "status": "success",
  "result": {
    "item_id": "item-uuid",
    "type": "resource"
  }
}
```

### 11.3 手动处理微信消息

手动触发微信消息处理

**端点**: `POST /integrations/wechat/process`

**请求体**:
```json
{
  "workspace_id": "workspace-uuid",
  "creator_id": "user-uuid",
  "xml_data": "<xml>...</xml>",
  "default_area_id": "area-uuid"
}
```

**响应** (200):
```json
{
  "status": "success",
  "result": {
    "item_id": "item-uuid"
  }
}
```

### 11.4 微信健康检查

检查微信服务状态

**端点**: `GET /integrations/wechat/health`

**响应** (200):
```json
{
  "status": "healthy",
  "service": "wechat-webhook"
}
```

### 11.5 发送微信文本消息

发送文本消息到微信

**端点**: `POST /integrations/wechat/send/text`

**请求体**:
```json
{
  "openid": "user-openid",
  "content": "Hello from AgentOS!"
}
```

**响应** (200):
```json
{
  "status": "success",
  "errcode": 0,
  "errmsg": "ok",
  "msgid": "1234567890"
}
```

### 11.6 发送微信图文消息

发送图文消息到微信

**端点**: `POST /integrations/wechat/send/news`

**请求体**:
```json
{
  "openid": "user-openid",
  "articles": [
    {
      "title": "文章标题",
      "description": "文章描述",
      "url": "https://example.com/article",
      "picurl": "https://example.com/image.jpg"
    }
  ]
}
```

**响应** (200):
```json
{
  "status": "success",
  "errcode": 0,
  "errmsg": "ok"
}
```

### 11.7 发送微信卡片消息

发送卡片消息到微信

**端点**: `POST /integrations/wechat/send/card`

**请求体**:
```json
{
  "openid": "user-openid",
  "title": "卡片标题",
  "description": "卡片描述",
  "url": "https://example.com",
  "image_url": "https://example.com/image.jpg"
}
```

**响应** (200):
```json
{
  "status": "success",
  "errcode": 0,
  "errmsg": "ok"
}
```

### 11.8 爬取 URL

爬取网页内容

**端点**: `POST /integrations/crawler/crawl`

**请求体**:
```json
{
  "url": "https://example.com",
  "timeout": 10
}
```

**响应** (200):
```json
{
  "url": "https://example.com",
  "title": "页面标题",
  "description": "页面描述",
  "content": "页面内容...",
  "links": ["https://example.com/page1"],
  "content_type": "text/html",
  "status": "success"
}
```

### 11.9 提取链接

从文本中提取链接

**端点**: `POST /integrations/crawler/extract-links`

**请求体**:
```json
{
  "text": "查看 https://example.com 和 https://google.com"
}
```

**响应** (200):
```json
{
  "urls": [
    "https://example.com",
    "https://google.com"
  ],
  "count": 2
}
```

### 11.10 从 URL 创建资源

从 URL 创建 Resource Item

**端点**: `POST /integrations/crawler/create-resource`

**请求头**:
```
Authorization: Bearer {access_token}
```

**请求体**:
```json
{
  "workspace_id": "workspace-uuid",
  "creator_id": "user-uuid",
  "url": "https://example.com",
  "title": "自定义标题",
  "default_area_id": "area-uuid"
}
```

**响应** (200):
```json
{
  "status": "success",
  "result": {
    "item_id": "item-uuid",
    "type": "resource",
    "url": "https://example.com",
    "title": "自定义标题"
  }
}
```

### 11.11 集成服务健康检查

检查集成服务状态

**端点**: `GET /integrations/health`

**响应** (200):
```json
{
  "status": "healthy",
  "service": "integrations"
}
```

---

## 12. 连接管理 (Connections)

**基础路径**: `/connections`

### 12.1 获取节点连接

查询节点的所有连接

**端点**: `GET /connections/{node_id}`

**查询参数**:
- `strong_only`: 是否只查询强连接 (默认: false)
- `limit`: 返回数量限制 (默认: 100)

**响应** (200):
```json
{
  "node_id": "node-uuid",
  "connections": [
    {
      "id": "edge-uuid",
      "from_node_id": "node-uuid-1",
      "to_node_id": "node-uuid-2",
      "weight": 0.85,
      "relation_type": "semantic",
      "is_strong": true,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total_count": 50,
  "strong_count": 10
}
```

### 12.2 获取强连接

查询节点的强连接

**端点**: `GET /connections/{node_id}/strong`

**查询参数**:
- `limit`: 返回数量限制 (默认: 50)

**响应** (200):
```json
{
  "node_id": "node-uuid",
  "connections": [],
  "total_count": 50,
  "strong_count": 10
}
```

### 12.3 获取连接统计

获取节点的连接统计信息

**端点**: `GET /connections/{node_id}/stats`

**响应** (200):
```json
{
  "node_id": "node-uuid",
  "total_connections": 50,
  "strong_connections": 10,
  "average_weight": 0.65,
  "connection_types": {
    "semantic": 30,
    "temporal": 15,
    "hierarchical": 5
  }
}
```

### 12.4 获取连接图

获取节点的连接图数据（用于可视化）

**端点**: `GET /connections/{node_id}/graph`

**查询参数**:
- `depth`: 图深度 (目前只支持 1)
- `limit`: 每层节点数量限制 (默认: 50)

**响应** (200):
```json
{
  "nodes": [
    {
      "id": "node-uuid",
      "label": "节点标题",
      "type": "note",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "edges": [
    {
      "from_node": "node-uuid-1",
      "to_node": "node-uuid-2",
      "weight": 0.85,
      "relation_type": "semantic",
      "is_strong": true
    }
  ]
}
```

### 12.5 重新计算连接

手动触发连接计算

**端点**: `POST /connections/recalculate`

**请求体**:
```json
{
  "item_id": "item-uuid",
  "limit": 100
}
```

**响应** (200):
```json
{
  "item_id": "item-uuid",
  "connections_created": 5,
  "connections_updated": 3,
  "message": "Processed 50 candidates"
}
```

### 12.6 连接服务健康检查

检查连接服务状态

**端点**: `GET /connections/health`

**响应** (200):
```json
{
  "status": "healthy",
  "service": "connection-engine",
  "version": "stage-3"
}
```

---

## 13. 工作区与条目 (Items)

**基础路径**: `/prd4`

### 13.1 创建工作区

创建新的工作区

**端点**: `POST /prd4/workspaces`

**请求头**:
```
Authorization: Bearer {access_token}
```

**请求体**:
```json
{
  "name": "我的工作区",
  "owner_id": "user-uuid",
  "description": "工作区描述"
}
```

**响应** (201):
```json
{
  "id": "workspace-uuid",
  "name": "我的工作区",
  "owner_id": "user-uuid",
  "description": "工作区描述",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 13.2 获取工作区

获取单个工作区

**端点**: `GET /prd4/workspaces/{workspace_id}`

**响应** (200):
```json
{
  "id": "workspace-uuid",
  "name": "我的工作区",
  "owner_id": "user-uuid"
}
```

### 13.3 列出工作区

列出工作区

**端点**: `GET /prd4/workspaces`

**查询参数**:
- `owner_id`: 所有者 ID
- `skip`: 跳过数量 (默认: 0)
- `limit`: 返回数量 (默认: 100)

**响应** (200): 返回工作区列表

### 13.4 创建区域

创建新的区域

**端点**: `POST /prd4/areas`

**请求体**:
```json
{
  "workspace_id": "workspace-uuid",
  "name": "工作",
  "parent_id": null,
  "color": "#FF5733"
}
```

**响应** (201):
```json
{
  "id": "area-uuid",
  "workspace_id": "workspace-uuid",
  "name": "工作",
  "parent_id": null,
  "color": "#FF5733"
}
```

### 13.5 获取区域

获取单个区域

**端点**: `GET /prd4/areas/{area_id}`

**响应** (200): 返回区域详情

### 13.6 列出区域

列出区域

**端点**: `GET /prd4/areas`

**查询参数**:
- `workspace_id`: 工作区 ID
- `parent_id`: 父区域 ID

**响应** (200): 返回区域列表

### 13.7 获取区域树

获取区域的树形结构

**端点**: `GET /prd4/areas/{workspace_id}/tree`

**响应** (200): 返回区域树

### 13.8 更新区域

更新区域

**端点**: `PUT /prd4/areas/{area_id}`

**请求体**:
```json
{
  "name": "更新后的名称",
  "color": "#00FF00"
}
```

**响应** (200): 返回更新后的区域

### 13.9 删除区域

删除区域

**端点**: `DELETE /prd4/areas/{area_id}`

**响应** (204): 无内容

### 13.10 创建项目

创建新项目

**端点**: `POST /prd4/projects`

**请求体**:
```json
{
  "workspace_id": "workspace-uuid",
  "area_id": "area-uuid",
  "name": "API 开发",
  "description": "开发 RESTful API",
  "status": "active"
}
```

**响应** (201):
```json
{
  "id": "project-uuid",
  "workspace_id": "workspace-uuid",
  "area_id": "area-uuid",
  "name": "API 开发",
  "status": "active"
}
```

### 13.11 获取项目

获取单个项目

**端点**: `GET /prd4/projects/{project_id}`

**响应** (200): 返回项目详情

### 13.12 列出项目

列出项目

**端点**: `GET /prd4/projects`

**查询参数**:
- `workspace_id`: 工作区 ID
- `area_id`: 区域 ID
- `skip`: 跳过数量
- `limit`: 返回数量

**响应** (200): 返回项目列表

### 13.13 创建条目

创建新条目

**端点**: `POST /prd4/items`

**请求体**:
```json
{
  "workspace_id": "workspace-uuid",
  "creator_id": "user-uuid",
  "type": "note",
  "title": "会议记录",
  "content": "今天讨论了...",
  "area_id": "area-uuid",
  "project_id": "project-uuid"
}
```

**响应** (201):
```json
{
  "id": "item-uuid",
  "workspace_id": "workspace-uuid",
  "creator_id": "user-uuid",
  "type": "note",
  "title": "会议记录",
  "status": "active"
}
```

### 13.14 获取条目

获取单个条目

**端点**: `GET /prd4/items/{item_id}`

**响应** (200): 返回条目详情

### 13.15 更新条目

更新条目

**端点**: `PUT /prd4/items/{item_id}`

**请求体**:
```json
{
  "title": "更新后的标题",
  "content": "更新后的内容"
}
```

**响应** (200): 返回更新后的条目

### 13.16 删除条目

删除条目（软删除）

**端点**: `DELETE /prd4/items/{item_id}`

**响应** (204): 无内容

### 13.17 列出条目

列出条目（带分页）

**端点**: `GET /prd4/items`

**查询参数**:
- `workspace_id`: 工作区 ID
- `type`: 类型过滤
- `area_id`: 区域 ID
- `project_id`: 项目 ID
- `status`: 状态过滤
- `page`: 页码
- `page_size`: 每页数量

**响应** (200):
```json
{
  "items": [],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```

### 13.18 创建任务扩展

为条目创建任务扩展

**端点**: `POST /prd4/task-extensions`

**请求体**:
```json
{
  "item_id": "item-uuid",
  "priority": 8,
  "due_date": "2024-12-31",
  "estimated_time_minutes": 120
}
```

**响应** (201): 返回任务扩展

### 13.19 获取任务扩展

获取条目的任务扩展

**端点**: `GET /prd4/task-extensions/{item_id}`

**响应** (200): 返回任务扩展

### 13.20 创建决策点

创建决策点

**端点**: `POST /prd4/decision-points`

**请求体**:
```json
{
  "task_id": "task-uuid",
  "title": "选择处理方式",
  "description": "请选择如何处理",
  "options": [
    {
      "id": "option-1",
      "title": "自动处理"
    }
  ]
}
```

**响应** (201): 返回决策点

### 13.21 获取任务的决策点

获取任务的所有决策点

**端点**: `GET /prd4/decision-points/{task_id}`

**响应** (200): 返回决策点列表

### 13.22 确认决策

确认决策点

**端点**: `POST /prd4/decision-points/{decision_id}/confirm`

**请求体**:
```json
{
  "option_id": "option-uuid",
  "confirmed_by": "user-uuid"
}
```

**响应** (200): 返回更新后的决策点

### 13.23 创建审计事件

创建审计日志事件

**端点**: `POST /prd4/ledger-events`

**请求体**:
```json
{
  "task_id": "task-uuid",
  "event_type": "status_change",
  "from_value": "todo",
  "to_value": "in_progress",
  "changed_by": "user-uuid"
}
```

**响应** (201): 返回审计事件

### 13.24 获取任务审计日志

获取任务的完整审计日志

**端点**: `GET /prd4/ledger-events/{task_id}`

**响应** (200): 返回审计事件列表

### 13.25 创建连接

创建图连接边

**端点**: `POST /prd4/connections/edges`

**请求体**:
```json
{
  "from_node_id": "node-uuid-1",
  "to_node_id": "node-uuid-2",
  "relation_type": "semantic",
  "weight": 0.85
}
```

**响应** (201): 返回连接边

### 13.26 获取节点的连接

查询节点的所有连接

**端点**: `GET /prd4/connections/{node_id}`

**查询参数**:
- `strong_only`: 是否只查询强连接

**响应** (200): 返回连接列表

### 13.27 获取强连接

仅查询强连接

**端点**: `GET /prd4/connections/{node_id}/strong`

**响应** (200): 返回强连接列表

### 13.28 删除连接

删除连接

**端点**: `DELETE /prd4/connections/edges/{edge_id}`

**响应** (204): 无内容

---

## 14. 可观测性 (Observability)

**基础路径**: `/observability`

### 14.1 获取性能指标

获取系统性能指标

**端点**: `GET /observability/metrics`

**响应** (200):
```json
{
  "request_count": 10000,
  "error_count": 50,
  "error_rate": 0.005,
  "avg_response_time": 150.5,
  "p95_response_time": 300.0,
  "p99_response_time": 500.0,
  "endpoint_stats": [
    {
      "endpoint": "/api/v1/cards",
      "count": 5000,
      "errors": 10,
      "avg_time": 100.0,
      "max_time": 500.0
    }
  ]
}
```

### 14.2 重置性能指标

重置性能指标统计

**端点**: `POST /observability/metrics/reset`

**响应** (200):
```json
{
  "status": "success",
  "message": "Metrics reset successfully"
}
```

### 14.3 获取健康状态

获取系统健康检查结果

**端点**: `GET /observability/health`

**响应** (200):
```json
{
  "status": "healthy",
  "checks": {
    "database": {
      "status": "healthy",
      "message": "Database connection OK"
    },
    "redis": {
      "status": "healthy",
      "message": "Redis connection OK"
    }
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### 14.4 简单健康检查

简单的健康检查端点

**端点**: `GET /observability/health/simple`

**响应** (200):
```json
{
  "status": "healthy",
  "service": "agent-os"
}
```

### 14.5 获取系统信息

获取系统信息

**端点**: `GET /observability/info`

**响应** (200):
```json
{
  "service": "agent-os",
  "version": "1.0.0",
  "environment": "production",
  "system": {
    "cpu_percent": 45.5,
    "memory": {
      "total": 17179869184,
      "available": 8589934592,
      "used": 8589934592,
      "percent": 50.0
    },
    "disk": {
      "total": 500000000000,
      "used": 250000000000,
      "free": 250000000000,
      "percent": 50.0
    }
  },
  "timestamp": 1704067200.0
}
```

---

## 认证与授权

### JWT Token 认证

大部分 API 端点需要 JWT Bearer Token 认证：

**请求头格式**:
```
Authorization: Bearer {access_token}
```

### Token 类型

1. **Access Token**: 用于访问 API，有效期 30 分钟
2. **Refresh Token**: 用于刷新 Access Token，有效期 7 天

### 获取 Token

通过 `/api/v1/auth/register` 或 `/api/v1/auth/login` 获取 token 对。

### 刷新 Token

当 Access Token 过期时，使用 Refresh Token 获取新的 token 对：

```bash
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ0eXAi..."
}
```

---

## 分页与过滤

### 分页参数

大多数列表端点支持分页：

**查询参数**:
- `page`: 页码 (从 1 开始，默认: 1)
- `page_size`: 每页数量 (默认: 20/50，最大: 100-200)

**响应格式**:
```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "has_more": true
}
```

### 过滤参数

常见过滤参数：
- `status`: 状态过滤
- `type`: 类型过滤
- `tags`: 标签过滤 (逗号分隔)
- `date_from`: 开始日期
- `date_to`: 结束日期
- `search`: 文本搜索

### 排序参数

常见排序参数：
- `sort_by`: 排序字段 (如: created_at, priority)
- `sort_order`: 排序方向 (asc, desc)

---

## 错误处理

### 错误响应格式

所有错误响应遵循统一格式：

```json
{
  "detail": "错误描述信息"
}
```

### HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 OK | 请求成功 |
| 201 Created | 资源创建成功 |
| 204 No Content | 删除成功，无返回内容 |
| 400 Bad Request | 请求参数错误 |
| 401 Unauthorized | 未认证或 Token 无效 |
| 403 Forbidden | 禁止访问 |
| 404 Not Found | 资源不存在 |
| 422 Unprocessable Entity | 请求格式正确但语义错误 |
| 500 Internal Server Error | 服务器内部错误 |

### 常见错误场景

1. **认证失败** (401):
   - Token 缺失或格式错误
   - Token 过期
   - Token 签名无效

2. **权限不足** (403):
   - 用户无权访问该资源
   - 跨工作区访问

3. **资源不存在** (404):
   - 资源 ID 不存在
   - 资源已被删除

4. **参数错误** (400):
   - 必填参数缺失
   - 参数格式错误
   - 参数值超出范围

---

## 版本历史

### v6.0 (2026-02-16) - 邮箱验证码注册登录 ⭐ NEW

- 新增邮箱验证码注册 API - POST /auth/register/email
- 新增邮箱验证码登录 API - POST /auth/login/email
- 集成阿里企业邮箱SMTP服务（smtp.qiye.aliyun.com:465）
- 支持所有邮箱类型（QQ、Gmail、163等）
- 实现无密码登录功能
- Web测试界面：http://localhost:8003/static/email-auth.html
- 总计 154+ API 端点
- 生产环境就绪

### v5.0 (2026-02-14)

- 新增验证码功能 API (PRD5)
- POST /auth/send-code - 发送验证码到邮箱
- POST /auth/verify-code - 验证邮箱验证码
- 集成 SMTP 邮件服务
- 支持验证码频控和锁定机制
- 总计 152+ API 端点

### v4.0 (2026-02-11)

- 完整的 API 文档，覆盖所有模块
- 150+ API 端点
- 新增 Stage3 Agent 工作流和技能 API
- 新增 Items PRD4 统一条目 API
- 新增 Connections 认知图 API
- 新增 Observability 可观测性 API
- 完善所有模块的 CRUD 操作
- 统一响应格式和错误处理

### v3.0 (2026-02-10)

- 新增微信集成 API
- 60+ API 端点

### v2.0 (2026-01-28)

- 生产级 API
- 完善认证和授权

### v1.0 (2026-01-01)

- 初始版本

---

**最后更新**: 2026-02-16
**维护者**: AgentOS Team
**文档版本**: v6.0
