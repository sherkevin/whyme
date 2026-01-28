# 🚀 AgentOS Core: Modular Architecture Specification (PRD1)

> PRD1 在 PRD0 基础上引入 **Server-Side Sandbox + Virtual IO** 架构，将 Aider 从本地 CLI 工具重构为远程开发环境，支持 Web/App/小程序多端。

## 1. 设计哲学：一切皆插件 (Everything is a Plugin)
- 通过严格的 Python Protocol / ABC 接口标准实现核心模块随意插拔，启动时由 `config.yaml` 动态加载实现类。
- 不绑定具体实现：Memory/Context/Tool/Coding 均为接口；实现以插件方式注入。

## 2. 产品需求文档 (PRD) - Refined (PRD1)

### 2.1 核心解耦需求（延续 PRD0）
1. **Memory Swappability**：配置可将记忆后端从 `Mem0` 切换到 `HippoRAG` 或 `LocalJSON`，无需改业务代码。
2. **Context Strategy**：上下文压缩策略（滑动窗口、摘要、关键信息提取）独立为策略模块，可按 Agent 配置。
3. **Universal Tool Registry**：统一注册中心抽象为 `ExecutableTool`；支持 MCP/本地函数，支持运行时热加载新的 Python 工具脚本。
4. **Coding Capability 可插拔**：Aider 只是 `CodingCapability` 的一个实现，其他实现可无感替换。

### 2.2 核心架构变更：Server-Side Sandbox with Virtual IO
> 目标：解决“文件系统隔离”和“交互模式不匹配”问题，保留 Aider 能力同时支持 Web/App 多端。

1) **沙盒 (Sandbox) 与文件系统**
- 每个 Session 启动独立 Docker/MicroVM，容器内 `/workspace` 为 Aider 的根目录。
- 工作区映射：容器挂载专用 Volume，保证 Aider 看到真实文件系统。
- 文件同步协议：
  - Web 端通过 API 读取/写入容器内文件；Aider 直接操作容器内文件，Git/Diff 逻辑无需降级。
  - 前端左侧展示文件树，点击加载文件内容；用户编辑后通过 API 保存到容器。

2) **虚拟 IO (Virtual IO) 与通信**
- 放弃解析 stdout，改为“劫持 IO”。继承并重写 Aider `InputOutput`，实现 `WebSocketIO`。
- `WebSocketIO` 将输出写入队列，由后端推送到 WebSocket；输入通过 WebSocket 事件唤醒阻塞的 `get_input`。
- 交互不再依赖 CLI；Web/App 以结构化 JSON 协议收发消息。

3) **结构化协议 (WebSocket JSON)**
- **后端 -> 前端 (Server Push)**
```json
{
  "type": "event",
  "payload": {
    "chunk": "I am looking at...",
    "action": "confirm_diff",
    "data": {"file": "main.py", "diff_content": "@@ -1,2 +1,3 @@..."},
    "fs_update": ["src/main.py", "README.md"],
    "status": "thinking" | "waiting_for_user" | "executing"
  }
}
```
- **前端 -> 后端 (User Action)**
```json
{
  "type": "input",
  "payload": {
    "text": "Yes, please apply.",
    "command": "/add src/main.py"
  }
}
```
- 结构化 action 便于小程序等弱渲染端以卡片方式展示（无需渲染复杂 Diff 文本）。

4) **文件系统 API（REST）**
- `GET /api/session/{id}/files/tree`：获取容器内文件树。
- `GET /api/session/{id}/files/content?path=...`：获取文件内容。
- `POST /api/session/{id}/files/save`：前端手动修改代码后写回容器（确保 Aider 感知最新状态）。

5) **多端适配策略 (Omnichannel)**
- **Web 端**：左侧文件树（REST）、中间 Monaco Editor、右侧 Chat (WebSocket)。满血模式，Diff 高亮、手动/自动改码共存。
- **小程序/App 端**：Chat-only。隐藏编辑器/文件树；收到 `confirm_diff` 以卡片交互（查看详情/确认/拒绝）；指令式体验。

