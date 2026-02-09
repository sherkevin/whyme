# 🚀 AgentOS Docker 快速启动指南

> **最快速方式：3分钟启动服务**

---

## ⚡ 一键启动 (推荐)

### 使用启动脚本

```bash
# 1. 进入项目目录
cd agentos

# 2. 运行启动脚本
./start.sh
```

脚本会自动：
- ✅ 检查 Docker 环境
- ✅ 创建配置文件
- ✅ 启动所有服务
- ✅ 等待服务就绪

**完成！** 访问 http://localhost:8000/docs 查看 API 文档

---

## 📋 手动启动

### 步骤 1: 配置环境

```bash
# 复制环境配置
cp .env.example .env

# （可选）编辑配置
vim .env
```

### 步骤 2: 启动服务

```bash
# 开发模式（SQLite）
docker-compose -f docker-compose.quick.yml up -d

# 或标准模式（PostgreSQL）
docker-compose up -d
```

### 步骤 3: 验证服务

```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f api

# 测试 API
curl http://localhost:8000/docs
```

---

## 🎯 访问服务

| 服务 | 地址 | 说明 |
|------|------|------|
| API 文档 | http://localhost:8000/docs | Swagger UI |
| API 端点 | http://localhost:8000 | REST API |
| WebSocket | ws://localhost:8003 | WebSocket 连接 |

---

## 🛠️ 常用命令

```bash
# 查看日志
docker-compose logs -f api

# 停止服务
docker-compose down

# 重启服务
docker-compose restart api

# 进入容器
docker-compose exec api bash

# 更新服务
git pull
docker-compose build api
docker-compose up -d
```

---

## 📖 详细文档

- [完整部署指南](DOCKER_DEPLOYMENT.md)
- [架构文档](ARCHITECTURE.md)
- [API 文档](docs/09-api/API_ENDPOINTS_COMPLETE.md)

---

## 🆘 常见问题

### Q: Docker 未安装？

A: 请先安装 Docker Desktop: https://www.docker.com/products/docker-desktop/

### Q: 端口被占用？

A: 修改 `.env` 文件中的端口：
```bash
API_PORT=8001
WS_PORT=8004
```

### Q: 服务无法启动？

A: 查看详细日志：
```bash
docker-compose logs api
```

---

**维护者:** AgentOS Team  
**最后更新:** 2026-02-09
