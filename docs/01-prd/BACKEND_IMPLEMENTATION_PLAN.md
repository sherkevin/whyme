# 后端系统实现方案 A - 解耦架构设计

**日期**: 2026-01-27
**方案**: 扩展 AgentOS Core，知识管理与Agent解耦
**用户规模**: 1000 用户
**关键需求**: AI能力 + 实时通信 + RAG融合

---

## 🎯 架构设计原则

### 核心理念

```
┌─────────────────────────────────────────────────┐
│           AgentOS Core (AI 编程助手)              │
├─────────────────────────────────────────────────┤
│  • WebSocket 实时通信                            │
│  • LLM 集成 (LiteLLM)                            │
│  • Aider 编程能力                                │
│  • 向量数据库 (Mem0)                             │
└─────────────────────────────────────────────────┘
                      ↕
              ┌───────────────┐
              │  RAG 接口层    │
              │ (抽象层)       │
              └───────────────┘
                      ↕
┌─────────────────────────────────────────────────┐
│       知识管理 & 任务系统 (新模块)                │
├─────────────────────────────────────────────────┤
│  • 用户系统 (JWT + PostgreSQL)                   │
│  • Inbox (收件箱)                                │
│  • Card (知识卡片)                               │
│  • Task (任务管理)                               │
└─────────────────────────────────────────────────┘
```

### 关键设计决策

1. **解耦**: 知识管理独立于Agent，可单独运行
2. **RAG接口**: 预留标准接口供Agent访问知识库
3. **用户隔离**: 1000用户的数据隔离
4. **渐进融合**: 先独立实现，后RAG集成

---

## 📋 数据库设计

### 用户系统表

```sql
-- 用户表
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 用户设置表
CREATE TABLE user_settings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    daily_goal INTEGER DEFAULT 10,  -- 每日目标（节奏/KPI）
    theme VARCHAR(20) DEFAULT 'light',  -- 主题
    language VARCHAR(10) DEFAULT 'zh',  -- 语言
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id)
);
```

### 知识管理表

```sql
-- 收件箱表
CREATE TABLE inbox_items (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'raw',  -- raw, processed, archived
    source VARCHAR(50),  -- manual, api, import
    metadata JSONB DEFAULT '{}',  -- 额外元数据
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_user_status (user_id, status)
);

-- 知识卡片表
CREATE TABLE cards (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    para_type VARCHAR(50),  -- 卡片类型：concept, action, reference
    tags TEXT[],  -- 标签数组
    source_inbox_item INTEGER REFERENCES inbox_items(id),  -- 来源收件项
    embedding VECTOR(384),  -- 向量嵌入（用于RAG）
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_user_type (user_id, para_type),
    INDEX idx_tags (tags)
);
```

### 任务管理表

```sql
-- 任务表
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    type VARCHAR(50),  -- task, habit, goal
    source VARCHAR(50),  -- manual, ai_generated, recurring
    status VARCHAR(20) DEFAULT 'pending',  -- pending, in_progress, completed
    priority INTEGER DEFAULT 5,  -- 1-10
    scheduled_date DATE,  -- 计划日期
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_user_date (user_id, scheduled_date),
    INDEX idx_status (status)
);
```

---

## 🏗️ 模块结构设计

### 目录结构

```
src/agent_os/
├── core/                 # 核心接口（已存在）
├── llm/                  # LLM集成（已存在）
├── memory/               # 记忆系统（已存在）
├── knowledge/             # 🆕 知识管理模块
│   ├── __init__.py
│   ├── models.py         # SQLAlchemy 模型
│   ├── schema.py         # Pydantic Schema
│   ├── crud.py           # CRUD 操作
│   └── rag_interface.py  # RAG 接口层
├── tasks/                # 🆕 任务管理模块
│   ├── __init__.py
│   ├── models.py
│   ├── schema.py
│   ├── crud.py
│   └── aggregation.py    # 聚合接口
├── auth/                 # 🆕 认证模块
│   ├── __init__.py
│   ├── models.py
│   ├── jwt_handler.py    # JWT 处理
│   └── dependencies.py   # FastAPI 依赖
├── server/               # FastAPI 服务器（已存在）
│   ├── app.py            # 🔄 添加新路由
│   └── dependencies/     # 🆕 数据库依赖
└── db/                   # 🆕 数据库模块
    ├── __init__.py
    ├── base.py           # Base 类
    ├── session.py        # 数据库会话
    └── migrations/       # Alembic 迁移
```

