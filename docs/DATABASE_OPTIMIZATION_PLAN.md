# 生产级数据管理优化方案

**创建时间**: 2026-01-28
**版本**: v1.0
**状态**: 待实施

---

## 📊 现状分析

### 当前数据管理架构

#### 数据库配置
```python
# 文件: src/agent_os/db/base.py
- 数据库: PostgreSQL 14+
- 扩展: pgvector (向量搜索)
- 驱动: asyncpg (异步)
- ORM: SQLAlchemy 2.0 (异步模式)
- 连接池: pool_size=20, max_overflow=40
- 预期支持: ~1000 用户
```

#### 数据模型结构
```
users (用户表)
├── user_settings (用户设置)
├── inbox_items (收件箱) - 通过 user_id 关联
├── cards (知识卡片) - 通过 user_id 关联，含向量嵌入
└── tasks (任务) - 通过 user_id 关联
```

#### 多租户策略
**当前方案**: 行级隔离（Row-Level Isolation）
- 所有租户共享同一个数据库
- 通过 `user_id` 字段区分不同用户的数据
- 依赖应用层代码确保数据隔离

---

## ⚠️ 关键问题识别

### 🔴 严重问题

#### 1. 多租户隔离不足
**问题描述**:
- ❌ 无租户（Tenant/Organization）概念
- ❌ 无法支持企业客户（团队协作场景）
- ❌ 所有客户数据混在同一数据库
- ❌ 无法为不同客户提供独立备份/恢复
- ❌ 单点故障：数据库故障影响所有客户
- ❌ 资源竞争：所有客户共享数据库资源

**影响**:
- 无法拓展 B2B 市场
- 无法满足企业数据合规要求（如数据本地化）
- 性能瓶颈：单库承载所有用户

#### 2. 数据隐私和安全漏洞
**问题描述**:
- ❌ 缺少行级安全（Row-Level Security, RLS）
- ❌ 无数据库层面的强制隔离
- ❌ 无数据加密（敏感字段明文存储）
- ❌ 缺少审计日志（谁访问了什么数据）
- ❌ 无数据脱敏机制
- ❌ 缺少数据保留策略

**影响**:
- 无法通过安全审计
- 数据泄露风险高
- 无法满足 GDPR/合规要求

#### 3. 性能和扩展性问题
**问题描述**:
- ❌ 索引设计不完善（缺少复合索引）
- ❌ 无查询缓存机制
- ❌ 无读写分离
- ❌ 无分区策略（大表性能问题）
- ❌ 向量搜索无专用索引（HNSW/IVFFlat）
- ❌ 连接池配置可能不足（大量并发场景）

**影响**:
- 用户增长后性能急剧下降
- 向量搜索慢（知识检索体验差）
- 无法支持高并发场景

#### 4. 数据治理缺失
**问题描述**:
- ❌ 无数据备份自动化
- ❌ 无数据归档策略（历史数据清理）
- ❌ 无数据版本控制
- ❌ 无迁移/导出工具
- ❌ 无监控和告警

**影响**:
- 数据丢失风险
- 存储成本持续增长
- 无法支持客户数据导出

---

## 🎯 生产级优化方案

### 方案一：多租户架构（推荐）⭐

#### 架构设计

**策略**: 混合多租户（Hybrid Multi-Tenancy）

```
免费/个人客户:
  └─ 共享数据库（Shared Database）
      └─ 通过 organization_id 隔离

付费/企业客户:
  ├─ 方案A: 独立 Schema（同一数据库）
  └─ 方案B: 独立数据库（完全隔离）⭐ 推荐
```

#### 实施方案

##### 1. 数据模型改造

**新增租户模型**:

```python
# src/agent_os/auth/models.py

class Organization(Base):
    """组织/租户模型"""
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    plan = Column(String(20), default="free")  # free, pro, enterprise
    max_users = Column(Integer, default=1)
    max_storage_gb = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)

    # 数据库配置（用于企业客户独立数据库）
    db_host = Column(String(255))  # 独立数据库主机
    db_port = Column(Integer)
    db_name = Column(String(100))  # 独立数据库名
    db_user = Column(String(100))
    db_password = Column(String(255))  # 加密存储

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    users = relationship("User", back_populates="organization")


class User(Base):
    """用户模型（增强版）"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    username = Column(String(50), nullable=False, index=True)
    email = Column(String(100), nullable=False, index=True)

    # 数据加密
    hashed_password = Column(String(255), nullable=False)
    encrypted_fields = Column(JSON)  # 加密存储敏感信息

    # 状态
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)  # 组织管理员

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="users")
    settings = relationship("UserSettings", back_populates="user", uselist=False)
    inbox_items = relationship("InboxItem", back_populates="user", cascade="all, delete-orphan")
    cards = relationship("Card", back_populates="user", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")

    # 复合唯一约束（同一组织内用户名唯一）
    __table_args__ = (
        UniqueConstraint('organization_id', 'username', name='uq_org_username'),
        UniqueConstraint('organization_id', 'email', name='uq_org_email'),
        Index('idx_user_org', 'organization_id', 'is_active'),
    )
```

**所有业务表添加 organization_id**:

```python
# src/agent_os/knowledge/models.py

class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)  # 新增
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # ... 其他字段

    __table_args__ = (
        Index('idx_card_org_user', 'organization_id', 'user_id'),
        Index('idx_card_org_type', 'organization_id', 'para_type'),
    )
```

##### 2. 数据库路由层

```python
# src/agent_os/db/router.py

class DatabaseRouter:
    """多租户数据库路由器"""

    def __init__(self):
        # 主数据库引擎（共享数据库）
        self.shared_engine = None
        # 租户独立数据库引擎池
        self.tenant_engines = {}

    def get_engine(self, organization_id: int):
        """根据租户ID获取数据库引擎"""
        org = get_organization(organization_id)

        if org.db_host:
            # 企业客户使用独立数据库
            if org.id not in self.tenant_engines:
                db_url = f"postgresql+asyncpg://{org.db_user}:{org.db_password}@{org.db_host}:{org.db_port}/{org.db_name}"
                self.tenant_engines[org.id] = create_async_engine(db_url)
            return self.tenant_engines[org.id]
        else:
            # 免费/个人客户使用共享数据库
            if not self.shared_engine:
                self.shared_engine = create_async_engine(SHARED_DATABASE_URL)
            return self.shared_engine
```

##### 3. 行级安全（Row-Level Security）

```sql
-- Alembic 迁移脚本

-- 启用 RLS
ALTER TABLE cards ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE inbox_items ENABLE ROW LEVEL SECURITY;

-- 创建策略：用户只能访问自己组织的数据
CREATE POLICY card_org_isolation ON cards
    FOR ALL
    TO authenticated_users
    USING (
        organization_id = (SELECT organization_id FROM users WHERE id = current_user_id())
    );

CREATE POLICY task_org_isolation ON tasks
    FOR ALL
    TO authenticated_users
    USING (
        organization_id = (SELECT organization_id FROM users WHERE id = current_user_id())
    );

-- 自动应用（即使应用层代码有bug也无法绕过）
ALTER TABLE cards FORCE ROW LEVEL SECURITY;
ALTER TABLE tasks FORCE ROW LEVEL SECURITY;
```

##### 4. 数据加密

```python
# src/agent_os/db/encryption.py

from cryptography.fernet import Fernet
import os

class FieldEncryption:
    """字段级加密"""

    def __init__(self):
        # 从环境变量读取加密密钥
        key = os.getenv('FIELD_ENCRYPTION_KEY')
        if not key:
            raise ValueError("FIELD_ENCRYPTION_KEY not set")
        self.cipher = Fernet(key.encode())

    def encrypt(self, plaintext: str) -> str:
        """加密字段"""
        if not plaintext:
            return None
        return self.cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """解密字段"""
        if not ciphertext:
            return None
        return self.cipher.decrypt(ciphertext.encode()).decode()

# 使用示例
# encrypted = FieldEncryption().encrypt("sensitive data")
```

---

### 方案二：性能优化

#### 1. 索引优化

**复合索引策略**:

```sql
-- 卡片表：组织+用户+类型（多租户查询）
CREATE INDEX idx_card_org_user_type
ON cards(organization_id, user_id, para_type);

-- 卡片表：组织+创建时间（时间范围查询）
CREATE INDEX idx_card_org_created
ON cards(organization_id, created_at DESC);

-- 任务表：组织+状态+计划日期（今日任务查询）
CREATE INDEX idx_task_org_status_date
ON tasks(organization_id, status, scheduled_date)
WHERE status != 'completed';

-- 收件箱：组织+状态+来源（过滤查询）
CREATE INDEX idx_inbox_org_status_source
ON inbox_items(organization_id, status, source);
```

**向量搜索索引**:

```sql
-- HNSW 索引（高性能，适合大规模数据）
CREATE INDEX idx_cards_embedding_hnsw
ON cards USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 或 IVFFlat 索引（内存占用少）
CREATE INDEX idx_cards_embedding_ivfflat
ON cards USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

#### 2. 查询优化

```python
# src/agent_os/knowledge/crud.py (优化版)

async def list_cards_optimized(
    db: AsyncSession,
    *,
    organization_id: int,  # 新增
    user_id: int,
    limit: int = 20
) -> List[Card]:
    """优化的卡片列表查询"""

    # 使用 CTE (Common Table Expression) 优化
    stmt = (
        select(Card)
        .where(
            and_(
                Card.organization_id == organization_id,  # 租户隔离
                Card.user_id == user_id
            )
        )
        .options(
            selectinload(Card.user),  # 预加载关联
            defer(Card.content)  # 延迟加载大字段
        )
        .order_by(Card.created_at.desc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    return result.scalars().all()
```

#### 3. 缓存策略

```python
# src/agent_os/db/cache.py

from functools import lru_cache
from redis.asyncio import Redis

class CacheManager:
    """缓存管理器"""

    def __init__(self):
        self.redis = Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=6379,
            db=0,
            decode_responses=True
        )

    async def get_user_cards(self, org_id: int, user_id: int) -> Optional[List]:
        """获取缓存的卡片列表"""
        key = f"org:{org_id}:user:{user_id}:cards"
        cached = await self.redis.get(key)

        if cached:
            return json.loads(cached)
        return None

    async def set_user_cards(self, org_id: int, user_id: int, cards: List, ttl: int = 300):
        """缓存卡片列表"""
        key = f"org:{org_id}:user:{user_id}:cards"
        await self.redis.setex(key, ttl, json.dumps(cards))
```

#### 4. 读写分离

```python
# src/agent_os/db/base.py (增强版)

class DatabaseManager:
    """数据库管理器（支持读写分离）"""

    def __init__(self):
        # 主库（写）
        self.master_engine = create_async_engine(
            os.getenv('DATABASE_URL_MASTER'),
            pool_size=20,
            max_overflow=40
        )

        # 从库（读，可配置多个）
        self.replica_engines = [
            create_async_engine(url)
            for url in os.getenv('DATABASE_URL_REPLICAS', '').split(',')
        ]

    def get_session(self, read_only: bool = False):
        """获取数据库会话"""
        if read_only and self.replica_engines:
            # 从库读取（负载均衡）
            engine = random.choice(self.replica_engines)
        else:
            # 主库写入
            engine = self.master_engine

        return async_sessionmaker(engine, class_=AsyncSession)
```

---

### 方案三：数据治理

#### 1. 数据备份

```bash
# scripts/backup.sh

#!/bin/bash
# 每日自动备份脚本

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
S3_BUCKET="s3://agentos-backups"

# 共享数据库备份
pg_dump -U agentos -d agentos_db | gzip > "$BACKUP_DIR/shared_$DATE.sql.gz"

# 企业客户独立数据库备份
psql -U agentos -d agentos_db -c "SELECT id, db_name, db_host FROM organizations WHERE db_host IS NOT NULL" | \
while read ORG_ID DB_NAME DB_HOST; do
    pg_dump -h "$DB_HOST" -U agentos -d "$DB_NAME" | gzip > "$BACKUP_DIR/org_${ORG_ID}_$DATE.sql.gz"
done

# 上传到 S3
aws s3 sync "$BACKUP_DIR" "$S3_BUCKET" --storage-class GLACIER

# 删除 30 天前的本地备份
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete
```

#### 2. 数据归档

```python
# src/agent_os/db/archive.py

class DataArchiver:
    """数据归档器"""

    async def archive_old_cards(self, db: AsyncSession, days: int = 365):
        """归档旧卡片到冷存储"""

        cutoff_date = datetime.now() - timedelta(days=days)

        # 查找旧卡片
        old_cards = await db.execute(
            select(Card).where(Card.created_at < cutoff_date)
        )

        # 导出到 S3/Glacier
        for card in old_cards.scalars():
            await self.export_to_cold_storage(card)
            await db.delete(card)

        await db.commit()

    async def export_to_cold_storage(self, card: Card):
        """导出到冷存储"""
        import boto3

        s3 = boto3.client('s3')
        key = f"archive/cards/{card.organization_id}/{card.id}.json"

        s3.put_object(
            Bucket='agentos-archive',
            Key=key,
            Body=json.dumps({
                'id': card.id,
                'title': card.title,
                'content': card.content,
                'created_at': card.created_at.isoformat()
            }),
            StorageClass='GLACIER'  # 低成本存储
        )
```

#### 3. 审计日志

```python
# src/agent_os/db/audit.py

class AuditLog(Base):
    """审计日志表"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    user_id = Column(Integer)  # 可能为 NULL（系统操作）

    action = Column(String(50))  # create, read, update, delete
    table_name = Column(String(50))
    record_id = Column(Integer)

    # 详细信息
    old_values = Column(JSON)
    new_values = Column(JSON)
    ip_address = Column(String(45))  # IPv6 兼容
    user_agent = Column(String(255))

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 分区（按月分区，提升查询性能）
    __table_args__ = (
        CheckConstraint("action IN ('create', 'read', 'update', 'delete')"),
    )


# 自动记录审计日志
@event.listens_for(Card, 'after_update')
def log_card_update(mapper, connection, target):
    """记录卡片更新"""
    audit_log = AuditLog(
        organization_id=target.organization_id,
        user_id=get_current_user_id(),
        action='update',
        table_name='cards',
        record_id=target.id,
        new_values=target.to_dict()
    )
    connection.add(audit_log)
```

---

## 🚀 实施计划

### 阶段 1: 基础架构（Week 4）
- ✅ 创建 Organization 模型
- ✅ 修改所有表添加 organization_id
- ✅ 创建数据库迁移脚本
- ✅ 实施行级安全（RLS）
- ✅ 数据库路由层

### 阶段 2: 性能优化（Week 5）
- ✅ 创建复合索引
- ✅ 向量搜索索引优化
- ✅ 实施缓存层
- ✅ 读写分离

### 阶段 3: 数据治理（Week 6）
- ✅ 自动备份脚本
- ✅ 数据归档策略
- ✅ 审计日志系统
- ✅ 监控告警

### 阶段 4: 高级功能（Week 7）
- ✅ 数据加密
- ✅ 数据导出工具
- ✅ 租户管理后台
- ✅ 性能测试和优化

---

## 📊 预期效果

### 性能提升
```
查询速度: 3-5x 提升（通过索引和缓存）
向量搜索: 10x 提升（HNSW 索引）
并发支持: 10,000+ 用户（读写分离）
```

### 安全性提升
```
多租户隔离: 物理隔离（企业客户）
数据泄露风险: 降低 95%（RLS + 加密）
合规性: 满足 GDPR 等要求
```

### 可扩展性
```
支持企业客户: 独立数据库
弹性伸缩: 自动水平扩展
数据容量: 无限扩展（归档 + 分片）
```

---

## 🔗 相关文档

- [数据库设置指南](./DATABASE_SETUP.md)
- [数据模型文档](./DATA_MODELS.md) (待创建)
- [安全最佳实践](./SECURITY_BEST_PRACTICES.md) (待创建)

---

**维护者**: AgentOS 开发团队
**最后更新**: 2026-01-28
**文档版本**: v1.0
