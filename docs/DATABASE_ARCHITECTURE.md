# 生产级数据库架构文档

**最后更新**: 2026-01-28
**版本**: v2.0 (Multi-Tenant Production Ready)

---

## 📊 架构概述

### 多租户策略

AgentOS 采用**混合多租户架构**（Hybrid Multi-Tenancy）:

```
┌─────────────────────────────────────────────────────────┐
│                  AgentOS 多租户架构                       │
└─────────────────────────────────────────────────────────┘

┌──────────────────┐         ┌──────────────────┐
│   共享数据库       │         │  独立数据库        │
│ (Shared DB)      │         │ (Dedicated DB)   │
├──────────────────┤         ├──────────────────┤
│ • 免费/个人用户    │         │ • 企业客户         │
│ • Startup 计划    │         │ • Enterprise 计划│
│ • organization_id │         │ • 物理数据隔离     │
│   行级隔离        │         │ • 独立性能保障     │
│ • 成本效益高      │         │ • 高级安全特性     │
└──────────────────┘         └──────────────────┘
```

### 数据库技术栈

| 组件 | 技术 | 版本 | 用途 |
|------|------|------|------|
| **数据库** | PostgreSQL | 14+ | 主数据库 |
| **向量搜索** | pgvector | 0.5.0+ | 向量嵌入和相似度搜索 |
| **驱动** | asyncpg | - | 异步数据库驱动 |
| **ORM** | SQLAlchemy | 2.0 | 异步 ORM |
| **迁移** | Alembic | - | 数据库迁移工具 |
| **缓存** | Redis | - | 查询结果缓存 |
| **连接池** | SQLAlchemy Pool | - | 数据库连接池 |

---

## 🗄️ 数据模型

### 核心表结构

```
organizations (组织/租户表)
├── id (PK)
├── name
├── slug (unique)
├── plan (free/pro/enterprise)
├── max_users
├── max_storage_gb
├── is_active
├── db_host (独立数据库配置)
├── db_port
├── db_name
├── db_user
└── db_password (encrypted)

users (用户表)
├── id (PK)
├── organization_id (FK) ← 多租户隔离
├── username (org内唯一)
├── email (org内唯一)
├── hashed_password
├── is_active
├── is_admin
└── timestamps

inbox_items (收件箱)
├── id (PK)
├── organization_id (FK) ← 多租户隔离
├── user_id (FK)
├── content
├── status
└── timestamps

cards (知识卡片)
├── id (PK)
├── organization_id (FK) ← 多租户隔离
├── user_id (FK)
├── title
├── content
├── para_type
├── tags (JSON)
├── embedding (vector)
└── timestamps

tasks (任务)
├── id (PK)
├── organization_id (FK) ← 多租户隔离
├── user_id (FK)
├── title
├── description
├── status
├── priority
└── timestamps

audit_logs (审计日志)
├── id (PK)
├── organization_id (FK)
├── user_id
├── action (create/read/update/delete)
├── table_name
├── old_values (JSON)
├── new_values (JSON)
├── ip_address
└── timestamps
```

### 索引策略

#### 复合索引（多租户查询优化）

```sql
-- 用户表：组织 + 活跃状态
CREATE INDEX idx_user_org_active ON users(organization_id, is_active);

-- 卡片表：组织 + 用户 + 类型
CREATE INDEX idx_card_org_user ON cards(organization_id, user_id);
CREATE INDEX idx_card_org_type ON cards(organization_id, para_type);
CREATE INDEX idx_card_org_created ON cards(organization_id, created_at DESC);

-- 任务表：组织 + 状态 + 计划日期
CREATE INDEX idx_task_org_user ON tasks(organization_id, user_id);
CREATE INDEX idx_task_org_status ON tasks(organization_id, status);
CREATE INDEX idx_task_org_status_date ON tasks(organization_id, status, scheduled_date)
  WHERE status != 'completed';  -- 部分索引（未完成任务）

-- 收件箱：组织 + 用户，组织 + 状态
CREATE INDEX idx_inbox_org_user ON inbox_items(organization_id, user_id);
CREATE INDEX idx_inbox_org_status ON inbox_items(organization_id, status);
```

#### 向量搜索索引（HNSW）

```sql
-- 高性能向量相似度搜索
CREATE INDEX idx_cards_embedding_hnsw
ON cards
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

#### 审计日志索引（时间序列）

```sql
-- 按时间分区 + 复合索引
CREATE INDEX idx_audit_org_action ON audit_logs(organization_id, action);
CREATE INDEX idx_audit_org_table ON audit_logs(organization_id, table_name);
CREATE INDEX idx_audit_created_at ON audit_logs(created_at DESC);
```

---

## 🔒 安全特性

### 1. 多租户数据隔离

#### 行级隔离（Row-Level Isolation）

所有业务表包含 `organization_id` 字段：

```python
# 查询自动过滤
SELECT * FROM cards
WHERE organization_id = :org_id
  AND user_id = :user_id;
