# PRD5 - Stage 1 后端验收补充需求

**文档类型:** 需求规格文档 (PRD)
**创建日期:** 2026-02-06
**优先级:** P0 (阻塞验收)
**目标:** 满足 PA 1.0 阶段一后端验收标准

---

## 📋 文档概述

### 背景

当前项目已完成 PRD4 的 7 个阶段实施，包含完善的数据模型、安全认证、连接引擎等核心功能。然而，根据 PA 1.0 阶段一后端验收标准验证，项目在 **67% 完成度**，主要缺失 **API 路由层** 的实现。

本文档定义补充需求，将项目从 **67%** 提升到 **100%**，完全满足 PA 1.0 阶段一验收标准。

### 验证差距总结

| 验收类别 | 状态 | 完成度 | 主要缺失 |
|---------|------|--------|----------|
| 项目工程基础 | ✅ | 100% | 无 |
| 鉴权与用户能力 | ⚠️ | 75% | API 路由 |
| Inbox 模块 | ⚠️ | 60% | API 路由、CRUD |
| Today 接口 | ❌ | 0% | 完全缺失 |
| 部署能力 | ✅ | 100% | 无 |

---

## 一、优先级 P0 - 阻塞验收的核心功能

**时间估算:** 2-3 天
**目标:** 满足验收标准，打通 Inbox → Today 信息流

### 1.1 认证 API 路由

**优先级:** P0
**模块:** `src/agent_os/auth/`

**需求描述:**

实现用户注册、登录、登出和信息查询的完整 API 接口。

#### 1.1.1 POST /auth/register

**功能:** 用户注册

**请求:**
```json
{
  "email": "user@example.com",
  "username": "testuser",
  "password": "secure_password",
  "full_name": "Test User"  // 可选
}
```

**响应 (201 Created):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "username": "testuser",
  "full_name": "Test User",
  "is_active": true,
  "is_verified": false,
  "created_at": "2026-02-06T00:00:00Z"
}
```

**错误响应:**
- 400: 用户名或邮箱已存在
- 400: 密码不符合要求（最少8字符）
- 422: 验证错误

**实现要点:**
- 使用 `get_password_hash()` 哈希密码
- 检查 email 和 username 唯一性
- 创建默认 workspace
- 返回 201 状态码

#### 1.1.2 POST /auth/login

**功能:** 用户登录

**请求:**
```json
{
  "username": "testuser",  // 或 email
  "password": "user_password"
}
```

**响应 (200 OK):**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "username": "testuser",
    "full_name": "Test User",
    "is_active": true
  }
}
```

**错误响应:**
- 401: 用户名或密码错误
- 401: 用户已被禁用
- 422: 验证错误

**实现要点:**
- 使用 `verify_password()` 验证密码
- 使用 `create_access_token()` 生成令牌
- 使用 `create_refresh_token()` 生成刷新令牌
- 更新 `last_login_at` 字段

#### 1.1.3 GET /auth/me

**功能:** 获取当前用户信息

**请求头:**
```
Authorization: Bearer <access_token>
```

**响应 (200 OK):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "username": "testuser",
  "full_name": "Test User",
  "is_active": true,
  "is_verified": false,
  "created_at": "2026-02-06T00:00:00Z",
  "last_login_at": "2026-02-06T01:00:00Z",
  "settings": {
    "daily_goal": 10,
    "theme": "light",
    "language": "zh"
  }
}
```

**错误响应:**
- 401: 未认证
- 404: 用户不存在

**实现要点:**
- 使用认证中间件从 token 获取 user_id
- 查询 User 和 UserSettings（如果存在）
- 返回用户信息

#### 1.1.4 PUT /auth/settings

**功能:** 更新用户配置

**请求头:**
```
Authorization: Bearer <access_token>
```

**请求:**
```json
{
  "daily_goal": 15,
  "theme": "dark",
  "language": "en"
}
```

**响应 (200 OK):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "username": "testuser",
  "settings": {
    "daily_goal": 15,
    "theme": "dark",
    "language": "en"
  }
}
```

**实现要点:**
- 验证用户权限
- 更新 User.settings 字段（JSONB）
- 返回更新后的用户信息

#### 1.1.5 POST /auth/refresh

**功能:** 刷新访问令牌

