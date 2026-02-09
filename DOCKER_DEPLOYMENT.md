# AgentOS Docker 部署指南

**版本:** 1.0  
**最后更新:** 2026-02-09  
**适用人群:** 开发者、运维人员、前端开发者

---

## 🚀 快速开始

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- 2GB+ 可用内存
- 5GB+ 可用磁盘空间

### 一键启动 (推荐)

```bash
# 克隆仓库
git clone https://github.com/your-org/agentos.git
cd agentos

# 运行启动脚本
./start.sh
```

启动脚本会自动：
1. 检查 Docker 环境
2. 创建必要的配置文件
3. 启动所有服务
4. 等待服务就绪

### 手动启动

```bash
# 1. 复制环境配置
cp .env.example .env

# 2. 启动服务
docker-compose -f docker-compose.quick.yml up -d

# 3. 查看日志
docker-compose -f docker-compose.quick.yml logs -f api
```

---

## 📋 部署模式

### 模式 1: 开发模式 (SQLite)

**适用场景:** 前端开发、快速测试、本地开发

**特点:**
- ✅ 无需配置数据库
- ✅ 一键启动
- ✅ 数据持久化到本地
- ⚠️ 不适合生产环境

**启动命令:**
```bash
docker-compose -f docker-compose.quick.yml up -d
```

**访问地址:**
- API 文档: http://localhost:8000/docs
- API 端点: http://localhost:8000
- WebSocket: ws://localhost:8003

---

### 模式 2: 标准模式 (PostgreSQL)

**适用场景:** 生产环境、团队协作、长期运行

**特点:**
- ✅ PostgreSQL 数据库
- ✅ Redis 缓存
- ✅ 数据持久化
- ✅ 适合生产环境

**启动命令:**
```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，配置数据库密码等

# 2. 启动所有服务
docker-compose up -d

# 3. 查看服务状态
docker-compose ps
```

**服务列表:**
- API 服务: http://localhost:8000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

---

### 模式 3: 完整模式 (含管理工具)

**适用场景:** 生产环境、完整监控、数据管理

**特点:**
- ✅ 所有标准模式服务
- ✅ PgAdmin 数据库管理
- ✅ Nginx 反向代理
- ✅ 日志聚合

**启动命令:**
```bash
# 启动核心服务
docker-compose up -d

# 启动管理工具
docker-compose --profile tools up -d

# 启动生产环境
docker-compose --profile production up -d
```

**访问地址:**
- API: http://localhost:8000
- PgAdmin: http://localhost:5050
- Nginx: http://localhost (如果启用)

---

## 🔧 配置说明

### 环境变量

主要配置项（在 `.env` 文件中）：

```bash
# 应用配置
ENVIRONMENT=production          # 环境: production/development
LOG_LEVEL=info                 # 日志级别: debug/info/warning/error
DEBUG=false                    # 调试模式

# 数据库配置
DATABASE_URL=postgresql://agentos:password@postgres:5432/agentos_db

# 安全配置
SECRET_KEY=your-secret-key     # 应用密钥（必须修改）
JWT_SECRET_KEY=your-jwt-secret # JWT 密钥（必须修改）

# LLM 配置
OPENAI_API_KEY=sk-...          # OpenAI API Key
ANTHROPIC_API_KEY=sk-ant-...   # Anthropic API Key

# CORS 配置
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

### 端口映射

| 服务 | 内部端口 | 外部端口 | 说明 |
|------|----------|----------|------|
| API | 8000 | 8000 | HTTP API |
| WebSocket | 8003 | 8003 | WebSocket 连接 |
| PostgreSQL | 5432 | 5432 | 数据库 |
| Redis | 6379 | 6379 | 缓存 |
| PgAdmin | 80 | 5050 | 数据库管理 |

### 数据持久化

数据存储在 Docker volumes 中：

```bash
# 查看所有 volumes
docker volume ls | grep agentos

# 备份数据
docker run --rm -v agentos-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/agentos-backup.tar.gz /data

