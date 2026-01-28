# 📘 AgentOS Core: Phase 2 - Open Coze Platform Evolution

## 1. 产品愿景 (Product Vision)

将 AgentOS 从一个单纯的后端 Agent 框架，升级为开源版的 **"Coze Programming Platform"**。核心价值在于通过自然语言（Vibe Coding）和标准化技能（Skills）驱动云端沙盒，实现从“写代码”到“构建应用/数据分析”的闭环体验。

## 2. 新增核心特性 (New Features)

### 2.1 开放技能系统 (Coze-style Skills)

* **定义**: 抛弃硬编码的 Prompt，采用 **Markdown + YAML Frontmatter** 的方式定义技能。
* **兼容性**: 结构上参考 Coze/OpenWork 标准，支持热加载。
* **功能**:
* 用户可上传/编写 `.md` 文件作为技能。
* 系统自动解析元数据（名称、依赖工具）和 Prompt。
* Agent 运行时动态挂载技能，实现“角色切换”（如：从“Python 工程师”切换为“数据分析师”）。



### 2.2 富媒体可视化 (Rich Artifact Rendering)

* **目标**: 解决纯文本交互在数据分析、报表展示场景下的局限性。
* **技术**: 前端集成 **`@json-render`**。
* **交互**:
* 当 Agent 生成数据报表、统计结果或配置单时，不再输出 Markdown 表格，而是输出结构化 JSON。
* 前端自动识别该 JSON 并渲染为交互式图表、表格或表单。



### 2.3 深度编码能力 (Deep Vibe Coding)

* **Aider 全量集成**: 从当前的“轻量级文件操作”升级为“全功能 Aider”。
* 启用 **Repo Map**: 让 Agent 理解整个项目结构。
* 启用 **Tree-sitter**: 提高代码修改的准确性。
* 启用 **Linting/Auto-fix**: 代码写入后自动检查语法错误。



---

# 🛠️ 技术设计文档 (Technical Design Document v2.0)

## 1. 架构升级概览 (Architecture Update)

```mermaid
graph TD
    subgraph "Frontend (Web IDE)"
        IDE[Monaco Editor]
        Chat[Chat Interface]
        Render[Artifact Renderer\n(@json-render)]
    end

    subgraph "AgentOS Kernel (Python)"
        Orchestrator[LangGraph Loop]
        SkillMgr[Skill Manager (New)]
        Aider[Full Aider Adapter (Upgrade)]
    end

    subgraph "Infrastructure"
        Docker[Docker Sandbox]
        Mem[Mem0 Vector Store]
    end

    IDE <-->|WebSocket| Orchestrator
    Orchestrator --> SkillMgr
    Orchestrator --> Aider
    SkillMgr -->|Parse| MD[Markdown Skills]
    Aider -->|Exec| Docker

```

## 2. 模块详细设计

### 2.1 Skill Manager (新模块)

**目标**: 实现 Coze 风格的技能定义。

**文件格式规范 (`/skills/data_analyst.md`)**:

```markdown
---
name: "data_analyst"
description: "专业的金融数据分析师"
tools: ["read_file", "run_python_code", "generate_report"] # 依赖的工具ID
---
# Role
你是一名精通 Pandas 和 Matplotlib 的数据分析师。

# Constraints
1. 在分析数据前，必须先读取文件前 5 行查看结构。
2. 生成图表时，请输出 JSON 数据用于前端渲染。

```

**接口定义 (`src/agent_os/skills/manager.py`)**:

```python
class Skill(BaseModel):
    name: str
    description: str
    system_prompt: str
    tools: List[str]

class SkillManager:
    def load_skill(self, path: str) -> Skill:
        # 解析 Frontmatter 和 Markdown Body
        pass
    
    def apply_skill_to_agent(self, agent_state: dict, skill: Skill):
        # 1. 替换或追加 System Prompt
        # 2. 过滤/挂载 ToolRegistry 中的工具
        pass

```

### 2.2 可视化渲染协议 (Protocol & Frontend)

**目标**: 使用 `@json-render` 增强展示。

**通信协议变更 (WebSocket Event)**:
后端不再只发送 text，而是发送 `artifact` 事件。

```json
{
  "type": "artifact",
  "payload": {
    "title": "2024 Q1 销售分析",
    "renderer": "json-render", // 指定渲染引擎
    "schema": { ... }, // json-render 的 schema (formily/json-schema)
    "data": { ... }    // 实际数据
  }
}

```

**前端实现策略**:

1. 在 React 前端安装依赖: `npm install @json-render/core @json-render/vue3` (注：根据前端框架选择对应包，如果是 React 则用 React 版本)。
2. 在 Chat 组件中增加 `ArtifactBlock`。
3. 当收到 `renderer: "json-render"` 消息时，将 `schema` 和 `data` 传递给组件渲染。

### 2.3 Aider Adapter 升级 (Full Implementation)

**目标**: 激活 `FullAiderAdapter`。

**重构路径**:

1. **Repo Map 生成**: 在 `src/agent_os/coding/aider_adapter.py` 中，集成 Aider 的 `RepoMap` 类。每次用户提问前，生成当前沙盒的文件树压缩摘要。
2. **Linter 集成**: 在 `run_command` 后，如果检测到是 Python 文件修改，自动运行 `flake8` 或 `syntax check`，如果失败则自动回滚或让 Agent 重试。

---

# 📝 Claude Code 执行指南 (Execution Plan)

请按照以下顺序执行开发任务：

## Phase 2.1: 技能系统基础设施 (Skill System)

1. **创建目录**: `mkdir -p src/agent_os/skills/library`。
2. **实现解析器**: 编写 `SkillManager` 类，支持解析带有 YAML Frontmatter 的 Markdown 文件。使用 `python-frontmatter` 库（需添加到 `pyproject.toml`）。
3. **集成 LangGraph**: 修改 `Agent Loop`，在初始化或通过 `/skill` 指令时调用 `SkillManager`，动态更新 State 中的 `system_message`。
4. **添加示例技能**: 创建 `src/agent_os/skills/library/default_coder.md` 和 `analysis_expert.md`。

## Phase 2.2: 全功能 Aider 集成 (Coding Power)

1. **依赖注入**: 确保 `FullAiderAdapter` 被实例化并替代当前的 `SimpleAdapter`。
2. **Repo Map**: 移植 Aider 的 `get_repo_map()` 逻辑。确保它读取的是 **Docker Sandbox** 里的文件，而不是宿主机文件（通过 `env.read_file` 接口）。
3. **Diff 处理**: 优化 `apply_edit` 逻辑，支持 Unified Diff 格式的补丁应用。

## Phase 2.3: 可视化协议与前端 (Visualization)

1. **协议更新**: 在 `src/agent_os/core/protocol.py` (或相应位置) 增加 `ArtifactMessage` 类型。
2. **工具增强**: 编写一个专门的 Python 工具 `emit_visualization(data: dict, schema: dict)`，用于供 Agent 调用以生成图表。
3. **前端指令**: (留给前端开发者的说明) "请集成 @json-render，并监听 WebSocket 的 `artifact` 事件进行渲染。"

