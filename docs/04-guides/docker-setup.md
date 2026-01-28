# Docker 多用户隔离部署指南

本指南说明如何部署具有强隔离性的多用户 AgentOS 环境。

## 架构概述

```
┌─────────────────────────────────────────┐
│         AgentOS Server (Host)           │
│  ┌─────────────────────────────────┐   │
│  │    FastAPI + WebSocket Server   │   │
│  │    SessionManager               │   │
│  └──────────────┬──────────────────┘   │
│                 │                       │
│  ┌──────────────┴──────────────────┐   │
│  │     DockerSandbox Manager       │   │
│  │  (为每个用户会话创建独立容器)     │   │
│  └──┬──────────┬──────────┬────────┘   │
└─────┼──────────┼──────────┼────────────┘
      │          │          │
   ┌──▼──┐    ┌──▼──┐    ┌──▼──┐
   │User1│    │User2│    │User3│
   │ 🐳  │    │ 🐳  │    │ 🐳  │
   │     │    │     │    │     │
   │512MB│    │512MB│    │512MB│
   │50%CPU│   │50%CPU│   │50%CPU│
   └─────┘    └─────┘    └─────┘
```

## 安全隔离特性

### 1. 资源隔离
- **内存限制**: 默认每个容器 512MB
- **CPU限制**: 默认每个容器 50% CPU
- **磁盘限制**: /tmp 使用 tmpfs，限制 100MB

### 2. 权限隔离
- **非root用户**: 容器内以 `agentuser` (UID 1000) 运行
- **Capabilities限制**: Drop ALL，仅添加必要权限（CHOWN, DAC_OVERRIDE等）
- **No new privileges**: 防止权限提升
- **非特权容器**: privileged=false

### 3. 网络隔离
- 可配置完全禁用网络 (`network_disabled: true`)
- 或使用独立网络命名空间

### 4. 文件系统隔离
- 可选只读根文件系统 (`read_only: true`)
- 独立的 /workspace 工作目录
- Tmpfs 临时文件系统

## 部署步骤

### 1. 启动 Docker Desktop

确保 Docker Desktop 正在运行：

```bash
docker --version
docker ps
```

### 2. 构建 Ubuntu 运行时镜像

```bash
cd D:\Codes\whyme
docker build -t agentos-ubuntu:latest -f Dockerfile .
```

构建过程包括：
- Ubuntu 22.04 基础镜像
- Python 3.11 + 常用开发工具
- Node.js, Go, Rust 等多语言支持
- AI/ML 常用 Python 库（numpy, pandas, scikit-learn等）
- 非root用户配置

### 3. 修改环境变量

移除或修改 `.env` 文件中的：

```bash
# 删除或注释掉这一行以使用 Docker
# AGENTOS_SANDBOX=local

# 或者明确指定使用 docker
AGENTOS_SANDBOX=docker
```

### 4. 验证配置

检查 `config.yaml`:

```yaml
sandbox:
  runtime: "docker"
  image: "agentos-ubuntu:latest"
  workspace: "/workspace"
  memory_limit: "512m"
  cpu_quota: 50000  # 50% CPU
  network_disabled: false
  read_only: false
```

### 5. 启动服务器

```bash
# 方式1: 直接启动
cd D:\Codes\whyme
python start.py

# 方式2: 使用 uvicorn
uvicorn src.agent_os.server.app:app --host 0.0.0.0 --port 8003 --reload
```

### 6. 测试隔离性

#### 测试1: 创建多个会话

访问 http://localhost:8003，创建多个项目：
- 每个项目会获得独立的 Docker 容器
- 每个容器有独立的文件系统
- 容器之间完全隔离

#### 测试2: 验证资源限制

在容器内执行：

```python
# 测试内存限制
import numpy as np
# 尝试分配超过 512MB 的内存应该失败
arr = np.zeros((1024, 1024, 128), dtype=np.float64)  # ~1GB
```

#### 测试3: 验证权限隔离

```bash
# 这些操作应该失败或受限
cat /etc/shadow  # 无权限
mount /dev/sda1  # 无权限
```

## 监控和管理

### 查看运行中的容器

```bash
docker ps --filter "label=agentos.sandbox=true"
```

### 查看容器资源使用

```bash
docker stats $(docker ps --filter "label=agentos.sandbox=true" -q)
```

### 清理停止的容器

```bash
docker container prune --filter "label=agentos.sandbox=true"
```

### 查看容器日志

```bash
docker logs <container_id>
```

## 配置调优

### 提高资源限制（高性能需求）

```yaml
sandbox:
  memory_limit: "1g"      # 1GB 内存
  cpu_quota: 100000       # 100% CPU（一个完整核心）
```

### 加强安全（生产环境）

```yaml
sandbox:
  network_disabled: true  # 完全禁用网络
  read_only: true        # 只读文件系统（除 /workspace 和 /tmp）
```

### 降低资源消耗（开发环境）

```yaml
sandbox:
  memory_limit: "256m"   # 256MB 内存
  cpu_quota: 25000       # 25% CPU
```

## 故障排查

### 问题1: Docker daemon 未运行

**错误**: `error during connect: open //./pipe/dockerDesktopLinuxEngine`

**解决**: 启动 Docker Desktop

### 问题2: 镜像不存在

**错误**: `Image 'agentos-ubuntu:latest' not found`

**解决**:
```bash
docker build -t agentos-ubuntu:latest -f Dockerfile .
```

### 问题3: 容器创建失败

**错误**: `Failed to load DockerSandbox`

**解决**: 检查 Docker Desktop 是否有足够资源配置（Settings > Resources）

### 问题4: 权限错误

**错误**: 文件创建失败

**解决**: 确保 Dockerfile 中 `agentuser` 对 /workspace 有写权限

## 生产部署建议

1. **使用 Docker Compose** 进行编排
2. **配置日志收集**（如 ELK stack）
3. **设置容器自动清理**策略
4. **监控资源使用**（Prometheus + Grafana）
5. **定期更新基础镜像**确保安全补丁
6. **配置备份策略**保存用户工作区数据
7. **使用 Kubernetes** 实现更大规模的多租户隔离

## 对比表

| 特性 | LocalSandbox | DockerSandbox |
|------|--------------|---------------|
| 隔离性 | ❌ 弱 | ✅ 强 |
| 安全性 | ❌ 与主机共享 | ✅ 容器隔离 |
| 资源限制 | ❌ 无 | ✅ CPU/内存/磁盘 |
| 多用户 | ❌ 不安全 | ✅ 安全隔离 |
| 性能 | ✅ 原生速度 | ⚠️ 轻微开销 |
| 适用场景 | 个人开发 | 生产/多用户 |

## 下一步

- [ ] 配置持久化存储（volume mounts）
- [ ] 实现容器回收机制
- [ ] 添加容器健康检查
- [ ] 集成监控告警
- [ ] 实现用户配额管理