# 恢复数据
docker run --rm -v agentos-data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/agentos-backup.tar.gz -C /
```

---

## 🛠️ 常用命令

### 服务管理

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 重启服务
docker-compose restart api

# 查看日志
docker-compose logs -f api

# 查看服务状态
docker-compose ps

# 进入容器
docker-compose exec api bash
```

### 数据库操作

```bash
# 连接 PostgreSQL
docker-compose exec postgres psql -U agentos -d agentos_db

# 运行数据库迁移
docker-compose exec api alembic upgrade head

# 备份数据库
docker-compose exec postgres pg_dump -U agentos agentos_db > backup.sql

# 恢复数据库
docker-compose exec -T postgres psql -U agentos agentos_db < backup.sql
```

### 日志查看

```bash
# 实时日志
docker-compose logs -f api

# 最近 100 行
docker-compose logs --tail=100 api

# 特定时间范围
docker-compose logs --since 2024-01-01T00:00:00 api
```

---

## 🔍 健康检查

### 检查服务状态

```bash
# API 健康检查
curl http://localhost:8000/health

# 查看容器健康状态
docker inspect agentos-api | jq '.[0].State.Health'

# 查看资源使用
docker stats agentos-api
```

### 常见问题排查

**1. 容器无法启动**

```bash
# 查看容器日志
docker-compose logs api

# 检查配置
docker-compose config

# 重新构建
docker-compose build --no-cache api
```

**2. 数据库连接失败**

```bash
# 检查 PostgreSQL 是否运行
docker-compose ps postgres

# 测试数据库连接
docker-compose exec postgres pg_isready -U agentos
```

**3. 端口被占用**

修改 `.env` 文件中的端口配置：
```bash
API_PORT=8001
POSTGRES_PORT=5433
```

---

## 📊 性能优化

### 资源限制

默认资源限制：

```yaml
api:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
      reservations:
        cpus: '0.5'
        memory: 512M
```

调整资源限制：
```bash
# 编辑 docker-compose.yml
# 或使用环境变量
docker-compose up -d --scale api=3
```

### 缓存优化

启用 Redis 缓存：
```bash
# 确保 Redis 服务运行
docker-compose up -d redis

# 配置缓存
REDIS_URL=redis://redis:6379/0
```

---

## 🔒 安全建议

### 生产环境配置

1. **修改默认密码**
   ```bash
   # 修改 .env 中的密码
   POSTGRES_PASSWORD=<strong-password>
   JWT_SECRET_KEY=<strong-secret>
   ```

2. **使用 HTTPS**
   ```bash
   # 启用 Nginx 反向代理
   docker-compose --profile production up -d
   ```

3. **限制网络访问**
   ```yaml
   # 只监听本地
   ports:
     - "127.0.0.1:8000:8000"
   ```

4. **定期更新**
   ```bash
   # 更新镜像
   docker-compose pull
   docker-compose up -d
   ```

---

## 🔄 更新与升级

### 更新应用

```bash
# 1. 拉取最新代码
git pull

# 2. 重新构建镜像
docker-compose build api

# 3. 重启服务
docker-compose up -d api

# 4. 运行数据库迁移
docker-compose exec api alembic upgrade head
```

### 备份与恢复

```bash
# 备份
./scripts/backup.sh

# 恢复
./scripts/restore.sh backup.tar.gz
```

---

## 📚 更多资源

- [Dockerfile 最佳实践](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [项目架构文档](ARCHITECTURE.md)
- [API 文档](docs/09-api/API_ENDPOINTS_COMPLETE.md)

---

## 🆘 获取帮助

- 查看 [FAQ](docs/11-deployment/FRONTEND_INTEGRATION_GUIDE.md#常见问题)
- 提交 [GitHub Issue](https://github.com/your-org/agentos/issues)
- 查看 [贡献指南](CONTRIBUTING.md)

---

**维护者:** AgentOS Team  
**最后更新:** 2026-02-09  
**许可证:** MIT
