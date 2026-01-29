# Skills System - 开发指南

**版本**: v1.0.0
**最后更新**: 2026-01-28
**状态**: ✅ 已完成并测试

---

## 目录

- [概述](#概述)
- [架构设计](#架构设计)
- [核心组件](#核心组件)
- [使用指南](#使用指南)
- [API参考](#api参考)
- [技能定义规范](#技能定义规范)
- [测试指南](#测试指南)
- [最佳实践](#最佳实践)

---

## 概述

Skills System是AgentOS Core的PRD2核心功能，实现了**Coze风格的开放技能系统**。它允许Agent通过Markdown + YAML Frontmatter文件动态切换角色和能力，无需修改代码即可扩展AI助手的功能。

### 核心特性

- ✅ **Markdown + YAML Frontmatter** - 简洁的技能定义格式
- ✅ **动态角色切换** - 运行时应用/切换技能
- ✅ **工具过滤** - 根据技能需求自动过滤可用工具
- ✅ **参数定制** - 每个技能可设置独立的temperature、max_tokens等参数
- ✅ **分类和标签** - 支持按category和tag组织技能
- ✅ **约束系统** - 定义技能的行为约束和规则

### 完成状态

| 模块 | 状态 | 测试 |
|------|------|------|
| SkillParser | ✅ 完成 | ✅ 7/7 通过 |
| SkillManager | ✅ 完成 | ✅ 9/9 通过 |
| Agent集成 | ✅ 完成 | ✅ 通过 |
| 示例技能库 | ✅ 完成 | 3个技能 |

---

## 架构设计

### 系统架构图

```
┌─────────────────────────────────────────────────────────┐
│                     Agent                               │
│  ┌───────────────────────────────────────────────────┐ │
│  │              SkillManager                          │ │
│  │  ┌──────────────┐      ┌──────────────────┐       │ │
│  │  │ SkillParser  │─────▶│  Skill Library   │       │ │
│  │  └──────────────┘      │  - default_coder  │       │ │
│  │         │               │  - data_analyst  │       │ │
│  │         │               │  - web_developer │       │ │
│  │         ▼               └──────────────────┘       │ │
│  │  ┌─────────────────────────────────────┐          │ │
│  │  │  Skills Dict (name -> Skill)        │          │ │
│  │  └─────────────────────────────────────┘          │ │
│  └───────────────────────────────────────────────────┘ │
│                          │                              │
│                          ▼                              │
│  ┌───────────────────────────────────────────────────┐ │
│  │              Agent State                           │ │
│  │  - system_prompt (modified by skill)              │ │
│  │  - active_skill (current skill name)              │ │
│  │  - temperature, max_tokens, model                  │ │
│  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 数据流

1. **技能加载**: SkillManager从目录读取.md文件 → SkillParser解析 → 存储到内存
2. **技能应用**: Agent.apply_skill(name) → 查找技能 → 修改agent_state → 过滤工具
3. **技能清除**: Agent.clear_skill() → 重置agent_state → 恢复默认行为

---

## 核心组件

### 1. SkillParser

负责解析Markdown + YAML Frontmatter格式的技能文件。

**位置**: `src/agent_os/skills/parser.py`

**核心方法**:
- `parse_file(file_path)` - 从文件解析
- `parse_content(content)` - 从字符串解析

**文件格式**:
```markdown
---
name: "skill_name"
description: "Skill description"
category: "coding"
version: "1.0.0"
tags: ["tag1", "tag2"]
tools: ["tool1", "tool2"]
temperature: 0.7
---

# Role
You are a skilled assistant...

# Constraints
- Constraint 1
- Constraint 2
```

### 2. SkillManager

管理技能的加载、缓存和应用。

**位置**: `src/agent_os/skills/manager.py`

**核心方法**:
- `load_skills_from_directory(directory)` - 批量加载技能
- `register_skill(skill)` - 注册单个技能
- `get_skill(name)` - 获取技能对象
- `list_skills(category, tag)` - 列出技能（支持过滤）
- `apply_skill(agent_state, skill_name, available_tools)` - 应用技能
- `clear_skill(agent_state)` - 清除技能

### 3. Skill (数据模型)

技能的数据结构定义。

**位置**: `src/agent_os/skills/models.py`

**字段说明**:
```python
class Skill(BaseModel):
    name: str                    # 唯一标识
    description: str             # 描述
    version: str                 # 版本号
    category: SkillCategory      # 分类
    tags: List[str]              # 标签
    system_prompt: str           # 系统提示词
    tools: List[str]             # 需要的工具
    constraints: List[str]       # 约束条件
    author: Optional[str]        # 作者
    temperature: Optional[float] # 温度参数
    max_tokens: Optional[int]    # 最大token数
    model: Optional[str]         # 模型名称
```

---

## 使用指南

### 基本使用

#### 1. 创建技能文件

在`src/agent_os/skills/library/`目录创建.md文件：

```markdown
---
name: "python_expert"
description: "Python编程专家"
category: "coding"
tags: ["python", "development"]
tools:
  - read_file
  - write_file
  - run_python
temperature: 0.2
---

# Role
You are an expert Python developer...

# Constraints
- Follow PEP 8 style guide
- Write docstrings for all functions
```

#### 2. 在Agent中使用

```python
from agent_os.agent import Agent

# 创建Agent
agent = Agent.from_config_file("config.yaml")

# 初始化技能系统
agent.initialize_skills()

# 列出可用技能
skills = agent.list_skills()
print(f"Available skills: {[s['name'] for s in skills]}")

# 应用技能
result = agent.apply_skill("python_expert")
if result['success']:
    print(f"Applied skill: {result['skill_name']}")
    print(f"Modified prompt: {result['modified_prompt'][:100]}...")
    print(f"Filtered tools: {result['filtered_tools']}")

# Agent现在使用python_expert技能进行对话
response = await agent.chat("Write a Python function to sort a list")

# 清除技能
agent.clear_skill()
```

### 高级使用

#### 按类别过滤技能

```python
# 只列出coding类别的技能
coding_skills = agent.list_skills(category="coding")

# 只列出包含"python"标签的技能
python_skills = agent.list_skills(tag="python")
```

#### 自定义技能目录

```python
# 从自定义目录加载技能
agent.initialize_skills(skills_directory="/path/to/custom/skills")
```

#### 程序化创建技能

```python
from agent_os.skills import SkillManager, Skill
from agent_os.skills.models import SkillCategory

# 创建SkillManager
manager = SkillManager()

# 创建技能对象
skill = Skill(
    name="custom_skill",
    description="Custom skill created programmatically",
    category=SkillCategory.CODING,
    system_prompt="You are a custom assistant",
    tools=["read_file", "write_file"],
    constraints=["Be helpful", "Be accurate"]
)

# 注册技能
manager.register_skill(skill)

# 应用技能
agent_state = {}
result = manager.apply_skill(
    agent_state=agent_state,
    skill_name="custom_skill",
    available_tools=["read_file", "write_file", "run_command"]
)
```

---

## API参考

### SkillParser

#### `parse_file(file_path: str | Path) -> Skill`

从Markdown文件解析技能。

**参数**:
- `file_path`: 技能文件路径

**返回**:
- `Skill`对象

**异常**:
- `SkillParseError`: 解析失败时抛出

#### `parse_content(content: str, source_file: str | None = None) -> Skill`

从Markdown内容字符串解析技能。

**参数**:
- `content`: Markdown内容（包含YAML frontmatter）
- `source_file`: 可选的源文件路径（用于错误信息）

**返回**:
- `Skill`对象

### SkillManager

#### `__init__(skills_directory: str | Path | None = None)`

初始化SkillManager。

**参数**:
- `skills_directory`: 可选的技能目录路径

#### `load_skills_from_directory(directory: str | Path, recursive: bool = False) -> Dict[str, Skill]`

从目录加载所有技能文件。

**参数**:
- `directory`: 技能目录路径
- `recursive`: 是否递归搜索子目录

**返回**:
- 加载的技能字典 {skill_name: Skill}

#### `apply_skill(agent_state: Dict, skill_name: str, available_tools: List[str]) -> SkillApplicationResult`

应用技能到Agent状态。

**参数**:
- `agent_state`: Agent状态字典
- `skill_name`: 要应用的技能名称
- `available_tools`: 当前可用的工具列表

**返回**:
- `SkillApplicationResult`对象，包含:
  - `success`: 是否成功
  - `skill_name`: 技能名称
  - `modified_prompt`: 修改后的系统提示
  - `filtered_tools`: 过滤后的工具列表
  - `error_message`: 错误信息（如果失败）

#### `list_skills(category: SkillCategory | None = None, tag: str | None = None) -> List[Skill]`

列出技能，支持过滤。

**参数**:
- `category`: 可选的类别过滤
- `tag`: 可选的标签过滤

**返回**:
- 匹配的技能列表

#### `clear_skill(agent_state: Dict) -> None`

清除当前应用的技能。

**参数**:
- `agent_state`: Agent状态字典

### Agent方法

#### `initialize_skills(skills_directory: str | Path | None = None) -> None`

初始化技能系统。

**参数**:
- `skills_directory`: 可选的自定义技能目录

#### `apply_skill(skill_name: str) -> Dict[str, Any]`

应用技能到Agent。

**参数**:
- `skill_name`: 技能名称

**返回**:
- 结果字典，包含success, skill_name, modified_prompt, filtered_tools等

#### `clear_skill() -> None`

清除当前应用的技能。

#### `list_skills(category: str | None = None, tag: str | None = None) -> List[Dict[str, Any]]`

列出可用技能。

**参数**:
- `category`: 可选的类别过滤
- `tag`: 可选的标签过滤

**返回**:
- 技能信息字典列表

#### `get_active_skill() -> str | None`

获取当前活动的技能名称。

**返回**:
- 技能名称或None

---

## 技能定义规范

### YAML Frontmatter字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `name` | string | ✅ | 技能唯一标识符 |
| `description` | string | ✅ | 技能描述 |
| `category` | string | ❌ | 技能类别（见下表） |
| `version` | string | ❌ | 版本号（默认"1.0.0"） |
| `author` | string | ❌ | 作者 |
| `tags` | array | ❌ | 标签列表 |
| `tools` | array | ❌ | 需要的工具列表 |
| `temperature` | float | ❌ | 温度参数（0.0-2.0） |
| `max_tokens` | int | ❌ | 最大token数 |
| `model` | string | ❌ | 指定模型 |

### 技能类别（SkillCategory）

| 值 | 说明 |
|----|------|
| `coding` | 编程开发 |
| `data_analysis` | 数据分析 |
| `writing` | 写作 |
| `research` | 研究调研 |
| `design` | 设计 |
| `management` | 管理 |
| `general` | 通用（默认） |

### Markdown Body结构

```markdown
# Role
[角色描述，定义AI的角色定位和能力]

# Constraints
[约束列表，每行一个，使用"-"开头]
- Constraint 1
- Constraint 2

# 其他可选章节
## Capabilities
[能力描述]

## Workflow
[工作流程]
```

### 示例技能文件

参见以下示例文件：
- `src/agent_os/skills/library/default_coder.md` - 默认编码助手
- `src/agent_os/skills/library/data_analyst.md` - 数据分析专家
- `src/agent_os/skills/library/web_developer.md` - Web开发专家

---

## 测试指南

### 运行测试

```bash
# 运行所有技能系统测试
pytest tests/test_skills.py -v

# 运行手动测试
python test_skills_manual.py

# 运行特定测试类
pytest tests/test_skills.py::TestSkillParser -v
pytest tests/test_skills.py::TestSkillManager -v
```

### 测试覆盖

当前测试覆盖：
- ✅ SkillParser: 7个测试（解析、错误处理、中文支持）
- ✅ SkillManager: 9个测试（加载、应用、过滤）
- ✅ Agent集成: 3个测试（初始化、应用、清除）
- ✅ 数据模型: 3个测试（创建、字段、枚举）

总计：**22个测试，全部通过**

### 添加新测试

创建新的测试用例：

```python
def test_my_new_skill():
    """Test a custom skill."""
    manager = SkillManager()

    # Create and register skill
    skill = Skill(
        name="test_skill",
        description="Test",
        system_prompt="You are a test assistant",
        tools=[]
    )
    manager.register_skill(skill)

    # Test the skill
    result = manager.apply_skill(
        agent_state={},
        skill_name="test_skill",
        available_tools=[]
    )

    assert result.success is True
```

---

## 最佳实践

### 1. 技能命名

- 使用小写字母和下划线：`python_expert`, `data_analyst`
- 使用描述性名称：避免`skill1`, `helper`等模糊名称
- 保持一致性：相同功能的技能使用相似命名模式

### 2. 系统提示词编写

- 明确定义角色和能力边界
- 提供具体的使用场景和示例
- 包含工作流程或步骤说明
- 避免过于宽泛或模糊的描述

好的提示词：
```
You are a Python expert specializing in data analysis with pandas.
When analyzing data, always:
1. Load and inspect the data first
2. Check for missing values
3. Provide visualizations when appropriate
```

不好的提示词：
```
You are helpful.
```

### 3. 约束设置

- 使用具体的、可执行的约束
- 按优先级排序约束
- 包含安全和质量相关的约束

示例：
```markdown
# Constraints
- Always read existing files before modifying
- Follow PEP 8 style guide for Python code
- Write docstrings for all functions
- Handle errors gracefully
- Test your code before considering it complete
```

### 4. 工具依赖

- 只列出技能真正需要的工具
- 考虑工具的可用性（如果工具不存在会警告）
- 优先使用通用工具而非特定工具

### 5. 参数调优

不同的任务可能需要不同的参数：

| 任务类型 | 推荐temperature | 推荐max_tokens |
|----------|----------------|----------------|
| 编码 | 0.1 - 0.3 | 2000 - 4000 |
| 创意写作 | 0.7 - 1.0 | 1000 - 2000 |
| 数据分析 | 0.2 - 0.4 | 1500 - 3000 |
| 技术文档 | 0.3 - 0.5 | 2000 - 4000 |

### 6. 版本管理

在技能文件中包含版本号，便于管理和升级：

```yaml
---
version: "1.0.0"
---
```

使用语义化版本号（Semantic Versioning）：
- `MAJOR.MINOR.PATCH`
- MAJOR: 不兼容的更改
- MINOR: 新增功能，向后兼容
- PATCH: Bug修复

### 7. 技能组织

建议的目录结构：

```
src/agent_os/skills/library/
├── coding/
│   ├── python_expert.md
│   ├── web_developer.md
│   └── system_programmer.md
├── data_analysis/
│   ├── data_analyst.md
│   └── ml_engineer.md
└── general/
    └── default_coder.md
```

---

## 故障排除

### 常见问题

#### 1. 技能加载失败

**症状**: `Loaded 0 skills from ...`

**可能原因**:
- 文件扩展名不是`.md`
- YAML格式错误
- 缺少必需的`name`字段

**解决方案**:
- 检查文件扩展名
- 验证YAML语法（使用在线YAML验证器）
- 确保包含`name`字段

#### 2. 技能应用失败

**症状**: `Skill not found: xxx`

**可能原因**:
- 技能名称拼写错误
- 技能文件未加载

**解决方案**:
- 使用`list_skills()`查看可用技能
- 检查技能文件的`name`字段
- 确保调用了`initialize_skills()`

#### 3. 工具过滤不正确

**症状**: 某些工具未包含在`filtered_tools`中

**可能原因**:
- 技能未在`tools`字段中列出该工具
- 工具不在`available_tools`列表中

**解决方案**:
- 检查技能文件的`tools`字段
- 确保`available_tools`包含所需工具

### 调试技巧

1. **启用详细输出**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

2. **检查技能对象**:
```python
skill = manager.get_skill("skill_name")
print(f"Skill: {skill.model_dump()}")
```

3. **验证agent_state**:
```python
result = agent.apply_skill("skill_name")
print(f"Agent state keys: {agent.agent_state.keys()}")
```

---

## 性能考虑

### 内存使用

- 每个技能对象约占用 1-5 KB 内存
- 100个技能约占用 100-500 KB
- 技能管理器使用字典存储，查找复杂度O(1)

### 加载时间

- 单个技能解析时间：~1-5 ms
- 100个技能加载时间：~100-500 ms
- 建议：启动时加载，运行时缓存

### 优化建议

1. **延迟加载**: 只在需要时加载技能目录
2. **技能缓存**: 避免重复解析相同的技能
3. **批量操作**: 使用`load_skills_from_directory`而非单个加载

---

## 未来扩展

### 计划中的功能

- [ ] 技能依赖关系管理
- [ ] 技能热重载（运行时更新）
- [ ] 技能市场/插件系统
- [ ] 技能版本控制和升级
- [ ] 技能分享和导入/导出
- [ ] 技能性能分析和优化建议
- [ ] 多语言技能文件支持

### 扩展点

系统设计支持以下扩展：

1. **自定义解析器**: 继承`SkillParser`支持其他格式
2. **自定义验证器**: 添加技能验证逻辑
3. **技能钩子**: 在应用/清除技能时执行自定义逻辑
4. **技能组合**: 支持同时应用多个技能

---

## 相关文档

- [PRD2 - Open Coze Platform Evolution](../01-prd/PRD2.md) - 产品需求文档
- [Architecture](architecture.md) - 系统架构
- [API Reference](api-reference.md) - 完整API文档
- [Testing Guide](../05-testing/testing-guide.md) - 测试指南

---

## 贡献指南

欢迎贡献新的技能！请遵循以下步骤：

1. Fork项目仓库
2. 创建技能文件：`src/agent_os/skills/library/your_skill.md`
3. 添加测试：`tests/test_skills.py`
4. 更新文档
5. 提交Pull Request

### 技能贡献模板

```markdown
---
name: "your_skill_name"
description: "Brief description"
category: "coding"
version: "1.0.0"
author: "Your Name <email@example.com>"
tags: ["tag1", "tag2"]
tools:
  - tool1
  - tool2
---

# Role
[Describe the role]

# Capabilities
[List capabilities]

# Constraints
- Constraint 1
- Constraint 2

# Workflow
1. Step 1
2. Step 2
```

---

**文档维护者**: AgentOS Development Team
**最后更新**: 2026-01-28
**文档版本**: 1.0.0