6) **优势**
- Aider 零感知：仍在本地文件语义下工作，Git/Diff 完整。
- 前后端解耦：标准 JSON 通信，便于多端换皮。
- 扩展性：未来可切换到 SSH 隧道等“真本地”场景，核心逻辑不变。

### 2.3 Aider 重构与集成需求（调整为 Library + Virtual IO）
- **目标**：提取 Aider 的 RepoMap、Git Diff 应用等核心能力，作为 `CodingCapability` 插件。
- **操作**：拉取 Aider 源码，保留 `coder/`, `repo/` 核心；抛弃 CLI 交互逻辑 (`io.py` 原实现不再直接用)。
- **去耦合**：以库方式导入 `from aider.coders import Coder`，实例化时注入自定义 `WebSocketIO`，不再运行 `aider` 子进程。

---

## 3. 技术设计文档 (TDD) - Component & Interface Level

### 3.1 系统架构（更新）
- **Configuration Layer**：`config.yaml` + Dynamic Class Loader。
- **AgentOS Kernel (LangGraph)**：State Orchestrator。
- **Abstract Interfaces (Protocols)**：`MemoryProvider`、`ContextManager`、`ToolRegistry`、`LLMProvider`、`CodingCapability`。
- **Plugins (Implementations)**：Mem0/HippoRAG、Sliding Window/Summarizer、MCP Client/Python Decorator、Aider Wrapper 等。
- **Sandbox Layer**：Session-scoped Docker/MicroVM + `/workspace`。
- **IO Layer**：`WebSocketIO`（结构化 JSON 事件）、文件系统 REST API。

### 3.2 核心接口定义（锁定：RuntimeContext + Reports + OpenAI Schema）

#### 3.2.1 RuntimeContext & Reports (新增)
```python
# src/agent_os/core/types.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class RuntimeContext(BaseModel):
    """请求运行时上下文，贯穿调用链，保持接口无状态"""
    session_id: str
    user_id: str
    trace_id: str
    sandbox_id: Optional[str] = None  # Docker/MicroVM 容器 ID

class PruningReport(BaseModel):
    """上下文裁剪报告"""
    original_tokens: int
    remaining_tokens: int
    pruned_count: int
    strategy_used: str  # e.g., "sliding_window", "summary"
    summary_content: Optional[str] = None
```

#### 3.2.2 Interfaces
```python
# src/agent_os/core/interfaces.py
from abc import ABC, abstractmethod
from .types import RuntimeContext, PruningReport
from typing import List, Dict, Any

class MemoryProvider(ABC):
    @abstractmethod
    async def add(self, ctx: RuntimeContext, content: str, metadata: Dict[str, Any] = None) -> str:
        """写入记忆，返回 memory_id；必须按 ctx.user_id 隔离"""
        ...

    @abstractmethod
    async def search(self, ctx: RuntimeContext, query: str, limit: int = 5) -> List[Dict]:
        """检索记忆；返回含 score/id/metadata 的列表"""
        ...

class ContextManager(ABC):
    @abstractmethod
    async def process(self, messages: List[Dict], max_tokens: int) -> tuple[List[Dict], PruningReport]:
        """处理/裁剪上下文；返回 (处理后的消息, PruningReport)"""
        ...

class ToolRegistry(ABC):
    @abstractmethod
    async def register_python_tool(self, func: callable):
        """基于类型提示生成 OpenAI JSON Schema 并注册"""
        ...

    @abstractmethod
    async def register_mcp(self, name: str, command: str, args: List[str]):
        """注册 MCP（懒加载，不立即启动）"""
        ...

    @abstractmethod
    async def get_definitions(self) -> List[Dict[str, Any]]:
        """返回 OpenAI 格式工具定义列表: [{"type": "function", "function": {...}}]"""
        ...

    @abstractmethod
    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """执行工具：检查进程存活->必要时重启->JSON-RPC 调用，30s 超时"""
        ...

class CodingCapability(ABC):
    @abstractmethod
    async def apply_edit(self, ctx: RuntimeContext, instructions: str) -> str:
        """在 ctx.sandbox_id 指定的沙盒执行代码修改，返回结果/摘要"""
        ...
```