**请求:**
```json
{
  "refresh_token": "eyJ..."
}
```

**响应 (200 OK):**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**实现要点:**
- 验证 refresh_token
- 检查 Session 是否有效
- 生成新的 access_token
- 可选：生成新的 refresh_token

### 1.2 Inbox 模块 API

**优先级:** P0
**模块:** `src/agent_os/inbox/`

**需求描述:**

实现 InboxItem 的创建、查询和状态管理接口。

#### 1.2.1 POST /inbox/items

**功能:** 创建原始 InboxItem

**请求头:**
```
Authorization: Bearer <access_token>
X-Workspace-ID: <workspace_id>
```

**请求:**
```json
{
  "type": "inbox",
  "title": "原始输入标题",
  "content": "原始输入内容",
  "source_type": "manual",  // manual | wechat | chrome_extension
  "source_meta": {
    "url": "https://...",
    "wechat_sender": "...",
    "thumb": "..."
  }
}
```

**响应 (201 Created):**
```json
{
  "id": "uuid",
  "type": "inbox",
  "title": "原始输入标题",
  "content": "原始输入内容",
  "status": "raw",
  "source_type": "manual",
  "source_meta": {...},
  "created_at": "2026-02-06T00:00:00Z",
  "updated_at": "2026-02-06T00:00:00Z"
}
```

**实现要点:**
- 使用 `create_item()` 函数
- 自动设置 `status = "raw"`
- 保存 source_meta 到 JSONB 字段
- 验证 workspace_id 权限

#### 1.2.2 GET /inbox/items

**功能:** 查询 InboxItem 列表（分页、过滤）

**请求头:**
```
Authorization: Bearer <access_token>
X-Workspace-ID: <workspace_id>
```

**查询参数:**
```
?page=1&limit=20&status=raw&sort=-created_at
```

**响应 (200 OK):**
```json
{
  "items": [
    {
      "id": "uuid",
      "type": "inbox",
      "title": "标题",
      "status": "raw",
      "created_at": "2026-02-06T00:00:00Z"
    }
  ],
  "total": 100,
  "page": 1,
  "limit": 20,
  "pages": 5
}
```

**实现要点:**
- 使用 `list_items()` 函数
- 过滤 `type='inbox'`
- 支持状态过滤 (`status=raw/processed/archived`)
- 支持分页 (`page`, `limit`)
- 支持排序 (`sort=-created_at`)

#### 1.2.3 GET /inbox/items/{id}

**功能:** 获取 InboxItem 详情

**请求头:**
```
Authorization: Bearer <access_token>
X-Workspace-ID: <workspace_id>
```

**响应 (200 OK):**
```json
{
  "id": "uuid",
  "type": "inbox",
  "title": "标题",
  "content": "内容",
  "status": "raw",
  "source_type": "manual",
  "source_meta": {...},
  "created_at": "2026-02-06T00:00:00Z",
  "updated_at": "2026-02-06T00:00:00Z"
}
```

**实现要点:**
- 使用 `get_item()` 函数
- 验证用户有权限访问此 item
- 返回完整 item 信息

#### 1.2.4 PATCH /inbox/items/{id}/status

**功能:** 更新 InboxItem 状态

**请求头:**
```
Authorization: Bearer <access_token>
X-Workspace-ID: <workspace_id>
```

**请求:**
```json
{
  "status": "processed"  // raw | processed | archived
}
```

**响应 (200 OK):**
```json
{
  "id": "uuid",
  "status": "processed",
  "updated_at": "2026-02-06T00:00:00Z"
}
```

**错误响应:**
- 400: 无效的状态值
- 404: Item 不存在
- 403: 无权限

**实现要点:**
- 验证状态值（raw/processed/archived）
- 更新 Item.status 字段
- 记录 updated_at 时间

#### 1.2.5 DELETE /inbox/items/{id}

**功能:** 删除 InboxItem（软删除）

**请求头:**
```
Authorization: Bearer <access_token>
X-Workspace-ID: <workspace_id>
```

**响应 (204 No Content):**

**实现要点:**
- 设置 `status = "deleted"`
- 或使用软删除机制
- 验证用户权限

### 1.3 Today 视图 API

**优先级:** P0
**模块:** `src/agent_os/today/`

**需求描述:**

实现 Today 视图的数据聚合接口，为前端提供用户当前需要关注的信息。