```

#### 行级安全（Row-Level Security, RLS）

数据库层面强制隔离（即使应用层有bug也无法绕过）：

```sql
-- 启用 RLS
ALTER TABLE cards ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE inbox_items ENABLE ROW LEVEL SECURITY;

-- 创建隔离策略
CREATE POLICY card_org_isolation ON cards
FOR ALL
TO public
USING (
    organization_id = (
        SELECT organization_id
        FROM users
        WHERE id = current_setting('app.user_id')::integer
    )
);
```

**优势**：
- ✅ 数据库层面强制隔离
- ✅ 防止应用层 bug 导致数据泄露
- ✅ 满足合规要求（SOC2, HIPAA）

### 2. 数据加密

#### 字段级加密

敏感字段使用 Fernet 对称加密：

```python
from agent_os.db.encryption import field_encryptor

# 加密数据库密码
encrypted_password = field_encryptor.encrypt("my_db_password")

# 解密
decrypted = field_encryptor.decrypt(encrypted_password)
```

**加密字段**：
- `organizations.db_password` - 独立数据库密码
- 未来可扩展：API keys, OAuth tokens 等

#### 传输加密

- TLS 1.3 加密数据库连接
- 强制 SSL 连接

### 3. 审计日志

记录所有数据访问和修改：

```python
from agent_os.db.audit import audit_logger

# 记录创建
await audit_logger.log_create(
    db=session,
    organization_id=user.organization_id,
    user_id=user.id,
    table_name="cards",
    record_id=card.id,
    new_values=card_dict,
    ip_address=request.client.host
)
```

**记录内容**：
- 谁（user_id）
- 什么操作（create/read/update/delete）
- 哪个表（table_name）
- 哪条记录（record_id）
- 变化前（old_values）
- 变化后（new_values）
- 何时（created_at）
- 从哪里（ip_address）

---

## ⚡ 性能优化

### 1. 连接池配置

```python
# src/agent_os/db/base.py

engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,        # 基础连接数
    max_overflow=40,     # 最大连接数（共60个）
    pool_pre_ping=True,  # 连接健康检查
    echo=False,          # 生产环境关闭 SQL 日志
)
```

**容量规划**：
- 60 个连接
- 每个查询平均 100ms
- 支持 ~600 请求/秒
- 可承载 ~10,000 并发用户

### 2. Redis 缓存层

#### 缓存策略

```python
from agent_os.db.cache import cache_manager, UserCache

# 缓存用户的卡片列表（5分钟）
cards = await UserCache.get_cards(org_id, user_id)
if not cards:
    cards = await db.query(Card).filter_by(user_id=user_id).all()
    await UserCache.set_cards(org_id, user_id, cards, ttl=300)
```

#### 缓存失效

```python
# 用户创建新卡片时，清除缓存
await UserCache.invalidate(org_id, user_id)
```

#### 缓存命中率目标

- 热数据：90%+ 命中率
- 温数据：70%+ 命中率
- 冷数据：不缓存

### 3. 查询优化

#### 预加载关联（Eager Loading）

```python
from sqlalchemy.orm import selectinload

# 避免N+1查询
stmt = (
    select(Card)
    .options(
        selectinload(Card.user),  # 预加载用户
        defer(Card.content),      # 延迟加载大字段
    )
    .where(Card.organization_id == org_id)
)
```

#### 延迟加载大字段

```python
# 列表查询不加载 content 字段
stmt = (
    select(Card)
    .options(defer(Card.content))
    .limit(20)
)
```

### 4. 读写分离（未来）

```python
# 主库（写）
master_engine = create_async_engine(DATABASE_URL_MASTER)

# 从库（读，可配置多个）
replica_engines = [
    create_async_engine(url)
    for url in DATABASE_URL_REPLICAS.split(',')
]

# 自动路由
def get_session(read_only=False):
    if read_only:
        return random.choice(replica_engines)
    else:
        return master_engine
```

---

## 🚀 部署架构

### 开发环境

```
┌─────────────────────────────────────┐
│         Application Server           │
│  (FastAPI + SQLAlchemy 2.0)         │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│      PostgreSQL (localhost)         │
│  • Shared database                  │
│  • All organizations               │
│  • pgvector extension               │
└─────────────────────────────────────┘
```

### 生产环境

```
┌──────────────────┐         ┌──────────────────┐
│  Load Balancer   │         │   Redis Cluster  │
└────────┬─────────┘         └──────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│           Application Servers (x3)              │
│  • FastAPI + Gunicorn                          │
│  • Connection pooling                          │
│  • Redis caching                               │
└─────┬───────────────────────────────┬──────────┘
      │                               │
      ▼                               ▼
