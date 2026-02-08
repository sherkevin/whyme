# 功能-测试映射文档

**最后更新**: 2026-01-28
**目的**: 说明每个功能对应的测试文件，用于验证功能完整性

---

## 📊 测试覆盖概览

```
总测试数: 456
核心模块测试: 260
其他测试: 196
```

---

## 🔐 认证系统 (Auth System)

### API 端点
- `POST /api/v1/auth/register` - 用户注册
- `POST /api/v1/auth/login` - 用户登录（用户名/邮箱）
- `POST /api/v1/auth/refresh` - 刷新访问令牌
- `GET /api/v1/auth/me` - 获取当前用户信息
- `PUT /api/v1/auth/settings` - 更新用户设置

### 测试文件映射

| 功能 | 测试文件 | 测试数 | 状态 | 测试命令 |
|------|---------|-------|------|---------|
| **Schema 验证** | `tests/test_auth_schema.py` | 21 | ✅ | `pytest tests/test_auth_schema.py -v` |
| - UserRegister 验证 | | 7 | ✅ | |
| - UserInfo 验证 | | 6 | ✅ | |
| - Token 验证 | | 4 | ✅ | |
| - UserSettingsUpdate 验证 | | 4 | ✅ | |
| **CRUD 操作** | `tests/test_auth_crud.py` | 14 | ✅ | `pytest tests/test_auth_crud.py -v` |
| - 创建用户 | | 3 | ✅ | |
| - 查询用户 | | 3 | ✅ | |
| - 认证用户 | | 4 | ✅ | |
| - 更新用户 | | 4 | ✅ | |
| **JWT 功能** | `tests/test_auth_jwt.py` | 20 | ✅ | `pytest tests/test_auth_jwt.py -v` |
| - Token 创建 | | 5 | ✅ | |
| - Token 验证 | | 5 | ✅ | |
| - Token 刷新 | | 4 | ✅ | |
| - 过期处理 | | 3 | ✅ | |
| - 其他 JWT 功能 | | 3 | ✅ | |
| **密码安全** | `tests/test_auth_security.py` | 7 | ✅ | `pytest tests/test_auth_security.py -v` |
| - 密码哈希 | | 3 | ✅ | |
| - 密码验证 | | 4 | ✅ | |
| **API 集成** | `tests/test_api_integration_auth.py` | 18 | ✅ | `pytest tests/test_api_integration_auth.py -v` |
| - 注册流程 | | 4 | ✅ | |
| - 登录流程（用户名） | | 4 | ✅ | |
| - 登录流程（邮箱） | | 4 | ✅ | |
| - Token 刷新 | | 3 | ✅ | |
| - 获取用户信息 | | 2 | ✅ | |
| - 更新设置 | | 1 | ✅ | |

**总计**: 75 个测试，状态: ✅ 100% 通过

---

## 🧠 知识管理系统 (Knowledge System)

### API 端点
- `POST /api/v1/knowledge/inbox` - 创建收件项
- `GET /api/v1/knowledge/inbox` - 查询收件项
- `GET /api/v1/knowledge/inbox/{id}` - 获取单个收件项
- `PUT /api/v1/knowledge/inbox/{id}` - 更新收件项
- `PATCH /api/v1/knowledge/inbox/{id}/status` - 更新状态
- `DELETE /api/v1/knowledge/inbox/{id}` - 删除收件项
- `POST /api/v1/knowledge/cards` - 创建卡片
- `GET /api/v1/knowledge/cards` - 查询卡片
- `GET /api/v1/knowledge/cards/{id}` - 获取单个卡片
- `PUT /api/v1/knowledge/cards/{id}` - 更新卡片
- `DELETE /api/v1/knowledge/cards/{id}` - 删除卡片
- `POST /api/v1/knowledge/cards/search` - 向量搜索
- `GET /api/v1/knowledge/cards/{id}/similar` - 查找相似卡片

### 测试文件映射

