# Toolkit系统 - 技术架构文档

**版本**: v1.0.0
**更新时间**: 2026-01-26

---

## 📋 目录
1. [系统概述](#系统概述)
2. [架构设计](#架构设计)
3. [API接口](#api接口)
4. [前端实现](#前端实现)
5. [数据模型](#数据模型)
6. [安全考虑](#安全考虑)

---

## 系统概述

### 什么是Toolkit？

Toolkit是AgentOS的核心扩展机制，允许每个项目通过**Skills**（Python脚本）和**MCP Servers**（Model Context Protocol服务器）来扩展AI Agent的能力。

### 核心特性

- ✅ **热插拔**: 动态添加/删除工具，无需重启服务
- ✅ **项目隔离**: 每个项目有独立的toolkit配置
- ✅ **文件管理**: 支持上传、编辑、删除工具文件
- ✅ **在线编辑**: 直接在浏览器中编辑代码
- ✅ **类型安全**: Python脚本和JSON配置的验证

---

## 架构设计

### 系统架构图

```
┌─────────────────────────────────────────────────────────┐
│                   AgentOS Studio                        │
│                                                          │
│  ┌────────────┐      ┌─────────────┐      ┌─────────┐ │
│  │  Frontend  │◄────►│   FastAPI   │◄────►│ Toolkit │ │
│  │  Browser  │      │   Backend   │      │ Manager │ │
│  └────────────┘      └─────────────┘      └─────────┘ │
│         │                   │                   │       │
│         │                   ▼                   ▼       │
│    Monaco Editor      REST API          File System   │
│    + File Upload    + WebSocket      + JSON Config   │
└─────────────────────────────────────────────────────────┘

Per-Project Workspace:
data/workspaces/{session_id}/
├── toolkit/
│   ├── bins/              # Skills (.py scripts)
│   │   ├── calculator.py
│   │   ├── weather.py
│   │   └── ...
│   ├── mcp_servers/       # MCP Configs (.json)
│   │   ├── filesystem.json
│   │   ├── database.json
│   │   └── ...
│   ├── registry.json      # Tool registry
│   └── manager.py         # Toolkit manager
```

### 组件说明

#### 1. ToolkitManager
**文件**: `src/agent_os/toolkit/manager.py`

**职责**:
- 管理技能和MCP服务器的注册表
- 处理工具的添加、删除、更新
- 提供工具查询接口
- 管理工具生命周期

**关键方法**:
```python
class ToolkitManager:
    def add_skill(self, name: str, code: str) -> None
    def remove_skill(self, name: str) -> None
    def list_skills(self) -> List[Dict]
    def get_skill(self, name: str) -> Dict

    def add_mcp_server(self, name: str, command: str) -> None
    def remove_mcp_server(self, name: str) -> None
    def list_mcp_servers(self) -> List[Dict]
    def get_mcp_server(self, name: str) -> Dict
```

#### 2. FastAPI后端
**文件**: `src/agent_os/server/app.py`

**路由设计**:
- `GET /api/sessions/{session_id}/toolkit/skills` - 列出技能
- `GET /api/sessions/{session_id}/toolkit/skills/{skill_name}` - 获取技能代码
- `POST /api/sessions/{session_id}/toolkit/skills` - 创建技能
- `PUT /api/sessions/{session_id}/toolkit/skills/{skill_name}` - 更新技能
- `DELETE /api/sessions/{session_id}/toolkit/skills/{skill_name}` - 删除技能
- `GET /api/sessions/{session_id}/toolkit/mcp-servers` - 列出MCP服务器
- `POST /api/sessions/{session_id}/toolkit/mcp-servers` - 添加MCP服务器
- `PUT /api/sessions/{session_id}/toolkit/mcp-servers/{server_name}` - 更新MCP服务器
- `DELETE /api/sessions/{session_id}/toolkit/mcp-servers/{server_name}` - 删除MCP服务器

#### 3. 前端界面
**文件**: `src/agent_os/server/static/index.html`

**主要组件**:
- Toolkit面板（Sidebar）
- 技能列表渲染
- MCP服务器列表渲染
- 上传模态框
- 编辑模态框

---

## API接口

### Skills API

#### 1. 列出所有技能
```http
GET /api/sessions/{session_id}/toolkit/skills
```

**响应**:
```json
{
  "skills": [
    {
      "name": "calculator",
      "description": "Calculator Skill - 安全的数学计算器",
      "file_path": "toolkit/bins/calculator.py"
    }
  ]
}
```

#### 2. 获取技能代码
```http
GET /api/sessions/{session_id}/toolkit/skills/{skill_name}
```

**响应**:
```json
{
  "name": "calculator",
  "code": "#!/usr/bin/env python3\n...",
  "description": "Calculator Skill"
}
```

#### 3. 创建技能
```http
POST /api/sessions/{session_id}/toolkit/skills
Content-Type: application/json

{
  "name": "my_skill"
}
```

**响应**:
```json
{
  "message": "Skill my_skill created successfully"
}
```

#### 4. 更新技能
```http
PUT /api/sessions/{session_id}/toolkit/skills/{skill_name}
Content-Type: application/json

{
  "code": "#!/usr/bin/env python3\n..."
}
```

#### 5. 删除技能
```http
DELETE /api/sessions/{session_id}/toolkit/skills/{skill_name}
```

### MCP Servers API

#### 1. 列出所有MCP服务器
```http
GET /api/sessions/{session_id}/toolkit/mcp-servers
```

**响应**:
```json
{
  "mcp_servers": [
    {
      "name": "filesystem",
      "command": "npx -y @modelcontextprotocol/server-filesystem /tmp",
      "description": "MCP Server: filesystem",
      "tools": []
    }
  ]
}
```

#### 2. 添加MCP服务器
```http
POST /api/sessions/{session_id}/toolkit/mcp-servers
Content-Type: application/json

{
  "name": "filesystem",
  "command": "npx -y @modelcontextprotocol/server-filesystem /tmp"
}
```

#### 3. 更新MCP服务器
```http
PUT /api/sessions/{session_id}/toolkit/mcp-servers/{server_name}
Content-Type: application/json

{
  "name": "filesystem",
  "command": "npx -y @modelcontextprotocol/server-filesystem /data"
}
```

#### 4. 删除MCP服务器
```http
DELETE /api/sessions/{session_id}/toolkit/mcp-servers/{server_name}
```

---

## 前端实现

### 1. Toolkit面板

**位置**: Sidebar中的独立面板

**触发方式**:
- 点击活动栏的🛠️图标
- 点击项目列表中的🛠️ Toolkit按钮

**界面结构**:
```
┌─────────────────────────────────┐
│ 🛠️ Toolkit (Project Name)      │
├─────────────────────────────────┤
│ [Skills] [MCP Servers]          │
├─────────────────────────────────┤
│ 💡 Skills are Python scripts... │
│ [+ New] [📤 Upload] [↻]         │
├─────────────────────────────────┤
│ 🔧 calculator                   │
│    Calculator Skill              │
│    [👁️ View] [✏️ Edit] [🗑️ Delete] │
├─────────────────────────────────┤
│ 🔧 weather                      │
│    Weather Skill                 │
│    [👁️ View] [✏️ Edit] [🗑️ Delete] │
└─────────────────────────────────┘
```

### 2. 技能查看模态框

**功能**: 展示技能详情而不编辑

**内容**:
- 技能名称
- 描述（从docstring提取）
- 文件信息（名称、路径、行数）
- 代码预览（前50行）

### 3. MCP编辑模态框

**功能**: 编辑MCP服务器JSON配置

**特性**:
- Server Name字段
- Command字段（monospace字体）
- JSON配置编辑器（200px高度）
- 实时同步：编辑字段自动更新JSON
- 验证：保存前检查JSON语法

### 4. 文件上传

**Skills上传流程**:
1. 点击"📤 Upload Skill"按钮
2. 选择.py文件
3. 读取文件内容
4. POST请求创建技能
5. PUT请求更新技能代码
6. 刷新技能列表

**MCP配置上传流程**:
1. 点击"📤 Upload Config"按钮
2. 选择.json文件
3. 解析JSON配置
4. 提取name和command
5. POST请求添加MCP服务器
6. 刷新MCP服务器列表

---

## 数据模型

### 1. Skill数据结构

```python
@dataclass
class Skill:
    name: str                    # 技能名称（文件名不含.py）
    description: str             # 从docstring提取
    file_path: str               # toolkit/bins/{name}.py
    code: str                   # Python代码
    created_at: datetime         # 创建时间
    updated_at: datetime         # 更新时间
```

### 2. MCP Server数据结构

```python
@dataclass
class MCPServer:
    name: str                   # 服务器名称
    command: str                # 启动命令
    description: str            # 描述信息
    tools: List[str]            # 可用工具列表
    config_path: str            # toolkit/mcp_servers/{name}.json
    created_at: datetime         # 创建时间
    updated_at: datetime         # 更新时间
```

### 3. Registry数据结构

```json
{
  "skills": {
    "calculator": {
      "name": "calculator",
      "description": "Calculator Skill",
      "file": "toolkit/bins/calculator.py",
      "enabled": true
    }
  },
  "mcp_servers": {
    "filesystem": {
      "name": "filesystem",
      "command": "npx -y @modelcontextprotocol/server-filesystem /tmp",
      "enabled": true
    }
  }
}
```

---

## 安全考虑

### 1. 文件路径验证

**问题**: 防止路径遍历攻击

**解决方案**:
```python
import os

def safe_join(workspace_root: str, user_path: str) -> str:
    """确保用户路径在workspace范围内"""
    full_path = os.path.abspath(os.path.join(workspace_root, user_path))
    if not full_path.startswith(os.path.abspath(workspace_root)):
        raise ValueError("Path traversal detected")
    return full_path
```

### 2. 代码执行隔离

**Skills执行**:
- 在项目workspace内执行
- 使用LocalSandbox或DockerSandbox隔离
- 限制文件系统访问范围

**MCP服务器**:
- 独立进程运行
- 使用npx进行沙箱隔离
- 资源限制（CPU、内存）

### 3. 输入验证

**Skills验证**:
- 文件扩展名检查（.py）
- Python语法验证
- 文件大小限制

**MCP验证**:
- JSON格式验证
- 必填字段检查（name, command）
- 命令安全检查

### 4. 权限控制

**当前实现**:
- 每个项目独立的toolkit
- 无法访问其他项目的工具
- 文件系统隔离

**未来增强**:
- 用户权限系统
- 工具审核机制
- 审计日志

---

## 性能优化

### 1. 懒加载
- Toolkit数据按需加载
- 技能代码仅在编辑时加载

### 2. 缓存策略
- 技能列表缓存（5分钟）
- MCP服务器列表缓存（5分钟）

### 3. 异步处理
- 文件上传异步处理
- 大文件分块上传（未来）

---

## 错误处理

### 1. API错误

```python
@app.post("/api/sessions/{session_id}/toolkit/skills")
async def create_skill(session_id: str, skill_data: dict):
    try:
        # 创建技能
        toolkit_manager.add_skill(...)
        return {"message": "Skill created"}
    except FileExistsError:
        raise HTTPException(status_code=400, detail="Skill already exists")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
```

### 2. 前端错误

```javascript
async function uploadSkillFile(files) {
    try {
        const res = await fetch(...);
        if (res.ok) {
            await refreshToolkit();
            alert('✅ Skill uploaded successfully!');
        } else {
            const error = await res.json();
            alert('Failed to upload: ' + error.detail);
        }
    } catch (err) {
        console.error('Upload error:', err);
        alert('Error uploading skill: ' + err.message);
    }
}
```

---

## 扩展性

### 1. 添加新的工具类型

**步骤**:
1. 定义新的数据模型
2. 实现Manager接口
3. 添加API端点
4. 更新前端UI

### 2. 插件系统

**设计考虑**:
- 插件发现机制
- 插件依赖管理
- 插件版本控制
- 插件市场集成

---

## 测试

### 单元测试
```python
def test_skill_creation():
    manager = ToolkitManager(workspace)
    manager.add_skill("test", "# Test code")
    assert "test" in manager.list_skills()

def test_mcp_server_addition():
    manager = ToolkitManager(workspace)
    manager.add_mcp_server("test", "echo server")
    servers = manager.list_mcp_servers()
    assert len(servers) == 1
```

### 集成测试
```python
def test_full_workflow():
    # 1. 创建技能
    client.post("/api/sessions/123/toolkit/skills", json={"name": "test"})

    # 2. 列出技能
    response = client.get("/api/sessions/123/toolkit/skills")
    assert "test" in response.json()["skills"][0]["name"]

    # 3. 删除技能
    client.delete("/api/sessions/123/toolkit/skills/test")
```

---

## 最佳实践

### 1. Skills开发
- 添加清晰的docstring
- 处理异常情况
- 提供使用示例
- 遵循PEP 8规范

### 2. MCP配置
- 使用绝对路径
- 添加描述信息
- 测试命令可用性
- 文档化工具列表

### 3. 错误处理
- 记录详细日志
- 提供用户友好的错误消息
- 实现重试机制
- 监控失败率

---

## 相关文档

- [用户指南](../04-guides/toolkit-management.md) - 如何使用Toolkit
- [API参考](api-reference.md) - 完整API文档
- [测试报告](../05-testing/test-summary.md) - 测试结果

---

**文档版本**: 1.0
**最后更新**: 2026-01-26
**维护者**: AgentOS Development Team
