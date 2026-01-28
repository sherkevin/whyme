# 后端功能缺失详细清单

**项目**: AgentOS Core vs 后端开发任务需求
**分析日期**: 2026-01-27

---

## 📊 功能对比矩阵

### 1. 工程 & 数据基础

| 功能点 | 后端需求 | AgentOS Core | 差距 | 实现状态 |
|--------|---------|--------------|------|----------|
| 项目结构 | 分层结构 | ✅ 完整分层架构 | 无 | ✅ 已实现 |
| 环境配置 | .env + 启动脚本 | ✅ .env + scripts/ | 无 | ✅ 已实现 |
| 数据库 | PostgreSQL + Alembic | ⚠️ JSON/Vector 存储 | **架构不同** | ⚠️ 需适配 |
| 基础表 | User/UserSettings | ⚠️ SessionManager | **不同概念** | ⚠️ 需重建 |

**总结**: 基础设施完善，但数据层架构完全不同。

---

### 2. 鉴权 & 用户系统

| 功能点 | 后端需求 | AgentOS Core | 差距 | 实现状态 |
|--------|---------|--------------|------|----------|
| 登录接口 | POST /auth/login | ❌ 不存在 | **完全缺失** | ❌ 需新建 |
| JWT 鉴权 | 中间件 | ⚠️ auth.py 框架 | **需补充** | ⚠️ 部分实现 |
| 用户信息 | GET /user/me | ❌ 不存在 | **完全缺失** | ❌ 需新建 |
| 用户设置 | PUT /user/settings | ❌ 不存在 | **完全缺失** | ❌ 需新建 |

**总结**: 鉴权系统几乎空白，需要从零开发。

---

### 3. Inbox & Knowledge 系统

| 功能点 | 后端需求 | AgentOS Core | 差距 | 实现状态 |
|--------|---------|--------------|------|----------|
| 收件箱表 | InboxItem (raw/processed) | ❌ 不存在 | **完全缺失** | ❌ 需新建 |
| 添加收件 | POST /inbox | ❌ 不存在 | **完全缺失** | ❌ 需新建 |
| 查询收件 | GET /inbox?status= | ❌ 不存在 | **完全缺失** | ❌ 需新建 |
| 卡片表 | Card (最小字段) | ❌ 不存在 | **完全缺失** | ❌ 需新建 |
| 创建卡片 | POST /cards | ❌ 不存在 | **完全缺失** | ❌ 需新建 |
| 查询卡片 | GET /cards?para_type= | ❌ 不存在 | **完全缺失** | ❌ 需新建 |

**总结**: Inbox 和 Card 系统完全缺失，属于新功能领域。

---

### 4. Task & Today 聚合

| 功能点 | 后端需求 | AgentOS Core | 差距 | 实现状态 |
|--------|---------|--------------|------|----------|
| 任务表 | Task (type/source/status) | ❌ 不存在 | **完全缺失** | ❌ 需新建 |
| 创建任务 | POST /tasks | ❌ 不存在 | **完全缺失** | ❌ 需新建 |
| 今日任务 | GET /tasks?date=today | ❌ 不存在 | **完全缺失** | ❌ 需新建 |
| 聚合接口 | GET /today | ❌ 不存在 | **完全缺失** | ❌ 需新建 |
| 产品对齐 | JSON 格式定义 | ❌ 不存在 | **完全缺失** | ❌ 需新建 |

**总结**: 任务管理系统完全缺失，属于新功能领域。

---

## 🔴 完全缺失的功能（16 项）

### 用户系统（4 项）

1. **POST /auth/login**
   - 需求：用户登录接口
   - 当前状态：❌ 不存在
   - 实现难度：⭐⭐
   - 工作量：1-2 天

2. **JWT 中间件**
   - 需求：Token 验证
   - 当前状态：⚠️ 有框架无实现
   - 实现难度：⭐⭐⭐
   - 工作量：2-3 天

3. **GET /user/me**
   - 需求：获取用户信息
   - 当前状态：❌ 不存在
   - 实现难度：⭐
   - 工作量：0.5-1 天

4. **PUT /user/settings**
   - 需求：更新用户设置
   - 当前状态：❌ 不存在
   - 实现难度：⭐⭐
   - 工作量：1-2 天

**小计**: 4.5-8 天

---

### Inbox 系统（3 项）

5. **InboxItem 数据模型**
   - 需求：收件箱表结构
   - 当前状态：❌ 不存在
   - 实现难度：⭐⭐
   - 工作量：1-2 天

6. **POST /inbox**
   - 需求：添加收件项
   - 当前状态：❌ 不存在
   - 实现难度：⭐⭐⭐
   - 工作量：1-2 天

7. **GET /inbox?status=**
   - 需求：查询收件项
   - 当前状态：❌ 不存在
   - 实现难度：⭐⭐
   - 工作量：1 天

**小计**: 3-5 天

---

### Card 系统（3 项）

8. **Card 数据模型**
   - 需求：卡片表结构
   - 当前状态：❌ 不存在
   - 实现难度：⭐⭐
   - 工作量：1-2 天

9. **POST /cards**
   - 需求：创建卡片
   - 当前状态：❌ 不存在
   - 实现难度：⭐⭐
   - 工作量：1-2 天