#### 3.2.3 Schema 内部标准
- 内部统一采用 **OpenAI Tool (type=function) JSON Schema** 作为 canonical format。
- Anthropic/其他模型通过 LiteLLM 在传输层自动转换，无需业务层维护双份 Schema。

#### 3.2.4 MCP 高可用策略
- **Lazy Connection**：首次调用时启动 MCP 进程。
- **Circuit Breaker/Restart**：调用失败若发现进程已退出（returncode 非空），尝试重启一次，再执行。
- **Process Manager**：`asyncio.subprocess` 管理生命周期，执行时设置 30s 超时。

### 3.3 Aider 重构策略 (Cannibalization Plan, Web 化后)
- 目录结构（保持）
```
src/agent_os/capabilities/coding/
├── __init__.py
├── aider_adapter.py         # AiderCodingCapability 实现，注入 WebSocketIO
└── _vendor/
    ├── repo_map.py
    ├── commands.py
    └── diffs.py
```
- **关键点**：
  1. 不运行 CLI；用库调用 + 自定义 IO。
  2. `WebSocketIO` 承担所有用户交互（请求输入、推送事件、fs 更新）。
  3. 保留 Git 安全带（脏检查、提交封装），支持 dry-run。
  4. Aider 依赖链：repo_map/diffs 及 git/rg/tree-sitter 等三方依赖须列出；仅 vendor 需要的核心文件，**明确排除** `aider/io.py`, `aider/main.py`。

### 3.4 IO 虚拟化示例（供实现参考）
```python
import asyncio
from aider.io import InputOutput

class WebSocketIO(InputOutput):
    def __init__(self, queue: asyncio.Queue, pretty=True, **kwargs):
        super().__init__(pretty=pretty, **kwargs)
        self.output_queue = queue
        self.input_event = asyncio.Event()
        self.user_input_buffer = None

    def tool_output(self, msg, log_only=False):
        if not log_only:
            self.output_queue.put_nowait({"type": "log", "content": msg})

    def get_input(self, prompt_text, *args, **kwargs):
        self.output_queue.put_nowait({"type": "request_input", "prompt": prompt_text})
        # 阻塞等待 WebSocket 侧调用 receive_input
        self.input_event.wait()
        result = self.user_input_buffer
        self.input_event.clear()
        self.user_input_buffer = None
        return result

    def receive_input(self, text):
        self.user_input_buffer = text
        self.input_event.set()
```

> 实现时应确保 Aider 运行在线程/任务中，避免阻塞主事件循环；`queue` 由后端 WebSocket handler 消费并推送到前端。

### 3.5 配置示例 (config.yaml)
```yaml
agent:
  name: "DevBot"

memory:
  provider: "src.agent_os.memory.mem0_impl.Mem0Provider"
  config:
    user_id: "kaiwen"

context:
  provider: "src.agent_os.context.window_impl.SlidingWindowContext"
  config:
    max_tokens: 8000

coding:
  provider: "src.agent_os.capabilities.coding.aider_adapter.AiderAdapter"

sandbox:
  runtime: "docker"
  image: "agentos/aider-runtime:latest"
  workspace: "/workspace"

io:
  websocket_path: "/ws"
  rest_prefix: "/api"
```

### 3.6 执行指南 (Prompt for Claude Code) 摘要
- 初始化 uv 项目与目录骨架；先定义 ABC 接口与工厂加载器。
- 引入 Sandbox + Virtual IO：后端提供 WebSocket 与文件 REST；Session 启动容器并挂载 `/workspace`。
- Aider 以库方式导入，实例化 `Coder` 时注入 `WebSocketIO`，确保无需解析 stdout。
- ToolRegistry 支持 Python/MCP 注册，输出统一 JSON Schema 给 LLM。

---

## 4. 验收与最小可用 (MVP)
- 能在容器内对示例仓库运行一条完整链路：文件树获取 -> 用户下发指令 -> Aider 生成/应用 diff -> fs_update 通知 -> 查看/确认结果。
- 核心接口 (Memory/Context/Tool/Coding) 已定义并有至少一个可运行实现。
- Web 端最小界面：文件树 + 编辑器 + Chat；小程序端 Chat-only 交互正常。
- 配置热插拔：更换 memory/context/coding provider 可不改业务代码。