| 功能 | 测试文件 | 测试数 | 状态 | 测试命令 |
|------|---------|-------|------|---------|
| **Schema 验证** | `tests/test_knowledge_schema.py` | 27 | ✅ | `pytest tests/test_knowledge_schema.py -v` |
| - InboxItemCreate | | 7 | ✅ | |
| - InboxItemUpdate | | 5 | ✅ | |
| - CardCreate | | 6 | ✅ | |
| - CardUpdate | | 5 | ✅ | |
| - VectorSearchRequest | | 4 | ✅ | |
| **CRUD 操作** | `tests/test_knowledge_crud.py` | 26 | ✅ | `pytest tests/test_knowledge_crud.py -v` |
| - Inbox CRUD | | 13 | ✅ | |
| - Card CRUD | | 13 | ✅ | |
| **向量搜索** | `tests/test_vector_search.py` | 22 | ✅ | `pytest tests/test_vector_search.py -v` |
| - 嵌入服务 | | 9 | ✅ | |
| - 卡片/收件箱嵌入 | | 3 | ✅ | |
| - 向量搜索 Schema | | 7 | ✅ | |
| - 单元测试 | | 3 | ✅ | |
| **API 集成** | `tests/test_api_integration_knowledge.py` | 29 | ✅ | `pytest tests/test_api_integration_knowledge.py -v` |
| - Inbox API | | 13 | ✅ | |
| - Card API | | 10 | ✅ | |
| - 向量搜索 API | | 6 | ✅ | |

**总计**: 104 个测试，状态: ✅ 100% 通过

**修复记录**: 2026-01-28 修复了异步调用问题（从同步 session 迁移到异步 AsyncSession）

---

## ✅ 任务管理系统 (Task System)

### API 端点
- `POST /api/v1/tasks` - 创建任务
- `GET /api/v1/tasks/{task_id}` - 获取单个任务
- `GET /api/v1/tasks` - 查询任务列表（支持过滤、分页、排序）
- `PUT /api/v1/tasks/{task_id}` - 更新任务
- `PATCH /api/v1/tasks/{task_id}/status` - 更新任务状态
- `DELETE /api/v1/tasks/{task_id}` - 删除任务
- `GET /api/v1/tasks/today` - 获取今日任务
- `GET /api/v1/tasks/stats` - 获取任务统计
- `POST /api/v1/tasks/batch` - 批量创建任务
- `PUT /api/v1/tasks/batch` - 批量更新任务
- `DELETE /api/v1/tasks/batch` - 批量删除任务

### 测试文件映射

| 功能 | 测试文件 | 测试数 | 状态 | 测试命令 |
|------|---------|-------|------|---------|
| **Schema 验证** | `tests/test_tasks_schema.py` | 34 | ✅ | `pytest tests/test_tasks_schema.py -v` |
| - TaskCreate | | 12 | ✅ | |
| - TaskUpdate | | 6 | ✅ | |
| - TaskResponse | | 1 | ✅ | |
| - TaskList/Stats | | 4 | ✅ | |
| - BatchCreate/Update | | 4 | ✅ | |
| - QueryParams | | 7 | ✅ | |
| **CRUD 操作** | `tests/test_tasks_crud.py` | 26 | ✅ | `pytest tests/test_tasks_crud.py -v` |
| - 创建任务 | | 3 | ✅ | |
| - 查询任务 | | 10 | ✅ | |
| - 更新任务 | | 2 | ✅ | |
| - 删除任务 | | 2 | ✅ | |
| - 今日任务 | | 2 | ✅ | |
| - 任务统计 | | 2 | ✅ | |
| - 批量操作 | | 5 | ✅ | |
| **API 集成** | `tests/test_api_integration_tasks.py` | 21 | ✅ | `pytest tests/test_api_integration_tasks.py -v` |
| - 创建任务 | | 2 | ✅ | |
| - 查询任务 | | 8 | ✅ | |
| - 更新任务 | | 3 | ✅ | |
| - 删除任务 | | 1 | ✅ | |
| - 批量操作 | | 4 | ✅ | |
| - 今日聚合 | | 3 | ✅ | |

**总计**: 81 个测试，状态: ✅ 100% 通过

---

## 🚧 其他模块

