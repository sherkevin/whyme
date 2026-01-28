# Toolkit管理 - 用户指南

**版本**: v1.0.0
**更新时间**: 2026-01-26

---

## 📚 目录
1. [快速开始](#快速开始)
2. [Skills管理](#skills管理)
3. [MCP服务器管理](#mcp服务器管理)
4. [项目隔离](#项目隔离)
5. [常见问题](#常见问题)

---

## 快速开始

### 什么是Toolkit？

Toolkit是AgentOS中每个项目独立的工具集，包含：
- **Skills**: Python脚本，扩展AI Agent的能力
- **MCP Servers**: Model Context Protocol服务器，提供外部工具

### 访问Toolkit

**方法1: 从活动栏**
1. 点击左侧活动栏的🛠️图标

**方法2: 从项目列表**
1. 点击📂 Projects按钮
2. 在项目列表中，点击[🛠️ Toolkit]按钮

Toolkit面板会打开，显示：
```
🛠️ Toolkit (My First Project)
```

标题显示当前正在管理的项目名称。

---

## Skills管理

### Skills是什么？

Skills是Python脚本文件（.py），AI Agent可以调用这些脚本来执行特定任务。

**示例Skills**:
- `calculator.py` - 数学计算
- `weather.py` - 获取天气信息
- `file_processor.py` - 文件处理

### 创建Skill

**步骤**:
1. 打开Toolkit面板
2. 确保在"Skills"标签
3.点击"+ New Skill"按钮
4. 输入技能名称（例如: `my_calculator`）
5. 按Enter
6. 在Monaco Editor中编写Python代码
7. 按Ctrl+S保存

**代码模板**:
```python
#!/usr/bin/env python3
"""
My Custom Skill
Description of what this skill does
"""

def my_function(arg1, arg2):
    """Do something useful"""
    result = arg1 + arg2
    return result

if __name__ == "__main__":
    import sys
    # 处理命令行参数
    if len(sys.argv) > 1:
        print(process_args(sys.argv[1:]))
    else:
        print("Usage: my_skill.py <args>")
```

### 上传Skill

**步骤**:
1. 点击"📤 Upload Skill"按钮
2. 选择.py文件
3. 等待上传完成
4. 看到"✅ Skill uploaded successfully!"提示

**要求**:
- 文件必须是.py格式
- 文件名将成为技能名称
- 建议添加清晰的docstring

### 查看Skill详情

**步骤**:
1. 在技能列表中找到目标技能
2. 点击"👁️ View"按钮
3. 查看模态框中的信息：
   - **描述**: 从docstring提取
   - **文件信息**: 名称、路径、行数
   - **代码预览**: 前50行代码

### 编辑Skill

**步骤**:
1. 点击"✏️ Edit"按钮（或直接点击技能项）
2. 在Monaco Editor中编辑代码
3. 按Ctrl+S保存更改

**Monaco Editor功能**:
- 语法高亮
- 代码折叠
- 自动缩进
- 括号匹配
- 多光标编辑

### 删除Skill

**步骤**:
1. 点击"🗑️ Delete"按钮
2. 确认删除
3. 技能从列表中移除

**注意**: 删除操作无法撤销，请谨慎操作。

### 使用Skill

AI Agent会自动发现并使用Toolkit中的Skills。你可以通过对话告诉AI使用特定技能：

```
你: 使用calculator技能计算15 * 27
AI: 我来使用calculator技能帮你计算...
AI: 15 * 27 = 405
```

---

## MCP服务器管理

### MCP Servers是什么？

MCP (Model Context Protocol) 服务器提供外部工具和数据处理能力。

**示例MCP Servers**:
- `filesystem` - 文件系统访问
- `database` - 数据库操作
- `web_search` - 网络搜索

### 添加MCP服务器

**方法1: 手动添加**
1. 切换到"MCP Servers"标签
2. 点击"+ Add Server"按钮
3. 输入服务器信息：
   - **Name**: 服务器名称（例如: `filesystem`）
   - **Command**: 启动命令（例如: `npx -y @modelcontextprotocol/server-filesystem /tmp`）
4. 点击OK

**方法2: 上传配置**
1. 点击"📤 Upload Config"按钮
2. 选择.json配置文件
3. 配置示例：
```json
{
  "name": "filesystem",
  "command": "npx -y @modelcontextprotocol/server-filesystem D:\\Data"
}
```

### 编辑MCP服务器

**步骤**:
1. 在MCP服务器列表中，点击"Edit"按钮
2. 在模态框中修改配置：
   - **Server Name**: 修改服务器名称
   - **Command**: 修改启动命令
   - **JSON Configuration**: 直接编辑完整JSON
3. 点击"Save Changes"

**实时同步特性**:
- 编辑Server Name或Command字段时，JSON自动更新
- 编辑JSON时，字段也会更新（如果格式正确）

### 删除MCP服务器

**步骤**:
1. 点击"Delete"按钮
2. 确认删除
3. 服务器从列表中移除

### MCP配置文件格式

**标准格式**:
```json
{
  "name": "server_name",
  "command": "npx -y @modelcontextprotocol/server-package <args>",
  "description": "MCP Server: server_name",
  "tools": []
}
```

**必填字段**:
- `name`: 服务器唯一标识
- `command`: 启动命令

**可选字段**:
- `description`: 描述信息
- `tools`: 工具列表（自动发现）

---

## 项目隔离

### 每项目独立的Toolkit

每个AgentOS项目都有自己独立的Toolkit：
- **Project A** 的Skills不会出现在 **Project B**
- **Project A** 的MCP服务器配置独立于 **Project B**

### 工作空间结构

```
data/workspaces/
├── project_a_session_id/
│   └── toolkit/
│       ├── bins/
│       │   ├── skill1.py      # Project A的技能
│       │   └── skill2.py
│       └── mcp_servers/
│           └── server1.json    # Project A的MCP配置
│
└── project_b_session_id/
    └── toolkit/
        ├── bins/
        │   ├── tool1.py       # Project B的技能（不同）
        │   └── tool2.py
        └── mcp_servers/
            └── server2.json   # Project B的MCP配置（不同）
```

### 切换项目Toolkit

**步骤**:
1. 点击📂 Projects按钮
2. 选择不同的项目
3. 点击该项目的[🛠️ Toolkit]按钮
4. Toolkit面板会显示该项目的工具

**界面提示**:
- Sidebar标题: `🛠️ Toolkit (Project Name)`
- 明确显示当前管理的项目

### 复制技能到其他项目

**方法1: 重新创建**
1. 在Project A，打开技能
2. 复制代码（Ctrl+A, Ctrl+C）
3. 切换到Project B
4. 创建新技能，粘贴代码（Ctrl+V）
5. 保存

**方法2: 文件复制**
```bash
# 复制技能文件
cp data/workspaces/project_a/toolkit/bins/skill.py \
   data/workspaces/project_b/toolkit/bins/skill.py

# 刷新Project B的Toolkit面板
```

---

## 常见问题

### Q1: 我创建了一个技能，但AI Agent找不到它？

**解决方案**:
1. 确保技能保存成功（看到"✅ saved"提示）
2. 刷新Toolkit面板（点击↻按钮）
3. 检查技能在正确的项目中
4. 确认技能代码语法正确

### Q2: 上传的技能文件在哪里？

**位置**: `data/workspaces/{project_name}/toolkit/bins/{skill_name}.py`

**查看**:
1. 打开Toolkit面板
2. 点击技能的"👁️ View"按钮
3. 查看"Path"字段

### Q3: 可以在同一项目中创建同名技能吗？

**不可以**。每个技能名称在项目中必须唯一。如果尝试创建同名技能，会收到错误提示。

### Q4: MCP服务器启动失败怎么办？

**检查项**:
1. 命令是否正确
2. 是否安装了必要的依赖（如Node.js、npx）
3. 路径是否存在
4. 端口是否被占用

**调试**:
```bash
# 手动测试命令
npx -y @modelcontextprotocol/server-filesystem /tmp

# 查看错误日志
cat data/workspaces/{project}/toolkit/mcp_servers/{server}.json
```

### Q5: 如何删除项目的所有工具？

**方法1: 手动删除**
1. 逐个删除Skills
2. 逐个删除MCP服务器

**方法2: 删除项目**
删除整个项目会连同Toolkit一起删除。**注意**: 此操作不可撤销！

### Q6: 编辑技能后，AI Agent会立即使用新版本吗？

**是的**。保存技能后，Toolkit会自动更新，AI Agent会立即使用新版本。

### Q7: 可以在Toolkit中添加子文件夹吗？

**当前不支持**。所有Skills必须直接在`toolkit/bins/`目录下，不能有子文件夹。

### Q8: MCP服务器可以同时运行多个吗？

**可以**。每个MCP服务器在独立进程中运行，互不干扰。

### Q9: 如何备份我的工具？

**备份Skills**:
```bash
# 备份整个Toolkit
cp -r data/workspaces/{project}/toolkit toolkit_backup
```

**导出单个Skill**:
1. 打开Skill进行编辑
2. 复制全部代码
3. 粘贴到本地文件

### Q10: 工具有大小限制吗？

**当前没有硬编码限制**，但建议：
- Skills: 保持简洁，< 1000行
- MCP配置: 通常很小（< 5KB）

---

## 高级用法

### 1. 技能模板

创建可重用的技能模板：

```python
#!/usr/bin/env python3
"""
{skill_name}
{description}
"""

import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="{description}")
    parser.add_argument("input", help="Input data")
    args = parser.parse_args()

    # 处理逻辑
    result = process(args.input)
    print(result)

def process(data):
    """处理数据并返回结果"""
    # 实现具体逻辑
    return data

if __name__ == "__main__":
    main()
```

### 2. 技能组合

让一个技能调用另一个技能：

```python
# main_skill.py
import subprocess

def complex_task():
    # 调用其他技能
    result1 = subprocess.run(
        ["python", "toolkit/bins/helper_skill.py", "arg1"],
        capture_output=True
    )

    # 处理结果
    output = result1.stdout.decode()

    # 继续处理
    return process_output(output)
```

### 3. MCP服务器链

配置MCP服务器使用其他MCP服务器：

```json
{
  "name": "orchestrator",
  "command": "npx -y my-mcp-orchestrator --mcp-config toolkit/mcp_servers"
}
```

---

## 最佳实践

### Skills开发
1. **清晰的docstring**: 帮助AI理解技能用途
2. **错误处理**: 捕获异常并提供友好的错误消息
3. **类型提示**: 使用Python类型注解
4. **单元测试**: 在本地测试技能逻辑
5. **文档注释**: 解释复杂逻辑

### MCP配置
1. **绝对路径**: 使用绝对路径避免路径问题
2. **环境变量**: 通过环境变量传递配置
3. **健康检查**: 确保服务器启动成功
4. **资源限制**: 设置合理的资源限制
5. **日志记录**: 记录服务器运行日志

---

## 相关文档

- [UI可视化指南](ui-visual-guide.md) - 界面截图和详细步骤
- [Docker部署指南](docker-setup.md) - 生产环境部署
- [测试报告](../05-testing/test-summary.md) - 功能测试结果

---

## 获取帮助

**遇到问题？**
1. 查看本文档的"常见问题"部分
2. 检查浏览器控制台的错误日志
3. 查看服务器日志：`cat data/workspaces/{project}/toolkit/*.log`
4. 提交Issue到GitHub仓库

---

**文档版本**: 1.0
**最后更新**: 2026-01-26
**维护者**: AgentOS Development Team
