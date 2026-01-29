# 🚀 快速启动指南

> **前端同学**: 按照以下步骤3分钟内启动后端服务

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
# 或
docker-compose -f docker-compose.api.yml logs -f api
```

### 停止服务

```bash
make stop
# 或
docker-compose -f docker-compose.api.yml down
```

---

## 方式三: 手动启动

### 1. 检查Docker

```bash
docker --version
docker info
```

### 2. 启动服务

```bash
# 创建数据目录
mkdir -p data logs

# 启动
docker-compose -f docker-compose.api.yml up -d
```

### 3. 验证服务

```bash
# 检查容器状态
docker ps

# 测试API
curl http://localhost:8000/docs
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

## 📚 更多文档

- [完整前端集成指南](docs/FRONTEND_INTEGRATION_GUIDE.md)
- [API端点总览](docs/API_ENDPOINTS_COMPLETE.md)
- [数据库架构](docs/DATABASE_ARCHITECTURE.md)

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

---

## 🎯 下一步

1. ✅ 服务已启动
2. 📖 访问 http://localhost:8000/docs
3. 🧪 测试API接口
4. 🔌 集成到你的前端应用

**需要帮助?** 查看 [前端集成指南](docs/FRONTEND_INTEGRATION_GUIDE.md)

---

**最后更新**: 2026-01-29