---

## 🔄 RAG 接口设计

### 抽象接口

```python
# knowledge/rag_interface.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class RAGProvider(ABC):
    """RAG 提供者抽象接口"""

    @abstractmethod
    async def search_knowledge(
        self,
        user_id: int,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """搜索知识库

        Args:
            user_id: 用户ID
            query: 搜索查询
            limit: 返回数量限制

        Returns:
            知识卡片列表，按相关性排序
        """
        pass

    @abstractmethod
    async def add_knowledge(
        self,
        user_id: int,
        content: str,
        metadata: Dict[str, Any]
    ) -> int:
        """添加知识到库

        Args:
            user_id: 用户ID
            content: 知识内容
            metadata: 元数据

        Returns:
            知识ID
        """
        pass

    @abstractmethod
    async def get_context(
        self,
        user_id: int,
        task_id: int
    ) -> str:
        """获取任务的上下文知识

        Args:
            user_id: 用户ID
            task_id: 任务ID

        Returns:
            格式化的上下文字符串
        """
        pass
```

### CardRAGProvider 实现

```python
# knowledge/rag_provider.py
class CardRAGProvider(RAGProvider):
    """基于 Card 的 RAG 提供"""

    def __init__(self, db_session, embedding_model):
        self.db = db_session
        self.embedding_model = embedding_model

    async def search_knowledge(
        self,
        user_id: int,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        # 1. 生成查询向量
        query_embedding = await self.embedding_model.embed(query)

        # 2. 向量搜索（使用 pgvector）
        sql = """
            SELECT id, title, content, para_type,
                   1 - (embedding <=> :query_vec) as similarity
            FROM cards
            WHERE user_id = :user_id
            ORDER BY embedding <=> :query_vec
            LIMIT :limit
        """

        # 3. 返回结果
        return await self.db.fetch_all(sql, {
            "user_id": user_id,
            "query_vec": query_embedding,
            "limit": limit
        })
```

---

## 🚀 实现阶段

### Week 1: 数据层 + 用户系统

**Day 1-2: 环境准备**
- [ ] 安装 PostgreSQL
- [ ] 安装 Alembic
- [ ] 配置数据库连接
- [ ] 创建基础表结构

**Day 3-4: 用户模型**
- [ ] User 模型
- [ ] UserSettings 模型
- [ ] 数据库迁移脚本

**Day 5-7: 认证系统**
- [ ] POST /auth/login
- [ ] JWT 中间件
- [ ] GET /user/me
- [ ] PUT /user/settings

### Week 2: 知识管理模块

**Day 8-10: Inbox 系统**
- [ ] InboxItem 模型
- [ ] POST /inbox
- [ ] GET /inbox?status=
- [ ] RAG 接口初步

**Day 11-14: Card 系统**
- [ ] Card 模型
- [ ] POST /cards
- [ ] GET /cards?para_type=
- [ ] 向量嵌入生成
- [ ] RAG 搜索接口

### Week 3: 任务管理模块

**Day 15-17: Task 基础**
- [ ] Task 模型
- [ ] POST /tasks
- [ ] GET /tasks?date=today
- [ ] 任务状态管理

**Day 18-21: 聚合与集成**
- [ ] GET /today（聚合接口）
- [ ] RAG 上下文注入
- [ ] Agent 集成测试
- [ ] 性能优化

---

## 📡 API 端点设计

### 认证相关

```python
# 登录
POST   /api/v1/auth/login
Body: {"username": "...", "password": "..."}
Response: {"access_token": "...", "token_type": "bearer"}

# 获取当前用户
GET    /api/v1/users/me
Headers: Authorization: Bearer {token}
Response: {"id": 1, "username": "...", "email": "..."}

# 更新设置
PUT    /api/v1/users/settings
Headers: Authorization: Bearer {token}
Body: {"daily_goal": 15, "theme": "dark"}
Response: {"daily_goal": 15, "theme": "dark"}
```

### Inbox 相关

