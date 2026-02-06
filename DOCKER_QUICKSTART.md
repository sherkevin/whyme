# 🐳 AgentOS Docker 快速部署

一键启动 AgentOS,无需手动安装任何依赖!

## ⚡ 快速开始

### 方式一: 一键部署脚本 (推荐)

```bash
# 运行一键部署脚本
bash docker-deploy.sh
```

脚本会自动:
- ✅ 检查 Docker 环境
- ✅ 构建应用镜像
- ✅ 启动服务容器
- ✅ 配置数据持久化

### 方式二: Docker Compose

```bash
# 1. 启动服务
docker-compose -f docker-compose.simple.yml up -d

# 2. 查看日志
docker-compose -f docker-compose.simple.yml logs -f

# 3. 访问应用
# 浏览器打开: http://localhost:8003
```

### 方式三: Docker 原生命令

```bash
# 1. 构建镜像
docker build -f Dockerfile.fast -t agentos:latest .

# 2. 运行容器
docker run -d \
  --name agentos \
  -p 8003:8003 \
  -v agentos-data:/app/data \
  agentos:latest

# 3. 查看日志
docker logs -f agentos
```

## 📦 文件说明

| 文件 | 说明 |
|------|------|
| `Dockerfile.fast` | 快速构建版本 (推荐) |
| `Dockerfile.app` | 多阶段构建优化版本 |
| `docker-compose.simple.yml` | Docker Compose 配置 |
| `docker-deploy.sh` | 一键部署脚本 |
| `requirements.txt` | Python 依赖列表 |
| `.dockerignore` | Docker 构建排除文件 |

## 🔧 配置 API 密钥

编辑 `.env` 文件添加你的 API 密钥:

```bash
# 复制示例配置
cp .env.example .env

# 编辑配置文件
nano .env
```

添加以下内容:

```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
MODEL=openai/gpt-4o-mini
```

## 📊 常用命令

### 查看服务状态

```bash
# Docker Compose
docker-compose -f docker-compose.simple.yml ps

# Docker 原生
docker ps -f name=agentos
```

### 查看日志

```bash
# Docker Compose
docker-compose -f docker-compose.simple.yml logs -f

# Docker 原生
docker logs -f agentos
```

### 停止服务

```bash
# Docker Compose
docker-compose -f docker-compose.simple.yml down

# Docker 原生
docker stop agentos
docker rm agentos
```

### 重启服务

```bash
# Docker Compose
docker-compose -f docker-compose.simple.yml restart

# Docker 原生
docker restart agentos
```

## 💾 数据持久化

数据存储在 Docker volume 中:

```bash
# 查看数据卷
docker volume ls | grep agentos

# 备份数据
docker run --rm \
  -v agentos-data:/data \
  -v $(pwd):/backup \
  ubuntu tar czf /backup/agentos-backup.tar.gz /data

# 恢复数据
docker run --rm \
  -v agentos-data:/data \
  -v $(pwd):/backup \
  ubuntu tar xzf /backup/agentos-backup.tar.gz -C /
```

## 🔍 故障排查

### 容器无法启动

```bash
# 查看详细日志
docker logs agentos

# 检查容器状态
docker ps -a

# 进入容器排查
docker exec -it agentos bash
```

### 端口被占用

修改 `docker-compose.simple.yml` 中的端口映射:

```yaml
ports:
  - "8004:8003"  # 使用 8004 端口
```

### 完全重置

```bash
# 停止并删除所有相关资源
docker-compose -f docker-compose.simple.yml down -v

# 删除镜像
docker rmi agentos:latest

# 重新构建
docker-compose -f docker-compose.simple.yml up -d --build
```

## 📚 更多文档

详细文档请查看 [DOCKER.md](./DOCKER.md)

## 🆘 获取帮助

遇到问题?

1. 查看 [故障排查](#故障排查) 部分
2. 查看完整文档 [DOCKER.md](./DOCKER.md)
3. 检查 [GitHub Issues](../../issues)

---

**Enjoy AgentOS! 🎉**