#### 1.3.1 GET /today

**功能:** 获取今日视图数据

**请求头:**
```
Authorization: Bearer <access_token>
X-Workspace-ID: <workspace_id>
```

**查询参数:**
```
?date=2026-02-06  # 可选，默认今天
```

**响应 (200 OK):**
```json
{
  "date": "2026-02-06",
  "inbox_count": 5,
  "inbox_items": [
    {
      "id": "uuid",
      "title": "待处理标题",
      "type": "inbox",
      "status": "raw",
      "created_at": "2026-02-06T09:00:00Z"
    }
  ],
  "active_tasks": [
    {
      "id": "uuid",
      "title": "进行中的任务",
      "status": "executing",
      "priority": 5
    }
  ],
  "upcoming_deadlines": [
    {
      "id": "uuid",
      "title": "即将到期",
      "deadline": "2026-02-07T00:00:00Z"
    }
  ],
  "suggestions": []  // 输出建议（当前为 mock）
}
```

**实现要点:**
- 聚合 InboxItem 中 status='raw' 的数量
- 查询最近的 active tasks
- 查询即将到期的决策点
- 返回 mock 的 suggestions（阶段一不要求真实实现）
- 所有数据按时间排序

### 1.4 Pydantic Schema 定义

**优先级:** P0
**文件:** `src/agent_os/auth/schema.py`, `src/agent_os/inbox/schema.py`, `src/agent_os/today/schema.py`

#### 1.4.1 认证 Schema

**文件:** `src/agent_os/auth/schema.py`

```python
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from uuid import UUID

class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=100)
    full_name: str | None = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    username: str
    full_name: str | None
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: datetime | None

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse

class UserSettingsUpdate(BaseModel):
    daily_goal: int | None = Field(None, ge=1, le=100)
    theme: str | None = "light"
    language: str | None = "zh"
```

#### 1.4.2 Inbox Schema

**文件:** `src/agent_os/inbox/schema.py`

```python
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import Literal, Optional, Dict, Any

class InboxItemCreate(BaseModel):
    type: Literal["inbox"] = "inbox"
    title: str = Field(..., min_length=1, max_length=500)
    content: str
    source_type: Literal["manual", "wechat", "chrome_extension"] = "manual"
    source_meta: Dict[str, Any] = Field(default_factory=dict)

class InboxItemUpdate(BaseModel):
    title: str | None = None
    content: str | None = None

class InboxItemStatusUpdate(BaseModel):
    status: Literal["raw", "processed", "archived", "deleted"]

class InboxItemResponse(BaseModel):
    id: UUID
    type: str
    title: str
    content: str
    status: str
    source_type: str
    source_meta: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

class InboxItemListResponse(BaseModel):
    items: list[InboxItemResponse]
    total: int
    page: int
    limit: int
    pages: int
```

#### 1.4.3 Today Schema

**文件:** `src/agent_os/today/schema.py`

```python
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import List

class TaskSummary(BaseModel):
    id: UUID
    title: str
    status: str
    priority: int

class DeadlineSummary(BaseModel):
    id: UUID
    title: str
    deadline: datetime

class TodayResponse(BaseModel):
    date: str
    inbox_count: int
    inbox_items: List[dict]
    active_tasks: List[TaskSummary]
    upcoming_deadlines: List[DeadlineSummary]
    suggestions: List[dict]
```

### 1.5 CRUD 操作实现

**优先级:** P0
**文件:** `src/agent_os/auth/crud.py`, `src/agent_os/inbox/crud.py`

#### 1.5.1 用户 CRUD

**文件:** `src/agent_os/auth/crud.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from agent_os.auth.models import User
from agent_os.auth.security import get_password_hash, verify_password

async def create_user(
    db: AsyncSession,
    email: str,
    username: str,
    password: str,
    full_name: str = None
) -> User:
    # 检查唯一性
    existing = await db.execute(
        select(User).where(User.email == email)
    )
    if existing.scalar_one_or_none():
        raise ValueError("Email already exists")

    # 创建用户
    user = User(
        email=email,
        username=username,
        password_hash=get_password_hash(password),
        full_name=full_name,
        is_active=True,
        is_verified=False
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 创建默认 workspace
    # ... workspace 创建逻辑

    return user

async def authenticate_user(
    db: AsyncSession,
    username: str,
    password: str
) -> User:
    # 查询用户（支持 email 或 username）
    result = await db.execute(
        select(User).where(
            (User.email == username) | (User.username == username)
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        raise ValueError("Invalid credentials")

    if not user.is_active:
        raise ValueError("User is disabled")

    return user
```

