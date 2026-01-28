# Prompt for Claude Code: 重构 Aider 以适配 MCP 与 Skills 系统

**目标**：对现有的 `mas_aider` 项目进行重构，使其具备扩展的工具调用能力。具体包括：

1. **Skills 系统**：支持通过 Python 脚本扩展能力（本地工具）。
2. **MCP 适配**：通过桥接脚本支持 Model Context Protocol 协议（远程工具）。
3. **CRUD 与热插拔**：允许 Aider 在运行时动态创建、列出、修改和删除工具，且立即生效。

**约束**：

* 保持 `mas_aider` 现有的 `AgentService` 和 `EnvironmentService` 架构。
* 不修改 Aider 源码，通过 `hooks` 或 `Environment` 注入方式实现。
* 工具必须以 CLI 形式暴露给 Aider。

---

## 第一部分：架构设计 (Architecture)

请在 `mas_aider/services` 和 `workspaces` 中实现以下文件结构和逻辑：

### 1. 文件结构定义

当 `EnvironmentService` 初始化工作区时，除了 `collab/` 目录，还需自动创建 `toolkit/` 目录：

```text
workspace_root/
├── collab/                 # (现有) 协作目录
├── toolkit/                # (新增) 工具箱根目录
│   ├── bins/               # 存放具体 Skill 脚本 (e.g. weather.py)
│   ├── mcp_servers/        # 存放 MCP Server 配置
│   ├── bridge.py           # 核心：MCP 协议桥接客户端
│   ├── manager.py          # 核心：工具增删查改管理器
│   └── registry.json       # 自动生成的工具清单 (这是热插拔的关键)
└── requirements.txt        # 工具依赖

```

### 2. 核心组件逻辑

* **Manager (manager.py)**:
* `list`: 扫描 `bins/` 下的脚本和 `mcp_servers/` 配置，生成人类可读的工具列表。
* `register`: 当 Aider 创建新脚本后，运行此命令更新 `registry.json`。
* `call`: 统一入口，如 `python toolkit/manager.py call <tool_name> <args>`。


* **Bridge (bridge.py)**:
* 实现一个轻量级的 MCP Client。
* 通过 `stdio` 启动 MCP Server 子进程。
* 将 Aider 的 CLI 参数转换为 JSON-RPC 请求发送给 Server。
* 将 Server 的 JSON 结果转换为纯文本输出。



---

## 第二部分：代码实现任务 (Implementation Tasks)

请按顺序执行以下代码编写任务：

### 任务 1：创建 MCP 桥接器 (`toolkit/bridge.py`)

编写一个 Python 脚本，功能如下：

* 依赖：使用 `mcp` 包 (需添加到依赖)。
* 输入：接收 Server 启动命令（如 `uvx -y @modelcontextprotocol/server-filesystem`）和工具名称、参数。
* 逻辑：建立连接 -> `list_tools` 校验 -> `call_tool` 执行 -> 打印结果。
* **关键点**：必须处理 `stdio` 通信，并具备超时处理机制。

### 任务 2：创建工具管理器 (`toolkit/manager.py`)

编写一个 CLI 工具，支持以下命令：

* `refresh`: 扫描 `toolkit/bins/*.py` 的 Docstring 和 `toolkit/mcp_servers/*.json`，生成 `tools_summary.md`。Aider 将通过读取这个 Markdown 文件来“感知”工具有哪些。
* `new <name>`: 创建一个标准化的 Skill 脚本模板。
* `add-mcp <name> <command>`: 创建一个 MCP 服务的 JSON 配置文件。

### 任务 3：修改 `EnvironmentService` (`mas_aider/services/environment_service.py`)

修改 `setup_workspace` 方法：

1. 在初始化时，将项目根目录下的 `global_toolkit/`（你需新建此模版目录）复制或软链接到 Agent 的 `workspace/toolkit/`。
2. 确保 Agent 有权限执行 `python toolkit/manager.py`。

### 任务 4：更新 System Prompt (`mas_aider/workflows/*.yaml`)

在 `collaboration.yaml` 和 `hulatang.yaml` 的 `roles` 定义中，追加以下 **Tool Use Protocol**：

```yaml
system_prompt_extension: |
  ## 🛠️ 工具箱 (Toolkit) 使用指南
  你拥有一个强大的工具箱，位于 `toolkit/` 目录。
  
  ### 1. 如何发现工具
  在开始任务前，请先运行以下命令查看可用工具：
  `/run python toolkit/manager.py list`
  
  ### 2. 如何调用工具
  - **本地 Skill**: 直接运行 `/run python toolkit/bins/<script_name>.py <args>`
  - **MCP 工具**: 运行 `/run python toolkit/bridge.py <config_name> <tool_name> '<json_args>'`
  
  ### 3. 如何扩展工具 (CRUD)
  - **创建新工具**: 直接编写新的 Python 脚本到 `toolkit/bins/` 目录，然后运行 `/run python toolkit/manager.py refresh`。
  - **修改工具**: 直接编辑 `toolkit/bins/` 下的代码，修改即时生效（热插拔）。
  - **删除工具**: `/run rm toolkit/bins/xxx.py`，然后运行 refresh。
  
  ⚠️ 所有的外部数据获取、复杂计算，请优先检查是否有现成工具，或者编写新工具来实现，而不是依靠你自己的训练数据猜测。

```

---

## 第三部分：CRUD 与 热插拔流程演示 (Workflow Demo)

请确保你的实现支持以下交互流程（这既是验收标准，也是给 Aider 的 Few-Shot 示例）：

**场景：Aider 发现没有天气工具，于是自己造一个并使用。**

1. **Search (查)**:
* Aider: `/run python toolkit/manager.py list`
* Output: "Current tools: [calc, file_search]. No weather tool found."


2. **Create (增)**:
* Aider: "I will create a weather tool using wttr.in."
* Aider creates file `toolkit/bins/weather.py`:
```python
import sys, requests
city = sys.argv[1]
print(requests.get(f"https://wttr.in/{city}?format=3").text)

```




3. **Refresh (热更新注册表)**:
* Aider: `/run python toolkit/manager.py refresh`
* Output: "Registry updated. Added: weather."


4. **Use (调用)**:
* Aider: `/run python toolkit/bins/weather.py Beijing`
* Output: "Beijing: ☀️ +25°C"



---

## 第四部分：执行步骤

请 Claude Code 执行以下操作：

1. 在项目根目录创建 `global_toolkit` 文件夹及基础代码 (`bridge.py`, `manager.py`)。
2. 修改 `mas_aider/services/environment_service.py` 加入初始化逻辑。
3. 更新 YAML 配置文件中的 Prompt。
4. 创建一个测试脚本 `test_toolkit.py`，模拟 Aider 调用流程，验证 MCP 和 Skill 的连通性。

**开始执行。**