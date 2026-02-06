# AgentOS Core

<div align="center">

**模块化的 AI 代理内核** | 微内核 + 插件架构

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[功能特性](#功能特性) • [快速开始](#快速开始) • [文档](#文档) • [开发计划](#开发计划)

</div>

---

## 项目简介

AgentOS Core 是一个高度模块化的 AI 代理内核，采用**微内核 + 插件架构**设计。通过严格的接口抽象和动态配置加载，实现核心模块的随意插拔，支持多种 LLM 提供商、记忆系统、上下文管理策略和编码能力。

### 核心特点

- **一切皆插件** - 所有核心模块均为接口，通过 `config.yaml` 动态加载实现
- **Skills System** - Coze风格的开放技能系统，支持动态角色切换 🆕
- **Server-Side Sandbox** - Docker/本地容器化隔离环境
- **Virtual IO** - WebSocket 通信，支持 Web/App/小程序多端
- **多模型支持** - 通过 LiteLLM 支持 OpenAI、Anthropic 等多种 LLM
- **编码能力** - 集成 Aider 的代码编辑和 Git 工作流
- **智能上下文** - Summarizer和KeyInfoExtractor策略 🆕

---

## 功能特性

### 已实现 ✅

| 模块 | 功能 | 状态 |
|------|------|------|
| **核心架构** | 接口定义、类型系统、动态配置 | ✅ 完成 |
| **LLM 集成** | LiteLLM 多模型支持 | ✅ 完成 |
| **Skills System** | 技能管理器、解析器、3个示例技能 | ✅ 完成 🆕 |
| **上下文管理** | 滑动窗口、Summarizer、KeyInfoExtractor | ✅ 完成 🆕 |
| **记忆系统** | Mem0 向量数据库、本地 JSON | 🟡 部分 |
| **工具系统** | 统一工具注册表 | ✅ 完成 |
| **编码能力** | Aider 适配器 | 🟡 部分 |
| **沙箱系统** | Docker/本地沙箱 | ✅ 完成 |
| **Web 服务器** | FastAPI + WebSocket | ✅ 完成 |
| **Web 前端** | Monaco Editor + 文件树 | ✅ 完成 |

### 总体完成度：90% (+5% Skills System)

详见 [开发进度追踪](docs/PROGRESS.md)

---

## 快速开始

### 🐳 方式一: Docker 部署 (推荐,无需安装 Python)

最简单的方式,无需手动安装任何依赖!

```bash
# 克隆项目
git clone https://github.com/yourusername/whyme.git
cd whyme

# 一键启动
bash docker-deploy.sh
```

或者手动启动:

```bash
# 使用 Docker Compose
docker-compose -f docker-compose.simple.yml up -d

# 或使用 Docker 原生命令
docker build -f Dockerfile.fast -t agentos:latest .
docker run -d --name agentos -p 8003:8003 agentos:latest
```

访问 http://localhost:8003 即可使用!

📖 **详细文档**: [DOCKER_QUICKSTART.md](./DOCKER_QUICKSTART.md) | [DOCKER.md](./DOCKER.md)

---

### 方式二: 本地安装

#### 环境要求

- Python 3.11 或更高版本
- pip 或 uv

#### 安装

```bash
# 克隆项目
git clone https://github.com/yourusername/whyme.git
cd whyme

# 安装依赖
pip install -e .

# 或使用 uv（推荐）
uv pip install -e .
```

### 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 添加 API 密钥
# OPENAI_API_KEY=sk-xxx
# ANTHROPIC_API_KEY=sk-ant-xxx
```

### 启动服务器

```bash
# 方式1：使用启动脚本（推荐）
python scripts/start.py

# 方式2：使用服务器脚本
python scripts/run_server.py

# 方式3：直接运行uvicorn
uvicorn src.agent_os.server.app:app --reload --port 8003
```

服务器将：
1. 自动使用 LocalSandbox（无需 Docker）
2. 在浏览器中打开 http://localhost:8003
3. 启用热重载

### 基本使用

1. 打开 http://localhost:8003
2. 在聊天框中输入指令，例如：
   - "创建一个 hello.py 文件，打印 Hello World"
   - "帮我写一个快速排序算法"
   - "分析当前目录的代码结构"
3. Agent 将自动执行并显示结果

### Skills System 使用 🆕

AgentOS Core 现在支持动态技能切换，让你可以快速改变AI助手的专业领域：

```python
from agent_os.agent import Agent

# 初始化Agent
agent = Agent.from_config_file("config.yaml")
agent.initialize_skills()

# 列出可用技能
skills = agent.list_skills()
for skill in skills:
    print(f"{skill['name']}: {skill['description']}")

# 应用技能 - 切换为数据分析专家
agent.apply_skill("data_analyst")
response = await agent.chat("分析这个CSV文件的数据趋势")

# 切换为Web开发专家
agent.apply_skill("web_developer")
response = await agent.chat("创建一个React组件显示用户列表")

# 清除技能，回到默认模式
agent.clear_skill()
```

**内置技能**:
- `default_coder` - 全栈开发专家
- `data_analyst` - 数据分析专家
- `web_developer` - Web开发专家

详见 [Skills System Guide](docs/03-toolkit/skills-system-guide.md)

---

## 配置说明

### config.yaml

```yaml
agent:
  name: "DevBot"

memory:
  provider: "agent_os.memory.local_json.LocalJSONProvider"
  # 或使用向量数据库
  # provider: "agent_os.memory.mem0_impl.Mem0Provider"
  config:
    storage_path: "./data/memory"

context:
  provider: "agent_os.context.sliding_window.SlidingWindowContext"
  config:
    max_tokens: 8000

llm:
  provider: "agent_os.llm.litellm_impl.LiteLLMProvider"
  config:
    model: "gpt-4"
    temperature: 0.7

coding:
  provider: "agent_os.capabilities.coding.aider_adapter.AiderAdapter"

sandbox:
  runtime: "local"  # 或 "docker"
  workspace: "./workspace"
```

---

## 文档

### 用户文档
- [快速开始指南](docs/04-guides/quickstart.md) - 新手入门教程
- [Toolkit管理指南](docs/04-guides/toolkit-management.md) - 工具箱使用说明
- [Docker部署指南](docs/04-guides/docker-setup.md) - 容器化部署

### 开发文档
- [API参考文档](docs/03-toolkit/api-reference.md) - 完整的API接口文档（前端团队）
- [前后端协作指南](docs/03-toolkit/collaboration-guidelines.md) - 团队协作规范
- [系统架构](docs/03-toolkit/architecture.md) - 技术架构设计
- [最新进度报告](docs/02-progress/latest-status.md) - 当前实现状态

### 产品文档
- [PRD0 - 产品概述](docs/01-prd/PRD0.md) - 产品需求文档概述
- [PRD1 - 架构规范](docs/01-prd/PRD1.md) - 详细的产品需求文档
- [PRD2 - Toolkit系统](docs/01-prd/PRD2.md) - Toolkit系统需求

### 测试文档
- [测试套件说明](tests/README.md) - 测试结构和运行方法
- [测试整理报告](docs/TEST_ORGANIZATION_REPORT.md) - 测试文件组织说明

---

## 架构设计

### 核心接口

```python
class MemoryProvider(ABC):
    async def add(self, ctx: RuntimeContext, content: str) -> str: ...
    async def search(self, ctx: RuntimeContext, query: str) -> List[Dict]: ...

class ContextManager(ABC):
    async def process(self, messages: List[Dict], max_tokens: int) -> tuple: ...

class ToolRegistry(ABC):
    async def register_python_tool(self, func: callable): ...
    async def execute(self, tool_name: str, arguments: Dict) -> Any: ...

class CodingCapability(ABC):
    async def apply_edit(self, ctx: RuntimeContext, instructions: str) -> str: ...
```

### 项目结构

```
.
├── src/agent_os/            # 核心代码
│   ├── core/               # 核心接口和类型定义
│   ├── memory/             # 记忆系统实现
│   ├── context/            # 上下文管理策略
│   ├── tools/              # 工具注册表
│   ├── llm/                # LLM 集成
│   ├── sandbox/            # 沙箱环境
│   ├── capabilities/       # 能力扩展（编码等）
│   ├── server/             # FastAPI 服务器和前端
│   └── agent.py            # Agent 主逻辑
│
├── tests/                  # 测试套件
│   ├── unit/               # 单元测试
│   ├── integration/        # 集成测试
│   ├── e2e/                # 端到端测试
│   └── temp/               # 临时测试
│
├── docs/                   # 文档
│   ├── 01-prd/             # 产品需求文档
│   ├── 02-progress/        # 进度报告
│   ├── 03-toolkit/         # Toolkit技术文档
│   ├── 04-guides/          # 用户指南
│   └── 05-testing/         # 测试报告
│
├── scripts/                # 可执行脚本
│   ├── run_server.py       # 启动服务器
│   └── start.py            # 备用启动脚本
│
├── logs/                   # 服务器日志（运行时生成）
├── tests-temp/             # 临时测试文件
├── screenshots/            # UI截图
│
├── config.yaml             # 主配置文件
├── pyproject.toml          # Python项目配置
├── docker-compose.yml      # Docker编排
├── Dockerfile              # Docker镜像
└── README.md               # 本文件
```

---

## 开发计划

### 最新完成 (2026-01-28) ✅

- ✅ **Skills System** (PRD2) - Coze风格开放技能系统
- ✅ **SummarizerContext** - LLM驱动的对话摘要
- ✅ **KeyInfoExtractor** - 关键信息提取策略
- ✅ **完整测试** - 22个单元测试 + 手动测试

### 高优先级 🔴

1. **WebSocketIO 线程安全修复**
   - 修复同步/异步混合调用问题
   - 确保线程安全的事件队列

2. **Diff 确认流程**
   - 实现后端 Diff 生成和发送
   - 处理用户确认/拒绝操作

3. **RepoMap 集成**
   - 集成Aider的RepoMap功能
   - 代码库结构理解

### 中优先级 🟡

4. **富媒体可视化** (PRD2)
   - Artifact协议定义
   - @json-render前端集成

5. **完整 Aider 集成**
   - 实例化 Aider Coder 类
   - Git 工作流支持
   - Tree-sitter语法解析

6. **记忆系统增强**
   - HippoRAG 集成
   - Mem0 云服务支持

详见 [开发进度追踪](docs/FINAL_DEVELOPMENT_SUMMARY.md)

---

## 技术栈

### 后端
- Python 3.11+
- FastAPI + Uvicorn
- LangGraph, LiteLLM
- Pydantic, YAML

### 前端
- Monaco Editor (VS Code 内核)
- WebSocket, REST API

### AI/ML
- sentence-transformers
- FAISS

---

## 贡献

欢迎贡献！请先阅读 [开发进度追踪](docs/PROGRESS.md) 了解当前的开发状态。

### 开发流程

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 致谢

- [Aider](https://github.com/paul-gauthier/aider) - AI 编码助手
- [LiteLLM](https://github.com/BerriAI/litellm) - 统一 LLM API
- [FastAPI](https://fastapi.tiangolo.com/) - 现代 Web 框架
- [LangGraph](https://github.com/langchain-ai/langgraph) - LLM 应用框架

---

<div align="center">

**[⬆ 返回顶部](#agentos-core)**

Made with ❤️ by the AgentOS Team

</div>
