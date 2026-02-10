# AgentOS API 完整参考文档

**版本**: v3.0
**最后更新**: 2026-02-10
**基础路径**: `/api/v1`
**总计**: 60+ API 端点

---

## 📋 目录

1. [认证系统 (Auth)](#1-认证系统-auth)
2. [知识管理 (Knowledge)](#2-知识管理-knowledge)
3. [任务管理 (Tasks)](#3-任务管理-tasks)
4. [搜索引擎 (Search)](#4-搜索引擎-search)
5. [洞察生成 (Insights)](#5-洞察生成-insights)
6. [内容抓取 (Ingestion)](#6-内容抓取-ingestion)
7. [微信集成 (WeChat)](#7-微信集成-wechat)
8. [爬虫工具 (Crawler)](#8-爬虫工具-crawler)

---

## 1. 认证系统 (Auth)

**基础路径**: `/api/v1/auth`

### 1.1 用户注册

创建新用户账户

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

### 1.3 刷新令牌

使用刷新令牌获取新的访问令牌

**端点**: `POST /api/v1/auth/refresh`

**请求头**:
```
Authorization: Bearer {refresh_token}
```

**响应** (200):
```json
{
  "access_token": "eyJ0eXAi...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### 1.4 获取用户信息

获取当前用户信息

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
  "theme": "dark",
  "language": "zh-CN"
}
```

**响应** (200):
```json
{
  "id": "settings-uuid",
  "theme": "dark",
  "language": "zh-CN"
}
```

---

## 2. 知识管理 (Knowledge)

**基础路径**: `/api/v1/knowledge`

### 2.1 创建 Inbox 项

创建新的收件箱项目

**端点**: `POST /api/v1/knowledge/inbox`

**请求头**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**请求体**:
```json
{
  "workspace_id": "workspace-uuid",
  "creator_id": "user-uuid",
  "content": "这是一个待整理的笔记内容",
  "source_type": "manual"
}
```

**响应** (201):
```json
{
  "id": "inbox-uuid",
  "content": "这是一个待整理的笔记内容",
  "status": "raw",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 2.2 列出 Inbox 项目

获取所有收件箱项目

**端点**: `GET /api/v1/knowledge/inbox`

**请求头**:
```
Authorization: Bearer {access_token}
```

**查询参数**:
- `status`: 过滤状态 (raw, processing, processed)
- `limit`: 返回数量限制 (默认: 50)
- `offset`: 偏移量 (默认: 0)

**响应** (200):
```json
{
  "items": [
    {
      "id": "inbox-uuid",
      "content": "笔记内容",
      "status": "raw",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

### 2.3 创建 Card

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
  "workspace_id": "workspace-uuid",
  "creator_id": "user-uuid",
  "title": "知识卡片标题",
  "content": "卡片详细内容",
  "card_type": "concept",
  "tags": ["重要", "技术"]
}
```

**响应** (201):
```json
{
  "id": "card-uuid",
  "title": "知识卡片标题",
  "content": "卡片详细内容",
  "card_type": "concept",
  "tags": ["重要", "技术"],
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 2.4 搜索 Card

搜索知识卡片

**端点**: `GET /api/v1/knowledge/cards/search`

**请求头**:
```
Authorization: Bearer {access_token}
```

**查询参数**:
- `q`: 搜索关键词
- `card_type`: 卡片类型过滤
- `tags`: 标签过滤 (逗号分隔)

**响应** (200):
```json
{
  "results": [
    {
      "id": "card-uuid",
      "title": "知识卡片标题",
      "content": "卡片详细内容",
      "score": 0.95
    }
  ],
  "total": 10
}
```

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
  "workspace_id": "workspace-uuid",
  "creator_id": "user-uuid",
  "title": "完成项目文档",
  "description": "编写完整的项目文档",
  "priority": "high",
  "due_date": "2024-12-31"
}
```

**响应** (201):
```json
{
  "id": "task-uuid",
  "title": "完成项目文档",
  "status": "todo",
  "priority": "high",
  "due_date": "2024-12-31",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 3.2 列出任务

获取任务列表

**端点**: `GET /api/v1/tasks`

**请求头**:
```
Authorization: Bearer {access_token}
```

**查询参数**:
- `status`: 任务状态 (todo, in_progress, done)
- `priority`: 优先级 (low, medium, high)
- `due_date`: 截止日期范围

**响应** (200):
```json
{
  "tasks": [
    {
      "id": "task-uuid",
      "title": "完成项目文档",
      "status": "todo",
      "priority": "high",
      "due_date": "2024-12-31"
    }
  ],
  "total": 25
}
```

### 3.3 更新任务

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
  "priority": "medium"
}
```

**响应** (200):
```json
{
  "id": "task-uuid",
  "title": "更新后的标题",
  "status": "in_progress",
  "priority": "medium",
  "updated_at": "2024-01-01T12:00:00Z"
}
```

### 3.4 删除任务

删除指定任务

**端点**: `DELETE /api/v1/tasks/{task_id}`

**请求头**:
```
Authorization: Bearer {access_token}
```

**响应** (204):
```
(空响应体)
```

### 3.5 今日聚合

获取今天的任务聚合

**端点**: `GET /api/v1/tasks/today`

**请求头**:
```
Authorization: Bearer {access_token}
```

**响应** (200):
```json
{
  "todo": 5,
  "in_progress": 3,
  "done": 10,
  "total": 18
}
```

---

## 4. 搜索引擎 (Search)

**基础路径**: `/api/v1/search`

### 4.1 全文搜索

全文搜索索引内容

**端点**: `POST /api/v1/search/fulltext`

**请求头**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**请求体**:
```json
{
  "query": "搜索关键词",
  "item_types": ["card", "task"],
  "limit": 20
}
```

**响应** (200):
```json
{
  "results": [
    {
      "id": "item-uuid",
      "item_type": "card",
      "title": "结果标题",
      "content": "匹配的内容片段...",
      "score": 0.89
    }
  ],
  "total": 45,
  "query_time_ms": 5.49
}
```

### 4.2 向量搜索

向量相似度搜索

**端点**: `POST /api/v1/search/vector`

**请求头**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**请求体**:
```json
{
  "query": "搜索查询",
  "item_types": ["card"],
  "limit": 10
}
```

**响应** (200):
```json
{
  "results": [
    {
      "id": "item-uuid",
      "item_type": "card",
      "title": "结果标题",
      "similarity": 0.92
    }
  ],
  "total": 10,
  "query_time_ms": 1.14
}
```

### 4.3 混合搜索

结合全文和向量搜索

**端点**: `POST /api/v1/search/hybrid`

**请求头**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**请求体**:
```json
{
  "query": "搜索查询",
  "item_types": ["card", "task"],
  "limit": 20,
  "alpha": 0.5
}
```

**响应** (200):
```json
{
  "results": [
    {
      "id": "item-uuid",
      "item_type": "card",
      "title": "结果标题",
      "content": "内容片段...",
      "score": 0.91,
      "similarity": 0.88
    }
  ],
  "total": 38,
  "query_time_ms": 2.21
}
```

---

## 5. 洞察生成 (Insights)

**基础路径**: `/api/v1/insights`

### 5.1 生成摘要

生成内容摘要

**端点**: `POST /api/v1/insights/summary`

**请求头**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**请求体**:
```json
{
  "item_types": ["card"],
  "time_range": "7d",
  "limit": 100
}
```

**响应** (200):
```json
{
  "summary": "过去7天创建了100个卡片，主要关注技术文档和用户手册...",
  "item_count": 100,
  "time_range": "7d"
}
```

### 5.2 趋势分析

分析内容趋势

**端点**: `POST /api/v1/insights/trends`

**请求头**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**请求体**:
```json
{
  "item_types": ["card"],
  "time_range": "30d"
}
```

**响应** (200):
```json
{
  "trends": [
    {
      "date": "2024-01-01",
      "count": 15
    },
    {
      "date": "2024-01-02",
      "count": 22
    }
  ],
  "growth_rate": "+15%"
}
```

### 5.3 主题提取

提取内容主题

**端点**: `POST /api/v1/insights/topics`

**请求头**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**请求体**:
```json
{
  "item_types": ["card"],
  "limit": 200
}
```

**响应** (200):
```json
{
  "topics": [
    {
      "name": "技术文档",
      "count": 45,
      "keywords": ["API", "文档", "开发"]
    },
    {
      "name": "用户手册",
      "count": 32,
      "keywords": ["指南", "教程", "使用"]
    }
  ]
}
```

---

## 6. 内容抓取 (Ingestion)

**基础路径**: `/api/v1/ingestion`

### 6.1 抓取 URL

抓取网页内容

**端点**: `POST /api/v1/ingestion/fetch`

**请求头**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**请求体**:
```json
{
  "url": "https://example.com/article",
  "workspace_id": "workspace-uuid",
  "creator_id": "user-uuid"
}
```

**响应** (200):
```json
{
  "job_id": "ingestion-uuid",
  "url": "https://example.com/article",
  "status": "processing",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 6.2 查询抓取任务状态

查询抓取任务状态

**端点**: `GET /api/v1/ingestion/jobs/{job_id}`

**请求头**:
```
Authorization: Bearer {access_token}
```

**响应** (200):
```json
{
  "id": "ingestion-uuid",
  "url": "https://example.com/article",
  "status": "completed",
  "title": "文章标题",
  "content": "抓取的内容...",
  "error": null
}
```

---

## 7. 微信集成 (WeChat)

**基础路径**: `/integrations/wechat`

### 7.1 Webhook 验证

验证微信服务器配置

**端点**: `GET /integrations/wechat/webhook`

**查询参数**:
- `signature`: 微信签名
- `timestamp`: 时间戳
- `nonce`: 随机数
- `echostr**: 验证字符串

**响应** (200):
```
{echostr}
```

### 7.2 接收微信消息

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
  "message": "WeChat message processed successfully",
  "result": {
    "id": "item-uuid",
    "type": "resource"
  }
}
```

### 7.3 发送文本消息 ✨

发送文本消息到微信

**端点**: `POST /integrations/wechat/send/text`

**请求头**:
```
Content-Type: application/json
```

**请求体**:
```json
{
  "openid": "user_openid",
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

**错误响应** (500):
```json
{
  "status": "error",
  "errcode": 40001,
  "errmsg": "invalid credential"
}
```

### 7.4 发送图文消息 ✨

发送图文消息到微信

**端点**: `POST /integrations/wechat/send/news`

**请求头**:
```
Content-Type: application/json
```

**请求体**:
```json
{
  "openid": "user_openid",
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

**注意**: 最多支持 8 篇文章

### 7.5 发送卡片消息 ✨

发送卡片消息（单图文）到微信

**端点**: `POST /integrations/wechat/send/card`

**请求头**:
```
Content-Type: application/json
```

**请求体**:
```json
{
  "openid": "user_openid",
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

**字段说明**:
- `openid`: 用户 OpenID（必填）
- `title`: 标题（必填）
- `description`: 描述（必填）
- `url`: 点击跳转 URL（必填）
- `image_url`: 图片 URL（可选）

### 7.6 手动处理消息

手动触发微信消息处理

**端点**: `POST /integrations/wechat/process`

**请求头**:
```
Content-Type: application/json
```

**请求体**:
```json
{
  "workspace_id": "workspace-uuid",
  "creator_id": "user-uuid",
  "xml_data": "<xml>...</xml_data>",
  "default_area_id": "area-uuid"
}
```

**响应** (200):
```json
{
  "status": "success",
  "result": {
    "id": "item-uuid"
  }
}
```

### 7.7 健康检查

检查微信服务状态

**端点**: `GET /integrations/wechat/health`

**响应** (200):
```json
{
  "status": "healthy",
  "service": "wechat-webhook"
}
```

---

## 8. 爬虫工具 (Crawler)

**基础路径**: `/integrations/crawler`

### 8.1 爬取 URL

爬取网页内容

**端点**: `POST /integrations/crawler/crawl`

**请求头**:
```
Content-Type: application/json
```

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

### 8.2 提取链接

从文本中提取链接

**端点**: `POST /integrations/crawler/extract-links`

**请求头**:
```
Content-Type: application/json
```

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

### 8.3 从 URL 创建资源

从 URL 创建 Resource Item

**端点**: `POST /integrations/crawler/create-resource`

**请求头**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
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

---

## 错误响应格式

所有错误响应遵循统一格式：

```json
{
  "detail": "错误描述信息"
}
```

**常见 HTTP 状态码**:
- `200 OK` - 请求成功
- `201 Created` - 资源创建成功
- `204 No Content` - 删除成功
- `400 Bad Request` - 请求参数错误
- `401 Unauthorized` - 未授权
- `403 Forbidden` - 禁止访问
- `404 Not Found` - 资源不存在
- `500 Internal Server Error` - 服务器内部错误

---

## 认证说明

大部分 API 需要 JWT Bearer Token 认证：

**请求头**:
```
Authorization: Bearer {access_token}
```

**获取 Token**:
通过 `/api/v1/auth/register` 或 `/api/v1/auth/login` 获取

**Token 有效期**:
- Access Token: 30 分钟
- Refresh Token: 7 天

---

## 分页说明

所有列表接口支持分页：

**查询参数**:
- `limit`: 每页数量 (默认: 50, 最大: 100)
- `offset`: 偏移量 (默认: 0)

**响应格式**:
```json
{
  "items": [...],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

---

## 版本历史

- **v3.0** (2026-02-10): 新增微信集成 API
- **v2.0** (2026-01-28): 生产级 API，60+ 端点
- **v1.0** (2026-01-01): 初始版本

---

**最后更新**: 2026-02-10
**维护者**: AgentOS Team