#### 1.5.2 Inbox CRUD

**文件:** `src/agent_os/inbox/crud.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from agent_os.items.models import Item

async def create_inbox_item(
    db: AsyncSession,
    workspace_id: UUID,
    creator_id: UUID,
    title: str,
    content: str,
    source_type: str,
    source_meta: dict
) -> Item:
    item_data = ItemCreate(
        workspace_id=workspace_id,
        creator_id=creator_id,
        type="inbox",
        title=title,
        content=content,
        source_type=source_type,
        source_meta=source_meta,
        status="raw"
    )

    return await create_item(db, item_data)

async def list_inbox_items(
    db: AsyncSession,
    workspace_id: UUID,
    status: str | None = None,
    page: int = 1,
    limit: int = 20
) -> dict:
    # 查询逻辑
    pass

async def update_inbox_item_status(
    db: AsyncSession,
    item_id: UUID,
    user_id: UUID,
    status: str
) -> Item:
    # 更新逻辑
    pass
```

---

## 二、优先级 P1 - 功能完善

**时间估算:** 1-2 天
**目标:** 完善错误处理、验证和文档

### 2.1 认证中间件

**优先级:** P1
**文件:** `src/agent_os/auth/dependencies.py`

**需求描述:**

实现 FastAPI 依赖注入，用于保护需要认证的端点。

```python
from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from agent_os.auth.security import decode_token
from agent_os.auth.models import User
from sqlalchemy import select

async def get_current_user(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
) -> User:
    """从 JWT token 获取当前用户"""

    # 提取 token
    scheme, token = authorization.split()
    if scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme"
        )

    # 解码 token
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    # 获取用户
    user_id = payload.get("sub")
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is disabled"
        )

    return user

# 使用示例
@app.get("/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
```

### 2.2 错误处理和验证

**优先级:** P1

**需求描述:**

实现统一的错误处理和请求验证。

**错误码规范:**
- 400: 请求参数错误
- 401: 未认证
- 403: 无权限
- 404: 资源不存在
- 409: 冲突（如重复注册）
- 422: 验证错误
- 500: 服务器错误

**异常处理示例:**
```python
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

@app.exception_handler(IntegrityError)
async def handle_integrity_error(request, exc):
    if "unique" in str(exc.orig):
        raise HTTPException(
            status_code=409,
            detail="Resource already exists"
        )
    raise HTTPException(status_code=500, detail="Database error")
```

### 2.3 API 文档

**优先级:** P1

**需求描述:**

使用 OpenAPI/Swagger 自动生成 API 文档。

**实现要点:**
- 所有路由添加描述
- 所有 schema 添加 example
- 添加认证说明（使用 FastAPI 的 security 参数）

**示例:**
```python
@router.post("/auth/register", response_model=UserResponse, status_code=201)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """
    用户注册

    - **email**: 用户邮箱（必须唯一）
    - **username**: 用户名（3-100字符）
    - **password**: 密码（最少8字符）

    返回创建的用户信息，包含 id、email、username 等。
    """
    # 实现逻辑
    pass
```

---

## 三、优先级 P2 - 优化和增强

**时间估算:** 1-2 天
**目标:** 性能优化和开发体验提升

### 3.1 性能优化

**优先级:** P2

**需求描述:**

- 添加查询性能优化（索引）
- 实现缓存机制（可选）
- 添加速率限制（防止滥用）

### 3.2 测试增强

**优先级:** P2

**需求描述:**

- 补充 E2E 测试
- 添加性能测试
- 实现代理数据生成

### 3.3 开发工具

**优先级:** P2

**需求描述:**

- API 调试工具
- 数据库迁移脚本
- 开发环境初始化脚本

---

## 四、实施计划

### 4.1 第一周（P0 - 核心功能）

**目标:** 实现所有 P0 需求

