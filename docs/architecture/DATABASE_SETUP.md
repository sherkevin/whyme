# 数据库设置指南

本文档说明如何设置 PostgreSQL 数据库并运行迁移。

---

## 📋 前置要求

1. **PostgreSQL 数据库** (版本 14+)
2. **pgvector 扩展** (用于向量搜索)
3. **Python 3.11+**

---

## 🚀 快速开始

### 1. 安装 PostgreSQL

#### Windows

```bash
# 使用 Chocolatey
choco install postgresql

# 或下载安装器
# https://www.postgresql.org/download/windows/
```

#### macOS

```bash
# 使用 Homebrew
brew install postgresql@14
brew services start postgresql@14
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install postgresql-14 postgresql-contrib-14
sudo systemctl start postgresql
```

### 2. 安装 pgvector 扩展

```bash
# 克隆 pgvector
git clone --branch v0.5.0 https://github.com/pgvector/pgvector.git
cd pgvector

# 编译安装 (确保 pg_config 在 PATH 中)
make
make install

# 或在 Windows 上使用预编译版本
# 下载: https://github.com/pgvector/pgvector/releases
```

### 3. 创建数据库和用户

```bash
# 切换到 postgres 用户
sudo -u postgres psql

# 在 psql 中执行:
CREATE USER agentos WITH PASSWORD 'agentos';
CREATE DATABASE agentos_db OWNER agentos;
GRANT ALL PRIVILEGES ON DATABASE agentos_db TO agentos;
\c agentos_db
CREATE EXTENSION vector;
\q
```

### 4. 安装 Python 依赖

```bash
pip install -r requirements-km.txt
```

### 5. 配置环境变量

创建 `.env` 文件或更新现有 `.env`:

```bash
# Database URL
DATABASE_URL=postgresql+asyncpg://agentos:agentos@localhost/agentos_db

# 如果使用远程数据库
# DATABASE_URL=postgresql+asyncpg://user:password@host:port/database
```

### 6. 运行数据库迁移

```bash
# 升级数据库到最新版本
alembic upgrade head

# 查看迁移历史
alembic history

# 回滚到上一个版本
alembic downgrade -1

# 查看当前版本
alembic current
```

---

## 🗄️ 数据库架构

迁移后将创建以下表：

### `users` - 用户表
- `id` - 主键
- `username` - 用户名（唯一）
- `email` - 邮箱（唯一）
- `hashed_password` - 加密密码
- `created_at` - 创建时间
- `updated_at` - 更新时间

### `user_settings` - 用户设置
- `id` - 主键
- `user_id` - 外键到 users
- `daily_goal` - 每日目标
- `theme` - 主题偏好
- `language` - 语言偏好

### `inbox_items` - 收件箱
- `id` - 主键
- `user_id` - 外键到 users
- `content` - 内容
- `status` - 状态 (raw/processed/archived)
- `source` - 来源
- `metadata` - 元数据 (JSON)

### `cards` - 知识卡片
- `id` - 主键
- `user_id` - 外键到 users
- `title` - 标题
- `content` - 内容
- `para_type` - 类型
- `tags` - 标签数组
- `embedding` - 向量嵌入 (384维)
- `source_inbox_item_id` - 来源收件项

### `tasks` - 任务
- `id` - 主键
- `user_id` - 外键到 users
- `title` - 标题
- `description` - 描述
- `type` - 类型
- `source` - 来源
- `status` - 状态
- `priority` - 优先级 (1-10)
- `scheduled_date` - 计划日期
- `completed_at` - 完成时间

---

## 🔍 验证安装

### 1. 检查 PostgreSQL

```bash
psql -U agentos -d agentos_db -c "SELECT version();"
```

### 2. 检查 pgvector

```bash
psql -U agentos -d agentos_db -c "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
```

应该返回 pgvector 版本号。

### 3. 检查表结构

```bash
psql -U agentos -d agentos_db -c "\dt"
```

应该看到所有创建的表。

### 4. 测试连接

```python
import asyncio
from agent_os.db.base import AsyncSessionLocal

async def test_connection():
    async with AsyncSessionLocal() as session:
        result = await session.execute("SELECT 1")
        print("Database connection successful!")

asyncio.run(test_connection())
```

---

## 📊 性能优化

### 连接池配置

已在 `src/agent_os/db/base.py` 中配置：

```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,      # 20 个连接（支持 ~1000 用户）
    max_overflow=40,   # 最大 60 个连接
    pool_pre_ping=True, # 连接健康检查
)
```

### 索引优化

数据库迁移会自动创建以下索引：

- 用户索引: `username`, `email`
- 收件箱索引: `(user_id, status)`
- 卡片索引: `(user_id, para_type)`
- 任务索引: `(user_id, scheduled_date)`, `status`

### 向量搜索索引

```sql
-- 为 cards 表创建向量索引（手动）
CREATE INDEX idx_cards_embedding_ivfflat
ON cards USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);  -- 根据数据量调整

-- 查看索引
\di
```

---

## 🔧 常见问题

### 问题 1: 认证失败

```
FATAL: password authentication failed for user "agentos"
```

**解决**: 检查密码是否正确，或重置密码：

```bash
psql -U postgres
ALTER USER agentos WITH PASSWORD 'new_password';
```

### 问题 2: pgvector 扩展未找到

```
ERROR: could not open extension control file: No such file or directory
```

**解决**: 安装 pgvector 扩展（见上文）。

### 问题 3: 迁移失败

```
sqlalchemy.exc.OperationalError: relation "users" already exists
```

**解决**: 回滚迁移并重新运行：

```bash
alembic downgrade base
alembic upgrade head
```

---

## 📖 下一步

数据库设置完成后，接下来：

1. **Week 1**: 实现用户认证系统
2. **Week 2**: 实现 Inbox + Card 系统
3. **Week 3**: 实现 Task 系统 + Agent 集成

---

## 💡 提示

- 开发时可以启用 SQL 日志查看查询（`echo=True`）
- 生产环境记得禁用日志并使用连接池
- 定期备份数据库
- 监控连接池使用情况
