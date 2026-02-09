# 🚀 AgentOS 快速启动指南

> **3分钟内启动后端服务**

---

## 方式一: Windows用户 (推荐)

### 一键启动

双击运行 `start.bat`

或手动执行:

```bash
# 1. 启动Docker Desktop
# 2. 双击 start.bat
# 3. 等待服务启动
# 4. 浏览器自动打开 http://localhost:8000/docs
```

### 常用命令

```bash
start.bat   # 启动服务
logs.bat    # 查看日志
stop.bat    # 停止服务
```

---

## 方式二: macOS/Linux用户

### 一键启动

```bash
# 启动服务
make start

# 或使用docker-compose
docker-compose -f docker-compose.api.yml up -d

# 查看日志
make logs
```

### 停止服务

```bash
make stop
# 或
docker-compose -f docker-compose.api.yml down
```

---

## 方式三: 开发模式

### 1. 安装依赖

```bash
# 使用 uv (推荐)
uv pip install -e .[dev]

# 或使用 pip
pip install -e .[dev]
```

### 2. 启动开发服务器

```bash
# 启动 API 服务
uvicorn agent_os.server.app:app --reload --host 0.0.0.0 --port 8000

# 启动 WebSocket 服务
uvicorn agent_os.server.ws_app:app --reload --host 0.0.0.0 --port 8003
```

### 3. 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行核心测试
pytest tests/test_websocket_io.py \
        tests/test_diff_confirmation.py \
        tests/test_conversation_persistence.py -v

# 测试覆盖率
pytest tests/ --cov=src/agent_os --cov-report=html
```

---

## ✅ 验证清单

启动后验证以下项目:

- [ ] 浏览器访问 http://localhost:8000/docs 正常
- [ ] Swagger UI可以加载
- [ ] 可以注册新用户
- [ ] 可以登录获取token
- [ ] 可以测试API接口

---

## 📱 快速测试

### 1. 注册用户

在Swagger UI中测试:

```
POST /api/v1/auth/register
{
  "username": "testuser",
  "email": "test@example.com",
  "password": "password123"
}
```

### 2. 登录

```
POST /api/v1/auth/login
{
  "username": "testuser",
  "password": "password123"
}
```

复制返回的 `access_token`

### 3. 测试对话接口

```
GET /api/v1/today?user_id=1
Headers:
  Authorization: Bearer <your_access_token>
```

---

## 🔧 配置CORS

如果遇到CORS错误，编辑 `docker-compose.api.yml`:

```yaml
environment:
  - CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

添加你的前端地址，然后重启:

```bash
docker-compose -f docker-compose.api.yml restart api
```

---

## 📊 主要API端点

### 认证
```
POST /api/v1/auth/register  # 用户注册
POST /api/v1/auth/login     # 用户登录
GET  /api/v1/auth/users/me  # 获取当前用户
```

### 对话
```
GET  /api/v1/conversations/{session_id}/history  # 获取对话历史
GET  /api/v1/conversations/{session_id}/tokens   # Token统计
GET  /api/v1/conversations/sessions/recent       # 最近会话
DELETE /api/v1/conversations/{conversation_id}   # 删除消息
```

### 聚合
```
GET /api/v1/today  # 今日统一视图
```

### 知识库
```
POST /api/v1/knowledge/inbox  # 添加到收件箱
GET  /api/v1/knowledge/cards  # 获取卡片列表
```

### 任务
```
POST /api/v1/tasks  # 创建任务
GET  /api/v1/tasks  # 获取任务列表
```

完整API文档: http://localhost:8000/docs

---

## 🆘 常见问题

### Q: 端口被占用?

A: 修改 `docker-compose.api.yml` 中的端口:
```yaml
ports:
  - "8001:8000"  # 改用8001
```

### Q: 容器启动失败?

A: 查看日志:
```bash
docker-compose -f docker-compose.api.yml logs api
```

### Q: 数据在哪里?

A: SQLite数据在 `./data/agentos.db`

### Q: 如何使用PostgreSQL?

A: 取消注释 `docker-compose.api.yml` 中的postgres服务

---

## 📚 更多文档

- [完整文档](docs/README.md)
- [API端点总览](docs/09-api/API_ENDPOINTS_COMPLETE.md)
- [数据库架构](docs/10-architecture/DATABASE_ARCHITECTURE.md)
- [前端集成指南](docs/11-deployment/FRONTEND_INTEGRATION_GUIDE.md)

---

## 🎯 下一步

1. ✅ 服务已启动
2. 📖 访问 http://localhost:8000/docs
3. 🧪 测试API接口
4. 🔌 集成到你的应用

---

**最后更新**: 2026-02-09