```python
# 添加收件项
POST   /api/v1/inbox
Headers: Authorization: Bearer {token}
Body: {"content": "...", "source": "manual"}
Response: {"id": 1, "status": "raw"}

# 查询收件项
GET    /api/v1/inbox?status=raw&limit=20
Headers: Authorization: Bearer {token}
Response: {"items": [...], "total": 42}

# 处理收件项
POST   /api/v1/inbox/{id}/process
Headers: Authorization: Bearer {token}
Response: {"card_id": 5}
```

### Card 相关

```python
# 创建卡片
POST   /api/v1/cards
Headers: Authorization: Bearer {token}
Body: {"title": "...", "content": "...", "para_type": "concept"}
Response: {"id": 1, "embedding_status": "generated"}

# 查询卡片
GET    /api/v1/cards?para_type=concept&tags=python
Headers: Authorization: Bearer {token}
Response: {"cards": [...], "total": 15}
```

### Task 相关

```python
# 创建任务
POST   /api/v1/tasks
Headers: Authorization: Bearer {token}
Body: {"title": "...", "type": "task", "scheduled_date": "2026-01-27"}
Response: {"id": 1, "status": "pending"}

# 今日任务
GET    /api/v1/tasks?date=today
Headers: Authorization: Bearer {token}
Response: {"tasks": [...], "total": 8}

# 更新任务状态
PUT    /api/v1/tasks/{id}/status
Headers: Authorization: Bearer {token}
Body: {"status": "completed"}
Response: {"status": "completed"}
```

### 聚合接口

```python
# 今日聚合（对齐产品定义）
GET    /api/v1/today
Headers: Authorization: Bearer {token}
Response: {
    "inbox_summary": {"raw": 5, "processed": 12},
    "knowledge_stats": {"total_cards": 42, "today_added": 3},
    "tasks": {
        "total": 8,
        "completed": 3,
        "pending": 5,
        "progress_rate": 0.375
    },
    "ai_suggestions": [...],  # Agent 建议
    "rag_context": "..."  # RAG 注入的上下文
}
```

---

## 🔌 Agent 融合接口

### RAG 知识注入

```python
# Agent 使用知识库的流程

async def agent_with_rag(user_query: str, user_id: int):
    # 1. 通过 RAG 接口搜索相关知识
    rag_provider = CardRAGProvider(db, embedding_model)
    knowledge = await rag_provider.search_knowledge(
        user_id=user_id,
        query=user_query,
        limit=5
    )

    # 2. 构建增强的 prompt
    context = "\n".join([k["content"] for k in knowledge])
    enhanced_prompt = f"""
    用户问题：{user_query}

    相关知识：
    {context}

    请基于以上知识回答用户问题。
    """

    # 3. 调用 LLM
    response = await llm.generate(enhanced_prompt)

    return response
```

---

## 📊 性能考虑（1000 用户）

### 数据库优化

```python
# 连接池配置
SQLALCHEMY_DATABASE_URI = "postgresql://..."
engine = create_async_engine(
    SQLALCHEMY_DATABASE_URI,
    pool_size=20,  # 20 个连接
    max_overflow=40,  # 最大 60 个连接
    pool_pre_ping=True,  # 连接健康检查
    echo=False
)

# 索引优化
CREATE INDEX CONCURRENTLY idx_cards_user_embedding
ON cards USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);  # 1000 用户 * 估算卡片数
```

### 缓存策略

```python
# Redis 缓存
from redis import Redis

redis = Redis(host='localhost', port=6379, db=0)

# 缓存用户知识
async def get_user_cards(user_id: int):
    cache_key = f"user:{user_id}:cards"

    # 尝试从缓存获取
    cached = redis.get(cache_key)
    if cached:
        return json.loads(cached)

    # 从数据库查询
    cards = await db.query(Card).filter_by(user_id=user_id).all()

    # 写入缓存（5分钟）
    redis.setex(cache_key, 300, json.dumps(cards))

    return cards
```

---

## 🎯 下一步行动

### 立即开始

我建议按以下顺序开始实现：

1. **今天**: 设置数据库层
   - 安装 PostgreSQL + Alembic
   - 创建基础表结构

2. **本周**: 实现用户系统
   - 登录 + JWT
   - 用户设置

3. **下周**: 知识管理模块
   - Inbox + Card
   - RAG 接口

**我可以立即开始吗？** 我将先创建数据库层的基础设施。
