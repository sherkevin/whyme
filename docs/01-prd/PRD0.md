# 🚀 AgentOS Core: Modular Architecture Specification (v2.0)

## 1. 设计哲学：一切皆插件 (Everything is a Plugin)

为了实现核心模块的随意插拔，我们定义一套严格的 **Python Protocol / ABC (Abstract Base Class)** 接口标准。系统启动时，通过 `config.yaml` 动态加载具体的实现类。

* **Memory**: 不绑定 Mem0，只定义 `MemoryProvider` 接口。
* **Context**: 不绑定具体策略，只定义 `ContextManager` 接口。
* **Tools**: 不区分 MCP 还是本地函数，统一抽象为 `ToolInterface`。
* **Coding**: Aider 只是 `CodingCapability` 的一种实现。

---

# 2. 产品需求文档 (PRD) - Refined

### 2.1 核心解耦需求

1. **Memory Swappability**: 用户可以在配置文件中将记忆后端从 `Mem0` 切换到 `HippoRAG` 或 `LocalJSON`，无需修改任何业务代码。
2. **Context Strategy**: 上下文压缩策略（如：滑动窗口、摘要总结、关键信息提取）应作为独立策略模块存在，可针对不同 Agent 配置不同策略。
3. **Universal Tool Registry**:
* 统一的注册中心，无论是 MCP Server、LangChain Tool 还是 Python 函数，注册后都变成统一的 `ExecutableTool` 对象。
* 支持**热加载**: 系统运行时可动态加载新的 Python 脚本文件作为工具集。



### 2.2 Aider 重构与集成需求

* **目标**: 提取 Aider 在 "代码库理解 (RepoMap)" 和 "Git Diff 应用" 方面的核心能力。
* **操作**: 拉取 Aider 源码，将其核心逻辑剥离，封装为 AgentOS 的一个 `Skill`。
* **去耦合**: Aider 的 CLI 交互逻辑（`io.py` 等）必须被抛弃，只保留核心逻辑（`coder/`, `repo/`）。

---

# 3. 技术设计文档 (TDD) - Component & Interface Level

## 3.1 系统架构图

```mermaid
graph TD
    subgraph "Configuration Layer"
        Config[config.yaml]
        Loader[Dynamic Class Loader]
    end

    subgraph "AgentOS Kernel (LangGraph)"
        Orchestrator[State Orchestrator]
    end

    subgraph "Abstract Interfaces (Protocols)"
        IMem[<<Interface>>\nMemoryProvider]
        ICtx[<<Interface>>\nContextManager]
        ITool[<<Interface>>\nToolRegistry]
        ILLM[<<Interface>>\nLLMProvider]
        ICode[<<Interface>>\nCodingCapability]
    end

    subgraph "Concrete Implementations (Plugins)"
        MemImpl1[Mem0 Adapter]
        MemImpl2[HippoRAG Adapter]
        
        CtxImpl1[Sliding Window]
        CtxImpl2[Summarizer]
        
        ToolImpl1[MCP Client]
        ToolImpl2[Python Decorator]
        
        AiderImpl[Aider Wrapper (Refactored)]
    end

    Config --> Loader
    Loader -- Inject --> Orchestrator
    Orchestrator --> IMem
    Orchestrator --> ICtx
    Orchestrator --> ITool
    Orchestrator --> ICode

    IMem <|.. MemImpl1
    IMem <|.. MemImpl2
    ICtx <|.. CtxImpl1
    ITool <|.. ToolImpl1
    ICode <|.. AiderImpl

```

## 3.2 核心接口定义 (Core Interfaces)

这是实现解耦的关键。Claude Code 在编写代码前必须先定义这些抽象类。

### A. Memory Provider

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class MemoryProvider(ABC):
    @abstractmethod
    async def add(self, content: str, metadata: Dict[str, Any] = None):
        """写入记忆"""
        pass

    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> List[Dict]:
        """检索记忆"""
        pass
    
    @abstractmethod
    async def clear(self, session_id: str):
        """清理上下文"""
        pass

```

### B. Context Manager

```python
class ContextManager(ABC):
    @abstractmethod
    async def prune(self, messages: List[Dict], max_tokens: int) -> List[Dict]:
        """裁剪或压缩消息历史"""
        pass

