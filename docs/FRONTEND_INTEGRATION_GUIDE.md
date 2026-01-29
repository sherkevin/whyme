# AgentOS 前端集成指南

**面向**: 前端开发同学
**目的**: 快速启动AgentOS后端服务进行集成测试
**更新时间**: 2026-01-29

---

## 🚀 一键启动 (推荐)

### 前置要求

确保已安装:
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac)
- 或 Docker Engine + Docker Compose (Linux)

### 快速启动

```bash
# 1. 克隆仓库
git clone https://github.com/sherkevin/whyme.git
cd whyme

# 2. 一键启动
docker-compose -f docker-compose.api.yml up -d

# 3. 查看日志
docker-compose -f docker-compose.api.yml logs -f api

# 4. 访问服务
# API文档: http://localhost:8000/docs
# API根路径: http://localhost:8000
```

### 验证服务

```bash
# 检查容器状态
docker-compose -f docker-compose.api.yml ps

# 测试API
curl http://localhost:8000/docs
curl http://localhost:8000/api/v1/auth/register
```

---

## 📚 核心API端点

### 1. 认证接口

```bash
# 注册
POST /api/v1/auth/register
Content-Type: application/json

{
  "username": "testuser",
  "email": "test@example.com",
  "password": "password123"
}

# 登录
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "testuser",
  "password": "password123"
}

# 返回
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### 2. 对话接口 (新增)

```bash
# 获取对话历史
GET /api/v1/conversations/{session_id}/history?user_id=1&limit=50

# 获取token统计
GET /api/v1/conversations/{session_id}/tokens?user_id=1

# 获取最近会话
GET /api/v1/conversations/sessions/recent?user_id=1&limit=10

# 删除消息
DELETE /api/v1/conversations/{conversation_id}?user_id=1
```

### 3. 聚合接口 (新增)

```bash
# 今日统一视图
GET /api/v1/today?user_id=1

# 返回
{
  "inbox_stats": {...},
  "tasks": [...],
  "knowledge": {...},
  "conversations": [...],
  "summary": {...}
}
```

### 4. 知识库接口

```bash
# 收件箱
POST /api/v1/knowledge/inbox
GET /api/v1/knowledge/cards
```

### 5. 任务接口

```bash
# 任务管理
POST /api/v1/tasks
GET /api/v1/tasks
```

---

## 🔧 配置说明

### 环境变量

编辑 `docker-compose.api.yml` 中的环境变量:

```yaml
environment:
  # API配置
  - API_KEY=your-api-key-here        # 你的API密钥
  - BASE_URL=http://localhost:8000   # API基础URL
  - CORS_ORIGINS=http://localhost:3000,http://localhost:5173  # 前端地址

  # LLM配置 (用于AI功能)
  - OPENAI_API_KEY=sk-...            # OpenAI API密钥
  - ANTHROPIC_API_KEY=sk-ant-...     # Anthropic API密钥
```

### CORS配置

默认允许的前端地址:
- `http://localhost:3000` (React开发服务器)
- `http://localhost:5173` (Vite开发服务器)

如需添加其他地址，修改环境变量:
```yaml
- CORS_ORIGINS=http://localhost:3000,http://localhost:5173,https://your-frontend.com
```

---

## 📊 数据库

### 默认配置 (SQLite)

开箱即用，数据存储在 `./data/agentos.db`

### 生产配置 (PostgreSQL)

如需使用PostgreSQL，取消注释 `docker-compose.api.yml` 中的postgres服务:

```yaml
services:
  api:
    depends_on:
      - postgres
    environment:
      - DATABASE_URL=postgresql+asyncpg://agentos:agentos123@postgres:5432/agentos_db

  postgres:
    # ... 已配置，取消注释即可
```

然后启动:
```bash
docker-compose -f docker-compose.api.yml --profile production up -d
```

---

## 🧪 测试API

### 使用Swagger UI

访问: http://localhost:8000/docs

提供交互式API文档，可直接测试所有接口。

### 使用curl示例

```bash
# 1. 注册用户
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123"
  }'

# 2. 登录获取token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "password123"
  }'

# 3. 使用token访问受保护接口
curl -X GET http://localhost:8000/api/v1/today?user_id=1 \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 使用Postman

1. 导入API定义
2. 设置环境变量:
   - `BASE_URL`: http://localhost:8000
   - `TOKEN`: (从登录接口获取)
3. 使用Bearer Token认证

---

## 🔌 WebSocket连接

### WebSocket端点

```
ws://localhost:8003/ws/chat/{session_id}
```

### 连接示例

```javascript
const ws = new WebSocket('ws://localhost:8003/ws/chat/session-123');

ws.onopen = () => {
  console.log('WebSocket connected');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};

// 发送消息
ws.send(JSON.stringify({
  type: 'chat',
  message: 'Hello, AgentOS!'
}));
```

### WebSocket事件类型

- `chat`: 聊天消息
- `tool_call`: 工具调用
- `diff_request`: Diff确认请求
- `error`: 错误信息

---

## 🐛 常见问题

### 1. 端口被占用

```bash
# 修改docker-compose.api.yml中的端口映射
ports:
  - "8001:8000"  # 改用8001端口