┌──────────────────┐         ┌──────────────────┐
│ PostgreSQL Master │ ◄─────► │ PostgreSQL Replica│
│  (Write)         │         │  (Read)          │
└──────────────────┘         └──────────────────┘
      │
      ├─────────────────┐
      │                 │
      ▼                 ▼
┌──────────┐    ┌──────────────┐
│ Org 1 DB │    │ Org 2 DB     │
│(Shared)  │    │(Dedicated)   │
└──────────┘    └──────────────┘
```

### 企业客户独立数据库

```python
# organizations 表配置
organization = {
    "id": 123,
    "name": "Acme Corp",
    "plan": "enterprise",
    "db_host": "db-acme.internal",
    "db_port": 5432,
    "db_name": "acme_production",
    "db_user": "acme_user",
    "db_password": "encrypted_password"
}

# 自动路由到独立数据库
session = await db_router.get_session(organization_id=123)
# → 连接到 acme_production 数据库
```

---

## 📦 数据库迁移

### 运行迁移

```bash
# 升级到最新版本
alembic upgrade head

# 查看当前版本
alembic current

# 查看迁移历史
alembic history

# 回滚一个版本
alembic downgrade -1

# 生成新迁移
alembic revision --autogenerate -m "description"
```

### 多租户迁移（002_add_multi_tenant_support）

**变更内容**：

1. ✅ 创建 `organizations` 表
2. ✅ 为所有业务表添加 `organization_id`
3. ✅ 创建复合索引优化多租户查询
4. ✅ 添加外键约束
5. ✅ 为现有用户创建默认组织
6. ✅ 可选：启用行级安全（RLS）

**回滚**：
```bash
# 如需回滚
alembic downgrade 001_initial
```

---

## 🔧 监控和维护

### 1. 数据库监控指标

```sql
-- 连接数监控
SELECT count(*) FROM pg_stat_activity;

-- 慢查询
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- 表大小
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- 索引使用情况
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

### 2. 数据备份

```bash
#!/bin/bash
# 每日备份脚本

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"

# 共享数据库
pg_dump -U agentos -d agentos_db | gzip > "$BACKUP_DIR/shared_$DATE.sql.gz"

# 企业客户独立数据库
while read ORG_ID DB_NAME DB_HOST; do
    pg_dump -h "$DB_HOST" -U agentos -d "$DB_NAME" | \
        gzip > "$BACKUP_DIR/org_${ORG_ID}_$DATE.sql.gz"
done < <(psql -U agentos -d agentos_db -t -A -F" " \
    -c "SELECT id, db_name, db_host FROM organizations WHERE db_host IS NOT NULL")

# 上传到 S3
aws s3 sync "$BACKUP_DIR" s3://agentos-backups --storage-class GLACIER
```

### 3. 数据归档

```python
# 归档 1 年前的数据到冷存储
from agent_os.db.archive import DataArchiver

archiver = DataArchiver()
await archiver.archive_old_cards(db, days=365)
```

---

## 📚 最佳实践

### 1. 查询模式

#### ✅ 推荐

```python
# 使用复合索引字段
stmt = select(Card).where(
    and_(
        Card.organization_id == org_id,
        Card.user_id == user_id,
        Card.para_type == "concept"
    )
)
```

#### ❌ 避免

```python
# 避免 SELECT *
result = await db.execute(select(Card))  # Bad

# 避免在索引列上使用函数
stmt = select(Card).where(
    func.lower(Card.title) == "test"  # 无法使用索引
)

# 避免 N+1 查询
for card in cards:
    print(card.user.username)  # N+1 问题
```

### 2. 事务管理

```python
from sqlalchemy.ext.asyncio import AsyncSession

async with db.begin() as trans:
    # 自动提交/回滚
    card = Card(...)
    db.add(card)

    await trans.commit()  # 自动提交
```

### 3. 连接管理

```python
# ✅ 使用依赖注入
@router.get("/cards")
async def get_cards(
    db: AsyncSession = Depends(get_db)
):
    # FastAPI 自动关闭连接
    return await db.query(Card).all()

# ❌ 手动管理（容易忘记关闭）
@router.get("/cards")
async def get_cards():
    db = AsyncSessionLocal()
    # 忘记关闭连接！
    return await db.query(Card).all()
```

---

## 🔗 相关文档

- [数据库优化方案](./DATABASE_OPTIMIZATION_PLAN.md) - 详细优化方案
- [数据库设置指南](./DATABASE_SETUP.md) - PostgreSQL 配置
- [数据模型文档](./DATA_MODELS.md) - 待创建
- [安全最佳实践](./SECURITY_BEST_PRACTICES.md) - 待创建

---

**维护者**: AgentOS 开发团队
**最后更新**: 2026-01-28
**文档版本**: v2.0