### RAG 接口
| 功能 | 测试文件 | 测试数 | 状态 | 测试命令 |
|------|---------|-------|------|---------|
| **RAG 接口** | `tests/test_rag_interface.py` | 12 | ✅ | `pytest tests/test_rag_interface.py -v` |
| - RAGProvider 抽象 | | 4 | ✅ | |
| - MockRAGProvider | | 4 | ✅ | |
| - CardRAGProvider | | 4 | ✅ | |

### 数据模型
| 功能 | 测试文件 | 测试数 | 状态 | 测试命令 |
|------|---------|-------|------|---------|
| **模型测试** | `tests/test_models.py` | 24 | ✅ | `pytest tests/test_models.py -v` |
| - User 模型 | | 6 | ✅ | |
| - UserSettings 模型 | | 4 | ✅ | |
| - InboxItem 模型 | | 4 | ✅ | |
| - Card 模型 | | 4 | ✅ | |
| - Task 模型 | | 6 | ✅ | |

---

## ⚠️ 需要修复的测试

### ✅ 已修复

#### 1. Knowledge CRUD 测试 (26 个测试) ✅

**文件**: `tests/test_knowledge_crud.py`
**状态**: ✅ 已修复（2026-01-28）
**修复内容**:
- 将同步 session 迁移到异步 AsyncSession
- 修正参数名（`db_obj` 而不是 `db_item`/`db_card`）
- 修正 source 值匹配 schema 约束
- 添加缺失的必需字段（`para_type`）

**测试结果**: 26/26 通过 ✅

---

## 📋 测试运行命令

### 运行所有核心模块测试
```bash
# 认证系统
pytest tests/test_auth_*.py tests/test_api_integration_auth.py -v

# 知识管理
pytest tests/test_knowledge_*.py tests/test_vector_search.py tests/test_api_integration_knowledge.py -v

# 任务管理
pytest tests/test_tasks_*.py tests/test_api_integration_tasks.py -v
```

### 运行单个模块测试
```bash
# Auth
pytest tests/test_auth_schema.py -v
pytest tests/test_auth_crud.py -v
pytest tests/test_auth_jwt.py -v
pytest tests/test_auth_security.py -v
pytest tests/test_api_integration_auth.py -v

# Knowledge
pytest tests/test_knowledge_schema.py -v
pytest tests/test_knowledge_crud.py -v
pytest tests/test_vector_search.py -v
pytest tests/test_api_integration_knowledge.py -v

# Tasks
pytest tests/test_tasks_schema.py -v
pytest tests/test_tasks_crud.py -v
pytest tests/test_api_integration_tasks.py -v
```

### 运行特定测试
```bash
# 运行特定测试类
pytest tests/test_auth_schema.py::TestUserRegister -v

# 运行特定测试方法
pytest tests/test_auth_schema.py::TestUserRegister::test_user_create_valid -v

# 运行并显示详细输出
pytest tests/test_auth_schema.py -v -s
```

---

## 📊 测试通过率统计

| 模块 | 测试数 | 通过 | 失败 | 通过率 |
|------|-------|------|------|--------|
| 认证系统 | 75 | 75 | 0 | 100% ✅ |
| 知识管理 | 104 | 104 | 0 | 100% ✅ |
| 任务管理 | 81 | 81 | 0 | 100% ✅ |
| RAG 接口 | 12 | 12 | 0 | 100% ✅ |
| 数据模型 | 24 | 24 | 0 | 100% ✅ |
| **核心总计** | **296** | **296** | **0** | **100%** ✅ |

**说明**: 所有核心模块测试全部通过 ✨

---

## 🎯 下一步行动

1. ✅ **已修复**: Task 模块批量操作路由顺序问题
2. ✅ **已修复**: Knowledge CRUD 测试（异步调用问题）
3. ✅ **完成**: Auth 模块（100% 通过）
4. ✅ **完成**: Knowledge 模块（100% 通过）
5. ✅ **完成**: Task 模块（100% 通过）

**核心功能测试状态**: ✅ 全部通过！

---

**维护者**: AgentOS 开发团队
**最后更新**: 2026-01-28
**文档版本**: v1.0