```

### C. Tool Registry

```python
class ToolRegistry(ABC):
    @abstractmethod
    def register_python_tool(self, func: callable):
        """注册本地函数"""
        pass
    
    @abstractmethod
    async def register_mcp_server(self, server_name: str, command: str, args: List[str]):
        """注册 MCP 服务"""
        pass
    
    @abstractmethod
    def get_tools_for_llm(self) -> List[Dict]:
        """获取适配 LLM 格式的工具定义 (JSON Schema)"""
        pass

```

## 3.3 Aider 重构策略 (The "Cannibalization" Plan)

我们需要引导 Claude Code 执行以下具体的重构步骤，将 Aider 转化为 `agent_os.skills.coding` 模块。

**目标结构**:

```text
src/agent_os/capabilities/coding/
├── __init__.py          # 暴露 CodingCapability 接口
├── aider_adapter.py     # 实现类
└── _vendor/             # 存放魔改后的 Aider 核心代码
    ├── repo_map.py      # 从 aider.repo_map 提取
    ├── commands.py      # 提取 git 操作
    └── diffs.py         # 提取 diff 应用逻辑

```

**重构指令**:

1. **Clone**: 拉取 `aider` 源码到临时目录。
2. **Analyze**: 重点分析 `aider/repo_map.py` (代码库拓扑图) 和 `aider/coders/` (编辑逻辑)。
3. **Extract**:
* **RepoMap**: 这是一个独立性很强的功能，直接抽取。
* **Git Management**: 抽取 Aider 对 Git 的封装（提交、脏检查）。
* **Edit Format**: 抽取 Aider 的 prompt 策略（它如何让 LLM 生成 diff），但不使用它的 loop。


4. **Wrap**: 编写 `AiderCodingCapability` 类实现上述 `CodingCapability` 接口。

---

# 4. 执行指南 (Prompt for Claude Code)

你可以直接复制以下内容给 Claude Code，开始项目构建：

```markdown
# Role
You are a Senior System Architect and Expert Python Engineer specialized in AI Agents.

# Task
Initialize the "AgentOS Core" project. We need a highly modular, decoupled architecture.
Follow the steps below strictly.

# Tech Stack
- Package Manager: `uv`
- Language: Python 3.11+
- Framework: LangGraph (Orchestration), LiteLLM (Model), FastAPI (Server)
- OS: Linux

# Step 1: Project Skeleton & Dependency Injection
1. Initialize a `uv` project.
2. Create the directory structure:
   src/agent_os/
     ├── core/interfaces.py  <-- Define ABCs here (MemoryProvider, ContextManager, ToolRegistry)
     ├── core/factory.py     <-- Factory to load classes from string paths in config
     ├── memory/             <-- Implementations (mem0_impl.py, simple_impl.py)
     ├── context/            <-- Implementations (window_impl.py)
     ├── tools/              <-- Implementations (mcp_registry.py, native_registry.py)
     └── main.py
3. Define the Abstract Base Classes (ABCs) as specified in the design document (MemoryProvider, etc.). **Decoupling is key.**

# Step 2: Aider Refactoring (The "Cannibalization")
1. We need Aider's "Repo Map" and "Git Diff" capabilities but NOT its CLI loop.
2. Create `src/agent_os/capabilities/coding/_vendor`.
3. Action: Clone the `aider` repository (paul-gauthier/aider) to a temp folder.
4. Copy `aider/repo_map.py` and `aider/grep.py` to `_vendor`.
5. Create an adapter class `src/agent_os/capabilities/coding/aider_adapter.py` that implements a `CodingCapability` interface.
   - This adapter should expose a method `generate_repo_map(root_dir: str) -> str`.
   - It should NOT depend on Aider's `InputOutput` or `Coder` classes directly if they are coupled to the CLI. Mock or refactor if necessary.

# Step 3: Tool & MCP Decoupling
1. Implement `ToolRegistry`.
2. It should allow registering a simple Python function via a `@tool` decorator.
3. It should allow registering an MCP Server (via stdio).
4. Provide a `to_openai_schema()` method that unifies both types for the LLM.

# Step 4: Configuration
Create a `config.yaml` example:

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

```

Start by creating the folder structure and the `core/interfaces.py` file to establish the contract.

```

```