| 任务 | 文件 | 测试数 |
|------|------|--------|
| 认证 Schema | `auth/schema.py` | - |
| 认证 CRUD | `auth/crud.py` | - |
| 认证路由 | `auth/router.py` | 8 |
| Inbox Schema | `inbox/schema.py` | - |
| Inbox CRUD | `inbox/crud.py` | - |
| Inbox 路由 | `inbox/router.py` | 10 |
| Today Schema | `today/schema.py` | - |
| Today 路由 | `today/router.py` | 5 |
| **总计** | **8 个文件** | **23 个测试** |

**验收标准:**
- 所有 P0 路由实现并可访问
- 23 个集成测试全部通过
- 手动测试所有 API 端点

### 4.2 第二周（P1 - 完善）

**目标:** 实现所有 P1 需求

| 任务 | 描述 |
|------|------|
| 认证中间件 | `auth/dependencies.py` |
| 错误处理 | 统一异常处理 |
| API 文档 | OpenAPI/Swagger |
| 完善测试 | 补充边界测试 |

**验收标准:**
- 中间件正常工作
- 错误处理完善
- API 文档可访问

### 4.3 第三周（P2 - 优化）

**目标:** 性能优化和收尾

| 任务 | 描述 |
|------|------|
| 性能优化 | 查询优化、缓存 |
| 测试增强 | E2E、性能测试 |
| 文档完善 | 部署文档、使用指南 |

---

## 五、技术规范

### 5.1 代码规范

**文件命名:**
- 路由文件: `{module}/router.py`
- CRUD 文件: `{module}/crud.py`
- Schema 文件: `{module}/schema.py`

**代码组织:**
- 路由只处理 HTTP 请求/响应
- 业务逻辑在 CRUD 层
- 数据验证在 Schema 层

### 5.2 测试规范

**测试文件命名:** `tests/test_{module}_integration.py`

**测试覆盖要求:**
- 每个路由至少 2 个测试
- 包含正常和异常场景
- 验证权限和边界条件

### 5.3 文档规范

**API 文档:**
- 使用 OpenAPI/Swagger 自动生成
- 包含请求/响应示例
- 标注认证方式

**代码文档:**
- 所有公开函数添加 docstring
- 复杂逻辑添加注释

---

## 六、成功标准

### 6.1 功能完整性

- ✅ 所有 P0 API 端点实现
- ✅ 认证中间件正常工作
- ✅ Inbox → Today 信息流打通
- ✅ 用户数据隔离有效

### 6.2 测试完整性

- ✅ 所有新增功能有测试覆盖
- ✅ 测试通过率 100%
- ✅ 包含边界和异常测试

### 6.3 文档完整性

- ✅ API 文档可访问
- ✅ 部署文档完整
- ✅ 使用指南清晰

### 6.4 质量标准

- ✅ 代码符合 PEP 8 规范
- ✅ 类型提示完整
- ✅ 错误处理完善
- ✅ 性能满足验收要求

---

## 七、风险和缓解

### 7.1 技术风险

**风险:** SQLAlchemy 异步查询复杂度
**缓解:** 提供清晰的 CRUD 示例和文档

**风险:** JWT 令牌管理
**缓解:** 使用 Session 模型跟踪活跃令牌

### 7.2 进度风险

**风险:** 估算时间不足
**缓解:**
- P0 功能优先
- P1/P2 可延后
- 分阶段交付

### 7.3 兼容性风险

**风险:** 与现有模型不兼容
**缓解:**
- 复用现有 Item CRUD
- 扩展而非修改

---

## 八、附录

### A. 当前已有基础

**可复用的组件:**
- ✅ User 模型（auth/models.py）
- ✅ JWT 安全工具（auth/security.py）
- ✅ Item CRUD（items/crud.py）
- ✅ 测试框架（tests/conftest.py）

**需要创建的组件:**
- ❌ API 路由
- ❌ Pydantic schema
- ❌ CRUD 操作
- ❌ 认证中间件

### B. 依赖清单

**新增依赖:**
- 无（使用现有依赖）

**现有相关依赖:**
- fastapi
- sqlalchemy
- pydantic
- pyjwt
- passlib
- python-jose

### C. 参考资料

- PA 1.0 阶段一验收标准
- PRD4 文档
- FastAPI 官方文档
- SQLAlchemy 异步教程

---

**文档版本:** 1.0
**最后更新:** 2026-02-06
**下次审查:** P0 实现完成后