10. **GET /cards?para_type=**
    - 需求：查询卡片
    - 当前状态：❌ 不存在
    - 实现难度：⭐⭐
    - 工作量：1 天

**小计**: 3-5 天

---

### Task 系统（5 项）

11. **Task 数据模型**
    - 需求：任务表结构
    - 当前状态：❌ 不存在
    - 实现难度：⭐⭐
    - 工作量：1-2 天

12. **POST /tasks**
    - 需求：创建任务
    - 当前状态：❌ 不存在
    - 实现难度：⭐⭐⭐
    - 工作量：1-2 天

13. **GET /tasks?date=today**
    - 需求：查询今日任务
    - 当前状态：❌ 不存在
    - 实现难度：⭐⭐
    - 工作量：1 天

14. **GET /today（聚合接口）**
    - 需求：今日聚合数据
    - 当前状态：❌ 不存在
    - 实现难度：⭐⭐⭐⭐
    - 工作量：2-3 天

15. **产品定义对齐**
    - 需求：JSON 格式规范
    - 当前状态：❌ 不存在
    - 实现难度：⭐⭐
    - 工作量：1 天

**小计**: 6-10 天

---

### 数据层（1 项）

16. **PostgreSQL + Alembic**
    - 需求：关系型数据库
    - 当前状态：⚠️ JSON/Vector 存储
    - 实现难度：⭐⭐⭐
    - 工作量：2-3 天

**小计**: 2-3 天

---

## 📈 总工作量估算

### 最小实现（MVP）

```
数据层: 2-3 天
用户系统: 4-5 天
Inbox 系统: 3-5 天
Card 系统: 3-5 天
Task 系统: 6-10 天

总计: 18-28 天
平均: 23 天
```

### 快速实现（使用 AgentOS Core 基础）

```
复用工程基础: -3 天
复用 API 框架: -2 天
复用 WebSocket: -1 天

总计: 12-22 天
平均: 17 天
```

**节省时间**: 25-30%

---

## 🎯 推荐实现路线图

### Week 1: 数据层 + 用户系统

**Day 1-3**: 数据层
- 安装 PostgreSQL + Alembic
- 创建数据模型
- 配置数据库连接

**Day 4-5**: 用户系统基础
- POST /auth/login
- JWT 中间件

**Day 6-7**: 用户系统完善
- GET /user/me
- PUT /user/settings

### Week 2: Inbox + Card 系统

**Day 8-10**: Inbox 系统
- InboxItem 模型
- POST /inbox
- GET /inbox

**Day 11-13**: Card 系统
- Card 模型
- POST /cards
- GET /cards

**Day 14**: 测试和修复

### Week 3: Task 系统

**Day 15-17**: Task 基础
- Task 模型
- POST /tasks
- GET /tasks

**Day 18-20**: 聚合接口
- GET /today
- JSON 格式对齐

**Day 21**: 集成测试

---

## 🛠️ 技术实现建议

### 1. 数据库选型

**推荐**: PostgreSQL + SQLAlchemy + Alembic

**理由**:
- ✅ 成熟稳定
- ✅ 类型安全
- ✅ 迁移友好
- ✅ 团队熟悉

### 2. API 设计

**推荐**: RESTful + JWT

**端点设计**:
```python
# 用户系统
POST   /auth/login
GET    /user/me
PUT    /user/settings

# Inbox 系统
POST   /inbox
GET    /inbox?status={raw|processed}
PUT    /inbox/:id
DELETE /inbox/:id

# Card 系统
POST   /cards
GET    /cards?para_type={type}
PUT    /cards/:id
DELETE /cards/:id

# Task 系统
POST   /tasks
GET    /tasks?date=today
PUT    /tasks/:id
DELETE /tasks/:id

# 聚合接口
GET    /today
```

### 3. 数据模型

```python
# User 表
class User(Base):
    id: int
    username: str
    email: str
    hashed_password: str
    created_at: datetime

# UserSettings 表
class UserSettings(Base):
    id: int
    user_id: int
    daily_goal: int  # 节奏/KPI
    theme: str
    created_at: datetime

# InboxItem 表
class InboxItem(Base):
    id: int
    user_id: int
    content: str
    status: str  # raw/processed
    source: str
    created_at: datetime

# Card 表
class Card(Base):
    id: int
    user_id: int
    title: str
    content: str
    para_type: str  # 卡片类型
    created_at: datetime

# Task 表
class Task(Base):
    id: int
    user_id: int
    title: str
    type: str
    source: str
    status: str  # pending/in_progress/completed
    scheduled_date: date
    created_at: datetime
```

---

## 🎊 总结

### 关键结论

1. **功能差异巨大**
   - 后端需求：知识管理 + 任务管理
   - AgentOS Core：AI 编程助手
   - **重叠度 < 25%**

2. **需要大量新开发**
   - 16 项功能完全缺失
   - 预计 18-28 天（最小实现）

3. **推荐基于 AgentOS Core 扩展**
   - 复用工程基础（省 3 天）
   - 获得额外 AI 能力
   - 统一技术栈

### 下一步行动

**选项 A**: 扩展 AgentOS Core（推荐）
- 工作量：17-23 天
- 优势：获得 AI 能力
- 适合：需要 AI 的场景

**选项 B**: 独立开发新后端
- 工作量：18-28 天
- 优势：架构简单
- 适合：纯后端需求

**建议**: 确认产品边界后立即开始开发！