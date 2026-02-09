# AgentOS 架构文档

**版本:** 1.0
**最后更新:** 2026-02-09

---

## 📐 系统架构概览

AgentOS 采用**微内核 + 插件架构**设计，实现高度模块化和可扩展性。

```
┌─────────────────────────────────────────────────────────────┐
│                         Client Layer                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   Web    │  │   CLI    │  │  Mobile  │  │ WebSocket│   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
└───────┼────────────┼────────────┼────────────┼─────────────┘
        │            │            │            │
┌───────┴────────────┴────────────┴────────────┴─────────────┐
│                       API Gateway                            │
│                    (FastAPI Server)                          │
└───────┬────────────┬────────────┬────────────┬─────────────┘
        │            │            │            │
┌───────┴────────────┴────────────┴────────────┴─────────────┐
│                      Core Kernel                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │  Agent  │  │ Memory  │  │ Context │  │  Skills │       │
│  │ Manager │  │ Provider│  │ Manager │  │ System  │       │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘       │
└───────┼────────────┼────────────┼────────────┼─────────────┘
        │            │            │            │
┌───────┴────────────┴────────────┴────────────┴─────────────┐
│                    Plugin Layer                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │   LLM   │  │ Vector  │  │  Tools  │  │   DB    │       │
│  │Provider │  │   Store │  │Registry │  │Provider │       │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
└─────────────────────────────────────────────────────────────┘
```

---

## 🏗️ 分层架构

### 1. 表现层 (Presentation Layer)

**职责**: 用户界面和API端点

**组件**:
- FastAPI 路由 (`src/agent_os/api/`)
- WebSocket 处理 (`src/agent_os/server/ws_app.py`)
- 认证中间件 (`src/agent_os/auth/`)

**技术栈**:
- FastAPI
- WebSocket
- JWT 认证

### 2. 应用层 (Application Layer)

**职责**: 业务逻辑和流程编排

**核心模块**:
- **Agent Manager** (`agent/`) - 任务执行和决策
- **Skills System** (`skills/`) - 动态技能加载
- **Context Manager** (`context/`) - 上下文管理
- **Memory Provider** (`memory/`) - 记忆管理

### 3. 领域层 (Domain Layer)

**职责**: 核心业务实体和规则

**核心实体**:
- **Items** (`items/`) - 统一内容索引
- **Tasks** (`tasks/`) - 任务和决策
- **Connections** (`connections/`) - 认知图谱
- **Knowledge** (`knowledge/`) - 知识库管理

### 4. 基础设施层 (Infrastructure Layer)

**职责**: 数据持久化和外部服务

**组件**:
- **Database** (`db/`) - SQLAlchemy ORM
- **Vector Store** - 向量数据库
- **LLM Provider** - 模型抽象层
- **Tools** (`tools/`) - 工具集成

---

## 🔌 插件架构

### Provider Pattern

所有核心组件都通过接口抽象，支持动态加载：

```python
# LLM Provider
class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str:
        pass

# Memory Provider
class MemoryProvider(ABC):
    @abstractmethod
    async def store(self, key: str, value: Any):
        pass

# Context Strategy
class ContextStrategy(ABC):
    @abstractmethod
    async def build_context(self, items: List[Item]) -> str:
        pass
```

### 配置驱动

通过 `config.yaml` 动态加载实现：

```yaml
providers:
  llm:
    type: "litellm"
    model: "claude-3-5-sonnet-20241022"

  memory:
    type: "mem0"
    vector_db: "pgvector"

  context:
    type: "sliding_window"
    max_tokens: 8000
```

---

## 📊 数据模型

### 核心实体关系

```
┌─────────────┐         ┌─────────────┐
│   Workspace │ 1    *  │     User    │
└─────────────┘─────────└─────────────┘
       │ 1                      │ 1
       │                        │
       │ *                      │ *
┌─────────────┐         ┌─────────────┐
│      Item   │────────│     Task    │
└─────────────┘         └─────────────┘
       │ *
       │
┌─────────────┐
│  Connection │
└─────────────┘
```

### 多租户设计

- **Workspace**: 顶层隔离
- **User**: 工作区成员
- **Item**: 所有内容的统一索引
- **Task**: 任务和决策审计

---

## 🔄 关键流程

### 1. Agent 执行流程

```
User Input
    ↓
Inbox Capture
    ↓
Parse & Classify → Item
    ↓
Context Manager → Build Context
    ↓
Agent Processor → LLM Generate
    ↓
Router → Direct/RAG/Skill
    ↓
Write-back → Item Update
    ↓
Response to User
```

### 2. 混合搜索流程

```
Query
    ↓
┌──────────────┬──────────────┐
│  Vector Search│ Keyword Search│
│   (Semantic)  │    (Text)     │
└──────┬───────┴──────┬───────┘
       │              │
       └──────┬───────┘
              ↓
     Combine (0.7 * Vector + 0.3 * Keyword)
              ↓
       Freshness Boost
              ↓
        Rank Results
              ↓
        Return Items
```

### 3. Connection 计算流程

```
Item Created/Updated
    ↓
Connection Engine
    ↓
┌─────────────────────────────┐
│ 5-Dimensional Weight Score: │
│ 1. Vector Similarity (40%)   │
│ 2. Keyword Overlap (20%)    │
│ 3. Entity Overlap (20%)     │
│ 4. Area Match (10%)         │
│ 5. Time Decay (10%)         │
└─────────────────────────────┘
    ↓
Strong Connection? (≥0.75)
    ↓
Create Graph Edge
```

---

## 🔐 安全架构

### 认证流程

```
Client Request
    ↓
JWT Validation
    ↓
Workspace Check
    ↓
Authorization
    ↓
Process Request
```

### 数据隔离

- **Workspace Level**: 物理隔离
- **User Level**: 权限控制
- **API Level**: Token 验证
- **DB Level**: Row-level security

---

## 📈 可扩展性设计

### 水平扩展

- **API Servers**: 无状态，可水平扩展
- **Database**: 连接池，支持读写分离
- **Vector Store**: 分布式索引
- **Workers**: 异步任务队列

### 垂直扩展

- **Caching**: Redis 缓存热点数据
- **CDN**: 静态资源分发
- **Load Balancer**: 请求分发

---

## 🔧 技术栈

### 后端
- **语言**: Python 3.11+
- **框架**: FastAPI
- **ORM**: SQLAlchemy 2.0 (Async)
- **数据库**: PostgreSQL 16 / SQLite
- **向量**: pgvector / LocalJSON

### AI/ML
- **LLM**: LiteLLM (多模型支持)
- **Embeddings**: SentenceTransformers
- **向量搜索**: SQLAlchemy + pgvector

### DevOps
- **容器**: Docker + Docker Compose
- **CI/CD**: GitHub Actions
- **质量**: ruff, mypy, pytest

---

## 📚 相关文档

- [API 文档](docs/09-api/API_ENDPOINTS_COMPLETE.md)
- [数据库架构](docs/10-architecture/DATABASE_ARCHITECTURE.md)
- [部署指南](docs/11-deployment/stage4-deployment-guide.md)
- [PRD4 设计](docs/01-prd/PRD4.md)

---

**维护者**: AgentOS Team
**架构师**: Backend Team
**最后更新**: 2026-02-09
