# AgentOS Docker 部署指南

本文档介绍如何使用 Docker 快速部署 AgentOS 应用。

## 📋 前置要求

- Docker 20.10+
- Docker Compose 2.0+ (可选)
- 至少 4GB 可用内存
- 至少 10GB 可用磁盘空间

## 🚀 快速开始

### 方式一: 使用 Docker Compose (推荐)

最简单的方式,一键启动完整的应用:

```bash
# 1. 克隆项目
git clone <repository-url>
cd whyme

# 2. (可选) 配置环境变量
cp .env.example .env
# 编辑 .env 文件,添加你的 API 密钥

# 3. 启动应用
docker-compose -f docker-compose.simple.yml up -d

# 4. 查看日志
docker-compose -f docker-compose.simple.yml logs -f

# 5. 访问应用
# 浏览器打开: http://localhost:8003
```

### 方式二: 手动构建和运行

如果需要更多控制,可以手动构建和运行:

```bash
# 1. 构建 Docker 镜像
docker build -f Dockerfile.app -t agentos:latest .

# 2. 运行容器
docker run -d \
  --name agentos-app \
  -p 8003:8003 \
  -v agentos-data:/app/data \
  -e OPENAI_API_KEY=your-api-key \
  -e ANTHROPIC_API_KEY=your-api-key \
  --restart unless-stopped \
  agentos:latest

# 3. 查看日志
docker logs -f agentos-app
```

## 🔧 环境变量配置

### 基础配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HOST` | 0.0.0.0 | 监听地址 |
| `PORT` | 8003 | 监听端口 |
| `LOG_LEVEL` | info | 日志级别 (debug/info/warning/error) |
| `AGENTOS_SANDBOX` | local | 沙箱模式 (local/docker) |

### API 密钥配置

| 变量 | 说明 | 必需 |
|------|------|------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | 可选* |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | 可选* |
| `MODEL` | 默认模型 | 可选 |

*至少需要配置一个 LLM 提供商的 API 密钥

### 数据库配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | sqlite+aiosqlite:///./data/agentos.db | 数据库连接字符串 |

### 安全配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SECRET_KEY` | agentos-secret-key-change-in-production | JWT 密钥 (生产环境请修改) |
| `ALGORITHM` | HS256 | JWT 算法 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 30 | 访问令牌过期时间(分钟) |

## 📂 数据持久化

默认情况下,应用数据存储在 Docker volume 中:

```bash
# 查看数据卷
docker volume ls

# 备份数据
docker run --rm -v agentos-data:/data -v $(pwd):/backup \
  ubuntu tar czf /backup/agentos-backup.tar.gz /data

# 恢复数据
docker run --rm -v agentos-data:/data -v $(pwd):/backup \
  ubuntu tar xzf /backup/agentos-backup.tar.gz -C /
```

## 🔍 常用命令

### Docker Compose 命令

```bash
# 启动服务
docker-compose -f docker-compose.simple.yml up -d

# 停止服务
docker-compose -f docker-compose.simple.yml down

# 重启服务
docker-compose -f docker-compose.simple.yml restart

# 查看日志
docker-compose -f docker-compose.simple.yml logs -f

# 查看服务状态
docker-compose -f docker-compose.simple.yml ps

# 进入容器
docker-compose -f docker-compose.simple.yml exec agentos bash

# 更新并重建
docker-compose -f docker-compose.simple.yml up -d --build
```

### Docker 原生命令

```bash
# 查看运行中的容器
docker ps

# 查看容器日志
docker logs -f agentos-app

# 进入容器
docker exec -it agentos-app bash

# 停止容器
docker stop agentos-app

# 启动容器
docker start agentos-app

# 删除容器
docker rm agentos-app

# 删除镜像
docker rmi agentos:latest
```

## 🔧 故障排查

### 容器无法启动

```bash
# 查看容器日志
docker logs agentos-app

# 检查容器状态
docker ps -a

# 检查健康状态
docker inspect agentos-app | grep -A 10 Health
```

### 端口被占用

```bash
# 修改 docker-compose.yml 中的端口映射
ports:
  - "8004:8003"  # 使用 8004 端口
```

### 内存不足

```bash
# 增加 Docker 内存限制
docker run -d \
  --name agentos-app \
  --memory=4g \
  --memory-swap=4g \
  ...
```

### 数据卷问题

```bash
# 清理并重新创建数据卷
docker-compose -f docker-compose.simple.yml down -v
docker-compose -f docker-compose.simple.yml up -d
```

## 🚀 生产环境部署

### 使用 Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8003;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 使用 HTTPS (Let's Encrypt)

```bash
# 安装 certbot
sudo apt-get install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo certbot renew --dry-run
```

### 性能优化

1. **使用多阶段构建**: 已在 Dockerfile.app 中实现
2. **启用缓存**: 使用 Docker BuildKit
   ```bash
   DOCKER_BUILDKIT=1 docker build -f Dockerfile.app -t agentos:latest .
   ```
3. **限制资源使用**:
   ```yaml
   services:
     agentos:
       deploy:
         resources:
           limits:
             cpus: '2'
             memory: 4G
           reservations:
             cpus: '1'
             memory: 2G
   ```

## 📊 监控和日志

### 查看资源使用

```bash
# 实时监控
docker stats agentos-app

# 详细信息
docker inspect agentos-app
```

### 日志管理

```bash
# 查看最近 100 行日志
docker logs --tail 100 agentos-app

# 查看最近 10 分钟的日志
docker logs --since 10m agentos-app

# 导出日志
docker logs agentos-app > agentos.log
```

## 🔐 安全建议

1. **修改默认密钥**:
   ```bash
   # 生成随机密钥
   openssl rand -hex 32
   ```

2. **使用非 root 用户**: 已在 Dockerfile 中实现

3. **限制容器权限**:
   ```bash
   docker run --read-only --tmpfs /tmp ...
   ```

4. **定期更新镜像**:
   ```bash
   docker pull agentos:latest
   docker-compose -f docker-compose.simple.yml up -d
   ```

## 📚 更多信息

- [Docker 官方文档](https://docs.docker.com/)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [AgentOS 主文档](./README.md)

## 🆘 获取帮助

如果遇到问题:

1. 检查 [故障排查](#故障排查) 部分
2. 查看 GitHub Issues
3. 联系技术支持

---

**Happy Coding! 🎉**