```

### 2. 数据库权限错误

```bash
# 确保data目录可写
chmod -R 777 ./data
```

### 3. CORS错误

```bash
# 检查并更新CORS_ORIGINS环境变量
# 确保包含你的前端地址
```

### 4. 容器无法启动

```bash
# 查看详细日志
docker-compose -f docker-compose.api.yml logs api

# 重建容器
docker-compose -f docker-compose.api.yml down
docker-compose -f docker-compose.api.yml build --no-cache
docker-compose -f docker-compose.api.yml up -d
```

---

## 📝 开发模式

### 代码热重载

修改 `src/` 目录下的代码会自动重载，无需重启容器。

### 查看日志

```bash
# 实时日志
docker-compose -f docker-compose.api.yml logs -f api

# 最近100行
docker-compose -f docker-compose.api.yml logs --tail=100 api
```

### 进入容器

```bash
# 进入容器shell
docker-compose -f docker-compose.api.yml exec api bash

# 运行测试
docker-compose -f docker-compose.api.yml exec api pytest tests/
```

---

## 🏗️ 项目结构

```
whyme/
├── src/agent_os/
│   ├── server/app.py          # FastAPI应用入口
│   ├── agent.py               # Agent核心逻辑
│   ├── conversations/         # 对话管理 (新增)
│   ├── aggregation/           # 聚合接口 (新增)
│   ├── auth/                  # 认证模块
│   ├── knowledge/             # 知识库
│   └── tasks/                 # 任务管理
├── tests/                     # 测试套件
├── docs/                      # 文档
├── docker-compose.api.yml     # Docker配置
├── Dockerfile.api             # API服务镜像
└── pyproject.toml             # Python依赖
```

---

## 🎯 快速集成示例

### React + TypeScript

```typescript
// api.ts
const API_BASE = 'http://localhost:8000';

export interface User {
  id: number;
  username: string;
  email: string;
}

export interface Message {
  id: number;
  role: 'user' | 'assistant' | 'tool';
  content: string;
  created_at: string;
}

// 登录
export async function login(username: string, password: string) {
  const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });

  if (!response.ok) throw new Error('Login failed');
  return response.json();
}

// 获取对话历史
export async function getConversationHistory(
  sessionId: string,
  userId: number,
  token: string
): Promise<Message[]> {
  const response = await fetch(
    `${API_BASE}/api/v1/conversations/${sessionId}/history?user_id=${userId}`,
    {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    }
  );

  if (!response.ok) throw new Error('Failed to fetch history');
  return response.json();
}

// 获取今日汇总
export async function getTodaySummary(userId: number, token: string) {
  const response = await fetch(
    `${API_BASE}/api/v1/today?user_id=${userId}`,
    {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    }
  );

  if (!response.ok) throw new Error('Failed to fetch summary');
  return response.json();
}
```

### Vue 3

```typescript
// composables/useAgentOS.ts
import { ref } from 'vue';

const API_BASE = 'http://localhost:8000';

export function useAgentOS() {
  const token = ref(localStorage.getItem('token') || '');
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'));

  const login = async (username: string, password: string) => {
    const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    const data = await response.json();
    token.value = data.access_token;
    localStorage.setItem('token', data.access_token);
    return data;
  };

  const getConversations = async (sessionId: string) => {
    const response = await fetch(
      `${API_BASE}/api/v1/conversations/${sessionId}/history?user_id=${user.value?.id}`,
      {
        headers: {
          'Authorization': `Bearer ${token.value}`,
        },
      }
    );

    return response.json();
  };

  return {
    token,
    user,
    login,
    getConversations,
  };
}
```

---

## 📖 更多文档

- [API完整文档](http://localhost:8000/docs) - Swagger UI
- [API端点总览](./API_ENDPOINTS_COMPLETE.md)
- [数据库架构](./DATABASE_ARCHITECTURE.md)
- [系统修复报告](./SYSTEM_FIXES_COMPLETION_REPORT.md)

---

## 🆘 获取帮助

### 问题排查流程

1. **检查容器状态**
   ```bash
   docker-compose -f docker-compose.api.yml ps
   ```

2. **查看日志**
   ```bash
   docker-compose -f docker-compose.api.yml logs -f api
   ```

3. **重启服务**
   ```bash
   docker-compose -f docker-compose.api.yml restart api
   ```

4. **完全重建**
   ```bash
   docker-compose -f docker-compose.api.yml down
   docker-compose -f docker-compose.api.yml build --no-cache
   docker-compose -f docker-compose.api.yml up -d
   ```

### 联系方式

- 查看项目文档: `docs/`
- 查看测试用例: `tests/`
- GitHub Issues: https://github.com/sherkevin/whyme/issues

---

## ✅ 启动检查清单

启动后，验证以下项目:

- [ ] 容器正常运行: `docker ps`
- [ ] API文档可访问: http://localhost:8000/docs
- [ ] 可以注册新用户
- [ ] 可以登录获取token
- [ ] 可以获取今日汇总
- [ ] 可以获取对话历史
- [ ] WebSocket可以连接
- [ ] CORS配置正确

---

**最后更新**: 2026-01-29
**维护者**: AgentOS Team
**状态**: 生产就绪 🚀
